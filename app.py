import asyncio
from datetime import datetime
import os
from threading import Thread
import discord
from discord import app_commands
from flask import Flask

# ==========================================
# 1. เว็บเซิร์ฟเวอร์ (Flask) รัน 24/7 บน Render
# ==========================================

app = Flask("")


@app.route("/")
def home():
  return "Bot is running 24/7 with Slash Commands!"


def run_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  t = Thread(target=run_web)
  t.daemon = True
  t.start()


# ==========================================
# 2. ตั้งค่าบอท Discord (ใช้ Client + CommandTree)
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


class MyBot(discord.Client):

  def __init__(self):
    super().__init__(intents=intents)
    self.tree = app_commands.CommandTree(self)
    self.start_time = None

  async def setup_hook(self):
    # ซิงค์คำสั่ง Slash Command กับ Discord
    await self.tree.sync()
    print("🔄 ซิงค์ Slash Commands สำเร็จแล้ว!")


client = MyBot()


# ==========================================
# 3. เหตุการณ์เมื่อบอทพร้อมทำงาน
# ==========================================
@client.event
async def on_ready():
  client.start_time = datetime.now()
  print(f"✅ บอทออนไลน์ในชื่อ: {client.user}")
  client.loop.create_task(update_uptime_presence())


async def update_uptime_presence():
  while True:
    if client.start_time:
      now = datetime.now()
      duration = now - client.start_time
      hours = int(duration.total_seconds() // 3600)
      minutes = int((duration.total_seconds() % 3600) // 60)
      seconds = int(duration.total_seconds() % 60)

      uptime_text = (
          f"⏱️ เปิดมาแล้ว: {hours}ชม. {minutes:02d}นาที {seconds:02d}วินาที"
      )
      await client.change_presence(activity=discord.CustomActivity(name=uptime_text))
    await asyncio.sleep(1)


# ==========================================
# 4. คำสั่ง Slash Commands (เข้า/ออกห้องเสียง)
# ==========================================


@client.tree.command(
    name="เข้าห้องเสียง", description="ให้บอทเข้ามาในห้องเสียงที่คุณกำลังใช้งานอยู่"
)
async def join_vc(interaction: discord.Interaction):
  # ตรวจสอบว่าผู้ใช้กดคำสั่งอยู่ในห้องเสียงหรือไม่
  if interaction.user.voice and interaction.user.voice.channel:
    channel = interaction.user.voice.channel
    try:
      # เช็กว่าบอทอยู่ในห้องอื่นอยู่แล้วไหม ถ้ามีให้ย้ายหรือออกก่อน
      if interaction.guild.voice_client:
        await interaction.guild.voice_client.move_to(channel)
      else:
        await channel.connect()

      await interaction.response.send_message(
          f"🎤 เข้ามาอยู่ในห้องเสียง **{channel.name}** เรียบร้อยแล้วครับ!",
          ephemeral=False,
      )
    except Exception as e:
      await interaction.response.send_message(
          f"❌ เกิดข้อผิดพลาดในการเข้าห้องเสียง: {e}", ephemeral=True
      )
  else:
    await interaction.response.send_message(
        "⚠️ คุณต้องเข้าไปอยู่ในห้องเสียงก่อน ถึงจะเรียกใช้คำสั่งนี้ได้ครับ!",
        ephemeral=True,
    )


@client.tree.command(
    name="ออกจากห้องเสียง", description="ให้บอทออกจากห้องเสียง"
)
async def leave_vc(interaction: discord.Interaction):
  if interaction.guild.voice_client:
    await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message(
        "👋 ออกจากห้องเสียงเรียบร้อยแล้วครับ!", ephemeral=False
    )
  else:
    await interaction.response.send_message(
        "⚠️ บอทไม่ได้อยู่ในห้องเสียงไหนเลยครับตอนนี้", ephemeral=True
    )


# ==========================================
# RUN APPLICATION
# ==========================================
if __name__ == "__main__":
  if not TOKEN:
    print("❌ Error: ไม่พบ DISCORD_TOKEN")
    sys.exit(1)

  keep_alive()

  try:
    client.run(TOKEN)
  except Exception as e:
    print(f"❌ Error: {e}")
