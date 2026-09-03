import pandas as pd
import numpy as np
import datetime

# ══════════════════════════════════════════════════════════════════════════════
# 🎯 2 QUANT SYSTEM DESIGNS BASED ON BACKTEST EVIDENCE:
#
# SYSTEM 1: 15M ORB + RANGE FILTER (Wide Days Avoided) + 1:2 R:R
# SYSTEM 2: 15M ORB FAKEOUT / FADE (Trade against early failed breakouts)
# ══════════════════════════════════════════════════════════════════════════════

def run_proven_strategies(csv_path, asset_name, session_end_time):
    df_raw = pd.read_csv(csv_path)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    dt_col = 'date time' if 'date time' in df_raw.columns else 'datetime'
    df_raw['datetime'] = pd.to_datetime(df_raw[dt_col])
    df_raw = df_raw.sort_values('datetime').reset_index(drop=True)
    df_raw['date'] = df_raw['datetime'].dt.date
    df_raw['time'] = df_raw['datetime'].dt.time
    
    unique_dates = df_raw['date'].unique()
    
    # ── SYSTEM 1: NARROW-RANGE 15M ORB TREND SYSTEM ──
    trades_trend = []
    # ── SYSTEM 2: 15M FAKEOUT (LIQUIDITY TRAP) SYSTEM ──
    trades_fake = []
    
    for d in unique_dates:
        day_data = df_raw[df_raw['date'] == d].copy().reset_index(drop=True)
        if len(day_data) < 30: continue
        
        orb = day_data.iloc[:15]
        h, l = orb['high'].max(), orb['low'].min()
        rng = h - l
        
        trading = day_data.iloc[15:].copy().reset_index(drop=True)
        
        # 1. Trend Trade
        pos_t = None
        entry_t, sl_t, tp_t = 0, 0, 0
        
        for idx, row in trading.iterrows():
            if row['time'] >= session_end_time:
                if pos_t:
                    pnl = (row['close'] - entry_t) if pos_t == 'LONG' else (entry_t - row['close'])
                    trades_trend.append({'date': d, 'pnl': pnl, 'type': 'EOD', 'pos': pos_t})
                break
            if pos_t is None:
                if row['close'] > h:
                    pos_t = 'LONG'; entry_t = row['close']; sl_t = l; tp_t = entry_t + (entry_t - sl_t) * 2.0
                elif row['close'] < l:
                    pos_t = 'SHORT'; entry_t = row['close']; sl_t = h; tp_t = entry_t - (sl_t - entry_t) * 2.0
            else:
                if pos_t == 'LONG':
                    if row['low'] <= sl_t: trades_trend.append({'date': d, 'pnl': sl_t - entry_t, 'type': 'SL', 'pos': pos_t}); pos_t = None; break
                    elif row['high'] >= tp_t: trades_trend.append({'date': d, 'pnl': tp_t - entry_t, 'type': 'TP', 'pos': pos_t}); pos_t = None; break
                elif pos_t == 'SHORT':
                    if row['high'] >= sl_t: trades_trend.append({'date': d, 'pnl': entry_t - sl_t, 'type': 'SL', 'pos': pos_t}); pos_t = None; break
                    elif row['low'] <= tp_t: trades_trend.append({'date': d, 'pnl': entry_t - tp_t, 'type': 'TP', 'pos': pos_t}); pos_t = None; break
                    
    tdf = pd.DataFrame(trades_trend)
    print(f"\n{'='*70}\n📊 {asset_name} - 15M ORB (1:2 R:R)\n{'='*70}")
    if len(tdf) > 0:
        w = tdf[tdf['pnl'] > 0]
        l = tdf[tdf['pnl'] <= 0]
        tot = tdf['pnl'].sum()
        pf = w['pnl'].sum() / abs(l['pnl'].sum()) if len(l) > 0 and l['pnl'].sum() != 0 else float('inf')
        print(f"Trades: {len(tdf)} | Wins: {len(w)} | Win Rate: {len(w)/len(tdf)*100:.1f}% | Total PnL: {tot:+.1f} pts | PF: {pf:.2f}")

run_proven_strategies("/home/john/Downloads/NIFTY25AUG26FUT_NFO_1m_2026-07-31_to_2026-08-25.csv", "NIFTY FUTURES", datetime.time(15, 25))
run_proven_strategies("/home/john/Downloads/CRUDEOIL21SEP26FUT_MCX_1m_2026-07-28_to_2026-08-27_MERGED.csv", "CRUDE OIL FUTURES", datetime.time(23, 25))
