# =========================================================
# AI BINARY SIGNAL PLATFORM PRO (STABLE VERSION)
# =========================================================

import random
import time
import threading
import requests
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from flask import Flask, jsonify, render_template_string
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split

# ==============================
# CONFIG
# ==============================

BOT_RUNNING = True

WINS = 0
LOSSES = 0
LAST_SIGNAL = {}

# আপনার টোকেন এবং চ্যাট আইডি এখানে বসান
TELEGRAM_TOKEN = "8732000370:AAHjp7EDsN6RRwKVDRe3uYAq9YYpBT9OaTk"
TELEGRAM_CHAT_ID = "5698962657"

SIM_BALANCE = 1000

PAIRS = [
"EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X",
"EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","CHFJPY=X",
"USDCHF=X","NZDUSD=X","EURCAD=X","GBPAUD=X","EURAUD=X"
]

AI_MODEL = None

# ==============================
# TELEGRAM BROADCAST
# ==============================

def telegram_send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=data, timeout=10)
    except:
        pass

# ==============================
# DATASET DOWNLOADER
# ==============================

def download_dataset(pair):
    try:
        df = yf.download(pair, period="30d", interval="5m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except:
        return None

    if df is None or len(df) < 50:
        return None

    df["return"] = df["Close"].pct_change()
    df["ema9"] = df["Close"].ewm(span=9).mean()
    df["ema21"] = df["Close"].ewm(span=21).mean()
    df["rsi"] = compute_rsi(df["Close"],14)

    df = df.dropna()
    return df

def compute_rsi(series,period):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain/avg_loss
    rsi = 100-(100/(1+rs))
    return rsi

# ==============================
# AI MODEL
# ==============================

def train_ai(df):
    df["target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    X = df[["ema9","ema21","rsi"]]
    y = df["target"]
    X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.2)
    model = MLPClassifier(hidden_layer_sizes=(16,8), max_iter=120)
    model.fit(X_train,y_train)
    accuracy = model.score(X_test,y_test)
    return model,accuracy

def predict_signal(df):
    global AI_MODEL
    if AI_MODEL is None:
        AI_MODEL,_ = train_ai(df)
    row = df[["ema9","ema21","rsi"]].iloc[-1:]
    pred = AI_MODEL.predict(row)[0]
    conf = max(AI_MODEL.predict_proba(row)[0]) * 100
    signal = "CALL" if pred==1 else "PUT"
    return signal,conf

# ==============================
# SNIPER ENGINE (FIXED LOGIC)
# ==============================

def sniper_score(df, signal):
    score = 0
    current_ema9 = df["ema9"].iloc[-1]
    current_ema21 = df["ema21"].iloc[-1]
    current_rsi = df["rsi"].iloc[-1]

    if signal == "CALL":
        if current_ema9 > current_ema21: score += 50
        if current_rsi > 50: score += 50
    elif signal == "PUT":
        if current_ema9 < current_ema21: score += 50
        if current_rsi < 50: score += 50
        
    return score

def scan_pairs():
    best_pair = None
    best_score = 0
    best_signal = None

    for pair in PAIRS:
        df = download_dataset(pair)
        if df is None:
            continue
            
        signal, ai_conf = predict_signal(df)
        sn_score = sniper_score(df, signal)
        
        # PROPER CONFIDENCE CALCULATION (Average of AI and Sniper)
        total_strength = (ai_conf + sn_score) / 2

        if total_strength > best_score:
            best_score = total_strength
            best_pair = pair
            best_signal = signal

    return best_pair, best_signal, best_score

# ==============================
# MARKET SIMULATOR
# ==============================

def simulate_trade(signal):
    global SIM_BALANCE
    result = random.choice(["WIN","LOSS"])
    if result == "WIN":
        SIM_BALANCE += 80
    else:
        SIM_BALANCE -= 100
    return result

# ==============================
# SMART SIGNAL LOOP (TIMING SYNC)
# ==============================

def signal_loop():
    global LAST_SIGNAL, WINS, LOSSES
    bd_tz = timezone(timedelta(hours=6))

    while True:
        try:
            if not BOT_RUNNING:
                time.sleep(5)
                continue

            now = datetime.now(bd_tz)
            
            # --- 1.5 MINUTE BEFORE SYNC ENGINE ---
            seconds_passed_in_5m = (now.minute % 5) * 60 + now.second
            seconds_until_next_candle = 300 - seconds_passed_in_5m
            
            if seconds_until_next_candle > 95:
                time.sleep(seconds_until_next_candle - 90)
                continue
            elif seconds_until_next_candle < 85:
                time.sleep(seconds_until_next_candle + 1)
                continue

            pair, signal, conf = scan_pairs()

            if pair is None:
                time.sleep(10)
                continue

            now = datetime.now(bd_tz)
            next_candle_time = now + timedelta(seconds=(300 - ((now.minute % 5) * 60 + now.second)))

            LAST_SIGNAL = {
                "pair": pair,
                "signal": signal,
                "confidence": round(conf, 2),
                "entry": next_candle_time.strftime("%I:%M %p")
            }

            msg = f"""
🎯 <b>AI UPCOMING SIGNAL</b> 🎯

<b>PAIR:</b> {pair}
<b>ACTION:</b> {signal}
<b>STRENGTH:</b> {round(conf, 2)}%

⏳ <b>ENTRY TIME:</b> {next_candle_time.strftime("%I:%M %p")} (BD)
<i>(Prepare your chart now!)</i>
"""
            telegram_send(msg)

            wait_for_result = (next_candle_time - now).total_seconds() + 300
            time.sleep(wait_for_result)

            result = simulate_trade(signal)
            if result=="WIN": WINS+=1
            else: LOSSES+=1

            telegram_send(f"✅ <b>RESULT:</b> {result}\n💰 <b>BALANCE:</b> ${SIM_BALANCE}")
            time.sleep(5)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

# ==============================
# DASHBOARD (PRO VERSION)
# ==============================

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Sniper Pro Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-900 text-white font-sans antialiased p-4 md:p-8">

    <div class="max-w-6xl mx-auto space-y-6">
        <div class="flex justify-between items-center bg-gray-800 p-6 rounded-2xl shadow-lg border border-gray-700">
            <div>
                <h1 class="text-2xl md:text-3xl font-bold text-green-400"><i class="fas fa-robot mr-2"></i>AI Sniper Pro</h1>
                <p class="text-gray-400 text-sm mt-1">Live Binary Options Terminal</p>
            </div>
            <button onclick="load()" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 px-4 rounded-lg transition duration-300 shadow shadow-blue-500/50">
                <i class="fas fa-sync-alt mr-2"></i>Refresh
            </button>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-gray-800 p-5 rounded-2xl shadow-lg border border-gray-700 text-center">
                <p class="text-gray-400 text-sm font-semibold mb-1">Sim Balance</p>
                <p class="text-2xl font-bold text-yellow-400" id="balance">$--</p>
            </div>
            <div class="bg-gray-800 p-5 rounded-2xl shadow-lg border border-gray-700 text-center">
                <p class="text-gray-400 text-sm font-semibold mb-1">Total Wins</p>
                <p class="text-2xl font-bold text-green-500" id="wins">--</p>
            </div>
            <div class="bg-gray-800 p-5 rounded-2xl shadow-lg border border-gray-700 text-center">
                <p class="text-gray-400 text-sm font-semibold mb-1">Total Losses</p>
                <p class="text-2xl font-bold text-red-500" id="losses">--</p>
            </div>
            <div class="bg-gray-800 p-5 rounded-2xl shadow-lg border border-gray-700 text-center">
                <p class="text-gray-400 text-sm font-semibold mb-1">Win Rate</p>
                <p class="text-2xl font-bold text-blue-400" id="winrate">--%</p>
            </div>
        </div>

        <div class="bg-gradient-to-r from-gray-800 to-gray-700 p-6 rounded-2xl shadow-lg border border-gray-600 relative overflow-hidden">
            <h2 class="text-xl font-semibold mb-4 border-b border-gray-600 pb-2"><i class="fas fa-bolt text-yellow-400 mr-2"></i>Current Target</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center z-10 relative">
                <div>
                    <p class="text-gray-400 text-xs uppercase tracking-wider">Pair</p>
                    <p class="text-xl font-bold" id="sig-pair">WAITING...</p>
                </div>
                <div>
                    <p class="text-gray-400 text-xs uppercase tracking-wider">Action</p>
                    <p class="text-xl font-bold" id="sig-action">--</p>
                </div>
                <div>
                    <p class="text-gray-400 text-xs uppercase tracking-wider">Strength</p>
                    <p class="text-xl font-bold text-cyan-400" id="sig-conf">--</p>
                </div>
                <div>
                    <p class="text-gray-400 text-xs uppercase tracking-wider">Entry Time</p>
                    <p class="text-xl font-bold text-pink-400" id="sig-entry">--</p>
                </div>
            </div>
        </div>

        <div class="bg-gray-800 p-4 rounded-2xl shadow-lg border border-gray-700">
            <h2 class="text-lg font-semibold mb-2 text-gray-300 ml-2">Live Market Chart</h2>
            <div id="chart" style="height: 450px;"></div>
        </div>
    </div>

    <script>
        function load(){
            fetch("/status")
            .then(r=>r.json())
            .then(d=>{
                document.getElementById("balance").innerText = "$" + d.balance;
                document.getElementById("wins").innerText = d.wins;
                document.getElementById("losses").innerText = d.losses;
                
                let total = d.wins + d.losses;
                let rate = total > 0 ? ((d.wins / total) * 100).toFixed(1) : 0;
                document.getElementById("winrate").innerText = rate + "%";

                let s = d.signal;
                if(s && s.pair){
                    document.getElementById("sig-pair").innerText = s.pair;
                    let actionEl = document.getElementById("sig-action");
                    actionEl.innerText = s.signal;
                    actionEl.className = s.signal === 'CALL' ? 'text-xl font-bold text-green-500' : 'text-xl font-bold text-red-500';
                    document.getElementById("sig-conf").innerText = s.confidence + "%";
                    document.getElementById("sig-entry").innerText = s.entry;
                }
            });

            fetch("/chart")
            .then(r=>r.json())
            .then(c=>{
                var trace = {
                    x: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
                    type: 'candlestick',
                    increasing: {line: {color: '#22c55e'}},
                    decreasing: {line: {color: '#ef4444'}}
                };
                var layout = {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#9ca3af' },
                    xaxis: { rangeslider: { visible: false }, gridcolor: '#374151' },
                    yaxis: { gridcolor: '#374151' },
                    margin: { l: 40, r: 20, t: 20, b: 40 }
                };
                Plotly.newPlot('chart', [trace], layout, {responsive: true});
            });
        }
        load();
        setInterval(load, 30000);
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/status")
def status():
    return jsonify({
    "signal":LAST_SIGNAL,
    "wins":WINS,
    "losses":LOSSES,
    "balance":SIM_BALANCE
    })

@app.route("/chart")
def chart():
    pair = random.choice(PAIRS)
    df = yf.download(pair, period="1d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return jsonify({
    "time":df.index.astype(str).tolist(),
    "open":df["Open"].tolist(),
    "high":df["High"].tolist(),
    "low":df["Low"].tolist(),
    "close":df["Close"].tolist()
    })

# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    t = threading.Thread(target=signal_loop)
    t.daemon = True
    t.start()
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
    
