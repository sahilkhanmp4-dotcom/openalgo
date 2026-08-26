"""
Institutional Strategy Parser & Parameter Validator
Validates strategy logic and identifies missing risk parameters before backtesting.
"""

from typing import Dict, Any, List, Tuple

DEFAULT_STRATEGY_CONFIG = {
    "strategy_name": "Custom_Algo",
    "symbol": "NIFTY25AUG26FUT",
    "exchange": "NFO",
    "timeframe": "5m",
    "trade_direction": "BOTH",  # LONG, SHORT, BOTH
    "capital": 100000.0,
    "quantity": 50,  # 1 lot Nifty
    "entry_time": "09:20",
    "exit_time": "15:15",
    "stoploss_type": "PERCENT",  # PERCENT, POINTS, ATR
    "stoploss_val": 1.0,  # 1% SL
    "target_type": "PERCENT",
    "target_val": 2.0,  # 2% Target
    "trailing_sl": False,
    "trailing_step": 0.5,
    "slippage_pct": 0.05,  # 0.05% slippage per leg
    "brokerage_per_trade": 40.0,  # ₹20 buy + ₹20 sell
    "tax_rate_pct": 0.08,  # STT + GST + Exchange + Stamp duty
    "indicators": {
        "fast_ema": 20,
        "slow_ema": 50,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30
    }
}

class StrategyValidator:
    @staticmethod
    def inspect_strategy(params: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """
        Validates parameters, applies smart defaults, and detects missing institutional gaps.
        Returns: (merged_config, warnings, questions_for_user)
        """
        config = DEFAULT_STRATEGY_CONFIG.copy()
        config.update(params)
        
        warnings = []
        questions = []
        
        # 1. Check Instrument & Timeframe
        if not params.get("symbol"):
            warnings.append("Symbol was not specified. Defaulting to NIFTY25AUG26FUT.")
        if not params.get("timeframe"):
            warnings.append("Timeframe was not specified. Defaulting to 5m.")
            
        # 2. Risk Management Check
        if not params.get("stoploss_val") or float(config["stoploss_val"]) <= 0:
            warnings.append("⚠️ No Stop Loss defined! Institutional standard mandates a Stop Loss (Defaulted to 1.0%).")
            questions.append("Would you like to set a custom Stop Loss (e.g. 0.5%, 1.0%, 30 points)?")
            
        if not params.get("target_val") or float(config["target_val"]) <= 0:
            warnings.append("⚠️ No Target defined! Risk-to-Reward ratio will be unconstrained (Defaulted to 2.0%).")
            
        # 3. Capital & Sizing Check
        if not params.get("capital") or float(config["capital"]) <= 0:
            config["capital"] = 100000.0
            
        # 4. Intraday Timing Check
        if config.get("entry_time") and config.get("exit_time"):
            if config["entry_time"] < "09:15" or config["exit_time"] > "15:30":
                warnings.append("Trading hours must be within Indian Market session (09:15 to 15:30).")
                config["entry_time"] = max("09:15", config["entry_time"])
                config["exit_time"] = min("15:25", config["exit_time"])

        return config, warnings, questions
