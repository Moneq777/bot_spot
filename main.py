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

# Получаем баланс монеты
def get_token_balance(token="WIF"):
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    coins = wallet["result"]["list"][0]["coin"]
    for coin in coins:
        if coin["coin"] == token:
            return float(coin.get("walletBalance", 0))
    return 0

# Получаем последние N цен закрытия
def get_recent_closes(n=200):
    candles = client.get_kline(category="spot", symbol=symbol, interval="1", limit=n)
    closes = [float(c[4]) for c in candles["result"]["list"]]
    return closes

# Покупка на 95% баланса
def buy_all():
    usdt = get_balance()
    print(f"[БАЛАНС] Доступно USDT: {usdt}")
    if usdt <= 0:
        print("[ОШИБКА] Недостаточно средств.")
        return 0
    price = get_price()
    qty = (usdt * 0.95) / price
    qty = float(f"{qty:.3f}")
    print(f"[ПОКУПКА] Покупаем {qty} {symbol}")
    try:
        client.place_order(category="spot", symbol=symbol, side="Buy", orderType="Market", qty=qty)
        return qty
    except Exception as e:
        print(f"[ОШИБКА ПОКУПКИ] {e}")
        return 0

# Продажа всей позиции — на 1% меньше баланса
def sell_all(entry_qty):
    actual_qty = get_token_balance("WIF")
    sell_qty = min(actual_qty, entry_qty) * 0.99
    sell_qty = float(f"{sell_qty:.3f}")
    try:
        client.place_order(category="spot", symbol=symbol, side="Sell", orderType="Market", qty=sell_qty)
        print(f"[ПРОДАЖА] Продано {sell_qty} {symbol}")
    except Exception as e:
        print(f"[ОШИБКА ПРОДАЖИ] {e}")

# Проверка тренда: SMA50 > SMA200
def is_uptrend():
    closes = get_recent_closes(200)
    sma50 = sum(closes[-50:]) / 50
    sma200 = sum(closes) / 200
    print(f"[ТРЕНД] SMA50: {sma50:.4f}, SMA200: {sma200:.4f}")
    return sma50 > sma200

# Проверка волатильности через ATR
def is_volatility_sufficient():
    closes = get_recent_closes(15)
    atr = sum([abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]) / (len(closes) - 1)
    print(f"[ВОЛАТИЛЬНОСТЬ] ATR: {atr:.4f}")
    return atr >= 0.005

# Ожидание сигнала на вход
def wait_for_pump():
    print("[ОЖИДАНИЕ] Ждём +3.2% роста от минимума...")
    while True:
        current = get_price()
        price_window.append(current)
        if len(price_window) < 10:
            print("[ОЖИДАНИЕ] Недостаточно данных...")
            time.sleep(60)
            continue

        local_min = min(price_window)
        threshold = local_min * 1.032
        print(f"[ЦЕНА] Текущая: {current:.4f}, Минимум: {local_min:.4f}, Цель: {threshold:.4f}")

        if current >= threshold and is_uptrend() and is_volatility_sufficient():
            print("[СИГНАЛ] Условия выполнены — входим.")
            return current

        time.sleep(60)

# Сопровождение позиции
def track_trade(entry_price, qty):
    peak = entry_price
    below_counter = 0
    while True:
        price = get_price()
        if price > peak:
            peak = price
            below_counter = 0
        elif price <= peak * 0.972:
            below_counter += 1
            print(f"[СТОП] Цена ниже пика -2.8% {below_counter}/3: {price:.4f}")
            if below_counter >= 3:
                print(f"[ВЫХОД] Продажа при откате от {peak:.4f} до {price:.4f}")
                sell_all(qty)
                price_window.clear()
                print("[ПАУЗА] 3 минуты...")
                time.sleep(180)
                return
        else:
            below_counter = 0
        time.sleep(60)

# Основной цикл
def run_bot():
    while True:
        print("[ПОИСК] Активен режим поиска...")
        entry_price = wait_for_pump()
        qty = buy_all()
        track_trade(entry_price, qty)

# Запуск
if __name__ == "__main__":
    run_bot()
