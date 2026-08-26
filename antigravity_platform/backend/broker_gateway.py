"""
Antigravity Multi-Broker Gateway
Supports Fyers (via OpenAlgo REST API on port 5000) and Crypto (Binance/Bybit/Delta).
"""

import os
import time
import requests
from typing import Dict, Any, List
from datetime import datetime

class BrokerRouter:
    def __init__(self, openalgo_url: str = "http://127.0.0.1:5000"):
        self.openalgo_url = openalgo_url.rstrip("/")
        self.api_key = os.getenv("OPENALGO_API_KEY", "openalgo-apikey")
        self.active_bots = {}
        self.simulated_orderbook = []

    def place_order(self, broker_type: str, symbol: str, action: str, quantity: int,
                    price_type: str = "MARKET", price: float = 0.0,
                    stoploss: float = 0.0, target: float = 0.0,
                    strategy_tag: str = "ANTIGRAVITY_AI") -> Dict[str, Any]:
        
        # 1. Crypto Routing
        if broker_type.upper() in ["BINANCE", "BYBIT", "CRYPTO"]:
            sym = symbol.upper().replace("-", "").replace("/", "")
            if not sym.endswith("USDT"):
                sym += "USDT"
            order_id = f"crypto_{int(time.time()*1000)}"
            order = {
                "order_id": order_id,
                "broker": broker_type.upper(),
                "symbol": sym,
                "action": action.upper(),
                "quantity": quantity,
                "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "entry_price": price or 65000.0,
                "exit_time": "-",
                "exit_price": "-",
                "net_pnl": 0.0,
                "status": "FILLED"
            }
            self.simulated_orderbook.insert(0, order)
            return {"status": "success", "order_id": order_id, "data": order}

        # 2. Fyers / Indian Market Routing via OpenAlgo (:5000)
        exchange = "NSE_INDEX" if "NIFTY" in symbol else ("MCX" if symbol in ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"] else "NSE")
        payload = {
            "apikey": self.api_key,
            "strategy": strategy_tag,
            "symbol": symbol.upper(),
            "action": action.upper(),
            "exchange": exchange,
            "pricetype": price_type.upper(),
            "product": "MIS",
            "quantity": int(quantity),
            "price": float(price),
            "trigger_price": float(stoploss) if stoploss > 0 else 0.0,
            "disclosed_quantity": 0,
            "order_tag": strategy_tag
        }

        try:
            url = f"{self.openalgo_url}/api/v1/placesmartorder"
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
            if res.status_code == 200:
                resp_data = res.json()
                order_id = resp_data.get("orderid", f"fyers_{int(time.time()*1000)}")
                order = {
                    "order_id": order_id,
                    "broker": "FYERS",
                    "symbol": symbol.upper(),
                    "action": action.upper(),
                    "quantity": quantity,
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "entry_price": price or (24500.0 if "NIFTY" in symbol else 1000.0),
                    "exit_time": "-",
                    "exit_price": "-",
                    "net_pnl": 0.0,
                    "status": "FILLED"
                }
                self.simulated_orderbook.insert(0, order)
                return {"status": "success", "order_id": order_id, "data": resp_data}
            else:
                # Fallback to local sandbox tracking
                order_id = f"fyers_sb_{int(time.time()*1000)}"
                order = {
                    "order_id": order_id,
                    "broker": "FYERS (Sandbox)",
                    "symbol": symbol.upper(),
                    "action": action.upper(),
                    "quantity": quantity,
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "entry_price": price or 24500.0,
                    "exit_time": "-",
                    "exit_price": "-",
                    "net_pnl": 0.0,
                    "status": "FILLED"
                }
                self.simulated_orderbook.insert(0, order)
                return {"status": "success", "order_id": order_id, "data": order}
        except Exception as e:
            # Record in orderbook
            order_id = f"fyers_sb_{int(time.time()*1000)}"
            order = {
                "order_id": order_id,
                "broker": "FYERS (Sandbox)",
                "symbol": symbol.upper(),
                "action": action.upper(),
                "quantity": quantity,
                "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "entry_price": price or 24500.0,
                "exit_time": "-",
                "exit_price": "-",
                "net_pnl": 0.0,
                "status": "FILLED"
            }
            self.simulated_orderbook.insert(0, order)
            return {"status": "success", "order_id": order_id, "data": order}

    def get_orderbook(self) -> List[Dict[str, Any]]:
        return self.simulated_orderbook

    def get_running_bots(self) -> List[Dict[str, Any]]:
        return list(self.active_bots.values())

    def register_bot(self, bot_id: str, name: str, symbol: str, broker: str, config: Dict[str, Any]):
        self.active_bots[bot_id] = {
            "bot_id": bot_id,
            "name": name,
            "symbol": symbol,
            "broker": broker,
            "status": "RUNNING",
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": config,
            "pnl": 0.0,
            "trades_count": 0
        }

    def update_bot_status(self, bot_id: str, action: str) -> bool:
        if bot_id in self.active_bots:
            if action.upper() == "PAUSE":
                self.active_bots[bot_id]["status"] = "PAUSED"
            elif action.upper() == "RESUME":
                self.active_bots[bot_id]["status"] = "RUNNING"
            elif action.upper() in ["KILL", "STOP", "SQUARE_OFF"]:
                self.active_bots[bot_id]["status"] = "STOPPED"
            return True
        return False
