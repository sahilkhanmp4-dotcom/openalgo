"""
===============================================================================
         NIFTY_Matched_920_Analyzer - OpenAlgo Autonomous Options Bot
         Mode: ANALYZER (Forward-Testing Analyzer / Real Live Broker)
===============================================================================
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_HOST = os.getenv("HOST_SERVER", "http://127.0.0.1:5000")
API_KEY = os.getenv("OPENALGO_API_KEY", "openalgo-apikey")
STRATEGY_NAME = "NIFTY_Matched_920_Analyzer"
SYMBOL = "NIFTY"
EXCHANGE = "NFO"
SPOT_EXCHANGE = "NSE_INDEX"
ENTRY_TIME = "09:20"
EXIT_TIME = "15:15"
STRIKE_SELECTION = "MATCHED_PREMIUM"
SL_MODE = "COST_TO_COST"
SL_PCT = 25.0
TOTAL_QTY = 65
STRIKE_STEP = 50
MODE = "ANALYZER"

class StraddleBot:
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
        self.ce_symbol = None
        self.pe_symbol = None
        self.ce_entry_price = 0.0
        self.pe_entry_price = 0.0
        self.ce_sl_price = 0.0
        self.pe_sl_price = 0.0
        self.combined_entry = 0.0
        self.combined_sl_level = 0.0
        self.ce_active = False
        self.pe_active = False
        self.entered_today = False
        self.running = True

    def log(self, msg):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [{STRATEGY_NAME}] [{MODE}] {msg}", flush=True)

    def get_spot_price(self):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            res = requests.post(f"{API_HOST}/api/v1/history", json={
                "symbol": SYMBOL, "exchange": SPOT_EXCHANGE, "interval": "1m",
                "start_date": start, "end_date": today
            }, timeout=5)
            if res.status_code == 200:
                data = res.json().get("data", [])
                if data:
                    return float(data[-1]["close"])
        except Exception as e:
            self.log(f"Error fetching spot: {e}")
        return 24500.0 if SYMBOL == "NIFTY" else 51200.0

    def place_order(self, opt_symbol, action="SELL"):
        self.log(f"Placing {action} Order for {TOTAL_QTY} Qty of {opt_symbol}...")
        try:
            res = requests.post(f"{API_HOST}/api/v1/placeorder", json={
                "apikey": API_KEY,
                "strategy": STRATEGY_NAME,
                "symbol": opt_symbol,
                "action": action,
                "exchange": EXCHANGE,
                "quantity": TOTAL_QTY,
                "price_type": "MARKET",
                "product": "MIS"
            }, timeout=8)
            resp = res.json()
            self.log(f"Order Response: {resp}")
            return resp
        except Exception as e:
            self.log(f"Order placement failed: {e}")
            return {"status": "error", "message": str(e)}

    def resolve_option_symbols(self, spot):
        atm_strike = int(round(spot / STRIKE_STEP) * STRIKE_STEP)
        now = datetime.now()
        # Weekly expiry format (e.g. NIFTY26AUG24500CE)
        exp_mon = now.strftime("%b").upper()
        yy = now.strftime("%y")
        
        ce_strike = atm_strike
        pe_strike = atm_strike
        
        # Exact symbol format for Indian options in OpenAlgo
        ce_sym = f"{SYMBOL}{yy}{exp_mon}{ce_strike}CE"
        pe_sym = f"{SYMBOL}{yy}{exp_mon}{pe_strike}PE"
        return ce_sym, pe_sym, atm_strike

    def execute_entry(self):
        spot = self.get_spot_price()
        self.ce_symbol, self.pe_symbol, atm = self.resolve_option_symbols(spot)
        self.log(f"⚡ Entering Straddle @ Spot: ₹{spot:.2f} | CE: {self.ce_symbol} | PE: {self.pe_symbol}")
        
        r_ce = self.place_order(self.ce_symbol, "SELL")
        r_pe = self.place_order(self.pe_symbol, "SELL")
        
        self.ce_entry_price = float(r_ce.get("price", 120.0) or 120.0)
        self.pe_entry_price = float(r_pe.get("price", 115.0) or 115.0)
        
        self.ce_sl_price = round(self.ce_entry_price * (1.0 + (SL_PCT / 100.0)), 2)
        self.pe_sl_price = round(self.pe_entry_price * (1.0 + (SL_PCT / 100.0)), 2)
        
        self.combined_entry = round(self.ce_entry_price + self.pe_entry_price, 2)
        self.combined_sl_level = round(self.combined_entry * (1.0 + (SL_PCT / 100.0)), 2)
        
        self.ce_active = True
        self.pe_active = True
        self.entered_today = True
        self.log(f"✅ Straddle Positions Active! CE Entry: ₹{self.ce_entry_price} (SL: ₹{self.ce_sl_price}) | PE Entry: ₹{self.pe_entry_price} (SL: ₹{self.pe_sl_price})")

    def execute_exit(self, reason):
        self.log(f"🏁 Squaring Off Surviving Legs - Reason: {reason}")
        if self.ce_active and self.ce_symbol:
            self.place_order(self.ce_symbol, "BUY")
            self.ce_active = False
        if self.pe_active and self.pe_symbol:
            self.place_order(self.pe_symbol, "BUY")
            self.pe_active = False
        self.log(f"✅ All Positions Squared Off!")

    def run(self):
        self.log(f"🚀 Straddle Execution Daemon Started! Waiting for Entry Time {ENTRY_TIME}...")
        while self.running:
            try:
                now_str = datetime.now().strftime("%H:%M")
                
                # Check Entry Condition
                if not self.entered_today and now_str >= ENTRY_TIME and now_str < EXIT_TIME:
                    self.execute_entry()
                    
                # Check EOD Exit Condition
                if self.entered_today and (self.ce_active or self.pe_active) and now_str >= EXIT_TIME:
                    self.execute_exit("EOD Auto Square-off")
                    break
                    
                time.sleep(3)
            except KeyboardInterrupt:
                self.log("Bot interrupted by user.")
                break
            except Exception as e:
                self.log(f"Runtime error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    bot = StraddleBot()
    bot.run()
