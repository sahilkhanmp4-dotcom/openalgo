#!/usr/bin/env python3
# ===============================================================================
# ⚡ CRUDE OIL - 20 & 50 EMA SEQUENTIAL REVERSAL BOT (LIVE TICK + TIMESTAMPS)
# ===============================================================================
# Modeled strictly with 3 sequential conditions & millisecond timestamps:
#
# 🟢 BUY LOGIC:
#   [Condition 1]: 12-bar downtrend check (>= 85% closes strictly below both 20 & 50 EMAs)
#                  ⬇️ (Wait until 100% satisfied)
#   [Condition 2]: Bullish Breakout closes above BOTH EMAs -> Mark High (breakout_high)
#                  ⬇️ (Wait min 2 bars gap & pullback)
#   [Condition 3]: Retest confirmed (Low touches upper EMA) & Trigger fires:
#                  Tick/Bar crosses & closes above Marked High -> ENTER BUY (LONG)
#                  SL = Retest Low - 3 pts | Trailing = Close below 20 EMA
#
# 🔴 SELL LOGIC:
#   [Condition 1]: 12-bar uptrend check (>= 85% closes strictly above both 20 & 50 EMAs)
#                  ⬇️ (Wait until 100% satisfied)
#   [Condition 2]: Bearish Breakdown closes below BOTH EMAs -> Mark Low (breakdown_low)
#                  ⬇️ (Wait min 2 bars gap & bounce)
#   [Condition 3]: Retest confirmed (High touches lower EMA) & Trigger fires:
#                  Tick/Bar crosses & closes below Marked Low -> ENTER SELL (SHORT)
#                  SL = Retest High + 3 pts | Trailing = Close above 20 EMA
# ===============================================================================

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

# Load environment configurations
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("crude_ema_tick_bot.log", mode="a")
    ]
)
logger = logging.getLogger("CrudeEMATickBot")

# ────────────────────────── CONFIGURATION ──────────────────────────
OPENALGO_HOST = os.getenv("OPENALGO_HOST", "http://127.0.0.1:5000")
API_KEY = "f9e70eaeb9587c1f29de4d6cbfc9e2d83e9cffc1ae4b5ffda2b7e3036cdd2cba"
logger.info(f"✅ Using Permanent API Key: {API_KEY[:8]}...{API_KEY[-6:]}")

# Strategy Parameters (Matching exact Pine Script defaults)
SYMBOL = os.getenv("CRUDE_SYMBOL", "")
EXCHANGE = "MCX"
INTERVAL = "5m"               # 5-minute timeframe
QUANTITY = 1                  # Number of contracts / lots
PRODUCT = "MIS"               # Intraday
PRICE_TYPE = "MARKET"

# Auto-resolve active MCX Crude Futures contract
if not SYMBOL or SYMBOL == "CRUDEOIL":
    try:
        import sqlite3
        db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "openalgo.db")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM symtoken WHERE exchange='MCX' AND symbol LIKE 'CRUDEOIL%FUT' AND symbol NOT LIKE 'CRUDEOILM%' AND (symbol LIKE '%SEP%' OR symbol LIKE '%AUG%') LIMIT 1;")
        row = cursor.fetchone()
        if row and row[0]:
            SYMBOL = row[0]
        else:
            SYMBOL = "CRUDEOIL21SEP26FUT"
        logger.info(f"🎯 Auto-selected active MCX Crude Future Contract: {SYMBOL}")
        conn.close()
    except Exception:
        SYMBOL = "CRUDEOIL21SEP26FUT"

TRADE_MODE = "BOTH"           # "BUY Only", "SELL Only", or "BOTH"
EMA_FAST = 20                 # Fast EMA (Trailing)
EMA_SLOW = 50                 # Slow EMA (Trend)

TREND_MIN_BARS = 12           # Minimum established trend lookback
TREND_MIN_RATIO = 85.0        # % of bars that must strictly stay on trend side
MIN_RETEST_GAP = 2            # Minimum bars after breakout before retest is valid
MAX_WAIT_BARS = 25            # Maximum bars to wait for Retest + Trigger
INVALIDATE_PTS = 15.0         # Invalidate setup if price crosses opposite EMA by X pts
SL_BUFFER = 3.0               # Stoploss buffer points
USE_TRAIL = True              # Trail exit when price closes on wrong side of 20 EMA

# Session & Intraday timing (MCX Crude Trading Hours)
EOD_HOUR = 23
EOD_MIN = 25


class CrudeSequentialStrategy:
    def __init__(self):
        # 3-Stage State Machines
        # Stage 0: Scanning Condition 1 (Trend Quality)
        # Stage 1: Condition 1 Passed -> Condition 2 Breakout/Breakdown Marked (Waiting for Retest)
        # Stage 2: Condition 2 Retest Done -> Condition 3 Trigger Armed (Waiting for Trigger Candle)
        # Stage 3: In Active Trade
        self.long_stage = 0
        self.breakout_high = None
        self.breakout_bar_l = 0
        self.retest_swing_low = None
        self.long_close_below_count = 0  # Counts candles closing below lower EMA after breakout

        self.short_stage = 0
        self.breakdown_low = None
        self.breakout_bar_s = 0
        self.retest_swing_high = None
        self.short_close_above_count = 0  # Counts candles closing above upper EMA after breakdown

        # Position Tracking
        self.position = 0           # +1 for Long, -1 for Short, 0 for Flat
        self.entry_price = 0.0
        self.current_sl = 0.0
        self.last_bar_time = None
        self.last_tick_price = 0.0

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate 20 and 50 Exponential Moving Averages."""
        df = df.copy()
        df["ema20"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
        df["ema_top"] = np.maximum(df["ema20"], df["ema50"])
        df["ema_bot"] = np.minimum(df["ema20"], df["ema50"])
        return df

    def check_downtrend_quality(self, df: pd.DataFrame, current_idx: int) -> float:
        """Check Condition 1: Purity (%) of established downtrend over last 12 bars."""
        if current_idx < TREND_MIN_BARS:
            return 0.0
        subset = df.iloc[current_idx - TREND_MIN_BARS: current_idx]
        count = ((subset["close"] < subset["ema20"]) & (subset["close"] < subset["ema50"])).sum()
        return (count / TREND_MIN_BARS) * 100.0

    def check_uptrend_quality(self, df: pd.DataFrame, current_idx: int) -> float:
        """Check Condition 1: Purity (%) of established uptrend over last 12 bars."""
        if current_idx < TREND_MIN_BARS:
            return 0.0
        subset = df.iloc[current_idx - TREND_MIN_BARS: current_idx]
        count = ((subset["close"] > subset["ema20"]) & (subset["close"] > subset["ema50"])).sum()
        return (count / TREND_MIN_BARS) * 100.0

    def place_order(self, action: str, price: float = 0.0, comment: str = ""):
        """Send automated order via OpenAlgo API."""
        payload = {
            "apikey": API_KEY,
            "strategy": "Crude_Sequential_EMA_Bot",
            "symbol": SYMBOL,
            "action": action.upper(),
            "exchange": EXCHANGE,
            "pricetype": PRICE_TYPE,
            "product": PRODUCT,
            "quantity": str(QUANTITY),
            "price": str(price) if PRICE_TYPE == "LIMIT" else "0"
        }
        ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        logger.info(f"[{ts_now}] 🚀 EXECUTING ORDER: {action} {QUANTITY}x {SYMBOL} ({comment})")
        try:
            url = f"{OPENALGO_HOST}/api/v1/orders"
            resp = requests.post(url, json=payload, timeout=8)
            logger.info(f"[{ts_now}] OpenAlgo Response [{resp.status_code}]: {resp.text}")
        except Exception as e:
            logger.error(f"[{ts_now}] Failed to place order: {e}")

    def on_tick(self, ltp: float):
        """Evaluate real-time ticks for live SL, Trailing, and fast triggers."""
        if ltp <= 0:
            return

        self.last_tick_price = ltp
        ts_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # 1. Real-time Live Trade Monitoring (SL & Trailing)
        if self.position == 1:
            pnl_pts = ltp - self.entry_price
            if ltp <= self.current_sl:
                logger.info(f"\n[{ts_now}] 🛑 TICK STOPLOSS HIT (Long): LTP ₹{ltp:.2f} <= SL ₹{self.current_sl:.2f}")
                self.place_order("SELL", comment="Live SL Hit ✖")
                self.position = 0
            else:
                print(f"[{ts_now}] 🟢 LONG ACTIVE | LTP: ₹{ltp:.2f} | Entry: ₹{self.entry_price:.2f} | SL: ₹{self.current_sl:.2f} | PnL: {pnl_pts:+.2f} pts", end="\r")

        elif self.position == -1:
            pnl_pts = self.entry_price - ltp
            if ltp >= self.current_sl:
                logger.info(f"\n[{ts_now}] 🛑 TICK STOPLOSS HIT (Short): LTP ₹{ltp:.2f} >= SL ₹{self.current_sl:.2f}")
                self.place_order("BUY", comment="Live SL Hit ✖")
                self.position = 0
            else:
                print(f"[{ts_now}] 🔴 SHORT ACTIVE | LTP: ₹{ltp:.2f} | Entry: ₹{self.entry_price:.2f} | SL: ₹{self.current_sl:.2f} | PnL: {pnl_pts:+.2f} pts", end="\r")

    def on_bar_close(self, df: pd.DataFrame):
        """Sequential rule evaluation on every completed 5m candle."""
        if len(df) < max(EMA_SLOW, TREND_MIN_BARS) + 5:
            return

        df = self.calculate_indicators(df)
        curr_idx = len(df) - 1
        curr = df.iloc[curr_idx]
        prev = df.iloc[curr_idx - 1]

        # Use local system time for all user-facing timestamps
        sys_time_str = datetime.now().strftime("%I:%M:%S %p")
        bar_dt = pd.to_datetime(curr["timestamp"], unit="s" if isinstance(curr["timestamp"], (int, float)) else None)
        bar_time_str = bar_dt.strftime("%I:%M:%S %p") if bar_dt is not None else sys_time_str
        is_eod = (datetime.now().hour == EOD_HOUR and datetime.now().minute >= EOD_MIN) or (datetime.now().hour > EOD_HOUR)

        allow_long = TRADE_MODE in ["BUY Only", "BOTH"]
        allow_short = TRADE_MODE in ["SELL Only", "BOTH"]

        dt_quality = self.check_downtrend_quality(df, curr_idx)
        ut_quality = self.check_uptrend_quality(df, curr_idx)
        cond1_long_ok = dt_quality >= TREND_MIN_RATIO
        cond1_short_ok = ut_quality >= TREND_MIN_RATIO

        # Print detailed status card on new candle or state transition
        if self.last_bar_time != curr["timestamp"]:
            self.last_bar_time = curr["timestamp"]
            
            # Determine state text & current action
            if self.position == 1:
                pos_status = f"🟢 IN LONG (BUY REVERSAL) TRADE @ ₹{self.entry_price:.2f} (SL: ₹{self.current_sl:.2f} | PnL: {curr['close'] - self.entry_price:+.2f} pts)"
                action_text = f"🎯 Action: Trailing price with 20 EMA (₹{curr['ema20']:.2f}) & SL (₹{self.current_sl:.2f})"
            elif self.position == -1:
                pos_status = f"🔴 IN SHORT (SELL REVERSAL) TRADE @ ₹{self.entry_price:.2f} (SL: ₹{self.current_sl:.2f} | PnL: {self.entry_price - curr['close']:+.2f} pts)"
                action_text = f"🎯 Action: Trailing price with 20 EMA (₹{curr['ema20']:.2f}) & SL (₹{self.current_sl:.2f})"
            else:
                if self.long_stage == 1:
                    pos_status = f"🔍 BUY REVERSAL: Breakout Marked @ ₹{self.breakout_high:.2f}"
                    action_text = f"🎯 Action: Waiting for Retest to Upper EMA (Pullback >= 2 candles)"
                elif self.long_stage == 2:
                    pos_status = f"🎯 BUY REVERSAL: Retest Done ✓ [Armed for Trigger]"
                    action_text = f"🎯 Action: Waiting for 5m candle body close above ₹{self.breakout_high:.2f} to BUY"
                elif self.short_stage == 1:
                    pos_status = f"🔍 SELL REVERSAL: Breakdown Marked @ ₹{self.breakdown_low:.2f}"
                    action_text = f"🎯 Action: Waiting for Retest to Lower EMA (Bounce >= 2 candles)"
                elif self.short_stage == 2:
                    pos_status = f"🎯 SELL REVERSAL: Retest Done ✓ [Armed for Trigger]"
                    action_text = f"🎯 Action: Waiting for 5m candle body close below ₹{self.breakdown_low:.2f} to SELL"
                else:
                    pos_status = (
                        f"⏳ Scanning Reversal Conditions (Need Prior Trend >= {TREND_MIN_RATIO:.0f}%):\n"
                        f"       • Buy Setup  (Downtrend Purity) : {dt_quality:.1f}% {'[READY FOR BREAKOUT ✅]' if cond1_long_ok else '[Building Trend ⏳]'}\n"
                        f"       • Sell Setup (Uptrend Purity)   : {ut_quality:.1f}% {'[READY FOR BREAKDOWN ✅]' if cond1_short_ok else '[Building Trend ⏳]'}"
                    )
                    action_text = f"🎯 Action: Watching 5m candles for Clean Trend Exhaustion"

            print(f"\n╔══════════════════════════════════════════════════════════════════════════════════════")
            print(f"║ 🕒 System Time: {sys_time_str} | Candle Time: {bar_time_str} | Symbol: {SYMBOL}")
            print(f"║ 📊 Current Price: ₹{curr['close']:.2f} | 20 EMA: ₹{curr['ema20']:.2f} | 50 EMA: ₹{curr['ema50']:.2f}")
            print(f"║ 📌 State: {pos_status}")
            print(f"║ {action_text}")
            print(f"╚══════════════════════════════════════════════════════════════════════════════════════\n")

        # =====================================================================
        # 1. POSITION MANAGEMENT & EXITS (ON BAR CLOSE)
        # =====================================================================
        if self.position == 1:
            if USE_TRAIL and curr["close"] < curr["ema20"] and not is_eod:
                logger.info(f"[{sys_time_str}] 📉 TRAIL EXIT (Long): Close ₹{curr['close']:.2f} < 20EMA ₹{curr['ema20']:.2f}")
                self.place_order("SELL", comment="Trail 20EMA Exit ▼")
                self.position = 0
            elif is_eod:
                logger.info(f"[{sys_time_str}] 🕐 EOD AUTO SQUARE-OFF (Long)")
                self.place_order("SELL", comment="EOD Exit 🕐")
                self.position = 0

        elif self.position == -1:
            if USE_TRAIL and curr["close"] > curr["ema20"] and not is_eod:
                logger.info(f"[{sys_time_str}] 📈 TRAIL EXIT (Short): Close ₹{curr['close']:.2f} > 20EMA ₹{curr['ema20']:.2f}")
                self.place_order("BUY", comment="Trail 20EMA Exit ▲")
                self.position = 0
            elif is_eod:
                logger.info(f"[{sys_time_str}] 🕐 EOD AUTO SQUARE-OFF (Short)")
                self.place_order("BUY", comment="EOD Exit 🕐")
                self.position = 0

        # =====================================================================
        # 2. LONG SEQUENTIAL FLOW (BUY)
        # =====================================================================
        if allow_long and self.position == 0:
            # ────────── STAGE 0: Waiting for Condition 1 (Trend) & Condition 2 (Breakout) ──────────
            if self.long_stage == 0:
                prev_below_top = prev["close"] < max(prev["ema20"], prev["ema50"])
                curr_above_top = curr["close"] > curr["ema_top"]
                is_bullish = curr["close"] > curr["open"]

                if cond1_long_ok and prev_below_top and curr_above_top and is_bullish and not is_eod:
                    # Condition 1 & 2 Fulfilled!
                    self.long_stage = 1
                    self.breakout_high = curr["high"]
                    self.breakout_bar_l = curr_idx
                    self.retest_swing_low = curr["low"]
                    self.long_close_below_count = 0
                    self.short_stage = 0
                    logger.info(f"\n[{sys_time_str}] ✅ [BUY Step 1 & 2 PASSED]: 12-Bar Downtrend Quality ({dt_quality:.0f}%) -> Breakout High Marked: ₹{self.breakout_high:.2f}")
                    logger.info(f"[{sys_time_str}] ⏳ Waiting for Condition 3 (Retest to 20/50 EMA with min 2 bars gap)...")

            # ────────── STAGE 1 & 2: Retest / Trigger Phase ──────────
            elif self.long_stage in [1, 2]:
                bars_since_l = curr_idx - self.breakout_bar_l
                self.retest_swing_low = min(self.retest_swing_low, curr["low"])

                # Check if candle closes below lower EMA (EMA Bottom)
                if curr["close"] < curr["ema_bot"]:
                    self.long_close_below_count += 1
                else:
                    self.long_close_below_count = 0

                # Invalidation Rule: Agar 1 se zyada candle (>= 2 candles) EMA ke neeche chali gayi -> Invalid
                if self.long_close_below_count > 1:
                    logger.info(f"[{sys_time_str}] ❌ BUY Setup Invalidated: More than 1 candle closed below EMAs ({self.long_close_below_count} candles). Waiting for new breakout...")
                    self.long_stage = 0
                    self.breakout_high = None
                    self.long_close_below_count = 0

                elif self.long_stage == 1:
                    # Retest Condition: low touches/goes below upper EMA
                    if bars_since_l >= MIN_RETEST_GAP and curr["low"] <= curr["ema_top"] and curr["close"] >= (curr["ema_bot"] - 5.0):
                        self.long_stage = 2
                        logger.info(f"\n[{sys_time_str}] ✅ [BUY Step 3 RETEST CONFIRMED]: Price pulled back to EMA (Gap: {bars_since_l} bars).")
                        logger.info(f"[{sys_time_str}] 🎯 ARMED FOR TRIGGER: Waiting for candle body close above Marked High ₹{self.breakout_high:.2f}")

                    # Invalidation on timeout or far cross
                    if curr["close"] < (curr["ema_bot"] - INVALIDATE_PTS) or bars_since_l > MAX_WAIT_BARS or is_eod:
                        logger.info(f"[{sys_time_str}] ❌ BUY Setup Invalidated / Timed out. Resetting to Step 1.")
                        self.long_stage = 0
                        self.breakout_high = None

                elif self.long_stage == 2:
                    # Final Trigger: Close above marked breakout high
                    if curr["close"] > self.breakout_high and curr["close"] > curr["open"] and not is_eod:
                        self.current_sl = self.retest_swing_low - SL_BUFFER
                        self.entry_price = curr["close"]
                        self.position = 1
                        logger.info(f"\n[{sys_time_str}] 🚀 [ALL 3 CONDITIONS SATISFIED] -> BUY ORDER TRIGGERED!")
                        logger.info(f"[{sys_time_str}] 🟢 ENTRY: ₹{self.entry_price:.2f} | INITIAL SL: ₹{self.current_sl:.2f} | TRAILING: Active on 20EMA")
                        self.place_order("BUY", comment=f"BUY ▲ SL:{self.current_sl:.2f}")

                        self.long_stage = 0
                        self.breakout_high = None

                    # Invalidation on timeout or far cross
                    if curr["close"] < (curr["ema_bot"] - INVALIDATE_PTS) or bars_since_l > MAX_WAIT_BARS or is_eod:
                        logger.info(f"[{sys_time_str}] ❌ BUY Trigger Timed out / Invalidated. Resetting to Step 1.")
                        self.long_stage = 0
                        self.breakout_high = None

        # =====================================================================
        # 3. SHORT SEQUENTIAL FLOW (SELL)
        # =====================================================================
        if allow_short and self.position == 0:
            # ────────── STAGE 0: Waiting for Condition 1 (Trend) & Condition 2 (Breakdown) ──────────
            if self.short_stage == 0:
                prev_above_bot = prev["close"] > min(prev["ema20"], prev["ema50"])
                curr_below_bot = curr["close"] < curr["ema_bot"]
                is_bearish = curr["close"] < curr["open"]

                if cond1_short_ok and prev_above_bot and curr_below_bot and is_bearish and not is_eod:
                    # Condition 1 & 2 Fulfilled!
                    self.short_stage = 1
                    self.breakdown_low = curr["low"]
                    self.breakout_bar_s = curr_idx
                    self.retest_swing_high = curr["high"]
                    self.short_close_above_count = 0
                    self.long_stage = 0
                    logger.info(f"\n[{sys_time_str}] ✅ [SELL Step 1 & 2 PASSED]: 12-Bar Uptrend Quality ({ut_quality:.0f}%) -> Breakdown Low Marked: ₹{self.breakdown_low:.2f}")
                    logger.info(f"[{sys_time_str}] ⏳ Waiting for Condition 3 (Retest to 20/50 EMA with min 2 bars gap)...")

            # ────────── STAGE 1 & 2: Retest / Trigger Phase ──────────
            elif self.short_stage in [1, 2]:
                bars_since_s = curr_idx - self.breakout_bar_s
                self.retest_swing_high = max(self.retest_swing_high, curr["high"])

                # Check if candle closes above upper EMA (EMA Top)
                if curr["close"] > curr["ema_top"]:
                    self.short_close_above_count += 1
                else:
                    self.short_close_above_count = 0

                # Invalidation Rule: Agar 1 se zyada candle (>= 2 candles) EMA ke upar chali gayi -> Invalid
                if self.short_close_above_count > 1:
                    logger.info(f"[{sys_time_str}] ❌ SELL Setup Invalidated: More than 1 candle closed above EMAs ({self.short_close_above_count} candles). Waiting for new breakdown...")
                    self.short_stage = 0
                    self.breakdown_low = None
                    self.short_close_above_count = 0

                elif self.short_stage == 1:
                    # Retest Condition: high touches/goes above lower EMA
                    if bars_since_s >= MIN_RETEST_GAP and curr["high"] >= curr["ema_bot"] and curr["close"] <= (curr["ema_top"] + 5.0):
                        self.short_stage = 2
                        logger.info(f"\n[{sys_time_str}] ✅ [SELL Step 3 RETEST CONFIRMED]: Price bounced back to EMA (Gap: {bars_since_s} bars).")
                        logger.info(f"[{sys_time_str}] 🎯 ARMED FOR TRIGGER: Waiting for candle body close below Marked Low ₹{self.breakdown_low:.2f}")

                    # Invalidation on timeout or far cross
                    if curr["close"] > (curr["ema_top"] + INVALIDATE_PTS) or bars_since_s > MAX_WAIT_BARS or is_eod:
                        logger.info(f"[{sys_time_str}] ❌ SELL Setup Invalidated / Timed out. Resetting to Step 1.")
                        self.short_stage = 0
                        self.breakdown_low = None

                elif self.short_stage == 2:
                    # Final Trigger: Close below marked breakdown low
                    if curr["close"] < self.breakdown_low and curr["close"] < curr["open"] and not is_eod:
                        self.current_sl = self.retest_swing_high + SL_BUFFER
                        self.entry_price = curr["close"]
                        self.position = -1
                        logger.info(f"\n[{sys_time_str}] 🚀 [ALL 3 CONDITIONS SATISFIED] -> SELL ORDER TRIGGERED!")
                        logger.info(f"[{sys_time_str}] 🔴 ENTRY: ₹{self.entry_price:.2f} | INITIAL SL: ₹{self.current_sl:.2f} | TRAILING: Active on 20EMA")
                        self.place_order("SELL", comment=f"SELL ▼ SL:{self.current_sl:.2f}")

                        self.short_stage = 0
                        self.breakdown_low = None

                    # Invalidation on timeout or far cross
                    if curr["close"] > (curr["ema_top"] + INVALIDATE_PTS) or bars_since_s > MAX_WAIT_BARS or is_eod:
                        logger.info(f"[{sys_time_str}] ❌ SELL Trigger Timed out / Invalidated. Resetting to Step 1.")
                        self.short_stage = 0
                        self.breakdown_low = None


def run_live_bot():
    """Main live loop to fetch live quotes and historical candles."""
    bot = CrudeSequentialStrategy()
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    logger.info(f"[{ts_now}] ⚡ Starting Crude Oil Sequential Reversal Engine on {EXCHANGE}:{SYMBOL} ({INTERVAL})...")
    logger.info(f"[{ts_now}] 📋 Sequential Pipeline: [Cond 1: Trend] -> [Cond 2: Retest] -> [Cond 3: Trigger]")

    last_candle_sync = 0.0
    session = requests.Session()
    conn_warned = False

    while True:
        try:
            current_time = time.time()
            
            # 1. Real-time Live Quote / Tick check every 2.5s (prevents broker 10 req/s rate-limit queue)
            quote_url = f"{OPENALGO_HOST}/api/v1/quotes"
            q_resp = session.post(quote_url, json={"apikey": API_KEY, "symbol": SYMBOL, "exchange": EXCHANGE}, timeout=8)
            if q_resp.status_code == 200:
                if conn_warned:
                    logger.info("🟢 Connection to OpenAlgo server restored!")
                    conn_warned = False
                q_data = q_resp.json().get("data", {})
                ltp = float(q_data.get("ltp") or 0.0)
                if ltp > 0:
                    bot.on_tick(ltp)

            # 2. Sync full 5m historical candles every 15 seconds
            if current_time - last_candle_sync >= 15.0:
                last_candle_sync = current_time
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                start_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
                
                hist_url = f"{OPENALGO_HOST}/api/v1/history"
                payload = {
                    "apikey": API_KEY,
                    "symbol": SYMBOL,
                    "exchange": EXCHANGE,
                    "interval": INTERVAL,
                    "start_date": start_date,
                    "end_date": today
                }
                resp = session.post(hist_url, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    if data:
                        df = pd.DataFrame(data)
                        bot.on_bar_close(df)

        except requests.exceptions.Timeout:
            # Broker network lag or rate limit queue — continue silently without crashing
            time.sleep(1)
            continue
        except requests.exceptions.ConnectionError:
            if not conn_warned:
                ts_now = datetime.now().strftime("%I:%M:%S %p")
                logger.warning(f"[{ts_now}] ⚠️ OpenAlgo server unreachable on port 5000. Retrying in background...")
                conn_warned = True
            time.sleep(2)
            continue
        except Exception as e:
            ts_now = datetime.now().strftime("%I:%M:%S %p")
            logger.error(f"[{ts_now}] Error in live loop: {e}")

        # 2-second safe interval between ticks
        time.sleep(2)


if __name__ == "__main__":
    try:
        run_live_bot()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
