import os
import io
import re
import json
import time
import asyncio
import logging
import sqlite3
import threading
import functools
from datetime import datetime, timezone
from contextlib import contextmanager

import aiohttp
from aiohttp import web
from PIL import Image
import discord
from discord.ext import commands
from telethon import TelegramClient, events
import primp

# ป้องกัน Error กรณีไม่มี zxingcpp บนเซิร์ฟเวอร์
try:
    import zxingcpp
    ZXING_AVAILABLE = True
except ImportError:
    ZXING_AVAILABLE = False

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
BANNER_URL = os.getenv("BANNER_URL", "https://i.postimg.cc/wxnxqqZ5/21exxc0mytmh1.gif")
DB_PATH = os.getenv("DB_PATH", "bot_users.db")

STATUS = {
    "VOUCHER_OUT_OF_STOCK": "ซองหมดแล้ว",
    "VOUCHER_REDEEMED": "ซองถูกแลกไปแล้ว",
    "VOUCHER_NOT_FOUND": "ไม่พบซองอั่งเปา",
    "VOUCHER_EXPIRED": "ซองหมดอายุ",
    "TARGET_USER_NOT_FOUND": "ไม่พบเบอร์โทรนี้ใน TrueWallet",
    "CANNOT_GET_OWN_VOUCHER": "ไม่สามารถรับซองของตัวเองได้",
}

SHORT_LINK_PATTERN = re.compile(
    r"https?://(?:"
    r"bit\.ly"
    r"|tinyurl\.com"
    r"|tmn\.app"
    r"|shorturl\.at"
    r"|shorturl\.asia"
    r"|nimble\.li"
    r"|rb\.gy"
    r"|cutt\.ly"
    r"|tiny\.cc"
    r"|is\.gd"
    r"|t\.ly"
    r"|ow\.ly"
    r"|buff\.ly"
    r"|adf\.ly"
    r"|shorte\.st"
    r"|clck\.ru"
    r")/\S+",
    re.I,
)

RAW_HASH_PATTERN = re.compile(r"\b([0-9A-Za-z]{32,36})\b")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

_db_local = threading.local()
_db_write_lock = threading.Lock()
_DB_RETRY = 5
_DB_RETRY_DELAY = 0.05


def _get_conn():
    conn = getattr(_db_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA cache_size=-8000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=134217728")
        _db_local.conn = conn
    return conn


@contextmanager
def db_read():
    conn = _get_conn()
    try:
        yield conn
    except sqlite3.DatabaseError:
        try:
            conn.close()
        except Exception:
            pass
        _db_local.conn = None
        raise


@contextmanager
def db_write():
    with _db_write_lock:
        conn = _get_conn()
        try:
            yield conn
            conn.commit()
        except sqlite3.DatabaseError:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            _db_local.conn = None
            raise


def _retry_db(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last_exc = None
        for attempt in range(_DB_RETRY):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                last_exc = exc
                logging.warning("DB retry %d/%d for %s: %s", attempt + 1, _DB_RETRY, fn.__name__, exc)
                time.sleep(_DB_RETRY_DELAY * (attempt + 1))
        raise last_exc
    return wrapper


def _run_in_executor(fn, *args):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, fn, *args)


@_retry_db
def init_db():
    with db_write() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_phone TEXT NOT NULL DEFAULT '',
                api_id TEXT NOT NULL DEFAULT '',
                api_hash TEXT NOT NULL DEFAULT '',
                truemoney_phone TEXT NOT NULL DEFAULT '',
                webhook_url TEXT NOT NULL DEFAULT '',
                notify_level INTEGER NOT NULL DEFAULT 0,
                is_running INTEGER NOT NULL DEFAULT 0,
                start_time TEXT,
                otp_phone_code_hash TEXT,
                otp_pending INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("CREATE TABLE IF NOT EXISTS global_stats (id INTEGER PRIMARY KEY CHECK (id = 1), lifetime_total REAL NOT NULL DEFAULT 0)")
        row = conn.execute("SELECT 1 FROM global_stats WHERE id = 1").fetchone()
        if not row:
            legacy_total = 0.0
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'history_%'")]
            for table in tables:
                if table[8:].isdigit():
                    total_row = conn.execute(f"SELECT COALESCE(SUM(amount_baht),0) FROM {table} WHERE status='success'").fetchone()
                    legacy_total += float(total_row[0] or 0)
            conn.execute("INSERT INTO global_stats (id, lifetime_total) VALUES (1, ?)", (legacy_total,))


@_retry_db
def get_user(user_id):
    cached = _user_cache.get(user_id)
    if cached is not None:
        return cached
    with db_read() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        result = dict(row) if row else None
        if result:
            _user_cache[user_id] = result
        return result


@_retry_db
def upsert_user(user_id, **values):
    with db_write() as conn:
        existing = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if existing:
            assignments = ", ".join(f"{key} = ?" for key in values)
            conn.execute(f"UPDATE users SET {assignments} WHERE user_id = ?", [*values.values(), user_id])
        else:
            merged = {"telegram_phone": "", "api_id": "", "api_hash": "", "truemoney_phone": "", "webhook_url": "", **values}
            columns = ["user_id", *merged.keys()]
            marks = ",".join("?" for _ in columns)
            conn.execute(f"INSERT INTO users ({','.join(columns)}) VALUES ({marks})", [user_id, *merged.values()])
    cached = _user_cache.get(user_id)
    if cached is not None:
        cached.update(values)
    else:
        _user_cache[user_id] = {"user_id": user_id, **values}


@_retry_db
def delete_user_data(user_id):
    with db_write() as conn:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.execute(f"DROP TABLE IF EXISTS history_{int(user_id)}")
    for suffix in (".session", ".session-journal"):
        path = f"tg_session_{int(user_id)}{suffix}"
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@_retry_db
def _ensure_history_table(user_id):
    with db_write() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS history_{int(user_id)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                voucher_hash TEXT NOT NULL,
                amount_baht REAL,
                redeem_phone TEXT,
                status TEXT NOT NULL
            )
        """)


def init_history(user_id):
    _ensure_history_table(user_id)


@_retry_db
def history_insert(user_id, timestamp, voucher_hash, amount, phone, status):
    _ensure_history_table(user_id)
    with db_write() as conn:
        conn.execute(
            f"INSERT INTO history_{int(user_id)} (timestamp,voucher_hash,amount_baht,redeem_phone,status) VALUES (?,?,?,?,?)",
            (timestamp, voucher_hash, amount, phone, status),
        )
        if status == "success" and amount is not None:
            conn.execute("UPDATE global_stats SET lifetime_total = lifetime_total + ? WHERE id = 1", (float(amount),))


@_retry_db
def user_total(user_id):
    _ensure_history_table(user_id)
    with db_read() as conn:
        row = conn.execute(f"SELECT COALESCE(SUM(amount_baht),0) total FROM history_{int(user_id)} WHERE status='success'").fetchone()
        return float(row["total"])


@_retry_db
def user_count(user_id):
    _ensure_history_table(user_id)
    with db_read() as conn:
        row = conn.execute(f"SELECT COUNT(*) total FROM history_{int(user_id)} WHERE status='success'").fetchone()
        return int(row["total"])


@_retry_db
def global_total():
    with db_read() as conn:
        row = conn.execute("SELECT lifetime_total FROM global_stats WHERE id = 1").fetchone()
        return float(row["lifetime_total"] if row else 0.0)


@_retry_db
def active_users():
    with db_read() as conn:
        row = conn.execute("SELECT COUNT(*) total FROM users WHERE is_running=1").fetchone()
        return int(row["total"])


def extract_hash(text):
    if not text:
        return None
    patterns = [
        r"gift\.truemoney\.com/campaign[^\s\"'<]*[?&]v=([A-Za-z0-9]+)",
        r"campaign/\?v=([A-Za-z0-9]+)",
        r"v=([A-Za-z0-9]+)(?:\s|$|/)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    m = RAW_HASH_PATTERN.search(text.strip())
    if m:
        candidate = m.group(1)
        if re.fullmatch(r"[0-9a-fA-F]{32,35}[0-9a-zA-Z]?", candidate):
            return candidate
    return None


def extract_all_hashes(text):
    if not text:
        return []
    found = []
    url_pattern = re.compile(
        r"gift\.truemoney\.com/campaign[^\s\"'<]*[?&]v=([A-Za-z0-9]+)"
        r"|campaign/\?v=([A-Za-z0-9]+)",
        re.I,
    )
    for m in url_pattern.finditer(text):
        h = m.group(1) or m.group(2)
        if h:
            found.append(h)
    for m in RAW_HASH_PATTERN.finditer(text):
        candidate = m.group(1)
        if re.fullmatch(r"[0-9a-fA-F]{32,35}[0-9a-zA-Z]?", candidate):
            found.append(candidate)
    seen = set()
    result = []
    for h in found:
        if h not in seen:
            seen.add(h)
            result.append(h)
    return result


def find_links(text):
    return SHORT_LINK_PATTERN.findall(text or "")


def response_json(resp):
    try:
        return resp.json()
    except Exception:
        try:
            return json.loads(resp.text)
        except Exception:
            return {}


def error_text(data, status_code=None):
    status = data.get("status", {}) if isinstance(data, dict) else {}
    code = status.get("code", "") if isinstance(status, dict) else ""
    message = status.get("message", "") if isinstance(status, dict) else ""
    if code and code in STATUS:
        return STATUS[code]
    if message:
        return str(message)
    if code:
        return f"รหัสข้อผิดพลาด: {code}"
    if isinstance(data, dict):
        for key in ("error", "detail", "reason"):
            value = data.get(key)
            if value:
                return str(value)
    if status_code is not None:
        return f"HTTP {status_code}"
    return "API ไม่ส่งรายละเอียดข้อผิดพลาด"


def receiver_name(data):
    try:
        root = data.get("data", {})
        ticket = root.get("my_ticket", {})
        for key in ("display_name", "claimer_name", "owner_name", "receiver_name", "name", "full_name"):
            if ticket.get(key):
                return ticket[key]
        for source in (root.get("receiver"), root.get("claimer"), root.get("owner")):
            if isinstance(source, dict):
                for key in ("display_name", "name", "full_name", "first_name"):
                    if source.get(key):
                        return source[key]
    except Exception:
        pass
    return "ไม่ทราบ"


def receiver_image(data):
    try:
        root = data.get("data", {})
        ticket = root.get("my_ticket", {})
        for source in (ticket, root.get("receiver"), root.get("redeemer_profile"), root.get("claimer"), root.get("owner"), root.get("owner_profile")):
            if isinstance(source, dict):
                for key in ("profile_image_url", "profile_picture_url", "image_url", "profile_pic"):
                    if source.get(key):
                        return source[key]
        for item in root.get("tickets", []):
            if item.get("profile_pic"):
                return item["profile_pic"]
    except Exception:
        pass
    return None


def mask_name(name):
    parts = (name or "ไม่ทราบ").split()
    if len(parts) <= 1:
        return parts[0] if parts else "ไม่ทราบ"
    return f"{parts[0]} " + " ".join("*****" for _ in parts[1:])


def normalize_phone(value):
    raw = (value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("66"):
        return "+" + digits
    if digits.startswith("0"):
        return "+66" + digits[1:]
    return ""


_RESOLVE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

_resolve_session: aiohttp.ClientSession | None = None


def _get_resolve_session() -> aiohttp.ClientSession:
    global _resolve_session
    if _resolve_session is None or _resolve_session.closed:
        connector = aiohttp.TCPConnector(limit=64, ttl_dns_cache=300, enable_cleanup_closed=True)
        timeout = aiohttp.ClientTimeout(total=6, connect=3)
        _resolve_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=_RESOLVE_HEADERS,
        )
    return _resolve_session


async def resolve_hash(_, url):
    session = _get_resolve_session()
    try:
        async with session.get(url, allow_redirects=True, max_redirects=10) as resp:
            final_url = str(resp.url)
            h = extract_hash(final_url)
            if h:
                return h
            if resp.status in (403, 429):
                logging.warning("resolve 403/429 on %s, trying primp", url)
                return await _resolve_hash_primp(url)
            body = await resp.text(errors="ignore")
            return extract_hash(body)
    except aiohttp.ClientError as exc:
        logging.error("resolve link aiohttp error: %s", exc)
        return await _resolve_hash_primp(url)
    except Exception as exc:
        logging.error("resolve link error: %s", exc)
        return None


async def _resolve_hash_primp(url):
    try:
        client = primp.AsyncClient(impersonate="chrome", impersonate_os="windows", timeout=5)
        resp = await client.get(url, follow_redirects=True)
        return extract_hash(str(getattr(resp, "url", url))) or extract_hash(resp.text)
    except Exception as exc:
        logging.error("primp resolve fallback error: %s", exc)
        return None


_REDEEM_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://gift.truemoney.com",
    "Accept-Encoding": "gzip, deflate, br",
}

_primp_pool: dict[str, primp.AsyncClient] = {}
_user_cache: dict[int, dict] = {}


def _cache_user(config: dict):
    if config:
        _user_cache[config["user_id"]] = config


def _invalidate_cache(user_id: int):
    _user_cache.pop(user_id, None)


def _get_primp_client(phone: str) -> primp.AsyncClient:
    client = _primp_pool.get(phone)
    if client is None:
        client = primp.AsyncClient(impersonate="chrome", impersonate_os="windows", timeout=3)
        _primp_pool[phone] = client
    return client


async def redeem(_, voucher_hash, phone):
    started = time.perf_counter()
    url = f"https://gift.truemoney.com/campaign/vouchers/{voucher_hash}/redeem"
    payload = {"mobile": phone, "voucher_hash": voucher_hash}
    headers = {**_REDEEM_HEADERS, "Referer": f"https://gift.truemoney.com/campaign/?v={voucher_hash}"}
    try:
        client = _get_primp_client(phone)
        resp = await client.post(url, json=payload, headers=headers)
        return resp, (time.perf_counter() - started) * 1000
    except Exception as exc:
        logging.error("redeem error: %s", exc)
        return None, (time.perf_counter() - started) * 1000


async def send_webhook(session, url, embed):
    if not url:
        logging.warning("webhook is empty")
        return
    try:
        async with session.post(url, json={"embeds": [embed]}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status not in (200, 204):
                logging.error("webhook returned %s: %s", resp.status, await resp.text())
    except Exception as exc:
        logging.error("webhook error: %s", exc)


async def process_voucher(user_id, http, primp_client, voucher_hash, phone, webhook, source_link, notify_level):
    resp, elapsed = await redeem(None, voucher_hash, phone)
    now = datetime.now(timezone.utc).isoformat()
    loop = asyncio.get_event_loop()
    source = f"[เปิดข้อความ]({source_link})" if source_link else "ไม่พบลิงก์ต้นทาง"
    if resp is None:
        if notify_level != 1:
            embed = {"title": "❌ รับไม่สำเร็จ", "description": "**เกิดข้อผิดพลาดในการเชื่อมต่อ**", "color": 15548997, "fields": [{"name": "🎫 รหัสซอง", "value": f"`{voucher_hash}`", "inline": True}, {"name": "📌 แหล่งที่มา", "value": source, "inline": True}, {"name": "⚡ ใช้เวลา", "value": f"`{elapsed:.0f}ms`", "inline": True}], "timestamp": now}
            asyncio.create_task(send_webhook(http, webhook, embed))
        loop.run_in_executor(None, lambda: history_insert(user_id, now, voucher_hash, None, phone, "error"))
        return
    data = response_json(resp)
    if resp.status_code == 200:
        try:
            amount = float(data["data"]["my_ticket"]["amount_baht"])
        except Exception:
            amount = None
        loop.run_in_executor(None, lambda: history_insert(user_id, now, voucher_hash, amount, phone, "success"))
        async def _send_success():
            total = await loop.run_in_executor(None, lambda: user_total(user_id))
            embed = {"title": "🧧 รับอั่งเปาสำเร็จ!", "color": 5763719, "fields": [{"name": "💰 จำนวนเงิน", "value": f"**{amount:.0f}** บาท" if amount is not None else "ไม่ทราบ", "inline": True}, {"name": "⚡ ใช้เวลา", "value": f"`{elapsed:.0f}ms`", "inline": True}, {"name": "🎫 รหัสซอง", "value": f"`{voucher_hash}`", "inline": True}, {"name": "📌 แหล่งที่มา", "value": source, "inline": True}, {"name": "👤 ผู้รับเงิน", "value": mask_name(receiver_name(data)), "inline": True}, {"name": "🔗 ลิงก์", "value": f"[เปิดซอง](https://gift.truemoney.com/campaign/?v={voucher_hash})", "inline": True}, {"name": "📊 ยอดรวมสะสม", "value": f"**{total:.0f}** บาท", "inline": False}], "timestamp": now}
            image = receiver_image(data)
            if image:
                embed["thumbnail"] = {"url": image}
            await send_webhook(http, webhook, embed)
        asyncio.create_task(_send_success())
        return
    logging.warning("redeem failed HTTP %s response=%s", resp.status_code, json.dumps(data, ensure_ascii=False)[:800])
    loop.run_in_executor(None, lambda: history_insert(user_id, now, voucher_hash, None, phone, "error"))
    if notify_level != 1:
        embed = {"title": "❌ รับไม่สำเร็จ", "description": f"**{error_text(data, resp.status_code)}**", "color": 15548997, "fields": [{"name": "🎫 รหัสซอง", "value": f"`{voucher_hash}`", "inline": True}, {"name": "📌 แหล่งที่มา", "value": source, "inline": True}, {"name": "⚡ ใช้เวลา", "value": f"`{elapsed:.0f}ms`", "inline": True}], "timestamp": now}
        asyncio.create_task(send_webhook(http, webhook, embed))


async def safe_process_voucher(*args, **kwargs):
    try:
        await process_voucher(*args, **kwargs)
    except Exception as exc:
        logging.exception("voucher processing failed: %s", exc)


_RECONNECT_DELAY_MIN = 5
_RECONNECT_DELAY_MAX = 120
_WATCHDOG_INTERVAL = 30


class TelegramSessionManager:
    def __init__(self):
        self.clients = {}
        self.http = {}
        self.primp = {}
        self.tasks = {}
        self.watchdog_tasks = {}
        self.starts = {}
        self._stopping = set()

    def _make_handler(self, user_id, client, http, primp_client, config):
        @client.on(events.NewMessage)
        async def handler(event):
            loop = asyncio.get_event_loop()
            runtime_config = _user_cache.get(user_id) or config
            phone = runtime_config.get("truemoney_phone", "") or config.get("truemoney_phone", "")
            webhook = runtime_config.get("webhook_url", "") or config.get("webhook_url", "")
            notify_level = runtime_config.get("notify_level", 0)

            source_link = None
            try:
                chat = event.chat
                username = getattr(chat, "username", None) if chat else None
                source_link = f"https://t.me/{username}/{event.id}" if username else None
            except Exception:
                pass

            raw_text = event.raw_text or ""
            texts_to_scan = [raw_text]

            try:
                if event.message and event.message.entities:
                    for entity in event.message.entities:
                        entity_url = getattr(entity, "url", None)
                        if entity_url:
                            texts_to_scan.append(entity_url)
            except Exception:
                pass

            seen_hashes = set()
            all_hashes = []
            for src in texts_to_scan:
                for h in extract_all_hashes(src):
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        all_hashes.append(h)

            if all_hashes:
                for voucher_hash in all_hashes:
                    asyncio.create_task(
                        safe_process_voucher(
                            user_id, http, primp_client, voucher_hash,
                            phone, webhook, source_link, notify_level,
                        )
                    )
                return

            all_links = []
            seen_links = set()
            for src in texts_to_scan:
                for lnk in find_links(src):
                    if lnk not in seen_links:
                        seen_links.add(lnk)
                        all_links.append(lnk)

            for link in all_links:
                asyncio.create_task(self.resolve_and_process(user_id, link, source_link, config))

            if event.photo:
                asyncio.create_task(self.scan_photo(user_id, event, source_link, config))

    async def _reconnect_loop(self, user_id):
        delay = _RECONNECT_DELAY_MIN
        while user_id not in self._stopping:
            try:
                client = self.clients.get(user_id)
                if client is None:
                    break
                if not client.is_connected():
                    logging.warning("user %s: Telegram disconnected, reconnecting in %ss", user_id, delay)
                    await asyncio.sleep(delay)
                    if user_id in self._stopping:
                        break
                    try:
                        await client.connect()
                        if await client.is_user_authorized():
                            delay = _RECONNECT_DELAY_MIN
                            logging.info("user %s: reconnected to Telegram", user_id)
                        else:
                            logging.error("user %s: session expired after reconnect", user_id)
                            loop = asyncio.get_event_loop()
                            loop.run_in_executor(None, lambda: upsert_user(user_id, is_running=0, otp_pending=0))
                            break
                    except Exception as exc:
                        logging.error("user %s: reconnect attempt failed: %s", user_id, exc)
                        delay = min(delay * 2, _RECONNECT_DELAY_MAX)
                        continue
                await asyncio.sleep(_WATCHDOG_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logging.error("user %s: reconnect loop error: %s", user_id, exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, _RECONNECT_DELAY_MAX)

    async def _run_client(self, user_id):
        while user_id not in self._stopping:
            try:
                client = self.clients.get(user_id)
                if client is None:
                    break
                if not client.is_connected():
                    await asyncio.sleep(2)
                    continue
                await client.run_until_disconnected()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logging.error("user %s: client loop error: %s", user_id, exc)
            if user_id in self._stopping:
                break
            await asyncio.sleep(3)

    async def start(self, user_id, config):
        if user_id in self.clients and self.clients[user_id].is_connected():
            return "running"
        try:
            api_id = int(config["api_id"])
            api_hash = config["api_hash"].strip()
            phone = normalize_phone(config["telegram_phone"])
            if not api_id or not api_hash or not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
                return "กรุณาตรวจสอบ API_ID, API_HASH และเบอร์ Telegram"
            config["telegram_phone"] = phone
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: upsert_user(user_id, telegram_phone=phone))
            await loop.run_in_executor(None, lambda: init_history(user_id))
            fresh = await loop.run_in_executor(None, lambda: get_user(user_id))
            if fresh:
                _cache_user(fresh)
            self._stopping.discard(user_id)
            old_client = self.clients.pop(user_id, None)
            if old_client:
                try:
                    await old_client.disconnect()
                except Exception:
                    pass
            http = self.http.get(user_id)
            if http is None or http.closed:
                http = aiohttp.ClientSession()
                self.http[user_id] = http
            primp_client = self.primp.get(user_id)
            if primp_client is None:
                primp_client = _get_primp_client(str(user_id))
                self.primp[user_id] = primp_client
            client = TelegramClient(f"tg_session_{user_id}", api_id, api_hash)
            await client.connect()
            self.clients[user_id] = client
            self.starts.setdefault(user_id, datetime.now(timezone.utc))
            self._make_handler(user_id, client, http, primp_client, config)
            if await client.is_user_authorized():
                await loop.run_in_executor(None, lambda: upsert_user(user_id, is_running=1, start_time=self.starts[user_id].isoformat(), otp_pending=0))
                for t_key in ("tasks", "watchdog_tasks"):
                    old = getattr(self, t_key).pop(user_id, None)
                    if old and not old.done():
                        old.cancel()
                self.tasks[user_id] = asyncio.create_task(self._run_client(user_id))
                self.watchdog_tasks[user_id] = asyncio.create_task(self._reconnect_loop(user_id))
                return "started"
            sent = await client.send_code_request(phone)
            await loop.run_in_executor(None, lambda: upsert_user(user_id, otp_phone_code_hash=sent.phone_code_hash, otp_pending=1, is_running=0))
            return "otp"
        except Exception as exc:
            logging.exception("start user %s failed", user_id)
            await loop.run_in_executor(None, lambda: upsert_user(user_id, is_running=0, otp_pending=0))
            await self.cleanup(user_id)
            return f"เปิดระบบไม่สำเร็จ: {exc}"

    async def resolve_and_process(self, user_id, link, source_link, config):
        voucher_hash = await resolve_hash(None, link)
        if voucher_hash:
            loop = asyncio.get_event_loop()
            runtime_config = await loop.run_in_executor(None, lambda: get_user(user_id)) or config
            http = self.http.get(user_id)
            primp_client = self.primp.get(user_id)
            if http and primp_client:
                await safe_process_voucher(
                    user_id, http, primp_client, voucher_hash,
                    runtime_config["truemoney_phone"], runtime_config["webhook_url"],
                    source_link, runtime_config.get("notify_level", 0),
                )

    async def scan_photo(self, user_id, event, source_link, config):
        if not ZXING_AVAILABLE:
            return
        try:
            data = await event.download_media(bytes)
            loop = asyncio.get_event_loop()
            image = await loop.run_in_executor(None, lambda: Image.open(io.BytesIO(data)).convert("RGB"))
            results = await loop.run_in_executor(None, lambda: zxingcpp.read_barcodes(image))
            for result in results:
                text = result.text or ""
                voucher_hash = extract_hash(text)
                if voucher_hash:
                    runtime_config = await loop.run_in_executor(None, lambda: get_user(user_id)) or config
                    http = self.http.get(user_id)
                    primp_client = self.primp.get(user_id)
                    if http and primp_client:
                        asyncio.create_task(safe_process_voucher(user_id, http, primp_client, voucher_hash, runtime_config["truemoney_phone"], runtime_config["webhook_url"], source_link, runtime_config.get("notify_level", 0)))
        except Exception as exc:
            logging.error("QR error user %s: %s", user_id, exc)

    async def submit_otp(self, user_id, code):
        loop = asyncio.get_event_loop()
        config = await loop.run_in_executor(None, lambda: get_user(user_id))
        client = self.clients.get(user_id)
        if not config or not client or not config.get("otp_pending"):
            return False, "ไม่พบคำขอ OTP"
        try:
            await client.sign_in(config["telegram_phone"], code, phone_code_hash=config["otp_phone_code_hash"])
            now_iso = datetime.now(timezone.utc).isoformat()
            await loop.run_in_executor(None, lambda: upsert_user(user_id, is_running=1, start_time=now_iso, otp_pending=0))
            self.starts[user_id] = datetime.now(timezone.utc)
            self._stopping.discard(user_id)
            for t_key in ("tasks", "watchdog_tasks"):
                old = getattr(self, t_key).pop(user_id, None)
                if old and not old.done():
                    old.cancel()
            self.tasks[user_id] = asyncio.create_task(self._run_client(user_id))
            self.watchdog_tasks[user_id] = asyncio.create_task(self._reconnect_loop(user_id))
            return True, "started"
        except Exception as exc:
            logging.exception("OTP error user %s", user_id)
            return False, f"ยืนยัน OTP ไม่สำเร็จ: {exc}"

    async def stop(self, user_id):
        self._stopping.add(user_id)
        client = self.clients.get(user_id)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
        await self.cleanup(user_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: upsert_user(user_id, is_running=0, otp_pending=0, start_time=None))

    async def cleanup(self, user_id):
        for t_key in ("tasks", "watchdog_tasks"):
            old = getattr(self, t_key).pop(user_id, None)
            if old and not old.done():
                old.cancel()
        http = self.http.pop(user_id, None)
        if http and not http.closed:
            try:
                await http.close()
            except Exception:
                pass
        primp_client = self.primp.pop(user_id, None)
        if primp_client:
            try:
                await primp_client.aclose()
            except Exception:
                pass
        self.clients.pop(user_id, None)
        self.starts.pop(user_id, None)

    def uptime(self, user_id):
        started = self.starts.get(user_id)
        if not started:
            return "ไม่ได้เปิดระบบ"
        seconds = int((datetime.now(timezone.utc) - started).total_seconds())
        hours, rem = divmod(seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours}ชม. {minutes}นาที {seconds}วินาที"

    async def resume_all(self):
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _get_all_running_users)
        for config in rows:
            user_id = config["user_id"]
            if user_id in self._stopping:
                continue
            required = ("telegram_phone", "api_id", "api_hash", "truemoney_phone", "webhook_url")
            if not all(config.get(k) for k in required):
                continue
            logging.info("auto-resuming user %s", user_id)
            asyncio.create_task(self._safe_resume(user_id, config))

    async def _safe_resume(self, user_id, config):
        try:
            _cache_user(config)
            result = await self.start(user_id, dict(config))
            logging.info("auto-resume user %s: %s", user_id, result)
        except Exception as exc:
            logging.error("auto-resume user %s failed: %s", user_id, exc)


@_retry_db
def _get_all_running_users():
    with db_read() as conn:
        rows = conn.execute("SELECT * FROM users WHERE is_running=1").fetchall()
        return [dict(r) for r in rows]


manager = TelegramSessionManager()
live_panel_tasks = {}


async def _presence_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            guild_count = len(bot.guilds)
            label = f"{guild_count} เซิฟเวอร์" if guild_count != 1 else "1 เซิฟเวอร์"
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.watching, name=label),
            )
        except Exception as exc:
            logging.error("presence error: %s", exc)
        await asyncio.sleep(3)


async def panel_embed_async():
    loop = asyncio.get_event_loop()
    au = await loop.run_in_executor(None, active_users)
    gt = await loop.run_in_executor(None, global_total)
    embed = discord.Embed(
        title="🧧 บอทรับดักซองฟรี 24/7 ชม",
        description=(
            f"👥 ผู้ใช้: **{au} คน**\n"
            f"💰 ยอดเงินสะสม: **{gt:.0f} บาท**\n"
            f"⏱️ เปิดมาแล้ว: **{bot.uptime_text()}**"
        ),
        color=0xFFD700,
    )
    embed.set_image(url=BANNER_URL)
    return embed


def panel_embed():
    au = active_users()
    gt = global_total()
    embed = discord.Embed(
        title="🧧 บอทรับดักซองฟรี 24/7 ชม",
        description=(
            f"👥 ผู้ใช้: **{au} คน**\n"
            f"💰 ยอดเงินสะสม: **{gt:.0f} บาท**\n"
            f"⏱️ เปิดมาแล้ว: **{bot.uptime_text()}**"
        ),
        color=0xFFD700,
    )
    embed.set_image(url=BANNER_URL)
    return embed


async def refresh_panel_message(message):
    try:
        while not bot.is_closed():
            await asyncio.sleep(1)
            embed = await panel_embed_async()
            await message.edit(embed=embed)
    except (discord.NotFound, discord.Forbidden):
        pass
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logging.error("panel refresh error: %s", exc)
    finally:
        live_panel_tasks.pop(message.id, None)


class SettingsModal(discord.ui.Modal, title="📋 ตั้งค่าข้อมูล"):
    telegram_phone = discord.ui.TextInput(label="เบอร์ Telegram", placeholder="09xxxxxxxx หรือ +669xxxxxxxx", required=True)
    api_id = discord.ui.TextInput(label="API_ID", placeholder="ตัวเลขจาก my.telegram.org/auth", required=True)
    api_hash = discord.ui.TextInput(label="API_HASH", placeholder="ค่าจาก my.telegram.org/auth", required=True)
    truemoney_phone = discord.ui.TextInput(label="เบอร์รับเงิน TrueMoney", placeholder="09xxxxxxxx", required=True)
    webhook_url = discord.ui.TextInput(label="Webhook", placeholder="https://discord.com/api/webhooks/...", required=True)

    async def on_submit(self, interaction):
        try:
            int(str(self.api_id.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ API_ID ต้องเป็นตัวเลข", ephemeral=True)
            return
        phone = normalize_phone(str(self.telegram_phone.value))
        if not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
            await interaction.response.send_message("❌ เบอร์ Telegram ไม่ถูกต้อง", ephemeral=True)
            return
        uid = interaction.user.id
        _kw = dict(telegram_phone=phone, api_id=str(self.api_id.value).strip(), api_hash=str(self.api_hash.value).strip(), truemoney_phone=str(self.truemoney_phone.value).strip(), webhook_url=str(self.webhook_url.value).strip())
        await asyncio.get_event_loop().run_in_executor(None, lambda: upsert_user(uid, **_kw))
        await interaction.response.send_message("✅ บันทึกข้อมูลเรียบร้อย", ephemeral=True)


class NotifyModal(discord.ui.Modal, title="🔔 การตั้งค่าแจ้งเตือน"):
    webhook_url = discord.ui.TextInput(label="Webhook", placeholder="วาง Webhook URL ที่นี่", required=True)
    notify_level = discord.ui.TextInput(label="แจ้งเตือนผล", placeholder="0=ทั้งหมด | 1=เฉพาะสำเร็จ", max_length=1, required=True)

    async def on_submit(self, interaction):
        try:
            level = 1 if int(str(self.notify_level.value).strip()) == 1 else 0
        except ValueError:
            level = 0
        uid = interaction.user.id
        wh = str(self.webhook_url.value).strip()
        await asyncio.get_event_loop().run_in_executor(None, lambda: upsert_user(uid, webhook_url=wh, notify_level=level))
        await interaction.response.send_message("✅ บันทึกการแจ้งเตือนเรียบร้อย", ephemeral=True)


class OTPModal(discord.ui.Modal, title="🔑 กรุณาใส่รหัส OTP ที่ได้รับ"):
    otp_code = discord.ui.TextInput(label="รหัส OTP", required=True, min_length=4, max_length=10)

    async def on_submit(self, interaction):
        code = "".join(filter(str.isdigit, str(self.otp_code.value)))
        success, message = await manager.submit_otp(interaction.user.id, code)
        if success:
            loop = asyncio.get_event_loop()
            uid = interaction.user.id
            total = await loop.run_in_executor(None, lambda: user_total(uid))
            count = await loop.run_in_executor(None, lambda: user_count(uid))
            await interaction.response.send_message(f"✅ เปิดระบบแล้ว\nยอดเงินสะสม: {total:.0f} บาท\nจำนวนที่รับสำเร็จ: {count} ครั้ง", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)


class OTPView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="ใส่รหัส OTP", style=discord.ButtonStyle.primary, emoji="🔑")
    async def otp(self, interaction, button):
        await interaction.response.send_modal(OTPModal())


class ChannelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="เลือกห้องที่จะแสดงแผงควบคุม", min_values=1, max_values=1)
    async def select_channel(self, interaction, select):
        selected = select.values[0] if select.values else None
        if not selected:
            await interaction.response.send_message("❌ ไม่พบห้องที่เลือก", ephemeral=True)
            return
        try:
            selected_channel = interaction.guild.get_channel(selected.id) if interaction.guild else None
            if selected_channel is None:
                selected_channel = bot.get_channel(selected.id)
            if selected_channel is None:
                selected_channel = await bot.fetch_channel(selected.id)
            if not isinstance(selected_channel, discord.abc.Messageable):
                await interaction.response.send_message("❌ ห้องที่เลือกไม่รองรับการส่งข้อความ", ephemeral=True)
                return
            message = await selected_channel.send(embed=await panel_embed_async(), view=ControlPanelView())
            old_task = live_panel_tasks.pop(message.id, None)
            if old_task and not old_task.done():
                old_task.cancel()
            live_panel_tasks[message.id] = asyncio.create_task(refresh_panel_message(message))
            await interaction.response.send_message(f"✅ แสดงแผงควบคุมที่ห้อง {selected_channel.mention} แล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์ส่งข้อความในห้องที่เลือก", ephemeral=True)
        except Exception as exc:
            logging.exception("channel panel error: %s", exc)
            await interaction.response.send_message("❌ ไม่สามารถแสดงแผงควบคุมในห้องที่เลือกได้", ephemeral=True)


class DeleteConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="ยืนยันลบทั้งหมด", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction, button):
        uid = interaction.user.id
        await manager.stop(uid)
        await asyncio.get_event_loop().run_in_executor(None, lambda: delete_user_data(uid))
        await interaction.response.edit_message(content="✅ ลบข้อมูลการตั้งค่า ประวัติการรับเงิน และข้อมูลเข้าสู่ระบบเรียบร้อยแล้ว", view=None)

    @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="ยกเลิกการลบข้อมูลแล้ว", view=None)


class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ตั้งค่าข้อมูล", style=discord.ButtonStyle.primary, emoji="📋", custom_id="panel_settings")
    async def settings(self, interaction, button):
        loop = asyncio.get_event_loop()
        uid = interaction.user.id
        config = await loop.run_in_executor(None, lambda: get_user(uid)) or {}
        modal = SettingsModal()
        modal.telegram_phone.default = config.get("telegram_phone", "")
        modal.api_id.default = config.get("api_id", "")
        modal.api_hash.default = config.get("api_hash", "")
        modal.truemoney_phone.default = config.get("truemoney_phone", "")
        modal.webhook_url.default = config.get("webhook_url", "")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="เช็คสถานะ", style=discord.ButtonStyle.success, emoji="📊", custom_id="panel_status")
    async def status(self, interaction, button):
        loop = asyncio.get_event_loop()
        uid = interaction.user.id
        config = await loop.run_in_executor(None, lambda: get_user(uid))
        running = bool(config and config.get("is_running"))
        total = await loop.run_in_executor(None, lambda: user_total(uid))
        count = await loop.run_in_executor(None, lambda: user_count(uid))
        uptime_str = manager.uptime(uid)

        status_icon = "🟢" if running else "🔴"
        status_text = "เปิดระบบแล้ว" if running else "ปิดระบบ"

        embed = discord.Embed(
            title="📊 สถานะระบบของคุณ",
            color=0x57F287 if running else 0xED4245,
        )
        embed.add_field(
            name="🔌 สถานะ",
            value=f"```{status_icon} {status_text}```",
            inline=False,
        )
        embed.add_field(
            name="💰 ยอดเงินสะสม",
            value=f"```{total:.0f} บาท```",
            inline=True,
        )
        embed.add_field(
            name="✅ จำนวนรับสำเร็จ",
            value=f"```{count} ครั้ง```",
            inline=True,
        )
        embed.add_field(
            name="⏱️ เปิดมาแล้ว",
            value=f"```{uptime_str}```",
            inline=False,
        )
        embed.set_footer(text="อัปเดตล่าสุด")
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="การตั้งค่าแจ้งเตือน", style=discord.ButtonStyle.secondary, emoji="🔔", custom_id="panel_notify")
    async def notify(self, interaction, button):
        loop = asyncio.get_event_loop()
        uid = interaction.user.id
        config = await loop.run_in_executor(None, lambda: get_user(uid)) or {}
        modal = NotifyModal()
        modal.webhook_url.default = config.get("webhook_url", "")
        modal.notify_level.default = str(config.get("notify_level", 0))
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="เปิดระบบ", style=discord.ButtonStyle.success, emoji="🟢", custom_id="panel_start")
    async def start(self, interaction, button):
        loop = asyncio.get_event_loop()
        uid = interaction.user.id
        config = await loop.run_in_executor(None, lambda: get_user(uid))
        required = ("telegram_phone", "api_id", "api_hash", "truemoney_phone", "webhook_url")
        if not config or not all(config.get(key) for key in required):
            await interaction.response.send_message("❌ กรุณาตั้งค่าข้อมูลให้ครบก่อนเปิดระบบ", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await manager.start(uid, config)
        if result == "otp":
            await interaction.edit_original_response(content="🔑 ส่งรหัส OTP ไป Telegram แล้ว กรุณากดปุ่มด้านล่างเพื่อกรอกรหัส", view=OTPView())
        elif result == "started":
            await interaction.edit_original_response(content="✅ เปิดระบบแล้ว", view=None)
        elif result == "running":
            await interaction.edit_original_response(content="⚠️ ระบบทำงานอยู่แล้ว", view=None)
        else:
            await interaction.edit_original_response(content=f"❌ {result}", view=None)

    @discord.ui.button(label="ปิดระบบ", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="panel_stop")
    async def stop(self, interaction, button):
        await manager.stop(interaction.user.id)
        await interaction.response.send_message("🔴 ปิดระบบเรียบร้อย", ephemeral=True)

    @discord.ui.button(label="ลบข้อมูลทั้งหมด", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="panel_delete")
    async def delete_all(self, interaction, button):
        await interaction.response.send_message("⚠️ การดำเนินการนี้จะหยุดระบบและลบค่าตั้งค่า ประวัติการรับเงิน และข้อมูลเข้าสู่ระบบทั้งหมดของคุณ กู้คืนไม่ได้ ยืนยันหรือไม่?", view=DeleteConfirmView(), ephemeral=True)


@bot.tree.command(name="xdcc", description="แสดงแผงควบคุมบอทรับดักซอง")
async def xdcc(interaction):
    await interaction.response.send_message("📌 กรุณาเลือกห้องที่จะแสดงแผงควบคุม", view=ChannelSelectView(), ephemeral=True)


_start_time = datetime.now(timezone.utc)


def uptime_text():
    seconds = int((datetime.now(timezone.utc) - _start_time).total_seconds())
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}วัน {hours}ชม. {minutes}นาที" if days else f"{hours}ชม. {minutes}นาที {seconds}วินาที"


bot.uptime_text = uptime_text


@bot.event
async def on_ready():
    loop = asyncio.get_event_loop()
    try:
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logging.info("Guild %s (%s): synced %s commands", guild.name, guild.id, len(synced))
        global_synced = await bot.tree.sync()
        logging.info("Global: synced %s commands", len(global_synced))
    except Exception:
        logging.exception("command sync failed")
    bot.add_view(ControlPanelView())
    logging.info("Bot logged in as %s (ID: %s)", bot.user, bot.user.id)
    await manager.resume_all()
    asyncio.create_task(_presence_loop())


# --- ส่วนของ aiohttp Web Server สำหรับ Health Check บน Render ---
async def handle_health_check(request):
    return web.Response(text="OK", status=200)

async def start_health_check_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    app.router.add_get('/health', handle_health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Health check HTTP server running on port {port}")


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN is required")
    
    init_db()

    async def main():
        # รัน Health Check Web Server และ รันบอท Discord พร้อมกัน
        await start_health_check_server()
        await bot.start(BOT_TOKEN)

    asyncio.run(main())
