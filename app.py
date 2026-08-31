import asyncio
from datetime import datetime
import os
from threading import Thread
import time
import discord
from discord import app_commands
from flask import Flask

# ==========================================
# 1. ระบบเว็บเซิร์ฟเวอร์ (Flask) สำหรับรัน 24/7 บน Render
# ==========================================

app = Flask("")


@app.route("/")
def home():
  return "Bot is running 24/7! 🔥 Voice Control System is active."


def run_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  t = Thread(target=run_web)
  t.daemon = True
  t.start()


# ==========================================
# 2. ตั้งค่าบอท Discord และ Intents
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


class VoiceBot(discord.Client):

  def __init__(self):
    super().__init__(intents=intents)
    self.tree = app_commands.CommandTree(self)
    self.start_time = None

  async def setup_hook(self):
    await self.tree.sync()
    print("✅ Sync คำสั่ง Slash Command (/) เรียบร้อย")


client = VoiceBot()

# ==========================================
# 3. ระบบนับเวลาออนไลน์
# ==========================================


@client.event
async def on_ready():
  client.start_time = datetime.now()
  print(f"✅ บอทออนไลน์ในชื่อ: {client.user}")
  print(f"✅ อยู่ใน {len(client.guilds)} เซิร์ฟเวอร์")

  # เริ่มลูปอัปเดตสถานะนับเวลาทุกๆ 1 นาที
  client.loop.create_task(update_uptime_presence())


async def update_uptime_presence():
  while True:
    if client.start_time:
      now = datetime.now()
      uptime_duration = now - client.start_time
      hours = int(uptime_duration.total_seconds() // 3600)
      minutes = int((uptime_duration.total_seconds() % 3600) // 60)
      seconds = int(uptime_duration.total_seconds() % 60)

      # ข้อความที่จะแสดงตรงสถานะบอท
      uptime_text = (
          f"⏱️ เปิดมาแล้ว: {hours}ชม. {minutes:02d}นาที {seconds:02d}วินาที"
      )
      activity = discord.CustomActivity(name=uptime_text)
      await client.change_presence(activity=activity)
    await asyncio.sleep(1)


# ==========================================
# 4. สร้าง Slash Commands (/เข้าห้องเสียง, /ออกห้องเสียง)
# ==========================================


@client.tree.command(
    name="เข้าห้องเสียง", description="🎤 สั่งให้บอทเข้ามาในห้องเสียงที่คุณอยู่"
)
async def join_voice(interaction: discord.Interaction):
  if interaction.user.voice and interaction.user.voice.channel:
    channel = interaction.user.voice.channel

    if interaction.guild.voice_client is not None:
      await interaction.guild.voice_client.move_to(channel)
      await interaction.response.send_message(
          f"🔄 ย้ายมาที่ห้อง **{channel.name}** เรียบร้อยครับ!", ephemeral=True
      )
    else:
      await channel.connect()
      await interaction.response.send_message(
          f"✅ เข้ามาที่ห้อง **{channel.name}** แล้วครับ!", ephemeral=True
      )
  else:
    await interaction.response.send_message(
        "❌ คุณต้องเข้าห้องเสียงก่อนใช้งานคำสั่งนี้!", ephemeral=True
    )


@client.tree.command(
    name="ออกห้องเสียง", description="🎤 สั่งให้บอทร่อกออกจากห้องเสียง"
)
async def leave_voice(interaction: discord.Interaction):
  if interaction.guild.voice_client is not None:
    await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message(
        "✅ ออกจากห้องเสียงเรียบร้อยแล้วครับ!", ephemeral=True
    )
  else:
    await interaction.response.send_message(
        "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ!", ephemeral=True
    )


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
  if not TOKEN:
    print(
        "❌ Error: ไม่พบ Token กรุณาตั้งค่า Environment Variable ชื่อ"
        " 'DISCORD_TOKEN' ให้เรียบร้อย"
    )
    sys.exit(1)

  print("=" * 50)
  print("   🔥 ระบบบอท Discord ควบคุมด้วยคำสั่งเสียง + นับเวลา")
  print("=" * 50)

  # เริ่มรันเว็บเซอร์เวอร์ไว้ก่อนเพื่อกัน Render ตัดระบบ
  keep_alive()

  # รันบอท
  try:
    client.run(TOKEN)
  except KeyboardInterrupt:
    print("\n👋 หยุดการทำงานของบอทแล้ว!")
  except Exception as e:
    print(f"❌ Error: {e}")
