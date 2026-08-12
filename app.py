import nextcord
from nextcord.ext import commands
import os
import threading
import asyncio
from flask import Flask

# 1. เว็บเซิร์ฟเวอร์สำหรับให้ UptimeRobot มา Ping (กันบอทดับบน Render)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอทและ Intents
intents = nextcord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever1 = 1204647300870311986  # ไอดี เซิร์ฟเวอร์ดิสคอร์ด[span_1](start_span)[span_1](end_span)
BotSever2 = 1512082655305404456  # ไอดี ห้องที่จะให้บอทลง[span_2](start_span)[span_2](end_span)

@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))[span_3](start_span)[span_3](end_span)
    
    # รอให้ระบบพร้อมสักครู่
    await asyncio.sleep(5)
    
    try:
        guild = bot.get_guild(BotSever1)
        if guild:
            vc = nextcord.utils.get(guild.channels, id=BotSever2)
            if vc:
                # เชื่อมต่อเข้าห้องเสียงจริงแบบเสถียร
                voice_client = await vc.connect()
                await voice_client.guild.change_voice_state(channel=vc, self_mute=False, self_deaf=True)[span_4](start_span)[span_4](end_span)
                print('Bot is ready and connected to voice.')[span_5](start_span)[span_5](end_span)
    except Exception as e:
        print(f"Voice connection error: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.self_stream:
        print(f'{member.name} is in {after.channel.name} and started speaking.')[span_6](start_span)[span_6](end_span)

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์เบื้องหลัง
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอทด้วย Token จาก Environment Variables ของ Render
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
