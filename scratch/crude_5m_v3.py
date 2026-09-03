import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# ═══════════════════ LOAD & RESAMPLE TO 5M ═══════════════════
df_1m = pd.read_csv("/home/john/Downloads/CRUDEOIL21SEP26FUT_MCX_1m_2026-07-28_to_2026-08-27_MERGED.csv")
df_1m.columns = [c.strip().lower() for c in df_1m.columns]
df_1m['datetime'] = pd.to_datetime(df_1m['date time'])
df_1m = df_1m.sort_values('datetime').reset_index(drop=True)
df_1m.set_index('datetime', inplace=True)

df = df_1m.resample('5min', closed='left', label='left').agg({
    'open': 'first', 'high': 'max', 'low': 'min',
    'close': 'last', 'volume': 'sum', 'oi': 'last'
}).dropna().reset_index()

df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

# ═══════════════════ STRICT STRATEGY LOGIC ═══════════════════
#
# STEP 1 - DOWNTREND CHECK:
#   Look back N bars. ALL of them must have close < ema20 AND close < ema50.
#   This ensures a REAL downtrend, not random noise.
#
# STEP 2 - BREAKOUT CANDLE:
#   Current bar: close > max(ema20, ema50) AND close > open (bullish)
#   Previous bar: close < max(ema20, ema50) (was below)
#   → Mark breakout candle HIGH. DO NOT BUY.
#
# STEP 3 - RETEST (MANDATORY):
#   After breakout (minimum 2 bars gap), a candle's LOW goes BELOW
#   the upper EMA (max of ema20, ema50). This means price actually
#   pulled back into the EMA zone. Close must stay above lower EMA
#   (not a full breakdown).
#
# STEP 4 - TRIGGER BUY:
#   After retest confirmed, a NEW bullish candle closes with body
#   above the breakout candle's marked HIGH. NOW BUY.
#
# EXIT: close < ema20 (trail) | SL hit (swing low) | EOD 23:25

DT_LOOKBACK = 5       # All last 5 bars must be below both EMAs
MIN_RETEST_GAP = 2    # At least 2 bars after breakout before retest valid
MAX_WAIT = 25         # Pattern expires after 25 bars
SL_BUFFER = 3.0

trades = []
markers = []  # For chart visualization: {'idx', 'type', 'price', 'text'}
position = None

state = 0  # 0=scan, 1=breakout(wait retest), 2=retest done(wait trigger)
breakout_high = None
breakout_idx = None
retest_swing_low = None

for i in range(55, len(df)):
    row = df.iloc[i]
    curr_time = row['datetime'].time()
    is_eod = curr_time >= datetime.time(23, 25) or curr_time < datetime.time(9, 10)

    ema_top = max(row['ema20'], row['ema50'])
    ema_bot = min(row['ema20'], row['ema50'])

    # ─── EXIT LOGIC (if in trade) ───
    if position is not None:
        if row['low'] <= position['sl']:
            ep = min(row['open'], position['sl'])
            trades.append({**position, 'exit_time': row['datetime'], 'exit_price': ep,
                           'reason': 'SL_HIT', 'pnl': ep - position['entry_price'], 'exit_idx': i})
            markers.append({'idx': i, 'type': 'exit', 'price': ep, 'text': f"SL {ep:.0f}"})
            position = None; state = 0; continue
        elif row['close'] < row['ema20'] and not is_eod:
            ep = row['close']
            trades.append({**position, 'exit_time': row['datetime'], 'exit_price': ep,
                           'reason': 'TRAIL_EMA20', 'pnl': ep - position['entry_price'], 'exit_idx': i})
            markers.append({'idx': i, 'type': 'exit', 'price': ep, 'text': f"Trail {ep:.0f}"})
            position = None; state = 0; continue
        elif is_eod:
            ep = row['close']
            trades.append({**position, 'exit_time': row['datetime'], 'exit_price': ep,
                           'reason': 'EOD_EXIT', 'pnl': ep - position['entry_price'], 'exit_idx': i})
            markers.append({'idx': i, 'type': 'exit', 'price': ep, 'text': f"EOD {ep:.0f}"})
            position = None; state = 0; continue

    if is_eod:
        state = 0; breakout_high = None; breakout_idx = None; retest_swing_low = None
        continue

    # ─── STEP 1: DOWNTREND CHECK ───
    # Check if ALL last DT_LOOKBACK bars had close below BOTH ema20 AND ema50
    def is_downtrend(idx):
        if idx < DT_LOOKBACK:
            return False
        for j in range(idx - DT_LOOKBACK, idx):  # bars BEFORE current bar
            r = df.iloc[j]
            if r['close'] >= r['ema20'] or r['close'] >= r['ema50']:
                return False
        return True

    # ─── STEP 2: BREAKOUT DETECTION ───
    if state == 0 and position is None:
        prev = df.iloc[i-1]
        prev_was_below = prev['close'] < max(prev['ema20'], prev['ema50'])
        curr_closes_above = row['close'] > ema_top
        is_bullish = row['close'] > row['open']
        downtrend_ok = is_downtrend(i)

        if downtrend_ok and prev_was_below and curr_closes_above and is_bullish:
            state = 1
            breakout_high = row['high']
            breakout_idx = i
            retest_swing_low = row['low']
            markers.append({'idx': i, 'type': 'breakout', 'price': row['high'], 'text': f"BRK H:{row['high']:.0f}"})

    # ─── STEP 3: WAIT FOR RETEST ───
    elif state == 1:
        bars_since = i - breakout_idx
        retest_swing_low = min(retest_swing_low, row['low'])

        # Retest = Low goes AT or BELOW the upper EMA (price comes back into EMA zone)
        # Must be at least MIN_RETEST_GAP bars after breakout
        if bars_since >= MIN_RETEST_GAP and row['low'] <= ema_top:
            # Close must still be above lower EMA (not a full breakdown)
            if row['close'] >= ema_bot - 5.0:
                state = 2
                markers.append({'idx': i, 'type': 'retest', 'price': row['low'], 'text': "RETEST ✓"})

        # Invalidate if price collapses below lower EMA or timeout
        if row['close'] < ema_bot - 15.0 or bars_since > MAX_WAIT:
            state = 0; breakout_high = None; breakout_idx = None; retest_swing_low = None

    # ─── STEP 4: WAIT FOR TRIGGER (CLOSE > BREAKOUT HIGH) ───
    elif state == 2:
        bars_since = i - breakout_idx
        retest_swing_low = min(retest_swing_low, row['low'])

        # Trigger: bullish candle, close above breakout high
        if row['close'] > breakout_high and row['close'] > row['open']:
            sl = retest_swing_low - SL_BUFFER
            position = {
                'entry_time': row['datetime'], 'entry_price': row['close'],
                'sl': sl, 'entry_idx': i
            }
            markers.append({'idx': i, 'type': 'buy', 'price': row['close'], 'text': f"BUY {row['close']:.0f}"})
            state = 0; breakout_high = None; breakout_idx = None; retest_swing_low = None

        # Invalidate
        if row['close'] < ema_bot - 15.0 or bars_since > MAX_WAIT:
            state = 0; breakout_high = None; breakout_idx = None; retest_swing_low = None

# ═══════════════════ RESULTS ═══════════════════
trades_df = pd.DataFrame(trades)
print("=" * 65)
print("📊 CRUDE OIL 5M - STRICT REVERSAL RETEST STRATEGY V3")
print("=" * 65)
print(f"Total Trades: {len(trades_df)}")
if len(trades_df) > 0:
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    total_pts = trades_df['pnl'].sum()
    total_inr = total_pts * 100
    pf = wins['pnl'].sum() / abs(losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')
    print(f"Wins: {len(wins)} | Losses: {len(losses)} | Win Rate: {len(wins)/len(trades_df)*100:.1f}%")
    print(f"Total Points: {total_pts:+.1f} | PnL @ 100 Lot: ₹{total_inr:+,.0f}")
    print(f"Max Win: +{trades_df['pnl'].max():.1f} | Max Loss: {trades_df['pnl'].min():.1f}")
    print(f"Profit Factor: {pf:.2f}")
    print("=" * 65)
    print("\nAll Trades:")
    print(trades_df[['entry_time','entry_price','exit_time','exit_price','reason','pnl']].to_string())

trades_df.to_csv("/home/john/Desktop/crude_5m_v3_trades.csv", index=False)

# ═══════════════════ CHART ═══════════════════
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                    row_heights=[0.8, 0.2],
                    subplot_titles=(f"Crude Oil 5M Reversal Retest V3 | {len(trades_df)} trades | {total_pts:+.1f} pts", "Volume"))

fig.add_trace(go.Candlestick(x=df['datetime'], open=df['open'], high=df['high'],
              low=df['low'], close=df['close'], name="Crude 5m"), row=1, col=1)
fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema20'], name="20 EMA", line=dict(color="#00f2fe", width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema50'], name="50 EMA", line=dict(color="#fe0979", width=1.5)), row=1, col=1)

markers_df = pd.DataFrame(markers)
for mtype, sym, clr, sz, loc in [
    ('breakout', 'diamond', '#FFD700', 12, 'top'),
    ('retest',   'circle',  '#FF8C00', 11, 'bottom'),
    ('buy',      'triangle-up', '#00FF88', 15, 'bottom'),
    ('exit',     'triangle-down', '#FF1744', 14, 'top'),
]:
    sub = markers_df[markers_df['type'] == mtype] if len(markers_df) > 0 else pd.DataFrame()
    if len(sub) > 0:
        fig.add_trace(go.Scatter(
            x=[df.iloc[idx]['datetime'] for idx in sub['idx']],
            y=sub['price'].values,
            mode='markers+text',
            marker=dict(symbol=sym, size=sz, color=clr, line=dict(color='black', width=1)),
            text=sub['text'].values,
            textposition=loc + ' center',
            textfont=dict(size=9, color=clr),
            name=mtype.upper()
        ), row=1, col=1)

vol_c = ['#00e676' if c >= o else '#ff1744' for o, c in zip(df['open'], df['close'])]
fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=vol_c, name="Vol"), row=2, col=1)

fig.update_layout(title="⚡ CRUDE 5M REVERSAL: Downtrend → Breakout (Mark High) → Retest → Trigger BUY",
                  template="plotly_dark", height=950, xaxis_rangeslider_visible=False, hovermode='x unified')

fig.write_html("/home/john/Desktop/crude_5m_v3_chart.html")
print(f"\nChart saved: /home/john/Desktop/crude_5m_v3_chart.html")
