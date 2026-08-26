"""
OpenAlgo Pine Script v5 & Automated Webhook Code Generator
Generates full TradingView strategies with automated OpenAlgo JSON Webhook triggers.
"""

from typing import Dict, Any

class PineScriptGenerator:
    @staticmethod
    def generate_pinescript_v5(config: Dict[str, Any], webhook_url: str = "http://127.0.0.1:5000/strategy/webhook/YOUR_WEBHOOK_ID") -> str:
        strat_name = config.get("strategy_name", "OpenAlgo_Trend_Strategy")
        symbol = config.get("symbol", "NIFTY")
        exchange = config.get("exchange", "NSE_INDEX")
        fast_ema = config.get("indicators", {}).get("fast_ema", 20) if isinstance(config.get("indicators"), dict) else 20
        slow_ema = config.get("indicators", {}).get("slow_ema", 50) if isinstance(config.get("indicators"), dict) else 50
        rsi_period = config.get("indicators", {}).get("rsi_period", 14) if isinstance(config.get("indicators"), dict) else 14
        rsi_thresh = config.get("indicators", {}).get("rsi_threshold", 50) if isinstance(config.get("indicators"), dict) else 50
        sl_pct = config.get("stoploss_val", 0.8)
        tg_pct = config.get("target_val", 1.8)
        quantity = config.get("quantity", 50)

        pinescript_code = f'''//@version=5
strategy("{strat_name}", overlay=true, initial_capital=100000, default_qty_type=strategy.fixed, default_qty_value={quantity})

// --- INPUT PARAMETERS ---
fastLength = input.int({fast_ema}, title="Fast EMA Period", minval=1)
slowLength = input.int({slow_ema}, title="Slow EMA Period", minval=1)
rsiLength  = input.int({rsi_period}, title="RSI Period", minval=1)
rsiThreshold = input.int({rsi_thresh}, title="RSI Bullish Filter", minval=1, maxval=100)

stopLossPct = input.float({sl_pct}, title="Stop Loss (%)", step=0.1) / 100.0
takeProfitPct = input.float({tg_pct}, title="Take Profit (%)", step=0.1) / 100.0

startHour = input.int(9, title="Trading Start Hour")
startMinute = input.int(20, title="Trading Start Minute")
endHour = input.int(15, title="Trading End Hour")
endMinute = input.int(15, title="Trading End Minute")

// --- INDICATORS ---
fastEma = ta.ema(close, fastLength)
slowEma = ta.ema(close, slowLength)
rsiVal  = ta.rsi(close, rsiLength)

plot(fastEma, color=color.new(color.teal, 0), title="Fast EMA", linewidth=2)
plot(slowEma, color=color.new(color.orange, 0), title="Slow EMA", linewidth=2)

// --- TIME WINDOW CHECK ---
inSession = (hour > startHour or (hour == startHour and minute >= startMinute)) and (hour < endHour or (hour == endHour and minute <= endMinute))

// --- SIGNAL CONDITIONS ---
longCondition = ta.crossover(fastEma, slowEma) and (rsiVal >= rsiThreshold) and inSession
shortCondition = ta.crossunder(fastEma, slowEma) and (rsiVal <= (100 - rsiThreshold)) and inSession

// --- OPENALGO WEBHOOK JSON ALERTS ---
// Copy this JSON into TradingView Alert Message for zero-touch auto trading:
/*
BUY Alert JSON:
{{
  "action": "BUY",
  "symbol": "{symbol}",
  "exchange": "{exchange}",
  "quantity": {quantity},
  "product": "MIS",
  "pricetype": "MARKET"
}}

SELL/EXIT Alert JSON:
{{
  "action": "SELL",
  "symbol": "{symbol}",
  "exchange": "{exchange}",
  "quantity": {quantity},
  "product": "MIS",
  "pricetype": "MARKET"
}}
*/

// --- STRATEGY EXECUTION ---
if (longCondition and strategy.position_size == 0)
    strategy.entry("Long", strategy.long)
    alert('{{\\n  "action": "BUY",\\n  "symbol": "{symbol}",\\n  "exchange": "{exchange}",\\n  "quantity": {quantity},\\n  "product": "MIS",\\n  "pricetype": "MARKET"\\n}}', alert.freq_once_per_bar_close)

if (shortCondition and strategy.position_size == 0)
    strategy.entry("Short", strategy.short)
    alert('{{\\n  "action": "SELL",\\n  "symbol": "{symbol}",\\n  "exchange": "{exchange}",\\n  "quantity": {quantity},\\n  "product": "MIS",\\n  "pricetype": "MARKET"\\n}}', alert.freq_once_per_bar_close)

// Exit rules
longSL = strategy.position_avg_price * (1 - stopLossPct)
longTP = strategy.position_avg_price * (1 + takeProfitPct)
shortSL = strategy.position_avg_price * (1 + stopLossPct)
shortTP = strategy.position_avg_price * (1 - takeProfitPct)

if (strategy.position_size > 0)
    strategy.exit("Exit Long", "Long", stop=longSL, limit=longTP)

if (strategy.position_size < 0)
    strategy.exit("Exit Short", "Short", stop=shortSL, limit=shortTP)

// Auto Square-off at end of session
if (not inSession and strategy.position_size != 0)
    strategy.close_all(comment="Intraday Squareoff")
'''
        return pinescript_code
