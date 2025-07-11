import os
import time
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
REENTRY_COOLDOWN = 10800  # 3 часа
REENTRY_THRESHOLD = 1.02  # +2% от последнего пика

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
    start_price = get_price()
    while True:
        current = get_price()
        if current >= start_price * 1.05:
            print(f"[ВХОД] Цена выросла на +5%: {current}")
            return current
        print(f"[МИНИМУМ] Ожидание роста: текущая цена = {current}, стартовая = {start_price}")
        time.sleep(10)

def track_trade(entry_price, qty):
    global last_peak, last_exit_time
    peak = entry_price
    while True:
        price = get_price()
        if price > peak:
            peak = price
        elif price <= peak * 0.97:
            print(f"[ВЫХОД] Цена упала на -3% от пика: {peak} → {price}")
            sell_all(qty)
            last_peak = peak
            last_exit_time = time.time()
            return
        time.sleep(10)

def run_bot():
    global last_peak, last_exit_time
    while True:
        now = time.time()
        price = get_price()

        # Повторный вход при пробое предыдущего пика +2%
        if last_peak and now - last_exit_time >= REENTRY_COOLDOWN:
            if price >= last_peak * REENTRY_THRESHOLD:
                print(f"[ПОВТОРНЫЙ ВХОД] Цена пробила пик +2%: {price} (пик был {last_peak})")
                qty = buy_all()
                track_trade(price, qty)
                print("[ОЖИДАНИЕ] Пауза 10 минут перед следующим циклом...")
                time.sleep(600)
                continue

        # Основной вход по +5% от локального минимума
        print("\n[ОЖИДАНИЕ СИГНАЛА] Ждём +5% роста от локального минимума...")
        entry_price = wait_for_5_percent_pump()
        qty = buy_all()
        track_trade(entry_price, qty)
        print("[ОЖИДАНИЕ] Пауза 10 минут перед следующим циклом...")
        time.sleep(600)

if __name__ == "__main__":
    run_bot()
