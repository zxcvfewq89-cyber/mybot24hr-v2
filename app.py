import asyncio
from datetime import datetime
import os
from threading import Thread
import time
import discord
from flask import Flask

# ==========================================
# 1. ระบบเว็บเซิร์ฟเวอร์ (Flask) รัน 24/7 บน Render
# ==========================================

app = Flask("")


@app.route("/")
def home():
  return "Bot is running 24/7 in Voice Channel! 🔥"


def run_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  t = Thread(target=run_web)
  t.daemon = True
  t.start()


# ==========================================
# 2. ตั้งค่าบอท Discord
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")
VOICE_CHANNEL_ID = os.getenv("VOICE_CHANNEL_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


class AlwaysOnlineVoiceBot(discord.Client):

  def __init__(self):
    super().__init__(intents=intents)
    self.start_time = None


client = AlwaysOnlineVoiceBot()

# ==========================================
# 3. เมื่อบอทพร้อม -> ออนสถานะ + เข้าห้องเสียงอัติโนมัติ
# ==========================================


@client.event
async def on_ready():
  client.start_time = datetime.now()
  print(f"✅ บอทออนไลน์ในชื่อ: {client.user}")

  # เริ่มลูปนับเวลาโชว์ที่สถานะ
  client.loop.create_task(update_uptime_presence())

  # สั่งให้บอทเชื่อมต่อเข้าห้องเสียงอัตโนมัติทันที
  if VOICE_CHANNEL_ID:
    try:
      channel_id = int(VOICE_CHANNEL_ID)
      channel = client.get_channel(channel_id)
      if channel is None:
        channel = await client.fetch_channel(channel_id)

      if channel:
        # เชื่อมต่อเข้าห้องเสียงโดยตรง (ใช้ตัวจัดการเสียงพื้นฐานของ discord.py)
        if client.voice_clients:
          for vc in client.voice_clients:
            await vc.disconnect()

        await channel.connect()
        print(f"🎤 บอทเข้ามาอยู่ในห้องเสียง: {channel.name} เรียบร้อยแล้ว!")
      else:
        print(
            "❌ ไม่พบห้องเสียงตาม ID ที่ระบุ กรุณาตรวจสอบ VOICE_CHANNEL_ID"
            " อีกครั้ง"
        )
    except Exception as e:
      print(f"❌ เกิดข้อผิดพลาดในการเข้าห้องเสียง: {e}")
  else:
    print(
        "⚠️ คำเตือน: ยังไม่ได้ตั้งค่า Environment Variable 'VOICE_CHANNEL_ID'"
    )


async def update_uptime_presence():
  while True:
    if client.start_time:
      now = datetime.now()
      uptime_duration = now - client.start_time
      hours = int(uptime_duration.total_seconds() // 3600)
      minutes = int((uptime_duration.total_seconds() % 3600) // 60)
      seconds = int(uptime_duration.total_seconds() % 60)

      uptime_text = (
          f"⏱️ เปิดมาแล้ว: {hours}ชม. {minutes:02d}นาที {seconds:02d}วินาที"
      )
      activity = discord.CustomActivity(name=uptime_text)
      await client.change_presence(activity=activity)
    await asyncio.sleep(1)


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
  if not TOKEN:
    print("❌ Error: ไม่พบ DISCORD_TOKEN")
    sys.exit(1)

  print("=" * 50)
  print("   🔥 ระบบบอทออนห้องเสียง 24 ชั่วโมง + นับเวลา")
  print("=" * 50)

  keep_alive()

  try:
    client.run(TOKEN)
  except KeyboardInterrupt:
    print("\n👋 ปิดการทำงานของบอทแล้ว!")
  except Exception as e:
    print(f"❌ Error: {e}")
