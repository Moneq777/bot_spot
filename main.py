import time
import datetime
from pybit.unified_trading import HTTP
import os

# === НАСТРОЙКИ ===
symbol = "WIFUSDT"
usdt_balance = 1000  # Эмуляция депозита, заменяется реальным в боевом режиме
entry_percent = 0.99
price_growth_threshold = 0.05  # +5% от минимума для входа
price_fall_threshold = 0.028  # -2.8% от максимума для выхода
reentry_trigger = 0.01         # Повторный вход при +1% от последнего хая

# === ИНИЦИАЛИЗАЦИЯ API ===
session = HTTP(
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
in_position = False
entry_price = 0
local_minimum = None
local_maximum = None
reentry_ready = False


# === ПОЛУЧЕНИЕ ТЕКУЩЕЙ ЦЕНЫ ===
def get_current_price():
    try:
        resp = session.latest_information_for_symbol(symbol=symbol)
        return float(resp["result"][0]["last_price"])
    except Exception as e:
        print(f"[ОШИБКА] Не удалось получить текущую цену: {e}")
        return None


# === ЗАГРУЗКА ИСТОРИЧЕСКИХ ЦЕН (12 ЧАСОВ) ===
def preload_prices():
    print("[ЗАГРУЗКА] Получаем исторические цены с Bybit...")
    try:
        response = session.get_kline(
            category="spot",
            symbol=symbol,
            interval="1",
            limit=720
        )
        candles = response["result"]["list"]
        closes = [float(c[4]) for c in candles]
        print(f"[ЗАГРУЗКА] Загружено {len(closes)} цен за последние 12 часов.")
        return closes
    except Exception as e:
        print(f"[ОШИБКА] Не удалось загрузить историю цен: {e}")
        return []


# === ГЛАВНАЯ ЛОГИКА ===
def run_bot():
    global in_position, entry_price, local_minimum, local_maximum, reentry_ready, usdt_balance

    historical_prices = preload_prices()
    if not historical_prices:
        print("[ОШИБКА] Нет исторических данных. Выход.")
        return

    local_minimum = min(historical_prices)
    local_maximum = max(historical_prices)

    print(f"[СТАТИСТИКА] Минимум за 12ч: {local_minimum:.4f}, максимум: {local_maximum:.4f}")
    print(f"[ПОИСК] Включен режим отслеживания +5% от локального минимума (12 часов)...")

    while True:
        price = get_current_price()
        if price is None:
            time.sleep(5)
            continue

        if not in_position:
            if price < local_minimum:
                local_minimum = price

            if price >= local_minimum * (1 + price_growth_threshold):
                entry_price = price
                amount = round((usdt_balance * entry_percent) / entry_price, 4)
                print(f"[ПОКУПКА] Цена: {entry_price:.4f}, Куплено: {amount} {symbol}")
                in_position = True
                reentry_ready = False
                local_maximum = entry_price  # сбрасываем максимум от точки входа
        else:
            if price > local_maximum:
                local_maximum = price

            if price <= local_maximum * (1 - price_fall_threshold):
                print(f"[ПРОДАЖА] Цена: {price:.4f}, Продано по стопу -2.8% от пика.")
                in_position = False
                reentry_ready = True
                local_minimum = price  # обновим минимум для следующего входа

        if reentry_ready and price >= local_maximum * (1 + reentry_trigger):
            entry_price = price
            amount = round((usdt_balance * entry_percent) / entry_price, 4)
            print(f"[ПОВТОРНЫЙ ВХОД] Цена: {entry_price:.4f}, Куплено: {amount} {symbol}")
            in_position = True
            reentry_ready = False
            local_maximum = entry_price

        print(f"[МИНИМУМ] Текущее: {price:.4f}, Локальный минимум: {local_minimum:.4f}")
        time.sleep(5)


if __name__ == "__main__":
    print("[СТАРТ] Запуск бота...")
    run_bot()
