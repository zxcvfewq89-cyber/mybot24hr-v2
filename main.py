import nextcord
from nextcord.ext import commands
import base64, codecs
import os
import urllib.request
from flask import Flask
from threading import Thread
import asyncio

# --- ตั้งค่า Web Server สำหรับ Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ---------------------------------

intents = nextcord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.all()

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever1 = 1204647300870311986  # ไอดี เซิฟเวอร์ดิสคอร์ด
BotSever2 = 1512082655305404456  # ไอดี ห้องที่จะให้บอทลง

# ฟังก์ชันสำหรับพาบอทเข้าห้องเสียงอัตโนมัติ
async def join_vc_channel():
    guild = bot.get_guild(BotSever1)
    if not guild:
        return
    vc = nextcord.utils.get(guild.channels, id=BotSever2)
    if vc:
        if not guild.voice_client:
            try:
                await vc.connect(timeout=20.0, reconnect=True)
                await guild.change_voice_state(channel=vc, self_mute=False, self_deaf=True)
                print("Successfully connected to voice channel.")
            except Exception as e:
                print(f"Error connecting to voice: {e}")
        else:
            await guild.change_voice_state(channel=vc, self_mute=False, self_deaf=True)

@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Streaming(
        name="", url="https://m.twitch.tv/lofigirl"))
    await join_vc_channel()
    print('Bot is ready.')

# ระบบตรวจสอบ: ถ้าบอทโดนเตะ หรือหลุดออก ระบบจะดึงกลับเข้าห้องอัตโนมัติ
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.self_stream:
        print(f'{member.name} is in {after.channel.name} and started speaking.')
    
    # ถ้าเกิดกรณีตัวบอทหลุดจากห้องเสียง ให้สั่งให้กลับเข้าห้องใหม่ใน 5 วินาที
    if member.id == bot.user.id:
        if before.channel is not None and after.channel is None:
            print("Bot disconnected! Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
            await join_vc_channel()

# รันเว็บ Server เบื้องหลัง
keep_alive()

# รันบอท
bot.run(os.getenv("DISCORD_TOKEN"))

