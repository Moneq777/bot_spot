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

def get_token_balance(token="WIF"):
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    coins = wallet["result"]["list"][0]["coin"]
    for coin in coins:
        if coin["coin"] == token:
            return float(coin.get("walletBalance", 0))
    return 0

def get_recent_volumes(limit=20):
    data = client.get_kline(category="spot", symbol=symbol, interval="1", limit=limit)
    candles = data["result"]["list"]
    volumes = [float(c[5]) for c in candles]
    opens = [float(c[1]) for c in candles]
    closes = [float(c[4]) for c in candles]
    return volumes, opens, closes

def is_volume_high():
    volumes, opens, closes = get_recent_volumes()
    avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
    last_volume = volumes[-1]
    green_candle = closes[-1] > opens[-1]
    print(f"[ОБЪЁМ] Последний: {last_volume}, Средний: {avg_volume}, Зелёная свеча: {green_candle}")
    return last_volume > avg_volume and green_candle

def buy_all():
    usdt = get_balance()
    print(f"[БАЛАНС] Доступно USDT: {usdt}")
    if usdt <= 0:
        print("[ОШИБКА] Баланс USDT не найден или недоступен.")
        return 0
    price = get_price()
    qty = (usdt * 0.95) / price
    qty = float(f"{qty:.3f}")
    print(f"[РАСЧЁТ] Покупаем {qty} {symbol} по цене {price}")
    try:
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
        print(f"[ОШИБКА] Не удалось купить: {e}")
        return 0

def sell_all(qty):
    if qty <= 0:
        print("[ОШИБКА] Нулевая продажа — ничего не делаем.")
        return
    actual_qty = get_token_balance("WIF")
    sell_qty = min(actual_qty, qty * 0.99)  # на 1% меньше
    sell_qty = float(f"{sell_qty:.2f}")
    try:
        client.place_order(
            category="spot",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=sell_qty
        )
        print(f"[ПРОДАЖА] Продано {sell_qty} {symbol}")
    except Exception as e:
        print(f"[ОШИБКА] Не удалось продать: {e}")

def wait_for_pump():
    print("[ОЖИДАНИЕ СИГНАЛА] Ждём +3.2% роста от локального минимума и фильтр по объёму...")
    while True:
        current = get_price()
        price_window.append(current)
        if len(price_window) < 10:
            print("[ОЖИДАНИЕ] Недостаточно данных для анализа — ждём...")
            time.sleep(60)
            continue
        local_min = min(price_window)
        if current >= local_min * 1.032:
            if is_volume_high():
                print(f"[ВХОД] Цена выросла на +3.2% от минимума: {local_min} → {current}")
                return current
            else:
                print("[ФИЛЬТР] Объём не прошёл проверку.")
        time.sleep(60)

def track_trade(entry_price, qty):
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
                print(f"[ВЫХОД] Падение на -2.8% от пика: {peak} → {price}")
                sell_all(qty)
                price_window.clear()
                print("[ОЖИДАНИЕ] Пауза 3 минуты после продажи...")
                time.sleep(180)
                return
        else:
            below_threshold_counter = 0
        time.sleep(60)

def run_bot():
    print("[СТАРТ] Бот запущен без предзагрузки истории.")
    while True:
        print("[ПОИСК] Включен режим отслеживания +3.2% от локального минимума...")
        entry_price = wait_for_pump()
        qty = buy_all()
        track_trade(entry_price, qty)

if __name__ == "__main__":
    run_bot()
