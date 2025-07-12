import os
import time
import json
from collections import deque
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

symbol = "WIFUSDT"
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
client = HTTP(api_key=api_key, api_secret=api_secret)

STATE_FILE = "state.json"
price_window = deque(maxlen=720)
last_peak = 0
last_exit_time = 0

def load_state():
    global last_peak, last_exit_time, price_window
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            last_peak = state.get("last_peak", 0)
            last_exit_time = state.get("last_exit_time", 0)
            price_window_data = state.get("price_window", [])
            price_window = deque(price_window_data[-720:], maxlen=720)
            print("[STATE] Состояние загружено.")

def save_state():
    state = {
        "last_peak": last_peak,
        "last_exit_time": last_exit_time,
        "price_window": list(price_window)
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    print("[STATE] Состояние сохранено.")

def get_price():
    try:
        data = client.get_tickers(category="spot", symbol=symbol)
        return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print(f"[ОШИБКА] Не удалось получить цену: {e}")
        return 0

def get_balance():
    try:
        wallet = client.get_wallet_balance(accountType="UNIFIED")
        coins = wallet["result"]["list"][0]["coin"]
        for coin in coins:
            if coin["coin"] == "USDT":
                return float(coin["availableToTrade"])
        return 0
    except Exception as e:
        print(f"[ОШИБКА] Не удалось получить баланс: {e}")
        return 0

def buy_all():
    try:
        usdt = get_balance()
        price = get_price()

        if usdt < 5:
            print(f"[ОШИБКА] Недостаточно средств: {usdt} USDT")
            return 0

        if price <= 0:
            print(f"[ОШИБКА] Неверная цена: {price}")
            return 0

        qty = round((usdt * 0.99) / price, 6)

        if qty <= 0:
            print(f"[ОШИБКА] Неверное количество для покупки: qty = {qty}")
            return 0

        client.place_order(
            category="spot",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=qty
        )
        print(f"[ПОКУПКА] Куплено {qty} {symbol}")
        return qty
    except Exception as e:
        print(f"[ОШИБКА] Ошибка при покупке: {e}")
        return 0

def sell_all(qty):
    try:
        client.place_order(
            category="spot",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=qty
        )
        print(f"[ПРОДАЖА] Продано {qty} {symbol}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка при продаже: {e}")

def wait_for_5_percent_pump():
    print("[ПОИСК] Включен режим отслеживания +5% от локального минимума (12 часов)...")
    while True:
        current = get_price()
        if current <= 0:
            print("[ОШИБКА] Пропуск из-за некорректной цены")
            time.sleep(60)
            continue
        price_window.append(current)
        local_min = min(price_window)
        print(f"[МИНИМУМ] Текущее: {current}, Локальный минимум: {local_min}")
        if current >= local_min * 1.052:
            print(f"[ВХОД] Цена выросла на +5.2% от минимума: {local_min} → {current}")
            return current
        time.sleep(60)

def track_trade(entry_price, qty):
    global last_peak, last_exit_time
    peak = entry_price
    below_threshold_counter = 0
    while True:
        price = get_price()
        if price > peak:
            peak = price
            below_threshold_counter = 0
        elif price <= peak * 0.972:
            below_threshold_counter += 1
            print(f"[НИЖЕ -2.8%] {below_threshold_counter} мин: {price} от пика {peak}")
            if below_threshold_counter >= 3:
                print(f"[ВЫХОД] Удержание -2.8% от пика: {peak} → {price}")
                sell_all(qty)
                price_window.clear()
                last_peak = peak
                last_exit_time = time.time()
                save_state()
                return
        else:
            below_threshold_counter = 0
        time.sleep(60)

def run_bot():
    global last_peak, last_exit_time
    load_state()
    while True:
        now = time.time()
        price = get_price()
        if last_peak and now - last_exit_time >= 1800:
            if price >= last_peak * 1.01:
                print(f"[ПОВТОРНЫЙ ВХОД] Цена пробила пик +1%: {price} (пик был {last_peak})")
                qty = buy_all()
                if qty == 0:
                    print("[ПРОПУСК] Покупка не удалась. Ждём 10 минут...")
                    time.sleep(600)
                    continue
                track_trade(price, qty)
                print("[ОЖИДАНИЕ] Пауза 10 минут перед следующим циклом...")
                time.sleep(600)
                continue
        print("\n[ОЖИДАНИЕ СИГНАЛА] Ждём +5% роста от локального минимума...")
        entry_price = wait_for_5_percent_pump()
        qty = buy_all()
        if qty == 0:
            print("[ПРОПУСК] Покупка не удалась. Ждём 10 минут...")
            time.sleep(600)
            continue
        track_trade(entry_price, qty)
        print("[ОЖИДАНИЕ] Пауза 10 минут перед следующим циклом...")
        time.sleep(600)

if __name__ == "__main__":
    run_bot()
