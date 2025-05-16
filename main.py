
import requests
import pandas as pd
from datetime import datetime
from telegram import Bot
import time

# === 設定參數 ===
TELEGRAM_TOKEN = "YOUR_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "15m"
API_URL = "https://api.bybit.com/v5/market/kline"
VOLUME_LOOKBACK = 20

bot = Bot(token=TELEGRAM_TOKEN)

def fetch_kline(symbol, interval="15m", limit=200):
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    r = requests.get(API_URL, params=params)
    data = r.json()["result"]["list"]
    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume", "turnover", "confirm", "cross_seq", "timestamp_end", "interval"
    ])
    df = df.astype({"timestamp": "int64", "open": "float", "high": "float", "low": "float", "close": "float", "volume": "float"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df[["timestamp", "open", "high", "low", "close", "volume"]]

def analyze_volume(df):
    recent_vol = df.iloc[-1]["volume"]
    avg_vol = df.iloc[-VOLUME_LOOKBACK-1:-1]["volume"].mean()
    return recent_vol > avg_vol

def calculate_obv(df):
    direction = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (df["volume"] * direction).cumsum()
    df["obv"] = obv
    return obv

def analyze_obv_trend(obv_series):
    return obv_series.diff().iloc[-5:].mean() > 0  # 最後5根平均斜率是否為正

def estimate_cvd(df):
    delta = df["close"].diff()
    direction = delta.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    cvd = (df["volume"] * direction).cumsum()
    df["cvd"] = cvd
    return cvd

def analyze_cvd_direction(cvd_series):
    return cvd_series.diff().iloc[-5:].mean() > 0  # 最後5根平均變化是否上升

def simulate_exit_advice(symbol, direction):
    if symbol == "BTCUSDT":
        return "1️⃣ +100點保本停損 ➜ 2️⃣ +300點啟動追蹤 ➜ 3️⃣ 回撤150點平倉 ➜ 4️⃣ 若虧損超過$30即止損"
    else:
        return "1️⃣ +20點保本停損 ➜ 2️⃣ +40點啟動追蹤 ➜ 3️⃣ 回撤20點平倉 ➜ 4️⃣ 若虧損超過$30即止損"

def check_breakout(df):
    recent = df.iloc[:-1]
    last_red = recent[recent["close"] < recent["open"]].iloc[-1:] if not recent[recent["close"] < recent["open"]].empty else None
    last_green = recent[recent["close"] > recent["open"]].iloc[-1:] if not recent[recent["close"] > recent["open"]].empty else None
    close_5m = df.iloc[-1]["close"]
    signal = None
    ref_price = None
    if last_red is not None and close_5m > last_red["open"].values[0]:
        signal = "long"
        ref_price = last_red["open"].values[0]
    elif last_green is not None and close_5m < last_green["close"].values[0]:
        signal = "short"
        ref_price = last_green["close"].values[0]
    return signal, ref_price

def send_notification(symbol, signal_type, price, vol_ok, obv_up, cvd_up):
    volume_tag = "✅" if vol_ok else "❌"
    obv_tag = "✅" if obv_up else "❌"
    cvd_tag = "✅" if cvd_up else "❌"
    strategy = simulate_exit_advice(symbol, signal_type)
    direction = "多單" if signal_type == "long" else "空單"
    message = f"""🔔 [{symbol}] {direction}訊號觸發
• 價格突破關鍵位置：{price}

📊 市場分析：
• Volume：{"高於均量" if vol_ok else "低於均量"} {volume_tag}
• CVD：{"多方優勢" if cvd_up else "空方優勢"} {cvd_tag}
• OBV：{"上升趨勢" if obv_up else "下降趨勢"} {obv_tag}

🎯 建議出場策略（{direction}）：
{strategy}
"""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# === 主迴圈 ===
while True:
    for symbol in SYMBOLS:
        try:
            df = fetch_kline(symbol)
            calculate_obv(df)
            estimate_cvd(df)
            signal, ref = check_breakout(df)
            if signal:
                vol_signal = analyze_volume(df)
                obv_signal = analyze_obv_trend(df["obv"])
                cvd_signal = analyze_cvd_direction(df["cvd"])
                send_notification(symbol, signal, df.iloc[-1]["close"], vol_signal, obv_signal, cvd_signal)
        except Exception as e:
            print(f"Error on {symbol}: {e}")
    time.sleep(300)
