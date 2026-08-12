import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands
import yt_dlp

# เว็บเซิร์ฟเวอร์
app = Flask(__name__)
@app.route("/")
def home(): return "Bot is running 24/7!"

def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ตั้งค่าบอท
bot = commands.Bot(intents=nextcord.Intents.all())
SONG_URL = "https://youtu.be/dHUPZiAwNC8?si=YVwaLBa2jYfGd1CL"
CHANNEL_ID = 1512082655305404456

def get_stream_url():
    ydl_opts = {'format': 'bestaudio', 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(SONG_URL, download=False)
        return info['url']

async def play_loop(voice_client):
    try:
        url = get_stream_url()
        ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        voice_client.play(nextcord.FFmpegPCMAudio(url, **ffmpeg_opts), after=lambda e: asyncio.run_coroutine_threadsafe(play_loop(voice_client), bot.loop))
    except Exception as e:
        print(f"Error: {e}")
        await asyncio.sleep(5)
        await play_loop(voice_client)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        vc = await channel.connect()
        await vc.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
        await play_loop(vc)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        await asyncio.sleep(2)
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            vc = await channel.connect()
            await play_loop(vc)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
