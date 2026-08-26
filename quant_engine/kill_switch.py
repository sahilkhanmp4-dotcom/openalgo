"""
OpenAlgo Phase 4: Emergency 1-Click PANIC KILL SWITCH
Immediate, nuclear-grade emergency liquidation and risk containment across OpenAlgo and Broker accounts.
"""

import os
import json
import sqlite3
from typing import Dict, Any, List
from quant_engine.telegram_alerts import TelegramAlertEngine
from quant_engine.rms_manager import RMSManager

from database.auth_db import get_auth_token
from services.cancel_all_order_service import cancel_all_orders
from services.close_position_service import close_position
from services.positionbook_service import get_positionbook

class PanicKillSwitch:
    @staticmethod
    def execute(reason: str = "Manual User Trigger", client_ip: str = "127.0.0.1") -> Dict[str, Any]:
        """
        Executes immediate complete emergency squareoff & order cancellation.
        """
        report = {
            "status": "success",
            "reason": reason,
            "orders_cancelled": 0,
            "positions_closed": 0,
            "details": []
        }

        # 1. Fetch active broker session
        try:
            con = sqlite3.connect("db/openalgo.db")
            cur = con.cursor()
            row = cur.execute("SELECT name, broker FROM auth WHERE is_revoked=0 LIMIT 1").fetchone()
            con.close()
        except Exception as e:
            row = None

        if row:
            username, broker = row
            auth_token = get_auth_token(username)

            # Step 1: Cancel all pending orders
            try:
                success, cancel_res, _ = cancel_all_orders(order_data={}, auth_token=auth_token, broker=broker)
                if success:
                    report["orders_cancelled"] = cancel_res.get("canceled_count", 1) if isinstance(cancel_res, dict) else 1
                    report["details"].append("All pending broker limit & SL orders cancelled.")
                else:
                    report["details"].append(f"Cancel orders notice: {cancel_res}")
            except Exception as e:
                report["details"].append(f"Order cancel exception: {e}")

            # Step 2: Fetch and Close all open positions
            try:
                success, pos_res, _ = get_positionbook(auth_token, None, broker)
                if success and isinstance(pos_res, dict) and "data" in pos_res:
                    positions = pos_res["data"]
                    for p in positions:
                        qty = int(p.get("quantity", 0))
                        sym = p.get("symbol", "")
                        exch = p.get("exchange", "NFO")
                        prod = p.get("product", "MIS")
                        if qty != 0:
                            succ, c_res, _ = close_position(auth_token, None, broker, sym, exch, prod)
                            if succ:
                                report["positions_closed"] += 1
                                report["details"].append(f"Closed position: {sym} (Qty: {qty})")
            except Exception as e:
                report["details"].append(f"Position close exception: {e}")

        # Step 3: Trigger RMS Lockout
        RMSManager.trigger_lock(f"EMERGENCY KILL SWITCH: {reason}")
        report["details"].append("Account RMS Circuit Breaker Locked.")

        # Step 4: Dispatch Urgent Telegram Alert
        TelegramAlertEngine.notify_kill_switch(user_ip=client_ip, reason=reason)
        report["details"].append("Emergency Telegram broadcast sent.")

        print(f"[PANIC KILL SWITCH EXECUTED] Reason: {reason} | Closed: {report['positions_closed']} | Cancelled: {report['orders_cancelled']}")
        return report

    @staticmethod
    def reset() -> Dict[str, Any]:
        """Manually reset the kill switch and unlock trading."""
        res = RMSManager.unlock_manual()
        return {"status": "success", "message": "Emergency Kill Switch reset. Trading re-enabled.", "rms": res}
