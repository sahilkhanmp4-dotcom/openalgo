"""
OpenAlgo Phase 4: Mode Manager (Analyzer vs Live Execution)
Provides 1-Click safe switching between ₹1 Cr Virtual Sandbox and Real Broker Execution.
"""

from typing import Dict, Any
from database.settings_db import get_analyze_mode, set_analyze_mode
from quant_engine.telegram_alerts import TelegramAlertEngine

class ModeManager:
    @staticmethod
    def get_current_mode() -> Dict[str, Any]:
        """Returns active execution mode: 'ANALYZER' or 'LIVE'."""
        try:
            is_analyze = get_analyze_mode()
            mode = "ANALYZER" if is_analyze else "LIVE"
        except Exception:
            mode = "ANALYZER"
            
        return {
            "mode": mode,
            "is_analyzer": mode == "ANALYZER",
            "is_live": mode == "LIVE",
            "description": "₹1 Crore Virtual Sandbox (No Real Risk)" if mode == "ANALYZER" else "Real Broker Order Execution (Live Capital)"
        }

    @classmethod
    def set_mode(cls, mode_str: str) -> Dict[str, Any]:
        """Toggles between 'ANALYZER' and 'LIVE'."""
        is_analyze = (mode_str.upper() == "ANALYZER")
        try:
            set_analyze_mode(is_analyze)
        except Exception as e:
            print(f"Error setting analyze mode: {e}")

        status = cls.get_current_mode()
        
        # Dispatch Telegram notice on mode change
        msg = f"🔄 *OPENALGO EXECUTION MODE CHANGED*\n━━━━━━━━━━━━━━━━━━━━\n📌 New Mode: *{status['mode']}*\n📝 {status['description']}\n━━━━━━━━━━━━━━━━━━━━"
        TelegramAlertEngine.send_message(msg)
        
        return status
