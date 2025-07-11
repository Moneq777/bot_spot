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

# Настройки стратегии
MIN_TRACKING_MINUTES = 720     # минимум за 12 часов
SLEEP_SECONDS = 10             # пауза между проверками (в секундах)
ENTRY_TRIGGER = 1.05           # вход при +5% от дна
EXIT_TRIGGER = 0.97            # выход при -3% от пика
FAST_MODE = False              # True = без паузы между сделками

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
    price_window = deque(maxlen=MIN_TRACKING_MINUTES * (60 // SLEEP_SECONDS))
    while True:
        price = get_price()
        price_window.append(price)

        local_min = min(price_window)
        if price >= local_min * ENTRY_TRIGGER:
            print(f"[ВХОД] Цена выросла на +5% от минимума: {local_min} → {price}")
            return price

        print(f"[ОЖИДАНИЕ] Текущая цена: {price}, минимум за {MIN_TRACKING_MINUTES} мин: {local_min}")
        time.sleep(SLEEP_SECONDS)

def track_trade(entry_price, qty):
    peak = entry_price
    while True:
        price = get_price()
        if price > peak:
            peak = price
        elif price <= peak * EXIT_TRIGGER:
            print(f"[ВЫХОД] Цена упала на -3% от пика: {peak} → {price}")
            sell_all(qty)
            break
        time.sleep(SLEEP_SECONDS)

def run_bot():
    while True:
        print("\n[ОЖИДАНИЕ СИГНАЛА] Следим за локальным минимумом...")
        entry_price = wait_for_5_percent_from_local_min()
        qty = buy_all()
        track_trade(entry_price, qty)

        if not FAST_MODE:
            print("[ПАУЗА] Ждём 10 минут перед следующей сделкой...")
            time.sleep(600)

if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        print("⚠️ Ошибка в работе бота:", e)
        time.sleep(30)
