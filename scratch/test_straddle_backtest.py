import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, "/home/john/openalgo")
from quant_engine.options_engine import IntradayStraddleBacktester, OptionsGreeksEngine
from quant_engine.backtester import BacktestEngine

print("🚀 Running NIFTY Same-Premium Straddle Backtest Simulation...")

# 1. Fetch NIFTY Spot 5m candles
engine = BacktestEngine({
    "symbol": "NIFTY 50",
    "exchange": "NSE_INDEX",
    "timeframe": "5m",
    "capital": 200000.0,
    "quantity": 50
})

end_d = datetime.now().strftime("%Y-%m-%d")
start_d = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

try:
    df_spot = engine.fetch_data(start_d, end_d)
    print(f"✅ Fetched {len(df_spot)} spot candle bars across dates: {df_spot['date_str'].nunique()} trading days")
except Exception as e:
    print(f"⚠️ Live history fetch error: {e}, using sample historical data")
    # Generate realistic Nifty price action over 60 days
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=45, freq="B").strftime("%Y-%m-%d")
    rows = []
    base_price = 24300.0
    for d in dates:
        times = [f"{h:02d}:{m:02d}" for h in range(9, 16) for m in range(0, 60, 5) if not (h==9 and m<15) and not (h==15 and m>30)]
        daily_drift = np.random.normal(0, 0.006)
        day_spot = base_price * (1 + daily_drift)
        base_price = day_spot
        for t in times:
            noise = np.random.normal(0, 0.001)
            p = day_spot * (1 + noise)
            rows.append({
                "date_str": d,
                "time_str": t,
                "datetime": pd.to_datetime(f"{d} {t}"),
                "open": p, "high": p*1.0005, "low": p*0.9995, "close": p,
                "volume": 1000
            })
    df_spot = pd.DataFrame(rows)

# Run Simulation 1: Cost-to-Cost Leg SL (30 Pts)
res_c2c = IntradayStraddleBacktester.simulate_920_straddle(
    df_spot=df_spot,
    symbol="NIFTY",
    entry_time="10:00",
    exit_time="14:30",
    strike_selection="ATM",
    sl_mode="COST_TO_COST",
    sl_leg_pct=25.0, # ~30 pts on 120 Rs option
    lot_size=50,
    iv=13.5,
    slippage_pct=0.05,
    brokerage=80.0
)

# Run Simulation 2: Combined SL
res_comb = IntradayStraddleBacktester.simulate_920_straddle(
    df_spot=df_spot,
    symbol="NIFTY",
    entry_time="10:00",
    exit_time="14:30",
    strike_selection="ATM",
    sl_mode="COMBINED",
    sl_leg_pct=25.0,
    lot_size=50,
    iv=13.5,
    slippage_pct=0.05,
    brokerage=80.0
)

print("\n" + "="*70)
print("📊 BACKTEST RESULTS: NIFTY 10:00 -> 14:30 STRADDLE SELLER BOT")
print("="*70)

def print_metrics(label, res):
    print(f"\n--- {label} ---")
    print(f"📅 Total Trading Days:   {res.get('total_days', 0)}")
    print(f"🎯 Total Trades Taken:   {res.get('total_trades', res.get('total_days', 0))}")
    print(f"🏆 Win Rate:             {res.get('win_rate', 0):.2f}%")
    print(f"💰 Total Net Profit:     ₹{res.get('total_net_pnl', 0):,.2f}")
    print(f"📈 Profit Factor:        {res.get('profit_factor', 0):.2f}")
    print(f"📉 Max Drawdown:         ₹{res.get('max_drawdown', 0):,.2f}")
    print(f"💵 Avg Profit / Day:     ₹{res.get('avg_pnl_per_day', (res.get('total_net_pnl', 0)/(res.get('total_days') or 1))):,.2f}")

print_metrics("MODE 1: Leg SL with Move to Cost-to-Cost (30 Pts)", res_c2c)
print_metrics("MODE 2: Combined SL (30 Pts Total)", res_comb)

