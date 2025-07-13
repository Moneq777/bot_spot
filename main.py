import os
import time
from collections import deque
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Загрузка API ключей
load_dotenv()
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

symbol = "WIFUSDT"
client = HTTP(api_key=api_key, api_secret=api_secret)

price_window = deque(maxlen=720)  # последние 12 часов (по 1 цене в минуту)

def get_price():
    try:
        data = client.get_tickers(category="spot", symbol=symbol)
        return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print(f"[ОШИБКА] Получение цены: {e}")
        return 0

def get_balance():
    try:
        wallet = client.get_wallet_balance(accountType="UNIFIED")
        coins = wallet["result"]["list"][0]["coin"]
        for coin in coins:
            if coin["coin"] == "USDT":
                return float(coin.get("walletBalance", 0))
    except Exception as e:
        print(f"[ОШИБКА] Получение баланса: {e}")
    return 0

def buy_all():
    usdt = get_balance()
    print(f"[БАЛАНС] Доступно USDT: {usdt}")
    if usdt <= 0:
        return 0
    price = get_price()
    qty = (usdt * 0.90) / price
    qty = float(f"{qty:.3f}")
    if qty <= 0:
        return 0
    try:
        client.place_order(category="spot", symbol=symbol, side="Buy", orderType="Market", qty=qty)
        print(f"[ПОКУПКА] Куплено {qty} {symbol} по цене {price}")
        return qty
    except Exception as e:
        print(f"[ОШИБКА] Покупка: {e}")
        return 0

def sell_all(qty):
    if qty <= 0:
        return
    try:
        client.place_order(category="spot", symbol=symbol, side="Sell", orderType="Market", qty=qty)
        print(f"[ПРОДАЖА] Продано {qty} {symbol}")
    except Exception as e:
        print(f"[ОШИБКА] Продажа: {e}")

def preload_prices():
    print("[ЗАГРУЗКА] Исторические цены...")
    try:
        candles = client.get_kline(category="spot", symbol=symbol, interval="1", limit=720)
        closes = [float(c[4]) for c in candles["result"]["list"]]
        price_window.extend(closes)
        print(f"[СТАТИСТИКА] Минимум: {min(closes)}, максимум: {max(closes)}")
    except Exception as e:
        print(f"[ОШИБКА] История цен: {e}")

def wait_for_pump(threshold=1.0025):
    print(f"[ОЖИДАНИЕ] Ждём роста +0.25% от минимума...")
    while True:
        current = get_price()
        if current == 0:
            time.sleep(60)
            continue
        price_window.append(current)
        local_min = min(price_window)
        print(f"[МИНИМУМ] {local_min} → Текущая: {current}")
        if current >= local_min * threshold:
            print(f"[ВХОД] Цена выросла на +0.25%: {local_min} → {current}")
            return current
        time.sleep(60)

def track_trade(entry_price, qty, drop_threshold=0.9975):
    peak = entry_price
    below_counter = 0
    while True:
        price = get_price()
        if price == 0:
            time.sleep(60)
            continue

        if price > peak:
            peak = price
            below_counter = 0
            print(f"[НОВЫЙ ПИК] {peak}")

        elif price <= peak * drop_threshold:
            below_counter += 1
            print(f"[НИЖЕ -0.25%] {below_counter}/3 минут: {price} от пика {peak}")
            if below_counter >= 3:
                print(f"[ВЫХОД] Цена упала на -0.25% от пика: {peak} → {price}")
                sell_all(qty)
                price_window.clear()
                return
        else:
            below_counter = 0

        time.sleep(60)

def run_bot():
    preload_prices()
    while True:
        print("[ПОИСК] Новый цикл...")
        entry_price = wait_for_pump()
        qty = buy_all()
        if qty > 0:
            track_trade(entry_price, qty)
            print("[ОЖИДАНИЕ] Пауза 10 минут перед следующей покупкой...")
            time.sleep(600)
        else:
            print("[ПРОПУСК] Покупка не выполнена. Повтор через 1 минуту.")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
