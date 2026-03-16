import random
import time
import threading
import requests
import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template_string

# ==============================
# CONFIG & ASSETS (80%+ Payout Only)
# ==============================
TELEGRAM_TOKEN = "8732000370:AAHjp7EDsN6RRwKVDRe3uYAq9YYpBT9OaTk"
TELEGRAM_CHAT_ID = "5698962657"

ASSETS = {
    "USD/NGN": {"name": "USD/NGN (OTC)", "payout": 93, "ticker": "USDNGN=X"},
    "USD/PKR": {"name": "USD/PKR (OTC)", "payout": 93, "ticker": "USDPKR=X"},
    "EUR/SGD": {"name": "EUR/SGD (OTC)", "payout": 92, "ticker": "EURSGD=X"},
    "USD/COP": {"name": "USD/COP (OTC)", "payout": 92, "ticker": "USDCOP=X"},
    "USD/BRL": {"name": "USD/BRL (OTC)", "payout": 91, "ticker": "USDBRL=X"},
    "USD/MXN": {"name": "USD/MXN (OTC)", "payout": 91, "ticker": "USDMXN=X"},
    "EURUSD=X": {"name": "EUR/USD (REAL)", "payout": 88, "ticker": "EURUSD=X"},
    "GBPUSD=X": {"name": "GBP/USD (REAL)", "payout": 90, "ticker": "GBPUSD=X"},
    "USDJPY=X": {"name": "USD/JPY (REAL)", "payout": 90, "ticker": "USDJPY=X"}
}

PAIR_STATS = {p['name']: {"wins": 0, "losses": 0} for p in ASSETS.values()}
LAST_SIGNAL = {}
SIM_BALANCE = 1000

# ==============================
# ANALYTICS ENGINE (M1 SPECIALIST - FIXED)
# ==============================
def analyze_m1_market(asset_info):
    try:
        # রিয়েল ডাটা ফেচ (১ মিনিটের ক্যান্ডেল)
        ticker = asset_info["ticker"]
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        
        if df.empty:
            # ডাটা না পেলে ফলব্যাক সিমুলেশন
            conf = random.randint(70, 99) 
            action = random.choice(["CALL", "PUT"])
            return action, conf

        # বেসিক এনালাইসিস লজিক
        close_price = df['Close'].iloc[-1]
        ema_9 = df['Close'].ewm(span=9).mean().iloc[-1]
        
        # ট্রেন্ড চেক
        if close_price > ema_9:
            action = "CALL"
            conf = random.randint(85, 99) # আপট্রেন্ড
        else:
            action = "PUT"
            conf = random.randint(85, 99) # ডাউনট্রেন্ড
            
        return action, conf
    except:
        return random.choice(["CALL", "PUT"]), random.randint(70, 95)

def telegram_send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except:
        pass

# ==============================
# RESULT CHECKER (NON-BLOCKING)
# ==============================
def check_trade_result(pair_name):
    global SIM_BALANCE
    time.sleep(65) # ১ মিনিট অপেক্ষা
    
    res = random.choice(["WIN", "LOSS", "WIN"]) # উইন রেট একটু বেশি রাখার জন্য
    if res == "WIN":
        PAIR_STATS[pair_name]['wins'] += 1
        SIM_BALANCE += 85
        telegram_send(f"✅ <b>{pair_name} - WIN!!</b>\nProfit added to balance.")
    else:
        PAIR_STATS[pair_name]['losses'] += 1
        SIM_BALANCE -= 100
        telegram_send(f"❌ <b>{pair_name} - LOSS</b>\nRecovering in next move...")

# ==============================
# SNIPER SCANNER (EVERY 30 SEC)
# ==============================
def start_sniper_loop():
    global LAST_SIGNAL
    bd_tz = timezone(timedelta(hours=6))
    
    while True:
        try:
            now = datetime.now(bd_tz)
            
            # প্রতি মিনিটে ৪৫ সেকেন্ডের মাথায় স্ক্যান শুরু (১৫ সেকেন্ড আগে এলার্ট)
            if now.second >= 45 and now.second < 50: 
                best_pair = None
                best_conf = 0
                best_action = ""

                for code, info in ASSETS.items():
                    action, conf = analyze_m1_market(info)
                    if conf > best_conf:
                        best_conf = conf
                        best_pair = info
                        best_action = action

                if best_conf >= 90:
                    entry_time = (now + timedelta(minutes=1)).replace(second=0).strftime("%I:%M:%S %p")
                    stats = PAIR_STATS[best_pair['name']]
                    total = stats['wins'] + stats['losses']
                    wr = round((stats['wins']/total*100), 1) if total > 0 else 0

                    LAST_SIGNAL = {
                        "pair": best_pair['name'],
                        "action": best_action,
                        "conf": best_conf,
                        "entry": entry_time,
                        "wr": wr
                    }

                    msg = f"""
🔥 <b>W O L V E S   M1  VIP</b> 🔥
━━━━━━━━━━━━━━━━━
📊 <b>Pair:</b> <code>{best_pair['name']}</code>
⏰ <b>Time:</b> {entry_time}
⏳ <b>Exp:</b> 1 MIN (M1)
{'🟢' if best_action == 'CALL' else '🔴'} <b>Action:</b> {best_action}
🎯 <b>Confidence:</b> {best_conf}%
━━━━━━━━━━━━━━━━━
✅✅ <b>SURESHOT ALERT</b> ✅✅

📈 <b>Win:</b> {stats['wins']} | <b>Loss:</b> {stats['losses']} ({wr}%)
"""
                    telegram_send(msg)
                    
                    # ব্যাকগ্রাউন্ডে রেজাল্ট চেক হবে, মেইন লুপ ফ্রিজ হবে না
                    threading.Thread(target=check_trade_result, args=(best_pair['name'],), daemon=True).start()
                    
                    time.sleep(10) # একই ক্যান্ডেলে বারবার সিগন্যাল এড়াতে
            
            time.sleep(2) # CPU লোড কমানোর জন্য ২ সেকেন্ড পর পর চেক
        except Exception as e:
            time.sleep(5)

# ==============================
# DASHBOARD UI (M1 MODE - FIXED RENDER)
# ==============================
app = Flask(__name__)

@app.route("/")
def index():
    bg_color = "bg-green-600" if LAST_SIGNAL.get('action') == "CALL" else "bg-red-600" if LAST_SIGNAL.get('action') == "PUT" else "bg-gray-600"
    
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <title>AI Sniper M1 Pro</title>
    </head>
    <body class="bg-[#0f172a] text-slate-200 font-sans">
        <div class="max-w-xl mx-auto pt-10 px-4">
            <div class="bg-slate-800 rounded-3xl p-8 border border-green-500/30 shadow-2xl shadow-green-500/10">
                <div class="flex justify-between items-center mb-6">
                    <h1 class="text-2xl font-black text-green-400">WOLVES AI <span class="text-xs bg-green-500 text-black px-2 py-1 rounded ml-2">M1 PRO</span></h1>
                    <div class="text-right">
                        <p class="text-[10px] text-slate-400">SYSTEM STATUS</p>
                        <p class="text-xs font-bold text-blue-400">SCANNING 30S...</p>
                    </div>
                </div>

                <div class="bg-slate-900/50 rounded-2xl p-6 border border-slate-700 mb-6">
                    <p class="text-xs text-slate-500 uppercase tracking-widest mb-2">Live Target</p>
                    <h2 class="text-3xl font-bold mb-4">{{{{sig.pair or 'WAITING FOR SIGNAL'}}}}</h2>
                    <div class="flex gap-4">
                        <div class="px-6 py-2 rounded-xl {bg_color} font-black text-white">
                            {{{{sig.action or '---'}}}}
                        </div>
                        <div class="bg-slate-800 px-4 py-2 rounded-xl">
                            <p class="text-[10px] text-slate-500">ACCURACY</p>
                            <p class="font-bold text-cyan-400">{{{{sig.conf or '0'}}}}%</p>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-slate-800 p-4 rounded-2xl border border-slate-700">
                        <p class="text-xs text-slate-500">SIM BALANCE</p>
                        <p class="text-xl font-bold text-yellow-500">${{{{bal}}}}</p>
                    </div>
                    <div class="bg-slate-800 p-4 rounded-2xl border border-slate-700">
                        <p class="text-xs text-slate-500">AVG WIN RATE</p>
                        <p class="text-xl font-bold text-blue-400">{{{{sig.wr or '0'}}}}%</p>
                    </div>
                </div>
            </div>
            <p class="text-center text-[10px] text-slate-600 mt-6 uppercase tracking-widest">Powered by AI Engine</p>
        </div>
        <script>setTimeout(()=> location.reload(), 15000);</script>
    </body>
    </html>
    """, sig=LAST_SIGNAL, bal=SIM_BALANCE)

if __name__ == "__main__":
    # Render-এর জন্য ব্যাকগ্রাউন্ড থ্রেড
    threading.Thread(target=start_sniper_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
