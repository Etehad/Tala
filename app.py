import os
import time
import re
import threading
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# ---------- تنظیمات تلگرام (همان‌هایی که خواستی) ----------
BOT_TOKEN = "8430179675:AAGxwcLMKHRC02yIT-qpkNRa32eV9n75ehU"
CHAT_ID = "-1004441007289"   # آیدی عددی چنل (با منفی)

# ---------- آدرس و شناسه‌های عناصر سایت ----------
URL_SITE = "https://www.iranjib.ir/showgroup/23/realtime_price/"
GOLD_PRICE_ID = "f_85_63_pr"
GOLD_CHANGE_ID = "f_85_64"
DOLLAR_PRICE_ID = "f_19054_127_pr"
DOLLAR_CHANGE_ID = "f_19054_99"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ---------- توابع کمکی (همان کد قبلی) ----------
def clean_number(text):
    if not text:
        return None
    text = text.replace(",", "").replace("٬", "").strip()
    try:
        return float(text)
    except ValueError:
        return None

def extract_change(change_html):
    soup = BeautifulSoup(change_html, "html.parser")
    percent_text = soup.find("span", style=re.compile(r"color"))
    percent = None
    if percent_text:
        match = re.search(r"([+-]?\d+\.?\d*)%", percent_text.text)
        if match:
            percent = float(match.group(1))
    price_span = soup.find("span", class_="lastprice")
    price_value = None
    if price_span:
        price_value = clean_number(price_span.text)
    return price_value, percent

def fetch_data():
    try:
        response = requests.get(URL_SITE, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ خطا در دریافت داده: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    gold_price_elem = soup.find(id=GOLD_PRICE_ID)
    if not gold_price_elem:
        print("⚠️ عنصر قیمت طلا پیدا نشد")
        return None
    gold_price_rial = clean_number(gold_price_elem.text)

    gold_change_elem = soup.find(id=GOLD_CHANGE_ID)
    gold_change_rial = gold_percent = None
    if gold_change_elem:
        gold_change_rial, gold_percent = extract_change(str(gold_change_elem))

    dollar_price_elem = soup.find(id=DOLLAR_PRICE_ID)
    if not dollar_price_elem:
        print("⚠️ عنصر قیمت دلار پیدا نشد")
        return None
    dollar_price_rial = clean_number(dollar_price_elem.text)

    dollar_change_elem = soup.find(id=DOLLAR_CHANGE_ID)
    dollar_change_rial = dollar_percent = None
    if dollar_change_elem:
        dollar_change_rial, dollar_percent = extract_change(str(dollar_change_elem))

    # تبدیل ریال به تومان (تقسیم بر ۱۰)
    return {
        "gold_price": gold_price_rial / 10 if gold_price_rial else None,
        "gold_change": gold_change_rial / 10 if gold_change_rial else None,
        "gold_percent": gold_percent,
        "dollar_price": dollar_price_rial / 10 if dollar_price_rial else None,
        "dollar_change": dollar_change_rial / 10 if dollar_change_rial else None,
        "dollar_percent": dollar_percent,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

def format_number(num, decimals=0):
    if num is None:
        return "---"
    return f"{num:,.{decimals}f}" if decimals > 0 else f"{num:,.0f}"

def make_message(data):
    if not data:
        return "❌ خطا در دریافت داده‌ها"

    gold_emoji = "📈" if data["gold_change"] and data["gold_change"] > 0 else "📉" if data["gold_change"] and data["gold_change"] < 0 else "➖"
    dollar_emoji = "📈" if data["dollar_change"] and data["dollar_change"] > 0 else "📉" if data["dollar_change"] and data["dollar_change"] < 0 else "➖"

    lines = [
        f"🕒 زمان بروزرسانی: {data['timestamp']}",
        ""
    ]
    gold_str = f"💰 طلا: {format_number(data['gold_price'], 0)} تومان"
    if data["gold_change"] is not None and data["gold_percent"] is not None:
        sign = "+" if data["gold_change"] > 0 else ""
        gold_str += f"  {gold_emoji} تغییر امروز: {sign}{format_number(data['gold_change'], 0)} تومان ({sign}{data['gold_percent']:.2f}%)"
    lines.append(gold_str)

    dollar_str = f"💵 دلار: {format_number(data['dollar_price'], 1)} تومان"
    if data["dollar_change"] is not None and data["dollar_percent"] is not None:
        sign = "+" if data["dollar_change"] > 0 else ""
        dollar_str += f"  {dollar_emoji} تغییر امروز: {sign}{format_number(data['dollar_change'], 0)} تومان ({sign}{data['dollar_percent']:.2f}%)"
    lines.append(dollar_str)

    return "\n".join(lines)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print("✅ پیام با موفقیت ارسال شد")
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")

# ---------- حلقه اصلی ارسال هر 2 دقیقه ----------
def worker():
    while True:
        try:
            print("🔄 دریافت داده...")
            data = fetch_data()
            if data:
                msg = make_message(data)
                send_telegram_message(msg)
            else:
                print("⚠️ داده‌ای برای ارسال وجود ندارد")
        except Exception as e:
            print(f"❌ خطا در حلقه اصلی: {e}")
        time.sleep(120)   # ۵ دقیقه

# ---------- مسیرهای وب (برای نگهداری سرویس) ----------
@app.route('/')
def index():
    return "🤖 ربات قیمت طلا و دلار فعال است. هر 2 دقیقه یک پیام ارسال می‌شود."

@app.route('/health')
def health():
    return "OK", 200

# ---------- اجرای اصلی ----------
if __name__ == '__main__':
    # راه‌اندازی ترد ارسال‌کننده در پس‌زمینه
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # اجرای وب‌سرویس (Render پورت را از متغیر PORT می‌دهد)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
