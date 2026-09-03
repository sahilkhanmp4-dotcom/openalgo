import pandas as pd
import numpy as np
import datetime

# Test 1: Fakeout / False Breakout Reversal Strategy (Fade the initial breakout)
# Test 2: Narrow ORB Filter + Retest Entry
# Test 3: 15m ORB with Trailing EMA exit instead of static RR

def test_orb_reversals_and_filters(csv_path, asset_name, session_end_time):
    df_raw = pd.read_csv(csv_path)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    dt_col = 'date time' if 'date time' in df_raw.columns else 'datetime'
    df_raw['datetime'] = pd.to_datetime(df_raw[dt_col])
    df_raw = df_raw.sort_values('datetime').reset_index(drop=True)
    df_raw['date'] = df_raw['datetime'].dt.date
    df_raw['time'] = df_raw['datetime'].dt.time
    
    unique_dates = df_raw['date'].unique()
    
    # ── 1. STRATEGY: ORB FADEOUT / FAKEOUT REVERSAL (Trade against initial fake break) ──
    fakeout_trades = []
    for d in unique_dates:
        day_data = df_raw[df_raw['date'] == d].copy().reset_index(drop=True)
        if len(day_data) < 30: continue
        
        # 15m ORB
        orb = day_data.iloc[:15]
        h, l = orb['high'].max(), orb['low'].min()
        rng = h - l
        
        trading = day_data.iloc[15:].copy().reset_index(drop=True)
        
        # Look for initial breakout that fails (closes back inside range)
        broke_high = False
        broke_low = False
        pos = None
        entry_p, sl, tp = 0, 0, 0
        
        for idx, row in trading.iterrows():
            if row['time'] >= session_end_time:
                if pos:
                    pnl = (row['close'] - entry_p) if pos == 'LONG' else (entry_p - row['close'])
                    fakeout_trades.append({'date': d, 'pnl': pnl, 'type': 'EOD', 'pos': pos})
                break
            
            if pos is None:
                if row['high'] > h and not broke_high and not broke_low:
                    broke_high = True # Swept high
                if broke_high and row['close'] < h: # Closed back inside = Short Fakeout
                    pos = 'SHORT'; entry_p = row['close']; sl = h + (rng * 0.2); tp = l; broke_high = False
                elif row['low'] < l and not broke_low and not broke_high:
                    broke_low = True # Swept low
                if broke_low and row['close'] > l: # Closed back inside = Long Fakeout
                    pos = 'LONG'; entry_p = row['close']; sl = l - (rng * 0.2); tp = h; broke_low = False
            else:
                if pos == 'LONG':
                    if row['low'] <= sl:
                        fakeout_trades.append({'date': d, 'pnl': sl - entry_p, 'type': 'SL', 'pos': pos})
                        pos = None; break
                    elif row['high'] >= tp:
                        fakeout_trades.append({'date': d, 'pnl': tp - entry_p, 'type': 'TP', 'pos': pos})
                        pos = None; break
                elif pos == 'SHORT':
                    if row['high'] >= sl:
                        fakeout_trades.append({'date': d, 'pnl': entry_p - sl, 'type': 'SL', 'pos': pos})
                        pos = None; break
                    elif row['low'] <= tp:
                        fakeout_trades.append({'date': d, 'pnl': entry_p - tp, 'type': 'TP', 'pos': pos})
                        pos = None; break
                        
    fdf = pd.DataFrame(fakeout_trades)
    print(f"\n⚡ FAKEOUT / LIQUIDITY TRAP STRATEGY FOR {asset_name} (Fading 15m ORB):")
    if len(fdf) > 0:
        wins = fdf[fdf['pnl'] > 0]
        losses = fdf[fdf['pnl'] <= 0]
        wr = len(wins) / len(fdf) * 100
        tot = fdf['pnl'].sum()
        pf = wins['pnl'].sum() / abs(losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')
        print(f"  • Trades: {len(fdf)} | Win Rate: {wr:.1f}% | Total PnL: {tot:+.1f} pts | Profit Factor: {pf:.2f}")

test_orb_reversals_and_filters("/home/john/Downloads/NIFTY25AUG26FUT_NFO_1m_2026-07-31_to_2026-08-25.csv", "NIFTY FUTURES", datetime.time(15, 25))
test_orb_reversals_and_filters("/home/john/Downloads/CRUDEOIL21SEP26FUT_MCX_1m_2026-07-28_to_2026-08-27_MERGED.csv", "CRUDE OIL FUTURES", datetime.time(23, 25))
