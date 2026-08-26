"""
Antigravity SMC & Pure Price Action Core Engine
Calculates Institutional Swings, BOS, CHoCH, Order Blocks, FVGs, and Liquidity Sweeps.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class SMCCoreEngine:
    @staticmethod
    def analyze_price_action(df: pd.DataFrame, swing_len: int = 3, fvg_min_pct: float = 0.05) -> pd.DataFrame:
        df = df.copy()
        n = len(df)
        if n < swing_len * 2 + 1:
            return df
            
        df["swing_high"] = False
        df["swing_low"] = False
        df["structure"] = None   # 'HH', 'HL', 'LH', 'LL'
        df["bos"] = False
        df["choch"] = False
        df["fvg_type"] = None    # 'BULLISH_FVG', 'BEARISH_FVG'
        df["order_block"] = None # 'BULLISH_OB', 'BEARISH_OB'
        df["liquidity_sweep"] = None # 'BUY_SIDE_SWEEP', 'SELL_SIDE_SWEEP'
        df["trend"] = "NEUTRAL"
        
        # 1. Swing Detection
        for i in range(swing_len, n - swing_len):
            high_win = df["high"].iloc[i - swing_len : i + swing_len + 1]
            low_win = df["low"].iloc[i - swing_len : i + swing_len + 1]
            if df["high"].iloc[i] == high_win.max():
                df.loc[df.index[i], "swing_high"] = True
            if df["low"].iloc[i] == low_win.min():
                df.loc[df.index[i], "swing_low"] = True

        # 2. Structure, BOS, CHoCH
        last_high, last_low = None, None
        prev_high, prev_low = None, None
        curr_trend = "NEUTRAL"

        for i in range(n):
            c = df["close"].iloc[i]
            h = df["high"].iloc[i]
            l = df["low"].iloc[i]

            if df["swing_high"].iloc[i]:
                prev_high = last_high
                last_high = h
                if prev_high is not None:
                    df.loc[df.index[i], "structure"] = "HH" if last_high > prev_high else "LH"

            if df["swing_low"].iloc[i]:
                prev_low = last_low
                last_low = l
                if prev_low is not None:
                    df.loc[df.index[i], "structure"] = "LL" if last_low < prev_low else "HL"

            # Bullish Break or Sweep
            if last_high is not None:
                if c > last_high:
                    if curr_trend == "BULLISH":
                        df.loc[df.index[i], "bos"] = True
                    else:
                        df.loc[df.index[i], "choch"] = True
                        curr_trend = "BULLISH"
                elif h > last_high and c <= last_high:
                    df.loc[df.index[i], "liquidity_sweep"] = "BUY_SIDE_SWEEP"

            # Bearish Break or Sweep
            if last_low is not None:
                if c < last_low:
                    if curr_trend == "BEARISH":
                        df.loc[df.index[i], "bos"] = True
                    else:
                        df.loc[df.index[i], "choch"] = True
                        curr_trend = "BEARISH"
                elif l < last_low and c >= last_low:
                    df.loc[df.index[i], "liquidity_sweep"] = "SELL_SIDE_SWEEP"

            df.loc[df.index[i], "trend"] = curr_trend

        # 3. FVGs
        for i in range(2, n):
            c1_h, c1_l = df["high"].iloc[i - 2], df["low"].iloc[i - 2]
            c3_h, c3_l = df["high"].iloc[i], df["low"].iloc[i]
            if c3_l > c1_h:
                gap = (c3_l - c1_h) / df["close"].iloc[i] * 100
                if gap >= fvg_min_pct:
                    df.loc[df.index[i - 1], "fvg_type"] = "BULLISH_FVG"
            elif c3_h < c1_l:
                gap = (c1_l - c3_h) / df["close"].iloc[i] * 100
                if gap >= fvg_min_pct:
                    df.loc[df.index[i - 1], "fvg_type"] = "BEARISH_FVG"

        # 4. Order Blocks
        for i in range(1, n - 1):
            if df["close"].iloc[i - 1] < df["open"].iloc[i - 1] and df["close"].iloc[i] > df["open"].iloc[i]:
                if df["close"].iloc[i] > df["high"].iloc[i - 1]:
                    df.loc[df.index[i - 1], "order_block"] = "BULLISH_OB"
            elif df["close"].iloc[i - 1] > df["open"].iloc[i - 1] and df["close"].iloc[i] < df["open"].iloc[i]:
                if df["close"].iloc[i] < df["low"].iloc[i - 1]:
                    df.loc[df.index[i - 1], "order_block"] = "BEARISH_OB"

        return df
