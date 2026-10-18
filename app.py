import ccxt
import time
import requests
from datetime import datetime

# ========== ตั้งค่าคีย์และเว็บฮุก ==========
API_KEY = 'H4Gpt7rviQNwV9AWzdjJThvd5Nl4sXecOpFgbAAuh3shz6FX8CR3liUgifyHgkAu'
SECRET = '6KJe411P75mveNtGUpyQojPGPOli0KvV1fB85QzWkOUqFKarLN2cX4fLYsDI8Kmt'

# 🔴 ใส่ Discord Webhook URL ของคุณตรงนี้ 🔴
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1561407506402648276/8JndP66iMZYxguAWwWd92f6fzKREm8tSLTR5YXP6QNxUdwqLZOtSX1HJ1gveNBg50Fta'
# =======================================

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})
exchange.set_sandbox_mode(True) # โหมดทดลอง

SYMBOL = 'BTC/USDT'

# ฟังก์ชันสำหรับส่งข้อความไป Discord
def send_discord_message(message, color=3447003): # สีฟ้าเริ่มต้น
    if not DISCORD_WEBHOOK_URL or 'ใส่ของคุณตรงนี้' in DISCORD_WEBHOOK_URL:
        print("⚠️ ยังไม่ได้ใส่ Discord Webhook URL")
        return
        
    data = {
        "embeds": [{
            "title": "🤖 รายงานสถานะจากบอทเทรด",
            "description": message,
            "color": color, # 3447003 = สีฟ้า(ปกติ), 3066993 = สีเขียว(กำไร), 15158332 = สีแดง(ขาดทุน)
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"ส่ง Discord ไม่สำเร็จ: {e}")

def show_balance():
    try:
        balance = exchange.fetch_balance()
        btc_free = balance['free'].get('BTC', 0)
        usdt_free = balance['free'].get('USDT', 0)
        print(f"💰 ยอดเงินทดลอง: {btc_free:.6f} BTC | {usdt_free:.2f} USDT")
        return btc_free, usdt_free
    except Exception as e:
        print(f"ดึงยอดเงินไม่ได้: {e}")
        return 0, 0

def try_trade():
    try:
        # 1. ดึงราคา
        ticker = exchange.fetch_ticker(SYMBOL)
        price = ticker['last']
        print(f"\n📊 {SYMBOL} ราคาปัจจุบัน: {price}")
        
        btc_free, usdt_free = show_balance()

        if usdt_free < 10:
            print("❌ USDT ไม่พอ (ต้องมีอย่างน้อย 10 USDT)")
            return

        # 2. ส่งคำสั่งซื้อ
        print("⏳ กำลังส่งคำสั่งซื้อ...")
        amount_to_buy = 10 / price
        
        # สมมติฐาน: ถ้าซื้อแล้วราคาตก เราจะตัดขาดทุน (แต่ในโค้ดทดลองนี้เราซื้อขายทันทีเพื่อดูผล)
        order = exchange.create_market_buy_order(SYMBOL, amount_to_buy)
        
        # ดึงข้อมูลสถานะคำสั่งซื้อ
        order_status = order.get('status', 'unknown')
        order_price = order.get('average', price) or price
        order_cost = order.get('cost', 10) or 10
        
        print(f"✅ ซื้อสำเร็จ! Order ID: {order['id']}")
        
        # 3. ส่งสถานะการเทรดไปที่ Discord
        msg = (
            f"**ดำเนินการ:** ซื้อ (Buy)\n"
            f"**คู่เงิน:** {SYMBOL}\n"
            f"**ราคาที่ได้:** {order_price:.2f} USDT\n"
            f"**จำนวนเงิน:** {order_cost:.2f} USDT\n"
            f"**สถานะคำสั่ง:** {order_status.upper()}\n"
            f"**Order ID:** `{order['id']}`"
        )
        
        # เช็คว่าซื้อได้ราคาดีกว่าที่ตั้งใจไหมเพื่อกำหนดสี (ในที่นี้สมมติว่าซื้อสำเร็จคือปกติ)
        send_discord_message(msg, color=3447003) 
        
        # แสดงยอดเงินหลังซื้อ
        print("\n--- ยอดเงินหลังทำรายการ ---")
        show_balance()

    except Exception as e:
        error_msg = f"เกิดข้อผิดพลาด: {str(e)}"
        print(f"❌ {error_msg}")
        # แจ้งเตือน Error ไป Discord ด้วย (สีแดง)
        send_discord_message(error_msg, color=15158332)

if __name__ == '__main__':
    print("=== บอททดลอง Binance Spot Testnet (มีแจ้งเตือน Discord) ===")
    try_trade()
