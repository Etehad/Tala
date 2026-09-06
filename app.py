import os
import time
import re
import threading
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# ---------- تنظیمات تلگرام (از متغیرهای محیطی) ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("متغیرهای محیطی BOT_TOKEN و CHAT_ID تنظیم نشده‌اند!")

# ---------- آدرس و شناسه‌های عناصر سایت ----------
URL_SITE = "https://www.iranjib.ir/showgroup/23/realtime_price/"
GOLD_PRICE_ID = "f_85_63_pr"
GOLD_CHANGE_ID = "f_85_64"
DOLLAR_PRICE_ID = "f_19054_127_pr"
DOLLAR_CHANGE_ID = "f_19054_99"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ---------- توابع کمکی ----------
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

    return {
        "gold_price": gold_price_rial / 10 if gold_price_rial else None,
        "gold_change": gold_change_rial / 10 if gold_change_rial else None,
        "gold_percent": gold_percent,
        "dollar_price": dollar_price_rial,          # ریال (تقسیم بر ۱۰ نشده)
        "dollar_change": dollar_change_rial,
        "dollar_percent": dollar_percent,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

def format_number(num, decimals=0):
    if num is None:
        return "---"
    if decimals == 0:
        return f"{num:,.0f}"
    else:
        return f"{num:,.{decimals}f}"

def make_message(data):
    if not data:
        return "❌ خطا در دریافت داده‌ها"

    # قیمت طلا
    gold_price_str = format_number(data['gold_price'], 0)
    # تغییرات طلا
    gold_change_str = format_number(data['gold_change'], 0) if data['gold_change'] is not None else "---"
    gold_percent_str = f"{data['gold_percent']:.2f}" if data['gold_percent'] is not None else "---"
    gold_sign = "+" if data['gold_change'] and data['gold_change'] > 0 else ""
    gold_percent_sign = "+" if data['gold_percent'] and data['gold_percent'] > 0 else ""

    # قیمت دلار
    dollar_price_str = format_number(data['dollar_price'], 0)
    # تغییرات دلار
    dollar_change_str = format_number(data['dollar_change'], 0) if data['dollar_change'] is not None else "---"
    dollar_percent_str = f"{data['dollar_percent']:.2f}" if data['dollar_percent'] is not None else "---"
    dollar_sign = "+" if data['dollar_change'] and data['dollar_change'] > 0 else ""
    dollar_percent_sign = "+" if data['dollar_percent'] and data['dollar_percent'] > 0 else ""

    # ساخت پیام با قرارگیری علامت در سمت چپ عدد (با کمک \u200E)
    lines = [
        f"💰 طلا: {gold_price_str} تومان",
        f"📊 تغییر امروز: \u200E{gold_sign}{gold_change_str} تومان (%\u200E{gold_percent_sign}{gold_percent_str})",
        "",
        f"💵 دلار: {dollar_price_str} تومان",
        f"📊 تغییر امروز: \u200E{dollar_sign}{dollar_change_str} تومان (%\u200E{dollar_percent_sign}{dollar_percent_str})"
    ]

    return "\n".join(lines)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print("✅ پیام با موفقیت ارسال شد")
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        return False

def worker():
    print("🚀 ترد worker شروع به کار کرد (هر 5 دقیقه)")
    send_telegram_message("🤖 ربات قیمت طلا و دلار راه‌اندازی شد و هر 5 دقیقه پیام ارسال می‌کند.")
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
        time.sleep(300)   # ۵ دقیقه

# ---------- شروع ترد worker در سطح ماژول (برای gunicorn) ----------
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()
print("🧵 ترد worker راه‌اندازی شد (daemon=True)")

# ---------- مسیرهای وب (برای سلامت سرویس) ----------
@app.route('/')
def index():
    return "🤖 ربات قیمت طلا و دلار فعال است. هر ۵ دقیقه یک پیام ارسال می‌شود."

@app.route('/health')
def health():
    return "OK", 200
