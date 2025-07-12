import time
import json
import requests
import os
from datetime import datetime
from pybit.unified_trading import HTTP

# Настройки
symbol = "WIFUSDT"
qty_percent = 0.99
timeframe = 60  # 1 минута в секундах
period_hours = 12
candles_limit = period_hours * 60  # 720 минут = 12 часов
price_history = []

# Пороговые значения
rise_threshold = 0.05
fall_threshold = 0.028
fall_time_minutes = 3

# Состояние
state_file = "bot_state.json"
bot_state = {
    "in_position": False,
    "entry_price": 0.0,
    "local_minimum": None,
    "local_maximum": None,
    "fall_start_time": None
}

# Инициализация клиента Bybit
session = HTTP(
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET"),
)

def save_state():
    with open(state_file, "w") as f:
        json.dump(bot_state, f)

def load_state():
    global bot_state
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            bot_state = json.load(f)

def get_current_price():
    resp = session.get_ticker(category="spot", symbol=symbol)
    return float(resp["result"]["list"][0]["lastPrice"])

def preload_prices():
    print("[ЗАГРУЗКА] Получаем исторические цены с Bybit...")
    resp = session.get_kline(category="spot", symbol=symbol, interval="1", limit=candles_limit)
    candles = resp["result"]["list"]
    closes = [float(c[4]) for c in candles]
    price_history.extend(closes)
    print(f"[ЗАГРУЗКА] Загружено {len(closes)} цен за последние 12 часов.")

def get_balance():
    wallet = session.get_wallet_balance(accountType="UNIFIED")
    usdt = float(wallet["result"]["list"][0]["totalEquity"])
    return usdt

def buy_asset():
    usdt = get_balance()
    price = get_current_price()
    quantity = round((usdt * qty_percent) / price, 5)
    print(f"[ПОКУПКА] Покупаем {quantity} {symbol.split('USDT')[0]} по цене {price}")
    # session.place_order(...)  # отключено для теста
    bot_state["in_position"] = True
    bot_state["entry_price"] = price
    save_state()

def sell_asset():
    print(f"[ПРОДАЖА] Продаём актив...")
    # session.place_order(...)  # отключено для теста
    bot_state["in_position"] = False
    bot_state["entry_price"] = 0.0
    bot_state["local_maximum"] = None
    bot_state["fall_start_time"] = None
    save_state()

def run_bot():
    load_state()
    preload_prices()

    print("[ПОИСК] Включён режим отслеживания +5% от локального минимума (12 часов)...")

    while True:
        price = get_current_price()
        price_history.append(price)
        if len(price_history) > candles_limit:
            price_history.pop(0)

        local_min = min(price_history)
        local_max = max(price_history)

        if not bot_state["in_position"]:
            print(f"[МИНИМУМ] Текущее: {price}, Локальный минимум: {local_min}")
            if price >= local_min * (1 + rise_threshold):
                print("[СИГНАЛ] Обнаружен рост +5% от минимума — ПОКУПКА")
                buy_asset()
        else:
            if bot_state["local_maximum"] is None or price > bot_state["local_maximum"]:
                bot_state["local_maximum"] = price
                bot_state["fall_start_time"] = None
                save_state()
                print(f"[МАКСИМУМ] Обновлён максимум: {price}")

            fall_level = bot_state["local_maximum"] * (1 - fall_threshold)
            if price <= fall_level:
                if bot_state["fall_start_time"] is None:
                    bot_state["fall_start_time"] = time.time()
                    print("[ПАДЕНИЕ] Засечено падение от пика, начинаем отсчёт...")
                elif time.time() - bot_state["fall_start_time"] >= fall_time_minutes * 60:
                    print("[ВЫХОД] Падение подтвердилось — ПРОДАЖА")
                    sell_asset()
            else:
                bot_state["fall_start_time"] = None

        time.sleep(timeframe)

if __name__ == "__main__":
    run_bot()
