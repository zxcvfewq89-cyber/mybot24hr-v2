import asyncio
from datetime import datetime
import os
from threading import Thread
import time
import discord
from flask import Flask

# ==========================================
# 1. เว็บเซิร์ฟเวอร์ (Flask) รัน 24/7 บน Render
# ==========================================

app = Flask("")


@app.route("/")
def home():
  return "Bot is running 24/7!"


def run_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  t = Thread(target=run_web)
  t.daemon = True
  t.start()


# ==========================================
# 2. ตั้งค่าบอท Discord (ใช้ commands.Bot เพื่อความเสถียรของเสียง)
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")
VOICE_CHANNEL_ID = os.getenv("VOICE_CHANNEL_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

client = discord.Client(intents=intents)
start_time = None


# ==========================================
# 3. เหตุการณ์เมื่อบอทรันสำเร็จ
# ==========================================
@client.event
async def on_ready():
  global start_time
  start_time = datetime.now()
  print(f"✅ บอทออนไลน์ในชื่อ: {client.user}")

  # เริ่มรันเวลานับถอยหลังโชว์ที่สถานะ
  client.loop.create_task(update_uptime_presence())

  # เชื่อมต่อเข้าห้องเสียงอัตโนมัติ
  if VOICE_CHANNEL_ID:
    try:
      channel_id = int(VOICE_CHANNEL_ID)
      # รอให้แคชโหลดเซิร์ฟเวอร์เสร็จครู่หนึ่ง
      await asyncio.sleep(3)

      channel = client.get_channel(channel_id)
      if not channel:
        channel = await client.fetch_channel(channel_id)

      if channel and isinstance(channel, discord.VoiceChannel):
        # เช็กว่าบอทอยู่ในห้องอื่นอยู่แล้วไหม ถ้ามีให้ออกก่อน
        for vc in client.voice_clients:
          await vc.disconnect(force=True)

        # เชื่อมต่อเข้าห้องเสียงโดยตรง
        await channel.connect()
        print(f"🎤 บอทเข้ามาอยู่ในห้องเสียง: {channel.name} สำเร็จ!")
      else:
        print("❌ ไม่พบ Voice Channel ตาม ID ที่ระบุ หรือไม่ใช่ห้องเสียง")
    except Exception as e:
      print(f"❌ เกิดข้อผิดพลาดตอนเข้าห้องเสียง: {e}")
  else:
    print("⚠️ ยังไม่ได้ตั้งค่า VOICE_CHANNEL_ID")


async def update_uptime_presence():
  while True:
    if start_time:
      now = datetime.now()
      duration = now - start_time
      hours = int(duration.total_seconds() // 3600)
      minutes = int((duration.total_seconds() % 3600) // 60)
      seconds = int(duration.total_seconds() % 60)

      uptime_text = (
          f"⏱️ เปิดมาแล้ว: {hours}ชม. {minutes:02d}นาที {seconds:02d}วินาที"
      )
      await client.change_presence(activity=discord.CustomActivity(name=uptime_text))
    await asyncio.sleep(1)


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
