import nextcord
from nextcord.ext import commands
import os
import threading
import asyncio
from flask import Flask

# 1. เว็บเซิร์ฟเวอร์สำหรับให้ UptimeRobot มา Ping (กันบอทดับ)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอทและ Intents ทั้งหมดเพื่อให้มองเห็นช่องเสียง
intents = nextcord.Intents.all()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever1 = 1204647300870311986  # ไอดี เซิร์ฟเวอร์ดิสคอร์ด[span_0](start_span)[span_0](end_span)
BotSever2 = 1512082655305404456  # ไอดี ห้องที่จะให้บอทลง[span_1](start_span)[span_1](end_span)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}[span_2](start_span)[span_2](end_span)')
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))[span_3](start_span)[span_3](end_span)
    
    # รอให้แคชของบอทโหลดข้อมูลเซิร์ฟเวอร์ทั้งหมดเสร็จก่อน (สำคัญมาก)
    await asyncio.sleep(5)
    
    guild = bot.get_guild(BotSever1)
    if guild:
        vc = guild.get_channel(BotSever2)
        if vc:
            try:
                # เช็คว่าเชื่อมต่ออยู่แล้วหรือยัง ถ้ายังให้เชื่อมต่อใหม่
                if guild.voice_client:
                    await guild.voice_client.move_to(vc)
                else:
                    voice_client = await vc.connect()
                    await voice_client.guild.change_voice_state(channel=vc, self_mute=False, self_deaf=True)[span_4](start_span)[span_4](end_span)
                print('Bot is ready and connected to voice.')[span_5](start_span)[span_5](end_span)
            except Exception as e:
                print(f"Voice connection error: {e}")
        else:
            print("Error: Could not find the voice channel! Please check CHANNEL ID.")
    else:
        print("Error: Could not find the guild! Please check GUILD ID.")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.self_stream:
        print(f'{member.name} is in {after.channel.name} and started speaking.')[span_6](start_span)[span_6](end_span)

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์เบื้องหลัง
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอทด้วย Token จาก Environment Variables
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
