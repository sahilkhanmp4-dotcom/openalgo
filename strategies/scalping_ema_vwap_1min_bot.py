#!/usr/bin/env python3
# ===============================================================================
# ⚡ 1-MIN EMA (20/50) + VWAP CONVERGENCE SCALPING & TREND FOLLOWING BOT
# ===============================================================================
# 
# 🎯 STRATEGY RULES:
# 1. TIMEFRAME: 1-Minute Candlestick (Live-Aggregated + History fallback).
# 2. CONVERGENCE & ALIGNMENT LOGIC:
#    🟢 BUY (LONG) ENTRY:
#       - Fast EMA (20) > Slow EMA (50).
#       - Price (Close) > Intraday VWAP.
#       - Bullish confirmation candle closing above 20 EMA, 50 EMA & VWAP.
#
#    🔴 SELL (SHORT) ENTRY:
#       - Fast EMA (20) < Slow EMA (50).
#       - Price (Close) < Intraday VWAP.
#       - Bearish confirmation candle closing below 20 EMA, 50 EMA & VWAP.
#
# 3. POSITION CONTROL:
#    - Strict Single-Position Rule: "Agar position hai to new nahi lena hai".
#
# 4. RISK MANAGEMENT & TARGETS:
#    - Initial SL (Stoploss): Swing Low/High (or VWAP/50 EMA buffer) at entry.
#    - Risk = |Entry Price - Initial SL|.
#    - Target 1 (1:2 R:R): Partial profit booking (50%) & Stoploss moved to Cost.
#    - Target 2 (1:3 R:R): Full Target Exit.
#    - Dynamic 20 EMA Trailing SL on candle close.
#    - Hard Intraday Auto Square-Off at EOD.
# ===============================================================================

import os
import sys
import time
import json
import logging
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

# Load environment configurations
load_dotenv()

LOG_FILE = "scalping_ema_vwap_1min_bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a")
    ]
)
logger = logging.getLogger("1MinConvergenceBot")

# ────────────────────────── CONFIGURATION ──────────────────────────
OPENALGO_HOST = os.getenv("OPENALGO_HOST", "http://127.0.0.1:5000")
API_KEY = os.getenv("OPENALGO_API_KEY", "f9e70eaeb9587c1f29de4d6cbfc9e2d83e9cffc1ae4b5ffda2b7e3036cdd2cba")

SYMBOL = os.getenv("TRADING_SYMBOL", "")
EXCHANGE = os.getenv("TRADING_EXCHANGE", "")
QUANTITY = int(os.getenv("QUANTITY", "0"))
PRODUCT = os.getenv("PRODUCT", "MIS")             # MIS for Intraday
PRICE_TYPE = "MARKET"

# Auto-resolve active Symbol if not provided in environment
if not SYMBOL or not EXCHANGE:
    try:
        db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "openalgo.db")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT exchange, symbol FROM symtoken WHERE exchange='NFO' AND symbol LIKE 'NIFTY%FUT' AND symbol NOT LIKE '%FPI%' ORDER BY symbol ASC LIMIT 1;")
        row = cursor.fetchone()
        if row and row[1]:
            EXCHANGE = row[0]
            SYMBOL = row[1]
            if QUANTITY <= 0:
                QUANTITY = 50
        else:
            EXCHANGE = "NSE"
            SYMBOL = "RELIANCE"
            if QUANTITY <= 0:
                QUANTITY = 1
        conn.close()
    except Exception:
        EXCHANGE = "NFO"
        SYMBOL = "NIFTY29SEP26FUT"
        if QUANTITY <= 0:
            QUANTITY = 50

if QUANTITY <= 0:
    QUANTITY = 50

TOTAL_QUANTITY = QUANTITY

# Indicator Parameters
EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
MIN_RISK_PTS = 2.0                                # Minimum risk floor points to prevent zero/micro SL

# Risk-Reward Multipliers
TARGET_RR_1 = 2.0                                 # 1:2 Risk-Reward
TARGET_RR_2 = 3.0                                 # 1:3 Risk-Reward
PARTIAL_BOOK_T1 = True                            # Book 50% quantity at 1:2 and move SL to Cost

# Intraday Timing (IST Defaults)
SQUARE_OFF_HOUR = int(os.getenv("EOD_HOUR", "15"))
SQUARE_OFF_MIN = int(os.getenv("EOD_MIN", "15"))

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scratch", "scalping_1min_state.json")


class LiveCandleAggregator:
    """Aggregates real-time ticks into 1-minute OHLCV candles."""
    def __init__(self):
        self.candles = []
        self.current_candle = None
        self.current_minute = None

    def process_tick(self, ltp: float, volume: float = 1.0) -> bool:
        """Add tick. Returns True if a 1-minute candle has just closed."""
        now = datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M:00")

        candle_closed = False
        if self.current_minute is None:
            self.current_minute = minute_key
            self.current_candle = {
                "timestamp": int(now.timestamp()),
                "datetime": minute_key,
                "open": ltp,
                "high": ltp,
                "low": ltp,
                "close": ltp,
                "volume": volume
            }
        elif self.current_minute != minute_key:
            # Previous candle finalized
            self.candles.append(self.current_candle)
            if len(self.candles) > 300:
                self.candles.pop(0)
            candle_closed = True

            # Start new candle
            self.current_minute = minute_key
            self.current_candle = {
                "timestamp": int(now.timestamp()),
                "datetime": minute_key,
                "open": ltp,
                "high": ltp,
                "low": ltp,
                "close": ltp,
                "volume": volume
            }
        else:
            # Update existing candle in progress
            self.current_candle["high"] = max(self.current_candle["high"], ltp)
            self.current_candle["low"] = min(self.current_candle["low"], ltp)
            self.current_candle["close"] = ltp
            self.current_candle["volume"] += volume

        return candle_closed

    def get_dataframe(self) -> pd.DataFrame:
        data = list(self.candles)
        if self.current_candle:
            data.append(self.current_candle)
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)


class ConvergenceScalpingBot:
    def __init__(self):
        self.position = 0
        self.entry_price = 0.0
        self.initial_sl = 0.0
        self.trailing_sl = 0.0
        self.target_1 = 0.0
        self.target_2 = 0.0
        self.risk_pts = 0.0
        
        self.remaining_qty = TOTAL_QUANTITY
        self.target_1_hit = False
        self.target_2_hit = False
        self.last_bar_time = None
        self.last_tick_price = 0.0

        self.aggregator = LiveCandleAggregator()
        self.load_state()

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            state = {
                "position": self.position,
                "entry_price": self.entry_price,
                "initial_sl": self.initial_sl,
                "trailing_sl": self.trailing_sl,
                "target_1": self.target_1,
                "target_2": self.target_2,
                "risk_pts": self.risk_pts,
                "remaining_qty": self.remaining_qty,
                "target_1_hit": self.target_1_hit,
                "target_2_hit": self.target_2_hit,
                "symbol": SYMBOL,
                "exchange": EXCHANGE,
                "timestamp": datetime.now().isoformat()
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    if state.get("symbol") == SYMBOL:
                        self.position = state.get("position", 0)
                        self.entry_price = state.get("entry_price", 0.0)
                        self.initial_sl = state.get("initial_sl", 0.0)
                        self.trailing_sl = state.get("trailing_sl", 0.0)
                        self.target_1 = state.get("target_1", 0.0)
                        self.target_2 = state.get("target_2", 0.0)
                        self.risk_pts = state.get("risk_pts", 0.0)
                        self.remaining_qty = state.get("remaining_qty", TOTAL_QUANTITY)
                        self.target_1_hit = state.get("target_1_hit", False)
                        self.target_2_hit = state.get("target_2_hit", False)
                        if self.position != 0:
                            logger.info(f"🔄 Recovered Active Position: {'LONG' if self.position == 1 else 'SHORT'} @ ₹{self.entry_price:.2f} | Remaining Qty: {self.remaining_qty}")
            except Exception as e:
                logger.error(f"Error loading state: {e}")

    def clear_state(self):
        self.position = 0
        self.entry_price = 0.0
        self.initial_sl = 0.0
        self.trailing_sl = 0.0
        self.target_1 = 0.0
        self.target_2 = 0.0
        self.risk_pts = 0.0
        self.remaining_qty = TOTAL_QUANTITY
        self.target_1_hit = False
        self.target_2_hit = False
        self.save_state()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"] if "datetime" in df.columns else df["timestamp"], unit="s" if isinstance(df["timestamp"].iloc[0], (int, float, np.integer, np.floating)) else None)
        
        # 1. EMAs
        df["ema20"] = df["close"].ewm(span=EMA_FAST_PERIOD, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=EMA_SLOW_PERIOD, adjust=False).mean()

        # 2. Session VWAP
        df["date"] = df["datetime"].dt.date
        df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3.0
        if "volume" not in df.columns or df["volume"].sum() == 0:
            df["volume"] = 1.0

        df["pv"] = df["typical_price"] * df["volume"]
        df["cum_pv"] = df.groupby("date")["pv"].cumsum()
        df["cum_vol"] = df.groupby("date")["volume"].cumsum()
        df["vwap"] = df["cum_pv"] / df["cum_vol"]
        df["vwap"] = df["vwap"].fillna(df["close"])

        return df

    def place_order(self, action: str, qty: int, comment: str = ""):
        if qty <= 0:
            return

        payload = {
            "apikey": API_KEY,
            "strategy": "Convergence_1Min_Scalper",
            "symbol": SYMBOL,
            "action": action.upper(),
            "exchange": EXCHANGE,
            "pricetype": PRICE_TYPE,
            "product": PRODUCT,
            "quantity": str(qty),
            "price": "0"
        }
        ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        logger.info(f"[{ts_now}] 🚀 EXECUTING ORDER: {action} {qty}x {SYMBOL} | Reason: {comment}")
        try:
            url = f"{OPENALGO_HOST}/api/v1/orders"
            resp = requests.post(url, json=payload, timeout=8)
            logger.info(f"[{ts_now}] OpenAlgo Response [{resp.status_code}]: {resp.text}")
        except Exception as e:
            logger.error(f"[{ts_now}] Failed to place order: {e}")

    def on_tick(self, ltp: float, volume: float = 1.0):
        if ltp <= 0:
            return

        self.last_tick_price = ltp
        ts_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # 1. Manage Active Position (SL, Targets)
        if self.position == 1:
            pnl_pts = ltp - self.entry_price
            effective_sl = max(self.initial_sl, self.trailing_sl)

            if ltp <= effective_sl:
                logger.info(f"\n[{ts_now}] 🛑 STOPLOSS HIT (Long): LTP ₹{ltp:.2f} <= SL ₹{effective_sl:.2f} (PnL: {pnl_pts:+.2f} pts)")
                self.place_order("SELL", self.remaining_qty, comment=f"SL Hit @ ₹{ltp:.2f}")
                self.clear_state()
                return

            if not self.target_1_hit and ltp >= self.target_1:
                self.target_1_hit = True
                if PARTIAL_BOOK_T1 and self.remaining_qty > 1:
                    exit_qty = self.remaining_qty // 2
                    self.remaining_qty -= exit_qty
                    logger.info(f"\n[{ts_now}] 🎯 TARGET 1 (1:2) HIT (Long) @ ₹{ltp:.2f}! Booking 50% ({exit_qty} qty). Moving SL to Cost ₹{self.entry_price:.2f}")
                    self.place_order("SELL", exit_qty, comment="Target 1 (1:2) Book 50%")
                else:
                    logger.info(f"\n[{ts_now}] 🎯 TARGET 1 (1:2) REACHED (Long) @ ₹{ltp:.2f}! Moving SL to Cost ₹{self.entry_price:.2f}")
                self.trailing_sl = max(self.trailing_sl, self.entry_price)
                self.save_state()

            if not self.target_2_hit and ltp >= self.target_2:
                self.target_2_hit = True
                logger.info(f"\n[{ts_now}] 🏆 TARGET 2 (1:3) HIT (Long) @ ₹{ltp:.2f}! Full Target Achieved.")
                self.place_order("SELL", self.remaining_qty, comment="Target 2 (1:3) Full Target Exit 🏆")
                self.clear_state()
                return

        elif self.position == -1:
            pnl_pts = self.entry_price - ltp
            effective_sl = min(self.initial_sl, self.trailing_sl) if self.trailing_sl > 0 else self.initial_sl

            if ltp >= effective_sl:
                logger.info(f"\n[{ts_now}] 🛑 STOPLOSS HIT (Short): LTP ₹{ltp:.2f} >= SL ₹{effective_sl:.2f} (PnL: {pnl_pts:+.2f} pts)")
                self.place_order("BUY", self.remaining_qty, comment=f"SL Hit @ ₹{ltp:.2f}")
                self.clear_state()
                return

            if not self.target_1_hit and ltp <= self.target_1:
                self.target_1_hit = True
                if PARTIAL_BOOK_T1 and self.remaining_qty > 1:
                    exit_qty = self.remaining_qty // 2
                    self.remaining_qty -= exit_qty
                    logger.info(f"\n[{ts_now}] 🎯 TARGET 1 (1:2) HIT (Short) @ ₹{ltp:.2f}! Booking 50% ({exit_qty} qty). Moving SL to Cost ₹{self.entry_price:.2f}")
                    self.place_order("BUY", exit_qty, comment="Target 1 (1:2) Book 50%")
                else:
                    logger.info(f"\n[{ts_now}] 🎯 TARGET 1 (1:2) REACHED (Short) @ ₹{ltp:.2f}! Moving SL to Cost ₹{self.entry_price:.2f}")
                self.trailing_sl = min(self.trailing_sl if self.trailing_sl > 0 else 999999.0, self.entry_price)
                self.save_state()

            if not self.target_2_hit and ltp <= self.target_2:
                self.target_2_hit = True
                logger.info(f"\n[{ts_now}] 🏆 TARGET 2 (1:3) HIT (Short) @ ₹{ltp:.2f}! Full Target Achieved.")
                self.place_order("BUY", self.remaining_qty, comment="Target 2 (1:3) Full Target Exit 🏆")
                self.clear_state()
                return

        # 2. Feed tick to aggregator and check for candle close
        closed = self.aggregator.process_tick(ltp, volume)
        if closed:
            df = self.aggregator.get_dataframe()
            if len(df) >= 15:
                self.on_bar_close(df)

    def on_bar_close(self, df: pd.DataFrame):
        df = self.calculate_indicators(df)
        curr_idx = len(df) - 1
        curr = df.iloc[curr_idx]
        prev = df.iloc[curr_idx - 1]

        now = datetime.now()
        sys_time_str = now.strftime("%I:%M:%S %p")
        bar_time_str = curr["datetime"].strftime("%I:%M:%S %p") if isinstance(curr["datetime"], datetime) else str(curr["datetime"])
        is_eod = (now.hour == SQUARE_OFF_HOUR and now.minute >= SQUARE_OFF_MIN) or (now.hour > SQUARE_OFF_HOUR)

        if is_eod:
            if self.position == 1:
                logger.info(f"[{sys_time_str}] 🕐 INTRADAY EOD AUTO SQUARE-OFF (Long)")
                self.place_order("SELL", self.remaining_qty, comment="EOD Auto Square-off 🕐")
                self.clear_state()
            elif self.position == -1:
                logger.info(f"[{sys_time_str}] 🕐 INTRADAY EOD AUTO SQUARE-OFF (Short)")
                self.place_order("BUY", self.remaining_qty, comment="EOD Auto Square-off 🕐")
                self.clear_state()
            return

        # 20 EMA Trailing Exit
        if self.position == 1:
            if curr["close"] < curr["ema20"]:
                logger.info(f"[{sys_time_str}] 📉 20 EMA TRAIL EXIT (Long): Candle Close ₹{curr['close']:.2f} < 20 EMA ₹{curr['ema20']:.2f}")
                self.place_order("SELL", self.remaining_qty, comment="20 EMA Trail Stop Triggered ▼")
                self.clear_state()
                return
            else:
                trail_candidate = max(curr["ema20"] - 1.0, prev["low"])
                if trail_candidate > self.trailing_sl:
                    self.trailing_sl = trail_candidate
                    self.save_state()

        elif self.position == -1:
            if curr["close"] > curr["ema20"]:
                logger.info(f"[{sys_time_str}] 📈 20 EMA TRAIL EXIT (Short): Candle Close ₹{curr['close']:.2f} > 20 EMA ₹{curr['ema20']:.2f}")
                self.place_order("BUY", self.remaining_qty, comment="20 EMA Trail Stop Triggered ▲")
                self.clear_state()
                return
            else:
                trail_candidate = min(curr["ema20"] + 1.0, prev["high"])
                if self.trailing_sl == 0 or trail_candidate < self.trailing_sl:
                    self.trailing_sl = trail_candidate
                    self.save_state()

        # Strict Single-Position Entry Check
        if self.position == 0 and not is_eod:
            bullish_alignment = (curr["ema20"] > curr["ema50"]) and (curr["close"] > curr["vwap"])
            bullish_candle = curr["close"] >= curr["open"] and curr["close"] > curr["ema20"]
            fresh_bullish = (prev["close"] <= prev["ema20"] or prev["close"] <= prev["vwap"] or prev["ema20"] <= prev["ema50"])

            bearish_alignment = (curr["ema20"] < curr["ema50"]) and (curr["close"] < curr["vwap"])
            bearish_candle = curr["close"] <= curr["open"] and curr["close"] < curr["ema20"]
            fresh_bearish = (prev["close"] >= prev["ema20"] or prev["close"] >= prev["vwap"] or prev["ema20"] >= prev["ema50"])

            if bullish_alignment and bullish_candle and fresh_bullish:
                self.position = 1
                self.entry_price = curr["close"]
                sl_base = min(curr["low"], prev["low"], curr["vwap"], curr["ema50"])
                self.risk_pts = max(self.entry_price - sl_base, MIN_RISK_PTS)
                self.initial_sl = self.entry_price - self.risk_pts
                self.trailing_sl = self.initial_sl
                self.target_1 = self.entry_price + (self.risk_pts * TARGET_RR_1)
                self.target_2 = self.entry_price + (self.risk_pts * TARGET_RR_2)
                self.remaining_qty = TOTAL_QUANTITY
                self.target_1_hit = False
                self.target_2_hit = False
                self.save_state()

                logger.info(f"\n{'='*75}")
                logger.info(f"[{sys_time_str}] 🚀 1-MIN CONVERGENCE BUY (LONG) TRIGGERED!")
                logger.info(f"📊 Price: ₹{self.entry_price:.2f} | 20 EMA: ₹{curr['ema20']:.2f} | 50 EMA: ₹{curr['ema50']:.2f} | VWAP: ₹{curr['vwap']:.2f}")
                logger.info(f"🎯 Entry: ₹{self.entry_price:.2f} | SL: ₹{self.initial_sl:.2f} (Risk: {self.risk_pts:.2f} pts)")
                logger.info(f"🎯 Target 1 (1:2): ₹{self.target_1:.2f} | Target 2 (1:3): ₹{self.target_2:.2f}")
                logger.info(f"{'='*75}\n")
                self.place_order("BUY", self.remaining_qty, comment=f"BUY Long (1:2, 1:3) SL:{self.initial_sl:.2f}")

            elif bearish_alignment and bearish_candle and fresh_bearish:
                self.position = -1
                self.entry_price = curr["close"]
                sl_base = max(curr["high"], prev["high"], curr["vwap"], curr["ema50"])
                self.risk_pts = max(sl_base - self.entry_price, MIN_RISK_PTS)
                self.initial_sl = self.entry_price + self.risk_pts
                self.trailing_sl = self.initial_sl
                self.target_1 = self.entry_price - (self.risk_pts * TARGET_RR_1)
                self.target_2 = self.entry_price - (self.risk_pts * TARGET_RR_2)
                self.remaining_qty = TOTAL_QUANTITY
                self.target_1_hit = False
                self.target_2_hit = False
                self.save_state()

                logger.info(f"\n{'='*75}")
                logger.info(f"[{sys_time_str}] 🚀 1-MIN CONVERGENCE SELL (SHORT) TRIGGERED!")
                logger.info(f"📊 Price: ₹{self.entry_price:.2f} | 20 EMA: ₹{curr['ema20']:.2f} | 50 EMA: ₹{curr['ema50']:.2f} | VWAP: ₹{curr['vwap']:.2f}")
                logger.info(f"🎯 Entry: ₹{self.entry_price:.2f} | SL: ₹{self.initial_sl:.2f} (Risk: {self.risk_pts:.2f} pts)")
                logger.info(f"🎯 Target 1 (1:2): ₹{self.target_1:.2f} | Target 2 (1:3): ₹{self.target_2:.2f}")
                logger.info(f"{'='*75}\n")
                self.place_order("SELL", self.remaining_qty, comment=f"SELL Short (1:2, 1:3) SL:{self.initial_sl:.2f}")

        if self.last_bar_time != curr["timestamp"]:
            self.last_bar_time = curr["timestamp"]
            if self.position == 1:
                status = f"🟢 LONG ACTIVE | Entry: ₹{self.entry_price:.2f} | SL: ₹{max(self.initial_sl, self.trailing_sl):.2f} | T1 (1:2): ₹{self.target_1:.2f} | T2 (1:3): ₹{self.target_2:.2f}"
            elif self.position == -1:
                status = f"🔴 SHORT ACTIVE | Entry: ₹{self.entry_price:.2f} | SL: ₹{self.trailing_sl:.2f} | T1 (1:2): ₹{self.target_1:.2f} | T2 (1:3): ₹{self.target_2:.2f}"
            else:
                bias = "🟢 BULLISH ALIGNED" if (curr["ema20"] > curr["ema50"] and curr["close"] > curr["vwap"]) else ("🔴 BEARISH ALIGNED" if (curr["ema20"] < curr["ema50"] and curr["close"] < curr["vwap"]) else "⏳ CONVERGING / CHOP")
                status = f"🔍 SCANNING 1-MIN SIGNALS | Trend State: {bias}"

            print(f"\n╔══════════════════════════════════════════════════════════════════════════════════════")
            print(f"║ 🕒 System Time: {sys_time_str} | Candle Time: {bar_time_str} | Symbol: {SYMBOL} (1m)")
            print(f"║ 📊 Price: ₹{curr['close']:.2f} | 20 EMA: ₹{curr['ema20']:.2f} | 50 EMA: ₹{curr['ema50']:.2f} | VWAP: ₹{curr['vwap']:.2f}")
            print(f"║ 📌 Status: {status}")
            print(f"╚══════════════════════════════════════════════════════════════════════════════════════\n")


def run_live_bot():
    bot = ConvergenceScalpingBot()
    logger.info("=" * 80)
    logger.info(f"⚡ Starting 1-Min 20/50 EMA + VWAP Convergence Scalping Engine")
    logger.info(f"🎯 Target R:R: 1:2 (T1) & 1:3 (T2) | Trailing SL: 20 EMA | Intraday Hard SL")
    logger.info(f"📌 Symbol: {SYMBOL} | Exchange: {EXCHANGE} | Quantity: {TOTAL_QUANTITY}")
    logger.info("=" * 80)

    session = requests.Session()
    conn_warned = False

    while True:
        try:
            # High-speed live quote polling
            quote_url = f"{OPENALGO_HOST}/api/v1/quotes"
            q_resp = session.post(quote_url, json={"apikey": API_KEY, "symbol": SYMBOL, "exchange": EXCHANGE}, timeout=4)
            if q_resp.status_code == 200:
                if conn_warned:
                    logger.info("🟢 Connection to OpenAlgo restored!")
                    conn_warned = False
                q_data = q_resp.json().get("data", {})
                ltp = float(q_data.get("ltp") or 0.0)
                vol = float(q_data.get("volume") or 1.0)
                if ltp > 0:
                    bot.on_tick(ltp, vol)

        except requests.exceptions.Timeout:
            time.sleep(0.5)
            continue
        except requests.exceptions.ConnectionError:
            if not conn_warned:
                logger.warning("⚠️ OpenAlgo server unreachable on port 5000. Retrying in background...")
                conn_warned = True
            time.sleep(1)
            continue
        except Exception as e:
            logger.error(f"Error in live loop: {e}")

        time.sleep(1.0)


if __name__ == "__main__":
    try:
        run_live_bot()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
