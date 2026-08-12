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
CHANNEL_ID = 1512082655305404456 

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    print('Bot is ready.')
    
    # เมื่อบอทออนไลน์ ให้เข้าห้องเสียงอัตโนมัติทันที
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        try:
            voice_client = await channel.connect()
            await voice_client.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
            
            # เล่นเสียงเงียบวนลูปเพื่อให้บอทอยู่ในห้องตลอดเวลา
            def play_silent(err=None):
                if voice_client and voice_client.is_connected():
                    source = nextcord.FFmpegPCMAudio("anullsrc=r=48000:cl=stereo", pipe=True, before_options="-f lavfi")
                    voice_client.play(source, after=play_silent)
            
            play_silent()
            print("Bot joined voice channel and started 24/7 standby mode.")
        except Exception as e:
            print(f"Error joining channel: {e}")

# 3. ระบบ Auto-Reconnect (ถ้าหลุด ดึงกลับเข้าห้องอัตโนมัติ)
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel is not None and after.channel is None:
        await asyncio.sleep(3)
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            try:
                voice_client = await channel.connect()
                def play_silent(err=None):
                    source = nextcord.FFmpegPCMAudio("anullsrc=r=48000:cl=stereo", pipe=True, before_options="-f lavfi")
                    voice_client.play(source, after=play_silent)
                play_silent()
            except: 
                pass

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    token = os.environ.get("DISCORD_TOKEN")
    if token: 
        bot.run(token)
