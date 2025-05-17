
import requests
import pandas as pd
from datetime import datetime
from telegram import Bot
import time

TELEGRAM_TOKEN = "7832725484:AAFetGmUw2UWZmcgX46Im3llWuDHaARjPGA"
TELEGRAM_CHAT_ID = "7574994738"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "15m"
API_URL = "https://api.bybit.com/v5/market/kline"
VOLUME_LOOKBACK = 20

bot = Bot(token=TELEGRAM_TOKEN)
bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✅ Debug 模式啟動中，策略系統已開始執行。")

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
    return obv_series.diff().iloc[-5:].mean() > 0

def estimate_cvd(df):
    delta = df["close"].diff()
    direction = delta.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    cvd = (df["volume"] * direction).cumsum()
    df["cvd"] = cvd
    return cvd

def analyze_cvd_direction(cvd_series):
    return cvd_series.diff().iloc[-5:].mean() > 0

def simulate_exit_advice(symbol, direction):
    if symbol == "BTCUSDT":
        return "1️⃣ +100點保本停損 ➜ 2️⃣ +300點啟動追蹤 ➜ 3️⃣ 回撤150點平倉 ➜ 4️⃣ 若虧損超過$30即止損"
    else:
        return "1️⃣ +20點保本停損 ➜ 2️⃣ +40點啟動追蹤 ➜ 3️⃣ 回撤20點平倉 ➜ 4️⃣ 若虧損超過$30即止損"

def check_breakout(df):
    recent = df.iloc[:-1]
    last_red = recent[recent["close"] < recent["open"]]
    last_green = recent[recent["close"] > recent["open"]]

    if last_red.empty or last_green.empty:
        print("⚠️ 找不到紅K或綠K，跳過判斷")
        return None, None

    last_red = last_red.iloc[-1:]
    last_green = last_green.iloc[-1:]

    close_5m = df.iloc[-1]["close"]
    signal = None
    ref_price = None

    if close_5m > last_red["open"].values[0]:
        signal = "long"
        ref_price = last_red["open"].values[0]
    elif close_5m < last_green["close"].values[0]:
        signal = "short"
        ref_price = last_green["close"].values[0]

    return signal, ref_price

def send_notification(symbol, signal_type, price, vol_ok, obv_up, cvd_up):
    volume_tag = "✅" if vol_ok else "❌"
    obv_tag = "✅" if obv_up else "❌"
    cvd_tag = "✅" if cvd_up else "❌"
    strategy = simulate_exit_advice(symbol, signal_type)
    direction = "多單" if signal_type == "long" else "空單"
    message = (
        f"🔔 [{symbol}] {direction}訊號觸發\n"
        f"• 價格突破關鍵位置：{price}\n\n"
        f"📊 市場分析：\n"
        f"• Volume：{'高於均量' if vol_ok else '低於均量'} {volume_tag}\n"
        f"• CVD：{'多方優勢' if cvd_up else '空方優勢'} {cvd_tag}\n"
        f"• OBV：{'上升趨勢' if obv_up else '下降趨勢'} {obv_tag}\n\n"
        f"🎯 建議出場策略（{direction}）：\n"
        f"{strategy}"
    )
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"❌ 發送訊息失敗: {e}")

while True:
    for symbol in SYMBOLS:
        print(f"🔍 檢查幣種: {symbol}, 時間: {datetime.utcnow()}")
        try:
            df = fetch_kline(symbol)
            print(f"📈 {symbol} 資料筆數: {len(df)}")
            calculate_obv(df)
            estimate_cvd(df)
            signal, ref = check_breakout(df)
            print(f"📊 判斷結果 signal={signal}, ref={ref}")
            if signal:
                vol_signal = analyze_volume(df)
                obv_signal = analyze_obv_trend(df["obv"])
                cvd_signal = analyze_cvd_direction(df["cvd"])
                send_notification(symbol, signal, df.iloc[-1]["close"], vol_signal, obv_signal, cvd_signal)
        except Exception as e:
            print(f"❌ {symbol} 發生錯誤: {e}")
    time.sleep(300)
