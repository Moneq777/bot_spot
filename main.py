import os
import time
from collections import deque
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# === НАСТРОЙКИ ===
PERCENT_ENTRY = 2.5           # Вход при +2.5%
FIX_PROFIT = 3.0              # Выход при +3% от входа
TRAILING_STOP = 2.8           # Трейлинг-стоп -2.8%
PRICE_WINDOW_MINUTES = 360    # 6 часов цен
SYMBOL = "WIFUSDT"            # Торгуемая пара
TOKEN = "WIF"                 # Название токена

# === ЗАГРУЗКА API ===
load_dotenv()
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

client = HTTP(api_key=api_key, api_secret=api_secret)
price_window = deque(maxlen=PRICE_WINDOW_MINUTES)

# === ПОЛУЧЕНИЕ ТЕКУЩЕЙ ЦЕНЫ ===
def get_price():
    data = client.get_tickers(category="spot", symbol=SYMBOL)
    return float(data["result"]["list"][0]["lastPrice"])

# === ПОЛУЧЕНИЕ БАЛАНСА ===
def get_balance():
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    for coin in wallet["result"]["list"][0]["coin"]:
        if coin["coin"] == "USDT":
            return float(coin.get("availableBalance", coin.get("walletBalance", 0)))
    return 0

def get_token_balance(token=TOKEN):
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    for coin in wallet["result"]["list"][0]["coin"]:
        if coin["coin"] == token:
            return float(coin.get("walletBalance", 0))
    return 0

# === ПОКУПКА ЧЕРЕЗ КОНВЕРТАЦИЮ (используем 98% от баланса) ===
def buy_all():
    usdt = get_balance()
    # Используем 98% от баланса для конвертации
    usdt_to_spend = round(usdt * 0.98, 2)
    print(f"[БАЛАНС] Доступно: {usdt:.4f} USDT, Планируем потратить: {usdt_to_spend:.2f} USDT")
    
    if usdt_to_spend <= 0:
        print("[ОШИБКА] Недостаточно средств для покупки")
        return 0, 0

    try:
        # Используем метод convert_exchange для конвертации USDT в токены
        convert = client.convert_exchange(
            fromCoin="USDT",
            toCoin=TOKEN,
            fromAmount=str(usdt_to_spend)
        )
        qty = float(convert["result"]["toAmount"])
        price = usdt_to_spend / qty  # примерное значение
        print(f"[ВХОД] Конвертировано {usdt_to_spend:.2f} USDT → {qty:.3f} {TOKEN} по цене ~{price:.4f} USDT")
        return qty, price
    except Exception as e:
        print(f"[ОШИБКА КОНВЕРТАЦИИ] {e}")
        return 0, 0

# === ПРОДАЖА ===
def sell_all():
    actual_qty = get_token_balance()
    sell_qty = round(actual_qty * 0.99, 2)

    if sell_qty < 0.001:
        print("[СКИП] Слишком малая сумма для продажи")
        return 0

    try:
        price = get_price()
        client.place_order(
            category="spot",
            symbol=SYMBOL,
            side="Sell",
            orderType="Market",
            qty=sell_qty
        )
        print(f"[ВЫХОД] Цена: {price:.4f}, Продано: {sell_qty:.2f} {TOKEN}")
        return price
    except Exception as e:
        print(f"[ОШИБКА ПРОДАЖИ] {e}")
        return 0

# === ОЖИДАНИЕ СИГНАЛА НА ВХОД ===
def wait_for_pump():
    print("[ОЖИДАНИЕ] Ждём роста +2.5% от минимума...")
    while True:
        current = get_price()
        price_window.append(current)
        if len(price_window) < 10:
            print("[ОЖИДАНИЕ] Сбор данных...")
            time.sleep(60)
            continue

        local_min = min(price_window)
        threshold = local_min * (1 + PERCENT_ENTRY / 100)
        print(f"[ЦЕНА] Текущая: {current:.4f}, Минимум: {local_min:.4f}, Цель входа: {threshold:.4f}")

        if current >= threshold:
            return current

        time.sleep(60)

# === СОПРОВОЖДЕНИЕ ПОЗИЦИИ ===
def track_trade(entry_price, qty):
    peak = entry_price
    below_counter = 0
    print(f"[СОПРОВОЖДЕНИЕ] Вход по цене {entry_price:.4f}, ждём +{FIX_PROFIT}% или трейлинг-стоп...")
    while True:
        price = get_price()

        # Выход при +3%
        if price >= entry_price * (1 + FIX_PROFIT / 100):
            print(f"[ФИКСАЦИЯ] Цена достигла +{FIX_PROFIT}%: {price:.4f}")
            exit_price = sell_all()
            if exit_price:
                pnl = (exit_price - entry_price) / entry_price * 100
                print(f"[ПРИБЫЛЬ] Вход: {entry_price:.4f}, Выход: {exit_price:.4f}, Доход: {pnl:.2f}%")
            price_window.clear()
            print("[ПАУЗА] 3 минуты...")
            time.sleep(180)
            return

        # Трейлинг-стоп
        if price > peak:
            peak = price
            below_counter = 0
        elif price <= peak * (1 - TRAILING_STOP / 100):
            below_counter += 1
            print(f"[СТОП] Цена ниже пика -{TRAILING_STOP}% {below_counter}/3: {price:.4f}")
            if below_counter >= 3:
                exit_price = sell_all()
                if exit_price:
                    pnl = (exit_price - entry_price) / entry_price * 100
                    print(f"[ПРИБЫЛЬ] Вход: {entry_price:.4f}, Выход: {exit_price:.4f}, Доход: {pnl:.2f}%")
                price_window.clear()
                print("[ПАУЗА] 3 минуты...")
                time.sleep(180)
                return
        else:
            below_counter = 0

        time.sleep(60)

# === ОСНОВНОЙ ЦИКЛ ===
def run_bot():
    while True:
        print("[ПОИСК] Ожидание сигнала...")
        wait_for_pump()
        qty, entry_price = buy_all()
        if qty > 0:
            track_trade(entry_price, qty)

if __name__ == "__main__":
    run_bot()
