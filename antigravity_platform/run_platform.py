#!/usr/bin/env python3
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from backend.app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8888))
    print(f"🚀 Starting Antigravity AlgoStudio 2.0 on http://127.0.0.1:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=False)
