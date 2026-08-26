"""
Strategy Persistence & Portfolio Store
Manages CRUD operations for user strategies (Save, List, Delete, Deploy status).
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List

STORAGE_FILE = os.path.join(os.path.dirname(__file__), "saved_strategies.json")

class StrategyStore:
    @staticmethod
    def _load_all() -> List[Dict[str, Any]]:
        if not os.path.exists(STORAGE_FILE):
            return []
        try:
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def _save_all(strategies: List[Dict[str, Any]]):
        os.makedirs(os.path.dirname(STORAGE_FILE), exist_ok=True)
        with open(STORAGE_FILE, "w") as f:
            json.dump(strategies, f, indent=2)

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        return cls._load_all()

    @classmethod
    def save(cls, config_or_data: Dict[str, Any], metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        strategies = cls._load_all()
        
        # Handle both save(data) and save(config, metrics)
        if "config" in config_or_data:
            cfg = config_or_data["config"]
            met = config_or_data.get("metrics", {})
        else:
            cfg = config_or_data
            met = metrics or {}
            
        name = cfg.get("strategy_name", f"Strategy_{int(time.time())}")
        existing = next((s for s in strategies if s.get("strategy_name") == name), None)
        
        entry = {
            "id": existing["id"] if existing else f"strat_{int(time.time() * 1000)}",
            "strategy_name": name,
            "symbol": cfg.get("symbol", "NIFTY"),
            "exchange": cfg.get("exchange", "NSE_INDEX"),
            "timeframe": cfg.get("timeframe", "5m"),
            "config": cfg,
            "metrics": met,
            "status": "READY",
            "created_at": existing["created_at"] if existing else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if existing:
            strategies = [entry if s.get("strategy_name") == name else s for s in strategies]
        else:
            strategies.insert(0, entry)
            
        cls._save_all(strategies)
        return entry

    @classmethod
    def delete(cls, strategy_id: str) -> bool:
        strategies = cls._load_all()
        strat_to_delete = next((s for s in strategies if s.get("id") == strategy_id), None)
        if not strat_to_delete:
            return False
            
        strategies = [s for s in strategies if s.get("id") != strategy_id]
        cls._save_all(strategies)
        return True

    @classmethod
    def update_status(cls, strategy_id: str, status: str) -> bool:
        strategies = cls._load_all()
        found = False
        for s in strategies:
            if s.get("id") == strategy_id:
                s["status"] = status
                s["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                found = True
                break
        if found:
            cls._save_all(strategies)
        return found

# Compatibility Aliases
StrategyStore.list_strategies = StrategyStore.get_all
StrategyStore.save_strategy = StrategyStore.save
StrategyStore.delete_strategy = StrategyStore.delete
