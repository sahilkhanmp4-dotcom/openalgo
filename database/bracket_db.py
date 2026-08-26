"""
Database Module for TradingView-Style Bracket Orders & Live Position Protection
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = "db/openalgo.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS position_brackets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            exchange TEXT NOT NULL,
            product TEXT NOT NULL,
            position_type TEXT NOT NULL, -- BUY or SELL
            quantity INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            stoploss_price REAL NOT NULL,
            target_price REAL NOT NULL,
            trailing_sl INTEGER DEFAULT 0, -- 1 or 0
            trailing_step REAL DEFAULT 0.0,
            trailing_peak REAL DEFAULT 0.0,
            status TEXT DEFAULT 'ACTIVE', -- ACTIVE, SL_TRIGGERED, TG_TRIGGERED, CANCELLED, CLOSED
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()

def save_or_update_bracket(data: Dict[str, Any]) -> int:
    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Cancel any existing active bracket for the same symbol
    cur.execute("""
        UPDATE position_brackets 
        SET status = 'CANCELLED', updated_at = ? 
        WHERE symbol = ? AND exchange = ? AND status = 'ACTIVE'
    """, (now, data["symbol"], data.get("exchange", "NSE")))
    
    cur.execute("""
        INSERT INTO position_brackets (
            symbol, exchange, product, position_type, quantity,
            entry_price, stoploss_price, target_price, trailing_sl,
            trailing_step, trailing_peak, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
    """, (
        data["symbol"],
        data.get("exchange", "NSE"),
        data.get("product", "MIS"),
        data.get("position_type", "BUY"),
        int(data.get("quantity", 1)),
        float(data.get("entry_price", 0.0)),
        float(data.get("stoploss_price", 0.0)),
        float(data.get("target_price", 0.0)),
        1 if data.get("trailing_sl") else 0,
        float(data.get("trailing_step", 0.0)),
        float(data.get("entry_price", 0.0)),
        now,
        now
    ))
    bracket_id = cur.lastrowid
    con.commit()
    con.close()
    return bracket_id

def get_active_brackets() -> List[Dict[str, Any]]:
    init_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute("SELECT * FROM position_brackets WHERE status = 'ACTIVE'").fetchall()
    results = [dict(row) for row in rows]
    con.close()
    return results

def update_bracket_status(bracket_id: int, status: str, trailing_peak: Optional[float] = None, sl_price: Optional[float] = None):
    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if trailing_peak is not None and sl_price is not None:
        cur.execute("""
            UPDATE position_brackets 
            SET status = ?, trailing_peak = ?, stoploss_price = ?, updated_at = ?
            WHERE id = ?
        """, (status, trailing_peak, sl_price, now, bracket_id))
    else:
        cur.execute("""
            UPDATE position_brackets 
            SET status = ?, updated_at = ?
            WHERE id = ?
        """, (status, now, bracket_id))
    con.commit()
    con.close()
