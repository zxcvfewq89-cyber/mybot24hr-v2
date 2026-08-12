import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. เว็บเซิร์ฟเวอร์ (เพื่อให้ Render ไม่ตัดการทำงาน)
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is active"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอท
intents = nextcord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(intents=intents)

# ใส่ ID ของคุณที่นี่
GUILD_ID = 1204647300870311986
CHANNEL_ID = 1512082655305404456

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # รอให้ระบบพร้อมแล้วเข้าห้องเสียง
    await asyncio.sleep(5)
    guild = bot.get_guild(GUILD_ID)
    if guild:
        channel = guild.get_channel(CHANNEL_ID)
        if channel:
            try:
                voice_client = await channel.connect()
                await voice_client.guild.change_voice_state(channel=channel, self_deaf=True)
                print("Connected to voice channel.")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์
    threading.Thread(target=run_web, daemon=True).start()
    # รันบอท
    bot.run(os.environ.get("DISCORD_TOKEN"))
