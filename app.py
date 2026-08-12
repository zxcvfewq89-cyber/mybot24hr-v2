import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. เว็บเซิร์ฟเวอร์เพื่อให้ UptimeRobot มา Ping (กันบอทดับบน Render)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอทและ Intents ตามที่คุณต้องการ
intents = nextcord.Intents.all()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever1 = 1204647300870311986  # ไอดี เซิฟเวอร์ดิสคอส
BotSever2 = 1512082655305404456  # ไอดี ห้องที่จะให้บอทลง

@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    
    # รอให้ระบบพร้อมสักครู่
    await asyncio.sleep(5)
    
    guild = bot.get_guild(BotSever1)
    if guild:
        vc = guild.get_channel(BotSever2)
        if vc:
            try:
                # คำสั่งเชื่อมต่อเข้าห้องเสียงจริง
                voice_client = await vc.connect()
                await voice_client.guild.change_voice_state(channel=vc, self_mute=False, self_deaf=True)
                print('Bot is ready and connected to voice.')
            except Exception as e:
                print(f"Voice connection error: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.self_stream:
        print(f'{member.name} is in {after.channel.name} and started streaming.')

if __name__ == "__main__":
    # เริ่มต้นรันเว็บเซิร์ฟเวอร์เบื้องหลัง
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอทโดยดึง Token จาก Environment Variables ของ Render (ปลอดภัยกว่าใส่ตรงๆ)
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
