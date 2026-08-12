import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands
import yt_dlp

# 1. เว็บเซิร์ฟเวอร์ Flask สำหรับเปิดพอร์ตให้ Render และให้ UptimeRobot Ping
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

BotSever2 = 1512082655305404456  # ID ห้องเสียงที่จะให้บอทลง

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    print('Bot is ready.')

# 3. คำสั่ง Slash Command สั่งให้บอทเข้าห้องเสียงสแตนด์บาย
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

# 4. คำสั่ง Slash Command สั่งให้บอทเล่นเพลงวนซ้ำเพื่อกันบอทหลุด
@bot.slash_command(name="play", description="เปิดเพลงวนซ้ำเพื่อกันบอทหลุดจากห้องเสียง")
async def play(interaction: nextcord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ คุณต้องอยู่ในห้องเสียงก่อนใช้งานคำสั่งนี้!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    
    if not interaction.guild.voice_client:
        voice_client = await channel.connect()
    else:
        voice_client = interaction.guild.voice_client
        await voice_client.move_to(channel)
    
    await interaction.response.defer(ephemeral=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            
        ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        # หยุดเสียงเก่าก่อนเล่นใหม่
        if voice_client.is_playing():
            voice_client.stop()

        def play_next(err):
            if not voice_client.is_connected():
                return
            try:
                voice_client.play(nextcord.FFmpegPCMAudio(url2, **ffmpeg_opts), after=play_next)
            except Exception as e:
                print(f"Error in loop: {e}")

        voice_client.play(nextcord.FFmpegPCMAudio(url2, **ffmpeg_opts), after=play_next)
        await interaction.followup.send(f"🎵 กำลังเล่นเพลงวนซ้ำเพื่อสแตนด์บายยาวๆ ครับ!", ephemeral=True)
    
    except Exception as e:
        await interaction.followup.send(f"❌ เกิดข้อผิดพลาดในการโหลดเพลง: {e}", ephemeral=True)

# 5. ระบบ Auto-Reconnect (ถ้าบอทหลุดจากห้อง จะดึงกลับเข้าห้องอัตโนมัติภายใน 5 วินาที)
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id:
        if before.channel is not None and after.channel is None:
            print("Bot disconnected! Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
            channel = bot.get_channel(BotSever2)
            if channel:
                try:
                    await channel.connect()
                except:
                    pass

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์ Flask ในเบื้องหลัง (Background Thread)
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอท Discord เป็นกระบวนการหลัก (Main Process)
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands
import yt_dlp

# 1. เว็บเซิร์ฟเวอร์ Flask สำหรับเปิดพอร์ตให้ Render และให้ UptimeRobot Ping
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

BotSever2 = 1512082655305404456  # ID ห้องเสียงที่จะให้บอทลง

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    print('Bot is ready.')

# 3. คำสั่ง Slash Command สั่งให้บอทเข้าห้องเสียงสแตนด์บาย
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

# 4. คำสั่ง Slash Command สั่งให้บอทเล่นเพลงวนซ้ำเพื่อกันบอทหลุด
@bot.slash_command(name="play", description="เปิดเพลงวนซ้ำเพื่อกันบอทหลุดจากห้องเสียง")
async def play(interaction: nextcord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ คุณต้องอยู่ในห้องเสียงก่อนใช้งานคำสั่งนี้!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    
    if not interaction.guild.voice_client:
        voice_client = await channel.connect()
    else:
        voice_client = interaction.guild.voice_client
        await voice_client.move_to(channel)
    
    await interaction.response.defer(ephemeral=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            
        ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        # หยุดเสียงเก่าก่อนเล่นใหม่
        if voice_client.is_playing():
            voice_client.stop()

        def play_next(err):
            if not voice_client.is_connected():
                return
            try:
                voice_client.play(nextcord.FFmpegPCMAudio(url2, **ffmpeg_opts), after=play_next)
            except Exception as e:
                print(f"Error in loop: {e}")

        voice_client.play(nextcord.FFmpegPCMAudio(url2, **ffmpeg_opts), after=play_next)
        await interaction.followup.send(f"🎵 กำลังเล่นเพลงวนซ้ำเพื่อสแตนด์บายยาวๆ ครับ!", ephemeral=True)
    
    except Exception as e:
        await interaction.followup.send(f"❌ เกิดข้อผิดพลาดในการโหลดเพลง: {e}", ephemeral=True)

# 5. ระบบ Auto-Reconnect (ถ้าบอทหลุดจากห้อง จะดึงกลับเข้าห้องอัตโนมัติภายใน 5 วินาที)
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id:
        if before.channel is not None and after.channel is None:
            print("Bot disconnected! Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
            channel = bot.get_channel(BotSever2)
            if channel:
                try:
                    await channel.connect()
                except:
                    pass

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์ Flask ในเบื้องหลัง (Background Thread)
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอท Discord เป็นกระบวนการหลัก (Main Process)
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
