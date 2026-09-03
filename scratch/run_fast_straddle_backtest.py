import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def norm_pdf(x):
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def bs_price(spot, strike, dte_days, iv_pct=14.0, opt_type="CE", rate_pct=6.5):
    T = max(dte_days / 365.0, 0.0001)
    sigma = max(iv_pct / 100.0, 0.01)
    r = rate_pct / 100.0
    S = float(spot)
    K = float(strike)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt_type.upper() == "CE":
        return max(S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2), 0.5)
    else:
        return max(K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1), 0.5)

def run_simulation():
    np.random.seed(42)
    trading_days = 250  # 1 full trading year
    lot_size = 50       # 1 Lot Nifty
    capital = 200000.0  # 2 Lakh margin
    sl_points = 30.0    # 30 pts stoploss per leg
    brokerage_per_day = 80.0 # Entry + Exit (4 orders @ 20) + STT/Taxes ~ Rs 150
    tax_friction = 70.0 # STT, GST, Exchange charges
    total_friction = brokerage_per_day + tax_friction
    
    dates = pd.date_range(end=datetime.now(), periods=trading_days, freq="B")
    
    trade_records = []
    equity = capital
    equity_curve = [equity]
    
    # Starting spot
    spot = 23500.0
    
    for i, dt in enumerate(dates):
        # Day of week for DTE (Weekly Expiry on Thursday: Monday=3 DTE, Tue=2 DTE, Wed=1 DTE, Thu=0.25 DTE, Fri=4 DTE)
        weekday = dt.weekday()
        days_to_exp = max((3 - weekday) % 7, 0.25)
        if days_to_exp == 0: days_to_exp = 0.25
        
        # IV fluctuations between 11% and 18%
        iv = np.random.uniform(11.5, 16.5)
        
        # Market regime: 60% Rangebound/Mild, 30% Directional Trend, 10% Choppy Whipsaw
        regime = np.random.choice(["SIDEWAYS", "TREND", "WHIPSAW"], p=[0.58, 0.32, 0.10])
        
        atm_strike = int(round(spot / 50.0) * 50)
        
        # Entry at 10:00 AM
        ce_entry = bs_price(spot, atm_strike, days_to_exp, iv, "CE")
        pe_entry = bs_price(spot, atm_strike, days_to_exp, iv, "PE")
        
        ce_sl = ce_entry + sl_points
        pe_sl = pe_entry + sl_points
        
        # Simulate 10:00 AM to 14:30 PM (4.5 hours = 54 5-minute bars)
        # Intraday spot movement
        if regime == "SIDEWAYS":
            intraday_move = np.random.normal(0, 0.0035) * spot  # ~ ±80 pts move
            vol_path = np.random.normal(0, 12, 54).cumsum()
        elif regime == "TREND":
            direction = 1 if np.random.rand() > 0.5 else -1
            intraday_move = direction * np.random.uniform(0.008, 0.018) * spot # ~ 200 - 400 pts trend
            vol_path = np.linspace(0, intraday_move, 54) + np.random.normal(0, 8, 54)
        else: # WHIPSAW
            intraday_move = np.random.normal(0, 0.002) * spot
            vol_path = np.sin(np.linspace(0, 3*np.pi, 54)) * 160 + np.random.normal(0, 10, 54)
            
        ce_active = True
        pe_active = True
        ce_exit = ce_entry
        pe_exit = pe_entry
        exit_reason = "14:30 PM (EOD Decay)"
        
        # Intraday bar simulation
        for b_idx in range(54):
            frac = (b_idx + 1) / 54.0
            curr_spot = spot + vol_path[b_idx]
            # Theta decay throughout the day
            curr_dte = max(days_to_exp - (frac * 0.75), 0.05)
            
            c_ce = bs_price(curr_spot, atm_strike, curr_dte, iv, "CE")
            c_pe = bs_price(curr_spot, atm_strike, curr_dte, iv, "PE")
            
            # Check CE SL
            if ce_active and c_ce >= ce_sl:
                ce_active = False
                ce_exit = ce_sl
                # Cost to cost for PE
                if pe_active:
                    pe_sl = pe_entry
                    
            # Check PE SL
            if pe_active and c_pe >= pe_sl:
                pe_active = False
                pe_exit = pe_sl
                # Cost to cost for CE
                if ce_active:
                    ce_sl = ce_entry
                    
            if not ce_active and not pe_active:
                exit_reason = "Both Legs SL Hit"
                break
                
        # If still active at 14:30 PM, exit at market price
        if ce_active:
            end_dte = max(days_to_exp - 0.70, 0.05)
            ce_exit = bs_price(spot + vol_path[-1], atm_strike, end_dte, iv, "CE")
        if pe_active:
            end_dte = max(days_to_exp - 0.70, 0.05)
            pe_exit = bs_price(spot + vol_path[-1], atm_strike, end_dte, iv, "PE")
            
        # PnL Calculation (Selling -> Profit = Entry - Exit)
        ce_pnl_pts = ce_entry - ce_exit
        pe_pnl_pts = pe_entry - pe_exit
        gross_pnl = (ce_pnl_pts + pe_pnl_pts) * lot_size
        net_pnl = gross_pnl - total_friction
        
        equity += net_pnl
        equity_curve.append(equity)
        
        trade_records.append({
            "date": dt.strftime("%Y-%m-%d"),
            "regime": regime,
            "ce_entry": round(ce_entry, 1),
            "pe_entry": round(pe_entry, 1),
            "ce_exit": round(ce_exit, 1),
            "pe_exit": round(pe_exit, 1),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "equity": round(equity, 2),
            "is_win": net_pnl > 0
        })
        
        # Spot drift to next day
        spot += np.random.normal(0, 0.007) * spot
        
    df_res = pd.DataFrame(trade_records)
    
    # Calculate Institutional Performance Metrics
    total_trades = len(df_res)
    winning_trades = df_res[df_res["net_pnl"] > 0]
    losing_trades = df_res[df_res["net_pnl"] <= 0]
    
    win_rate = (len(winning_trades) / total_trades) * 100
    total_gross = df_res["gross_pnl"].sum()
    total_net = df_res["net_pnl"].sum()
    
    total_gain = winning_trades["net_pnl"].sum()
    total_loss = abs(losing_trades["net_pnl"].sum())
    profit_factor = round(total_gain / (total_loss if total_loss > 0 else 1.0), 2)
    
    eq_series = pd.Series(equity_curve)
    cummax = eq_series.cummax()
    drawdown = cummax - eq_series
    max_dd = drawdown.max()
    max_dd_pct = (max_dd / cummax.max()) * 100
    
    avg_trade_pnl = df_res["net_pnl"].mean()
    avg_win = winning_trades["net_pnl"].mean()
    avg_loss = losing_trades["net_pnl"].mean()
    
    # Sharpe Ratio
    daily_returns = df_res["net_pnl"] / capital
    sharpe = (daily_returns.mean() / (daily_returns.std() + 1e-9)) * math.sqrt(252)
    
    print("\n" + "="*75)
    print("📈 NIFTY SAME-PREMIUM OPTION SELLER (10:00 -> 14:30) PERFORMANCE REPORT")
    print("="*75)
    print(f"⏱️  Backtest Horizon:        {total_trades} Trading Days (1 Full Year)")
    print(f"💼 Starting Capital:         ₹{capital:,.2f}")
    print(f"💰 Final Capital:            ₹{equity:,.2f}")
    print(f"🚀 Total Net Profit:         ₹{total_net:,.2f} ({((total_net/capital)*100):.2f}% ROI)")
    print(f"🎯 Win Rate:                 {win_rate:.2f}% ({len(winning_trades)} Wins / {len(losing_trades)} Losses)")
    print(f"📊 Profit Factor:            {profit_factor}")
    print(f"📉 Max Drawdown:             ₹{max_dd:,.2f} ({max_dd_pct:.2f}%)")
    print(f"💎 Sharpe Ratio:             {sharpe:.2f}")
    print(f"💵 Avg Profit / Day:         ₹{avg_trade_pnl:,.2f}")
    print(f"🟢 Avg Winning Trade:        ₹{avg_win:,.2f}")
    print(f"🔴 Avg Losing Trade:         ₹{avg_loss:,.2f}")
    print(f"⚖️  Risk : Reward (Payoff):   1 : {abs(avg_win/avg_loss):.2f}")
    print("="*75)
    
    # Breakdown by Market Condition
    print("\n📌 Breakdown by Market Regime:")
    for reg, grp in df_res.groupby("regime"):
        reg_wins = (grp["net_pnl"] > 0).sum()
        print(f"  • {reg.upper():<10} ({len(grp)} days): Net PnL: ₹{grp['net_pnl'].sum():>9,.2f} | Win Rate: {(reg_wins/len(grp))*100:>5.1f}%")
        
    return df_res

if __name__ == "__main__":
    run_simulation()
