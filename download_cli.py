#!/usr/bin/env python3
"""
Interactive Command-Line Tool to Download Market Data (OHLC, Volume, OI)
Usage:
    python3 download_cli.py
    python3 download_cli.py NIFTY25AUG26FUT NFO 5m 2026-08-01 2026-08-25
"""

import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import pytz

from database.auth_db import get_auth_token
from services.history_service import get_history_with_auth

IST = pytz.timezone("Asia/Kolkata")

def main():
    print("=" * 60)
    print("⚡ OpenAlgo Market Data Downloader (CLI)")
    print("=" * 60)
    
    # Check active broker
    con = sqlite3.connect("db/openalgo.db")
    cur = con.cursor()
    row = cur.execute("SELECT name, broker FROM auth WHERE is_revoked=0 LIMIT 1").fetchone()
    con.close()
    
    if not row:
        print("❌ Error: No active broker login found in OpenAlgo.")
        return
        
    username, broker = row
    auth_token = get_auth_token(username)
    print(f"✅ Connected Broker: {broker.upper()} (User: {username})")
    print("-" * 60)
    
    # Command line arguments or interactive prompt
    if len(sys.argv) >= 2:
        symbol = sys.argv[1].upper()
        exchange = sys.argv[2].upper() if len(sys.argv) > 2 else "NFO"
        interval = sys.argv[3] if len(sys.argv) > 3 else "5m"
        start_date = sys.argv[4] if len(sys.argv) > 4 else (datetime.now(IST) - timedelta(days=25)).strftime("%Y-%m-%d")
        end_date = sys.argv[5] if len(sys.argv) > 5 else datetime.now(IST).strftime("%Y-%m-%d")
    else:
        print("\n📝 Enter Details (or press Enter for defaults):")
        symbol_input = input("1. Trading Symbol [default: NIFTY25AUG26FUT]: ").strip()
        symbol = symbol_input.upper() if symbol_input else "NIFTY25AUG26FUT"
        
        exchange_input = input("2. Exchange (NFO / NSE / NSE_INDEX / MCX / BSE) [default: NFO]: ").strip()
        exchange = exchange_input.upper() if exchange_input else "NFO"
        
        interval_input = input("3. Timeframe (1m / 3m / 5m / 15m / 30m / 1h / D) [default: 5m]: ").strip()
        interval = interval_input if interval_input else "5m"
        
        today = datetime.now(IST).date()
        default_start = (today - timedelta(days=25)).strftime("%Y-%m-%d")
        default_end = today.strftime("%Y-%m-%d")
        
        start_input = input(f"4. Start Date (YYYY-MM-DD) [default: {default_start}]: ").strip()
        start_date = start_input if start_input else default_start
        
        end_input = input(f"5. End Date (YYYY-MM-DD) [default: {default_end}]: ").strip()
        end_date = end_input if end_input else default_end

    print(f"\n⏳ Fetching {symbol} ({exchange}) [{interval}] from {start_date} to {end_date}...")
    
    try:
        success, response, status = get_history_with_auth(
            auth_token=auth_token,
            feed_token=None,
            broker=broker,
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )
        
        if not success:
            err = response.get("message", response) if isinstance(response, dict) else str(response)
            print(f"❌ Fetch Error: {err}")
            return
            
        data = response.get("data", [])
        if not data:
            print("⚠️ No candle data returned for given dates/symbol.")
            return
            
        df = pd.DataFrame(data)
        if "timestamp" in df.columns:
            df["Date Time"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d %H:%M:%S")
            
        if "oi" not in df.columns:
            df["oi"] = 0
            
        cols = ["Date Time", "open", "high", "low", "close", "volume", "oi"]
        df_export = df[[c for c in cols if c in df.columns]].copy()
        
        output_filename = f"{symbol}_{exchange}_{interval}.csv"
        df_export.to_csv(output_filename, index=False)
        
        print("\n" + "=" * 60)
        print(f"🎉 SUCCESS! Fetched {len(df_export)} candles.")
        print(f"💾 File Saved to: {os.path.abspath(output_filename)}")
        print("=" * 60)
        print("\n--- Last 5 Candles ---")
        print(df_export.tail(5).to_string(index=False))
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    main()
