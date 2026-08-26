"""
OpenAlgo Phase 4: Instant Telegram Alerts & Notification Engine
Dispatches real-time structured trade alerts, RMS locks, and emergency notifications.
"""

import os
import json
import httpx
from datetime import datetime
import pytz
from typing import Dict, Any, Optional

IST = pytz.timezone("Asia/Kolkata")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "telegram_config.json")

class TelegramAlertEngine:
    @staticmethod
    def get_config() -> Dict[str, Any]:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "enabled": False,
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "trade_alerts": True,
            "sl_tp_alerts": True,
            "rms_alerts": True,
            "eod_summary": True
        }

    @classmethod
    def save_config(cls, config: Dict[str, Any]) -> bool:
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving telegram config: {e}")
            return False

    @classmethod
    def send_message(cls, text: str) -> Dict[str, Any]:
        """Sends markdown formatted message to Telegram Chat."""
        cfg = cls.get_config()
        if not cfg.get("enabled") or not cfg.get("bot_token") or not cfg.get("chat_id"):
            return {"status": "skipped", "message": "Telegram alerts disabled or not configured"}

        url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
        payload = {
            "chat_id": cfg["chat_id"],
            "text": text,
            "parse_mode": "Markdown"
        }

        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    return {"status": "success", "message": "Alert sent"}
                else:
                    return {"status": "error", "message": f"Telegram API error: {res.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @classmethod
    def notify_trade_entry(cls, strategy: str, symbol: str, action: str, qty: int, price: float, sl: float, tg: float, mode: str = "ANALYZER"):
        mode_badge = "🧪 [ANALYZER / PAPER]" if mode == "ANALYZER" else "🔥 [LIVE TRADING]"
        now_str = datetime.now(IST).strftime("%H:%M:%S IST")
        icon = "🟢" if action.upper() == "BUY" else "🔴"
        
        msg = (
            f"{icon} *OPENALGO TRADE ENTRY* {mode_badge}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Strategy:* `{strategy}`\n"
            f"📊 *Symbol:* `{symbol}`\n"
            f"⚡ *Action:* `{action.upper()}` | *Qty:* `{qty}`\n"
            f"💰 *Entry Price:* `₹{price}`\n"
            f"🛡️ *Stop Loss:* `₹{sl}`\n"
            f"🎯 *Target (TP):* `₹{tg}`\n"
            f"⏰ *Time:* `{now_str}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        return cls.send_message(msg)

    @classmethod
    def notify_trade_exit(cls, strategy: str, symbol: str, action: str, qty: int, entry_price: float, exit_price: float, pnl: float, reason: str, mode: str = "ANALYZER"):
        mode_badge = "🧪 [ANALYZER]" if mode == "ANALYZER" else "🔥 [LIVE]"
        now_str = datetime.now(IST).strftime("%H:%M:%S IST")
        pnl_icon = "🟢" if pnl >= 0 else "🔴"
        pnl_sign = "+" if pnl >= 0 else ""
        
        msg = (
            f"🏁 *OPENALGO TRADE EXIT* {mode_badge}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Strategy:* `{strategy}`\n"
            f"📊 *Symbol:* `{symbol}` ({action})\n"
            f"🎯 *Exit Reason:* `{reason}`\n"
            f"💰 *Entry:* `₹{entry_price}` ➔ *Exit:* `₹{exit_price}`\n"
            f"{pnl_icon} *Net P&L:* `{pnl_sign}₹{pnl:,.2f}`\n"
            f"⏰ *Time:* `{now_str}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        return cls.send_message(msg)

    @classmethod
    def notify_rms_lock(cls, reason: str, daily_pnl: float, max_loss_limit: float):
        now_str = datetime.now(IST).strftime("%H:%M:%S IST")
        msg = (
            f"⚠️ *RMS DAILY RISK LOCK TRIGGERED* ⚠️\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 *Reason:* `{reason}`\n"
            f"📉 *Current Daily P&L:* `₹{daily_pnl:,.2f}`\n"
            f"🛡️ *Max Loss Threshold:* `₹{max_loss_limit:,.2f}`\n"
            f"🔒 *Status:* Trading locked for the day to protect capital.\n"
            f"⏰ *Time:* `{now_str}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        return cls.send_message(msg)

    @classmethod
    def notify_kill_switch(cls, user_ip: str = "127.0.0.1", reason: str = "Manual Trigger"):
        now_str = datetime.now(IST).strftime("%H:%M:%S IST")
        msg = (
            f"🚨 *EMERGENCY PANIC KILL SWITCH ACTIVATED* 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💥 *Action Taken:*\n"
            f"  • ALL open pending orders CANCELLED.\n"
            f"  • ALL open market positions SQUARED OFF.\n"
            f"  • Strategy bots auto-halted.\n"
            f"👤 *Initiator:* `{user_ip}`\n"
            f"📋 *Reason:* `{reason}`\n"
            f"⏰ *Time:* `{now_str}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        return cls.send_message(msg)
