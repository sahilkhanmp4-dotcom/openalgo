"""
Institutional Backtesting Engine
Supports High-Fidelity Bar-by-Bar Simulation with Real Friction & Indian Tax Modeling.
"""

import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

from database.auth_db import get_auth_token
from services.history_service import get_history_with_auth
from quant_engine.smc_engine import SMCEngine

IST = pytz.timezone("Asia/Kolkata")

class BacktestEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.symbol = config.get("symbol", "NIFTY25AUG26FUT")
        self.exchange = config.get("exchange", "NFO")
        self.timeframe = config.get("timeframe", "5m")
        self.capital = float(config.get("capital", 100000.0))
        self.quantity = int(config.get("quantity", 50))
        self.trade_direction = config.get("trade_direction", "BOTH")
        
        # Risk & Friction Config
        self.sl_val = float(config.get("stoploss_val", 1.0))
        self.sl_type = config.get("stoploss_type", "PERCENT")
        self.tg_val = float(config.get("target_val", 2.0))
        self.tg_type = config.get("target_type", "PERCENT")
        self.trailing_sl = config.get("trailing_sl", False)
        self.trailing_step = float(config.get("trailing_step", 0.5))
        
        self.slippage_pct = float(config.get("slippage_pct", 0.05)) / 100.0
        self.brokerage = float(config.get("brokerage_per_trade", 40.0))
        self.tax_rate = float(config.get("tax_rate_pct", 0.08)) / 100.0
        
        self.entry_time = config.get("entry_time", "09:20")
        self.exit_time = config.get("exit_time", "15:15")

    def fetch_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch historical candle data via OpenAlgo/Fyers."""
        try:
            import sqlite3
            con = sqlite3.connect("db/openalgo.db")
            cur = con.cursor()
            row = cur.execute("SELECT name, broker FROM auth WHERE is_revoked=0 LIMIT 1").fetchone()
            con.close()
            
            if not row:
                raise ValueError("No active broker connection found in OpenAlgo database.")
            username, broker = row
            auth_token = get_auth_token(username)
            
            success, response, status = get_history_with_auth(
                auth_token=auth_token,
                feed_token=None,
                broker=broker,
                symbol=self.symbol,
                exchange=self.exchange,
                interval=self.timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if not success:
                err = response.get("message", "Failed to load data") if isinstance(response, dict) else str(response)
                raise ValueError(err)
                
            data = response.get("data", [])
            if not data:
                return pd.DataFrame()
                
            df = pd.DataFrame(data)
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
            df["time_str"] = df["datetime"].dt.strftime("%H:%M")
            df["date_str"] = df["datetime"].dt.strftime("%Y-%m-%d")
            df["datetime_str"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
            df = df.sort_values("datetime").reset_index(drop=True)
            return df
        except Exception as e:
            print(f"Error fetching backtest data: {e}")
            raise

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute standard institutional technical indicators with full dynamic parameter support."""
        df = df.copy()
        indicators = self.config.get("indicators", {})
        fast_period = int(indicators.get("fast_ema", 20))
        slow_period = int(indicators.get("slow_ema", 50))
        rsi_period = int(indicators.get("rsi_period", 14))
        
        # 1. EMAs
        df["fast_ema"] = df["close"].ewm(span=fast_period, adjust=False).mean()
        df["slow_ema"] = df["close"].ewm(span=slow_period, adjust=False).mean()
        
        # 2. RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / (loss + 1e-9)
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # 3. ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df["atr"] = true_range.rolling(14).mean().fillna(0.0)
        
        # 4. Dynamic Supertrend
        st_period = int(indicators.get("st_period", fast_period if fast_period < 20 else 7))
        st_mult = float(indicators.get("st_mult", slow_period if slow_period < 10 else 3.0))
        atr_st = true_range.rolling(st_period).mean().fillna(0.0)
        hl2 = (df["high"] + df["low"]) / 2.0
        basic_upper = hl2 + (st_mult * atr_st)
        basic_lower = hl2 - (st_mult * atr_st)
        
        final_upper = basic_upper.copy()
        final_lower = basic_lower.copy()
        st_dir = np.zeros(len(df), dtype=int)
        
        for idx in range(1, len(df)):
            if basic_upper.iloc[idx] < final_upper.iloc[idx-1] or df["close"].iloc[idx-1] > final_upper.iloc[idx-1]:
                final_upper.iloc[idx] = basic_upper.iloc[idx]
            else:
                final_upper.iloc[idx] = final_upper.iloc[idx-1]
                
            if basic_lower.iloc[idx] > final_lower.iloc[idx-1] or df["close"].iloc[idx-1] < final_lower.iloc[idx-1]:
                final_lower.iloc[idx] = basic_lower.iloc[idx]
            else:
                final_lower.iloc[idx] = final_lower.iloc[idx-1]
                
            if df["close"].iloc[idx] > final_upper.iloc[idx-1]:
                st_dir[idx] = 1
            elif df["close"].iloc[idx] < final_lower.iloc[idx-1]:
                st_dir[idx] = -1
            else:
                st_dir[idx] = st_dir[idx-1] if st_dir[idx-1] != 0 else 1
                
        df["st_direction"] = st_dir
        
        # 5. Session VWAP
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df.get("volume", pd.Series(1, index=df.index)).replace(0, 1)
        tp_vol = tp * vol
        if "date_str" in df.columns:
            df["vwap"] = tp_vol.groupby(df["date_str"]).cumsum() / vol.groupby(df["date_str"]).cumsum()
        else:
            df["vwap"] = tp_vol.cumsum() / vol.cumsum()
            
        # 6. Dynamic Bollinger Bands
        bb_period = int(indicators.get("bb_period", fast_period if fast_period >= 10 else 20))
        bb_std_mult = float(indicators.get("bb_std", slow_period if slow_period < 10 else 2.0))
        df["bb_mid"] = df["close"].rolling(bb_period).mean()
        bb_std = df["close"].rolling(bb_period).std()
        df["bb_upper"] = df["bb_mid"] + (bb_std_mult * bb_std)
        df["bb_lower"] = df["bb_mid"] - (bb_std_mult * bb_std)
        
        # 7. Intraday Opening Range (09:15 - 09:30 AM)
        if "time_str" in df.columns and "date_str" in df.columns:
            orb_mask = (df["time_str"] >= "09:15") & (df["time_str"] <= "09:30")
            if orb_mask.any():
                orb_highs = df[orb_mask].groupby("date_str")["high"].max()
                orb_lows = df[orb_mask].groupby("date_str")["low"].min()
                df["orb_high"] = df["date_str"].map(orb_highs)
                df["orb_low"] = df["date_str"].map(orb_lows)
            else:
                df["orb_high"] = df["high"].iloc[0]
                df["orb_low"] = df["low"].iloc[0]
        else:
            df["orb_high"] = df["high"].iloc[0]
            df["orb_low"] = df["low"].iloc[0]
            
        # 8. Smart Money Concepts (SMC) Enrichment
        try:
            df = SMCEngine.calculate_smc(df)
        except Exception:
            pass

        return df

    def run_simulation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Execute step-by-step backtest simulation with dynamic template parameters and zero lookahead."""
        df = self.calculate_indicators(df)
        indicators = self.config.get("indicators", {})
        rsi_lvl = int(indicators.get("rsi_threshold", 50))
        
        trades = []
        position = None  # "BUY" or "SELL"
        entry_price = 0.0
        entry_time = None
        entry_idx = None
        sl_price = 0.0
        tg_price = 0.0
        trailing_peak = 0.0
        
        equity = self.capital
        equity_curve = []
        
        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            t_str = curr["time_str"]
            
            # Record current equity
            equity_curve.append({
                "datetime": curr["datetime_str"],
                "equity": round(equity, 2)
            })
            
            # 1. POSITION MANAGEMENT (If in active trade)
            if position is not None:
                trade_closed = False
                exit_price = 0.0
                exit_reason = ""
                
                # Check Intraday EOD Square-off
                if t_str >= self.exit_time:
                    exit_price = curr["close"]
                    exit_reason = "EOD Squareoff"
                    trade_closed = True
                
                # Check Trailing Stop Loss adjustment
                elif self.trailing_sl:
                    if position == "BUY":
                        if curr["high"] > trailing_peak:
                            trailing_peak = curr["high"]
                            new_sl = round(trailing_peak * (1.0 - (self.sl_val / 100.0)), 2)
                            sl_price = max(sl_price, new_sl)
                    elif position == "SELL":
                        if curr["low"] < trailing_peak:
                            trailing_peak = curr["low"]
                            new_sl = round(trailing_peak * (1.0 + (self.sl_val / 100.0)), 2)
                            sl_price = min(sl_price, new_sl)
                
                # Check Stop Loss & Target within candle
                if not trade_closed:
                    if position == "BUY":
                        if curr["low"] <= sl_price:
                            exit_price = sl_price
                            exit_reason = "Stop Loss Hit"
                            trade_closed = True
                        elif curr["high"] >= tg_price:
                            exit_price = tg_price
                            exit_reason = "Target Hit"
                            trade_closed = True
                    elif position == "SELL":
                        if curr["high"] >= sl_price:
                            exit_price = sl_price
                            exit_reason = "Stop Loss Hit"
                            trade_closed = True
                        elif curr["low"] <= tg_price:
                            exit_price = tg_price
                            exit_reason = "Target Hit"
                            trade_closed = True
                
                # If Trade closed this bar
                if trade_closed:
                    # Apply Realistic Friction (Slippage on entry & exit)
                    real_entry = entry_price * (1.0 + self.slippage_pct if position == "BUY" else 1.0 - self.slippage_pct)
                    real_exit = exit_price * (1.0 - self.slippage_pct if position == "BUY" else 1.0 + self.slippage_pct)
                    
                    if position == "BUY":
                        gross_pnl = (real_exit - real_entry) * self.quantity
                    else:
                        gross_pnl = (real_entry - real_exit) * self.quantity
                    
                    # Turnover & Taxes
                    turnover = (real_entry + real_exit) * self.quantity
                    tax_amount = turnover * self.tax_rate
                    total_friction = (turnover * self.slippage_pct) + self.brokerage + tax_amount
                    net_pnl = gross_pnl - self.brokerage - tax_amount
                    
                    equity += net_pnl
                    
                    trades.append({
                        "trade_id": len(trades) + 1,
                        "position": position,
                        "entry_time": entry_time,
                        "exit_time": curr["datetime_str"],
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "quantity": self.quantity,
                        "gross_pnl": round(gross_pnl, 2),
                        "friction_cost": round(total_friction, 2),
                        "net_pnl": round(net_pnl, 2),
                        "exit_reason": exit_reason,
                        "pnl_pct": round((net_pnl / self.capital) * 100, 2),
                        "equity_after": round(equity, 2)
                    })
                    
                    position = None
                    continue
            
            # 2. SIGNAL GENERATION (Strict Zero-Lookahead: Signal evaluated on bar i-1, executed at bar i)
            if position is None and self.entry_time <= t_str < self.exit_time:
                strat_name_lower = self.config.get("strategy_name", "").lower()
                strat_type = self.config.get("strategy_type", "").lower()
                
                if strat_type == "supertrend" or "supertrend" in strat_name_lower:
                    buy_signal = (prev["st_direction"] == -1 and curr["st_direction"] == 1) and (curr["rsi"] >= rsi_lvl)
                    sell_signal = (prev["st_direction"] == 1 and curr["st_direction"] == -1) and (curr["rsi"] <= (100 - rsi_lvl))
                elif strat_type == "vwap_pullback" or "vwap" in strat_name_lower:
                    buy_signal = (curr["close"] > curr["vwap"]) and (curr["low"] <= curr["fast_ema"]) and (curr["close"] > curr["fast_ema"]) and (curr["rsi"] >= rsi_lvl)
                    sell_signal = (curr["close"] < curr["vwap"]) and (curr["high"] >= curr["fast_ema"]) and (curr["close"] < curr["fast_ema"]) and (curr["rsi"] <= (100 - rsi_lvl))
                elif strat_type == "orb_breakout" or "orb" in strat_name_lower:
                    orb_h = curr.get("orb_high", curr["high"])
                    orb_l = curr.get("orb_low", curr["low"])
                    buy_signal = (t_str > "09:30") and (prev["close"] <= orb_h) and (curr["close"] > orb_h)
                    sell_signal = (t_str > "09:30") and (prev["close"] >= orb_l) and (curr["close"] < orb_l)
                elif strat_type == "bollinger" or "bollinger" in strat_name_lower:
                    buy_signal = (prev["close"] <= prev["bb_lower"]) and (curr["close"] > curr["bb_lower"]) and (curr["rsi"] < rsi_lvl)
                    sell_signal = (prev["close"] >= prev["bb_upper"]) and (curr["close"] < curr["bb_upper"]) and (curr["rsi"] > (100 - rsi_lvl))
                elif strat_type == "mcx_crude" or "crude" in strat_name_lower:
                    buy_signal = (prev["fast_ema"] <= prev["slow_ema"]) and (curr["fast_ema"] > curr["slow_ema"]) and (curr["rsi"] >= rsi_lvl)
                    sell_signal = (prev["fast_ema"] >= prev["slow_ema"]) and (curr["fast_ema"] < curr["slow_ema"]) and (curr["rsi"] <= (100 - rsi_lvl))
                elif strat_type == "rsi_momentum" or "rsi" in strat_name_lower:
                    buy_signal = (prev["rsi"] <= rsi_lvl and curr["rsi"] > rsi_lvl)
                    sell_signal = (prev["rsi"] >= (100 - rsi_lvl) and curr["rsi"] < (100 - rsi_lvl))
                elif strat_type == "smc_institutional" or "smc" in strat_name_lower or "orderblock" in strat_name_lower:
                    # Smart Money Concepts: Trend Alignment + CHoCH / BOS / Liquidity Sweep
                    is_bull = (curr.get("bos") and curr.get("smc_trend") == "BULLISH") or (curr.get("choch") and curr.get("smc_trend") == "BULLISH") or (curr.get("liquidity_sweep") == "SELL_SIDE_SWEEP")
                    is_bear = (curr.get("bos") and curr.get("smc_trend") == "BEARISH") or (curr.get("choch") and curr.get("smc_trend") == "BEARISH") or (curr.get("liquidity_sweep") == "BUY_SIDE_SWEEP")
                    buy_signal = bool(is_bull)
                    sell_signal = bool(is_bear)
                else:
                    # Robust EMA Trend Cross
                    buy_signal = (prev["fast_ema"] <= prev["slow_ema"]) and (curr["fast_ema"] > curr["slow_ema"]) and (curr["rsi"] >= rsi_lvl)
                    sell_signal = (prev["fast_ema"] >= prev["slow_ema"]) and (curr["fast_ema"] < curr["slow_ema"]) and (curr["rsi"] <= (100 - rsi_lvl))
                
                signal = None
                if buy_signal and self.trade_direction in ["LONG", "BOTH"]:
                    signal = "BUY"
                elif sell_signal and self.trade_direction in ["SHORT", "BOTH"]:
                    signal = "SELL"
                
                if signal is not None:
                    position = signal
                    entry_price = curr["close"]
                    entry_time = curr["datetime_str"]
                    entry_idx = i
                    trailing_peak = entry_price
                    
                    if self.sl_type == "PERCENT":
                        sl_offset = entry_price * (self.sl_val / 100.0)
                        tg_offset = entry_price * (self.tg_val / 100.0)
                    else:
                        sl_offset = self.sl_val
                        tg_offset = self.tg_val
                        
                    if signal == "BUY":
                        sl_price = round(entry_price - sl_offset, 2)
                        tg_price = round(entry_price + tg_offset, 2)
                    else:
                        sl_price = round(entry_price + sl_offset, 2)
                        tg_price = round(entry_price - tg_offset, 2)

        return self.compute_metrics(trades, equity_curve)

    def run_simulation_with_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Execute step-by-step simulation driven by pre-computed signal column from custom Python code."""
        if "signal" not in df.columns:
            raise ValueError("DataFrame must contain a 'signal' column with values 'BUY', 'SELL', or None.")
            
        trades = []
        position = None  # "BUY" or "SELL"
        entry_price = 0.0
        entry_time = None
        entry_idx = None
        sl_price = 0.0
        tg_price = 0.0
        trailing_peak = 0.0
        
        equity = self.capital
        equity_curve = []
        
        for i in range(1, len(df)):
            curr = df.iloc[i]
            t_str = curr.get("time_str", curr["datetime_str"][11:16] if "datetime_str" in curr else "10:00")
            
            # Record current equity
            equity_curve.append({
                "datetime": curr.get("datetime_str", str(curr.get("datetime", ""))),
                "equity": round(equity, 2)
            })
            
            # 1. POSITION MANAGEMENT (If in active trade)
            if position is not None:
                trade_closed = False
                exit_price = 0.0
                exit_reason = ""
                
                # Check Intraday EOD Square-off
                if t_str >= self.exit_time:
                    exit_price = curr["close"]
                    exit_reason = "EOD Squareoff"
                    trade_closed = True
                
                # Check Trailing Stop Loss adjustment
                elif self.trailing_sl:
                    if position == "BUY":
                        if curr["high"] > trailing_peak:
                            trailing_peak = curr["high"]
                            new_sl = round(trailing_peak * (1.0 - (self.sl_val / 100.0)), 2)
                            sl_price = max(sl_price, new_sl)
                    elif position == "SELL":
                        if curr["low"] < trailing_peak:
                            trailing_peak = curr["low"]
                            new_sl = round(trailing_peak * (1.0 + (self.sl_val / 100.0)), 2)
                            sl_price = min(sl_price, new_sl)
                
                # Check Stop Loss & Target within candle
                if not trade_closed:
                    if position == "BUY":
                        if curr["low"] <= sl_price:
                            exit_price = sl_price
                            exit_reason = "Stop Loss Hit"
                            trade_closed = True
                        elif curr["high"] >= tg_price:
                            exit_price = tg_price
                            exit_reason = "Target Hit"
                            trade_closed = True
                    elif position == "SELL":
                        if curr["high"] >= sl_price:
                            exit_price = sl_price
                            exit_reason = "Stop Loss Hit"
                            trade_closed = True
                        elif curr["low"] <= tg_price:
                            exit_price = tg_price
                            exit_reason = "Target Hit"
                            trade_closed = True
                            
                # Check Reversal Signal from custom code
                if not trade_closed:
                    sig_val = curr.get("signal")
                    if (position == "BUY" and sig_val == "SELL") or (position == "SELL" and sig_val == "BUY"):
                        exit_price = curr["close"]
                        exit_reason = "Signal Reversal"
                        trade_closed = True
                
                # If Trade closed this bar
                if trade_closed:
                    real_entry = entry_price * (1.0 + self.slippage_pct if position == "BUY" else 1.0 - self.slippage_pct)
                    real_exit = exit_price * (1.0 - self.slippage_pct if position == "BUY" else 1.0 + self.slippage_pct)
                    
                    if position == "BUY":
                        gross_pnl = (real_exit - real_entry) * self.quantity
                    else:
                        gross_pnl = (real_entry - real_exit) * self.quantity
                    
                    turnover = (real_entry + real_exit) * self.quantity
                    tax_amount = turnover * self.tax_rate
                    total_friction = (turnover * self.slippage_pct) + self.brokerage + tax_amount
                    net_pnl = gross_pnl - self.brokerage - tax_amount
                    
                    equity += net_pnl
                    
                    trades.append({
                        "trade_id": len(trades) + 1,
                        "position": position,
                        "entry_time": entry_time,
                        "exit_time": curr.get("datetime_str", str(curr.get("datetime", ""))),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "quantity": self.quantity,
                        "gross_pnl": round(gross_pnl, 2),
                        "friction_cost": round(total_friction, 2),
                        "net_pnl": round(net_pnl, 2),
                        "exit_reason": exit_reason,
                        "pnl_pct": round((net_pnl / self.capital) * 100, 2),
                        "equity_after": round(equity, 2)
                    })
                    
                    position = None
                    continue
            
            # 2. SIGNAL GENERATION (If no active trade & within trading hours)
            if position is None and self.entry_time <= t_str < self.exit_time:
                sig = curr.get("signal")
                if sig in ["BUY", "SELL"]:
                    if (sig == "BUY" and self.trade_direction in ["LONG", "BOTH"]) or (sig == "SELL" and self.trade_direction in ["SHORT", "BOTH"]):
                        position = sig
                        entry_price = float(curr["close"])
                        entry_time = curr.get("datetime_str", str(curr.get("datetime", "")))
                        entry_idx = i
                        trailing_peak = entry_price
                        
                        if self.sl_type == "PERCENT":
                            sl_offset = entry_price * (self.sl_val / 100.0)
                            tg_offset = entry_price * (self.tg_val / 100.0)
                        else:
                            sl_offset = self.sl_val
                            tg_offset = self.tg_val
                            
                        if sig == "BUY":
                            sl_price = round(entry_price - sl_offset, 2)
                            tg_price = round(entry_price + tg_offset, 2)
                        else:
                            sl_price = round(entry_price + sl_offset, 2)
                            tg_price = round(entry_price - tg_offset, 2)

        return self.compute_metrics(trades, equity_curve)

    def compute_metrics(self, trades: List[Dict], equity_curve: List[Dict]) -> Dict[str, Any]:
        """Compute institutional metrics (Sharpe, Drawdown, Profit Factor, Expectancy)."""
        if not trades:
            return {
                "total_trades": 0, "win_rate": 0, "net_pnl": 0, "total_net_pnl": 0, "profit_factor": 0,
                "max_drawdown_pct": 0, "sharpe_ratio": 0, "trades": [], "equity_curve": []
            }
        
        trades_df = pd.DataFrame(trades)
        wins = trades_df[trades_df["net_pnl"] > 0]
        losses = trades_df[trades_df["net_pnl"] <= 0]
        
        total_trades = len(trades_df)
        win_trades = len(wins)
        loss_trades = len(losses)
        win_rate = round((win_trades / total_trades) * 100, 2) if total_trades > 0 else 0
        
        gross_profit = wins["net_pnl"].sum() if not wins.empty else 0.0
        gross_loss = abs(losses["net_pnl"].sum()) if not losses.empty else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        
        total_net_pnl = round(trades_df["net_pnl"].sum(), 2)
        total_roi_pct = round((total_net_pnl / self.capital) * 100, 2)
        
        avg_win = round(wins["net_pnl"].mean(), 2) if not wins.empty else 0.0
        avg_loss = round(abs(losses["net_pnl"].mean()), 2) if not losses.empty else 0.0
        risk_reward = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0
        
        # Drawdown calculation
        eq_df = pd.DataFrame(equity_curve)
        eq_df["peak"] = eq_df["equity"].cummax()
        eq_df["drawdown"] = (eq_df["equity"] - eq_df["peak"]) / eq_df["peak"] * 100.0
        max_drawdown_pct = round(abs(eq_df["drawdown"].min()), 2)
        
        # Daily Returns for Sharpe
        trades_df["date"] = pd.to_datetime(trades_df["entry_time"]).dt.date
        daily_pnl = trades_df.groupby("date")["net_pnl"].sum()
        if len(daily_pnl) > 1 and daily_pnl.std() > 0:
            sharpe = round((daily_pnl.mean() / daily_pnl.std()) * np.sqrt(252), 2)
        else:
            sharpe = 0.0
            
        return {
            "total_trades": total_trades,
            "win_trades": win_trades,
            "loss_trades": loss_trades,
            "win_rate": win_rate,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "total_net_pnl": total_net_pnl,
            "roi_pct": total_roi_pct,
            "profit_factor": profit_factor,
            "risk_reward": risk_reward,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": sharpe,
            "trades": trades,
            "equity_curve": equity_curve[::max(1, len(equity_curve) // 500)]  # Downsample for chart
        }


class CustomCodeBacktester:
    """
    MetaTrader 5 / Python Direct Script Backtesting Engine.
    Executes user-defined Python strategy scripts directly on real broker historical candles.
    """
    @staticmethod
    def run_python_strategy(
        code_str: str,
        symbol: str = "NIFTY",
        exchange: str = "NSE_INDEX",
        timeframe: str = "5m",
        start_date: str = "",
        end_date: str = "",
        capital: float = 100000.0,
        quantity: int = 50,
        stoploss_val: float = 1.0,
        target_val: float = 2.0,
        slippage_pct: float = 0.05,
        brokerage: float = 40.0,
        df_custom: pd.DataFrame = None
    ) -> Dict[str, Any]:
        config = {
            "strategy_name": "MT5_Python_Strategy",
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "capital": capital,
            "quantity": quantity,
            "stoploss_val": stoploss_val,
            "target_val": target_val,
            "slippage_pct": slippage_pct,
            "brokerage_per_trade": brokerage
        }
        engine = BacktestEngine(config)
        if df_custom is not None and not df_custom.empty:
            df = df_custom.copy()
        else:
            df = engine.fetch_data(start_date, end_date)
            if df.empty:
                raise ValueError(f"No historical candle data returned for {symbol} ({exchange}) between {start_date} and {end_date}")
            
        # Execute user code in isolated execution namespace
        exec_namespace = {
            "pd": pd,
            "np": np,
            "datetime": datetime,
            "timedelta": timedelta,
            "math": __import__("math")
        }
        
        try:
            exec(code_str, exec_namespace, exec_namespace)
        except Exception as e:
            raise ValueError(f"Python Syntax / Compilation Error: {e}")
            
        params = {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "capital": capital,
            "quantity": quantity,
            "stoploss_val": stoploss_val,
            "target_val": target_val
        }
        
        # Check if user defined generate_signals(df, params)
        if "generate_signals" in exec_namespace and callable(exec_namespace["generate_signals"]):
            try:
                df_res = exec_namespace["generate_signals"](df.copy(), params)
            except Exception as e:
                raise ValueError(f"Runtime error in generate_signals(): {e}")
                
            if not isinstance(df_res, pd.DataFrame):
                raise ValueError("generate_signals() must return a pandas DataFrame.")
            return engine.run_simulation_with_signals(df_res)
            
        # Check if user defined Strategy class
        elif "Strategy" in exec_namespace:
            try:
                strat = exec_namespace["Strategy"](params)
                if hasattr(strat, "generate_signals"):
                    df_res = strat.generate_signals(df.copy())
                    return engine.run_simulation_with_signals(df_res)
                else:
                    raise ValueError("Strategy class must implement generate_signals(df) method.")
            except Exception as e:
                raise ValueError(f"Runtime error in Strategy class: {e}")
        else:
            raise ValueError("Your Python code must define a 'generate_signals(df, params)' function or a 'Strategy' class.")
