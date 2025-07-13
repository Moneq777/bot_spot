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

# Храним последние 720 цен (12 часов, если 1 цена в минуту)
price_window = deque(maxlen=720)

# Получаем текущую цену
def get_price():
    data = client.get_tickers(category="spot", symbol=symbol)
    return float(data["result"]["list"][0]["lastPrice"])

# Получаем доступный баланс USDT
def get_balance():
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    coins = wallet["result"]["list"][0]["coin"]
    for coin in coins:
        if coin["coin"] == "USDT":
            return float(coin.get("walletBalance", 0))
    return 0

# Покупка на 90% баланса
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

# Продажа всей позиции
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

# Подгружаем цены за последние 12 часов
def preload_prices():
    print("[ЗАГРУЗКА] Получаем исторические цены с Bybit...")
    candles = client.get_kline(category="spot", symbol=symbol, interval="1", limit=720)
    closes = [float(c[4]) for c in candles["result"]["list"]]
    price_window.extend(closes)
    print(f"[ЗАГРУЗКА] Загружено {len(closes)} цен за последние 12 часов.")
    print(f"[СТАТИСТИКА] Минимум: {min(closes)}, максимум: {max(closes)}")

# Ждём +0.25% роста от минимума
def wait_for_pump():
    print("[ОЖИДАНИЕ СИГНАЛА] Ждём +0.25% роста от локального минимума...")
    while True:
        current = get_price()
        price_window.append(current)
        if len(price_window) < 10:
            print("[ОЖИДАНИЕ] Недостаточно данных для анализа — ждём...")
            time.sleep(60)
            continue
        local_min = min(price_window)
        print(f"[МИНИМУМ] Текущее: {current}, Локальный минимум: {local_min}")
        if current >= local_min * 1.0025:
            print(f"[ВХОД] Цена выросла на +0.25% от минимума: {local_min} → {current}")
            return current
        time.sleep(60)

# Сопровождение позиции до -0.25% от пика (3 минуты подряд)
def track_trade(entry_price, qty):
    peak = entry_price
    below_threshold_counter = 0
    while True:
        price = get_price()
        if price > peak:
            peak = price
            below_threshold_counter = 0
        elif price <= peak * 0.9975:
            below_threshold_counter += 1
            print(f"[НИЖЕ -0.25%] {below_threshold_counter} мин: {price} от пика {peak}")
            if below_threshold_counter >= 3:
                print(f"[ВЫХОД] Падение на -0.25% от пика: {peak} → {price}")
                sell_all(qty)
                price_window.clear()  # Сбросить окно цен после выхода
                print("[ОЖИДАНИЕ] Пауза 10 минут после продажи...")
                time.sleep(600)
                return
        else:
            below_threshold_counter = 0
        time.sleep(60)

# Основной цикл
def run_bot():
    preload_prices()
    while True:
        print("[ПОИСК] Включен режим отслеживания +0.25% от локального минимума...")
        entry_price = wait_for_pump()
        qty = buy_all()
        track_trade(entry_price, qty)

# Старт
if __name__ == "__main__":
    run_bot()
