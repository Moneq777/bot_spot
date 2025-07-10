import os
import time
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

symbol = "WIFUSDT"
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
client = HTTP(api_key=api_key, api_secret=api_secret)

def get_price():
    data = client.get_tickers(category="spot", symbol=symbol)
    return float(data["result"]["list"][0]["lastPrice"])

def get_balance():
    wallet = client.get_wallet_balance(accountType="UNIFIED")
    coins = wallet["result"]["list"][0]["coin"]
    for coin in coins:
        if coin["coin"] == "USDT":
            return float(coin["availableToTrade"])
    return 0

def buy_all():
    usdt = get_balance()
    price = get_price()
    qty = round(usdt / price, 6)
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
    client.place_order(
        category="spot",
        symbol=symbol,
        side="Sell",
        orderType="Market",
        qty=qty
    )
    print(f"[ПРОДАЖА] Продано {qty} {symbol}")

def wait_for_5_percent_pump():
    start_price = get_price()
    while True:
        current = get_price()
        if current >= start_price * 1.05:
            print(f"[ВХОД] Цена выросла на +5%: {current}")
            return current
        time.sleep(10)

def track_trade(entry_price, qty):
    peak = entry_price
    while True:
        price = get_price()
        if price > peak:
            peak = price
        elif price <= peak * 0.97:
            print(f"[ВЫХОД] Цена упала на -3% от пика: {peak} → {price}")
            sell_all(qty)
            break
        time.sleep(10)

def run_bot():
    while True:
        print("\n[ОЖИДАНИЕ СИГНАЛА] Ждём +5% роста...")
        entry_price = wait_for_5_percent_pump()
        qty = buy_all()
        track_trade(entry_price, qty)
        print("[ОЖИДАНИЕ] Ждём следующей точки входа...")
        time.sleep(600)

if __name__ == "__main__":
    run_bot()
