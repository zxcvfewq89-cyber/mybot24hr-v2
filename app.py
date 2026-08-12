import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. เว็บเซิร์ฟเวอร์ Flask สำหรับ Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# 2. ตั้งค่าบอท
intents = nextcord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever2 = 1512082655305404456 

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    print('Bot is ready.')

# 3. คำสั่ง /play (โหมดเสียงเงียบ 24/7)
@bot.slash_command(name="play", description="เปิดโหมดสแตนด์บาย 24/7 แบบไม่หลุด")
async def play(interaction: nextcord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ คุณต้องอยู่ในห้องเสียงก่อน!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    
    if not interaction.guild.voice_client:
        voice_client = await channel.connect()
    else:
        voice_client = interaction.guild.voice_client
        await voice_client.move_to(channel)

    # ฟังก์ชันเล่นเสียงเงียบแบบวนลูป
    def play_silent(err=None):
        if voice_client and voice_client.is_connected():
            # ใช้ ffmpeg สร้างเสียงเงียบแบบไม่มีวันจบ
            source = nextcord.FFmpegPCMAudio("anullsrc=r=48000:cl=stereo", pipe=True, before_options="-f lavfi")
            voice_client.play(source, after=play_silent)

    if not voice_client.is_playing():
        play_silent()
        await interaction.response.send_message("✅ บอทเข้าโหมดสแตนด์บาย 24/7 เรียบร้อย! (บอทจะไม่ออกจากห้องแล้ว)")
    else:
        await interaction.response.send_message("⚠️ บอทอยู่ในห้องเสียงและกำลังทำงานอยู่ครับ")

# 4. ระบบ Auto-Reconnect
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel is not None and after.channel is None:
        await asyncio.sleep(2)
        channel = bot.get_channel(BotSever2)
        if channel:
            try:
                voice_client = await channel.connect()
                # เมื่อกลับเข้าห้อง ให้เริ่มเล่นเสียงเงียบใหม่ทันที
                def play_silent(err=None):
                    source = nextcord.FFmpegPCMAudio("anullsrc=r=48000:cl=stereo", pipe=True, before_options="-f lavfi")
                    voice_client.play(source, after=play_silent)
                play_silent()
            except: pass

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    token = os.environ.get("DISCORD_TOKEN")
    if token: bot.run(token)

