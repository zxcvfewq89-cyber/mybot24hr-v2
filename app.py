import asyncio
from datetime import datetime
import os
import random
import sys
from threading import Thread
import discord
from discord.ext import commands, tasks
from flask import Flask
import requests

# ==========================================
# CONFIG (ดึง Token จาก Environment Variables ของโฮสต์)
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")
VOICE_CHANNEL_ID = 1512082646610739270  # ID ห้องเสียงของคุณ

# ==========================================
# สร้างเว็บเซิร์ฟเวอร์ด้วย Flask (สำหรับรันบนโฮสต์)
# ==========================================

app = Flask("")


@app.route("/")
def home():
  return "Bot is running 24/7! 🔥 Fast-AFK System is active."


def run_web():
  # ดึงพอร์ตจาก Render มาใช้โดยอัตโนมัติ (ป้องกันปัญหา No open ports detected)
  port = int(os.environ.get("PORT", 7860))
  app.run(host="0.0.0.0", port=port)


def self_ping():
  while True:
    try:
      # ใช้พอร์ตที่รันจริงหรือเรียกผ่าน localhost
      port = int(os.environ.get("PORT", 7860))
      requests.get(f"http://127.0.0.1:{port}", timeout=5)
    except Exception:
      pass
    import time

    time.sleep(30)


def keep_alive():
  t = Thread(target=run_web)
  t.daemon = True
  t.start()

  p = Thread(target=self_ping)
  p.daemon = True
  p.start()


# ==========================================
# คลาสบอทยืนห้องเงียบๆ
# ==========================================


class AFKBot:

  def __init__(self, token, voice_channel_id):
    self.token = token
    self.voice_channel_id = voice_channel_id
    self.bot = commands.Bot(command_prefix="!", intents=self.get_intents())
    self.start_time = datetime.now()
    self.setup_tasks()
    self.setup_commands()

  def get_intents(self):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.voice_states = True
    return intents

  def setup_tasks(self):
    @tasks.loop(seconds=1)
    async def rotate_presence():
      now = datetime.now()
      uptime_duration = now - self.start_time
      hours = int(uptime_duration.total_seconds() // 3600)
      minutes = int((uptime_duration.total_seconds() % 3600) // 60)
      seconds = int(uptime_duration.total_seconds() % 60)

      uptime_text = (
          f"⏱️ เปิดมาแล้ว: {hours}ชม. {minutes:02d}นาที {seconds:02d}วินาที"
      )
      activity = discord.CustomActivity(name=uptime_text)
      await self.bot.change_presence(activity=activity)

    self.rotate_presence_task = rotate_presence

  async def stay_in_voice(self):
    while True:
      try:
        voice_client = None
        if self.bot.guilds:
          for vc in self.bot.voice_clients:
            if vc.guild.id == self.bot.guilds[0].id:
              voice_client = vc
              break

        if not voice_client:
          channel = self.bot.get_channel(self.voice_channel_id)
          if channel:
            voice_client = await channel.connect()
            print(f"✅ บอท: เข้าห้อง {channel.name} แล้ว (เงียบ)")

        if voice_client and voice_client.channel.id != self.voice_channel_id:
          target_channel = self.bot.get_channel(self.voice_channel_id)
          if target_channel:
            await voice_client.move_to(target_channel)
            print("🔄 บอท: ถูกย้ายห้อง ดึงกลับเข้าห้องที่กำหนดทันที!")

        await asyncio.sleep(15)

      except Exception:
        await asyncio.sleep(15)

  def setup_commands(self):
    bot = self.bot

    @bot.event
    async def on_ready():
      self.start_time = datetime.now()

      if not self.rotate_presence_task.is_running():
        self.rotate_presence_task.start()

      print(f"✅ บอทออนไลน์ในชื่อ: {bot.user}")
      print(f"✅ อยู่ใน {len(bot.guilds)} เซิร์ฟเวอร์")
      print(f"✅ ห้องเสียง ID: {self.voice_channel_id}")
      print("🔇 โหมด: เงียบ (ไม่เล่นเสียง) | เช็คทุก 15 วินาที")

      bot.loop.create_task(self.stay_in_voice())

      try:
        await bot.tree.sync()
        print("✅ Sync คำสั่ง Slash Command (/) เรียบร้อย")
      except Exception as e:
        print(f"❌ Sync Error: {e}")

    @bot.event
    async def on_voice_state_update(member, before, after):
      if member.id != bot.user.id:
        return

      voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
      if voice_client and before.channel and not after.channel:
        await asyncio.sleep(1)
        channel = bot.get_channel(self.voice_channel_id)
        if channel:
          await channel.connect()
          print("🔄 บอท: หลุด/โดนเตะจากห้อง เชื่อมต่อใหม่ทันที!")

    @bot.tree.command(name="join", description="🎤 สั่งให้บอทเข้าห้องเสียง")
    async def join(interaction: discord.Interaction):
      await interaction.response.defer()
      channel = bot.get_channel(self.voice_channel_id)
      if not channel:
        embed = discord.Embed(
            title="❌ Error", description="ไม่พบห้องเสียง", color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return

      voice_client = discord.utils.get(
          bot.voice_clients, guild=interaction.guild
      )
      if voice_client:
        await voice_client.move_to(channel)
      else:
        await channel.connect()

      embed = discord.Embed(
          title="✅ บอทเข้าห้องแล้ว!",
          description=f"🎤 {channel.name}\n🔇 โหมดเงียบ",
          color=0x00ff88,
      )
      await interaction.followup.send(embed=embed)

    @bot.tree.command(name="leave", description="🎤 สั่งให้บอทออกจากห้องเสียง")
    async def leave(interaction: discord.Interaction):
      await interaction.response.defer()
      voice_client = discord.utils.get(
          bot.voice_clients, guild=interaction.guild
      )
      if voice_client:
        await voice_client.disconnect()
        embed = discord.Embed(title="✅ บอทออกจากห้องแล้ว!", color=0x00ff88)
        await interaction.followup.send(embed=embed)
      else:
        embed = discord.Embed(
            title="❌ Error",
            description="บอทยังไม่ได้อยู่ในห้องเสียง",
            color=0xff0000,
        )
        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="afk", description="📊 ดูสถานะบอท")
    async def afk_status(interaction: discord.Interaction):
      voice_client = discord.utils.get(
          bot.voice_clients, guild=interaction.guild
      )

      now = datetime.now()
      uptime_duration = now - self.start_time
      hours = int(uptime_duration.total_seconds() // 3600)
      minutes = int((uptime_duration.total_seconds() % 3600) // 60)
      seconds = int(uptime_duration.total_seconds() % 60)

      embed = discord.Embed(title="📊 สถานะบอท AFK", color=0x00ccff)

      if voice_client and voice_client.channel:
        embed.add_field(
            name="🟢 สถานะ", value="✅ กำลังยืนห้อง (เช็คทุก 15 วิ)", inline=True
        )
        embed.add_field(
            name="🎤 ห้อง", value=f"<#{voice_client.channel.id}>", inline=True
        )
      else:
        embed.add_field(
            name="🔴 สถานะ", value="❌ ไม่อยู่ในห้องเสียง", inline=True
        )

      embed.add_field(
          name="⏱️ เปิดใช้งานมาแล้ว",
          value=f"{hours} ชม. {minutes} นาที {seconds} วินาที",
          inline=False,
      )

      embed.set_footer(text="🔥 Fast-AFK System (15s check)")
      await interaction.response.send_message(embed=embed)


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
  if not TOKEN:
    print(
        "❌ Error: ไม่พบ Token กรุณาตั้งค่า Environment Variable ชื่อ"
        " 'DISCORD_TOKEN' บนโฮสต์ให้เรียบร้อย"
    )
    sys.exit(1)

  print("=" * 50)
  print("   🔥 ระบบบอทยืนห้อง (รันเว็บ + เช็คทุก 15 วินาที)")
  print("=" * 50)
  print(f"   🎤 ห้องเสียง ID: {VOICE_CHANNEL_ID}")
  print("=" * 50)
  print("")

  keep_alive()

  afk_bot = AFKBot(TOKEN, VOICE_CHANNEL_ID)

  try:
    asyncio.run(afk_bot.bot.start(TOKEN))
  except KeyboardInterrupt:
    print("\n👋 หยุดการทำงานของบอทแล้ว!")
  except Exception as e:
    print(f"❌ Error: {e}")
