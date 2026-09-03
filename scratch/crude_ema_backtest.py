import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# 1. Load Data
file_path = "/home/john/Downloads/CRUDEOIL21SEP26FUT_MCX_1m_2026-07-28_to_2026-08-27_MERGED.csv"
df = pd.read_csv(file_path)

# Normalize column names
df.columns = [c.strip().lower() for c in df.columns]
df['datetime'] = pd.to_datetime(df['date time'])
df = df.sort_values('datetime').reset_index(drop=True)

# 2. Indicators: 20 EMA and 50 EMA
df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

# 3. Strategy State Machine Simulation
# Rules:
# - Intraday: MCX session 09:00 to 23:25 (EOD square-off at 23:25)
# - State 0 (Searching Downtrend): Price < EMA20 and Price < EMA50 (both close and open under EMAs for at least a few bars)
# - State 1 (Breakout): Price gives a strong body close above BOTH 20 EMA and 50 EMA (min(open, close) > max(ema20, ema50) or close > max(ema20, ema50)). Record breakout candle High and index.
# - State 2 (Retest): Price pulls back to touch/retest 20 EMA or 50 EMA (Low <= max(ema20, ema50) + 2 points and Low >= min(ema20, ema50) - 10 points) without breaking below major swing low.
# - State 3 (Trigger Buy): Price closes with body above Breakout Candle High (close > breakout_high).
# - Entry: Buy executed. SL = Lowest low of the retest / previous swing low.
# - Trailing Target: Trailed using 20 EMA (when candle closes below 20 EMA or Low < 20 EMA, exit). Also SL hit exit.
# - Intraday: Force exit by 23:25.

trades = []
position = None # {'entry_time', 'entry_price', 'sl', 'breakout_high', 'entry_idx'}

state = 0
breakout_high = None
breakout_idx = None
retest_occurred = False
retest_swing_low = None
downtrend_count = 0

for i in range(50, len(df)):
    row = df.iloc[i]
    prev = df.iloc[i-1]
    curr_time = row['datetime'].time()
    
    # Intraday Square-off condition at 23:25
    is_eod = curr_time >= datetime.time(23, 25) or curr_time < datetime.time(9, 5)
    
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
            
        # Trailing Exit using 20 EMA (close below 20 EMA)
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
            
    # 2. Breakout detection from downtrend
    if state == 0 and downtrend_count >= 5:
        # Check if current candle closes with body above BOTH 20 EMA and 50 EMA
        if row['close'] > max(row['ema20'], row['ema50']) and row['open'] < max(row['ema20'], row['ema50']):
            state = 1
            breakout_high = row['high']
            breakout_idx = i
            retest_occurred = False
            retest_swing_low = row['low']
            
    # 3. Retest detection
    elif state == 1:
        # Retest means price touches back into EMA zone (20 EMA or 50 EMA)
        ema_top = max(row['ema20'], row['ema50'])
        ema_bottom = min(row['ema20'], row['ema50'])
        
        # Track swing low during retest
        retest_swing_low = min(retest_swing_low, row['low'])
        
        if row['low'] <= ema_top + 1.5 and row['close'] >= ema_bottom - 4.0:
            retest_occurred = True
            
        # If price falls deeply below 50 EMA, pattern invalidates
        if row['close'] < ema_bottom - 8.0 or (i - breakout_idx > 30):
            state = 0
            breakout_high = None
            retest_occurred = False
            downtrend_count = 0
            
        # 4. Trigger Buy: After retest, candle closes with body above breakout candle High
        elif retest_occurred and row['close'] > breakout_high and row['close'] > row['open']:
            # BUY SIGNAL TRIGGERED!
            sl = retest_swing_low - 1.0 # 1 point buffer below retest swing low
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

# 4. Trade Analysis & Summary
trades_df = pd.DataFrame(trades)
print("="*60)
print("📊 CRUDE OIL 1-MIN EMA RETEST STRATEGY BACKTEST RESULTS")
print("="*60)
print(f"Total Trades: {len(trades_df)}")
if len(trades_df) > 0:
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    win_rate = (len(wins) / len(trades_df)) * 100
    total_points = trades_df['pnl'].sum()
    # Crude lot size = 100
    total_profit_inr = total_points * 100
    
    print(f"Winning Trades: {len(wins)}")
    print(f"Losing Trades: {len(losses)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total Points Captured: {total_points:.2f} pts")
    print(f"Total Net PnL (@ 100 lot size): ₹{total_profit_inr:,.2f}")
    print(f"Max Win: +{trades_df['pnl'].max():.2f} pts")
    print(f"Max Loss: {trades_df['pnl'].min():.2f} pts")
    print("="*60)
    print("\nTrade Log Sample (First 10 Trades):")
    print(trades_df[['entry_time', 'entry_price', 'exit_time', 'exit_price', 'reason', 'pnl']].head(10).to_string())

# 5. Save Trades CSV
trades_df.to_csv("/home/john/openalgo/scratch/crude_backtest_trades.csv", index=False)

# 6. Interactive Visualizer Generation (Plotting Every Candle & Buy/Sell Marker)
# Build interactive HTML using Plotly
print("\nGenerating Interactive Chart with all candles, EMAs, Buy/Sell markers...")

fig = make_subplots(
    rows=2, cols=1, 
    shared_xaxes=True, 
    vertical_spacing=0.04, 
    row_heights=[0.8, 0.2],
    subplot_titles=(f"Crude Oil 1m EMA Retest Strategy (Total PnL: {total_points:.1f} pts / ₹{total_profit_inr:,.0f})", "Volume")
)

# Candlestick
fig.add_trace(go.Candlestick(
    x=df['datetime'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name="Crude Oil 1m"
), row=1, col=1)

# EMA 20 & 50
fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema20'], name="20 EMA (Trail)", line=dict(color="#00f2fe", width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema50'], name="50 EMA (Trend)", line=dict(color="#fe0979", width=1.5)), row=1, col=1)

# Buy Markers
if len(trades_df) > 0:
    buy_times = trades_df['entry_time']
    buy_prices = trades_df['entry_price']
    fig.add_trace(go.Scatter(
        x=buy_times,
        y=buy_prices,
        mode='markers',
        marker=dict(symbol='triangle-up', size=14, color='#00ff88', line=dict(color='black', width=1)),
        name='BUY Entry',
        text=[f"BUY @ {p:.1f}" for p in buy_prices]
    ), row=1, col=1)

    # Sell / Exit Markers
    exit_times = trades_df['exit_time']
    exit_prices = trades_df['exit_price']
    exit_colors = ['#00e676' if p > 0 else '#ff1744' for p in trades_df['pnl']]
    fig.add_trace(go.Scatter(
        x=exit_times,
        y=exit_prices,
        mode='markers',
        marker=dict(symbol='triangle-down', size=14, color=exit_colors, line=dict(color='black', width=1)),
        name='EXIT',
        text=[f"EXIT @ {p:.1f} ({r}, PnL: {pnl:+.1f})" for p, r, pnl in zip(exit_prices, trades_df['reason'], trades_df['pnl'])]
    ), row=1, col=1)

# Volume
vol_colors = ['#00e676' if c >= o else '#ff1744' for o, c in zip(df['open'], df['close'])]
fig.add_trace(go.Bar(
    x=df['datetime'],
    y=df['volume'],
    name="Volume",
    marker_color=vol_colors
), row=2, col=1)

fig.update_layout(
    title="⚡ CRUDE OIL 1M - DOWNTREND BREAKOUT + RETEST + 20 EMA TRAIL BACKTEST",
    template="plotly_dark",
    height=900,
    xaxis_rangeslider_visible=False,
    hovermode='x unified'
)

html_path = "/home/john/openalgo/scratch/crude_backtest_chart.html"
fig.write_html(html_path)
print(f"Chart successfully saved to {html_path}")

