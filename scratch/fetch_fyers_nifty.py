import hashlib
import json
import os
import sys
import urllib.parse
import httpx
import pandas as pd

CLIENT_ID = "0XQB0ESO8W-200"
SECRET_KEY = "tH62ZvXgTXWqOMdl"
REDIRECT_URI = "http://127.0.0.1:5000/fyers/callback"

def get_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": "openalgo"
    }
    return f"https://api-t1.fyers.in/api/v3/generate-authcode?{urllib.parse.urlencode(params)}"

def exchange_auth_code(auth_code: str) -> str:
    url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    checksum_input = f"{CLIENT_ID}:{SECRET_KEY}"
    app_id_hash = hashlib.sha256(checksum_input.encode("utf-8")).hexdigest()
    
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code.strip()
    }
    
    headers = {"Content-Type": "application/json"}
    with httpx.Client(timeout=30.0) as client:
        res = client.post(url, headers=headers, json=payload)
        res_data = res.json()
        if res_data.get("s") == "ok" and "access_token" in res_data:
            return res_data["access_token"]
        else:
            raise Exception(f"Token generation failed: {res_data}")

def fetch_historical_data(access_token: str, symbol: str, resolution: str = "5", range_from: str = "2025-08-01", range_to: str = "2025-08-25"):
    headers = {
        "Authorization": f"{CLIENT_ID}:{access_token}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"https://api-t1.fyers.in/data/history"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "date_format": "1",
        "range_from": range_from,
        "range_to": range_to,
        "cont_flag": "1",
        "oi_flag": "1"
    }
    
    with httpx.Client(timeout=30.0) as client:
        res = client.get(endpoint, headers=headers, params=params)
        res_data = res.json()
        if res_data.get("s") != "ok":
            raise Exception(f"Fyers History API Error: {res_data.get('message', res_data)}")
        
        candles = res_data.get("candles", [])
        if not candles:
            print(f"No candles returned for {symbol}")
            return pd.DataFrame()
        
        if len(candles[0]) == 7:
            df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
        else:
            df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["oi"] = 0
            
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
        return df

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Auth URL:")
        print(get_auth_url())
    else:
        code_or_token = sys.argv[1]
        if code_or_token.startswith("ey"):  # Already an access token
            token = code_or_token
        else:
            print(f"Exchanging auth code for access token...")
            token = exchange_auth_code(code_or_token)
            print(f"Access Token successfully generated!")
        
        # Test with Nifty August Future
        # Let's try current/latest or August contract
        symbol = sys.argv[2] if len(sys.argv) > 2 else "NSE:NIFTY25AUGFUT"
        print(f"\nFetching OHLCV + OI data for {symbol}...")
        df = fetch_historical_data(token, symbol)
        print("\n--- Top 5 Candles ---")
        print(df.head())
        print("\n--- Last 5 Candles ---")
        print(df.tail())
        
        # Save to CSV
        csv_file = f"{symbol.replace(':', '_')}_history.csv"
        df.to_csv(csv_file, index=False)
        print(f"\nData saved to {csv_file}")
