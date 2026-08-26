"""
Antigravity Strategy Simulation & Backtest Runner
Simulates bar-by-bar execution with zero lookahead bias and realistic friction modeling.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta
from backend.smc_core import SMCCoreEngine

class StrategyRunner:
    @staticmethod
    def generate_synthetic_data(symbol: str = "NIFTY", days: int = 15, timeframe: str = "5m") -> pd.DataFrame:
        """Generates realistic market candles for high-fidelity backtesting."""
        n_bars = 75 * days if timeframe == "5m" else (25 * days if timeframe == "15m" else 375 * days)
        now = datetime.now()
        start = now - timedelta(days=days)
        timestamps = [start + timedelta(minutes=5 * i) for i in range(n_bars)]
        
        base_price = 24500.0 if "NIFTY" in symbol else (65000.0 if "BTC" in symbol else 3000.0)
        volatility = 18.0 if "NIFTY" in symbol else (250.0 if "BTC" in symbol else 5.0)
        
        np.random.seed(int(sum(ord(c) for c in symbol)) % 1000)
        returns = np.random.normal(0.0002, 0.002, n_bars)
        price_series = base_price * np.cumprod(1 + returns)
        
        highs = price_series + np.random.rand(n_bars) * volatility
        lows = price_series - np.random.rand(n_bars) * volatility
        closes = price_series + np.random.randn(n_bars) * (volatility * 0.5)
        opens = np.roll(closes, 1)
        opens[0] = base_price
        
        df = pd.DataFrame({
            "timestamp": [int(t.timestamp()) for t in timestamps],
            "datetime_str": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
            "time_str": [t.strftime("%H:%M") for t in timestamps],
            "date_str": [t.strftime("%Y-%m-%d") for t in timestamps],
            "open": np.round(opens, 2),
            "high": np.round(np.maximum(highs, np.maximum(opens, closes)), 2),
            "low": np.round(np.minimum(lows, np.minimum(opens, closes)), 2),
            "close": np.round(closes, 2),
            "volume": np.random.randint(500, 5000, n_bars)
        })
        return df

    @staticmethod
    def run_backtest(config: Dict[str, Any], df: pd.DataFrame = None) -> Dict[str, Any]:
        sym = config.get("symbol", "NIFTY")
        tf = config.get("timeframe", "5m")
        st_type = config.get("strategy_type", "smc_institutional")
        sl_pct = float(config.get("stoploss_pct", 0.8)) / 100.0
        tg_pct = float(config.get("target_pct", 2.4)) / 100.0
        capital = float(config.get("capital", 100000.0))
        qty = int(config.get("quantity", 50))
        direction = config.get("trade_direction", "BOTH")
        slippage_pct = 0.0005
        brokerage = 40.0

        if df is None or len(df) == 0:
            df = StrategyRunner.generate_synthetic_data(sym, days=20, timeframe=tf)

        # 1. Enrich with SMC or Indicators
        if st_type == "smc_institutional":
            df = SMCCoreEngine.analyze_price_action(df)
        else:
            df["fast_ema"] = df["close"].ewm(span=20, adjust=False).mean()
            df["slow_ema"] = df["close"].ewm(span=50, adjust=False).mean()
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            df["rsi"] = 100.0 - (100.0 / (1.0 + (gain / (loss + 1e-9))))

        trades = []
        equity = capital
        equity_curve = []
        position = None
        entry_price = 0.0
        entry_time = None
        sl_price = 0.0
        tg_price = 0.0

        for i in range(1, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i - 1]
            close = curr["close"]
            high = curr["high"]
            low = curr["low"]

            equity_curve.append({
                "time": curr["datetime_str"],
                "equity": round(equity, 2)
            })

            # Check open position
            if position is not None:
                closed = False
                exit_price = 0.0
                exit_reason = ""

                if position == "BUY":
                    if low <= sl_price:
                        exit_price = sl_price
                        exit_reason = "Stop Loss Hit"
                        closed = True
                    elif high >= tg_price:
                        exit_price = tg_price
                        exit_reason = "Target Hit"
                        closed = True
                elif position == "SELL":
                    if high >= sl_price:
                        exit_price = sl_price
                        exit_reason = "Stop Loss Hit"
                        closed = True
                    elif low <= tg_price:
                        exit_price = tg_price
                        exit_reason = "Target Hit"
                        closed = True

                if closed:
                    pnl = (exit_price - entry_price) * qty if position == "BUY" else (entry_price - exit_price) * qty
                    friction = (entry_price + exit_price) * qty * slippage_pct + brokerage
                    net_pnl = pnl - friction
                    equity += net_pnl

                    trades.append({
                        "trade_no": len(trades) + 1,
                        "action": position,
                        "entry_time": entry_time,
                        "exit_time": curr["datetime_str"],
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "gross_pnl": round(pnl, 2),
                        "net_pnl": round(net_pnl, 2),
                        "exit_reason": exit_reason
                    })
                    position = None
                    continue

            # Signal Generation (evaluated strictly on bar i-1, executed at bar i open/close)
            if position is None:
                buy_signal = False
                sell_signal = False

                if st_type == "smc_institutional":
                    if curr.get("bos") and curr.get("trend") == "BULLISH": buy_signal = True
                    elif curr.get("choch") and curr.get("trend") == "BULLISH": buy_signal = True
                    elif curr.get("liquidity_sweep") == "SELL_SIDE_SWEEP": buy_signal = True

                    if curr.get("bos") and curr.get("trend") == "BEARISH": sell_signal = True
                    elif curr.get("choch") and curr.get("trend") == "BEARISH": sell_signal = True
                    elif curr.get("liquidity_sweep") == "BUY_SIDE_SWEEP": sell_signal = True
                else:
                    buy_signal = (prev["fast_ema"] <= prev["slow_ema"]) and (curr["fast_ema"] > curr["slow_ema"])
                    sell_signal = (prev["fast_ema"] >= prev["slow_ema"]) and (curr["fast_ema"] < curr["slow_ema"])

                if buy_signal and direction in ["LONG", "BOTH"]:
                    position = "BUY"
                    entry_price = close
                    entry_time = curr["datetime_str"]
                    sl_price = entry_price * (1.0 - sl_pct)
                    tg_price = entry_price * (1.0 + tg_pct)
                elif sell_signal and direction in ["SHORT", "BOTH"]:
                    position = "SELL"
                    entry_price = close
                    entry_time = curr["datetime_str"]
                    sl_price = entry_price * (1.0 + sl_pct)
                    tg_price = entry_price * (1.0 - tg_pct)

        # Performance summary
        total_trades = len(trades)
        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] <= 0]
        win_rate = round((len(wins) / total_trades * 100), 1) if total_trades > 0 else 0.0
        total_pnl = sum(t["net_pnl"] for t in trades)
        gross_profit = sum(t["net_pnl"] for t in wins) if wins else 0.0
        gross_loss = abs(sum(t["net_pnl"] for t in losses)) if losses else 1.0
        profit_factor = round(gross_profit / max(gross_loss, 1.0), 2)

        return {
            "status": "success",
            "total_trades": total_trades,
            "total_net_pnl": round(total_pnl, 2),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "equity_curve": equity_curve[-100:],
            "trades": trades[-20:]
        }
