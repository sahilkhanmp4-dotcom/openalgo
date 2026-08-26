import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# डेटा स्टोर करने का रास्ता
STORAGE_DIR = os.path.expanduser("~/market_data")
os.makedirs(STORAGE_DIR, exist_ok=True)

OPENALGO_HOST = "http://127.0.0.1:5000"
# OpenAlgo की सेटिंग्स से अपनी API Key यहाँ डालें (यदि ऑथेंटिकेशन ऑन है)
API_KEY = "YOUR_OPENALGO_API_KEY"

def sync_symbol_history(symbol="NSE:NIFTY50-INDEX", interval="1m", days=10):
    file_path = os.path.join(STORAGE_DIR, f"{symbol.replace(':', '_')}_{interval}.parquet")
    
    start_date = None
    df_existing = pd.DataFrame()
    
    # 1. चेक करें कि लोकल डेटा कहाँ तक मौजूद है
    if os.path.exists(file_path):
        df_existing = pd.read_parquet(file_path)
        if not df_existing.empty:
            last_recorded_time = df_existing['timestamp'].max()
            start_date = last_recorded_time.strftime("%Y-%m-%d")
            print(f"[{symbol}] लोकल डेटा उपलब्ध है: {last_recorded_time} तक")
    
    # अगर फ़ाइल नहीं है, तो पिछले N दिनों का डेटा लाएँ
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        print(f"[{symbol}] नया सिंबल! पिछला {days} दिनों का डेटा सिंक किया जा रहा है...")

    end_date = datetime.now().strftime("%Y-%m-%d")

    # 2. केवल मिसिंग रेंज के लिए OpenAlgo History API को कॉल करें
    url = f"{OPENALGO_HOST}/api/v1/history"
    params = {
        "symbol": symbol,
        "interval": interval,
        "from_date": start_date,
        "to_date": end_date,
        "apikey": API_KEY
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if data.get("status") == "success" and data.get("data"):
            df_new = pd.DataFrame(data["data"])
            df_new['timestamp'] = pd.to_datetime(df_new['timestamp'])
            
            # 3. पुराने और नए डेटा को मर्ज करें
            df_final = pd.concat([df_existing, df_new]).drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
            
            # 4. फास्ट Parquet फाइल में सेव करें
            df_final.to_parquet(file_path, index=False)
            print(f"[{symbol}] सिंक पूरा हुआ। कुल कैंडल्स: {len(df_final)}")
            return df_final
        else:
            print(f"[{symbol}] कोई नया डेटा नहीं मिला।")
            return df_existing
    except Exception as e:
        print(f"[{symbol}] सिंक में एरर: {e}")
        return df_existing

if __name__ == "__main__":
    # जिन-जिन सिंबल्स को आप ट्रैक करते हैं, उनकी लिस्ट यहाँ डालें
    watchlist = ["NSE:NIFTY50-INDEX", "NSE:BANKNIFTY-INDEX", "NSE:RELIANCE-EQ"]
    
    print("--- OpenAlgo Incremental Data Sync शुरू हो रहा है ---")
    for sym in watchlist:
        sync_symbol_history(sym, interval="1m")
