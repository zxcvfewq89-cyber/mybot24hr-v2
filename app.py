import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. สร้างเว็บเซิร์ฟเวอร์ Flask เพื่อเปิดพอร์ตให้ Render ตรวจจับ
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. ตั้งค่าบอท Discord
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

# 3. ฟังก์ชันสำหรับรันบอท Discord แยกออกมาต่างหาก
def run_bot():
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")

if __name__ == "__main__":
    # รันบอท Discord ในเบื้องหลัง (Background Thread)
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # รันเว็บเซิร์ฟเวอร์ Flask เป็นกระบวนการหลัก (Main Process) เพื่อให้ Render จับพอร์ตได้ทันที
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
