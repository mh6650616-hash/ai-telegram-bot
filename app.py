# =========================================================
# AI BINARY SIGNAL PLATFORM PRO (RENDER STABLE VERSION)
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
VIP_MODE = False

SIGNAL_DELAY = 180

WINS = 0
LOSSES = 0

LAST_SIGNAL = {}

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

    url = f"https://api.telegram.org/bot{8732000370:AAHjp7EDsN6RRwKVDRe3uYAq9YYpBT9OaTk}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
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
        
        # FIX: yfinance multi-index column fix
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
# SNIPER ENGINE
# ==============================

def sniper_score(df):

    score = 0

    if df["ema9"].iloc[-1] > df["ema21"].iloc[-1]:
        score += 40

    if df["rsi"].iloc[-1] > 55:
        score += 30

    if df["rsi"].iloc[-1] < 45:
        score += 30

    return score

# ==============================
# PAIR SCANNER
# ==============================

def scan_pairs():

    best_pair = None
    best_score = 0
    best_signal = None

    for pair in PAIRS:

        df = download_dataset(pair)

        if df is None:
            continue

        signal,conf = predict_signal(df)

        score = sniper_score(df)

        total = conf + score

        if total > best_score:

            best_score = total
            best_pair = pair
            best_signal = signal

    return best_pair,best_signal,best_score

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
# SIGNAL LOOP
# ==============================

def signal_loop():

    global LAST_SIGNAL,WINS,LOSSES
    
    # Bangladesh Time Zone setup (UTC +6)
    bd_tz = timezone(timedelta(hours=6))

    while True:

        try:

            if not BOT_RUNNING:
                time.sleep(5)
                continue

            pair,signal,conf = scan_pairs()

            if pair is None:
                time.sleep(20)
                continue

            # Fetching current time with BD Timezone
            now = datetime.now(bd_tz)

            expiry = now + timedelta(minutes=1)

            LAST_SIGNAL = {
                "pair":pair,
                "signal":signal,
                "confidence":round(conf,2),
                "entry":now.strftime("%H:%M"),
                "expiry":expiry.strftime("%H:%M")
            }

            msg = f"""
AI SIGNAL

PAIR: {pair}
SIGNAL: {signal}
CONFIDENCE: {round(conf,2)}%
ENTRY: {now.strftime("%H:%M")}
"""

            telegram_send(msg)

            time.sleep(60)

            result = simulate_trade(signal)

            if result=="WIN":
                WINS+=1
            else:
                LOSSES+=1

            telegram_send(f"RESULT: {result}")

            time.sleep(SIGNAL_DELAY)

        except:
            time.sleep(10)

# ==============================
# DASHBOARD
# ==============================

app = Flask(__name__)

HTML = """
<html>
<head>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
body{background:#0f172a;color:white;font-family:Arial;text-align:center}
.card{background:#1e293b;padding:20px;margin:20px;border-radius:10px}
button{padding:10px;margin:5px;background:#22c55e;border:none;border-radius:5px}
</style>
</head>

<body>

<h1>AI Binary Trading Dashboard</h1>

<button onclick="load()">Refresh</button>

<div class="card" id="signal"></div>

<div class="card" id="stats"></div>

<div class="card"><div id="chart"></div></div>

<script>

function load(){

fetch("/status")
.then(r=>r.json())
.then(d=>{

document.getElementById("signal").innerHTML =
"PAIR: "+(d.signal.pair || "-")+"<br>"+
"SIGNAL: "+(d.signal.signal || "-")+"<br>"+
"CONFIDENCE: "+(d.signal.confidence || "-")

document.getElementById("stats").innerHTML =
"WINS: "+d.wins+"<br>"+
"LOSSES: "+d.losses+"<br>"+
"BALANCE: "+d.balance

})

fetch("/chart")
.then(r=>r.json())
.then(c=>{

var data=[{

x:c.time,
open:c.open,
high:c.high,
low:c.low,
close:c.close,
type:'candlestick'

}]

Plotly.newPlot('chart',data)

})

}

load()

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

    # FIX: yfinance multi-index column fix
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
    
