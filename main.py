import os
import time
from collections import deque
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

symbol = "WIFUSDT"
client = HTTP(api_key=api_key, api_secret=api_secret)

price_window = deque(maxlen=720)

def get_price():
    data = client.get_tickers(category="spot", symbol=symbol)
    return float(data["result"]["list"][0]["lastPrice"])

def get_balance():
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    coins = wallet["result"]["list"][0]["coin"]
    for coin in coins:
        if coin["coin"] == "USDT":
            return float(coin.get("walletBalance", 0))
    return 0

def buy_all():
    usdt = get_balance()
    print(f"[БАЛАНС] Доступно USDT: {usdt}")
    if usdt <= 0:
        print("[ОШИБКА] Баланс USDT не найден или недоступен.")
        return 0
    price = get_price()
    qty = (usdt * 0.90) / price
    qty = float(f"{qty:.3f}")
    print(f"[РАСЧЁТ] Покупаем {qty} {symbol} по цене {price}")
    if qty <= 0:
        print("[ОШИБКА] Рассчитано 0 монет для покупки — пропуск.")
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

def sell_all(qty):
    if qty <= 0:
        print("[ОШИБКА] Нулевая продажа — ничего не делаем.")
        return
    client.place_order(
        category="spot",
        symbol=symbol,
        side="Sell",
        orderType="Market",
        qty=qty
    )
    print(f"[ПРОДАЖА] Продано {qty} {symbol}")

def preload_prices():
    print("[ЗАГРУЗКА] Получаем исторические цены с Bybit...")
    candles = client.get_kline(category="spot", symbol=symbol, interval="1", limit=720)
    closes = [float(c[4]) for c in candles["result"]["list"]]
    price_window.extend(closes)
    print(f"[ЗАГРУЗКА] Загружено {len(closes)} цен за последние 12 часов.")
    print(f"[СТАТИСТИКА] Минимум: {min(closes)}, максимум: {max(closes)}")

# Ожидаем рост +0.25% от локального минимума
def wait_for_signal():
    print("[ОЖИДАНИЕ СИГНАЛА] Ждём +0.25% роста от локального минимума...")
    while True:
        current = get_price()
        price_window.append(current)
        local_min = min(price_window)
        print(f"[МИНИМУМ] Текущее: {current}, Локальный минимум: {local_min}")
        if current >= local_min * 1.0025:
            print(f"[ВХОД] Цена выросла на +0.25%: {local_min} → {current}")
            return current
        time.sleep(60)

# Сопровождаем сделку, ждём -0.25% падения 3 раза подряд
def track_trade(entry_price, qty):
    peak = entry_price
    below_threshold_counter = 0
    print(f"[ТРЕКИНГ] Начинаем сопровождение сделки. Вход по: {entry_price}")
    while True:
        price = get_price()
        if price > peak:
            peak = price
            below_threshold_counter = 0
        elif price <= peak * 0.9975:
            below_threshold_counter += 1
            print(f"[НИЖЕ -0.25%] {below_threshold_counter}/3 → Цена: {price}, Пик: {peak}")
            if below_threshold_counter >= 3:
                print(f"[ВЫХОД] Подтверждено падение на -0.25%: {peak} → {price}")
                sell_all(qty)
                price_window.clear()
                return
        else:
            print(f"[ТРЕКИНГ] Цена: {price}, Пик: {peak} — всё в норме.")
            below_threshold_counter = 0
        time.sleep(60)

def run_bot():
    preload_prices()
    while True:
        print("[ПОИСК] Режим +0.25% от минимума активен...")
        entry_price = wait_for_signal()
        qty = buy_all()
        track_trade(entry_price, qty)
        print("[ОЖИДАНИЕ] Пауза 10 минут перед следующим циклом...")
        time.sleep(600)

if __name__ == "__main__":
    run_bot()
