import nextcord
from nextcord.ext import commands
import os
import threading
import asyncio
from flask import Flask

# 1. เว็บเซิร์ฟเวอร์สำหรับให้ UptimeRobot มา Ping (กันบอทดับ)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอทและ Intents
intents = nextcord.Intents.all()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever2 = 1512082655305404456  # ไอดี ห้องที่จะให้บอทลง[span_1](start_span)[span_1](end_span)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')[span_2](start_span)[span_2](end_span)
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))[span_3](start_span)[span_3](end_span)
    print('Bot is ready.')[span_4](start_span)[span_4](end_span)

# 3. คำสั่ง Slash Command สั่งให้บอทเข้าห้องเสียง
@bot.slash_command(name="join", description="สั่งให้บอทเข้าห้องเสียงสแตนด์บาย")
async def join(interaction: nextcord.Interaction):
    channel = bot.get_channel(BotSever2)
    
    if channel:
        try:
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()
                await voice_client.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)[span_5](start_span)[span_5](end_span)
            
            await interaction.response.send_message(f"✅ บอทเข้ามาสแตนด์บายในห้อง **{channel.name}** เรียบร้อย!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ เกิดข้อผิดพลาดในการเข้าห้อง: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ ไม่พบห้องเสียงที่ตั้งค่าไว้ กรุณาตรวจสอบ ID ห้องอีกครั้ง", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.self_stream:
        print(f'{member.name} is in {after.channel.name} and started speaking.')[span_6](start_span)[span_6](end_span)

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์เบื้องหลัง
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # รันบอทด้วย Token จาก Environment Variables
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
