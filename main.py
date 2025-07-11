import os
import time
from collections import deque
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

symbol = "WIFUSDT"
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
client = HTTP(api_key=api_key, api_secret=api_secret)

# 🔧 Быстрый режим: True — без паузы, False — с паузой 10 минут
FAST_MODE = False

def get_price():
    data = client.get_tickers(category="spot", symbol=symbol)
    return float(data["result"]["list"][0]["lastPrice"])

def get_balance():
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    coins = wallet["result"]["list"][0]["coin"]
    for coin in coins:
        if coin["coin"] == "USDT":
            return float(coin["availableToTrade"])
    return 0

def buy_all():
    usdt = get_balance()
    price = get_price()
    qty = round(usdt / price, 6)
    client.place_order(
        category="spot",
        symbol=symbol,
        side="Buy",
        orderType="Market",
        qty=qty
    )
    print(f"[ПОКУПКА] Куплено {qty} {symbol}")
    return qty

def sell_all(qty):
    client.place_order(
        category="spot",
        symbol=symbol,
        side="Sell",
        orderType="Market",
        qty=qty
    )
    print(f"[ПРОДАЖА] Продано {qty} {symbol}")

def wait_for_5_percent_from_local_min():
    price_window = deque(maxlen=60)  # 10 минут по 10 сек
    while True:
        price = get_price()
        price_window.append(price)

        local_min = min(price_window)
        if price >= local_min * 1.05:
            print(f"[ВХОД] Цена выросла на +5% от минимума: {local_min} → {price}")
            return price

        print(f"[ОЖИДАНИЕ] Текущая цена: {price}, минимум за 10 мин: {local_min}")
        time.sleep(10)

def track_trade(entry_price, qty):
    peak = entry_price
    while True:
        price = get_price()
        if price > peak:
            peak = price
        elif price <= peak * 0.97:
            print(f"[ВЫХОД] Цена упала на -3% от пика: {peak} → {price}")
            sell_all(qty)
            break
        time.sleep(10)

def run_bot():
    while True:
        print("\n[ОЖИДАНИЕ СИГНАЛА] Следим за локальным минимумом...")
        entry_price = wait_for_5_percent_from_local_min()
        qty = buy_all()
        track_trade(entry_price, qty)

        if not FAST_MODE:
            print("[ОЖИДАНИЕ] Пауза 10 минут перед новой сделкой...")
            time.sleep(600)

if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        print("⚠️ Ошибка в работе бота:", e)
        time.sleep(30)
