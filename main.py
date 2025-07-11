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

# Глобальные переменные
last_peak = 0
last_exit_time = 0
REENTRY_COOLDOWN = 1800        # 30 минут
REENTRY_THRESHOLD = 1.01       # +1% от пика
price_window = deque(maxlen=720)  # 720 минут (12 часов)

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

def wait_for_5_percent_pump():
    print("[ПОИСК] Ожидание +5% от локального минимума (12ч)...")
    while True:
        current = get_price()
        price_window.append(current)
        local_min = min(price_window)

        print(f"[МИНИМУМ] Текущая цена: {current}, Минимум за 12ч: {local_min}")

        if current >= local_min * 1.05:
            print(f"[ВХОД] Цена выросла на +5%: {local_min} → {current}")
            return current
        time.sleep(60)

def track_trade(entry_price, qty):
    global last_peak, last_exit_time
    peak = entry_price
    while True:
        price = get_price()
        if price > peak:
            peak = price
        elif price <= peak * 0.97:
            print(f"[ВЫХОД] -3% от пика: {peak} → {price}")
            sell_all(qty)
            price_window.clear()  # сбрасываем старые минимумы
            last_peak = peak
            last_exit_time = time.time()
            return
        time.sleep(60)

def run_bot():
    global last_peak, last_exit_time
    while True:
        now = time.time()
        price = get_price()

        # Повторный вход после выхода
        if last_peak and now - last_exit_time >= REENTRY_COOLDOWN:
            if price >= last_peak * REENTRY_THRESHOLD:
                print(f"[ПОВТОРНЫЙ ВХОД] Превышение пика +1%: {last_peak} → {price}")
                qty = buy_all()
                track_trade(price, qty)
                print("[ОЖИДАНИЕ] Пауза 10 минут...")
                time.sleep(600)
                continue

        # Стандартный вход по +5% от минимума
        print("\n[ОЖИДАНИЕ СИГНАЛА] Ждём +5% от минимума...")
        entry_price = wait_for_5_percent_pump()
        qty = buy_all()
        track_trade(entry_price, qty)
        print("[ОЖИДАНИЕ] Пауза 10 минут...")
        time.sleep(600)

if __name__ == "__main__":
    run_bot()
