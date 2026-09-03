"""
Bracket Order & Live Position Protection Service
Provides TradingView-Style OCO (One-Cancels-Other) Bracket SL and Target Execution.
"""

import threading
import time
from typing import Dict, Any, List
from database.bracket_db import get_active_brackets, update_bracket_status, save_or_update_bracket
from database.auth_db import get_auth_token, get_first_available_api_key, get_auth_token_broker
from utils.logging import get_logger

logger = get_logger(__name__)

class BracketManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.running = False
        self.worker_thread = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.start_monitoring_thread()
            return cls._instance

    def start_monitoring_thread(self):
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="BracketMonitorThread")
        self.worker_thread.start()
        logger.info("[BRACKET SERVICE] Started background bracket OCO monitoring thread")

    def _monitor_loop(self):
        time.sleep(3)
        while self.running:
            try:
                active_brackets = get_active_brackets()
                if active_brackets:
                    from services.quotes_service import get_quotes
                    api_key = get_first_available_api_key()
                    
                    for b in active_brackets:
                        sym = b.get("symbol")
                        exch = b.get("exchange", "NSE")
                        if not sym:
                            continue
                        try:
                            # Fetch live quote / LTP using valid api_key
                            success, res, _ = get_quotes(symbol=sym, exchange=exch, api_key=api_key)
                            if success and res and "data" in res:
                                quote_data = res.get("data")
                                ltp = 0.0
                                if isinstance(quote_data, dict):
                                    ltp = float(quote_data.get("ltp") or quote_data.get("last_price") or quote_data.get("lp") or 0.0)
                                elif isinstance(quote_data, list) and len(quote_data) > 0:
                                    first = quote_data[0]
                                    if isinstance(first, dict):
                                        ltp = float(first.get("ltp") or first.get("last_price") or first.get("lp") or 0.0)
                                
                                if ltp > 0:
                                    self.process_ltp_tick(sym, ltp, api_key=api_key)
                        except Exception as ex:
                            logger.debug(f"[BRACKET MONITOR] Error fetching quote for {sym}: {ex}")
            except Exception as e:
                logger.error(f"[BRACKET MONITOR ERROR] {e}")
            time.sleep(1.0)

    def process_ltp_tick(self, symbol: str, ltp: float, api_key: str = None, auth_token: str = None, broker: str = None):
        """
        Evaluates LTP tick against active bracket orders and executes Stop Loss / Target immediately.
        """
        if not api_key:
            api_key = get_first_available_api_key()
            
        active_brackets = get_active_brackets()
        for b in active_brackets:
            if b["symbol"].upper() == symbol.upper():
                b_id = b["id"]
                pos = b["position_type"].upper()
                sl = float(b["stoploss_price"])
                tg = float(b["target_price"])
                trailing = bool(b["trailing_sl"])
                step = float(b["trailing_step"])
                peak = float(b["trailing_peak"])
                
                exit_triggered = False
                reason = ""
                
                # Check Trailing SL
                if trailing and step > 0:
                    if pos == "BUY" and ltp > peak:
                        new_peak = ltp
                        diff = new_peak - peak
                        if diff >= step:
                            new_sl = round(sl + diff, 2)
                            update_bracket_status(b_id, "ACTIVE", trailing_peak=new_peak, sl_price=new_sl)
                            logger.info(f"[BRACKET TRAIL] {symbol} New Peak: {new_peak} | Shifted SL to {new_sl}")
                    elif pos == "SELL" and ltp < peak:
                        new_peak = ltp
                        diff = peak - new_peak
                        if diff >= step:
                            new_sl = round(sl - diff, 2)
                            update_bracket_status(b_id, "ACTIVE", trailing_peak=new_peak, sl_price=new_sl)
                            logger.info(f"[BRACKET TRAIL] {symbol} New Low: {new_peak} | Shifted SL to {new_sl}")
                
                # Check Stop Loss & Target
                if pos == "BUY":
                    if sl > 0 and ltp <= sl:
                        exit_triggered = True
                        reason = f"SL_TRIGGERED (LTP {ltp} <= SL {sl})"
                    elif tg > 0 and ltp >= tg:
                        exit_triggered = True
                        reason = f"TG_TRIGGERED (LTP {ltp} >= Target {tg})"
                elif pos == "SELL":
                    if sl > 0 and ltp >= sl:
                        exit_triggered = True
                        reason = f"SL_TRIGGERED (LTP {ltp} >= SL {sl})"
                    elif tg > 0 and ltp <= tg:
                        exit_triggered = True
                        reason = f"TG_TRIGGERED (LTP {ltp} <= Target {tg})"
                        
                if exit_triggered:
                    logger.info(f"[BRACKET TRIGGERED] {symbol} {reason}. Executing OCO Close...")
                    status_name = "SL_TRIGGERED" if "SL" in reason else "TG_TRIGGERED"
                    update_bracket_status(b_id, status_name)
                    self._execute_close(b, reason, api_key=api_key, auth_token=auth_token, broker=broker)

    def _execute_close(self, bracket: Dict[str, Any], reason: str, api_key: str = None, auth_token: str = None, broker: str = None):
        """Execute position close in live broker or analyze mode."""
        try:
            from services.place_smart_order_service import place_smart_order
            if not api_key:
                api_key = get_first_available_api_key()

            order_data = {
                "strategy": f"Bracket {reason}",
                "exchange": bracket["exchange"],
                "symbol": bracket["symbol"],
                "action": "SELL" if bracket["position_type"].upper() == "BUY" else "BUY",
                "product_type": bracket["product"],
                "pricetype": "MARKET",
                "quantity": str(bracket.get("quantity") or 0),
                "position_size": "0" # Close position
            }
            if api_key:
                place_smart_order(order_data=order_data, api_key=api_key)
            else:
                logger.warning(f"[BRACKET CLOSE WARNING] No active API key found to execute close for {bracket['symbol']}")
        except Exception as e:
            logger.error(f"Error executing bracket close order: {e}")

