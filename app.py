import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. เว็บเซิร์ฟเวอร์
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอท
intents = nextcord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(help_command=None, intents=intents)

BotSever1 = 1204647300870311986
BotSever2 = 1512082655305404456

@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Activity(
        type=nextcord.ActivityType.watching, 
        name="บอทออนไลน์ 24 ชม."
    ))
    print(f'Logged in as {bot.user}')
    
    # หน่วงเวลาให้บอทเชื่อมต่อเซิร์ฟเวอร์ดิสคอร์ดเสถียรก่อนเข้าห้อง
    await asyncio.sleep(8)
    
    guild = bot.get_guild(BotSever1)
    if guild:
        vc = guild.get_channel(BotSever2)
        if vc and not guild.voice_client:
            try:
                voice_client = await vc.connect()
                await voice_client.guild.change_voice_state(channel=vc, self_deaf=True)
                print("Joined voice channel successfully.")
            except Exception as e:
                print(f"Auto-join error: {e}")

# --- Slash Commands ---
@bot.slash_command(name="join", description="สั่งให้บอทเข้าห้องเสียง")
async def join(interaction: nextcord.Interaction):
    if interaction.user.voice and interaction.user.voice.channel:
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()
            await voice_client.guild.change_voice_state(channel=channel, self_deaf=True)
        await interaction.response.send_message(f"✅ เข้าห้อง {channel.name} เรียบร้อย!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ กรุณาเข้าห้องเสียงก่อนใช้คำสั่งนี้", ephemeral=True)

@bot.slash_command(name="leave", description="สั่งให้บอทออกจากห้องเสียง")
async def leave(interaction: nextcord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 บอทออกจากห้องเสียงแล้ว", ephemeral=True)
    else:
        await interaction.response.send_message("❌ บอทไม่ได้อยู่ในห้องเสียง", ephemeral=True)

class ShopView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label="⚔️ ไอเทมหายาก", style=nextcord.ButtonStyle.primary, custom_id="rare_item")
    async def rare_item_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        embed = nextcord.Embed(title="⚔️ ไอเทมหายาก", description="[1] ดาบมหากาฬ +10 | [2] เกราะเทพเจ้า", color=nextcord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="store", description="เปิดร้านค้า")
async def store(interaction: nextcord.Interaction):
    await interaction.response.send_message("🛒 ร้านค้าไอเทม:", view=ShopView(), ephemeral=True)

@bot.slash_command(name="status", description="เช็คสถานะ")
async def status(interaction: nextcord.Interaction):
    await interaction.response.send_message(f"✅ ออนไลน์ | Latency: {round(bot.latency * 1000)} ms", ephemeral=True)

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    token = os.environ.get("DISCORD_TOKEN")
    bot.run(token)

