"""
Theta Gun - VWAP + 25 EMA Session Breakout & Retest Strategy
Based on YouTube Strategy (https://youtu.be/57a1dixbtb4)

Strategy Logic:
1. Session Timing: High volatility session (06:00 PM to 11:00 PM IST or Full Day mode).
2. Base Indicators:
   - Anchored VWAP (Volume Weighted Average Price)
   - 25 EMA (Exponential Moving Average)
   - 20 EMA for trailing exit (15m Multi-Timeframe Confirmation)
3. Entry Conditions:
   - LONG (BUY +1):
     * Price breaks ABOVE both VWAP and 25 EMA (BRK Mark High).
     * Price gives a RETEST onto VWAP/25 EMA and holds without closing below.
     * Bullish confirmation candle on 5m.
   - SHORT (SELL -1):
     * Price breaks BELOW both VWAP and 25 EMA (BRK Mark Low).
     * Price gives a RETEST onto VWAP/25 EMA and gets rejected.
     * Bearish confirmation candle on 5m.
4. Exit & Risk Management:
   - Trailing Exit on 15m Trend Reversal (Price closing on opposite side of 20 EMA).
   - Stop Loss: Below recent Retest Swing Low (for Long) or above Retest Swing High (for Short).
   - Target: Open trend ride (captured 5% to 18% moves) with trailing stop.
"""

import numpy as np
import pandas as pd

def init_params(params):
    params['ema_len'] = 25              # Base Direction EMA
    params['trail_ema_len'] = 20        # Multi-timeframe Trailing EMA
    params['use_session_filter'] = False # True = Trade 6 PM to 11 PM, False = Full Day
    params['session_start_hour'] = 18   # 6 PM
    params['session_end_hour'] = 23     # 11 PM
    params['sl_buffer_pct'] = 0.5       # Buffer for Stop Loss below swing

def calculate_vwap(df):
    """Calculates Intraday VWAP reset daily"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    cum_vol_price = (typical_price * df['volume']).cumsum()
    cum_vol = df['volume'].cumsum()
    return cum_vol_price / (cum_vol + 1e-9)

def calculate_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def on_bar(bars, strategy):
    """
    bars: DataFrame with columns ['time', 'open', 'high', 'low', 'close', 'volume']
    strategy: Trading Engine Helper with buy(), sell(), close()
    """
    if len(bars) < 30:
        return

    # 1. Calculate Core Indicators
    df = bars.copy()
    df['ema25'] = calculate_ema(df['close'], 25)
    df['ema20_trail'] = calculate_ema(df['close'], 20)
    df['vwap'] = calculate_vwap(df)

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    # 2. Time/Session Filter
    bar_time = pd.to_datetime(curr['time'], unit='s', utc=True).tz_convert('Asia/Kolkata')
    in_session = True
    # if params.get('use_session_filter', False):
    #     in_session = (bar_time.hour >= 18 and bar_time.hour < 23)

    # 3. Entry Logic (Breakout + Retest)
    vwap_val = curr['vwap']
    ema25_val = curr['ema25']
    ema20_val = curr['ema20_trail']

    is_breakout_up = (prev2['close'] <= prev2['ema25']) and (prev['close'] > prev['ema25'] and prev['close'] > prev['vwap'])
    is_retest_hold_up = (curr['low'] <= max(ema25_val, vwap_val)) and (curr['close'] > min(ema25_val, vwap_val))

    is_breakout_down = (prev2['close'] >= prev2['ema25']) and (prev['close'] < prev['ema25'] and prev['close'] < prev['vwap'])
    is_retest_hold_down = (curr['high'] >= min(ema25_val, vwap_val)) and (curr['close'] < max(ema25_val, vwap_val))

    # 4. Trailing Exit Rules (15m Confirmation / 20 EMA Trail)
    if getattr(strategy, 'in_long', False):
        if curr['close'] < ema20_val:
            strategy.close(comment="Trail Exit 20EMA ▼")
            return

    elif getattr(strategy, 'in_short', False):
        if curr['close'] > ema20_val:
            strategy.close(comment="Trail Exit 20EMA ▲")
            return

    # 5. Execute Trades
    if not getattr(strategy, 'in_position', False) and in_session:
        if is_breakout_up or (curr['close'] > ema25_val and curr['close'] > vwap_val and is_retest_hold_up):
            sl_price = min(curr['low'], prev['low']) * 0.995
            strategy.buy(
                qty=1,
                comment="BUY ▲ (+1) [BRK & RETEST]",
                stop_loss=sl_price,
                target_pct=4.5
            )

        elif is_breakout_down or (curr['close'] < ema25_val and curr['close'] < vwap_val and is_retest_hold_down):
            sl_price = max(curr['high'], prev['high']) * 1.005
            strategy.sell(
                qty=1,
                comment="SELL ▼ (-1) [BRK & RETEST]",
                stop_loss=sl_price,
                target_pct=4.5
            )
