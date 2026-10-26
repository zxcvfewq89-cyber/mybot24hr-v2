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
# ⚠️ [ ส่วนตั้งค่าสำคัญ ] ⚠️
# =====================================================================
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("DISCORD_OWNER_ID", "1564080596173721670"))
GUILD_ID = 1204647300870311986
GIF_URL = "https://cdn.discordapp.com/attachments/1542432996701900870/1564081671081304116/turn-anime.gif?ex=6adff811&is=6adea691&hm=e1aa4a485c432703096b2135767c090df884c98dca14e074874dcadf674bb46c&"
# =====================================================================

# --- [ ระบบ Logic ดึง Token ] ---
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

# --- [ Web Server สำหรับ Render / UptimeRobot ] ---
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

# --- [ คำสั่งสำหรับ Sync Slash Commands แบบ Manual ] ---
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

# ... (ฟังก์ชัน Clone ต่างๆ และ Class Modal/View ทั้งหมดเหมือนเดิม) ...
