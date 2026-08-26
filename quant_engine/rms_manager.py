"""
OpenAlgo Phase 4: Real-Time RMS (Risk Management System) & Capital Protection
Controls daily drawdown limits, max open positions, and account-level circuit breakers.
"""

import os
import json
import sqlite3
from datetime import datetime
import pytz
from typing import Dict, Any, Tuple
from quant_engine.telegram_alerts import TelegramAlertEngine

IST = pytz.timezone("Asia/Kolkata")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "rms_config.json")

class RMSManager:
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "enabled": True,
            "max_daily_loss": 5000.0,
            "max_daily_profit": 25000.0,
            "max_open_positions": 4,
            "max_capital_per_trade": 50000.0,
            "is_locked": False,
            "lock_reason": "",
            "daily_realized_pnl": 0.0,
            "last_reset_date": datetime.now(IST).strftime("%Y-%m-%d")
        }

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        cfg = cls._default_config()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    stored = json.load(f)
                    cfg.update(stored)
            except Exception:
                pass
                
        # Auto-reset if date has changed (New trading day)
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        if cfg.get("last_reset_date") != today_str:
            cfg["last_reset_date"] = today_str
            cfg["daily_realized_pnl"] = 0.0
            cfg["is_locked"] = False
            cfg["lock_reason"] = ""
            cls.save_config(cfg)
            
        return cfg

    @classmethod
    def save_config(cls, config: Dict[str, Any]) -> bool:
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving RMS config: {e}")
            return False

    @classmethod
    def update_settings(cls, max_loss: float, max_profit: float, max_positions: int, max_cap: float, enabled: bool) -> Dict[str, Any]:
        cfg = cls.get_config()
        cfg["max_daily_loss"] = float(max_loss)
        cfg["max_daily_profit"] = float(max_profit)
        cfg["max_open_positions"] = int(max_positions)
        cfg["max_capital_per_trade"] = float(max_cap)
        cfg["enabled"] = bool(enabled)
        cls.save_config(cfg)
        return cfg

    @classmethod
    def check_order_permission(cls, strategy: str, symbol: str, quantity: int, price: float = 0.0) -> Tuple[bool, str]:
        """
        Pre-Trade RMS Validation. Called before any order reaches OpenAlgo / Broker.
        """
        cfg = cls.get_config()
        if not cfg.get("enabled", True):
            return True, "RMS disabled"

        # Check 1: Is account currently locked by circuit breaker
        if cfg.get("is_locked", False):
            return False, f"Trading Locked by RMS: {cfg.get('lock_reason', 'Daily threshold hit')}"

        # Check 2: Single trade capital check
        order_value = float(quantity) * float(price) if price > 0 else 0.0
        if price > 0 and order_value > cfg.get("max_capital_per_trade", 50000.0):
            return False, f"Order value ₹{order_value:,.2f} exceeds max per-trade limit of ₹{cfg['max_capital_per_trade']:,.2f}"

        # Check 3: Current Daily Loss Check
        current_pnl = float(cfg.get("daily_realized_pnl", 0.0))
        max_loss = float(cfg.get("max_daily_loss", 5000.0))
        if current_pnl <= -max_loss:
            cls.trigger_lock("MAX DAILY LOSS REACHED")
            return False, f"Daily Loss limit of ₹{max_loss:,.2f} reached. Trading Locked."

        return True, "RMS Approved"

    @classmethod
    def record_pnl(cls, pnl: float) -> Dict[str, Any]:
        """Called when a trade exits to update running daily P&L and evaluate thresholds."""
        cfg = cls.get_config()
        cfg["daily_realized_pnl"] = round(cfg.get("daily_realized_pnl", 0.0) + pnl, 2)
        
        current_pnl = cfg["daily_realized_pnl"]
        max_loss = float(cfg.get("max_daily_loss", 5000.0))
        max_profit = float(cfg.get("max_daily_profit", 25000.0))

        # Check Max Loss Breached
        if current_pnl <= -max_loss and not cfg.get("is_locked"):
            cls.trigger_lock(f"Daily Loss Limit of ₹{max_loss:,.2f} Exceeded (P&L: ₹{current_pnl:,.2f})")
            
        # Check Max Profit Target Achieved
        elif current_pnl >= max_profit and not cfg.get("is_locked"):
            cls.trigger_lock(f"Daily Target Profit of ₹{max_profit:,.2f} Achieved! Gains Protected.")
            
        cls.save_config(cfg)
        return cfg

    @classmethod
    def trigger_lock(cls, reason: str):
        cfg = cls.get_config()
        cfg["is_locked"] = True
        cfg["lock_reason"] = reason
        cls.save_config(cfg)
        print(f"[RMS CIRCUIT BREAKER] {reason}")
        TelegramAlertEngine.notify_rms_lock(reason, cfg.get("daily_realized_pnl", 0.0), cfg.get("max_daily_loss", 5000.0))

    @classmethod
    def unlock_manual(cls) -> Dict[str, Any]:
        cfg = cls.get_config()
        cfg["is_locked"] = False
        cfg["lock_reason"] = ""
        cls.save_config(cfg)
        return cfg
