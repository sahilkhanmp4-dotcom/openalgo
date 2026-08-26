"""
===============================================================================
                     Nifty_AI_Algo - OpenAlgo Automated Bot
        Mode: ANALYZER (Forward-Testing Analyzer / Live Trading)
===============================================================================
"""

import os
import time
import threading
from datetime import datetime, timedelta
import pandas as pd
from openalgo import api

# --- CONFIGURATION ---
API_KEY = os.getenv("OPENALGO_API_KEY", "openalgo-apikey")
API_HOST = os.getenv("HOST_SERVER", "http://127.0.0.1:5000")
WS_URL = os.getenv("WEBSOCKET_URL", "ws://127.0.0.1:8765")

SYMBOL = "NIFTY"
EXCHANGE = "NSE_INDEX"
QUANTITY = 50
PRODUCT = "MIS"
TIMEFRAME = "5m"

FAST_EMA = 20
SLOW_EMA = 50
STOPLOSS_PCT = 0.8
TARGET_PCT = 2.0
TRADE_DIRECTION = "BOTH"
STRATEGY_NAME = "Nifty_AI_Algo"

class QuantBot:
    def __init__(self):
        self.client = api(api_key=API_KEY, host=API_HOST, ws_url=WS_URL)
        self.position = None
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tg_price = 0.0
        self.ltp = None
        self.exit_in_progress = False
        self.running = True
        self.stop_event = threading.Event()
        self.instrument = [{"exchange": EXCHANGE, "symbol": SYMBOL}]

    def on_ltp_update(self, data):
        if data.get("type") == "market_data" and data.get("symbol") == SYMBOL:
            self.ltp = float(data["data"]["ltp"])
            if self.position and not self.exit_in_progress:
                if self.position == "BUY":
                    if self.ltp <= self.sl_price:
                        self.place_exit("STOPLOSS HIT")
                    elif self.ltp >= self.tg_price:
                        self.place_exit("TARGET HIT")
                elif self.position == "SELL":
                    if self.ltp >= self.sl_price:
                        self.place_exit("STOPLOSS HIT")
                    elif self.ltp <= self.tg_price:
                        self.place_exit("TARGET HIT")

    def fetch_candles(self):
        end = datetime.now()
        start = end - timedelta(days=5)
        df = self.client.history(
            symbol=SYMBOL, exchange=EXCHANGE, interval=TIMEFRAME,
            start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d")
        )
        return df

    def check_signals(self, df):
        if df is None or len(df) < SLOW_EMA + 2:
            return None
        df["fast_ema"] = df["close"].ewm(span=FAST_EMA, adjust=False).mean()
        df["slow_ema"] = df["close"].ewm(span=SLOW_EMA, adjust=False).mean()
        
        prev = df.iloc[-3]
        last = df.iloc[-2]
        
        if prev["fast_ema"] <= prev["slow_ema"] and last["fast_ema"] > last["slow_ema"]:
            return "BUY" if TRADE_DIRECTION in ["LONG", "BOTH"] else None
        if prev["fast_ema"] >= prev["slow_ema"] and last["fast_ema"] < last["slow_ema"]:
            return "SELL" if TRADE_DIRECTION in ["SHORT", "BOTH"] else None
        return None

    def place_entry(self, signal):
        print(f"[ORDER] Placing {signal} order for {QUANTITY} qty of {SYMBOL}...")
        res = self.client.placeorder(
            strategy=STRATEGY_NAME, symbol=SYMBOL, exchange=EXCHANGE,
            action=signal, quantity=QUANTITY, price_type="MARKET", product=PRODUCT
        )
        if res.get("status") == "success":
            self.position = signal
            self.entry_price = self.ltp or float(res.get("price", 0))
            if signal == "BUY":
                self.sl_price = round(self.entry_price * (1 - (STOPLOSS_PCT / 100)), 2)
                self.tg_price = round(self.entry_price * (1 + (TARGET_PCT / 100)), 2)
            else:
                self.sl_price = round(self.entry_price * (1 + (STOPLOSS_PCT / 100)), 2)
                self.tg_price = round(self.entry_price * (1 - (TARGET_PCT / 100)), 2)
            print(f"[ENTRY EXECUTED] {signal} @ {self.entry_price} | SL: {self.sl_price} | TG: {self.tg_price}")

    def place_exit(self, reason):
        if not self.position or self.exit_in_progress:
            return
        self.exit_in_progress = True
        action = "SELL" if self.position == "BUY" else "BUY"
        print(f"[EXIT] Closing {self.position} - Reason: {reason}")
        self.client.placeorder(
            strategy=STRATEGY_NAME, symbol=SYMBOL, exchange=EXCHANGE,
            action=action, quantity=QUANTITY, price_type="MARKET", product=PRODUCT
        )
        self.position = None
        self.exit_in_progress = False

    def run(self):
        print(f"Starting {STRATEGY_NAME} Bot on {SYMBOL} ({EXCHANGE})...")
        def ws_worker():
            self.client.connect()
            self.client.subscribe_ltp(self.instrument, self.on_ltp_update)
        
        t_ws = threading.Thread(target=ws_worker, daemon=True)
        t_ws.start()
        time.sleep(2)
        
        while self.running:
            try:
                if not self.position and not self.exit_in_progress:
                    df = self.fetch_candles()
                    sig = self.check_signals(df)
                    if sig:
                        self.place_entry(sig)
                time.sleep(5)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    bot = QuantBot()
    bot.run()
