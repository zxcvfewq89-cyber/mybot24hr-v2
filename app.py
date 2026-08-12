import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. สร้างเว็บเซิร์ฟเวอร์ Flask สำหรับให้ Render และ UptimeRobot Ping
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# 2. ตั้งค่าบอท Discord และ Intents
intents = nextcord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever2 = 1512082655305404456  # ไอดี ห้องที่จะให้บอทลง

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    print('Bot is ready.')

@bot.slash_command(name="join", description="สั่งให้บอทเข้าห้องเสียงสแตนด์บาย")
async def join(interaction: nextcord.Interaction):
    channel = bot.get_channel(BotSever2)
    if channel:
        try:
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()
                await voice_client.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
            await interaction.response.send_message(f"✅ บอทเข้ามาสแตนด์บายในห้อง **{channel.name}** เรียบร้อย!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ เกิดข้อผิดพลาดในการเข้าห้อง: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ ไม่พบห้องเสียงที่ตั้งค่าไว้ กรุณาตรวจสอบ ID ห้องอีกครั้ง", ephemeral=True)

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์ Flask ในเบื้องหลัง (Background Thread) เพื่อเปิดพอร์ตให้ Render
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอท Discord เป็นกระบวนการหลัก (Main Process) เพื่อให้บอทออนไลน์และเชื่อมต่อได้เสถียร 100%
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
