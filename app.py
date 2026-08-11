import os
import threading
import asyncio
from flask import Flask
import nextcord
from nextcord.ext import commands

# 1. เว็บเซิร์ฟเวอร์สำหรับ Render (ใช้พอร์ต 10000 ตามที่ Render กำหนด)
app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="0; url=https://discord.com" />
</head>
<body></body>
</html>
"""

@app.route("/")
def home():
    return HTML_CONTENT

def run_web():
    app.run(host="0.0.0.0", port=10000)

# 2. ตั้งค่าบอท Nextcord และเปิด Intents ครบถ้วน (แก้ปัญหาบอทไม่เห็นห้องเสียง)
intents = nextcord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

BotSever1 = 1204647300870311986  # ไอดี เซิร์ฟเวอร์ดิสคอร์ด
BotSever2 = 1512082655305404456  # ไอดี ห้องเสียง

@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Streaming(
        name="Phakaphop", url="https://www.twitch.tv/phakaphpop"))
    
    # หน่วงเวลา 3 วินาทีเพื่อให้บอทเชื่อมต่อเซิร์ฟเวอร์และโหลดช่องทั้งหมดเสร็จก่อน
    await asyncio.sleep(3)
    
    try:
        guild = bot.get_guild(BotSever1)
        if guild:
            # ใช้ get_channel เพื่อดึงห้องเสียงให้ชัวร์ยิ่งขึ้น
            vc = guild.get_channel(BotSever2)
            if vc and not guild.voice_client:
                await vc.connect(self_deaf=True)
                print(f"Successfully joined voice channel: {vc.name}")
            else:
                print("Could not find voice channel or already connected.")
        else:
            print("Could not find guild.")
    except Exception as e:
        print(f"Voice join error: {e}")
        
    print('Bot is ready.')

# ระบบปุ่มกดดูสินค้าในร้านค้า (View)
class ShopView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label="⚔️ ไอเทมหายาก", style=nextcord.ButtonStyle.primary, custom_id="rare_item")
    async def rare_item_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        embed = nextcord.Embed(title="⚔️ หมวดหมู่: ไอเทมหายาก", description="รายการไอเทมระดับตำนานที่มีจำหน่าย:", color=nextcord.Color.blue())
        embed.add_field(name="[1] ดาบมหากาฬ +10", value="ราคา: 150 บาท | คงเหลือ: 5 ชิ้น", inline=False)
        embed.add_field(name="[2] เกราะเทพเจ้า", value="ราคา: 250 บาท | คงเหลือ: 2 ชิ้น", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @nextcord.ui.button(label="🧪 ยาและไอเทมฟื้นฟู", style=nextcord.ButtonStyle.success, custom_id="potion_item")
    async def potion_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        embed = nextcord.Embed(title="🧪 หมวดหมู่: ยาและไอเทมฟื้นฟู", description="รายการยาเพิ่มพลังและบัฟต่างๆ:", color=nextcord.Color.green())
        embed.add_field(name="[3] ยาฟื้นพลัง (x50)", value="ราคา: 30 บาท | คงเหลือ: 99 ชิ้น", inline=False)
        embed.add_field(name="[4] ยาเพิ่มพลังโจมตี", value="ราคา: 50 บาท | คงเหลือ: 40 ชิ้น", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="store", description="เปิดแผงควบคุมร้านค้าและดูสินค้า")
async def store(interaction: nextcord.Interaction):
    embed = nextcord.Embed(title="🛒 ร้านค้าไอเทมเกมออนไลน์", description="ยินดีต้อนรับสู่หน้าร้านค้า! กรุณาเลือกหมวดหมู่สินค้าที่คุณต้องการจากปุ่มด้านล่าง:", color=nextcord.Color.gold())
    await interaction.response.send_message(embed=embed, view=ShopView())

@bot.slash_command(name="status", description="ตรวจสอบสถานะการทำงานของบอท")
async def status(interaction: nextcord.Interaction):
    embed = nextcord.Embed(title="🤖 สถานะบอท", description="บอททำงานปกติและพร้อมให้บริการครับ!", color=nextcord.Color.green())
    embed.add_field(name="สถานะเซิร์ฟเวอร์", value="✅ ออนไลน์ 24/7", inline=True)
    embed.add_field(name="ความหน่วง (Latency)", value=f"{round(bot.latency * 1000)} ms", inline=True)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    # รันเว็บเซิร์ฟเวอร์ Flask ไว้ที่พอร์ต 10000 (สำหรับ Render)
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # ดึง Token จาก Environment Variables ของ Render อย่างปลอดภัย
    token = os.environ.get("DISCORD_TOKEN")
    bot.run(token)
