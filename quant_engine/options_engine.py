"""
Multi-Leg Options Strategy & Greeks Engine (Opstra / Sensibull Style)
Supports Black-Scholes Greeks, Interactive Multi-Leg Payoff, Live Spot Fetching,
Dynamic Strike Selection, and Granular 9:20 Intraday Straddle Simulation.
"""

import math
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

# Pure Python standard normal distribution functions (Zero scipy dependency)
def norm_pdf(x: float) -> float:
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

# Universal OpenAlgo Instruments Catalog (Indices, MCX Commodities, Stock F&O, Equities)
INSTRUMENT_CATALOG: Dict[str, Dict[str, Any]] = {
    # 1. Major Indian Indices
    "NIFTY": {"name": "NIFTY 50", "category": "INDEX", "exchange": "NSE_INDEX", "opt_exchange": "NFO", "strike_step": 50, "lot_size": 65, "baseline_spot": 24500.0, "expiry_day": 3},
    "BANKNIFTY": {"name": "BANK NIFTY", "category": "INDEX", "exchange": "NSE_INDEX", "opt_exchange": "NFO", "strike_step": 100, "lot_size": 15, "baseline_spot": 51200.0, "expiry_day": 2},
    "FINNIFTY": {"name": "NIFTY FINANCIAL SERVICES", "category": "INDEX", "exchange": "NSE_INDEX", "opt_exchange": "NFO", "strike_step": 50, "lot_size": 65, "baseline_spot": 23400.0, "expiry_day": 1},
    "MIDCPNIFTY": {"name": "NIFTY MIDCAP SELECT", "category": "INDEX", "exchange": "NSE_INDEX", "opt_exchange": "NFO", "strike_step": 25, "lot_size": 120, "baseline_spot": 12800.0, "expiry_day": 0},
    "SENSEX": {"name": "BSE SENSEX", "category": "INDEX", "exchange": "BSE_INDEX", "opt_exchange": "BFO", "strike_step": 100, "lot_size": 10, "baseline_spot": 80400.0, "expiry_day": 4},
    "BANKEX": {"name": "BSE BANKEX", "category": "INDEX", "exchange": "BSE_INDEX", "opt_exchange": "BFO", "strike_step": 100, "lot_size": 15, "baseline_spot": 57800.0, "expiry_day": 4},

    # 2. MCX Commodities (Options & Futures)
    "CRUDEOIL": {"name": "MCX CRUDE OIL (100 BBL)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 50, "lot_size": 100, "baseline_spot": 6400.0, "expiry_day": 1},
    "CRUDEOILM": {"name": "MCX CRUDE OIL MINI (10 BBL)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 50, "lot_size": 10, "baseline_spot": 6400.0, "expiry_day": 1},
    "NATURALGAS": {"name": "MCX NATURAL GAS (1250 mmBtu)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 5, "lot_size": 1250, "baseline_spot": 195.0, "expiry_day": 2},
    "NATGASMINI": {"name": "MCX NATURAL GAS MINI (250 mmBtu)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 5, "lot_size": 250, "baseline_spot": 195.0, "expiry_day": 2},
    "GOLD": {"name": "MCX GOLD (1 KG)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 100, "lot_size": 100, "baseline_spot": 72500.0, "expiry_day": 4},
    "GOLDM": {"name": "MCX GOLD MINI (100 GM)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 100, "lot_size": 10, "baseline_spot": 72500.0, "expiry_day": 4},
    "SILVER": {"name": "MCX SILVER (30 KG)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 500, "lot_size": 30, "baseline_spot": 85000.0, "expiry_day": 3},
    "SILVERM": {"name": "MCX SILVER MINI (5 KG)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 500, "lot_size": 5, "baseline_spot": 85000.0, "expiry_day": 3},
    "COPPER": {"name": "MCX COPPER (2500 KG)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 5, "lot_size": 2500, "baseline_spot": 820.0, "expiry_day": 3},
    "ZINC": {"name": "MCX ZINC (5000 KG)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 2.5, "lot_size": 5000, "baseline_spot": 275.0, "expiry_day": 3},
    "ALUMINIUM": {"name": "MCX ALUMINIUM (5000 KG)", "category": "COMMODITY", "exchange": "MCX", "opt_exchange": "MCX", "strike_step": 2.5, "lot_size": 5000, "baseline_spot": 235.0, "expiry_day": 3},

    # 3. High-Volume Stock Futures & Options
    "RELIANCE": {"name": "RELIANCE INDUSTRIES", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 20, "lot_size": 250, "baseline_spot": 3000.0, "expiry_day": 3},
    "HDFCBANK": {"name": "HDFC BANK", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 10, "lot_size": 550, "baseline_spot": 1650.0, "expiry_day": 3},
    "ICICIBANK": {"name": "ICICI BANK", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 10, "lot_size": 700, "baseline_spot": 1200.0, "expiry_day": 3},
    "SBIN": {"name": "STATE BANK OF INDIA", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 5, "lot_size": 750, "baseline_spot": 820.0, "expiry_day": 3},
    "INFY": {"name": "INFOSYS", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 20, "lot_size": 400, "baseline_spot": 1850.0, "expiry_day": 3},
    "TCS": {"name": "TATA CONSULTANCY SERVICES", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 50, "lot_size": 175, "baseline_spot": 4400.0, "expiry_day": 3},
    "TATAMOTORS": {"name": "TATA MOTORS", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 10, "lot_size": 575, "baseline_spot": 1050.0, "expiry_day": 3},
    "BAJFINANCE": {"name": "BAJAJ FINANCE", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 50, "lot_size": 125, "baseline_spot": 7200.0, "expiry_day": 3},
    "AXISBANK": {"name": "AXIS BANK", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 10, "lot_size": 625, "baseline_spot": 1180.0, "expiry_day": 3},
    "BHARTIARTL": {"name": "BHARTI AIRTEL", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 10, "lot_size": 475, "baseline_spot": 1550.0, "expiry_day": 3},
    "LT": {"name": "LARSEN & TOUBRO", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 25, "lot_size": 175, "baseline_spot": 3600.0, "expiry_day": 3},
    "KOTAKBANK": {"name": "KOTAK MAHINDRA BANK", "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO", "strike_step": 10, "lot_size": 400, "baseline_spot": 1800.0, "expiry_day": 3}
}

class OptionsGreeksEngine:
    @staticmethod
    def calculate_greeks(spot: float, strike: float, time_to_expiry_days: float, iv_pct: float, rate_pct: float = 6.5, opt_type: str = "CE") -> Dict[str, float]:
        """
        Computes Black-Scholes theoretical price & Greeks.
        """
        T = max(time_to_expiry_days / 365.0, 0.0001)
        sigma = max(iv_pct / 100.0, 0.01)
        r = rate_pct / 100.0
        S = float(spot)
        K = float(strike)
        
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
        vega = S * norm_pdf(d1) * math.sqrt(T) / 100.0
        
        if opt_type.upper() == "CE":
            price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
            delta = norm_cdf(d1)
            theta = (- (S * norm_pdf(d1) * sigma) / (2.0 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365.0
        else:
            price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
            delta = norm_cdf(d1) - 1.0
            theta = (- (S * norm_pdf(d1) * sigma) / (2.0 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0
            
        return {
            "price": max(round(price, 2), 0.5),
            "delta": round(delta, 3),
            "gamma": round(gamma, 5),
            "theta": round(theta, 2),
            "vega": round(vega, 2)
        }

    @classmethod
    def generate_payoff(cls, spot: float, legs: List[Dict[str, Any]], days_to_expiry: float = 4.0, iv: float = 14.0) -> Dict[str, Any]:
        """
        Generates Multi-Leg Payoff curves (T+0 vs Expiry), Greeks and Breakevens.
        """
        if not legs:
            return {
                "spot_prices": [], "expiry_payoff": [], "t0_payoff": [],
                "max_profit": 0, "max_loss": 0, "breakevens": [], "pop_pct": 50.0,
                "portfolio_greeks": {"delta": 0, "theta": 0, "vega": 0}
            }

        spot_range = np.linspace(spot * 0.94, spot * 1.06, 120)
        expiry_payoffs = []
        t0_payoffs = []
        
        total_delta = 0.0
        total_theta = 0.0
        total_vega = 0.0
        
        for leg in legs:
            action_mult = 1 if leg["action"].upper() == "BUY" else -1
            qty = int(leg.get("quantity", 50))
            k = float(leg["strike"])
            prem = float(leg.get("premium", 0.0))
            opt = leg["opt_type"].upper()
            
            # Compute Greek contributions
            greeks = cls.calculate_greeks(spot, k, days_to_expiry, iv, opt_type=opt)
            total_delta += greeks["delta"] * action_mult * qty
            total_theta += greeks["theta"] * action_mult * qty
            total_vega += greeks["vega"] * action_mult * qty
        
        for s_eval in spot_range:
            pnl_exp = 0.0
            pnl_t0 = 0.0
            for leg in legs:
                action_mult = 1 if leg["action"].upper() == "BUY" else -1
                qty = int(leg.get("quantity", 50))
                k = float(leg["strike"])
                prem = float(leg.get("premium", 0.0))
                opt = leg["opt_type"].upper()
                
                # Expiry payoff
                if opt == "CE":
                    intrinsic = max(s_eval - k, 0.0)
                else:
                    intrinsic = max(k - s_eval, 0.0)
                pnl_exp += (intrinsic - prem) * action_mult * qty
                
                # T+0 Payoff
                t0_greeks = cls.calculate_greeks(s_eval, k, days_to_expiry, iv, opt_type=opt)
                t0_price = t0_greeks["price"]
                pnl_t0 += (t0_price - prem) * action_mult * qty
                
            expiry_payoffs.append(round(pnl_exp, 2))
            t0_payoffs.append(round(pnl_t0, 2))
            
        max_profit = round(max(expiry_payoffs), 2)
        min_profit = round(min(expiry_payoffs), 2)
        
        # Calculate Breakevens
        breakevens = []
        for j in range(1, len(expiry_payoffs)):
            if (expiry_payoffs[j-1] <= 0 and expiry_payoffs[j] > 0) or (expiry_payoffs[j-1] >= 0 and expiry_payoffs[j] < 0):
                be_spot = spot_range[j]
                breakevens.append(round(be_spot, 0))
                
        # Probability of Profit (POP)
        if len(breakevens) >= 2:
            be_low, be_high = min(breakevens), max(breakevens)
            std_move = spot * (iv / 100.0) * math.sqrt(days_to_expiry / 365.0)
            if std_move > 0:
                z_low = (be_low - spot) / std_move
                z_high = (be_high - spot) / std_move
                pop_pct = round((norm_cdf(z_high) - norm_cdf(z_low)) * 100.0, 1)
            else:
                pop_pct = 68.0
        else:
            pop_pct = 65.0
            
        return {
            "spot_prices": [round(s, 1) for s in spot_range],
            "expiry_payoff": expiry_payoffs,
            "t0_payoff": t0_payoffs,
            "max_profit": max_profit if max_profit < 500000 else "Unlimited",
            "max_loss": min_profit if min_profit > -500000 else "Unlimited",
            "breakevens": breakevens,
            "pop_pct": min(max(pop_pct, 10.0), 95.0),
            "portfolio_greeks": {
                "delta": round(total_delta, 2),
                "theta": round(total_theta, 2),
                "vega": round(total_vega, 2)
            }
        }

    @classmethod
    def get_market_spot_and_strikes(cls, symbol: str = "NIFTY", iv: float = 14.0, days: float = 4.0) -> Dict[str, Any]:
        """
        Fetches live/latest spot price and generates strike matrix around ATM with revised lot sizes
        across all OpenAlgo asset classes (Indices, Commodities, Stocks).
        """
        sym = symbol.upper()
        meta = INSTRUMENT_CATALOG.get(sym, {
            "name": sym, "category": "STOCK", "exchange": "NSE", "opt_exchange": "NFO",
            "strike_step": 50, "lot_size": 50, "baseline_spot": 1000.0, "expiry_day": 3
        })
        
        strike_step = meta.get("strike_step", 50)
        lot_size = meta.get("lot_size", 50)
        spot = meta.get("baseline_spot", 1000.0)
        exchange = meta.get("exchange", "NSE")

        # Attempt to fetch latest real spot from historical / broker feed
        try:
            from quant_engine.backtester import BacktestEngine
            engine = BacktestEngine({"symbol": sym, "exchange": exchange, "timeframe": "5m"})
            today = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            df = engine.fetch_data(start, today)
            if not df.empty:
                spot = float(df.iloc[-1]["close"])
        except Exception:
            pass

        atm_strike = int(round(spot / strike_step) * strike_step)
        
        # Generate 15 strikes below and above ATM
        strikes_data = []
        for i in range(-12, 13):
            k = atm_strike + (i * strike_step)
            ce_greeks = cls.calculate_greeks(spot, k, days, iv, opt_type="CE")
            pe_greeks = cls.calculate_greeks(spot, k, days, iv, opt_type="PE")
            
            tag = "ATM" if k == atm_strike else (f"OTM +{abs(i)*strike_step}" if (i > 0) else f"ITM -{abs(i)*strike_step}")
            
            strikes_data.append({
                "strike": k,
                "label": f"{k} ({'ATM' if k == atm_strike else tag})",
                "is_atm": (k == atm_strike),
                "ce_price": ce_greeks["price"],
                "pe_price": pe_greeks["price"],
                "ce_delta": ce_greeks["delta"],
                "pe_delta": pe_greeks["delta"],
                "ce_theta": ce_greeks["theta"],
                "pe_theta": pe_greeks["theta"]
            })

        return {
            "symbol": sym,
            "name": meta.get("name", sym),
            "category": meta.get("category", "INDEX"),
            "exchange": exchange,
            "opt_exchange": meta.get("opt_exchange", "NFO"),
            "spot_price": round(spot, 2),
            "atm_strike": atm_strike,
            "strike_step": strike_step,
            "lot_size": lot_size,
            "strikes": strikes_data
        }


class IntradayStraddleBacktester:
    @staticmethod
    def _get_dte_for_date(date_str: str, symbol: str = "NIFTY") -> float:
        """Calculates exact remaining days to weekly/monthly expiry."""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            w = dt.weekday()  # Mon=0, Tue=1, Wed=2, Thu=3, Fri=4
            meta = INSTRUMENT_CATALOG.get(symbol.upper(), {})
            exp_day = meta.get("expiry_day", 3)
            days = (exp_day - w) % 7
            if days == 0:
                return 0.25  # Expiry day ~ 6 trading hours remaining
            return float(days) + 0.25
        except Exception:
            return 3.0

    @classmethod
    def _fetch_real_option_candles(cls, symbol_name: str, strike: int, opt_type: str, date_str: str) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
        """
        Queries OpenAlgo Database & Broker API for authentic 5-minute historical candles of real option contract.
        """
        try:
            import sqlite3
            from database.auth_db import get_auth_token
            from services.history_service import get_history_with_auth

            con = sqlite3.connect("db/openalgo.db")
            cur = con.cursor()
            row = cur.execute("SELECT name, broker FROM auth WHERE is_revoked=0 LIMIT 1").fetchone()
            if not row:
                con.close()
                return None, None
            username, broker = row
            auth_token = get_auth_token(username)

            cur.execute("SELECT symbol, exchange FROM symtoken WHERE name=? AND (strike=? OR strike BETWEEN ?-1 AND ?+1) AND instrumenttype=? LIMIT 1", (symbol_name, strike, strike, strike, opt_type))
            res = cur.fetchone()
            con.close()
            if not res:
                return None, None
            opt_sym, exch = res

            success, resp, _ = get_history_with_auth(auth_token, None, broker, opt_sym, exch, "5m", date_str, date_str)
            if success and isinstance(resp, dict) and resp.get("data"):
                df = pd.DataFrame(resp["data"])
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
                df["time_str"] = df["datetime"].dt.strftime("%H:%M")
                return opt_sym, df
        except Exception:
            pass
        return None, None

    @classmethod
    def simulate_920_straddle(
        cls,
        df_spot: pd.DataFrame,
        symbol: str = "NIFTY",
        entry_time: str = "09:20",
        exit_time: str = "15:15",
        strike_selection: str = "ATM",  # "ATM" or "MATCHED_PREMIUM"
        sl_mode: str = "INDIVIDUAL",  # "INDIVIDUAL", "COST_TO_COST", "COMBINED"
        sl_leg_pct: float = 25.0,
        lot_size: int = 65,
        iv: float = 14.0,
        slippage_pct: float = 0.05,
        brokerage: float = 80.0,
        strike_step: int = 50
    ) -> Dict[str, Any]:
        """
        Simulates Daily Intraday Short Straddle/Strangle on authentic OpenAlgo Broker Data
        using REAL OPTION CONTRACT CANDLES from Fyers/Broker feed, with ZERO look-ahead bias.
        """
        if df_spot.empty or "date_str" not in df_spot.columns:
            return {"total_days": 0, "win_rate": 0, "profit_factor": 0, "total_net_pnl": 0, "trade_logs": [], "equity_curve": []}
            
        trades = []
        capital = 200000.0  # Standard 2 Lakh margin per 1 Lot Straddle
        equity = capital
        equity_curve = []
        
        grouped = df_spot.groupby("date_str")
        
        for date, group in grouped:
            day_candles = group.sort_values("datetime").reset_index(drop=True)
            trade_candles = day_candles[(day_candles["time_str"] >= entry_time) & (day_candles["time_str"] <= exit_time)]
            if trade_candles.empty or len(trade_candles) < 5:
                continue
                
            entry_row = trade_candles.iloc[0]
            spot_entry = float(entry_row["open"])
            atm_strike = int(round(spot_entry / strike_step) * strike_step)
            dte_base = cls._get_dte_for_date(date, symbol)
            
            # Strike Selection
            if strike_selection == "MATCHED_PREMIUM":
                ce_candidates = [k for k in [atm_strike, atm_strike + strike_step, atm_strike + 2*strike_step, atm_strike + 3*strike_step] if k >= spot_entry - strike_step/2]
                pe_candidates = [k for k in [atm_strike, atm_strike - strike_step, atm_strike - 2*strike_step, atm_strike - 3*strike_step] if k <= spot_entry + strike_step/2]
                
                best_pair = (atm_strike, atm_strike)
                min_diff = 999999.0
                for ce_k in ce_candidates:
                    ce_p = OptionsGreeksEngine.calculate_greeks(spot_entry, ce_k, dte_base, iv, opt_type="CE")["price"]
                    for pe_k in pe_candidates:
                        pe_p = OptionsGreeksEngine.calculate_greeks(spot_entry, pe_k, dte_base, iv, opt_type="PE")["price"]
                        diff = abs(ce_p - pe_p)
                        if diff < min_diff:
                            min_diff = diff
                            best_pair = (ce_k, pe_k)
                ce_strike, pe_strike = best_pair
            else:
                ce_strike = atm_strike
                pe_strike = atm_strike

            # Attempt to fetch 100% REAL OPTION CANDLES from OpenAlgo Broker Feed
            real_ce_sym, df_real_ce = cls._fetch_real_option_candles(symbol, ce_strike, "CE", date)
            real_pe_sym, df_real_pe = cls._fetch_real_option_candles(symbol, pe_strike, "PE", date)

            use_real_candles = (
                df_real_ce is not None and not df_real_ce.empty and
                df_real_pe is not None and not df_real_pe.empty
            )

            if use_real_candles:
                # Align real option candles to entry and exit windows
                df_ce_filt = df_real_ce[(df_real_ce["time_str"] >= entry_time) & (df_real_ce["time_str"] <= exit_time)].reset_index(drop=True)
                df_pe_filt = df_real_pe[(df_real_pe["time_str"] >= entry_time) & (df_real_pe["time_str"] <= exit_time)].reset_index(drop=True)
                
                if not df_ce_filt.empty and not df_pe_filt.empty:
                    ce_entry_prem = round(float(df_ce_filt.iloc[0]["open"]), 2)
                    pe_entry_prem = round(float(df_pe_filt.iloc[0]["open"]), 2)
                    data_source = "REAL BROKER FEED"
                else:
                    use_real_candles = False

            if not use_real_candles:
                # Theoretical Greeks Fallback for older expired dates
                ce_greeks_entry = OptionsGreeksEngine.calculate_greeks(spot_entry, ce_strike, dte_base, iv, opt_type="CE")
                pe_greeks_entry = OptionsGreeksEngine.calculate_greeks(spot_entry, pe_strike, dte_base, iv, opt_type="PE")
                ce_entry_prem = max(round(ce_greeks_entry["price"], 2), 5.0)
                pe_entry_prem = max(round(pe_greeks_entry["price"], 2), 5.0)
                real_ce_sym = f"{symbol}_{ce_strike}CE"
                real_pe_sym = f"{symbol}_{pe_strike}PE"
                data_source = "GREEKS MODEL"

            combined_entry = round(ce_entry_prem + pe_entry_prem, 2)
            combined_sl_level = round(combined_entry * (1.0 + (sl_leg_pct / 100.0)), 2)
            
            ce_sl_price = round(ce_entry_prem * (1.0 + (sl_leg_pct / 100.0)), 2)
            pe_sl_price = round(pe_entry_prem * (1.0 + (sl_leg_pct / 100.0)), 2)
            
            ce_active = True
            pe_active = True
            ce_exit_prem = 0.0
            pe_exit_prem = 0.0
            ce_exit_time = f"{exit_time} (EOD)"
            pe_exit_time = f"{exit_time} (EOD)"
            
            spot_exit = float(trade_candles.iloc[-1]["close"])
            total_bars = len(trade_candles)
            
            # Bar-by-bar chronological execution
            for bar_idx, (_, candle) in enumerate(trade_candles.iterrows()):
                c_spot = candle["close"]
                c_time = candle["time_str"]
                
                if use_real_candles:
                    c_ce_bar = df_ce_filt.iloc[min(bar_idx, len(df_ce_filt)-1)]
                    c_pe_bar = df_pe_filt.iloc[min(bar_idx, len(df_pe_filt)-1)]
                    ce_eval = float(c_ce_bar["close"])
                    pe_eval = float(c_pe_bar["close"])
                    ce_high = float(c_ce_bar["high"])
                    pe_high = float(c_pe_bar["high"])
                else:
                    intraday_decay_frac = (bar_idx / max(total_bars, 1)) * 0.85
                    curr_dte = max(dte_base - intraday_decay_frac, 0.001)
                    ce_eval = OptionsGreeksEngine.calculate_greeks(c_spot, ce_strike, curr_dte, iv, opt_type="CE")["price"]
                    pe_eval = OptionsGreeksEngine.calculate_greeks(c_spot, pe_strike, curr_dte, iv, opt_type="PE")["price"]
                    ce_high = ce_eval
                    pe_high = pe_eval

                if sl_mode == "COMBINED":
                    curr_combined = round(ce_eval + pe_eval, 2)
                    if curr_combined >= combined_sl_level:
                        ce_active = False
                        pe_active = False
                        ce_exit_prem = round(ce_eval, 2)
                        pe_exit_prem = round(pe_eval, 2)
                        ce_exit_time = f"{c_time} (Combined SL)"
                        pe_exit_time = f"{c_time} (Combined SL)"
                        break
                else:
                    if ce_active and ce_high >= ce_sl_price:
                        ce_active = False
                        ce_exit_prem = ce_sl_price
                        ce_exit_time = f"{c_time} (SL Hit)"
                        if sl_mode == "COST_TO_COST" and pe_active:
                            pe_sl_price = pe_entry_prem
                            
                    if pe_active and pe_high >= pe_sl_price:
                        pe_active = False
                        pe_exit_prem = pe_sl_price
                        pe_exit_time = f"{c_time} (Cost SL Hit)" if (sl_mode == "COST_TO_COST" and pe_sl_price == pe_entry_prem) else f"{c_time} (SL Hit)"
                        if sl_mode == "COST_TO_COST" and ce_active:
                            ce_sl_price = ce_entry_prem
                            
                if not ce_active and not pe_active:
                    break
                    
            # EOD square-off
            if use_real_candles:
                if ce_active:
                    ce_exit_prem = round(float(df_ce_filt.iloc[-1]["close"]), 2)
                if pe_active:
                    pe_exit_prem = round(float(df_pe_filt.iloc[-1]["close"]), 2)
            else:
                dte_eod = max(dte_base - 0.85, 0.001)
                if ce_active:
                    ce_eod_eval = OptionsGreeksEngine.calculate_greeks(spot_exit, ce_strike, dte_eod, iv, opt_type="CE")["price"]
                    ce_exit_prem = round(max(ce_eod_eval, 0.5), 2)
                if pe_active:
                    pe_eod_eval = OptionsGreeksEngine.calculate_greeks(spot_exit, pe_strike, dte_eod, iv, opt_type="PE")["price"]
                    pe_exit_prem = round(max(pe_eod_eval, 0.5), 2)
                
            ce_pnl = round((ce_entry_prem - ce_exit_prem) * lot_size, 2)
            pe_pnl = round((pe_entry_prem - pe_exit_prem) * lot_size, 2)
            gross_pnl = round(ce_pnl + pe_pnl, 2)
            
            friction = round((abs(gross_pnl) * (slippage_pct / 100.0)) + brokerage, 2)
            net_pnl = round(gross_pnl - friction, 2)
            
            if ce_active and pe_active:
                outcome = "PROFIT (BOTH DECAYED)"
            elif not ce_active and pe_active:
                outcome = "CE SL HIT (PE PROFIT)" if pe_pnl > 0 else "CE SL HIT (PE LOSS)"
            elif ce_active and not pe_active:
                outcome = "PE SL HIT (CE PROFIT)" if ce_pnl > 0 else "PE SL HIT (CE LOSS)"
            elif "Combined" in ce_exit_time:
                outcome = "COMBINED SL HIT"
            elif "Cost" in ce_exit_time or "Cost" in pe_exit_time:
                outcome = "1 SL + 1 COST EXIT (SAVED)"
            else:
                outcome = "BOTH SL HIT (WHIPSAW)"
                
            equity += net_pnl
            
            trades.append({
                "date": date,
                "data_source": data_source,
                "spot_0920": round(spot_entry, 1),
                "atm_strike": atm_strike,
                "ce_strike": ce_strike,
                "pe_strike": pe_strike,
                "ce_symbol": real_ce_sym,
                "pe_symbol": real_pe_sym,
                "ce_entry": ce_entry_prem,
                "ce_exit": ce_exit_prem,
                "ce_exit_time": ce_exit_time,
                "pe_entry": pe_entry_prem,
                "pe_exit": pe_exit_prem,
                "pe_exit_time": pe_exit_time,
                "spot_1515": round(spot_exit, 1),
                "ce_pnl": ce_pnl,
                "pe_pnl": pe_pnl,
                "gross_pnl": gross_pnl,
                "friction": friction,
                "net_pnl": net_pnl,
                "outcome": outcome
            })
            equity_curve.append({"date": date, "equity": round(equity, 2)})
            
        tdf = pd.DataFrame(trades) if trades else pd.DataFrame()
        wins = tdf[tdf["net_pnl"] > 0] if not tdf.empty else pd.DataFrame()
        losses = tdf[tdf["net_pnl"] <= 0] if not tdf.empty else pd.DataFrame()
        
        total_days = len(tdf)
        win_days = len(wins)
        loss_days = len(losses)
        win_rate = round((win_days / total_days) * 100, 2) if total_days > 0 else 0
        
        gross_profit = wins["net_pnl"].sum() if not wins.empty else 0.0
        gross_loss = abs(losses["net_pnl"].sum()) if not losses.empty else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        total_net_pnl = round(tdf["net_pnl"].sum(), 2) if not tdf.empty else 0.0
        
        # Max drawdown % calculation
        max_dd_pct = 0.0
        if equity_curve:
            eq_series = pd.Series([e["equity"] for e in equity_curve])
            peak = eq_series.cummax()
            dd = (eq_series - peak) / peak * 100.0
            max_dd_pct = round(abs(dd.min()), 2)

        return {
            "total_days": total_days,
            "win_days": win_days,
            "loss_days": loss_days,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_dd_pct,
            "total_net_pnl": total_net_pnl,
            "trade_logs": trades,
            "equity_curve": equity_curve
        }
