import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# 1. Load 1m Data & Resample to 5-Minute Candles
file_path = "/home/john/Downloads/CRUDEOIL21SEP26FUT_MCX_1m_2026-07-28_to_2026-08-27_MERGED.csv"
df_1m = pd.read_csv(file_path)
df_1m.columns = [c.strip().lower() for c in df_1m.columns]
df_1m['datetime'] = pd.to_datetime(df_1m['date time'])
df_1m = df_1m.sort_values('datetime').reset_index(drop=True)
df_1m.set_index('datetime', inplace=True)

# Resample to 5-Minute
df = df_1m.resample('5min', closed='left', label='left').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum',
    'oi': 'last'
}).dropna().reset_index()

# 2. Indicators: 20 EMA and 50 EMA on 5-Minute
df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

# 3. Strategy State Machine Simulation (5-Minute Timeframe)
# Rules:
# - Intraday: MCX session 09:00 to 23:25 (EOD square-off at 23:25)
# - State 0 (Downtrend): Price < EMA20 and Price < EMA50 for at least 4 bars
# - State 1 (Breakout): Price gives body close above BOTH 20 EMA and 50 EMA. Record breakout candle High.
# - State 2 (Retest): Price pulls back to touch/retest 20 EMA or 50 EMA zone without breaking swing low.
# - State 3 (Trigger Buy): After retest, price closes with body above Breakout Candle High (close > breakout_high).
# - Entry: Buy executed. SL = Retest / Previous swing low.
# - Trailing Target: Trailed using 20 EMA (close below 20 EMA exits).
# - Intraday: No carry forward, force exit by 23:25.

trades = []
position = None

state = 0
breakout_high = None
breakout_idx = None
retest_occurred = False
retest_swing_low = None
downtrend_count = 0

for i in range(50, len(df)):
    row = df.iloc[i]
    curr_time = row['datetime'].time()
    
    # Intraday Square-off condition at 23:25
    is_eod = curr_time >= datetime.time(23, 25) or curr_time < datetime.time(9, 10)
    
    if position is not None:
        # Check Stoploss
        if row['low'] <= position['sl']:
            exit_price = min(row['open'], position['sl'])
            trades.append({
                'entry_time': position['entry_time'],
                'entry_price': position['entry_price'],
                'exit_time': row['datetime'],
                'exit_price': exit_price,
                'type': 'BUY',
                'reason': 'SL_HIT',
                'pnl': exit_price - position['entry_price'],
                'entry_idx': position['entry_idx'],
                'exit_idx': i
            })
            position = None
            state = 0
            downtrend_count = 0
            continue
            
        # Trailing Exit using 20 EMA (5m candle closes below 20 EMA)
        elif row['close'] < row['ema20']:
            exit_price = row['close']
            trades.append({
                'entry_time': position['entry_time'],
                'entry_price': position['entry_price'],
                'exit_time': row['datetime'],
                'exit_price': exit_price,
                'type': 'BUY',
                'reason': 'TRAIL_EMA20_EXIT',
                'pnl': exit_price - position['entry_price'],
                'entry_idx': position['entry_idx'],
                'exit_idx': i
            })
            position = None
            state = 0
            downtrend_count = 0
            continue
            
        # EOD Exit
        elif is_eod:
            exit_price = row['close']
            trades.append({
                'entry_time': position['entry_time'],
                'entry_price': position['entry_price'],
                'exit_time': row['datetime'],
                'exit_price': exit_price,
                'type': 'BUY',
                'reason': 'INTRADAY_EOD_EXIT',
                'pnl': exit_price - position['entry_price'],
                'entry_idx': position['entry_idx'],
                'exit_idx': i
            })
            position = None
            state = 0
            downtrend_count = 0
            continue

    if is_eod:
        state = 0
        breakout_high = None
        retest_occurred = False
        continue

    # State Machine Logic
    # 1. Downtrend check
    if row['close'] < row['ema20'] and row['close'] < row['ema50']:
        downtrend_count += 1
    else:
        if state == 0:
            downtrend_count = max(0, downtrend_count - 1)
            
    # 2. Breakout detection from downtrend (5m close above both EMAs)
    if state == 0 and downtrend_count >= 3:
        if row['close'] > max(row['ema20'], row['ema50']) and row['open'] < max(row['ema20'], row['ema50']):
            state = 1
            breakout_high = row['high']
            breakout_idx = i
            retest_occurred = False
            retest_swing_low = row['low']
            
    # 3. Retest detection
    elif state == 1:
        ema_top = max(row['ema20'], row['ema50'])
        ema_bottom = min(row['ema20'], row['ema50'])
        retest_swing_low = min(retest_swing_low, row['low'])
        
        # Low touches back near EMA band
        if row['low'] <= ema_top + 3.0 and row['close'] >= ema_bottom - 8.0:
            retest_occurred = True
            
        # Pattern invalidation if it breaks deeply below 50 EMA or takes > 20 bars (100 mins)
        if row['close'] < ema_bottom - 15.0 or (i - breakout_idx > 20):
            state = 0
            breakout_high = None
            retest_occurred = False
            downtrend_count = 0
            
        # 4. Trigger Buy: 5m candle closes with body above breakout candle High
        elif retest_occurred and row['close'] > breakout_high and row['close'] > row['open']:
            sl = retest_swing_low - 2.0
            position = {
                'entry_time': row['datetime'],
                'entry_price': row['close'],
                'sl': sl,
                'breakout_high': breakout_high,
                'entry_idx': i
            }
            state = 0
            breakout_high = None
            retest_occurred = False
            downtrend_count = 0

# 4. Results & Summary
trades_df = pd.DataFrame(trades)
print("="*65)
print("📊 CRUDE OIL 5-MINUTE EMA RETEST STRATEGY BACKTEST RESULTS")
print("="*65)
print(f"Total Trades: {len(trades_df)}")
if len(trades_df) > 0:
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    win_rate = (len(wins) / len(trades_df)) * 100
    total_points = trades_df['pnl'].sum()
    total_profit_inr = total_points * 100
    
    print(f"Winning Trades: {len(wins)}")
    print(f"Losing Trades: {len(losses)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total Points Captured: {total_points:+.2f} pts")
    print(f"Total Net PnL (@ 100 lot size): ₹{total_profit_inr:+,.2f}")
    print(f"Max Win: +{trades_df['pnl'].max():.2f} pts")
    print(f"Max Loss: {trades_df['pnl'].min():.2f} pts")
    print(f"Profit Factor: {wins['pnl'].sum() / abs(losses['pnl'].sum()) if len(losses) > 0 else 'Inf':.2f}")
    print("="*65)
    print("\nComplete Trade Log:")
    print(trades_df[['entry_time', 'entry_price', 'exit_time', 'exit_price', 'reason', 'pnl']].to_string())

# Save Files
trades_df.to_csv("/home/john/openalgo/scratch/crude_5m_backtest_trades.csv", index=False)
trades_df.to_csv("/home/john/Desktop/crude_5m_backtest_trades.csv", index=False)

# 5. Interactive 5-Minute Chart Generation
fig = make_subplots(
    rows=2, cols=1, 
    shared_xaxes=True, 
    vertical_spacing=0.04, 
    row_heights=[0.8, 0.2],
    subplot_titles=(f"Crude Oil 5M EMA Retest Strategy | Total PnL: {total_points:+.1f} pts (₹{total_profit_inr:+,.0f})", "Volume")
)

# Candlestick
fig.add_trace(go.Candlestick(
    x=df['datetime'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name="Crude Oil 5m"
), row=1, col=1)

# EMA 20 & 50
fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema20'], name="20 EMA (Trail)", line=dict(color="#00f2fe", width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema50'], name="50 EMA (Trend)", line=dict(color="#fe0979", width=1.5)), row=1, col=1)

# Buy & Exit Markers
if len(trades_df) > 0:
    fig.add_trace(go.Scatter(
        x=trades_df['entry_time'],
        y=trades_df['entry_price'],
        mode='markers',
        marker=dict(symbol='triangle-up', size=14, color='#00ff88', line=dict(color='black', width=1)),
        name='BUY Entry',
        text=[f"BUY @ {p:.1f}" for p in trades_df['entry_price']]
    ), row=1, col=1)

    exit_colors = ['#00e676' if p > 0 else '#ff1744' for p in trades_df['pnl']]
    fig.add_trace(go.Scatter(
        x=trades_df['exit_time'],
        y=trades_df['exit_price'],
        mode='markers',
        marker=dict(symbol='triangle-down', size=14, color=exit_colors, line=dict(color='black', width=1)),
        name='EXIT',
        text=[f"EXIT @ {p:.1f} ({r}, PnL: {pnl:+.1f})" for p, r, pnl in zip(trades_df['exit_price'], trades_df['reason'], trades_df['pnl'])]
    ), row=1, col=1)

vol_colors = ['#00e676' if c >= o else '#ff1744' for o, c in zip(df['open'], df['close'])]
fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], name="Volume", marker_color=vol_colors), row=2, col=1)

fig.update_layout(
    title="⚡ CRUDE OIL 5-MINUTE - DOWNTREND BREAKOUT + RETEST + 20 EMA TRAILING BACKTEST",
    template="plotly_dark",
    height=900,
    xaxis_rangeslider_visible=False,
    hovermode='x unified'
)

html_path = "/home/john/Desktop/crude_5m_backtest_chart.html"
fig.write_html(html_path)
fig.write_html("/home/john/openalgo/scratch/crude_5m_backtest_chart.html")
print(f"\n5M Interactive Chart saved to {html_path}")
