"""
===============================================================================
  CrudeOil_MCX_Breakout - OpenAlgo MT5-Style Python Algo Bot
  Mode: ANALYZER (Forward-Testing Analyzer / Real Live Broker)
  Symbol: CRUDEOIL (MCX) | TF: 5m | Qty: 100
===============================================================================
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from openalgo import api

# --- USER CUSTOM STRATEGY LOGIC ---
def generate_signals(df, params):
    df["signal"] = "BUY"
    return df


# --- AUTOMATED OPENALGO BOT DRIVER ---
API_KEY = os.getenv("OPENALGO_API_KEY", "openalgo-apikey")
API_HOST = os.getenv("HOST_SERVER", "http://127.0.0.1:5000")
WS_URL = os.getenv("WEBSOCKET_URL", "ws://127.0.0.1:8765")

SYMBOL = "CRUDEOIL"
EXCHANGE = "MCX"
QUANTITY = 100
PRODUCT = "MIS"
TIMEFRAME = "5m"
STOPLOSS_PCT = 1.0
TARGET_PCT = 2.5
STRATEGY_NAME = "CrudeOil_MCX_Breakout"
MODE = "ANALYZER"

class CustomPythonBot:
    def __init__(self):
        self.client = api(api_key=API_KEY, host=API_HOST, ws_url=WS_URL)
        self.position = None
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.tg_price = 0.0
        self.ltp = None
        self.running = True
        self.instrument = [{"exchange": EXCHANGE, "symbol": SYMBOL}]

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{STRATEGY_NAME}] [{MODE}] {msg}", flush=True)

    def fetch_recent_candles(self):
        end = datetime.now()
        start = end - timedelta(days=5)
        df = self.client.history(
            symbol=SYMBOL, exchange=EXCHANGE, interval=TIMEFRAME,
            start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d")
        )
        return df

    def place_order(self, action):
        self.log(f"Placing {action} order for {QUANTITY} qty of {SYMBOL}...")
        res = self.client.placeorder(
            strategy=STRATEGY_NAME, symbol=SYMBOL, exchange=EXCHANGE,
            action=action, quantity=QUANTITY, price_type="MARKET", product=PRODUCT
        )
        return res

    def run(self):
        self.log(f"Starting Python Algo Bot on {SYMBOL} ({EXCHANGE})...")
        while self.running:
            try:
                df = self.fetch_recent_candles()
                if df is not None and not df.empty:
                    params = {
                        "symbol": SYMBOL, "exchange": EXCHANGE, "timeframe": TIMEFRAME,
                        "quantity": QUANTITY, "stoploss_val": STOPLOSS_PCT, "target_val": TARGET_PCT
                    }
                    if "generate_signals" in globals():
                        df_signals = generate_signals(df, params)
                        if not df_signals.empty and "signal" in df_signals.columns:
                            last_sig = df_signals.iloc[-1]["signal"]
                            if last_sig in ["BUY", "SELL"] and last_sig != self.position:
                                if self.position:
                                    # Square off previous
                                    self.place_order("SELL" if self.position == "BUY" else "BUY")
                                self.place_order(last_sig)
                                self.position = last_sig
                time.sleep(10)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log(f"Runtime tick error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = CustomPythonBot()
    bot.run()
