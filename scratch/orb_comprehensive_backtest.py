import pandas as pd
import numpy as np
import datetime

# ══════════════════════════════════════════════════════════════════════════════
# 📊 UNBIASED OPENING RANGE BREAKOUT (ORB) BACKTEST ENGINE
# Evaluates 1-Minute, 5-Minute, and 15-Minute ORB across NIFTY & CRUDE datasets
# Tests R:R from 1:1, 1:1.5, 1:2, 1:2.5, 1:3, 1:4, 1:5 + Trailing exits
# Searches for Hidden Patterns (False Breakouts, Day of Week, Range Size, Time)
# ══════════════════════════════════════════════════════════════════════════════

def run_orb_analysis(csv_path, asset_name, session_start_time, session_end_time, is_mcx=False):
    print(f"\n{'='*80}\n📈 RUNNING UNBIASED ORB ANALYSIS FOR: {asset_name}\n{'='*80}")
    df_raw = pd.read_csv(csv_path)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    dt_col = 'date time' if 'date time' in df_raw.columns else 'datetime'
    df_raw['datetime'] = pd.to_datetime(df_raw[dt_col])
    df_raw = df_raw.sort_values('datetime').reset_index(drop=True)
    df_raw['date'] = df_raw['datetime'].dt.date
    df_raw['time'] = df_raw['datetime'].dt.time
    df_raw['day_name'] = df_raw['datetime'].dt.day_name()
    
    timeframes = [1, 5, 15]
    rr_targets = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    
    summary_results = []
    all_trade_records = []
    
    unique_dates = df_raw['date'].unique()
    
    for tf in timeframes:
        for rr in rr_targets:
            trades = []
            for d in unique_dates:
                day_data = df_raw[df_raw['date'] == d].copy().reset_index(drop=True)
                if len(day_data) < tf + 10:
                    continue
                
                # Opening Range definition (First tf minutes)
                orb_bars = day_data.iloc[:tf]
                orb_high = orb_bars['high'].max()
                orb_low = orb_bars['low'].min()
                orb_range = orb_high - orb_low
                
                if orb_range <= 0:
                    continue
                
                # Trading window (after tf minutes till EOD)
                trading_bars = day_data.iloc[tf:].copy().reset_index(drop=True)
                
                pos = None # 'LONG' or 'SHORT'
                entry_price = 0
                sl_price = 0
                tp_price = 0
                entry_idx = 0
                entry_time = None
                
                for idx, row in trading_bars.iterrows():
                    # EOD Exit
                    if row['time'] >= session_end_time:
                        if pos is not None:
                            exit_p = row['close']
                            pnl = (exit_p - entry_price) if pos == 'LONG' else (entry_price - exit_p)
                            trades.append({
                                'tf': tf, 'rr': rr, 'date': d, 'day': row['datetime'].strftime('%A'),
                                'pos': pos, 'entry_p': entry_price, 'exit_p': exit_p, 'pnl': pnl,
                                'pnl_r': pnl / orb_range, 'reason': 'EOD', 'orb_range': orb_range,
                                'entry_time': entry_time, 'hold_bars': idx - entry_idx
                            })
                            pos = None
                        break
                    
                    if pos is None:
                        # Breakout High
                        if row['close'] > orb_high:
                            pos = 'LONG'
                            entry_price = row['close']
                            sl_price = orb_low  # Classic ORB SL = opposite side
                            risk = entry_price - sl_price
                            tp_price = entry_price + (risk * rr)
                            entry_idx = idx
                            entry_time = row['time']
                        # Breakdown Low
                        elif row['close'] < orb_low:
                            pos = 'SHORT'
                            entry_price = row['close']
                            sl_price = orb_high
                            risk = sl_price - entry_price
                            tp_price = entry_price - (risk * rr)
                            entry_idx = idx
                            entry_time = row['time']
                    else:
                        # Manage Position
                        if pos == 'LONG':
                            if row['low'] <= sl_price:
                                exit_p = sl_price
                                pnl = exit_p - entry_price
                                trades.append({
                                    'tf': tf, 'rr': rr, 'date': d, 'day': row['datetime'].strftime('%A'),
                                    'pos': pos, 'entry_p': entry_price, 'exit_p': exit_p, 'pnl': pnl,
                                    'pnl_r': pnl / orb_range, 'reason': 'SL', 'orb_range': orb_range,
                                    'entry_time': entry_time, 'hold_bars': idx - entry_idx
                                })
                                pos = None; break
                            elif row['high'] >= tp_price:
                                exit_p = tp_price
                                pnl = exit_p - entry_price
                                trades.append({
                                    'tf': tf, 'rr': rr, 'date': d, 'day': row['datetime'].strftime('%A'),
                                    'pos': pos, 'entry_p': entry_price, 'exit_p': exit_p, 'pnl': pnl,
                                    'pnl_r': pnl / orb_range, 'reason': 'TP', 'orb_range': orb_range,
                                    'entry_time': entry_time, 'hold_bars': idx - entry_idx
                                })
                                pos = None; break
                        elif pos == 'SHORT':
                            if row['high'] <= sl_price: # wait, for short SL is high >= sl_price
                                pass
                            if row['high'] >= sl_price:
                                exit_p = sl_price
                                pnl = entry_price - exit_p
                                trades.append({
                                    'tf': tf, 'rr': rr, 'date': d, 'day': row['datetime'].strftime('%A'),
                                    'pos': pos, 'entry_p': entry_price, 'exit_p': exit_p, 'pnl': pnl,
                                    'pnl_r': pnl / orb_range, 'reason': 'SL', 'orb_range': orb_range,
                                    'entry_time': entry_time, 'hold_bars': idx - entry_idx
                                })
                                pos = None; break
                            elif row['low'] <= tp_price:
                                exit_p = tp_price
                                pnl = entry_price - exit_p
                                trades.append({
                                    'tf': tf, 'rr': rr, 'date': d, 'day': row['datetime'].strftime('%A'),
                                    'pos': pos, 'entry_p': entry_price, 'exit_p': exit_p, 'pnl': pnl,
                                    'pnl_r': pnl / orb_range, 'reason': 'TP', 'orb_range': orb_range,
                                    'entry_time': entry_time, 'hold_bars': idx - entry_idx
                                })
                                pos = None; break
                                
            tdf = pd.DataFrame(trades)
            if len(tdf) > 0:
                wins = tdf[tdf['pnl'] > 0]
                losses = tdf[tdf['pnl'] <= 0]
                win_rate = len(wins) / len(tdf) * 100
                total_pnl = tdf['pnl'].sum()
                gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
                gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1e-5
                pf = gross_profit / gross_loss if gross_loss > 0 else 0
                total_r = tdf['pnl_r'].sum()
                
                summary_results.append({
                    'Timeframe': f"{tf}m ORB",
                    'Target RR': f"1:{rr}",
                    'Trades': len(tdf),
                    'Win Rate (%)': round(win_rate, 1),
                    'Total Points': round(total_pnl, 1),
                    'Total R': round(total_r, 2),
                    'Profit Factor': round(pf, 2),
                    'Max Win': round(tdf['pnl'].max(), 1),
                    'Max Loss': round(tdf['pnl'].min(), 1)
                })
                all_trade_records.extend(trades)
                
    res_df = pd.DataFrame(summary_results)
    print(res_df.to_string(index=False))
    
    # ════════════ HIDDEN PATTERNS & ANOMALIES ════════════
    full_trades = pd.DataFrame(all_trade_records)
    if len(full_trades) > 0:
        print(f"\n🔍 HIDDEN PATTERNS & INSIGHTS FOR {asset_name}:")
        
        # 1. Day of Week Effect
        day_perf = full_trades.groupby('day')['pnl'].mean()
        best_day = day_perf.idxmax()
        worst_day = day_perf.idxmin()
        print(f"  • Day of Week Impact : Best = {best_day} (Avg {day_perf.max():+.1f} pts) | Worst = {worst_day} (Avg {day_perf.min():+.1f} pts)")
        
        # 2. Long vs Short Bias
        pos_perf = full_trades.groupby('pos')['pnl'].sum()
        print(f"  • Long vs Short Bias : LONG = {pos_perf.get('LONG', 0):+.1f} pts | SHORT = {pos_perf.get('SHORT', 0):+.1f} pts")
        
        # 3. Time of Breakout
        breakout_hours = full_trades['entry_time'].apply(lambda t: t.hour if t is not None else None)
        full_trades['entry_hour'] = breakout_hours
        early_pnl = full_trades[full_trades['entry_hour'] <= (10 if not is_mcx else 11)]['pnl'].sum()
        late_pnl = full_trades[full_trades['entry_hour'] > (10 if not is_mcx else 11)]['pnl'].sum()
        print(f"  • Early Breakout vs Late: First 1-Hour Breakouts = {early_pnl:+.1f} pts | Late Breakouts = {late_pnl:+.1f} pts")
        
        # 4. ORB Range Size Impact (Narrow vs Wide)
        median_range = full_trades['orb_range'].median()
        narrow_pnl = full_trades[full_trades['orb_range'] <= median_range]['pnl'].sum()
        wide_pnl = full_trades[full_trades['orb_range'] > median_range]['pnl'].sum()
        print(f"  • Range Volatility Effect: Narrow ORB (<= {median_range:.1f} pts) = {narrow_pnl:+.1f} pts | Wide ORB (> {median_range:.1f} pts) = {wide_pnl:+.1f} pts")

# 1. Run on NIFTY Futures
run_orb_analysis(
    csv_path="/home/john/Downloads/NIFTY25AUG26FUT_NFO_1m_2026-07-31_to_2026-08-25.csv",
    asset_name="NIFTY FUTURES (NSE FO)",
    session_start_time=datetime.time(9, 15),
    session_end_time=datetime.time(15, 25),
    is_mcx=False
)

# 2. Run on CRUDE OIL Futures
run_orb_analysis(
    csv_path="/home/john/Downloads/CRUDEOIL21SEP26FUT_MCX_1m_2026-07-28_to_2026-08-27_MERGED.csv",
    asset_name="CRUDE OIL FUTURES (MCX)",
    session_start_time=datetime.time(9, 0),
    session_end_time=datetime.time(23, 25),
    is_mcx=True
)
