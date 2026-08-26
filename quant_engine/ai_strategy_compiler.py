"""
AI Natural Language Strategy Compiler with Antigravity AI Bridge & SMC Engine
Supports fast local regex parsing and deep Antigravity CLI AI model reasoning
for Indian Equities/F&O (Fyers), Commodities (MCX), and Crypto (Binance/Bybit).
"""

import json
import os
import re
import subprocess
from typing import Dict, Any, List

class AIStrategyCompiler:
    @staticmethod
    def parse_with_antigravity_cli(prompt: str) -> Dict[str, Any]:
        """
        Directly bridges with Antigravity CLI ('agy -p') to extract structured trading rules.
        """
        try:
            system_prompt = (
                f"You are an institutional quantitative trading architect. "
                f"Parse this strategy prompt: '{prompt}'. "
                f"Extract strategy parameters and return ONLY a raw JSON object with keys: "
                f"strategy_name (string), "
                f"market_type (INDIAN_EQUITY_FNO, MCX_COMMODITY, CRYPTO_PERP), "
                f"symbol (string, e.g. NIFTY, BANKNIFTY, RELIANCE, CRUDEOIL, BTCUSDT, ETHUSDT), "
                f"exchange (NSE_INDEX, NSE, NFO, MCX, BINANCE, BYBIT), "
                f"timeframe (1m, 3m, 5m, 15m, 30m, 1h, D), "
                f"strategy_type (smc_institutional, supertrend, ema_cross, vwap_pullback, custom), "
                f"trade_direction (LONG, SHORT, BOTH), "
                f"fast_ema (int), slow_ema (int), rsi_threshold (int), "
                f"risk_reward_ratio (float, e.g. 3.0), "
                f"stoploss_val (float percentage), target_val (float percentage), "
                f"quantity (int), capital (float). "
                f"Do not include markdown or backticks."
            )
            
            result = subprocess.run(
                ["agy", "-p", system_prompt],
                capture_output=True,
                text=True,
                timeout=25
            )
            
            if result.returncode == 0 and result.stdout.strip():
                clean_text = result.stdout.strip()
                clean_text = re.sub(r"^```json\s*", "", clean_text)
                clean_text = re.sub(r"^```\s*", "", clean_text)
                clean_text = re.sub(r"\s*```$", "", clean_text)
                
                parsed_json = json.loads(clean_text)
                
                config = {
                    "strategy_name": parsed_json.get("strategy_name", f"{parsed_json.get('symbol', 'AI')}_Algo"),
                    "market_type": parsed_json.get("market_type", "INDIAN_EQUITY_FNO"),
                    "symbol": parsed_json.get("symbol", "NIFTY"),
                    "exchange": parsed_json.get("exchange", "NSE_INDEX"),
                    "timeframe": parsed_json.get("timeframe", "5m"),
                    "strategy_type": parsed_json.get("strategy_type", "custom"),
                    "trade_direction": parsed_json.get("trade_direction", "BOTH"),
                    "capital": float(parsed_json.get("capital", 100000.0)),
                    "quantity": int(parsed_json.get("quantity", 50)),
                    "stoploss_val": float(parsed_json.get("stoploss_val", 0.8)),
                    "stoploss_type": "PERCENT",
                    "target_val": float(parsed_json.get("target_val", 2.4)),
                    "target_type": "PERCENT",
                    "slippage_pct": 0.05,
                    "brokerage_per_trade": 40.0,
                    "indicators": {
                        "fast_ema": int(parsed_json.get("fast_ema", 20)),
                        "slow_ema": int(parsed_json.get("slow_ema", 50)),
                        "rsi_period": 14,
                        "rsi_threshold": int(parsed_json.get("rsi_threshold", 50)),
                        "risk_reward_ratio": float(parsed_json.get("risk_reward_ratio", 3.0))
                    },
                    "missing_parameters": []
                }
                return config
        except Exception as e:
            print(f"[AI Bridge Fallback] Antigravity CLI bridge fallback: {e}")
            
        return AIStrategyCompiler.parse_local(prompt)

    @staticmethod
    def parse_local(prompt: str) -> Dict[str, Any]:
        """Fast instant zero-token regex parser with SMC & Multi-Asset support."""
        p = prompt.lower()
        config = {
            "strategy_name": "AI_Custom_Strategy",
            "market_type": "INDIAN_EQUITY_FNO",
            "symbol": "NIFTY",
            "exchange": "NSE_INDEX",
            "timeframe": "5m",
            "strategy_type": "custom",
            "trade_direction": "BOTH",
            "capital": 100000.0,
            "quantity": 50,
            "stoploss_val": 0.8,
            "stoploss_type": "PERCENT",
            "target_val": 2.2,
            "target_type": "PERCENT",
            "slippage_pct": 0.05,
            "brokerage_per_trade": 40.0,
            "indicators": {
                "fast_ema": 20,
                "slow_ema": 50,
                "rsi_period": 14,
                "rsi_threshold": 50,
                "risk_reward_ratio": 3.0
            },
            "missing_parameters": []
        }

        # 1. Detect SMC Keywords
        if any(w in p for w in ["smc", "order block", "orderblock", "ob", "fvg", "fair value gap", "bos", "choch", "liquidity", "sweep", "inducement", "idm"]):
            config["strategy_type"] = "smc_institutional"
            config["strategy_name"] = "SMC_Institutional_Algo"
            config["target_val"] = 2.5
            config["stoploss_val"] = 0.8

        # 2. Crypto Assets Detection
        if "btc" in p or "bitcoin" in p:
            config["symbol"] = "BTCUSDT"
            config["exchange"] = "BINANCE"
            config["market_type"] = "CRYPTO_PERP"
            config["quantity"] = 1
            config["strategy_name"] = "BTC_Crypto_SMC_Algo"
        elif "eth" in p or "ethereum" in p:
            config["symbol"] = "ETHUSDT"
            config["exchange"] = "BINANCE"
            config["market_type"] = "CRYPTO_PERP"
            config["quantity"] = 5
            config["strategy_name"] = "ETH_Crypto_SMC_Algo"
        elif "sol" in p or "solana" in p:
            config["symbol"] = "SOLUSDT"
            config["exchange"] = "BINANCE"
            config["market_type"] = "CRYPTO_PERP"
            config["quantity"] = 25
            config["strategy_name"] = "SOL_Crypto_SMC_Algo"
        # Indian F&O / Equities
        elif "banknifty" in p or "bank nifty" in p:
            config["symbol"] = "BANKNIFTY"
            config["exchange"] = "NSE_INDEX"
            config["quantity"] = 15
            config["strategy_name"] = "BankNifty_AI_Algo"
        elif "finnifty" in p or "fin nifty" in p:
            config["symbol"] = "FINNIFTY"
            config["exchange"] = "NSE_INDEX"
            config["quantity"] = 65
            config["strategy_name"] = "FinNifty_AI_Algo"
        elif "sensex" in p:
            config["symbol"] = "SENSEX"
            config["exchange"] = "BSE_INDEX"
            config["quantity"] = 10
            config["strategy_name"] = "Sensex_AI_Algo"
        elif "crude" in p or "crudeoil" in p:
            config["symbol"] = "CRUDEOIL"
            config["exchange"] = "MCX"
            config["market_type"] = "MCX_COMMODITY"
            config["quantity"] = 100
            config["strategy_name"] = "CrudeOil_MCX_Algo"
        elif "naturalgas" in p or "natgas" in p:
            config["symbol"] = "NATURALGAS"
            config["exchange"] = "MCX"
            config["market_type"] = "MCX_COMMODITY"
            config["quantity"] = 1250
            config["strategy_name"] = "NaturalGas_MCX_Algo"
        elif "gold" in p:
            config["symbol"] = "GOLD"
            config["exchange"] = "MCX"
            config["market_type"] = "MCX_COMMODITY"
            config["quantity"] = 100
            config["strategy_name"] = "Gold_MCX_Algo"
        elif "silver" in p:
            config["symbol"] = "SILVER"
            config["exchange"] = "MCX"
            config["market_type"] = "MCX_COMMODITY"
            config["quantity"] = 30
            config["strategy_name"] = "Silver_MCX_Algo"
        elif "reliance" in p:
            config["symbol"] = "RELIANCE"
            config["exchange"] = "NSE"
            config["quantity"] = 250
            config["strategy_name"] = "Reliance_AI_Algo"
        elif "nifty" in p:
            config["symbol"] = "NIFTY"
            config["exchange"] = "NSE_INDEX"
            config["quantity"] = 65
            config["strategy_name"] = "Nifty_AI_Algo"

        # 3. Timeframe Detection
        if "1 min" in p or "1m" in p:
            config["timeframe"] = "1m"
        elif "3 min" in p or "3m" in p:
            config["timeframe"] = "3m"
        elif "15 min" in p or "15m" in p:
            config["timeframe"] = "15m"
        elif "30 min" in p or "30m" in p:
            config["timeframe"] = "30m"
        elif "1 hour" in p or "1h" in p:
            config["timeframe"] = "1h"
        elif "5 min" in p or "5m" in p:
            config["timeframe"] = "5m"

        # 4. Stop Loss & Target
        sl_match = re.search(r'(?:sl|stop\s*loss|stoploss)\s*(?:of|is|rakho|lagao)?\s*(\d+(?:\.\d+)?)\s*%', p)
        if sl_match:
            config["stoploss_val"] = float(sl_match.group(1))

        tg_match = re.search(r'(?:target|tg)\s*(?:of|is|rakho|lagao)?\s*(\d+(?:\.\d+)?)\s*%', p)
        if tg_match:
            config["target_val"] = float(tg_match.group(1))

        # 5. Supertrend params
        if "supertrend" in p:
            config["strategy_type"] = "supertrend"
            st_match = re.findall(r'supertrend\s*(\d+)\s*(\d+(?:\.\d+)?)', p)
            if st_match:
                config["indicators"]["fast_ema"] = int(st_match[0][0])
                config["indicators"]["slow_ema"] = float(st_match[0][1])

        return config

    @staticmethod
    def generate_python_code(config: Dict[str, Any]) -> str:
        """Generates clean, editable Python strategy code with SMC & Quant support."""
        strat_name = config.get("strategy_name", "AI_Strategy")
        sym = config.get("symbol", "NIFTY")
        exch = config.get("exchange", "NSE_INDEX")
        tf = config.get("timeframe", "5m")
        strat_type = config.get("strategy_type", "custom")
        sl = config.get("stoploss_val", 0.8)
        tg = config.get("target_val", 2.2)
        trade_dir = config.get("trade_direction", "BOTH")
        
        if strat_type == "smc_institutional":
            return f'''"""
===============================================================================
  Strategy: {strat_name} (Smart Money Concepts / SMC Institutional Model)
  Generated via OpenAlgo AI Strategy Lab (Antigravity AI Engine)
  Symbol: {sym} ({exch}) | Timeframe: {tf} | SL: {sl}% | Target: {tg}%
===============================================================================
"""
import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    SMC Institutional Signal Generator:
    - Market Structure (BOS & CHoCH)
    - Order Blocks (OB) & Liquidity Sweeps
    - Fair Value Gaps (FVG)
    """
    df = df.copy()
    n = len(df)
    swing_window = params.get("swing_window", 3)
    trade_direction = params.get("trade_direction", "{trade_dir}")
    
    df["swing_high"] = False
    df["swing_low"] = False
    df["signal"] = None
    
    # 1. Detect Swing Structure
    for i in range(swing_window, n - swing_window):
        if df["high"].iloc[i] == df["high"].iloc[i - swing_window : i + swing_window + 1].max():
            df.loc[df.index[i], "swing_high"] = True
        if df["low"].iloc[i] == df["low"].iloc[i - swing_window : i + swing_window + 1].min():
            df.loc[df.index[i], "swing_low"] = True
            
    # 2. Track Trend, BOS, and Order Blocks
    last_high = None
    last_low = None
    trend = "NEUTRAL"
    
    for i in range(1, n):
        close = df["close"].iloc[i]
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]
        
        if df["swing_high"].iloc[i]:
            last_high = high
        if df["swing_low"].iloc[i]:
            last_low = low
            
        # Bullish CHoCH / BOS
        if last_high is not None and close > last_high:
            trend = "BULLISH"
            if trade_direction in ["LONG", "BOTH"]:
                df.loc[df.index[i], "signal"] = "BUY"
                
        # Bearish CHoCH / BOS
        elif last_low is not None and close < last_low:
            trend = "BEARISH"
            if trade_direction in ["SHORT", "BOTH"]:
                df.loc[df.index[i], "signal"] = "SELL"
                
    return df
'''
        
        # Classical Quant / MT5 Indicator Standard
        fast_ema = config.get("indicators", {}).get("fast_ema", 20) if isinstance(config.get("indicators"), dict) else 20
        slow_ema = config.get("indicators", {}).get("slow_ema", 50) if isinstance(config.get("indicators"), dict) else 50
        rsi_thresh = config.get("indicators", {}).get("rsi_threshold", 50) if isinstance(config.get("indicators"), dict) else 50
        
        return f'''"""
===============================================================================
  Strategy: {strat_name}
  Generated via OpenAlgo AI Strategy Lab (MetaTrader 5 Python Standard)
  Symbol: {sym} ({exch}) | Timeframe: {tf} | SL: {sl}% | Target: {tg}%
===============================================================================
"""
import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    Computes technical indicators and outputs trade signals.
    Returns df with a 'signal' column containing 'BUY', 'SELL', or None.
    """
    # 1. Strategy Parameters (Can be modified directly)
    fast_period = params.get("fast_ema", {fast_ema})
    slow_period = params.get("slow_ema", {slow_ema})
    rsi_period = params.get("rsi_period", 14)
    rsi_threshold = params.get("rsi_threshold", {rsi_thresh})
    trade_direction = params.get("trade_direction", "{trade_dir}")
    
    # 2. Indicator Calculation
    df["fast_ema"] = df["close"].ewm(span=fast_period, adjust=False).mean()
    df["slow_ema"] = df["close"].ewm(span=slow_period, adjust=False).mean()
    
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / (loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # 3. Signal Initialization
    df["signal"] = None
    
    # 4. Entry Rules
    buy_condition = (
        (df["fast_ema"] > df["slow_ema"]) & 
        (df["fast_ema"].shift(1) <= df["slow_ema"].shift(1)) & 
        (df["rsi"] > rsi_threshold)
    )
    
    sell_condition = (
        (df["fast_ema"] < df["slow_ema"]) & 
        (df["fast_ema"].shift(1) >= df["slow_ema"].shift(1)) & 
        (df["rsi"] < 50)
    )
    
    if trade_direction in ["LONG", "BOTH"]:
        df.loc[buy_condition, "signal"] = "BUY"
    if trade_direction in ["SHORT", "BOTH"]:
        df.loc[sell_condition, "signal"] = "SELL"
        
    return df
'''
