"""
Antigravity AlgoPlatform Backend Web Server
Provides high-speed endpoints for AI Strategy Synthesis, Backtesting,
Multi-Broker Execution (Fyers & Crypto), and Live Orderbook Sync.
"""

import os
import sys
import uuid
from flask import Flask, request, jsonify, send_from_directory

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.ai_engine import AntigravityAIEngine
from backend.runner import StrategyRunner
from backend.broker_gateway import BrokerRouter

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "frontend"))
router = BrokerRouter()

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "frontend"), "index.html")

@app.route("/api/ai/parse", methods=["POST"])
def ai_parse():
    data = request.get_json() or {}
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"status": "error", "message": "Prompt is required"}), 400
    config = AntigravityAIEngine.parse_prompt(prompt)
    python_code = AntigravityAIEngine.generate_python_code(config)
    return jsonify({
        "status": "success",
        "config": config,
        "python_code": python_code
    })

@app.route("/api/code/generate", methods=["POST"])
def code_generate():
    data = request.get_json() or {}
    code = AntigravityAIEngine.generate_python_code(data)
    return jsonify({"status": "success", "code": code})

@app.route("/api/backtest/run", methods=["POST"])
def run_backtest():
    config = request.get_json() or {}
    res = StrategyRunner.run_backtest(config)
    return jsonify(res)

@app.route("/api/deploy/openalgo", methods=["POST"])
def deploy_to_openalgo():
    data = request.get_json() or {}
    strat_name = data.get("strategy_name", "AI_Algo")
    symbol = data.get("symbol", "NIFTY")
    broker = data.get("broker", "FYERS")
    quantity = int(data.get("quantity", 50))
    action = data.get("action", "BUY")
    sl = float(data.get("stoploss_pct", 0.8))
    tg = float(data.get("target_pct", 2.4))
    
    bot_id = f"bot_{str(uuid.uuid4())[:8]}"
    router.register_bot(bot_id, strat_name, symbol, broker, data)
    
    # Place initial trigger / order
    order_res = router.place_order(
        broker_type=broker,
        symbol=symbol,
        action=action,
        quantity=quantity,
        price_type="MARKET",
        stoploss=sl,
        target=tg,
        strategy_tag=strat_name
    )
    
    return jsonify({
        "status": "success",
        "message": f"Strategy '{strat_name}' successfully deployed to OpenAlgo ({broker})!",
        "bot_id": bot_id,
        "order": order_res
    })

@app.route("/api/live/bots", methods=["GET"])
def get_live_bots():
    return jsonify({"status": "success", "bots": router.get_running_bots()})

@app.route("/api/live/action", methods=["POST"])
def bot_action():
    data = request.get_json() or {}
    bot_id = data.get("bot_id")
    action = data.get("action")
    if router.update_bot_status(bot_id, action):
        return jsonify({"status": "success", "message": f"Bot {bot_id} updated to {action}"})
    return jsonify({"status": "error", "message": "Bot not found"}), 404

@app.route("/api/live/orderbook", methods=["GET"])
def get_live_orderbook():
    return jsonify({"status": "success", "orders": router.get_orderbook()})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8888))
    print(f"🚀 Starting Antigravity AlgoStudio on http://127.0.0.1:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=False)
