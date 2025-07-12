import time
import math
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
import pytz

# Настройки
symbol = "WIFUSDT"
percent_growth = 0.05    # вход при +5% от локального минимума
percent_fall = 0.028     # выход при -2.8% от локального максимума
reentry_growth = 0.01    # повторный вход при +1% от предыдущего хая
usdt_to_spend_ratio = 0.99  # вход на 99% баланса
interval = 60  # интервал проверки (в секундах)

# Авторизация с новыми ключами
session = HTTP(
    api_key="c78mZcJDiDQNSOK9wt",
    api_secret="h323E9rjwbsSpDhtF4PSEpVbEoxPhGJ6rYAz"
)

# Получение текущей цены
def get_current_price():
    try:
        resp = session.get_ticker(category="spot", symbol=symbol)
        return float(resp["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print(f"[ОШИБКА] Не удалось получить текущую цену: {e}")
        return None

# Загрузка исторических цен за 12 часов (720 свечей по 1 минуте)
def preload_prices():
    print("[ЗАГРУЗКА] Получаем исторические цены с Bybit...")
    end_time = int(time.time() * 1000)
    start_time = end_time - 12 * 60 * 60 * 1000
    candles = session.get_kline(
        category="spot",
        symbol=symbol,
        interval="1",
        start=start_time,
        end=end_time,
        limit=720
    )
    closes = [float(c["close"]) for c in candles["result"]["list"]]
    print(f"[ЗАГРУЗКА] Загружено {len(closes)} цен за последние 12 часов.")
    return closes

# Получение баланса
def get_balance():
    try:
        balances = session.get_wallet_balance(accountType="UNIFIED")["result"]["list"]
        for acc in balances:
            for coin in acc["coin"]:
                if coin["coin"] == "USDT":
                    return float(coin["availableToTrade"])
        return 0
    except Exception as e:
        print(f"[ОШИБКА] Не удалось получить баланс: {e}")
        return 0

# Покупка
def buy(amount):
    try:
        resp = session.place_order(
            category="spot",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=amount
        )
        print(f"[ПОКУПКА] Куплено {amount} {symbol}")
        return True
    except Exception as e:
        print(f"[ОШИБКА] Не удалось купить: {e}")
        return False

# Продажа
def sell():
    try:
        balances = session.get_wallet_balance(accountType="UNIFIED")["result"]["list"]
        for acc in balances:
            for coin in acc["coin"]:
                if coin["coin"] == symbol.replace("USDT", ""):
                    qty = float(coin["availableToTrade"])
                    if qty > 0:
                        session.place_order(
                            category="spot",
                            symbol=symbol,
                            side="Sell",
                            orderType="Market",
                            qty=qty
                        )
                        print(f"[ПРОДАЖА] Продано {qty} {symbol}")
                        return True
        return False
    except Exception as e:
        print(f"[ОШИБКА] Не удалось продать: {e}")
        return False

# Основная логика
def run_bot():
    prices = preload_prices()
    if not prices:
        print("[ОШИБКА] Исторические цены не загружены.")
        return

    local_min = min(prices)
    local_max = max(prices)
    print(f"[СТАТИСТИКА] Минимум за 12ч: {local_min}, максимум: {local_max}")
    print(f"[ПОИСК] Включён режим отслеживания +{percent_growth*100:.0f}% от локального минимума (12 часов)...")

    in_position = False
    entry_price = 0
    exit_price = 0
    last_max_price = 0

    while True:
        price = get_current_price()
        if not price:
            time.sleep(interval)
            continue

        now = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%H:%M:%S")
        print(f"[{now}] Текущая: {price:.4f}, Локальный минимум: {local_min:.4f}")

        if not in_position:
            if price >= local_min * (1 + percent_growth):
                balance = get_balance()
                if balance > 5:
                    amount = (balance * usdt_to_spend_ratio) / price
                    amount = math.floor(amount * 1000) / 1000
                    if buy(amount):
                        in_position = True
                        entry_price = price
                        last_max_price = price
                        print(f"[ВХОД] Вход в рынок по цене: {price:.4f}")
        else:
            if price > last_max_price:
                last_max_price = price
            drawdown = (last_max_price - price) / last_max_price
            if drawdown >= percent_fall:
                if sell():
                    print(f"[ВЫХОД] Выход при падении -{percent_fall*100:.1f}% от хая: {price:.4f}")
                    in_position = False
                    local_min = price
                    print("[ОЖИДАНИЕ СИГНАЛА] Ждём +1% от предыдущего хая...")
                    while True:
                        price = get_current_price()
                        if not price:
                            time.sleep(interval)
                            continue
                        now = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%H:%M:%S")
                        print(f"[{now}] Повторный вход: текущая цена {price:.4f}, хай {last_max_price:.4f}")
                        if price >= last_max_price * (1 + reentry_growth):
                            balance = get_balance()
                            if balance > 5:
                                amount = (balance * usdt_to_spend_ratio) / price
                                amount = math.floor(amount * 1000) / 1000
                                if buy(amount):
                                    in_position = True
                                    entry_price = price
                                    last_max_price = price
                                    print(f"[ПОВТОРНЫЙ ВХОД] Вход по {price:.4f}")
                                    break
                        time.sleep(interval)
        time.sleep(interval)

# Запуск
if __name__ == "__main__":
    print("[СТАРТ] Запуск бота...")
    run_bot()
