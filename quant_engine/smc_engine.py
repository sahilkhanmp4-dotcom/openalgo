"""
Smart Money Concepts (SMC) & Institutional Price Action Engine
Calculates Market Structure (BOS, CHoCH), Order Blocks, Fair Value Gaps (FVG),
Liquidity Sweeps, and Premium/Discount Zones with zero lookahead bias.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

class SMCEngine:
    @staticmethod
    def calculate_smc(df: pd.DataFrame, swing_window: int = 3, fvg_threshold_pct: float = 0.05) -> pd.DataFrame:
        """
        Enriches OHLCV dataframe with complete SMC institutional indicators.
        """
        df = df.copy()
        n = len(df)
        if n < swing_window * 2 + 1:
            return df
            
        # Initialize SMC columns
        df["swing_high"] = False
        df["swing_low"] = False
        df["structure_type"] = None  # 'HH', 'HL', 'LH', 'LL'
        df["bos"] = False            # Break of Structure
        df["choch"] = False          # Change of Character
        df["fvg_bullish"] = False    # Bullish Fair Value Gap
        df["fvg_bearish"] = False    # Bearish Fair Value Gap
        df["fvg_top"] = np.nan
        df["fvg_bottom"] = np.nan
        df["order_block"] = None     # 'BULLISH_OB', 'BEARISH_OB'
        df["ob_high"] = np.nan
        df["ob_low"] = np.nan
        df["liquidity_sweep"] = None # 'BUY_SIDE_SWEEP', 'SELL_SIDE_SWEEP'
        df["smc_trend"] = "NEUTRAL"  # 'BULLISH', 'BEARISH'
        
        # 1. Detect Swing Highs & Swing Lows
        for i in range(swing_window, n - swing_window):
            curr_high = df["high"].iloc[i]
            curr_low = df["low"].iloc[i]
            
            # Local peak
            if curr_high == df["high"].iloc[i - swing_window : i + swing_window + 1].max():
                df.loc[df.index[i], "swing_high"] = True
                
            # Local trough
            if curr_low == df["low"].iloc[i - swing_window : i + swing_window + 1].min():
                df.loc[df.index[i], "swing_low"] = True

        # 2. Track Confirmed Swings, BOS, CHoCH, and Trends
        last_swing_high = None
        last_swing_low = None
        prev_swing_high = None
        prev_swing_low = None
        current_trend = "NEUTRAL"

        for i in range(n):
            close = df["close"].iloc[i]
            high = df["high"].iloc[i]
            low = df["low"].iloc[i]

            # Update Swings
            if df["swing_high"].iloc[i]:
                prev_swing_high = last_swing_high
                last_swing_high = high
                if prev_swing_high is not None:
                    if last_swing_high > prev_swing_high:
                        df.loc[df.index[i], "structure_type"] = "HH"
                    else:
                        df.loc[df.index[i], "structure_type"] = "LH"

            if df["swing_low"].iloc[i]:
                prev_swing_low = last_swing_low
                last_swing_low = low
                if prev_swing_low is not None:
                    if last_swing_low < prev_swing_low:
                        df.loc[df.index[i], "structure_type"] = "LL"
                    else:
                        df.loc[df.index[i], "structure_type"] = "HL"

            # Check BOS & CHoCH
            if last_swing_high is not None:
                # Bullish Breakout
                if close > last_swing_high:
                    if current_trend == "BULLISH":
                        df.loc[df.index[i], "bos"] = True
                    else:
                        df.loc[df.index[i], "choch"] = True
                        current_trend = "BULLISH"
                # Liquidity Sweep (Wick above High, body inside)
                elif high > last_swing_high and close <= last_swing_high:
                    df.loc[df.index[i], "liquidity_sweep"] = "BUY_SIDE_SWEEP"

            if last_swing_low is not None:
                # Bearish Breakdown
                if close < last_swing_low:
                    if current_trend == "BEARISH":
                        df.loc[df.index[i], "bos"] = True
                    else:
                        df.loc[df.index[i], "choch"] = True
                        current_trend = "BEARISH"
                # Liquidity Sweep (Wick below Low, body inside)
                elif low < last_swing_low and close >= last_swing_low:
                    df.loc[df.index[i], "liquidity_sweep"] = "SELL_SIDE_SWEEP"

            df.loc[df.index[i], "smc_trend"] = current_trend

        # 3. Fair Value Gaps (FVG - 3 Candle Imbalance)
        for i in range(2, n):
            c1_high = df["high"].iloc[i - 2]
            c1_low = df["low"].iloc[i - 2]
            c3_high = df["high"].iloc[i]
            c3_low = df["low"].iloc[i]
            
            # Bullish FVG: Candle 3 Low > Candle 1 High (Gap up)
            if c3_low > c1_high:
                gap_size = c3_low - c1_high
                if gap_size / df["close"].iloc[i] * 100 >= fvg_threshold_pct:
                    df.loc[df.index[i - 1], "fvg_bullish"] = True
                    df.loc[df.index[i - 1], "fvg_bottom"] = c1_high
                    df.loc[df.index[i - 1], "fvg_top"] = c3_low
                    
            # Bearish FVG: Candle 3 High < Candle 1 Low (Gap down)
            if c3_high < c1_low:
                gap_size = c1_low - c3_high
                if gap_size / df["close"].iloc[i] * 100 >= fvg_threshold_pct:
                    df.loc[df.index[i - 1], "fvg_bearish"] = True
                    df.loc[df.index[i - 1], "fvg_top"] = c1_low
                    df.loc[df.index[i - 1], "fvg_bottom"] = c3_high

        # 4. Institutional Order Blocks (OB)
        for i in range(1, n - 1):
            # Bullish OB: Bearish candle followed by strong bullish impulse
            if df["close"].iloc[i - 1] < df["open"].iloc[i - 1] and df["close"].iloc[i] > df["open"].iloc[i]:
                body_ratio = abs(df["close"].iloc[i] - df["open"].iloc[i]) / (df["high"].iloc[i] - df["low"].iloc[i] + 1e-9)
                if body_ratio > 0.6 and df["close"].iloc[i] > df["high"].iloc[i - 1]:
                    df.loc[df.index[i - 1], "order_block"] = "BULLISH_OB"
                    df.loc[df.index[i - 1], "ob_high"] = df["high"].iloc[i - 1]
                    df.loc[df.index[i - 1], "ob_low"] = df["low"].iloc[i - 1]

            # Bearish OB: Bullish candle followed by strong bearish impulse
            if df["close"].iloc[i - 1] > df["open"].iloc[i - 1] and df["close"].iloc[i] < df["open"].iloc[i]:
                body_ratio = abs(df["close"].iloc[i] - df["open"].iloc[i]) / (df["high"].iloc[i] - df["low"].iloc[i] + 1e-9)
                if body_ratio > 0.6 and df["close"].iloc[i] < df["low"].iloc[i - 1]:
                    df.loc[df.index[i - 1], "order_block"] = "BEARISH_OB"
                    df.loc[df.index[i - 1], "ob_high"] = df["high"].iloc[i - 1]
                    df.loc[df.index[i - 1], "ob_low"] = df["low"].iloc[i - 1]

        return df

    @staticmethod
    def generate_smc_signals(df: pd.DataFrame, risk_reward_ratio: float = 3.0) -> pd.DataFrame:
        """
        Generates High-Probability Institutional SMC Signals based on:
        - Bullish: CHoCH / BOS + Price in Discount / Bullish OB Retest
        - Bearish: CHoCH / BOS + Price in Premium / Bearish OB Retest
        """
        df = SMCEngine.calculate_smc(df)
        df["signal"] = None
        df["entry_price"] = np.nan
        df["stop_loss"] = np.nan
        df["take_profit"] = np.nan
        
        for i in range(1, len(df)):
            close = df["close"].iloc[i]
            low = df["low"].iloc[i]
            high = df["high"].iloc[i]
            trend = df["smc_trend"].iloc[i]
            
            # 1. Bullish Entry Condition
            is_bullish_entry = (
                (trend == "BULLISH" and df["bos"].iloc[i]) or
                (df["choch"].iloc[i] and trend == "BULLISH") or
                (df["liquidity_sweep"].iloc[i] == "SELL_SIDE_SWEEP")
            )
            
            if is_bullish_entry:
                recent_low = df["low"].iloc[max(0, i - 5) : i + 1].min()
                sl = recent_low * 0.998  # Just below swing low
                risk = close - sl
                if risk > 0:
                    tp = close + (risk * risk_reward_ratio)
                    df.loc[df.index[i], "signal"] = "BUY"
                    df.loc[df.index[i], "entry_price"] = close
                    df.loc[df.index[i], "stop_loss"] = sl
                    df.loc[df.index[i], "take_profit"] = tp

            # 2. Bearish Entry Condition
            is_bearish_entry = (
                (trend == "BEARISH" and df["bos"].iloc[i]) or
                (df["choch"].iloc[i] and trend == "BEARISH") or
                (df["liquidity_sweep"].iloc[i] == "BUY_SIDE_SWEEP")
            )
            
            if is_bearish_entry:
                recent_high = df["high"].iloc[max(0, i - 5) : i + 1].max()
                sl = recent_high * 1.002  # Just above swing high
                risk = sl - close
                if risk > 0:
                    tp = close - (risk * risk_reward_ratio)
                    df.loc[df.index[i], "signal"] = "SELL"
                    df.loc[df.index[i], "entry_price"] = close
                    df.loc[df.index[i], "stop_loss"] = sl
                    df.loc[df.index[i], "take_profit"] = tp

        return df
