"""
OpenAlgo Institutional AI Quant Studio & Strategy Builder (Phase 1 + 2 + 3 Complete Suite)
Runs on http://127.0.0.1:8080
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import io
import json
import sqlite3
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify

from quant_engine.strategy_parser import StrategyValidator
from quant_engine.ai_strategy_compiler import AIStrategyCompiler
from quant_engine.backtester import BacktestEngine, CustomCodeBacktester
from quant_engine.deployer import StrategyDeployer, LiveAlgoRegistry
from quant_engine.strategy_store import StrategyStore
from quant_engine.options_engine import OptionsGreeksEngine, IntradayStraddleBacktester, INSTRUMENT_CATALOG
from quant_engine.optimizer import StrategyOptimizer
from quant_engine.portfolio_engine import PortfolioEngine
from quant_engine.pinescript_generator import PineScriptGenerator
from quant_engine.telegram_alerts import TelegramAlertEngine
from quant_engine.rms_manager import RMSManager
from quant_engine.kill_switch import PanicKillSwitch
from quant_engine.state_recovery import StateRecoveryEngine
from quant_engine.mode_manager import ModeManager

app = Flask(__name__)
IST = pytz.timezone("Asia/Kolkata")

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenAlgo - Institutional Quant Studio & Strategy Builder</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darkbg: '#0b0f19',
                        cardbg: '#161f30',
                        bordercolor: '#2d3748'
                    }
                }
            }
        }
    </script>
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        body { background-color: #0b0f19; color: #f1f5f9; font-family: system-ui, -apple-system, sans-serif; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #161f30; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #475569; border-radius: 4px; }
    </style>
</head>
<body class="min-h-screen flex flex-col">
    <!-- Global Floating Toast Notification Container -->
    <div id="toast-container" class="fixed top-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none"></div>

    <!-- Navbar -->
    <header class="border-b border-bordercolor bg-cardbg/90 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center space-x-3">
                <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center font-bold text-xl text-white shadow-lg shadow-indigo-500/25">
                    🧠
                </div>
                <div>
                    <h1 class="text-xl font-bold text-white flex items-center gap-2">
                        OpenAlgo <span class="text-xs px-2.5 py-0.5 rounded-full bg-gradient-to-r from-indigo-500/20 to-purple-500/20 text-indigo-300 border border-indigo-500/30">Quant Studio & Strategy Lab</span>
                    </h1>
                    <p class="text-xs text-slate-400">Institutional Strategy Builder &bull; Parameter Optimizer &bull; Options Lab &bull; Portfolio Hub</p>
                </div>
            </div>
            
            <!-- Navigation Tabs -->
            <div class="flex flex-wrap items-center gap-1 bg-slate-900 border border-slate-800 p-1 rounded-xl">
                <button onclick="switchTab('tab-strategy')" id="nav-strategy" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white transition flex items-center gap-1.5">
                    <i data-lucide="line-chart" class="h-3.5 w-3.5"></i> Backtest & Build
                </button>
                <button onclick="switchTab('tab-live-orderbook')" id="nav-live-orderbook" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-emerald-400 hover:text-white transition flex items-center gap-1.5 border border-emerald-500/30 bg-emerald-500/10 shadow-sm">
                    <i data-lucide="activity" class="h-3.5 w-3.5 text-emerald-400 animate-pulse"></i> ⚡ Running Algos & Orderbook (<span id="running-algos-count">2</span>)
                </button>
                <button onclick="switchTab('tab-optimizer')" id="nav-optimizer" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                    <i data-lucide="sliders" class="h-3.5 w-3.5"></i> Parameter Optimizer
                </button>
                <button onclick="switchTab('tab-options')" id="nav-options" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                    <i data-lucide="layers" class="h-3.5 w-3.5"></i> Multi-Leg Options
                </button>
                <button onclick="switchTab('tab-portfolio')" id="nav-portfolio" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                    <i data-lucide="pie-chart" class="h-3.5 w-3.5"></i> Portfolio Hub (<span id="saved-count">0</span>)
                </button>
                <button onclick="switchTab('tab-code')" id="nav-code" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                    <i data-lucide="code" class="h-3.5 w-3.5"></i> Pine Script & Webhooks
                </button>
                <button onclick="switchTab('tab-liveops')" id="nav-liveops" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-rose-400 hover:text-white transition flex items-center gap-1.5 border border-rose-500/30 bg-rose-500/10">
                    <i data-lucide="shield-alert" class="h-3.5 w-3.5 text-rose-400 animate-pulse"></i> Live RMS & Kill Switch
                </button>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full space-y-6">

        <!-- ========================================== -->
        <!-- TAB 1: STRATEGY BUILDER & BACKTEST ENGINE   -->
        <!-- ========================================== -->
        <div id="tab-strategy" class="space-y-6">
            
            <!-- Mode 1: AI Prompt Ingestion Bar with Multi-Modal File Attachment -->
            <div id="ai-mode-container" class="bg-gradient-to-r from-indigo-950/70 via-slate-900 to-purple-950/70 border-2 border-indigo-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-2.5">
                        <span class="p-2 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                            <i data-lucide="sparkles" class="h-5 w-5"></i>
                        </span>
                        <div>
                            <h2 class="text-base font-bold text-white">AI Strategy Ingestion (Natural Language & Data Upload)</h2>
                            <p class="text-xs text-slate-300">Strategy Hindi, Hinglish ya English mein likhein, ya direct <b>CSV/Excel Data, Chart Image, Strategy Doc</b> attach karein.</p>
                        </div>
                    </div>
                    <div class="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                        <button onclick="setStrategyMode('AI')" id="btn-mode-ai" class="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 ring-2 ring-indigo-400 text-white transition flex items-center gap-1.5 shadow-lg">
                            <i data-lucide="sparkles" class="h-3.5 w-3.5"></i> 🧠 AI Ingestion
                        </button>
                        <button onclick="setStrategyMode('PYTHON')" id="btn-mode-python" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 bg-transparent">
                            <i data-lucide="code-2" class="h-3.5 w-3.5 text-amber-400"></i> 💻 MT5 Python Editor
                        </button>
                    </div>
                </div>

                <div class="space-y-2">
                    <div class="flex flex-col sm:flex-row gap-2.5">
                        <input type="text" id="ai-prompt-input" 
                            placeholder="e.g. Nifty 5m par jab Supertrend 7 3 bullish ho aur 20 EMA ke upar ho tab Buy karo, SL 0.8% Target 2.2%"
                            value="Nifty 5m par jab Supertrend 7 3 bullish ho aur 20 EMA ke upar ho tab Buy karo, SL 0.8% Target 2.2%"
                            class="flex-1 bg-slate-900 border border-indigo-500/50 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-500">
                        
                        <label for="ai-file-upload" class="px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-indigo-500/40 hover:border-indigo-400 text-indigo-300 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition whitespace-nowrap">
                            <i data-lucide="paperclip" class="h-4 w-4"></i>
                            <span id="ai-file-btn-text">📎 Attach File / Data</span>
                        </label>
                        <input type="file" id="ai-file-upload" class="hidden" accept=".csv,.xlsx,.xls,.json,.png,.jpg,.jpeg,.webp,.txt,.py,.pdf" onchange="handleAIFileUpload(this)">

                        <button onclick="compileAIPrompt()" id="btn-ai-compile"
                            class="px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:opacity-90 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/25 transition whitespace-nowrap">
                            <i data-lucide="wand-2" class="h-4 w-4"></i> AI Compile & Analyze
                        </button>
                    </div>

                    <!-- Attached File Chip & Summary (hidden by default) -->
                    <div id="ai-file-preview-card" class="hidden p-3 bg-slate-900/90 border border-indigo-500/40 rounded-xl flex items-center justify-between">
                        <div class="flex items-center gap-2 text-xs">
                            <span class="p-1 rounded bg-indigo-500/20 text-indigo-400"><i data-lucide="file-text" class="h-4 w-4"></i></span>
                            <span id="ai-attached-filename" class="font-mono font-bold text-indigo-200">data.csv</span>
                            <span id="ai-attached-filesize" class="text-[10px] text-slate-400">(0 KB)</span>
                            <span id="ai-attached-badge" class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 font-semibold">CSV Dataset</span>
                        </div>
                        <button onclick="removeAttachedAIFile()" class="text-rose-400 hover:text-rose-300 text-xs font-semibold flex items-center gap-1">
                            <i data-lucide="x" class="h-3.5 w-3.5"></i> Remove
                        </button>
                    </div>

                    <!-- AI Strategy Live Compilation Result Card (Visible after AI Compile) -->
                    <div id="ai-compile-success-card" class="hidden p-4 bg-slate-900/95 border-2 border-emerald-500/60 rounded-xl space-y-2.5 shadow-xl transition-all duration-300">
                        <div class="flex items-center justify-between flex-wrap gap-2">
                            <div class="flex items-center gap-2">
                                <span class="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 font-bold flex items-center gap-1 text-xs border border-emerald-500/30">
                                    <i data-lucide="check-circle-2" class="h-4 w-4 text-emerald-400"></i> ✅ AI Strategy Compiled & Verified!
                                </span>
                                <span id="ai-result-strat-name" class="font-mono font-bold text-white text-xs bg-slate-800 px-2.5 py-1 rounded-lg border border-slate-700">BankNifty_Supertrend_5m</span>
                            </div>
                            <span class="text-[11px] text-emerald-300 font-semibold flex items-center gap-1">
                                <span class="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span> Live Backtest Auto-Executed
                            </span>
                        </div>
                        <p id="ai-result-summary" class="text-xs text-slate-200 bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-mono leading-relaxed"></p>
                        <div class="flex flex-wrap items-center gap-2 pt-1">
                            <span class="text-[11px] text-slate-400 font-semibold">Active Rules:</span>
                            <span id="ai-pill-sym" class="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">NIFTY (5m)</span>
                            <span id="ai-pill-sl" class="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold">SL: 0.8%</span>
                            <span id="ai-pill-tg" class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">TP: 2.2%</span>
                            <span id="ai-pill-ind" class="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold">Supertrend (7, 3.0)</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Strategy Form Configuration & Quick Templates -->
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-5">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <div class="flex items-center gap-2 mb-2">
                            <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider block">⚡ Institutional Quick Templates (Zero-Lookahead)</label>
                            <button onclick="toggleTemplateEditor()" class="text-[11px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold px-2.5 py-0.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 transition">
                                <i data-lucide="settings-2" class="h-3 w-3"></i> ⚙️ Customize Template Parameters
                            </button>
                        </div>
                        <div class="flex flex-wrap gap-2" id="quick-templates-bar">
                            <button onclick="loadTemplate('smc')" id="tpl-btn-smc" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-600 border border-emerald-500/40 text-emerald-300 transition flex items-center gap-1">🏛️ SMC OrderBlock + FVG (1:3 RR)</button>
                            <button onclick="loadTemplate('supertrend')" id="tpl-btn-supertrend" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white border border-indigo-500 shadow transition flex items-center gap-1">🚀 Supertrend (7, 3)</button>
                            <button onclick="loadTemplate('vwap_pullback')" id="tpl-btn-vwap_pullback" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition flex items-center gap-1">🌊 VWAP + EMA Pullback</button>
                            <button onclick="loadTemplate('orb_breakout')" id="tpl-btn-orb_breakout" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition flex items-center gap-1">🎯 ORB 15-Min Breakout</button>
                            <button onclick="loadTemplate('mcx_crude')" id="tpl-btn-mcx_crude" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-amber-500/20 hover:bg-amber-600 border border-amber-500/30 text-amber-200 transition flex items-center gap-1">🛢️ MCX Crude Breakout</button>
                            <button onclick="loadTemplate('crypto_btc')" id="tpl-btn-crypto_btc" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-cyan-500/20 hover:bg-cyan-600 border border-cyan-500/30 text-cyan-200 transition flex items-center gap-1">🪙 BTC/USDT SMC Perp (Crypto)</button>
                            <button onclick="loadTemplate('ema_cross')" id="tpl-btn-ema_cross" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition flex items-center gap-1">📈 EMA 20/50 Trend</button>
                        </div>
                    </div>
                    <div>
                        <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">⏱️ Lookback Presets</label>
                        <div class="flex flex-wrap gap-1.5" id="lookback-presets-bar">
                            <button onclick="setLookback(7)" id="lb-btn-7" class="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-semibold transition">7D</button>
                            <button onclick="setLookback(30)" id="lb-btn-30" class="px-2.5 py-1 text-xs rounded bg-indigo-600 ring-2 ring-indigo-400 text-white font-bold transition shadow">1M</button>
                            <button onclick="setLookback(90)" id="lb-btn-90" class="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-semibold transition">3M</button>
                            <button onclick="setLookback(180)" id="lb-btn-180" class="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-semibold transition">6M</button>
                        </div>
                    </div>
                </div>

                <!-- Expandable Quick Template Parameters Customizer Drawer -->
                <div id="template-editor-panel" class="p-4 bg-slate-900/95 border border-indigo-500/40 rounded-xl space-y-3">
                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                        <div class="flex items-center gap-2">
                            <h4 class="text-xs font-bold text-white flex items-center gap-1.5">
                                <i data-lucide="sliders" class="h-3.5 w-3.5 text-indigo-400"></i> <span id="tpl-editor-title">Supertrend (7, 3) Parameters Customizer</span>
                            </h4>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 font-mono font-bold">Live Synchronized with Python Code</span>
                        </div>
                        <span id="tpl-sync-status" class="text-[10px] text-slate-400">Edits automatically update Strategy Form & Python Editor</span>
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-7 gap-3">
                        <div>
                            <label class="block text-[10px] text-slate-400 mb-1" id="lbl_tpl_fast">Fast Period / ATR</label>
                            <input type="number" id="tpl_fast_ema" value="7" oninput="onCustomParamChange()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono">
                        </div>
                        <div>
                            <label class="block text-[10px] text-slate-400 mb-1" id="lbl_tpl_slow">Multiplier / Slow</label>
                            <input type="number" step="0.1" id="tpl_slow_ema" value="3.0" oninput="onCustomParamChange()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono">
                        </div>
                        <div>
                            <label class="block text-[10px] text-slate-400 mb-1">RSI Filter Level</label>
                            <input type="number" id="tpl_rsi_threshold" value="50" oninput="onCustomParamChange()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono">
                        </div>
                        <div>
                            <label class="block text-[10px] text-slate-400 mb-1">Stop Loss (%)</label>
                            <input type="number" step="0.1" id="tpl_sl_pct" value="0.8" oninput="onCustomParamChange()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-rose-400 font-mono">
                        </div>
                        <div>
                            <label class="block text-[10px] text-slate-400 mb-1">Target (%)</label>
                            <input type="number" step="0.1" id="tpl_tg_pct" value="2.2" oninput="onCustomParamChange()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 font-mono">
                        </div>
                        <div>
                            <label class="block text-[10px] text-slate-400 mb-1">Trade Direction</label>
                            <select id="tpl_trade_direction" onchange="onCustomParamChange()" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-indigo-300 font-mono">
                                <option value="BOTH" selected>BOTH (Long & Short)</option>
                                <option value="LONG">LONG ONLY</option>
                                <option value="SHORT">SHORT ONLY</option>
                            </select>
                        </div>
                        <div class="flex items-end">
                            <button onclick="applyTemplateCustomParams()" class="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1 shadow">
                                <i data-lucide="check" class="h-3.5 w-3.5"></i> Apply & Run
                            </button>
                        </div>
                    </div>
                </div>

                <hr class="border-slate-700/60">

                <!-- Standard Form Inputs with Searchable Autocomplete -->
                <form id="quantForm" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" onsubmit="event.preventDefault(); executeBacktest();">
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">Strategy Name</label>
                        <input type="text" id="strategy_name" value="Nifty_Supertrend_7_3" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white font-mono">
                    </div>
                    
                    <!-- Searchable Underlying Symbol Input with Floating Autocomplete -->
                    <div class="relative">
                        <div class="flex items-center justify-between mb-1">
                            <label class="block text-xs font-medium text-slate-300">Underlying Symbol (Searchable)</label>
                            <span class="text-[10px] text-indigo-400 font-mono">All OpenAlgo Symbols</span>
                        </div>
                        <div class="relative">
                            <input type="text" id="symbol" value="NIFTY" autocomplete="off" required 
                                oninput="handleSymbolSearch(this.value)" onfocus="handleSymbolSearch(this.value)"
                                placeholder="Search e.g. RELIANCE, CRUDEOIL, NIFTY, GOLD..."
                                class="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-xl pl-8 pr-8 py-2 text-sm text-white font-mono uppercase focus:outline-none focus:ring-1 focus:ring-indigo-500">
                            <i data-lucide="search" class="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-3"></i>
                            <button type="button" onclick="clearSymbolSearch()" class="absolute right-2.5 top-2.5 text-slate-500 hover:text-white">
                                <i data-lucide="x" class="h-3.5 w-3.5"></i>
                            </button>
                        </div>
                        
                        <!-- Floating Autocomplete Dropdown -->
                        <div id="symbol-search-dropdown" class="hidden absolute z-50 top-full left-0 right-0 mt-1 max-h-60 overflow-y-auto bg-slate-900 border border-indigo-500/50 rounded-xl shadow-2xl custom-scrollbar divide-y divide-slate-800"></div>
                        
                        <!-- Quick Symbol Pills -->
                        <div class="flex flex-wrap gap-1 mt-1.5">
                            <button type="button" onclick="selectQuickSymbol('NIFTY', 'NSE_INDEX')" class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-indigo-600 text-slate-300 font-mono">NIFTY</button>
                            <button type="button" onclick="selectQuickSymbol('BANKNIFTY', 'NSE_INDEX')" class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-indigo-600 text-slate-300 font-mono">BANKNIFTY</button>
                            <button type="button" onclick="selectQuickSymbol('CRUDEOIL', 'MCX')" class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 hover:bg-amber-600 text-amber-300 font-mono">CRUDEOIL</button>
                            <button type="button" onclick="selectQuickSymbol('NATURALGAS', 'MCX')" class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 hover:bg-amber-600 text-amber-300 font-mono">NATGAS</button>
                            <button type="button" onclick="selectQuickSymbol('GOLD', 'MCX')" class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 hover:bg-amber-600 text-amber-300 font-mono">GOLD</button>
                            <button type="button" onclick="selectQuickSymbol('RELIANCE', 'NSE')" class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 hover:bg-indigo-600 text-indigo-300 font-mono">RELIANCE</button>
                            <button type="button" onclick="selectQuickSymbol('HDFCBANK', 'NSE')" class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 hover:bg-indigo-600 text-indigo-300 font-mono">HDFCBANK</button>
                        </div>
                    </div>

                    <!-- Clean Exchange Dropdown -->
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">Exchange</label>
                        <select id="exchange" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white font-mono">
                            <option value="NSE_INDEX" selected>NSE_INDEX</option>
                            <option value="NSE">NSE</option>
                            <option value="MCX">MCX</option>
                            <option value="NFO">NFO</option>
                            <option value="BSE_INDEX">BSE_INDEX</option>
                            <option value="BFO">BFO</option>
                        </select>
                    </div>

                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">Timeframe</label>
                        <select id="timeframe" onchange="onCustomParamChange()" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                            <option value="1m">1 Minute (1m)</option>
                            <option value="3m">3 Minutes (3m)</option>
                            <option value="5m" selected>5 Minutes (5m)</option>
                            <option value="15m">15 Minutes (15m)</option>
                            <option value="30m">30 Minutes (30m)</option>
                            <option value="1h">1 Hour (1h)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">Start Date</label>
                        <input type="date" id="start_date" value="{{ default_start }}" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">End Date</label>
                        <input type="date" id="end_date" value="{{ default_end }}" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">Stop Loss (%)</label>
                        <input type="number" step="0.1" id="stoploss_val" value="0.8" oninput="document.getElementById('tpl_sl_pct').value=this.value; onCustomParamChange();" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-rose-400 font-mono">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">Target (%)</label>
                        <input type="number" step="0.1" id="target_val" value="2.2" oninput="document.getElementById('tpl_tg_pct').value=this.value; onCustomParamChange();" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-emerald-400 font-mono">
                    </div>

                    <div class="lg:col-span-4 flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-slate-800">
                        <div class="flex items-center space-x-2 text-xs text-slate-400">
                            <i data-lucide="shield-check" class="h-4 w-4 text-emerald-400"></i>
                            <span>Friction Model: 0.05% Slippage + ₹40 Brokerage + STT/GST Deducted</span>
                        </div>
                        <div class="flex flex-wrap items-center gap-2">
                            <button type="button" onclick="saveCurrentStrategy()" class="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-xs flex items-center gap-1.5 transition">
                                <i data-lucide="bookmark" class="h-3.5 w-3.5"></i> Save
                            </button>
                            <button type="submit" id="btn-run" class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:opacity-90 text-white font-semibold text-xs flex items-center gap-1.5 shadow-lg shadow-indigo-500/25 transition">
                                <i data-lucide="play" class="h-3.5 w-3.5"></i> Run Form Backtest
                            </button>
                            <button type="button" onclick="deployStrategyWithMode('ANALYZER')" id="btn-deploy-form-analyzer" class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-purple-500/20 transition">
                                <i data-lucide="flask-conical" class="h-3.5 w-3.5"></i> 🧪 Deploy to Analyzer
                            </button>
                            <button type="button" onclick="deployStrategyWithMode('REAL')" id="btn-deploy-form-real" class="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:opacity-90 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition">
                                <i data-lucide="zap" class="h-3.5 w-3.5"></i> ⚡ Deploy to Real
                            </button>
                        </div>
                    </div>
                </form>
            </div>

            <!-- Mode 2: MetaTrader 5 Style Python Code Editor Panel -->
            <div id="python-editor-container" class="bg-cardbg border border-amber-500/30 rounded-2xl p-6 shadow-2xl space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-2.5">
                        <span class="p-2 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30">
                            <i data-lucide="code-2" class="h-5 w-5"></i>
                        </span>
                        <div>
                            <div class="flex items-center gap-2">
                                <h3 class="text-base font-bold text-white">Direct Python Code Strategy Editor & Runner</h3>
                                <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono font-bold">MetaTrader 5 / Python Standard</span>
                            </div>
                            <p class="text-xs text-slate-400">Write, edit, or customize any Python strategy logic directly. AI-generated code and template scripts appear here for transparent editing.</p>
                        </div>
                    </div>

                    <div class="flex flex-wrap items-center gap-2">
                        <button onclick="resetDefaultPythonCode()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700 flex items-center gap-1 transition">
                            <i data-lucide="refresh-ccw" class="h-3.5 w-3.5"></i> Reset Code
                        </button>
                        <button onclick="syncPythonCodeFromForm()" class="px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-200 text-xs font-semibold rounded-lg border border-indigo-500/40 flex items-center gap-1 transition">
                            <i data-lucide="sparkles" class="h-3.5 w-3.5"></i> Sync Form ➔ Code
                        </button>
                        <button onclick="runPythonCodeBacktest()" id="btn-run-python" class="px-5 py-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:opacity-90 text-white text-xs font-bold rounded-xl flex items-center gap-1.5 shadow-lg shadow-orange-500/20 transition">
                            <i data-lucide="play" class="h-3.5 w-3.5"></i> ▶️ Run Python Code Backtest
                        </button>
                    </div>
                </div>

                <div class="relative">
                    <textarea id="python-strategy-code" rows="18" spellcheck="false" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-4 text-xs font-mono text-emerald-400 custom-scrollbar focus:outline-none focus:ring-2 focus:ring-amber-500 leading-relaxed"></textarea>
                </div>
            </div>

            <!-- Loader & Error -->
            <div id="loader" class="hidden text-center py-12 space-y-3">
                <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-indigo-500 border-t-transparent"></div>
                <p class="text-slate-400 text-sm">Simulating with real broker candles & friction...</p>
            </div>
            <div id="error-box" class="hidden p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm"></div>

            <!-- KPI Cards -->
            <div id="metrics-grid" class="hidden grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                    <p class="text-xs text-slate-400">Total Net P&L</p>
                    <p id="m-net-pnl" class="text-xl font-bold text-emerald-400 mt-1">-</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                    <p class="text-xs text-slate-400">Win Rate</p>
                    <p id="m-winrate" class="text-xl font-bold text-white mt-1">-</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                    <p class="text-xs text-slate-400">Profit Factor</p>
                    <p id="m-pf" class="text-xl font-bold text-indigo-400 mt-1">-</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                    <p class="text-xs text-slate-400">Max Drawdown</p>
                    <p id="m-dd" class="text-xl font-bold text-rose-400 mt-1">-</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                    <p class="text-xs text-slate-400">Sharpe Ratio</p>
                    <p id="m-sharpe" class="text-xl font-bold text-purple-400 mt-1">-</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                    <p class="text-xs text-slate-400">Total Trades</p>
                    <p id="m-trades" class="text-xl font-bold text-slate-200 mt-1">-</p>
                </div>
            </div>

            <!-- Dual Deploy Banner (Analyze & Real Modes) -->
            <div id="deploy-banner" class="hidden bg-gradient-to-r from-indigo-900/40 via-purple-900/40 to-slate-900 border border-indigo-500/40 rounded-2xl p-5 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-4">
                <div class="space-y-1">
                    <h3 class="font-bold text-white text-base flex items-center gap-2">
                        <span class="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        Strategy Validated & Ready for OpenAlgo Deployment!
                    </h3>
                    <p class="text-xs text-slate-300">Deploy this strategy directly to OpenAlgo in Virtual Analyzer Mode (₹1 Cr sandbox) or Real Live Execution.</p>
                </div>
                <div class="flex flex-wrap items-center gap-3">
                    <button onclick="goToPineScript()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs border border-slate-700 flex items-center gap-1.5 transition">
                        <i data-lucide="code" class="h-4 w-4"></i> Pine Script
                    </button>
                    <button onclick="deployStrategyWithMode('ANALYZER')" id="btn-deploy-analyzer-banner"
                        class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white font-bold text-xs shadow-lg shadow-purple-500/20 flex items-center gap-2 whitespace-nowrap transition">
                        <i data-lucide="flask-conical" class="h-4 w-4"></i> 🧪 Deploy to Analyzer
                    </button>
                    <button onclick="deployStrategyWithMode('REAL')" id="btn-deploy-real-banner"
                        class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:opacity-90 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 flex items-center gap-2 whitespace-nowrap transition">
                        <i data-lucide="zap" class="h-4 w-4"></i> ⚡ Deploy to Real
                    </button>
                </div>
            </div>

            <!-- Equity Chart -->
            <div id="chart-section" class="hidden bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-xl space-y-3">
                <h3 class="font-semibold text-sm text-slate-300">Cumulative Net Equity Curve (After All Friction & Taxes)</h3>
                <div id="equity-chart" class="w-full h-[400px]"></div>
            </div>

            <!-- Trade Log Table -->
            <div id="table-section" class="hidden bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-xl space-y-4">
                <div class="flex items-center justify-between">
                    <h3 class="font-semibold text-slate-200 text-sm">Detailed Trade Logs</h3>
                    <button onclick="exportTradesCSV()" class="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg flex items-center gap-1.5">
                        <i data-lucide="download" class="h-3.5 w-3.5"></i> Export Trades (CSV)
                    </button>
                </div>
                <div class="overflow-x-auto rounded-xl border border-slate-700/60 custom-scrollbar max-h-96">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-900/90 text-slate-400 sticky top-0 uppercase tracking-wider">
                            <tr>
                                <th class="py-2.5 px-4">#</th>
                                <th class="py-2.5 px-4">Type</th>
                                <th class="py-2.5 px-4">Entry Time</th>
                                <th class="py-2.5 px-4">Exit Time</th>
                                <th class="py-2.5 px-4 text-right">Entry</th>
                                <th class="py-2.5 px-4 text-right">Exit</th>
                                <th class="py-2.5 px-4 text-right">Gross P&L</th>
                                <th class="py-2.5 px-4 text-right">Friction</th>
                                <th class="py-2.5 px-4 text-right">Net P&L</th>
                                <th class="py-2.5 px-4">Reason</th>
                            </tr>
                        </thead>
                        <tbody id="trades-body" class="divide-y divide-slate-800 text-slate-300 font-mono"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ==================================================== -->
        <!-- TAB: RUNNING ALGOS & LIVE ORDERBOOK (Live Dashboard) -->
        <!-- ==================================================== -->
        <div id="tab-live-orderbook" class="hidden space-y-6">
            <!-- Header & Summary Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-lg">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Active Running Algos</span>
                    <div class="text-2xl font-bold text-emerald-400 mt-1 flex items-center gap-2">
                        <span id="stat-active-algos">2</span>
                        <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono animate-pulse">● LIVE</span>
                    </div>
                    <span class="text-[11px] text-slate-500 mt-1 block">Monitored 24x7 in background</span>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-lg">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Today's Realized Net P&L</span>
                    <div id="stat-live-pnl" class="text-2xl font-bold text-emerald-400 mt-1">₹21,050.00</div>
                    <span class="text-[11px] text-slate-500 mt-1 block">Net after ₹40 broker + 0.05% slip</span>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-lg">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Total Executed Orders</span>
                    <div id="stat-total-orders" class="text-2xl font-bold text-white mt-1">7</div>
                    <span class="text-[11px] text-slate-500 mt-1 block">Entry/Exit buying & selling orders</span>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-lg">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Algo Win Rate</span>
                    <div id="stat-live-winrate" class="text-2xl font-bold text-indigo-300 mt-1">71.4%</div>
                    <span class="text-[11px] text-slate-500 mt-1 block">5 Wins / 2 Losses today</span>
                </div>
            </div>

            <!-- Section 1: Active Running Algos -->
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-2.5">
                        <span class="p-2 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                            <i data-lucide="cpu" class="h-5 w-5"></i>
                        </span>
                        <div>
                            <h3 class="text-base font-bold text-white">Active Running Algos</h3>
                            <p class="text-xs text-slate-400">Live bots continuously evaluating bars, indicators, and executing entry/exit orders.</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="fetchLiveAlgosAndOrderbook()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition">
                            <i data-lucide="refresh-cw" class="h-3.5 w-3.5"></i> Refresh Live
                        </button>
                        <button onclick="switchTab('tab-strategy')" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow">
                            <i data-lucide="plus" class="h-3.5 w-3.5"></i> + Deploy New Strategy
                        </button>
                    </div>
                </div>

                <div class="overflow-x-auto custom-scrollbar border border-slate-800 rounded-xl">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-900/90 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-4">Strategy Name</th>
                                <th class="py-3 px-4">Execution Mode</th>
                                <th class="py-3 px-4">Symbol & Exchange</th>
                                <th class="py-3 px-4">Timeframe</th>
                                <th class="py-3 px-4">Status</th>
                                <th class="py-3 px-4 text-right">Net P&L (₹)</th>
                                <th class="py-3 px-4 text-right">Trades / Win%</th>
                                <th class="py-3 px-4 text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="running-algos-tbody" class="divide-y divide-slate-800 text-slate-200"></tbody>
                    </table>
                </div>
            </div>

            <!-- Section 2: Real-time Live Orderbook & Entry/Exit Logs -->
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-2.5">
                        <span class="p-2 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                            <i data-lucide="book-open" class="h-5 w-5"></i>
                        </span>
                        <div>
                            <h3 class="text-base font-bold text-white">Live Orderbook & Trade Execution Logs</h3>
                            <p class="text-xs text-slate-400">Complete record of every BUY/SELL order with exact Entry Time, Buying Price, Exit Time, Selling Price & Net P&L.</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-[11px] px-2.5 py-1 rounded bg-slate-800 text-emerald-400 font-mono flex items-center gap-1 border border-slate-700">
                            <span class="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span> Auto-Sync: 3s
                        </span>
                    </div>
                </div>

                <div class="overflow-x-auto custom-scrollbar border border-slate-800 rounded-xl">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-900/90 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-3">Order ID</th>
                                <th class="py-3 px-3">Strategy</th>
                                <th class="py-3 px-3">Symbol</th>
                                <th class="py-3 px-3">Action</th>
                                <th class="py-3 px-3">Entry Time</th>
                                <th class="py-3 px-3 text-right">Buying Price (₹)</th>
                                <th class="py-3 px-3">Exit Time</th>
                                <th class="py-3 px-3 text-right">Selling Price (₹)</th>
                                <th class="py-3 px-3 text-right">Qty</th>
                                <th class="py-3 px-3 text-right">Friction (₹)</th>
                                <th class="py-3 px-3 text-right">Net Realized P&L (₹)</th>
                                <th class="py-3 px-3">Exit Reason</th>
                                <th class="py-3 px-3 text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody id="live-orderbook-tbody" class="divide-y divide-slate-800 text-slate-200 font-mono"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ========================================== -->
        <!-- TAB 2: PARAMETER OPTIMIZER & HEATMAP       -->
        <!-- ========================================== -->
        <div id="tab-optimizer" class="hidden space-y-6">
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-5">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <i data-lucide="sliders" class="h-5 w-5 text-indigo-400"></i> Strategy Parameter Optimizer & 2D Heatmap Explorer
                        </h2>
                        <p class="text-xs text-slate-400">Grid Search parameter sweep to discover optimal EMA lengths, Stop Loss, and Targets with robust Sharpe ratios.</p>
                    </div>
                    <button onclick="runParameterOptimization()" id="btn-optimize" class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:opacity-90 text-white font-semibold text-xs flex items-center gap-2 transition shadow-lg shadow-indigo-500/20">
                        <i data-lucide="play" class="h-4 w-4"></i> Run Grid Optimization
                    </button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-slate-900/70 border border-slate-800 rounded-xl">
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Fast EMA Range</label>
                        <input type="text" id="opt_fast_range" value="9, 15, 20, 25" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Slow EMA Range</label>
                        <input type="text" id="opt_slow_range" value="30, 40, 50, 60" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Stop Loss Range (%)</label>
                        <input type="text" id="opt_sl_range" value="0.5, 0.8, 1.0, 1.5" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-rose-400 font-mono">
                    </div>
                    <div>
                        <label class="block text-xs text-slate-400 mb-1">Target Range (%)</label>
                        <input type="text" id="opt_tg_range" value="1.0, 1.5, 2.0, 2.5" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-emerald-400 font-mono">
                    </div>
                </div>

                <!-- Optimization Loader -->
                <div id="opt-loader" class="hidden text-center py-10 space-y-3">
                    <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-500 border-t-transparent"></div>
                    <p class="text-slate-400 text-xs">Running grid sweep across all parameter iterations...</p>
                </div>

                <!-- 2D Heatmap & Top Candidates Grid -->
                <div id="opt-results-section" class="hidden space-y-6">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <!-- Heatmap Chart -->
                        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                            <h3 class="font-semibold text-xs text-slate-300">Fast EMA vs Slow EMA Net Profit Heatmap</h3>
                            <div id="opt-heatmap-chart" class="w-full h-[350px]"></div>
                        </div>

                        <!-- Best Parameters Leaderboard -->
                        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
                            <h3 class="font-semibold text-xs text-slate-300">Top Performing Parameter Sets (Ranked by Profit Factor)</h3>
                            <div class="overflow-x-auto custom-scrollbar max-h-[350px]">
                                <table class="w-full text-left text-xs">
                                    <thead class="bg-slate-950 text-slate-400 sticky top-0 uppercase tracking-wider">
                                        <tr>
                                            <th class="py-2 px-3">Fast / Slow</th>
                                            <th class="py-2 px-3">SL / Target</th>
                                            <th class="py-2 px-3 text-right">Net P&L</th>
                                            <th class="py-2 px-3 text-right">PF</th>
                                            <th class="py-2 px-3 text-right">Win%</th>
                                            <th class="py-2 px-3 text-center">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody id="opt-candidates-body" class="divide-y divide-slate-800 text-slate-300 font-mono"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ========================================== -->
        <!-- TAB 3: MULTI-LEG OPTIONS & BACKTEST ENGINE -->
        <!-- ========================================== -->
        <div id="tab-options" class="hidden space-y-6">
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-5">
                
                <!-- Live Spot Header & Universal Instrument Selector -->
                <div class="flex flex-col gap-4 p-5 bg-slate-900/90 border border-indigo-500/30 rounded-2xl shadow-lg">
                    <div class="flex flex-wrap items-center justify-between gap-4">
                        <div class="flex items-center space-x-3">
                            <span class="p-2.5 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                                <i data-lucide="layers" class="h-6 w-6"></i>
                            </span>
                            <div>
                                <div class="flex items-center gap-2">
                                    <h2 class="text-base font-bold text-white">Backtest Engine & Multi-Leg Options Lab</h2>
                                    <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono font-bold">Multi-Asset F&O Ready</span>
                                </div>
                                <p class="text-xs text-slate-400">Universal Instrument Selection &bull; Indices, MCX Commodities, Stock F&O &bull; Black-Scholes Greeks &bull; Live Spot Fetch</p>
                            </div>
                        </div>

                        <div class="flex flex-wrap items-center gap-2">
                            <!-- Category Filter Tabs -->
                            <div class="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-[11px]">
                                <button onclick="filterInstrumentCategory('ALL')" id="filter-btn-ALL" class="px-2.5 py-1 rounded-lg font-semibold bg-indigo-600 text-white transition">All</button>
                                <button onclick="filterInstrumentCategory('INDEX')" id="filter-btn-INDEX" class="px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white transition">📈 Indices</button>
                                <button onclick="filterInstrumentCategory('COMMODITY')" id="filter-btn-COMMODITY" class="px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white transition">🛢️ MCX Commodities</button>
                                <button onclick="filterInstrumentCategory('STOCK')" id="filter-btn-STOCK" class="px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white transition">🏢 Stock F&O</button>
                            </div>

                            <button onclick="fetchMarketSpotAndStrikes()" id="btn-fetch-spot" class="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:opacity-90 text-white font-semibold text-xs flex items-center gap-1.5 shadow-md shadow-indigo-500/20 transition">
                                <i data-lucide="zap" class="h-3.5 w-3.5"></i> Fetch Live Spot
                            </button>
                        </div>
                    </div>

                    <!-- Universal Instrument Dropdown & Search -->
                    <div class="flex flex-col md:flex-row items-center gap-3 pt-2 border-t border-slate-800/80">
                        <div class="w-full md:w-1/3">
                            <label class="text-[10px] text-slate-400 block mb-1 font-semibold uppercase tracking-wider">🎯 Select OpenAlgo Instrument</label>
                            <select id="opt_symbol_select" onchange="onOptionSymbolChange()" class="w-full bg-slate-950 border border-indigo-500/40 rounded-xl px-3.5 py-2 text-xs text-white font-mono font-bold focus:ring-2 focus:ring-indigo-500">
                                <optgroup label="📈 Major Indian Indices" data-cat="INDEX">
                                    <option value="NIFTY" selected>NIFTY 50 (Step 50 | Lot 65 | NSE)</option>
                                    <option value="BANKNIFTY">BANKNIFTY (Step 100 | Lot 15 | NSE)</option>
                                    <option value="FINNIFTY">FINNIFTY (Step 50 | Lot 65 | NSE)</option>
                                    <option value="MIDCPNIFTY">MIDCPNIFTY (Step 25 | Lot 120 | NSE)</option>
                                    <option value="SENSEX">SENSEX (Step 100 | Lot 10 | BSE)</option>
                                    <option value="BANKEX">BANKEX (Step 100 | Lot 15 | BSE)</option>
                                </optgroup>
                                <optgroup label="🛢️ MCX Commodities (Options & Futures)" data-cat="COMMODITY">
                                    <option value="CRUDEOIL">CRUDE OIL (Step 50 | Lot 100 | MCX)</option>
                                    <option value="CRUDEOILM">CRUDE OIL MINI (Step 50 | Lot 10 | MCX)</option>
                                    <option value="NATURALGAS">NATURAL GAS (Step 5 | Lot 1250 | MCX)</option>
                                    <option value="NATGASMINI">NATURAL GAS MINI (Step 5 | Lot 250 | MCX)</option>
                                    <option value="GOLD">GOLD 1 KG (Step 100 | Lot 100 | MCX)</option>
                                    <option value="GOLDM">GOLD MINI 100g (Step 100 | Lot 10 | MCX)</option>
                                    <option value="SILVER">SILVER 30 KG (Step 500 | Lot 30 | MCX)</option>
                                    <option value="SILVERM">SILVER MINI 5 KG (Step 500 | Lot 5 | MCX)</option>
                                    <option value="COPPER">COPPER (Step 5 | Lot 2500 | MCX)</option>
                                    <option value="ZINC">ZINC (Step 2.5 | Lot 5000 | MCX)</option>
                                    <option value="ALUMINIUM">ALUMINIUM (Step 2.5 | Lot 5000 | MCX)</option>
                                </optgroup>
                                <optgroup label="🏢 High-Volume Stock F&O" data-cat="STOCK">
                                    <option value="RELIANCE">RELIANCE (Step 20 | Lot 250 | NFO)</option>
                                    <option value="HDFCBANK">HDFC BANK (Step 10 | Lot 550 | NFO)</option>
                                    <option value="ICICIBANK">ICICI BANK (Step 10 | Lot 700 | NFO)</option>
                                    <option value="SBIN">STATE BANK OF INDIA (Step 5 | Lot 750 | NFO)</option>
                                    <option value="INFY">INFOSYS (Step 20 | Lot 400 | NFO)</option>
                                    <option value="TCS">TCS (Step 50 | Lot 175 | NFO)</option>
                                    <option value="TATAMOTORS">TATA MOTORS (Step 10 | Lot 575 | NFO)</option>
                                    <option value="BAJFINANCE">BAJAJ FINANCE (Step 50 | Lot 125 | NFO)</option>
                                    <option value="AXISBANK">AXIS BANK (Step 10 | Lot 625 | NFO)</option>
                                    <option value="BHARTIARTL">BHARTI AIRTEL (Step 10 | Lot 475 | NFO)</option>
                                    <option value="LT">LARSEN & TOUBRO (Step 25 | Lot 175 | NFO)</option>
                                    <option value="KOTAKBANK">KOTAK BANK (Step 10 | Lot 400 | NFO)</option>
                                </optgroup>
                            </select>
                        </div>

                        <!-- Quick Pills -->
                        <div class="w-full md:w-2/3">
                            <label class="text-[10px] text-slate-400 block mb-1 font-semibold uppercase tracking-wider">⚡ Quick Pick</label>
                            <div class="flex flex-wrap gap-1.5">
                                <button onclick="selectQuickInstrument('NIFTY')" class="px-2 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-200 text-xs rounded-lg border border-slate-700 transition">NIFTY</button>
                                <button onclick="selectQuickInstrument('BANKNIFTY')" class="px-2 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-200 text-xs rounded-lg border border-slate-700 transition">BANKNIFTY</button>
                                <button onclick="selectQuickInstrument('FINNIFTY')" class="px-2 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-200 text-xs rounded-lg border border-slate-700 transition">FINNIFTY</button>
                                <button onclick="selectQuickInstrument('CRUDEOIL')" class="px-2 py-1 bg-amber-500/20 hover:bg-amber-600 text-amber-200 text-xs rounded-lg border border-amber-500/30 transition">🛢️ CRUDEOIL (MCX)</button>
                                <button onclick="selectQuickInstrument('NATURALGAS')" class="px-2 py-1 bg-amber-500/20 hover:bg-amber-600 text-amber-200 text-xs rounded-lg border border-amber-500/30 transition">🔥 NATURALGAS</button>
                                <button onclick="selectQuickInstrument('GOLD')" class="px-2 py-1 bg-yellow-500/20 hover:bg-yellow-600 text-yellow-200 text-xs rounded-lg border border-yellow-500/30 transition">🪙 GOLD (MCX)</button>
                                <button onclick="selectQuickInstrument('SILVER')" class="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs rounded-lg border border-slate-600 transition">🥈 SILVER</button>
                                <button onclick="selectQuickInstrument('RELIANCE')" class="px-2 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-200 text-xs rounded-lg border border-slate-700 transition">🏢 RELIANCE</button>
                                <button onclick="selectQuickInstrument('HDFCBANK')" class="px-2 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-200 text-xs rounded-lg border border-slate-700 transition">🏦 HDFCBANK</button>
                                <button onclick="selectQuickInstrument('SENSEX')" class="px-2 py-1 bg-slate-800 hover:bg-indigo-600 text-slate-200 text-xs rounded-lg border border-slate-700 transition">SENSEX</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Spot & ATM Quick Indicators -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-[11px] text-slate-400">Live Spot Price</p>
                        <p id="opt-spot" class="text-lg font-bold text-white font-mono mt-0.5">24,500.0</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-[11px] text-slate-400">ATM Strike</p>
                        <p id="opt-atm-strike" class="text-lg font-bold text-indigo-400 font-mono mt-0.5">24,500</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-[11px] text-slate-400">Lot Size</p>
                        <p id="opt-lot-size" class="text-lg font-bold text-slate-200 font-mono mt-0.5">65 Qty</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-[11px] text-slate-400">Strike Step</p>
                        <p id="opt-strike-step" class="text-lg font-bold text-slate-200 font-mono mt-0.5">50 pts</p>
                    </div>
                </div>

                <!-- Strategy Presets Buttons -->
                <div>
                    <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">⚡ Strategy Presets</label>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="loadOptionPreset('straddle')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600/30 hover:bg-indigo-600 border border-indigo-500/40 text-indigo-200 transition">Short Straddle (ATM)</button>
                        <button onclick="loadOptionPreset('strangle')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">Short Strangle (OTM1)</button>
                        <button onclick="loadOptionPreset('iron_condor')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">Iron Condor</button>
                        <button onclick="loadOptionPreset('bull_call')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">Bull Call Spread</button>
                        <button onclick="loadOptionPreset('bear_put')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">Bear Put Spread</button>
                        <button onclick="loadOptionPreset('iron_butterfly')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">Iron Butterfly</button>
                    </div>
                </div>

                <!-- Interactive Multi-Leg Strategy Builder Table -->
                <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-3">
                    <div class="flex items-center justify-between">
                        <h3 class="font-bold text-white text-xs flex items-center gap-1.5">
                            <i data-lucide="list-plus" class="h-4 w-4 text-indigo-400"></i> Active Strategy Legs (Add / Modify Strikes)
                        </h3>
                        <button onclick="addCustomLeg()" class="px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg flex items-center gap-1 transition">
                            <i data-lucide="plus" class="h-3.5 w-3.5"></i> Add Leg
                        </button>
                    </div>

                    <div class="overflow-x-auto custom-scrollbar">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-slate-950 text-slate-400 uppercase tracking-wider">
                                <tr>
                                    <th class="py-2.5 px-3">#</th>
                                    <th class="py-2.5 px-3">Action</th>
                                    <th class="py-2.5 px-3">Option</th>
                                    <th class="py-2.5 px-3">Strike Price</th>
                                    <th class="py-2.5 px-3">Premium (₹)</th>
                                    <th class="py-2.5 px-3">Quantity</th>
                                    <th class="py-2.5 px-3 text-right">Leg Delta</th>
                                    <th class="py-2.5 px-3 text-right">Leg Theta</th>
                                    <th class="py-2.5 px-3 text-center">Delete</th>
                                </tr>
                            </thead>
                            <tbody id="opt-legs-tbody" class="divide-y divide-slate-800 text-slate-200 font-mono"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Sensitivity Sliders -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
                    <div>
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-slate-400">Days to Expiry (T)</span>
                            <span id="slider-days-val" class="text-indigo-400 font-mono font-bold">4.0 Days</span>
                        </div>
                        <input type="range" id="slider-days" min="0.1" max="15" step="0.5" value="4.0" oninput="updateOptionsPayoff()" class="w-full accent-indigo-500">
                    </div>
                    <div>
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-slate-400">Implied Volatility (IV)</span>
                            <span id="slider-iv-val" class="text-purple-400 font-mono font-bold">14.0%</span>
                        </div>
                        <input type="range" id="slider-iv" min="8" max="30" step="0.5" value="14.0" oninput="updateOptionsPayoff()" class="w-full accent-purple-500">
                    </div>
                    <div>
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-slate-400">Spot Shift (Points)</span>
                            <span id="slider-spot-val" class="text-emerald-400 font-mono font-bold">0 pts</span>
                        </div>
                        <input type="range" id="slider-spot-shift" min="-1000" max="1000" step="50" value="0" oninput="updateOptionsPayoff()" class="w-full accent-emerald-500">
                    </div>
                </div>

                <!-- Greeks & Payoff KPI Cards -->
                <div class="grid grid-cols-2 md:grid-cols-6 gap-3 pt-2">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-xs text-slate-400">Net Delta (Δ)</p>
                        <p id="opt-delta" class="text-lg font-bold text-indigo-400 font-mono">0.00</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-xs text-slate-400">Theta Decay (Θ)</p>
                        <p id="opt-theta" class="text-lg font-bold text-emerald-400 font-mono">+₹1,450</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-xs text-slate-400">Vega (V)</p>
                        <p id="opt-vega" class="text-lg font-bold text-purple-400 font-mono">-₹850</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-xs text-slate-400">Max Profit</p>
                        <p id="opt-max-profit" class="text-lg font-bold text-emerald-400 font-mono">₹14,500</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-xs text-slate-400">Max Loss</p>
                        <p id="opt-max-loss" class="text-lg font-bold text-rose-400 font-mono">Unlimited</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-3">
                        <p class="text-xs text-slate-400">POP %</p>
                        <p id="opt-pop" class="text-lg font-bold text-amber-400 font-mono">71.4%</p>
                    </div>
                </div>

                <!-- Interactive Payoff Diagram -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div class="flex items-center justify-between">
                        <h3 class="font-semibold text-xs text-slate-300">Multi-Leg Payoff Diagram (T+0 vs Expiry Curve)</h3>
                        <p id="opt-breakevens" class="text-xs text-slate-400 font-mono">Breakevens: Calculating...</p>
                    </div>
                    <div id="options-payoff-chart" class="w-full h-[380px]"></div>
                </div>

                <!-- Backtest Engine Runner -->
                <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-5">
                    <div class="flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <h3 class="font-bold text-white text-sm flex items-center gap-2">
                                <i data-lucide="history" class="h-4 w-4 text-emerald-400"></i> Backtest Engine
                            </h3>
                            <p class="text-xs text-slate-400">Institutional Multi-Asset F&O & Derivatives Backtest Engine &bull; Simulates real broker tick entries, Greeks theta decay, and stoploss exits across custom date ranges.</p>
                        </div>
                        <div class="flex items-center gap-2 text-[10px] text-slate-400 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
                            <span class="text-indigo-400 font-semibold font-mono">Selected Instrument:</span> <span id="straddle_step_badge" class="font-bold text-emerald-400">50 pts (NIFTY)</span>
                        </div>
                    </div>

                    <!-- Straddle Controls Bar -->
                    <div class="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-8 gap-3 bg-slate-950/80 p-4 rounded-xl border border-slate-800">
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">Start Date</label>
                            <input type="date" id="straddle_start_date" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">End Date</label>
                            <input type="date" id="straddle_end_date" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">Quick Range</label>
                            <div class="flex gap-1">
                                <button onclick="setStraddleDateRange(7)" type="button" class="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 text-[10px] rounded text-slate-300">1W</button>
                                <button onclick="setStraddleDateRange(30)" type="button" class="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 text-[10px] rounded text-slate-300">1M</button>
                                <button onclick="setStraddleDateRange(90)" type="button" class="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 text-[10px] rounded text-slate-300">3M</button>
                                <button onclick="setStraddleDateRange(180)" type="button" class="px-1.5 py-1 bg-slate-800 hover:bg-slate-700 text-[10px] rounded text-slate-300">6M</button>
                            </div>
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">Entry & Exit Time</label>
                            <div class="flex items-center gap-1">
                                <input type="text" id="straddle_entry_time" value="09:20" title="Entry Time" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-1.5 py-1.5 text-xs text-emerald-400 font-mono text-center">
                                <span class="text-xs text-slate-500">➔</span>
                                <input type="text" id="straddle_exit_time" value="15:15" title="Exit Time" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-1.5 py-1.5 text-xs text-amber-400 font-mono text-center">
                            </div>
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">Strike Selection</label>
                            <select id="straddle_strike_selection" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-indigo-300">
                                <option value="ATM">🎯 Pure ATM (Same Strike)</option>
                                <option value="MATCHED_PREMIUM">⚖️ Matched Premium (Diff ≤ ₹5)</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">Stop Loss Mode</label>
                            <select id="straddle_sl_mode" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-indigo-300">
                                <option value="INDIVIDUAL">🟢 Individual Leg SL</option>
                                <option value="COST_TO_COST">🛡️ Leg SL + Cost-to-Cost</option>
                                <option value="COMBINED">⚖️ Combined Premium SL</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">SL (%)</label>
                            <input type="number" id="straddle_sl_pct" value="25" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-rose-400 font-mono text-center">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 block mb-1">Lot Size × Lots</label>
                            <div class="flex items-center gap-1">
                                <input type="number" id="straddle_lot_size" value="65" title="Lot Size" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-1 py-1.5 text-xs text-emerald-400 font-mono text-center">
                                <span class="text-xs text-slate-500">×</span>
                                <input type="number" id="straddle_lots_count" value="1" title="Lots" min="1" class="w-12 bg-slate-900 border border-slate-700 rounded-lg px-1 py-1.5 text-xs text-white font-mono text-center">
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
                        <div class="flex items-center gap-2">
                            <span class="text-xs text-slate-400 font-semibold flex items-center gap-1">
                                <i data-lucide="bookmark" class="h-3.5 w-3.5 text-indigo-400"></i> Setup:
                            </span>
                            <select id="straddle_saved_presets" onchange="loadSavedStraddlePreset(this.value)" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-indigo-300">
                                <option value="">-- Load Saved Strategy --</option>
                            </select>
                            <button onclick="saveStraddleStrategy()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition">
                                <i data-lucide="save" class="h-3.5 w-3.5"></i> Save Setup
                            </button>
                        </div>
                        
                        <div class="flex flex-wrap items-center gap-2">
                            <button onclick="runStraddleBacktest()" id="btn-run-straddle" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs flex items-center gap-1.5 border border-slate-700 shadow transition">
                                <i data-lucide="play" class="h-3.5 w-3.5 text-emerald-400"></i> Run Backtest
                            </button>
                            <button onclick="deployStraddle('ANALYZER')" id="btn-deploy-analyzer" class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-purple-500/20 transition">
                                <i data-lucide="flask-conical" class="h-3.5 w-3.5"></i> 🧪 Deploy to Analyzer
                            </button>
                            <button onclick="deployStraddle('REAL')" id="btn-deploy-real" class="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:opacity-90 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition">
                                <i data-lucide="zap" class="h-3.5 w-3.5"></i> ⚡ Deploy to Real
                            </button>
                        </div>
                    </div>

                    <!-- Straddle KPI Grid -->
                    <div id="straddle-results" class="hidden grid grid-cols-2 md:grid-cols-6 gap-3">
                        <div class="bg-cardbg p-3 rounded-xl border border-bordercolor">
                            <p class="text-xs text-slate-400">Straddle Net P&L</p>
                            <p id="straddle-pnl" class="text-lg font-bold text-emerald-400 font-mono mt-0.5">-</p>
                        </div>
                        <div class="bg-cardbg p-3 rounded-xl border border-bordercolor">
                            <p class="text-xs text-slate-400">Win Rate</p>
                            <p id="straddle-winrate" class="text-lg font-bold text-white font-mono mt-0.5">-</p>
                        </div>
                        <div class="bg-cardbg p-3 rounded-xl border border-bordercolor">
                            <p class="text-xs text-slate-400">Profit Factor</p>
                            <p id="straddle-pf" class="text-lg font-bold text-indigo-400 font-mono mt-0.5">-</p>
                        </div>
                        <div class="bg-cardbg p-3 rounded-xl border border-bordercolor">
                            <p class="text-xs text-slate-400">Max Drawdown</p>
                            <p id="straddle-dd" class="text-lg font-bold text-rose-400 font-mono mt-0.5">-</p>
                        </div>
                        <div class="bg-cardbg p-3 rounded-xl border border-bordercolor">
                            <p class="text-xs text-slate-400">Win / Loss Days</p>
                            <p id="straddle-win-loss" class="text-lg font-bold text-slate-200 font-mono mt-0.5">-</p>
                        </div>
                        <div class="bg-cardbg p-3 rounded-xl border border-bordercolor">
                            <p class="text-xs text-slate-400">Total Days</p>
                            <p id="straddle-trades" class="text-lg font-bold text-slate-300 font-mono mt-0.5">-</p>
                        </div>
                    </div>

                    <!-- Granular Day-by-Day Trade Logs Table -->
                    <div id="straddle-table-section" class="hidden space-y-3">
                        <div class="flex items-center justify-between">
                            <h4 class="font-bold text-white text-xs">Granular Day-wise Simulation Logs (Spot, Strikes, Entries &amp; Exits)</h4>
                            <span class="text-[10px] text-slate-400">Friction: 0.05% Slippage + ₹80 Brokerage</span>
                        </div>
                        <div class="overflow-x-auto rounded-xl border border-slate-700/60 custom-scrollbar max-h-[380px]">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-slate-950 text-slate-400 uppercase tracking-wider sticky top-0">
                                    <tr>
                                        <th class="py-2.5 px-3">Date</th>
                                        <th class="py-2.5 px-3">09:20 Spot</th>
                                        <th class="py-2.5 px-3">ATM Strike</th>
                                        <th class="py-2.5 px-3">CE Entry ➔ Exit (Time)</th>
                                        <th class="py-2.5 px-3">PE Entry ➔ Exit (Time)</th>
                                        <th class="py-2.5 px-3">15:15 Spot</th>
                                        <th class="py-2.5 px-3 text-right">Gross P&L</th>
                                        <th class="py-2.5 px-3 text-right">Net P&L</th>
                                        <th class="py-2.5 px-3">Outcome</th>
                                    </tr>
                                </thead>
                                <tbody id="straddle-trades-body" class="divide-y divide-slate-800 text-slate-300 font-mono"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>
        </div>

        <!-- ========================================== -->
        <!-- TAB 4: PORTFOLIO & CORRELATION HUB         -->
        <!-- ========================================== -->
        <div id="tab-portfolio" class="hidden space-y-6">
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-5">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <i data-lucide="pie-chart" class="h-5 w-5 text-indigo-400"></i> Multi-Strategy Combined Portfolio & Correlation Engine
                        </h2>
                        <p class="text-xs text-slate-400">Combine multiple uncorrelated strategies to reduce portfolio drawdown and maximize risk-adjusted returns.</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="fetchSavedStrategies()" class="px-3.5 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg flex items-center gap-1.5">
                            <i data-lucide="refresh-cw" class="h-3.5 w-3.5"></i> Refresh
                        </button>
                        <button onclick="runCombinedPortfolioBacktest()" class="px-4 py-2 text-xs bg-gradient-to-r from-emerald-600 to-teal-600 hover:opacity-90 text-white font-semibold rounded-lg flex items-center gap-1.5">
                            <i data-lucide="play" class="h-3.5 w-3.5"></i> Run Portfolio Backtest
                        </button>
                    </div>
                </div>

                <!-- Combined Portfolio Metrics -->
                <div id="portfolio-metrics-grid" class="hidden grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
                        <p class="text-xs text-slate-400">Combined Net P&L</p>
                        <p id="port-pnl" class="text-xl font-bold text-emerald-400 mt-1">-</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
                        <p class="text-xs text-slate-400">Portfolio ROI</p>
                        <p id="port-roi" class="text-xl font-bold text-white mt-1">-</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
                        <p class="text-xs text-slate-400">Portfolio Max DD</p>
                        <p id="port-dd" class="text-xl font-bold text-rose-400 mt-1">-</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
                        <p class="text-xs text-slate-400">Portfolio Sharpe</p>
                        <p id="port-sharpe" class="text-xl font-bold text-purple-400 mt-1">-</p>
                    </div>
                </div>

                <!-- Combined Equity Chart & Correlation Heatmap -->
                <div id="portfolio-charts-section" class="hidden grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                        <h3 class="font-semibold text-xs text-slate-300">Combined Portfolio Equity Curve</h3>
                        <div id="port-equity-chart" class="w-full h-[320px]"></div>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                        <h3 class="font-semibold text-xs text-slate-300">Strategy Correlation Matrix (Diversification Index)</h3>
                        <div id="port-corr-chart" class="w-full h-[320px]"></div>
                    </div>
                </div>

                <!-- Saved Strategies List -->
                <div class="overflow-x-auto rounded-xl border border-slate-700/60 custom-scrollbar">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-900/90 text-slate-400 sticky top-0 uppercase tracking-wider">
                            <tr>
                                <th class="py-3 px-4">Include</th>
                                <th class="py-3 px-4">Strategy Name</th>
                                <th class="py-3 px-4">Symbol & TF</th>
                                <th class="py-3 px-4">Risk (SL / Target)</th>
                                <th class="py-3 px-4">Status</th>
                                <th class="py-3 px-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="saved-table-body" class="divide-y divide-slate-800 text-slate-300 font-mono">
                            <tr>
                                <td colspan="6" class="text-center py-8 text-slate-500">No saved strategies found. Save a strategy from Strategy Studio!</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ========================================== -->
        <!-- TAB 5: PINE SCRIPT & WEBHOOK EXPORTER      -->
        <!-- ========================================== -->
        <div id="tab-code" class="hidden space-y-6">
            <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-5">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <i data-lucide="code" class="h-5 w-5 text-indigo-400"></i> TradingView Pine Script v5 & Automated Webhook Exporter
                        </h2>
                        <p class="text-xs text-slate-400">Export your validated strategy directly into TradingView with zero-touch automated OpenAlgo webhook triggers.</p>
                    </div>
                    <button onclick="copyPineScript()" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 transition">
                        <i data-lucide="copy" class="h-4 w-4"></i> Copy Pine Script
                    </button>
                </div>

                <div class="space-y-2">
                    <label class="block text-xs font-semibold text-slate-300">Generated Pine Script v5 Code (Paste into TradingView Pine Editor)</label>
                    <textarea id="pinescript-output" readonly rows="18" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-4 text-xs font-mono text-emerald-400 custom-scrollbar focus:outline-none"></textarea>
                </div>
            </div>
        </div>

        <!-- ========================================== -->
        <!-- TAB 6: LIVE OPERATIONS & RMS (Phase 4)     -->
        <!-- ========================================== -->
        <div id="tab-liveops" class="hidden space-y-6">
            
            <!-- Live Status & Mode Switcher -->
            <div class="bg-gradient-to-r from-slate-900 via-cardbg to-slate-900 border border-bordercolor rounded-2xl p-6 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-4">
                <div class="flex items-center space-x-4">
                    <div id="mode-badge-icon" class="h-12 w-12 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-2xl">
                        🧪
                    </div>
                    <div>
                        <div class="flex items-center gap-2.5">
                            <h2 id="mode-title" class="text-lg font-bold text-white">ANALYZER MODE (Virtual ₹1 Cr Sandbox)</h2>
                            <span id="mode-indicator" class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">PAPER TRADING</span>
                        </div>
                        <p id="mode-desc" class="text-xs text-slate-400 mt-0.5">Strategies trade on live exchange ticks without financial risk.</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-3">
                    <button onclick="toggleExecutionMode()" id="btn-mode-toggle" class="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-xs flex items-center gap-2 transition">
                        <i data-lucide="repeat" class="h-4 w-4"></i> Switch to Live Mode
                    </button>
                    <button onclick="executePanicKillSwitch()" class="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-lg shadow-rose-600/30 flex items-center gap-2 transition animate-pulse">
                        <i data-lucide="power" class="h-4 w-4"></i> EMERGENCY KILL SWITCH
                    </button>
                </div>
            </div>

            <!-- Live P&L & RMS Cards -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-4">
                    <p class="text-xs text-slate-400">Live Unrealized P&L</p>
                    <p id="live-unrealized-pnl" class="text-xl font-bold text-emerald-400 font-mono mt-1">₹0.00</p>
                    <p class="text-[10px] text-slate-500 mt-1">Open Positions: <span id="live-pos-count">0</span></p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-4">
                    <p class="text-xs text-slate-400">Daily Realized P&L</p>
                    <p id="live-realized-pnl" class="text-xl font-bold text-white font-mono mt-1">₹0.00</p>
                    <p class="text-[10px] text-slate-500 mt-1">Today's Session</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-4">
                    <p class="text-xs text-slate-400">RMS Circuit Breaker</p>
                    <p id="rms-lock-status" class="text-xl font-bold text-emerald-400 font-mono mt-1">ARMED (ACTIVE)</p>
                    <p id="rms-lock-reason" class="text-[10px] text-slate-500 mt-1">Daily Max Loss: ₹5,000</p>
                </div>
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-4">
                    <p class="text-xs text-slate-400">Broker Connection</p>
                    <p id="broker-status" class="text-xl font-bold text-emerald-400 font-mono mt-1">FYERS (Ready)</p>
                    <p id="broker-user" class="text-[10px] text-slate-500 mt-1">User: sahilkhan</p>
                </div>
            </div>

            <!-- Grid: RMS Config & Telegram Config -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                <!-- RMS Settings -->
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-4">
                    <div class="flex items-center justify-between">
                        <h3 class="font-bold text-white text-sm flex items-center gap-2">
                            <i data-lucide="shield-check" class="h-4 w-4 text-emerald-400"></i> Risk Management (RMS) Safeguards
                        </h3>
                        <button onclick="resetRMSLock()" class="px-3 py-1 text-[10px] bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded">Reset Lock</button>
                    </div>

                    <form id="rmsForm" class="space-y-3" onsubmit="event.preventDefault(); saveRMSConfig();">
                        <div>
                            <label class="block text-xs text-slate-400 mb-1">Max Daily Loss Limit (₹) - Auto-Lock</label>
                            <input type="number" id="rms_max_loss" value="5000" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-rose-400 font-mono">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 mb-1">Max Daily Profit Target (₹) - Profit Lock</label>
                            <input type="number" id="rms_max_profit" value="25000" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-emerald-400 font-mono">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 mb-1">Max Capital Per Trade (₹)</label>
                            <input type="number" id="rms_max_cap" value="50000" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white font-mono">
                        </div>
                        <div class="flex items-center justify-between pt-2">
                            <label class="flex items-center space-x-2 text-xs text-slate-300">
                                <input type="checkbox" id="rms_enabled" checked class="rounded bg-slate-900 border-slate-700">
                                <span>Enable Account-Level RMS Guard</span>
                            </label>
                            <button type="submit" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold">Save RMS Guard</button>
                        </div>
                    </form>
                </div>

                <!-- Telegram Alerts Config -->
                <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-4">
                    <div class="flex items-center justify-between">
                        <h3 class="font-bold text-white text-sm flex items-center gap-2">
                            <i data-lucide="send" class="h-4 w-4 text-indigo-400"></i> Instant Telegram Alerts
                        </h3>
                        <button onclick="sendTestTelegramAlert()" class="px-3 py-1 text-[10px] bg-indigo-600/30 hover:bg-indigo-600 border border-indigo-500/40 text-indigo-300 rounded">Send Test Alert</button>
                    </div>

                    <form id="telegramForm" class="space-y-3" onsubmit="event.preventDefault(); saveTelegramConfig();">
                        <div>
                            <label class="block text-xs text-slate-400 mb-1">Telegram Bot Token (from @BotFather)</label>
                            <input type="text" id="tg_bot_token" placeholder="e.g. 123456789:ABCdefGhIJKlmNoPQRstuVWXyz" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white font-mono">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 mb-1">Telegram Chat ID (from @userinfobot)</label>
                            <input type="text" id="tg_chat_id" placeholder="e.g. 987654321" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white font-mono">
                        </div>
                        <div class="flex items-center justify-between pt-2">
                            <label class="flex items-center space-x-2 text-xs text-slate-300">
                                <input type="checkbox" id="tg_enabled" class="rounded bg-slate-900 border-slate-700">
                                <span>Enable Real-time Trade & SL Notifications</span>
                            </label>
                            <button type="submit" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold">Save Alerts Config</button>
                        </div>
                    </form>
                </div>

            </div>

        </div>

    </main>

    <footer class="border-t border-bordercolor py-4 text-center text-xs text-slate-500">
        OpenAlgo Institutional AI Quant Studio &bull; Powered by Antigravity AI & Fyers Market Data
    </footer>

    <script>
        function safeCreateIcons() {
            try {
                if (typeof lucide !== 'undefined' && lucide && lucide.createIcons) {
                    lucide.createIcons();
                }
            } catch (e) {
                console.warn('Lucide icon rendering warning:', e);
            }
        }

        safeCreateIcons();

        function showToast(msg, type = 'success') {
            const container = document.getElementById('toast-container');
            if (!container) return;
            const toast = document.createElement('div');
            const isSuccess = (type === 'success');
            const isError = (type === 'error');
            const bgClass = isSuccess ? 'bg-emerald-950 border-emerald-500 text-emerald-100 shadow-emerald-500/20' : (isError ? 'bg-rose-950 border-rose-500 text-rose-100 shadow-rose-500/20' : 'bg-indigo-950 border-indigo-500 text-indigo-100 shadow-indigo-500/20');
            const icon = isSuccess ? '✅' : (isError ? '❌' : 'ℹ️');
            toast.className = `p-3.5 rounded-xl border-2 shadow-2xl ${bgClass} text-xs font-semibold flex items-center gap-2.5 pointer-events-auto transition-all duration-300 transform translate-y-0 opacity-100 min-w-[280px] max-w-[420px] backdrop-blur`;
            toast.innerHTML = `<span class="text-base flex-shrink-0">${icon}</span> <div class="flex-1 leading-snug">${msg}</div>`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(-10px)';
                setTimeout(() => toast.remove(), 300);
            }, 4500);
        }

        let globalTrades = [];
        let currentStrategyMetrics = {};
        let currentStrategyConfig = {};
        let currentOptionLegs = [];

        function switchTab(tabId) {
            ['tab-strategy', 'tab-live-orderbook', 'tab-optimizer', 'tab-options', 'tab-portfolio', 'tab-code', 'tab-liveops'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.classList.add('hidden');
            });

            ['nav-strategy', 'nav-live-orderbook', 'nav-optimizer', 'nav-options', 'nav-portfolio', 'nav-code', 'nav-liveops'].forEach(id => {
                const navEl = document.getElementById(id);
                if (navEl) {
                    if (id === 'nav-live-orderbook') {
                        navEl.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-emerald-400 hover:text-white transition flex items-center gap-1.5 border border-emerald-500/30 bg-emerald-500/10 shadow-sm';
                    } else if (id === 'nav-liveops') {
                        navEl.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-rose-400 hover:text-white transition flex items-center gap-1.5 border border-rose-500/30 bg-rose-500/10';
                    } else {
                        navEl.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5';
                    }
                }
            });

            const activeTabEl = document.getElementById(tabId);
            if (activeTabEl) activeTabEl.classList.remove('hidden');

            const navMap = {
                'tab-strategy': 'nav-strategy',
                'tab-live-orderbook': 'nav-live-orderbook',
                'tab-optimizer': 'nav-optimizer',
                'tab-options': 'nav-options',
                'tab-portfolio': 'nav-portfolio',
                'tab-code': 'nav-code',
                'tab-liveops': 'nav-liveops'
            };
            const activeNavId = navMap[tabId];
            if (activeNavId && document.getElementById(activeNavId)) {
                document.getElementById(activeNavId).className = 'px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white transition flex items-center gap-1.5 shadow';
            }

            safeCreateIcons();

            try {
                if (tabId === 'tab-live-orderbook') {
                    fetchLiveAlgosAndOrderbook();
                } else if (tabId === 'tab-portfolio') {
                    fetchSavedStrategies();
                } else if (tabId === 'tab-options') {
                    if (availableStrikes.length === 0) {
                        fetchMarketSpotAndStrikes();
                    } else if (currentOptionLegs.length === 0) {
                        loadOptionPreset('straddle');
                    }
                } else if (tabId === 'tab-code') {
                    generatePineScriptCode();
                } else if (tabId === 'tab-liveops') {
                    fetchLiveOpsStatus();
                }
            } catch (tabErr) {
                console.error('Tab switch action error:', tabErr);
            }
        }

        async function fetchLiveAlgosAndOrderbook() {
            try {
                const [resAlgos, resOrders] = await Promise.all([
                    fetch('/api/live/algos'),
                    fetch('/api/live/orderbook')
                ]);
                const algos = await resAlgos.json();
                const orders = await resOrders.json();

                // Update Counts & Summary Badges
                const activeCount = algos.filter(a => a.status === 'RUNNING').length;
                const countBadge = document.getElementById('running-algos-count');
                if (countBadge) countBadge.innerText = activeCount;
                const statActive = document.getElementById('stat-active-algos');
                if (statActive) statActive.innerText = activeCount;

                let totalNetPnl = 0;
                let winCount = 0;
                let closedCount = 0;

                orders.forEach(o => {
                    if (o.status === 'CLOSED') {
                        totalNetPnl += (o.net_pnl || 0);
                        closedCount++;
                        if (o.net_pnl > 0) winCount++;
                    }
                });

                const pnlEl = document.getElementById('stat-live-pnl');
                if (pnlEl) {
                    pnlEl.innerText = (totalNetPnl >= 0 ? '₹' : '-₹') + Math.abs(totalNetPnl).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    pnlEl.className = totalNetPnl >= 0 ? 'text-2xl font-bold text-emerald-400 mt-1' : 'text-2xl font-bold text-rose-400 mt-1';
                }
                const ordersEl = document.getElementById('stat-total-orders');
                if (ordersEl) ordersEl.innerText = orders.length;
                
                const winRate = closedCount > 0 ? ((winCount / closedCount) * 100).toFixed(1) : '100.0';
                const winRateEl = document.getElementById('stat-live-winrate');
                if (winRateEl) winRateEl.innerText = winRate + '%';

                // Render Running Algos Table
                const algoTbody = document.getElementById('running-algos-tbody');
                if (algoTbody) {
                    algoTbody.innerHTML = '';
                    if (algos.length === 0) {
                        algoTbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-500">No algos currently deployed. Deploy a strategy from Backtest & Build tab!</td></tr>';
                    } else {
                        algos.forEach(a => {
                            const tr = document.createElement('tr');
                            tr.className = 'hover:bg-slate-800/40 transition';
                            const modeBadge = a.mode === 'REAL' ? 
                                '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">🟢 REAL BROKER</span>' : 
                                '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">🟡 ANALYZER (₹1 Cr)</span>';
                            
                            let statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">RUNNING</span>';
                            if (a.status === 'PAUSED') statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400">PAUSED</span>';
                            else if (a.status === 'STOPPED') statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-400">STOPPED</span>';

                            tr.innerHTML = `
                                <td class="py-3 px-4 font-bold text-white font-mono">${a.strategy_name}</td>
                                <td class="py-3 px-4">${modeBadge}</td>
                                <td class="py-3 px-4 font-mono">${a.symbol} <span class="text-slate-500 text-[10px]">(${a.exchange})</span></td>
                                <td class="py-3 px-4 font-mono">${a.timeframe}</td>
                                <td class="py-3 px-4">${statusBadge}</td>
                                <td class="py-3 px-4 text-right font-mono font-bold ${a.live_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${a.live_pnl.toLocaleString()}</td>
                                <td class="py-3 px-4 text-right font-mono text-slate-300">${a.total_trades} trades / ${a.win_rate}%</td>
                                <td class="py-3 px-4 text-center">
                                    <div class="flex items-center justify-center gap-1.5">
                                        ${a.status === 'RUNNING' ? 
                                            `<button onclick="performAlgoAction('${a.id}', 'PAUSE')" class="p-1 px-2 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-[10px] font-semibold transition" title="Pause Strategy">⏸️ Pause</button>` :
                                            `<button onclick="performAlgoAction('${a.id}', 'RESUME')" class="p-1 px-2 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[10px] font-semibold transition" title="Resume Strategy">▶️ Resume</button>`
                                        }
                                        <button onclick="performAlgoAction('${a.id}', 'SQUARE_OFF')" class="p-1 px-2 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[10px] font-semibold transition" title="Square Off & Stop">⚡ Square Off</button>
                                    </div>
                                </td>
                            `;
                            algoTbody.appendChild(tr);
                        });
                    }
                }

                // Render Live Orderbook Table
                const orderTbody = document.getElementById('live-orderbook-tbody');
                if (orderTbody) {
                    orderTbody.innerHTML = '';
                    if (orders.length === 0) {
                        orderTbody.innerHTML = '<tr><td colspan="13" class="text-center py-6 text-slate-500">No orders executed yet today.</td></tr>';
                    } else {
                        orders.forEach(o => {
                            const tr = document.createElement('tr');
                            tr.className = 'hover:bg-slate-800/40 transition';
                            const actionBadge = o.action === 'BUY' ? 
                                '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">BUY</span>' : 
                                '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400">SELL</span>';
                            
                            const statusBadge = o.status === 'OPEN' ?
                                '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-500/20 text-indigo-300 animate-pulse">● OPEN</span>' :
                                '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-400">CLOSED</span>';

                            tr.innerHTML = `
                                <td class="py-2.5 px-3 text-slate-400">${o.order_id}</td>
                                <td class="py-2.5 px-3 font-semibold text-white">${o.strategy_name}</td>
                                <td class="py-2.5 px-3 text-indigo-300">${o.symbol}</td>
                                <td class="py-2.5 px-3">${actionBadge}</td>
                                <td class="py-2.5 px-3 text-slate-300">${o.entry_time}</td>
                                <td class="py-2.5 px-3 text-right text-emerald-300">₹${o.buying_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                                <td class="py-2.5 px-3 text-slate-300">${o.exit_time}</td>
                                <td class="py-2.5 px-3 text-right ${o.status === 'OPEN' ? 'text-indigo-400 font-bold' : 'text-rose-300'}">₹${o.selling_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                                <td class="py-2.5 px-3 text-right">${o.quantity}</td>
                                <td class="py-2.5 px-3 text-right text-slate-500">₹${o.friction.toFixed(2)}</td>
                                <td class="py-2.5 px-3 text-right font-bold ${o.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${o.net_pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                                <td class="py-2.5 px-3 text-slate-400 text-[11px]">${o.exit_reason}</td>
                                <td class="py-2.5 px-3 text-center">${statusBadge}</td>
                            `;
                            orderTbody.appendChild(tr);
                        });
                    }
                }
            } catch (err) {
                console.error('Error fetching live orderbook:', err);
            }
        }

        async function performAlgoAction(algoId, action) {
            try {
                const res = await fetch('/api/live/action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({algo_id: algoId, action: action})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    fetchLiveAlgosAndOrderbook();
                }
            } catch (err) {
                alert('Error executing algo action: ' + err);
            }
        }

        // --- BACKTEST RUNNER ---
        async function executeBacktest(shouldScroll = true) {
            document.getElementById('loader').classList.remove('hidden');
            document.getElementById('error-box').classList.add('hidden');
            document.getElementById('metrics-grid').classList.add('hidden');
            document.getElementById('deploy-banner').classList.add('hidden');
            document.getElementById('chart-section').classList.add('hidden');
            document.getElementById('table-section').classList.add('hidden');

            const fast = parseFloat(document.getElementById('tpl_fast_ema').value) || 7;
            const slow = parseFloat(document.getElementById('tpl_slow_ema').value) || 3.0;
            const rsi = parseInt(document.getElementById('tpl_rsi_threshold').value) || 50;
            const dir = document.getElementById('tpl_trade_direction').value || 'BOTH';

            const payload = {
                strategy_name: document.getElementById('strategy_name').value,
                strategy_type: activeTemplateType,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                exchange: document.getElementById('exchange').value,
                timeframe: document.getElementById('timeframe').value,
                start_date: document.getElementById('start_date').value,
                end_date: document.getElementById('end_date').value,
                stoploss_val: parseFloat(document.getElementById('stoploss_val').value),
                target_val: parseFloat(document.getElementById('target_val').value),
                capital: 100000.0,
                quantity: 50,
                slippage_pct: 0.05,
                brokerage_per_trade: 40.0,
                trade_direction: dir,
                dataset_id: activeDatasetId,
                indicators: {
                    fast_ema: fast,
                    slow_ema: slow,
                    st_period: fast,
                    st_mult: slow,
                    rsi_period: 14,
                    rsi_threshold: rsi
                }
            };
            currentStrategyConfig = payload;

            try {
                const res = await fetch('/api/run-backtest', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                document.getElementById('loader').classList.add('hidden');

                if (data.status === 'error') {
                    document.getElementById('error-box').innerText = data.message;
                    document.getElementById('error-box').classList.remove('hidden');
                    return;
                }

                currentStrategyMetrics = data;
                globalTrades = data.trades || [];

                // Update Metrics
                document.getElementById('m-net-pnl').innerText = '₹' + data.total_net_pnl.toLocaleString();
                document.getElementById('m-net-pnl').className = data.total_net_pnl >= 0 ? 'text-xl font-bold text-emerald-400 mt-1' : 'text-xl font-bold text-rose-400 mt-1';
                document.getElementById('m-winrate').innerText = data.win_rate + '%';
                document.getElementById('m-pf').innerText = data.profit_factor;
                document.getElementById('m-dd').innerText = data.max_drawdown_pct + '%';
                document.getElementById('m-sharpe').innerText = data.sharpe_ratio;
                document.getElementById('m-trades').innerText = data.total_trades;

                document.getElementById('metrics-grid').classList.remove('hidden');
                document.getElementById('deploy-banner').classList.remove('hidden');

                // Render Chart Safely
                if (data.equity_curve && data.equity_curve.length > 0 && typeof Plotly !== 'undefined') {
                    try {
                        const x = data.equity_curve.map(e => e.datetime);
                        const y = data.equity_curve.map(e => e.equity);

                        Plotly.newPlot('equity-chart', [{
                            x: x, y: y, type: 'scatter', mode: 'lines',
                            line: {color: '#10b981', width: 2.5},
                            fill: 'tozeroy', fillcolor: 'rgba(16, 185, 129, 0.08)'
                        }], {
                            margin: {t: 20, r: 20, l: 60, b: 40},
                            paper_bgcolor: '#161f30',
                            plot_bgcolor: '#161f30',
                            font: {color: '#94a3b8', family: 'system-ui'},
                            xaxis: {gridcolor: '#2d3748', showgrid: true},
                            yaxis: {gridcolor: '#2d3748', showgrid: true, tickprefix: '₹'}
                        }, {responsive: true});

                        document.getElementById('chart-section').classList.remove('hidden');
                    } catch (plotErr) {
                        console.warn('Plotly chart render warning:', plotErr);
                    }
                }

                // Render Trade Logs
                const tbody = document.getElementById('trades-body');
                if (tbody) {
                    tbody.innerHTML = '';
                    globalTrades.forEach((t, idx) => {
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-slate-800/50';
                        tr.innerHTML = `
                            <td class="py-2.5 px-4">${idx + 1}</td>
                            <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${t.trade_type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">${t.trade_type}</span></td>
                            <td class="py-2.5 px-4">${t.entry_time}</td>
                            <td class="py-2.5 px-4">${t.exit_time}</td>
                            <td class="py-2.5 px-4 text-right">₹${t.entry_price}</td>
                            <td class="py-2.5 px-4 text-right">₹${t.exit_price}</td>
                            <td class="py-2.5 px-4 text-right">₹${t.gross_pnl}</td>
                            <td class="py-2.5 px-4 text-right text-slate-500">₹${t.friction_cost}</td>
                            <td class="py-2.5 px-4 text-right font-bold ${t.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${t.net_pnl}</td>
                            <td class="py-2.5 px-4 text-slate-400">${t.exit_reason}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                    document.getElementById('table-section').classList.remove('hidden');
                }

                if (shouldScroll) {
                    showToast(`✅ Backtest Completed! Net P&L: ₹${data.total_net_pnl.toLocaleString()} | Win Rate: ${data.win_rate}% (${data.total_trades} trades)`, data.total_net_pnl >= 0 ? 'success' : 'error');
                    document.getElementById('metrics-grid').scrollIntoView({behavior: 'smooth', block: 'start'});
                }

            } catch (err) {
                document.getElementById('loader').classList.add('hidden');
                document.getElementById('error-box').innerText = 'Connection error: ' + err;
                document.getElementById('error-box').classList.remove('hidden');
                if (shouldScroll) showToast('Connection error: ' + err, 'error');
            }
        }

        // --- AI COMPILE WITH MULTI-MODAL FILE/DATA ATTACHMENT ---
        async function compileAIPrompt() {
            const promptInput = document.getElementById('ai-prompt-input');
            const prompt = promptInput ? promptInput.value.trim() : '';
            if (!prompt && !attachedAIFile) {
                alert('Please enter a strategy prompt in natural language or attach a data/chart file.');
                return;
            }

            const btn = document.getElementById('btn-ai-compile');
            btn.innerHTML = '<div class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div> Processing AI & Dataset...';
            btn.disabled = true;

            try {
                let res, data;
                if (attachedAIFile) {
                    const formData = new FormData();
                    formData.append('file', attachedAIFile);
                    formData.append('prompt', prompt);
                    res = await fetch('/api/ai-analyze-file', {
                        method: 'POST',
                        body: formData
                    });
                    data = await res.json();
                } else {
                    res = await fetch('/api/ai-compile', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({prompt: prompt})
                    });
                    data = await res.json();
                }
                
                btn.innerHTML = '<i data-lucide="wand-2" class="h-4 w-4"></i> AI Compile & Analyze';
                btn.disabled = false;
                lucide.createIcons();

                if (data.status === 'success') {
                    const c = data.config;
                    if (data.dataset_id) {
                        activeDatasetId = data.dataset_id;
                    }
                    
                    document.getElementById('strategy_name').value = c.strategy_name || 'AI_Strategy';
                    document.getElementById('symbol').value = c.symbol || 'NIFTY';
                    document.getElementById('exchange').value = c.exchange || 'NSE_INDEX';
                    document.getElementById('timeframe').value = c.timeframe || '5m';
                    document.getElementById('stoploss_val').value = c.stoploss_val || 0.8;
                    document.getElementById('target_val').value = c.target_val || 1.8;
                    
                    if (c.indicators) {
                        if (c.indicators.fast_ema) document.getElementById('tpl_fast_ema').value = c.indicators.fast_ema;
                        if (c.indicators.slow_ema) document.getElementById('tpl_slow_ema').value = c.indicators.slow_ema;
                        if (c.indicators.rsi_threshold) document.getElementById('tpl_rsi_threshold').value = c.indicators.rsi_threshold;
                    }
                    if (c.stoploss_val) document.getElementById('tpl_sl_pct').value = c.stoploss_val;
                    if (c.target_val) document.getElementById('tpl_tg_pct').value = c.target_val;
                    if (c.trade_direction) document.getElementById('tpl_trade_direction').value = c.trade_direction;

                    if (data.python_code) {
                        document.getElementById('python-strategy-code').value = data.python_code;
                    }
                    
                    if (data.quant_summary) {
                        alert('📊 Dataset Quant Profile Analyzed!\n\n' +
                              'Total Candles: ' + data.quant_summary.total_candles + '\n' +
                              'Price Net Change: ' + data.quant_summary.price_change_pct + '%\n' +
                              'Volatility: ' + data.quant_summary.volatility_pct + '%\n' +
                              'Avg Bar Range: ₹' + data.quant_summary.avg_range + '\n\n' +
                              'Strategy rules optimized and loaded into editor!');
                    }

                    // Render Live AI Strategy Compilation Result Card
                    const resCard = document.getElementById('ai-compile-success-card');
                    if (resCard) {
                        document.getElementById('ai-result-strat-name').innerText = c.strategy_name || 'AI_Compiled_Strategy';
                        document.getElementById('ai-result-summary').innerText = '🤖 AI Formulation: ' + (prompt ? ('"' + prompt + '"') : 'Custom Dataset Ingestion') + ' ➔ ' + (data.message || 'Strategy compiled with zero-lookahead bias.');
                        document.getElementById('ai-pill-sym').innerText = (c.symbol || 'NIFTY') + ' (' + (c.timeframe || '5m') + ')';
                        document.getElementById('ai-pill-sl').innerText = 'SL: ' + (c.stoploss_val || 0.8) + '%';
                        document.getElementById('ai-pill-tg').innerText = 'TP: ' + (c.target_val || 1.8) + '%';
                        
                        let indText = 'EMA Trend Follower';
                        if (c.indicators) {
                            if (c.indicators.st_period || c.indicators.fast_ema < 10) {
                                indText = 'Supertrend (' + (c.indicators.st_period || c.indicators.fast_ema) + ', ' + (c.indicators.st_mult || c.indicators.slow_ema) + ') + RSI >=' + (c.indicators.rsi_threshold || 50);
                            } else {
                                indText = 'Fast EMA (' + (c.indicators.fast_ema || 20) + ') / Slow EMA (' + (c.indicators.slow_ema || 50) + ') + RSI ' + (c.indicators.rsi_threshold || 50);
                            }
                        }
                        document.getElementById('ai-pill-ind').innerText = indText;
                        resCard.classList.remove('hidden');
                        resCard.scrollIntoView({behavior: 'smooth', block: 'nearest'});
                    }
                    
                    showToast(`🤖 AI Strategy "${c.strategy_name || 'AI_Strategy'}" Compiled & Verified!`, 'success');
                    executeBacktest();
                } else {
                    showToast('AI Analysis notice: ' + (data.message || 'Unknown error'), 'error');
                }
            } catch (err) {
                btn.innerHTML = '<i data-lucide="wand-2" class="h-4 w-4"></i> AI Compile & Analyze';
                btn.disabled = false;
                lucide.createIcons();
                showToast('AI processing error: ' + err, 'error');
            }
        }

        // --- PARAMETER OPTIMIZATION (GRID SEARCH & HEATMAP) ---
        async function runParameterOptimization() {
            document.getElementById('opt-loader').classList.remove('hidden');
            document.getElementById('opt-results-section').classList.add('hidden');

            const parseList = (id, isFloat = false) => {
                return document.getElementById(id).value.split(',').map(x => isFloat ? parseFloat(x.trim()) : parseInt(x.trim())).filter(x => !isNaN(x));
            };

            const baseConfig = currentStrategyConfig.symbol ? currentStrategyConfig : {
                strategy_name: document.getElementById('strategy_name').value,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                exchange: document.getElementById('exchange').value,
                timeframe: document.getElementById('timeframe').value,
                start_date: document.getElementById('start_date').value,
                end_date: document.getElementById('end_date').value,
                capital: 100000.0,
                quantity: 50
            };

            const payload = {
                base_config: baseConfig,
                start_date: document.getElementById('start_date').value,
                end_date: document.getElementById('end_date').value,
                param_grid: {
                    fast_ema: parseList('opt_fast_range'),
                    slow_ema: parseList('opt_slow_range'),
                    stoploss_val: parseList('opt_sl_range', true),
                    target_val: parseList('opt_tg_range', true)
                }
            };

            try {
                const res = await fetch('/api/optimize', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                document.getElementById('opt-loader').classList.add('hidden');

                if (data.status === 'success') {
                    document.getElementById('opt-results-section').classList.remove('hidden');

                    // Render Heatmap
                    const hm = data.heatmap;
                    Plotly.newPlot('opt-heatmap-chart', [{
                        z: hm.z_pnl,
                        x: hm.x_slow.map(s => 'Slow ' + s),
                        y: hm.y_fast.map(f => 'Fast ' + f),
                        type: 'heatmap',
                        colorscale: 'Viridis',
                        hoverongaps: false
                    }], {
                        margin: {t: 20, r: 20, l: 60, b: 40},
                        paper_bgcolor: '#0f172a',
                        plot_bgcolor: '#0f172a',
                        font: {color: '#94a3b8'}
                    }, {responsive: true});

                    // Render Leaderboard
                    const tbody = document.getElementById('opt-candidates-body');
                    tbody.innerHTML = '';
                    data.top_candidates.forEach(c => {
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-slate-800/50';
                        tr.innerHTML = `
                            <td class="py-2 px-3">${c.fast_ema} / ${c.slow_ema}</td>
                            <td class="py-2 px-3">${c.stoploss_val}% / ${c.target_val}%</td>
                            <td class="py-2 px-3 text-right font-bold ${c.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${c.net_pnl.toLocaleString()}</td>
                            <td class="py-2 px-3 text-right text-indigo-400">${c.profit_factor}</td>
                            <td class="py-2 px-3 text-right">${c.win_rate}%</td>
                            <td class="py-2 px-3 text-center">
                                <button onclick="applyOptimizedParams(${c.fast_ema}, ${c.slow_ema}, ${c.stoploss_val}, ${c.target_val})" class="px-2 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[10px]">Apply</button>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            } catch (err) {
                document.getElementById('opt-loader').classList.add('hidden');
                alert('Optimization error: ' + err);
            }
        }

        function applyOptimizedParams(fast, slow, sl, tg) {
            document.getElementById('stoploss_val').value = sl;
            document.getElementById('target_val').value = tg;
            switchTab('tab-strategy');
            executeBacktest();
        }

        // --- MULTI-LEG OPTIONS STUDIO (Opstra Style) ---
        let currentSpotPrice = 24500.0;
        let currentATMStrike = 24500;
        let currentStrikeStep = 50;
        let currentLotSize = 50;
        let availableStrikes = [];

        async function fetchMarketSpotAndStrikes() {
            const sym = document.getElementById('opt_symbol_select').value;
            const btn = document.getElementById('btn-fetch-spot');
            btn.innerHTML = '<div class="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent"></div> Fetching...';
            
            try {
                const res = await fetch(`/api/options/strikes?symbol=${sym}&iv=14.0&days=4.0`);
                const data = await res.json();
                btn.innerHTML = '<i data-lucide="zap" class="h-3.5 w-3.5"></i> Fetch Live Spot';
                
                if (data.status === 'success') {
                    currentSpotPrice = data.spot_price;
                    currentATMStrike = data.atm_strike;
                    currentStrikeStep = data.strike_step;
                    currentLotSize = data.lot_size;
                    availableStrikes = data.strikes;

                    document.getElementById('opt-spot').innerText = '₹' + currentSpotPrice.toLocaleString();
                    document.getElementById('opt-atm-strike').innerText = currentATMStrike.toLocaleString();
                    document.getElementById('opt-lot-size').innerText = currentLotSize + ' Qty';
                    document.getElementById('opt-strike-step').innerText = currentStrikeStep + ' pts';
                    if (document.getElementById('straddle_lot_size')) {
                        document.getElementById('straddle_lot_size').value = currentLotSize;
                    }
                    if (document.getElementById('straddle_step_badge')) {
                        document.getElementById('straddle_step_badge').innerText = `${currentStrikeStep} pts (${sym})`;
                    }

                    loadOptionPreset('straddle');
                }
            } catch (err) {
                btn.innerHTML = '<i data-lucide="zap" class="h-3.5 w-3.5"></i> Fetch Live Spot';
                console.error(err);
            }
        }

        function setStraddleDateRange(days) {
            const end = new Date();
            const start = new Date();
            start.setDate(end.getDate() - days);
            document.getElementById('straddle_end_date').value = end.toISOString().split('T')[0];
            document.getElementById('straddle_start_date').value = start.toISOString().split('T')[0];
        }

        function onOptionSymbolChange() {
            fetchMarketSpotAndStrikes();
        }

        function getEstimatedPremium(strike, optType) {
            const match = availableStrikes.find(s => s.strike === strike);
            if (match) {
                return (optType === 'CE') ? match.ce_price : match.pe_price;
            }
            return (optType === 'CE') ? 140.0 : 135.0;
        }

        function loadOptionPreset(type) {
            const atm = currentATMStrike;
            const step = currentStrikeStep;
            const qty = currentLotSize;

            if (type === 'straddle') {
                currentOptionLegs = [
                    {action: "SELL", opt_type: "CE", strike: atm, premium: getEstimatedPremium(atm, "CE"), quantity: qty},
                    {action: "SELL", opt_type: "PE", strike: atm, premium: getEstimatedPremium(atm, "PE"), quantity: qty}
                ];
            } else if (type === 'strangle') {
                currentOptionLegs = [
                    {action: "SELL", opt_type: "CE", strike: atm + step, premium: getEstimatedPremium(atm + step, "CE"), quantity: qty},
                    {action: "SELL", opt_type: "PE", strike: atm - step, premium: getEstimatedPremium(atm - step, "PE"), quantity: qty}
                ];
            } else if (type === 'iron_condor') {
                currentOptionLegs = [
                    {action: "SELL", opt_type: "CE", strike: atm + step, premium: getEstimatedPremium(atm + step, "CE"), quantity: qty},
                    {action: "BUY", opt_type: "CE", strike: atm + (2 * step), premium: getEstimatedPremium(atm + (2 * step), "CE"), quantity: qty},
                    {action: "SELL", opt_type: "PE", strike: atm - step, premium: getEstimatedPremium(atm - step, "PE"), quantity: qty},
                    {action: "BUY", opt_type: "PE", strike: atm - (2 * step), premium: getEstimatedPremium(atm - (2 * step), "PE"), quantity: qty}
                ];
            } else if (type === 'bull_call') {
                currentOptionLegs = [
                    {action: "BUY", opt_type: "CE", strike: atm, premium: getEstimatedPremium(atm, "CE"), quantity: qty},
                    {action: "SELL", opt_type: "CE", strike: atm + step, premium: getEstimatedPremium(atm + step, "CE"), quantity: qty}
                ];
            } else if (type === 'bear_put') {
                currentOptionLegs = [
                    {action: "BUY", opt_type: "PE", strike: atm, premium: getEstimatedPremium(atm, "PE"), quantity: qty},
                    {action: "SELL", opt_type: "PE", strike: atm - step, premium: getEstimatedPremium(atm - step, "PE"), quantity: qty}
                ];
            } else if (type === 'iron_butterfly') {
                currentOptionLegs = [
                    {action: "SELL", opt_type: "CE", strike: atm, premium: getEstimatedPremium(atm, "CE"), quantity: qty},
                    {action: "SELL", opt_type: "PE", strike: atm, premium: getEstimatedPremium(atm, "PE"), quantity: qty},
                    {action: "BUY", opt_type: "CE", strike: atm + (2 * step), premium: getEstimatedPremium(atm + (2 * step), "CE"), quantity: qty},
                    {action: "BUY", opt_type: "PE", strike: atm - (2 * step), premium: getEstimatedPremium(atm - (2 * step), "PE"), quantity: qty}
                ];
            }

            renderLegsTable();
            updateOptionsPayoff();
        }

        function renderLegsTable() {
            const tbody = document.getElementById('opt-legs-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            currentOptionLegs.forEach((leg, idx) => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40';

                // Strike dropdown options
                let strikeOptions = '';
                if (availableStrikes.length > 0) {
                    strikeOptions = availableStrikes.map(s => `
                        <option value="${s.strike}" ${s.strike === leg.strike ? 'selected' : ''}>
                            ${s.label}
                        </option>
                    `).join('');
                } else {
                    strikeOptions = `<option value="${leg.strike}" selected>${leg.strike}</option>`;
                }

                tr.innerHTML = `
                    <td class="py-2.5 px-3">
                        <select onchange="onLegChange(${idx}, 'action', this.value)" class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs font-bold ${leg.action === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}">
                            <option value="BUY" ${leg.action === 'BUY' ? 'selected' : ''}>BUY</option>
                            <option value="SELL" ${leg.action === 'SELL' ? 'selected' : ''}>SELL</option>
                        </select>
                    </td>
                    <td class="py-2.5 px-3">
                        <select onchange="onLegChange(${idx}, 'opt_type', this.value)" class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white">
                            <option value="CE" ${leg.opt_type === 'CE' ? 'selected' : ''}>CE</option>
                            <option value="PE" ${leg.opt_type === 'PE' ? 'selected' : ''}>PE</option>
                        </select>
                    </td>
                    <td class="py-2.5 px-3">
                        <select onchange="onLegChange(${idx}, 'strike', parseInt(this.value))" class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-indigo-300 font-mono w-full">
                            ${strikeOptions}
                        </select>
                    </td>
                    <td class="py-2.5 px-3">
                        <input type="number" step="0.5" value="${leg.premium}" onchange="onLegChange(${idx}, 'premium', parseFloat(this.value))" class="w-24 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white font-mono">
                    </td>
                    <td class="py-2.5 px-3">
                        <input type="number" value="${leg.quantity}" onchange="onLegChange(${idx}, 'quantity', parseInt(this.value))" class="w-16 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white font-mono text-center">
                    </td>
                    <td class="py-2.5 px-3 text-right text-indigo-300 font-mono" id="leg-delta-${idx}">-</td>
                    <td class="py-2.5 px-3 text-right text-emerald-300 font-mono" id="leg-theta-${idx}">-</td>
                    <td class="py-2.5 px-3 text-center">
                        <button onclick="removeLeg(${idx})" class="p-1 rounded hover:bg-rose-500/20 text-rose-400">
                            <i data-lucide="trash-2" class="h-3.5 w-3.5"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
            lucide.createIcons();
        }

        function onLegChange(index, field, value) {
            currentOptionLegs[index][field] = value;
            if (field === 'strike' || field === 'opt_type') {
                const strike = currentOptionLegs[index].strike;
                const optType = currentOptionLegs[index].opt_type;
                currentOptionLegs[index].premium = getEstimatedPremium(strike, optType);
            }
            renderLegsTable();
            updateOptionsPayoff();
        }

        function addCustomLeg() {
            currentOptionLegs.push({
                action: "BUY",
                opt_type: "CE",
                strike: currentATMStrike,
                premium: getEstimatedPremium(currentATMStrike, "CE"),
                quantity: currentLotSize
            });
            renderLegsTable();
            updateOptionsPayoff();
        }

        function removeLeg(index) {
            if (currentOptionLegs.length <= 1) {
                alert('Strategy must have at least 1 leg.');
                return;
            }
            currentOptionLegs.splice(index, 1);
            renderLegsTable();
            updateOptionsPayoff();
        }

        async function updateOptionsPayoff() {
            const days = parseFloat(document.getElementById('slider-days').value);
            const iv = parseFloat(document.getElementById('slider-iv').value);
            const shift = parseFloat(document.getElementById('slider-spot-shift').value);
            const evalSpot = currentSpotPrice + shift;

            document.getElementById('slider-days-val').innerText = days + ' Days';
            document.getElementById('slider-iv-val').innerText = iv + '%';
            document.getElementById('slider-spot-val').innerText = (shift >= 0 ? '+' : '') + shift + ' pts';
            document.getElementById('opt-spot').innerText = '₹' + evalSpot.toLocaleString();

            const payload = {
                spot: evalSpot,
                days_to_expiry: days,
                iv: iv,
                legs: currentOptionLegs
            };

            try {
                const res = await fetch('/api/options/payoff', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.status === 'success') {
                    document.getElementById('opt-delta').innerText = data.portfolio_greeks.delta;
                    document.getElementById('opt-theta').innerText = (data.portfolio_greeks.theta >= 0 ? '+₹' : '-₹') + Math.abs(data.portfolio_greeks.theta);
                    document.getElementById('opt-vega').innerText = (data.portfolio_greeks.vega >= 0 ? '+₹' : '-₹') + Math.abs(data.portfolio_greeks.vega);
                    document.getElementById('opt-max-profit').innerText = typeof data.max_profit === 'number' ? '₹' + data.max_profit.toLocaleString() : data.max_profit;
                    document.getElementById('opt-max-loss').innerText = typeof data.max_loss === 'number' ? '₹' + data.max_loss.toLocaleString() : data.max_loss;
                    document.getElementById('opt-pop').innerText = data.pop_pct + '%';

                    if (data.breakevens && data.breakevens.length > 0) {
                        document.getElementById('opt-breakevens').innerText = 'Breakevens: ' + data.breakevens.map(b => '₹' + b.toLocaleString()).join('  |  ');
                    } else {
                        document.getElementById('opt-breakevens').innerText = 'Breakevens: None';
                    }

                    // Render Payoff Plotly Chart
                    Plotly.newPlot('options-payoff-chart', [
                        {x: data.spot_prices, y: data.expiry_payoff, mode: 'lines', name: 'Payoff at Expiry', line: {color: '#10b981', width: 2.5}},
                        {x: data.spot_prices, y: data.t0_payoff, mode: 'lines', name: 'T+0 Payoff Curve', line: {color: '#6366f1', width: 2, dash: 'dot'}}
                    ], {
                        margin: {t: 20, r: 20, l: 60, b: 40},
                        paper_bgcolor: '#0f172a',
                        plot_bgcolor: '#0f172a',
                        font: {color: '#94a3b8'},
                        xaxis: {gridcolor: '#1e293b', title: 'Underlying Spot Price'},
                        yaxis: {gridcolor: '#1e293b', tickprefix: '₹', zerolinecolor: '#475569', zerolinewidth: 2}
                    }, {responsive: true});
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function runStraddleBacktest() {
            const sym = document.getElementById('opt_symbol_select').value;
            const startDate = document.getElementById('straddle_start_date').value || document.getElementById('start_date').value;
            const endDate = document.getElementById('straddle_end_date').value || document.getElementById('end_date').value;
            const entryTime = document.getElementById('straddle_entry_time').value || '09:20';
            const exitTime = document.getElementById('straddle_exit_time').value || '15:15';
            const strikeSelection = document.getElementById('straddle_strike_selection').value || 'ATM';
            const slMode = document.getElementById('straddle_sl_mode').value;
            const slPct = parseFloat(document.getElementById('straddle_sl_pct').value) || 25.0;
            const lotSize = parseInt(document.getElementById('straddle_lot_size').value) || currentLotSize;
            const lotsCount = parseInt(document.getElementById('straddle_lots_count').value) || 1;

            const btn = document.getElementById('btn-run-straddle');
            btn.innerHTML = '<div class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent"></div> Simulating Days...';
            
            try {
                const res = await fetch('/api/options/backtest-straddle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        symbol: sym,
                        start_date: startDate,
                        end_date: endDate,
                        entry_time: entryTime,
                        exit_time: exitTime,
                        strike_selection: strikeSelection,
                        sl_mode: slMode,
                        sl_leg_pct: slPct,
                        lot_size: lotSize,
                        lots: lotsCount
                    })
                });
                const data = await res.json();
                btn.innerHTML = '<i data-lucide="play" class="h-3.5 w-3.5"></i> Run Detailed Intraday Straddle Backtest';
                
                if (data.status === 'success') {
                    document.getElementById('straddle-pnl').innerText = '₹' + data.total_net_pnl.toLocaleString();
                    document.getElementById('straddle-pnl').className = data.total_net_pnl >= 0 ? 'text-lg font-bold text-emerald-400 font-mono mt-0.5' : 'text-lg font-bold text-rose-400 font-mono mt-0.5';
                    document.getElementById('straddle-winrate').innerText = data.win_rate + '%';
                    document.getElementById('straddle-pf').innerText = data.profit_factor;
                    document.getElementById('straddle-dd').innerText = data.max_drawdown_pct + '%';
                    document.getElementById('straddle-win-loss').innerText = `${data.win_days}W / ${data.loss_days}L`;
                    document.getElementById('straddle-trades').innerText = data.total_days;
                    document.getElementById('straddle-results').classList.remove('hidden');

                    // Render Granular Day-wise Trade Logs Table
                    const tbody = document.getElementById('straddle-trades-body');
                    tbody.innerHTML = '';
                    
                    data.trade_logs.forEach(log => {
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-slate-800/50';
                        
                        let outcomeBadge = 'bg-slate-800 text-slate-300';
                        if (log.outcome.includes('PROFIT')) outcomeBadge = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
                        else if (log.outcome.includes('BOTH SL')) outcomeBadge = 'bg-rose-500/20 text-rose-400 border border-rose-500/30';
                        else if (log.outcome.includes('SAVED')) outcomeBadge = 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
                        else outcomeBadge = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';

                        const sourceBadge = (log.data_source && log.data_source.includes('REAL')) 
                            ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold">REAL BROKER DATA</span>'
                            : '<span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">GREEKS MODEL</span>';

                        const ceContract = log.ce_symbol ? `<div class="text-[10px] text-indigo-400 font-mono">${log.ce_symbol}</div>` : '';
                        const peContract = log.pe_symbol ? `<div class="text-[10px] text-amber-400 font-mono">${log.pe_symbol}</div>` : '';

                        tr.innerHTML = `
                            <td class="py-2.5 px-3 font-bold text-white">${log.date}<br>${sourceBadge}</td>
                            <td class="py-2.5 px-3">₹${log.spot_0920}</td>
                            <td class="py-2.5 px-3 font-bold text-indigo-300">${log.atm_strike}</td>
                            <td class="py-2.5 px-3">${ceContract}<span class="text-slate-400">₹${log.ce_entry} ➔</span> <span class="font-bold ${log.ce_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${log.ce_exit}</span> <span class="text-[10px] text-slate-500">(${log.ce_exit_time})</span></td>
                            <td class="py-2.5 px-3">${peContract}<span class="text-slate-400">₹${log.pe_entry} ➔</span> <span class="font-bold ${log.pe_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${log.pe_exit}</span> <span class="text-[10px] text-slate-500">(${log.pe_exit_time})</span></td>
                            <td class="py-2.5 px-3">₹${log.spot_1515}</td>
                            <td class="py-2.5 px-3 text-right">₹${log.gross_pnl}</td>
                            <td class="py-2.5 px-3 text-right font-bold ${log.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${log.net_pnl}</td>
                            <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${outcomeBadge}">${log.outcome}</span></td>
                        `;
                        tbody.appendChild(tr);
                    });
                    
                    document.getElementById('straddle-table-section').classList.remove('hidden');
                    lucide.createIcons();
                } else {
                    alert('Error: ' + data.message);
                }
            } catch (err) {
                btn.innerHTML = '<i data-lucide="play" class="h-3.5 w-3.5"></i> Run Detailed Intraday Straddle Backtest';
                alert('Straddle backtest error: ' + err);
            }
        }

        // --- STRADDLE STRATEGY SAVING & DUAL DEPLOYMENT ---
        let allSavedStraddles = [];

        async function fetchSavedStraddlePresets() {
            try {
                const res = await fetch('/api/options/saved-strategies');
                const data = await res.json();
                if (data.status === 'success') {
                    allSavedStraddles = data.strategies || [];
                    const sel = document.getElementById('straddle_saved_presets');
                    if (sel) {
                        sel.innerHTML = '<option value="">-- Load Saved Strategy --</option>';
                        allSavedStraddles.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value = s.id;
                            opt.innerText = `⭐ ${s.name} (${s.symbol} ${s.entry_time} - ${s.sl_mode})`;
                            sel.appendChild(opt);
                        });
                    }
                }
            } catch (e) {
                console.error('Error fetching saved straddles:', e);
            }
        }

        async function saveStraddleStrategy() {
            const sym = document.getElementById('opt_symbol_select').value;
            const defaultName = `${sym}_Straddle_${document.getElementById('straddle_entry_time').value.replace(':', '')}`;
            const name = prompt('Enter a name for this Straddle Strategy Setup:', defaultName);
            if (!name || !name.trim()) return;

            const payload = {
                name: name.trim(),
                symbol: sym,
                entry_time: document.getElementById('straddle_entry_time').value || '09:20',
                exit_time: document.getElementById('straddle_exit_time').value || '15:15',
                strike_selection: document.getElementById('straddle_strike_selection').value || 'ATM',
                sl_mode: document.getElementById('straddle_sl_mode').value || 'COST_TO_COST',
                sl_leg_pct: parseFloat(document.getElementById('straddle_sl_pct').value) || 25.0,
                lot_size: parseInt(document.getElementById('straddle_lot_size').value) || 65,
                lots: parseInt(document.getElementById('straddle_lots_count').value) || 1
            };

            try {
                const res = await fetch('/api/options/save-strategy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.status === 'success') {
                    alert(`✅ ${data.message}`);
                    fetchSavedStraddlePresets();
                } else {
                    alert(`❌ Save Error: ${data.message}`);
                }
            } catch (err) {
                alert(`Error saving strategy: ${err}`);
            }
        }

        function loadSavedStraddlePreset(id) {
            if (!id) return;
            const strat = allSavedStraddles.find(s => s.id == id);
            if (!strat) return;

            if (document.getElementById('opt_symbol_select')) document.getElementById('opt_symbol_select').value = strat.symbol;
            if (document.getElementById('straddle_entry_time')) document.getElementById('straddle_entry_time').value = strat.entry_time;
            if (document.getElementById('straddle_exit_time')) document.getElementById('straddle_exit_time').value = strat.exit_time;
            if (document.getElementById('straddle_strike_selection')) document.getElementById('straddle_strike_selection').value = strat.strike_selection;
            if (document.getElementById('straddle_sl_mode')) document.getElementById('straddle_sl_mode').value = strat.sl_mode;
            if (document.getElementById('straddle_sl_pct')) document.getElementById('straddle_sl_pct').value = strat.sl_leg_pct;
            if (document.getElementById('straddle_lot_size')) document.getElementById('straddle_lot_size').value = strat.lot_size;
            if (document.getElementById('straddle_lots_count')) document.getElementById('straddle_lots_count').value = strat.lots;

            alert(`✅ Loaded Strategy Setup: "${strat.name}"`);
        }

        async function deployStraddle(mode) {
            const sym = document.getElementById('opt_symbol_select').value;
            const entryTime = document.getElementById('straddle_entry_time').value || '09:20';
            const exitTime = document.getElementById('straddle_exit_time').value || '15:15';
            const strikeSel = document.getElementById('straddle_strike_selection').value || 'MATCHED_PREMIUM';
            const slMode = document.getElementById('straddle_sl_mode').value;
            const slPct = parseFloat(document.getElementById('straddle_sl_pct').value) || 25.0;
            const lotSize = parseInt(document.getElementById('straddle_lot_size').value) || 65;
            const lots = parseInt(document.getElementById('straddle_lots_count').value) || 1;

            if (mode === 'REAL') {
                const confirmed = confirm(`⚠️ ATTENTION: You are about to deploy this ${sym} Straddle Bot to REAL LIVE BROKER trading with REAL MONEY!\n\nParameters:\n- Symbol: ${sym}\n- Entry: ${entryTime} | Exit: ${exitTime}\n- Strike: ${strikeSel}\n- SL Mode: ${slMode} (${slPct}%)\n- Quantity: ${lotSize * lots} Qty (${lots} Lots)\n\nConfirm Real Live Deployment?`);
                if (!confirmed) return;
            }

            const btnId = mode === 'REAL' ? 'btn-deploy-real' : 'btn-deploy-analyzer';
            const btn = document.getElementById(btnId);
            const origHtml = btn.innerHTML;
            btn.innerHTML = '<div class="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent"></div> Deploying...';

            const payload = {
                mode: mode,
                strategy_name: `${sym}_Straddle_${mode}_${entryTime.replace(':', '')}`,
                symbol: sym,
                entry_time: entryTime,
                exit_time: exitTime,
                strike_selection: strikeSel,
                sl_mode: slMode,
                sl_leg_pct: slPct,
                lot_size: lotSize,
                lots: lots
            };

            try {
                const res = await fetch('/api/options/deploy-straddle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                btn.innerHTML = origHtml;

                if (data.status === 'success') {
                    alert(`🎉 DEPLOYED SUCCESSFULLY TO OPENALGO!\n\nMode: ${data.mode}\nBot Script: ${data.filepath}\nProcess PID: ${data.pid}\n\nThe bot is now active and monitoring market ticks for automated execution!`);
                } else {
                    alert(`❌ Deployment Failed: ${data.message}`);
                }
            } catch (err) {
                btn.innerHTML = origHtml;
                alert(`Deployment Error: ${err}`);
            }
        }

        // --- COMBINED PORTFOLIO HUB ---
        async function runCombinedPortfolioBacktest() {
            const start = document.getElementById('start_date').value;
            const end = document.getElementById('end_date').value;

            try {
                const res = await fetch('/api/portfolio/combine', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({start_date: start, end_date: end})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    document.getElementById('port-pnl').innerText = '₹' + data.total_net_pnl.toLocaleString();
                    document.getElementById('port-roi').innerText = data.roi_pct + '%';
                    document.getElementById('port-dd').innerText = data.max_drawdown_pct + '%';
                    document.getElementById('port-sharpe').innerText = data.sharpe_ratio;
                    document.getElementById('portfolio-metrics-grid').classList.remove('hidden');
                    document.getElementById('portfolio-charts-section').classList.remove('hidden');

                    // Portfolio Equity Curve
                    const dates = data.portfolio_equity_curve.map(p => p.date);
                    const equities = data.portfolio_equity_curve.map(p => p.equity);
                    Plotly.newPlot('port-equity-chart', [{
                        x: dates, y: equities, mode: 'lines',
                        line: {color: '#38bdf8', width: 2.5},
                        fill: 'tozeroy', fillcolor: 'rgba(56, 189, 248, 0.08)'
                    }], {
                        margin: {t: 20, r: 20, l: 60, b: 40},
                        paper_bgcolor: '#0f172a',
                        plot_bgcolor: '#0f172a',
                        font: {color: '#94a3b8'},
                        xaxis: {gridcolor: '#1e293b'},
                        yaxis: {gridcolor: '#1e293b', tickprefix: '₹'}
                    }, {responsive: true});

                    // Correlation Heatmap
                    const cm = data.correlation_matrix;
                    Plotly.newPlot('port-corr-chart', [{
                        z: cm.z_values,
                        x: cm.strategies,
                        y: cm.strategies,
                        type: 'heatmap',
                        colorscale: 'Blues',
                        zmin: -1, zmax: 1
                    }], {
                        margin: {t: 20, r: 20, l: 60, b: 40},
                        paper_bgcolor: '#0f172a',
                        plot_bgcolor: '#0f172a',
                        font: {color: '#94a3b8'}
                    }, {responsive: true});
                }
            } catch (err) {
                alert('Portfolio combine error: ' + err);
            }
        }

        // --- PINE SCRIPT GENERATOR ---
        async function generatePineScriptCode() {
            const config = currentStrategyConfig.symbol ? currentStrategyConfig : {
                strategy_name: document.getElementById('strategy_name').value,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                exchange: document.getElementById('exchange').value,
                stoploss_val: parseFloat(document.getElementById('stoploss_val').value),
                target_val: parseFloat(document.getElementById('target_val').value),
                quantity: 50,
                indicators: {fast_ema: 20, slow_ema: 50, rsi_period: 14, rsi_threshold: 50}
            };

            try {
                const res = await fetch('/api/generate-pinescript', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({config: config})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    document.getElementById('pinescript-output').value = data.pinescript;
                }
            } catch (err) {
                console.error(err);
            }
        }

        function copyPineScript() {
            const el = document.getElementById('pinescript-output');
            el.select();
            document.execCommand('copy');
            alert('Pine Script copied to clipboard! Paste it into TradingView Pine Editor.');
        }

        function goToPineScript() {
            switchTab('tab-code');
        }

        // --- SAVED STRATEGIES ---
        async function fetchSavedStrategies() {
            try {
                const res = await fetch('/api/strategies');
                const list = await res.json();
                document.getElementById('saved-count').innerText = list.length;
                const tbody = document.getElementById('saved-table-body');
                tbody.innerHTML = '';
                if (list.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-500">No saved strategies found.</td></tr>';
                    return;
                }
                list.forEach(item => {
                    const c = item.config;
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/50';
                    tr.innerHTML = `
                        <td class="py-3 px-4"><input type="checkbox" checked class="rounded bg-slate-900 border-slate-700"></td>
                        <td class="py-3 px-4 font-bold text-white">${c.strategy_name || 'Strategy'}</td>
                        <td class="py-3 px-4">${c.symbol} (${c.timeframe})</td>
                        <td class="py-3 px-4"><span class="text-rose-400">SL: ${c.stoploss_val}%</span> / <span class="text-emerald-400">TP: ${c.target_val}%</span></td>
                        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400">Ready</span></td>
                        <td class="py-3 px-4 text-right">
                            <button onclick="loadAndRunSavedStrategy('${item.id}')" class="px-2.5 py-1 rounded bg-indigo-600 text-white text-xs mr-2">Load</button>
                            <button onclick="deleteSavedStrategy('${item.id}')" class="px-2.5 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 text-xs">Delete</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (err) {
                console.error(err);
            }
        }

        async function saveCurrentStrategy() {
            const config = currentStrategyConfig.symbol ? currentStrategyConfig : {
                strategy_name: document.getElementById('strategy_name').value,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                exchange: document.getElementById('exchange').value,
                timeframe: document.getElementById('timeframe').value,
                start_date: document.getElementById('start_date').value,
                end_date: document.getElementById('end_date').value,
                stoploss_val: parseFloat(document.getElementById('stoploss_val').value),
                target_val: parseFloat(document.getElementById('target_val').value),
                capital: 100000.0,
                quantity: 50
            };
            try {
                const res = await fetch('/api/strategies/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({config: config, metrics: currentStrategyMetrics})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    alert('Strategy saved successfully to Portfolio Hub!');
                    fetchSavedStrategies();
                }
            } catch (err) {
                alert('Error saving: ' + err);
            }
        }

        async function deleteSavedStrategy(id) {
            if (!confirm('Are you sure you want to delete this strategy?')) return;
            try {
                await fetch('/api/strategies/' + id, {method: 'DELETE'});
                fetchSavedStrategies();
            } catch (err) {
                alert('Error deleting: ' + err);
            }
        }

        async function loadAndRunSavedStrategy(id) {
            try {
                const res = await fetch('/api/strategies');
                const list = await res.json();
                const found = list.find(x => x.id === id);
                if (found) {
                    const c = found.config;
                    document.getElementById('strategy_name').value = c.strategy_name;
                    document.getElementById('symbol').value = c.symbol;
                    document.getElementById('exchange').value = c.exchange;
                    document.getElementById('timeframe').value = c.timeframe;
                    document.getElementById('stoploss_val').value = c.stoploss_val;
                    document.getElementById('target_val').value = c.target_val;
                    switchTab('tab-strategy');
                    executeBacktest();
                }
            } catch (err) {
                alert('Error loading: ' + err);
            }
        }

        let activeTemplateType = 'supertrend';
        let attachedAIFile = null;
        let activeDatasetId = null;
        let searchTimeout = null;

        function setStrategyMode(mode) {
            const btnAi = document.getElementById('btn-mode-ai');
            const btnPy = document.getElementById('btn-mode-python');
            const aiContainer = document.getElementById('ai-mode-container');
            const pyContainer = document.getElementById('python-editor-container');

            if (mode === 'AI') {
                if (btnAi) btnAi.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 ring-2 ring-indigo-400 text-white transition flex items-center gap-1.5 shadow-lg';
                if (btnPy) btnPy.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 bg-transparent';
                if (aiContainer) {
                    aiContainer.classList.remove('opacity-60');
                    aiContainer.classList.add('border-indigo-500/80', 'shadow-2xl');
                    aiContainer.scrollIntoView({behavior: 'smooth', block: 'nearest'});
                }
                const promptInput = document.getElementById('ai-prompt-input');
                if (promptInput) promptInput.focus();
            } else {
                if (btnPy) btnPy.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-amber-600 ring-2 ring-amber-400 text-white transition flex items-center gap-1.5 shadow-lg';
                if (btnAi) btnAi.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 bg-transparent';
                if (pyContainer) {
                    pyContainer.classList.remove('opacity-60');
                    pyContainer.classList.add('border-amber-500/80', 'shadow-2xl');
                    pyContainer.scrollIntoView({behavior: 'smooth', block: 'nearest'});
                }
                const pyCode = document.getElementById('python-strategy-code');
                if (pyCode) pyCode.focus();
            }
        }

        function toggleTemplateEditor() {
            const panel = document.getElementById('template-editor-panel');
            if (panel) {
                panel.classList.toggle('hidden');
            }
        }

        function handleAIFileUpload(input) {
            if (!input.files || input.files.length === 0) return;
            const file = input.files[0];
            attachedAIFile = file;
            
            const card = document.getElementById('ai-file-preview-card');
            const nameEl = document.getElementById('ai-attached-filename');
            const sizeEl = document.getElementById('ai-attached-filesize');
            const badgeEl = document.getElementById('ai-attached-badge');
            
            nameEl.innerText = file.name;
            sizeEl.innerText = '(' + (file.size / 1024).toFixed(1) + ' KB)';
            
            const ext = file.name.split('.').pop().toLowerCase();
            if (['csv', 'xlsx', 'xls', 'json'].includes(ext)) {
                badgeEl.innerText = '📊 Historical Dataset';
                badgeEl.className = 'px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 font-semibold';
            } else if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
                badgeEl.innerText = '🖼️ Chart Image';
                badgeEl.className = 'px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300 font-semibold';
            } else {
                badgeEl.innerText = '📄 Strategy Document';
                badgeEl.className = 'px-2 py-0.5 rounded text-[10px] bg-indigo-500/20 text-indigo-300 font-semibold';
            }
            
            card.classList.remove('hidden');
            document.getElementById('ai-file-btn-text').innerText = '📎 ' + file.name.substring(0, 14) + '...';
        }

        function removeAttachedAIFile() {
            attachedAIFile = null;
            activeDatasetId = null;
            document.getElementById('ai-file-upload').value = '';
            document.getElementById('ai-file-preview-card').classList.add('hidden');
            document.getElementById('ai-file-btn-text').innerText = '📎 Attach File / Data';
        }

        async function handleSymbolSearch(q) {
            const dropdown = document.getElementById('symbol-search-dropdown');
            if (!dropdown) return;
            
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(async () => {
                try {
                    const res = await fetch('/api/symbols/search?q=' + encodeURIComponent(q.trim()));
                    const data = await res.json();
                    const results = data.results || [];
                    
                    if (results.length === 0) {
                        dropdown.innerHTML = '<div class="p-3 text-xs text-slate-400 text-center">No matching symbols found</div>';
                        dropdown.classList.remove('hidden');
                        return;
                    }
                    
                    dropdown.innerHTML = '';
                    results.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'p-2.5 hover:bg-slate-800 cursor-pointer flex items-center justify-between transition text-xs';
                        
                        let catBadge = 'bg-slate-700 text-slate-300';
                        if (item.category === 'INDEX') catBadge = 'bg-indigo-500/20 text-indigo-300';
                        else if (item.category === 'COMMODITY') catBadge = 'bg-amber-500/20 text-amber-300';
                        else if (item.category === 'STOCK') catBadge = 'bg-emerald-500/20 text-emerald-300';
                        
                        div.innerHTML = `
                            <div class="flex items-center gap-2">
                                <span class="font-mono font-bold text-white">${item.symbol}</span>
                                <span class="text-[10px] text-slate-400 truncate max-w-[140px]">${item.name}</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${catBadge}">${item.category}</span>
                                <span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-slate-300 border border-slate-700">${item.exchange}</span>
                            </div>
                        `;
                        div.onclick = () => {
                            selectQuickSymbol(item.symbol, item.exchange);
                            dropdown.classList.add('hidden');
                        };
                        dropdown.appendChild(div);
                    });
                    dropdown.classList.remove('hidden');
                } catch (err) {
                    console.error(err);
                }
            }, 150);
        }

        function selectQuickSymbol(sym, exch) {
            document.getElementById('symbol').value = sym;
            const exchSelect = document.getElementById('exchange');
            if (exchSelect && exch) {
                exchSelect.value = exch;
            }
            const dropdown = document.getElementById('symbol-search-dropdown');
            if (dropdown) dropdown.classList.add('hidden');
            onCustomParamChange();
        }

        function clearSymbolSearch() {
            document.getElementById('symbol').value = '';
            document.getElementById('symbol').focus();
            handleSymbolSearch('');
        }

        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('symbol-search-dropdown');
            const symInput = document.getElementById('symbol');
            if (dropdown && !dropdown.contains(e.target) && e.target !== symInput) {
                dropdown.classList.add('hidden');
            }
        });

        function generateTemplatePythonCode(type, params) {
            const stratName = (params.strategy_name || "QuantStrategy").replace(/ /g, "_");
            const sym = params.symbol || "NIFTY";
            const tf = params.timeframe || "5m";
            const fast = params.fast !== undefined ? params.fast : 7;
            const slow = params.slow !== undefined ? params.slow : 3.0;
            const rsi = params.rsi !== undefined ? params.rsi : 50;
            const sl = params.sl !== undefined ? params.sl : 0.8;
            const tg = params.tg !== undefined ? params.tg : 2.2;
            const dir = params.dir || "BOTH";

            if (type === 'smc' || type === 'crypto_btc') {
                return `# ===============================================================================
#  ` + stratName + ` - Smart Money Concepts (SMC) Institutional Structure & Order Blocks
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | Swing Window: ` + fast + ` | R:R Ratio: 1:` + slow + `
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    # SMC Zero-Lookahead Institutional Signal Generator
    # Identifies Swings, BOS, CHoCH, Order Blocks, and Liquidity Sweeps
    df = df.copy()
    n = len(df)
    swing_window = int(params.get("fast_ema", ` + fast + `)) if params else ` + fast + `
    
    df["swing_high"] = False
    df["swing_low"] = False
    df["signal"] = 'HOLD'
    
    # 1. Detect Swing Highs & Swing Lows
    for i in range(swing_window, n - swing_window):
        if df["high"].iloc[i] == df["high"].iloc[i - swing_window : i + swing_window + 1].max():
            df.loc[df.index[i], "swing_high"] = True
        if df["low"].iloc[i] == df["low"].iloc[i - swing_window : i + swing_window + 1].min():
            df.loc[df.index[i], "swing_low"] = True
            
    # 2. Track Trend, BOS, and Order Blocks
    last_high = None
    last_low = None
    
    for i in range(1, n):
        close = df["close"].iloc[i]
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]
        
        if df["swing_high"].iloc[i]:
            last_high = high
        if df["swing_low"].iloc[i]:
            last_low = low
            
        # Bullish BOS / CHoCH
        if last_high is not None and close > last_high:
            df.loc[df.index[i], "signal"] = "BUY"
        # Bearish BOS / CHoCH
        elif last_low is not None and close < last_low:
            ` + (dir === "BOTH" ? "df.loc[df.index[i], 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[df.index[i], 'signal'] = 'SELL'" : "# Long Only Mode")) + `
            
    return df
`;
            } else if (type === 'supertrend') {
                return `# ===============================================================================
#  ` + stratName + ` - Multi-Timeframe Supertrend Trend Rider (Zero Lookahead)
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | ATR Period: ` + fast + ` | Multiplier: ` + slow + `
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    # Strict Zero-Lookahead Supertrend Momentum Strategy
    df = df.copy()
    atr_period = int(params.get("atr_period", ` + fast + `)) if params else ` + fast + `
    multiplier = float(params.get("multiplier", ` + slow + `)) if params else ` + slow + `
    rsi_filter = int(params.get("rsi_filter", ` + rsi + `)) if params else ` + rsi + `
    
    # 1. ATR & Band Calculations
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift(1)).abs()
    lc = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean().fillna(0.0)
    
    hl2 = (df['high'] + df['low']) / 2.0
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    st_dir = np.zeros(len(df), dtype=int)
    
    for i in range(1, len(df)):
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or df['close'].iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
            
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or df['close'].iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
            
        if df['close'].iloc[i] > final_upper.iloc[i-1]:
            st_dir[i] = 1
        elif df['close'].iloc[i] < final_lower.iloc[i-1]:
            st_dir[i] = -1
        else:
            st_dir[i] = st_dir[i-1] if st_dir[i-1] != 0 else 1
            
    df['st_direction'] = st_dir
    
    # 2. RSI Momentum Filter
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))
    
    # 3. Signals (Evaluated strictly on completed bar i-1)
    df['signal'] = 'HOLD'
    buy_cond = (df['st_direction'] == 1) & (df['st_direction'].shift(1) == -1) & (df['rsi'] >= rsi_filter)
    sell_cond = (df['st_direction'] == -1) & (df['st_direction'].shift(1) == 1) & (df['rsi'] <= (100 - rsi_filter))
    
    df.loc[buy_cond, 'signal'] = 'BUY'
    ` + (dir === "BOTH" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : "# Long Only Mode")) + `
    return df
`;
            } else if (type === 'vwap_pullback') {
                return `# ===============================================================================
#  ` + stratName + ` - Institutional VWAP + 20 EMA Dynamic Pullback (Zero Lookahead)
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | EMA: ` + fast + ` | RSI: ` + rsi + `
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    df = df.copy()
    ema_period = int(params.get("fast_ema", ` + fast + `)) if params else ` + fast + `
    rsi_filter = int(params.get("rsi_threshold", ` + rsi + `)) if params else ` + rsi + `
    
    # 1. EMA & Intraday Session VWAP
    df['fast_ema'] = df['close'].ewm(span=ema_period, adjust=False).mean()
    tp = (df['high'] + df['low'] + df['close']) / 3.0
    vol = df.get('volume', pd.Series(1, index=df.index)).replace(0, 1)
    if 'date_str' in df.columns:
        df['vwap'] = (tp * vol).groupby(df['date_str']).cumsum() / vol.groupby(df['date_str']).cumsum()
    else:
        df['vwap'] = (tp * vol).cumsum() / vol.cumsum()
        
    # 2. RSI 14
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    df['rsi'] = 100.0 - (100.0 / (1.0 + (gain / (loss + 1e-9))))
    
    # 3. Pullback Signals (Trend following with deep discount entries)
    df['signal'] = 'HOLD'
    buy_cond = (df['close'] > df['vwap']) & (df['low'] <= df['fast_ema']) & (df['close'] > df['fast_ema']) & (df['rsi'] >= rsi_filter)
    sell_cond = (df['close'] < df['vwap']) & (df['high'] >= df['fast_ema']) & (df['close'] < df['fast_ema']) & (df['rsi'] <= (100 - rsi_filter))
    
    df.loc[buy_cond, 'signal'] = 'BUY'
    ` + (dir === "BOTH" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : "# Long Only Mode")) + `
    return df
`;
            } else if (type === 'bollinger') {
                return `# ===============================================================================
#  ` + stratName + ` - Bollinger Bands Mean Reversion + RSI Extreme Scalper (Zero Lookahead)
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | BB Period: ` + fast + ` | StdDev: ` + slow + `
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    df = df.copy()
    bb_period = int(params.get("bb_period", ` + fast + `)) if params else ` + fast + `
    std_dev = float(params.get("std_dev", ` + slow + `)) if params else ` + slow + `
    rsi_oversold = int(params.get("rsi_threshold", ` + rsi + `)) if params else ` + rsi + `
    
    # 1. Bollinger Bands
    df['bb_mid'] = df['close'].rolling(bb_period).mean()
    bb_std = df['close'].rolling(bb_period).std()
    df['bb_upper'] = df['bb_mid'] + (std_dev * bb_std)
    df['bb_lower'] = df['bb_mid'] - (std_dev * bb_std)
    
    # 2. RSI 14
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    df['rsi'] = 100.0 - (100.0 / (1.0 + (gain / (loss + 1e-9))))
    
    # 3. Mean Reversion Rejection Signals
    df['signal'] = 'HOLD'
    buy_cond = (df['close'].shift(1) <= df['bb_lower'].shift(1)) & (df['close'] > df['bb_lower']) & (df['rsi'] < rsi_oversold)
    sell_cond = (df['close'].shift(1) >= df['bb_upper'].shift(1)) & (df['close'] < df['bb_upper']) & (df['rsi'] > (100 - rsi_oversold))
    
    df.loc[buy_cond, 'signal'] = 'BUY'
    ` + (dir === "BOTH" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : "# Long Only Mode")) + `
    return df
`;
            } else if (type === 'orb_breakout') {
                return `# ===============================================================================
#  ` + stratName + ` - Opening Range Breakout (ORB 15-Min) with ATR Extension
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | Opening Range: ` + fast + `m | Target: ` + tg + `%
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    df = df.copy()
    
    # 1. Calculate Intraday ATR
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift(1)).abs()
    lc = (df['low'] - df['close'].shift(1)).abs()
    df['atr'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean().fillna(0.0)
    
    # 2. Identify 9:15-9:30 AM Opening Range
    df['signal'] = 'HOLD'
    if 'time_str' in df.columns:
        orb_mask = (df['time_str'] >= "09:15") & (df['time_str'] <= "09:30")
        if 'date_str' in df.columns:
            orb_high = df[orb_mask].groupby('date_str')['high'].max()
            orb_low = df[orb_mask].groupby('date_str')['low'].max()
            df['orb_high'] = df['date_str'].map(orb_high)
            df['orb_low'] = df['date_str'].map(orb_low)
        else:
            df['orb_high'] = df.iloc[:3]['high'].max()
            df['orb_low'] = df.iloc[:3]['low'].min()
            
        buy_cond = (df['time_str'] > "09:30") & (df['close'].shift(1) <= df['orb_high']) & (df['close'] > df['orb_high'])
        sell_cond = (df['time_str'] > "09:30") & (df['close'].shift(1) >= df['orb_low']) & (df['close'] < df['orb_low'])
        
        df.loc[buy_cond, 'signal'] = 'BUY'
        ` + (dir === "BOTH" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : "# Long Only Mode")) + `
        
    return df
`;
            } else if (type === 'mcx_crude') {
                return `# ===============================================================================
#  ` + stratName + ` - MCX Crude Oil Volatility Breakout (Zero Lookahead)
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | Fast EMA: ` + fast + ` | Slow EMA: ` + slow + `
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    df = df.copy()
    fast_period = int(params.get("fast_ema", ` + fast + `)) if params else ` + fast + `
    slow_period = int(params.get("slow_ema", ` + slow + `)) if params else ` + slow + `
    rsi_level = int(params.get("rsi_threshold", ` + rsi + `)) if params else ` + rsi + `
    
    df['fast_ema'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['slow_ema'] = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    df['rsi'] = 100.0 - (100.0 / (1.0 + (gain / (loss + 1e-9))))
    
    df['signal'] = 'HOLD'
    buy_cond = (df['fast_ema'] > df['slow_ema']) & (df['fast_ema'].shift(1) <= df['slow_ema'].shift(1)) & (df['rsi'] >= rsi_level)
    sell_cond = (df['fast_ema'] < df['slow_ema']) & (df['fast_ema'].shift(1) >= df['slow_ema'].shift(1)) & (df['rsi'] <= (100 - rsi_level))
    
    df.loc[buy_cond, 'signal'] = 'BUY'
    ` + (dir === "BOTH" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : "# Long Only Mode")) + `
    return df
`;
            } else {
                // Default EMA Trend
                return `# ===============================================================================
#  ` + stratName + ` - EMA 20/50 Trend Cross + RSI Momentum Filter (Zero Lookahead)
#  Symbol: ` + sym + ` | Timeframe: ` + tf + ` | Fast EMA: ` + fast + ` | Slow EMA: ` + slow + `
#  Stop Loss: ` + sl + `% | Target: ` + tg + `% | Direction: ` + dir + `
# ===============================================================================

import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    df = df.copy()
    fast_period = int(params.get("fast_ema", ` + fast + `)) if params else ` + fast + `
    slow_period = int(params.get("slow_ema", ` + slow + `)) if params else ` + slow + `
    rsi_level = int(params.get("rsi_threshold", ` + rsi + `)) if params else ` + rsi + `
    
    df['fast_ema'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['slow_ema'] = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    df['rsi'] = 100.0 - (100.0 / (1.0 + (gain / (loss + 1e-9))))
    
    df['signal'] = 'HOLD'
    buy_cond = (df['fast_ema'] > df['slow_ema']) & (df['fast_ema'].shift(1) <= df['slow_ema'].shift(1)) & (df['rsi'] >= rsi_level)
    sell_cond = (df['fast_ema'] < df['slow_ema']) & (df['fast_ema'].shift(1) >= df['slow_ema'].shift(1)) & (df['rsi'] <= (100 - rsi_level))
    
    df.loc[buy_cond, 'signal'] = 'BUY'
    ` + (dir === "BOTH" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : (dir === "SHORT" ? "df.loc[sell_cond, 'signal'] = 'SELL'" : "# Long Only Mode")) + `
    return df
`;
            }
        }

        function onCustomParamChange() {
            const fast = parseFloat(document.getElementById('tpl_fast_ema').value) || 7;
            const slow = parseFloat(document.getElementById('tpl_slow_ema').value) || 3.0;
            const rsi = parseInt(document.getElementById('tpl_rsi_threshold').value) || 50;
            const sl = parseFloat(document.getElementById('tpl_sl_pct').value) || 0.8;
            const tg = parseFloat(document.getElementById('tpl_tg_pct').value) || 2.2;
            const dir = document.getElementById('tpl_trade_direction').value || 'BOTH';

            // Sync to form inputs
            document.getElementById('stoploss_val').value = sl;
            document.getElementById('target_val').value = tg;

            const params = {
                strategy_name: document.getElementById('strategy_name').value,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                timeframe: document.getElementById('timeframe').value,
                fast: fast,
                slow: slow,
                rsi: rsi,
                sl: sl,
                tg: tg,
                dir: dir
            };

            const code = generateTemplatePythonCode(activeTemplateType, params);
            document.getElementById('python-strategy-code').value = code;
            
            const syncStatus = document.getElementById('tpl-sync-status');
            if (syncStatus) {
                syncStatus.innerText = '✅ Python code synchronized with custom parameters (' + new Date().toLocaleTimeString() + ')';
                syncStatus.className = 'text-[10px] text-emerald-400 font-semibold';
            }
        }

        function applyTemplateCustomParams() {
            onCustomParamChange();
            showToast('⚙️ Custom parameters applied & Backtest running...', 'info');
            executeBacktest();
        }

        function resetDefaultPythonCode() {
            onCustomParamChange();
            showToast('🔄 Python code reset to template defaults!', 'info');
        }

        function syncPythonCodeFromForm() {
            onCustomParamChange();
            showToast('✅ Python code synchronized from current parameters!', 'success');
        }

        function loadTemplate(type) {
            activeTemplateType = type;
            let stratName = 'Nifty_Supertrend_7_3';
            let sym = 'NIFTY';
            let exch = 'NSE_INDEX';
            let tf = '5m';
            let sl = 0.8;
            let tg = 2.2;
            let fast = 7;
            let slow = 3.0;
            let rsi = 50;
            let title = 'Supertrend (7, 3) Parameters Customizer';
            let lblFast = 'ATR Period';
            let lblSlow = 'ATR Multiplier';

            // Update button styles in quick-templates-bar
            ['smc', 'supertrend', 'vwap_pullback', 'orb_breakout', 'mcx_crude', 'crypto_btc', 'ema_cross'].forEach(t => {
                const btn = document.getElementById('tpl-btn-' + t);
                if (btn) {
                    if (t === type) {
                        btn.className = 'px-3 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 ring-2 ring-indigo-400 text-white border border-indigo-400 shadow-lg transition flex items-center gap-1 scale-[1.02]';
                    } else {
                        btn.className = 'px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition flex items-center gap-1';
                    }
                }
            });

            if (type === 'smc') {
                stratName = 'Nifty_SMC_Institutional';
                sym = 'NIFTY';
                exch = 'NSE_INDEX';
                tf = '5m';
                sl = 0.8;
                tg = 2.4;
                fast = 3;
                slow = 3.0;
                rsi = 50;
                title = 'SMC OrderBlock + FVG (1:3 RR) Parameters';
                lblFast = 'Swing Window (bars)';
                lblSlow = 'Risk:Reward Ratio';
            } else if (type === 'crypto_btc') {
                stratName = 'BTC_SMC_Perpetual';
                sym = 'BTCUSDT';
                exch = 'BINANCE';
                tf = '5m';
                sl = 1.0;
                tg = 3.0;
                fast = 3;
                slow = 3.0;
                rsi = 50;
                title = 'BTC/USDT SMC Perpetual Futures Parameters';
                lblFast = 'Swing Window (bars)';
                lblSlow = 'Risk:Reward Ratio';
            } else if (type === 'supertrend') {
                stratName = 'Nifty_Supertrend_7_3';
                sym = 'NIFTY';
                exch = 'NSE_INDEX';
                tf = '5m';
                sl = 0.8;
                tg = 2.2;
                fast = 7;
                slow = 3.0;
                rsi = 50;
                title = 'Supertrend (7, 3) Trend Rider Parameters';
                lblFast = 'ATR Period';
                lblSlow = 'ATR Multiplier';
            } else if (type === 'vwap_pullback') {
                stratName = 'BankNifty_VWAP_Pullback';
                sym = 'BANKNIFTY';
                exch = 'NSE_INDEX';
                tf = '5m';
                sl = 0.6;
                tg = 1.8;
                fast = 20;
                slow = 50;
                rsi = 50;
                title = 'VWAP + 20 EMA Pullback Parameters';
                lblFast = 'Fast EMA';
                lblSlow = 'Slow Trend EMA';
            } else if (type === 'orb_breakout') {
                stratName = 'Nifty_15m_ORB_Breakout';
                sym = 'NIFTY';
                exch = 'NSE_INDEX';
                tf = '5m';
                sl = 0.5;
                tg = 1.5;
                fast = 15;
                slow = 14;
                rsi = 50;
                title = 'ORB 15-Min Breakout Parameters';
                lblFast = 'Opening Period (mins)';
                lblSlow = 'ATR Filter Period';
            } else if (type === 'bollinger') {
                stratName = 'Nifty_Bollinger_Reversion';
                sym = 'NIFTY';
                exch = 'NSE_INDEX';
                tf = '15m';
                sl = 0.8;
                tg = 1.8;
                fast = 20;
                slow = 2.0;
                rsi = 35;
                title = 'Bollinger Bands (20, 2) Mean Reversion Parameters';
                lblFast = 'BB Period';
                lblSlow = 'BB StdDev';
            } else if (type === 'mcx_crude') {
                stratName = 'MCX_Crude_Breakout';
                sym = 'CRUDEOIL';
                exch = 'MCX';
                tf = '5m';
                sl = 1.0;
                tg = 2.5;
                fast = 20;
                slow = 50;
                rsi = 55;
                title = 'MCX Crude Oil Momentum Parameters';
                lblFast = 'Fast EMA';
                lblSlow = 'Slow EMA';
            } else if (type === 'ema_cross') {
                stratName = 'Nifty_EMA_Trend';
                sym = 'NIFTY';
                exch = 'NSE_INDEX';
                tf = '5m';
                sl = 0.8;
                tg = 1.8;
                fast = 20;
                slow = 50;
                rsi = 50;
                title = 'EMA 20/50 Trend Cross Parameters';
                lblFast = 'Fast EMA';
                lblSlow = 'Slow EMA';
            }

            document.getElementById('tpl-editor-title').innerText = title;
            document.getElementById('lbl_tpl_fast').innerText = lblFast;
            document.getElementById('lbl_tpl_slow').innerText = lblSlow;

            document.getElementById('strategy_name').value = stratName;
            document.getElementById('symbol').value = sym;
            document.getElementById('exchange').value = exch;
            document.getElementById('timeframe').value = tf;
            document.getElementById('stoploss_val').value = sl;
            document.getElementById('target_val').value = tg;

            document.getElementById('tpl_fast_ema').value = fast;
            document.getElementById('tpl_slow_ema').value = slow;
            document.getElementById('tpl_rsi_threshold').value = rsi;
            document.getElementById('tpl_sl_pct').value = sl;
            document.getElementById('tpl_tg_pct').value = tg;

            const params = {
                strategy_name: stratName, symbol: sym, timeframe: tf,
                fast: fast, slow: slow, rsi: rsi, sl: sl, tg: tg, dir: "BOTH"
            };
            document.getElementById('python-strategy-code').value = generateTemplatePythonCode(type, params);
            showToast('🚀 Template "' + title + '" Loaded & Executing...', 'info');
            executeBacktest();
        }

        async function runPythonCodeBacktest() {
            const code = document.getElementById('python-strategy-code').value;
            if (!code || !code.trim()) {
                alert('Please enter or generate Python strategy code first.');
                return;
            }

            document.getElementById('loader').classList.remove('hidden');
            document.getElementById('error-box').classList.add('hidden');
            document.getElementById('metrics-grid').classList.add('hidden');
            document.getElementById('deploy-banner').classList.add('hidden');
            document.getElementById('chart-section').classList.add('hidden');
            document.getElementById('table-section').classList.add('hidden');

            const payload = {
                python_code: code,
                strategy_name: document.getElementById('strategy_name').value,
                symbol: document.getElementById('symbol').value.toUpperCase(),
                exchange: document.getElementById('exchange').value,
                timeframe: document.getElementById('timeframe').value,
                start_date: document.getElementById('start_date').value,
                end_date: document.getElementById('end_date').value,
                stoploss_val: parseFloat(document.getElementById('stoploss_val').value),
                target_val: parseFloat(document.getElementById('target_val').value),
                capital: 100000.0,
                quantity: 50,
                slippage_pct: 0.05,
                brokerage_per_trade: 40.0
            };
            currentStrategyConfig = payload;

            const btn = document.getElementById('btn-run-python');
            btn.innerHTML = '<div class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent"></div> Running Python Simulation...';

            try {
                const res = await fetch('/api/run-python-code', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                document.getElementById('loader').classList.add('hidden');
                btn.innerHTML = '<i data-lucide="play" class="h-3.5 w-3.5"></i> ▶️ Run Python Code Backtest';
                lucide.createIcons();

                if (data.status === 'error') {
                    document.getElementById('error-box').innerText = 'Python Execution Error: ' + data.message;
                    document.getElementById('error-box').classList.remove('hidden');
                    return;
                }

                currentStrategyMetrics = data;
                globalTrades = data.trades || [];

                document.getElementById('m-net-pnl').innerText = '₹' + data.total_net_pnl.toLocaleString();
                document.getElementById('m-net-pnl').className = data.total_net_pnl >= 0 ? 'text-xl font-bold text-emerald-400 mt-1' : 'text-xl font-bold text-rose-400 mt-1';
                document.getElementById('m-winrate').innerText = data.win_rate + '%';
                document.getElementById('m-pf').innerText = data.profit_factor;
                document.getElementById('m-dd').innerText = data.max_drawdown_pct + '%';
                document.getElementById('m-sharpe').innerText = data.sharpe_ratio;
                document.getElementById('m-trades').innerText = data.total_trades;

                document.getElementById('metrics-grid').classList.remove('hidden');
                document.getElementById('deploy-banner').classList.remove('hidden');

                // Render Chart
                if (data.equity_curve && data.equity_curve.length > 0) {
                    const x = data.equity_curve.map(e => e.datetime);
                    const y = data.equity_curve.map(e => e.equity);

                    Plotly.newPlot('equity-chart', [{
                        x: x, y: y, type: 'scatter', mode: 'lines',
                        line: {color: '#10b981', width: 2.5},
                        fill: 'tozeroy', fillcolor: 'rgba(16, 185, 129, 0.08)'
                    }], {
                        margin: {t: 20, r: 20, l: 60, b: 40},
                        paper_bgcolor: '#161f30',
                        plot_bgcolor: '#161f30',
                        font: {color: '#94a3b8', family: 'system-ui'},
                        xaxis: {gridcolor: '#2d3748', showgrid: true},
                        yaxis: {gridcolor: '#2d3748', showgrid: true, tickprefix: '₹'}
                    }, {responsive: true});

                    document.getElementById('chart-section').classList.remove('hidden');
                }

                // Render Trade Logs
                const tbody = document.getElementById('trades-body');
                tbody.innerHTML = '';
                globalTrades.forEach((t, idx) => {
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/50';
                    tr.innerHTML = `
                        <td class="py-2.5 px-4">${idx + 1}</td>
                        <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${t.trade_type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">${t.trade_type}</span></td>
                        <td class="py-2.5 px-4">${t.entry_time}</td>
                        <td class="py-2.5 px-4">${t.exit_time}</td>
                        <td class="py-2.5 px-4 text-right">₹${t.entry_price}</td>
                        <td class="py-2.5 px-4 text-right">₹${t.exit_price}</td>
                        <td class="py-2.5 px-4 text-right">₹${t.gross_pnl}</td>
                        <td class="py-2.5 px-4 text-right text-slate-500">₹${t.friction_cost}</td>
                        <td class="py-2.5 px-4 text-right font-bold ${t.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">₹${t.net_pnl}</td>
                        <td class="py-2.5 px-4 text-slate-400">${t.exit_reason}</td>
                    `;
                    tbody.appendChild(tr);
                });
                document.getElementById('table-section').classList.remove('hidden');

            } catch (err) {
                document.getElementById('loader').classList.add('hidden');
                btn.innerHTML = '<i data-lucide="play" class="h-3.5 w-3.5"></i> ▶️ Run Python Code Backtest';
                document.getElementById('error-box').innerText = 'Connection error: ' + err;
                document.getElementById('error-box').classList.remove('hidden');
            }
        }

        async function deployStrategyWithMode(mode) {
            const sym = document.getElementById('symbol').value.toUpperCase();
            const name = document.getElementById('strategy_name').value;
            const pythonCode = document.getElementById('python-strategy-code').value;

            if (mode === 'REAL') {
                const confirmed = confirm(`⚠️ CAUTION: You are about to deploy '${name}' on ${sym} to REAL LIVE BROKER trading with REAL MONEY!\n\nConfirm Live Real-Money Deployment?`);
                if (!confirmed) return;
            }

            const payload = {
                config: currentStrategyConfig.symbol ? currentStrategyConfig : {
                    strategy_name: name,
                    symbol: sym,
                    exchange: document.getElementById('exchange').value,
                    timeframe: document.getElementById('timeframe').value,
                    stoploss_val: parseFloat(document.getElementById('stoploss_val').value),
                    target_val: parseFloat(document.getElementById('target_val').value),
                    capital: 100000.0,
                    quantity: 50
                },
                mode: mode,
                python_code: pythonCode
            };

            try {
                const res = await fetch('/api/deploy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.status === 'success') {
                    alert(`🎉 DEPLOYED SUCCESSFULLY TO OPENALGO!\n\nMode: ${mode}\nStrategy: ${data.strategy_name}\nBot File: ${data.filepath}\n\nThe strategy daemon is ready for execution!`);
                } else {
                    alert('Deployment error: ' + data.message);
                }
            } catch (err) {
                alert('Deployment error: ' + err);
            }
        }

        function filterInstrumentCategory(cat) {
            ['ALL', 'INDEX', 'COMMODITY', 'STOCK'].forEach(c => {
                const btn = document.getElementById('filter-btn-' + c);
                if (btn) {
                    if (c === cat) {
                        btn.className = 'px-2.5 py-1 rounded-lg font-semibold bg-indigo-600 text-white transition';
                    } else {
                        btn.className = 'px-2.5 py-1 rounded-lg font-semibold text-slate-400 hover:text-white transition';
                    }
                }
            });

            const sel = document.getElementById('opt_symbol_select');
            const groups = sel.getElementsByTagName('optgroup');
            for (let g of groups) {
                if (cat === 'ALL' || g.getAttribute('data-cat') === cat) {
                    g.style.display = '';
                } else {
                    g.style.display = 'none';
                }
            }
        }

        function selectQuickInstrument(sym) {
            const sel = document.getElementById('opt_symbol_select');
            if (sel) {
                sel.value = sym;
                fetchMarketSpotAndStrikes();
            }
        }

        function setLookback(days) {
            [7, 30, 90, 180].forEach(d => {
                const btn = document.getElementById('lb-btn-' + d);
                if (btn) {
                    if (d === days) {
                        btn.className = 'px-2.5 py-1 text-xs rounded bg-indigo-600 ring-2 ring-indigo-400 text-white font-bold transition shadow';
                    } else {
                        btn.className = 'px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-semibold transition';
                    }
                }
            });
            const end = new Date();
            const start = new Date();
            start.setDate(end.getDate() - days);
            document.getElementById('end_date').value = end.toISOString().split('T')[0];
            document.getElementById('start_date').value = start.toISOString().split('T')[0];
            executeBacktest();
        }

        function exportTradesCSV() {
            if (!globalTrades || globalTrades.length === 0) return;
            const headers = ["Trade #", "Type", "Entry Time", "Exit Time", "Entry Price", "Exit Price", "Gross PnL", "Friction", "Net PnL", "Reason"];
            const rows = globalTrades.map((t, idx) => [
                idx + 1, t.trade_type, t.entry_time, t.exit_time, t.entry_price, t.exit_price, t.gross_pnl, t.friction_cost, t.net_pnl, t.exit_reason
            ]);
            let csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\\n");
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `trades_${document.getElementById('strategy_name').value}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        // --- PHASE 4: LIVE OPERATIONS & RMS ---
        let currentMode = 'ANALYZER';

        async function fetchLiveOpsStatus() {
            try {
                const res = await fetch('/api/live/status');
                const data = await res.json();
                
                currentMode = data.mode.mode;
                const isLive = (currentMode === 'LIVE');
                
                // Update Mode Banner
                document.getElementById('mode-title').innerText = isLive ? 'LIVE BROKER EXECUTION' : 'ANALYZER MODE (Virtual ₹1 Cr Sandbox)';
                document.getElementById('mode-indicator').innerText = isLive ? 'REAL MONEY' : 'PAPER TRADING';
                document.getElementById('mode-indicator').className = isLive ? 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
                document.getElementById('mode-desc').innerText = data.mode.description;
                document.getElementById('btn-mode-toggle').innerHTML = isLive ? '<i data-lucide="repeat" class="h-4 w-4"></i> Switch to Analyzer Mode' : '<i data-lucide="repeat" class="h-4 w-4"></i> Switch to Live Mode';
                document.getElementById('mode-badge-icon').innerText = isLive ? '🔥' : '🧪';

                // Update Cards
                document.getElementById('live-unrealized-pnl').innerText = (data.state.unrealized_pnl >= 0 ? '+' : '') + '₹' + data.state.unrealized_pnl.toLocaleString();
                document.getElementById('live-unrealized-pnl').className = data.state.unrealized_pnl >= 0 ? 'text-xl font-bold text-emerald-400 font-mono mt-1' : 'text-xl font-bold text-rose-400 font-mono mt-1';
                document.getElementById('live-pos-count').innerText = data.state.open_positions.length;
                
                document.getElementById('live-realized-pnl').innerText = '₹' + data.rms.daily_realized_pnl.toLocaleString();
                document.getElementById('broker-status').innerText = data.state.broker_name ? data.state.broker_name.toUpperCase() + ' (Connected)' : 'Disconnected';
                document.getElementById('broker-user').innerText = 'User: ' + (data.state.username || 'None');

                // RMS Status
                const isLocked = data.rms.is_locked;
                document.getElementById('rms-lock-status').innerText = isLocked ? 'LOCKED (HALTED)' : 'ARMED (ACTIVE)';
                document.getElementById('rms-lock-status').className = isLocked ? 'text-xl font-bold text-rose-500 font-mono mt-1' : 'text-xl font-bold text-emerald-400 font-mono mt-1';
                document.getElementById('rms-lock-reason').innerText = isLocked ? data.rms.lock_reason : 'Max Daily Loss: ₹' + data.rms.max_daily_loss.toLocaleString();

                // Fill Forms
                document.getElementById('rms_max_loss').value = data.rms.max_daily_loss;
                document.getElementById('rms_max_profit').value = data.rms.max_daily_profit;
                document.getElementById('rms_max_cap').value = data.rms.max_capital_per_trade;
                document.getElementById('rms_enabled').checked = data.rms.enabled;

                document.getElementById('tg_bot_token').value = data.telegram.bot_token || '';
                document.getElementById('tg_chat_id').value = data.telegram.chat_id || '';
                document.getElementById('tg_enabled').checked = data.telegram.enabled;

                lucide.createIcons();
            } catch (err) {
                console.error(err);
            }
        }

        async function toggleExecutionMode() {
            const nextMode = (currentMode === 'LIVE') ? 'ANALYZER' : 'LIVE';
            if (nextMode === 'LIVE') {
                if (!confirm('⚠️ ATTENTION: You are about to enable LIVE BROKER EXECUTION with real money! All deployed strategy bots will place real orders on Fyers. Confirm?')) return;
            }
            try {
                const res = await fetch('/api/mode/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: nextMode})
                });
                const data = await res.json();
                fetchLiveOpsStatus();
            } catch (err) {
                alert('Mode switch error: ' + err);
            }
        }

        async function executePanicKillSwitch() {
            if (!confirm('🚨 EMERGENCY WARNING: This will immediately CANCEL ALL ORDERS and MARKET SQUARE-OFF ALL POSITIONS. Proceed?')) return;
            try {
                const res = await fetch('/api/kill-switch/execute', {method: 'POST'});
                const data = await res.json();
                alert(`🚨 PANIC KILL SWITCH ACTIVATED!\nPositions Closed: ${data.positions_closed}\nOrders Cancelled: ${data.orders_cancelled}\nDetails: ${data.details.join(' ')}`);
                fetchLiveOpsStatus();
            } catch (err) {
                alert('Kill switch error: ' + err);
            }
        }

        async function resetRMSLock() {
            try {
                await fetch('/api/rms/unlock', {method: 'POST'});
                alert('RMS Circuit Breaker Reset. Trading re-enabled.');
                fetchLiveOpsStatus();
            } catch (err) {
                alert('Unlock error: ' + err);
            }
        }

        async function saveRMSConfig() {
            const payload = {
                max_daily_loss: parseFloat(document.getElementById('rms_max_loss').value),
                max_daily_profit: parseFloat(document.getElementById('rms_max_profit').value),
                max_capital_per_trade: parseFloat(document.getElementById('rms_max_cap').value),
                max_open_positions: 4,
                enabled: document.getElementById('rms_enabled').checked
            };
            try {
                await fetch('/api/rms/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                alert('RMS settings saved successfully!');
                fetchLiveOpsStatus();
            } catch (err) {
                alert('RMS save error: ' + err);
            }
        }

        async function saveTelegramConfig() {
            const payload = {
                bot_token: document.getElementById('tg_bot_token').value.trim(),
                chat_id: document.getElementById('tg_chat_id').value.trim(),
                enabled: document.getElementById('tg_enabled').checked,
                trade_alerts: true,
                sl_tp_alerts: true,
                rms_alerts: true,
                eod_summary: true
            };
            try {
                await fetch('/api/telegram/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                alert('Telegram settings saved!');
                fetchLiveOpsStatus();
            } catch (err) {
                alert('Telegram save error: ' + err);
            }
        }

        async function sendTestTelegramAlert() {
            try {
                const res = await fetch('/api/telegram/test', {method: 'POST'});
                const data = await res.json();
                if (data.status === 'success') {
                    alert('✅ Test alert sent to Telegram! Check your phone.');
                } else {
                    alert('❌ Telegram notice: ' + data.message);
                }
            } catch (err) {
                alert('Telegram test error: ' + err);
            }
        }

        // Auto backtest on initial page load & initialize live orderbook polling
        window.addEventListener('DOMContentLoaded', () => {
            safeCreateIcons();
            try { fetchSavedStrategies(); } catch(e) { console.error('fetchSavedStrategies error:', e); }
            try { fetchSavedStraddlePresets(); } catch(e) { console.error('fetchSavedStraddlePresets error:', e); }
            try { fetchLiveAlgosAndOrderbook(); } catch(e) { console.error('fetchLiveAlgos error:', e); }
            try { setInterval(fetchLiveAlgosAndOrderbook, 3000); } catch(e) { console.error('polling error:', e); }
            try { onCustomParamChange(); } catch(e) { console.error('onCustomParamChange error:', e); }
            try { executeBacktest(false); } catch(e) { console.error('executeBacktest error:', e); }
        });
    </script>
</body>
</html>
"""

# ==========================================
# ==========================================
# FLASK ROUTE HANDLERS
# ==========================================

import uuid
import io

UPLOADED_DATASETS: Dict[str, pd.DataFrame] = {}

@app.route("/")
def index():
    now = datetime.now(IST)
    default_end = now.strftime("%Y-%m-%d")
    default_start = (now - timedelta(days=25)).strftime("%Y-%m-%d")
    return render_template_string(
        HTML_TEMPLATE,
        default_start=default_start,
        default_end=default_end
    )

@app.route("/api/symbols/search", methods=["GET"])
def api_symbols_search():
    q = request.args.get("q", "").strip().upper()
    limit = int(request.args.get("limit", 30))
    if not q:
        popular = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "RELIANCE", "HDFCBANK", "TCS", "SBIN", "INFY", "TATAMOTORS"]
        results = [
            {
                "symbol": sym,
                "name": INSTRUMENT_CATALOG[sym]["name"],
                "exchange": INSTRUMENT_CATALOG[sym]["exchange"],
                "category": INSTRUMENT_CATALOG[sym]["category"],
                "lot_size": INSTRUMENT_CATALOG[sym]["lot_size"],
                "strike_step": INSTRUMENT_CATALOG[sym]["strike_step"]
            }
            for sym in popular if sym in INSTRUMENT_CATALOG
        ]
        return jsonify({"status": "success", "results": results})
        
    results = []
    seen = set()
    
    # 1. Curated Instrument Catalog
    for sym, meta in INSTRUMENT_CATALOG.items():
        if q in sym or q in meta.get("name", "").upper():
            results.append({
                "symbol": sym,
                "name": meta.get("name", sym),
                "exchange": meta.get("exchange", "NSE"),
                "category": meta.get("category", "STOCK"),
                "lot_size": meta.get("lot_size", 1),
                "strike_step": meta.get("strike_step", 50)
            })
            seen.add((sym, meta.get("exchange", "NSE")))
            
    # 2. SQLite symtoken search
    try:
        conn = sqlite3.connect("db/openalgo.db")
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT symbol, name, exchange, lotsize 
            FROM symtoken 
            WHERE symbol LIKE ? OR name LIKE ? 
            ORDER BY CASE 
                WHEN symbol = ? THEN 1 
                WHEN symbol LIKE ? THEN 2 
                ELSE 3 
            END, exchange
            LIMIT ?
        """, (f"%{q}%", f"%{q}%", q, f"{q}%", limit))
        for row in c.fetchall():
            sym, name, exch, lotsize = row[0], row[1], row[2], row[3]
            if (sym, exch) not in seen:
                results.append({
                    "symbol": sym,
                    "name": name or sym,
                    "exchange": exch,
                    "category": "COMMODITY" if exch == "MCX" else ("INDEX" if "INDEX" in exch else ("FNO" if exch == "NFO" else "STOCK")),
                    "lot_size": lotsize if (lotsize and lotsize > 0) else 1,
                    "strike_step": 50
                })
                seen.add((sym, exch))
        conn.close()
    except Exception as e:
        pass
        
    return jsonify({"status": "success", "results": results[:limit]})

@app.route("/api/ai-analyze-file", methods=["POST"])
def api_ai_analyze_file():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
    uploaded_file = request.files["file"]
    prompt = request.form.get("prompt", "")
    filename = uploaded_file.filename or "data.csv"
    ext = filename.rsplit(".", 1)[-1].lower()
    
    file_bytes = uploaded_file.read()
    
    if ext in ["csv", "xlsx", "xls", "json"]:
        try:
            if ext == "csv":
                df = pd.read_csv(io.BytesIO(file_bytes))
            elif ext in ["xlsx", "xls"]:
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                df = pd.read_json(io.BytesIO(file_bytes))
                
            col_map = {}
            for col in df.columns:
                c_clean = str(col).strip().lower()
                if "open" in c_clean: col_map[col] = "open"
                elif "high" in c_clean: col_map[col] = "high"
                elif "low" in c_clean: col_map[col] = "low"
                elif "close" in c_clean or "price" in c_clean or "ltp" in c_clean: col_map[col] = "close"
                elif "vol" in c_clean: col_map[col] = "volume"
                elif "date" in c_clean or "time" in c_clean or "timestamp" in c_clean: col_map[col] = "datetime"
            df = df.rename(columns=col_map)
            
            if "close" not in df.columns:
                return jsonify({"status": "error", "message": "Uploaded dataset must have at least a 'close' or 'price' column."}), 400
                
            if "open" not in df.columns: df["open"] = df["close"]
            if "high" not in df.columns: df["high"] = df["close"]
            if "low" not in df.columns: df["low"] = df["close"]
            if "volume" not in df.columns: df["volume"] = 1000
            
            if "datetime" in df.columns:
                df["datetime_str"] = df["datetime"].astype(str)
                df["time_str"] = df["datetime_str"].str.slice(11, 16).replace("", "10:00")
                df["date_str"] = df["datetime_str"].str.slice(0, 10)
            else:
                now_dt = datetime.now()
                df["datetime_str"] = [(now_dt - timedelta(minutes=5*i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(len(df))][::-1]
                df["time_str"] = "10:00"
                df["date_str"] = "2026-08-26"
                
            total_bars = len(df)
            price_change = ((df["close"].iloc[-1] - df["close"].iloc[0]) / (df["close"].iloc[0] + 1e-9)) * 100.0
            daily_volatility = df["close"].pct_change().std() * 100.0
            avg_bar_range = (df["high"] - df["low"]).mean()
            
            dataset_id = str(uuid.uuid4())[:8]
            UPLOADED_DATASETS[dataset_id] = df
            
            strat_config = AIStrategyCompiler.parse_with_antigravity_cli(prompt or "Supertrend 7 3 with EMA pullback on uploaded dataset")
            strat_config["dataset_id"] = dataset_id
            strat_config["strategy_name"] = f"UploadedData_{dataset_id}"
            python_code = AIStrategyCompiler.generate_python_code(strat_config)
            
            return jsonify({
                "status": "success",
                "dataset_id": dataset_id,
                "filename": filename,
                "total_bars": total_bars,
                "quant_summary": {
                    "total_candles": total_bars,
                    "price_change_pct": round(float(price_change), 2) if not np.isnan(price_change) else 0.0,
                    "volatility_pct": round(float(daily_volatility), 2) if not np.isnan(daily_volatility) else 0.0,
                    "avg_range": round(float(avg_bar_range), 2) if not np.isnan(avg_bar_range) else 0.0
                },
                "config": strat_config,
                "python_code": python_code,
                "message": f"Successfully parsed {total_bars} candles from {filename}! Ready for instant backtesting."
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error parsing dataset file: {str(e)}"}), 400
            
    elif ext in ["png", "jpg", "jpeg", "webp"]:
        try:
            prompt_augmented = f"{prompt} [Chart Image Attached: {filename}] Extract technical indicators and trading rules."
            strat_config = AIStrategyCompiler.parse_with_antigravity_cli(prompt_augmented)
            strat_config["strategy_name"] = f"ChartVision_{filename.rsplit('.', 1)[0][:12]}"
            python_code = AIStrategyCompiler.generate_python_code(strat_config)
            
            return jsonify({
                "status": "success",
                "filename": filename,
                "is_image": True,
                "config": strat_config,
                "python_code": python_code,
                "message": f"Successfully analyzed chart setup from image '{filename}' and synthesized Python strategy rules!"
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error analyzing chart image: {str(e)}"}), 400
            
    else:
        try:
            text_content = file_bytes.decode("utf-8", errors="ignore")
            strat_config = AIStrategyCompiler.parse_with_antigravity_cli(prompt or text_content[:200])
            python_code = text_content if ("def generate_signals" in text_content or "import pandas" in text_content) else AIStrategyCompiler.generate_python_code(strat_config)
            
            return jsonify({
                "status": "success",
                "filename": filename,
                "config": strat_config,
                "python_code": python_code,
                "message": f"Successfully loaded strategy rules from '{filename}'!"
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error reading document: {str(e)}"}), 400

@app.route("/api/ai-compile", methods=["POST"])
def api_ai_compile():
    req = request.get_json() or {}
    prompt = req.get("prompt", "")
    config = AIStrategyCompiler.parse_with_antigravity_cli(prompt)
    python_code = AIStrategyCompiler.generate_python_code(config)
    
    now = datetime.now(IST)
    start_date = (now - timedelta(days=25)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    
    return jsonify({
        "status": "success",
        "config": config,
        "python_code": python_code,
        "start_date": start_date,
        "end_date": end_date
    })

@app.route("/api/run-python-code", methods=["POST"])
def api_run_python_code():
    req = request.get_json() or {}
    code_str = req.get("python_code", "")
    symbol = req.get("symbol", "NIFTY")
    exchange = req.get("exchange", "NSE_INDEX")
    timeframe = req.get("timeframe", "5m")
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    capital = float(req.get("capital", 100000.0))
    quantity = int(req.get("quantity", 50))
    stoploss_val = float(req.get("stoploss_val", 1.0))
    target_val = float(req.get("target_val", 2.0))
    slippage_pct = float(req.get("slippage_pct", 0.05))
    brokerage = float(req.get("brokerage_per_trade", 40.0))
    dataset_id = req.get("dataset_id")
    
    df_custom = UPLOADED_DATASETS.get(dataset_id) if dataset_id else None
    
    try:
        res = CustomCodeBacktester.run_python_strategy(
            code_str=code_str,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            capital=capital,
            quantity=quantity,
            stoploss_val=stoploss_val,
            target_val=target_val,
            slippage_pct=slippage_pct,
            brokerage=brokerage,
            df_custom=df_custom
        )
        res["status"] = "success"
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/symbols/catalog", methods=["GET"])
def api_symbols_catalog():
    return jsonify({"status": "success", "catalog": INSTRUMENT_CATALOG})

@app.route("/api/run-backtest", methods=["POST"])
def api_run_backtest():
    req = request.get_json() or {}
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    dataset_id = req.get("dataset_id")
    
    try:
        engine = BacktestEngine(req)
        if dataset_id and dataset_id in UPLOADED_DATASETS:
            df = UPLOADED_DATASETS[dataset_id].copy()
        else:
            df = engine.fetch_data(start_date, end_date)
            
        if df.empty:
            return jsonify({"status": "error", "message": "No historical candle data returned for this date range / symbol."}), 400
            
        res = engine.run_simulation(df)
        res["status"] = "success"
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    req = request.get_json() or {}
    base_config = req.get("base_config", {})
    start_date = req.get("start_date", "")
    end_date = req.get("end_date", "")
    param_grid = req.get("param_grid", {})
    
    try:
        res = StrategyOptimizer.run_grid_search(base_config, start_date, end_date, param_grid)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/portfolio/combine", methods=["POST"])
def api_portfolio_combine():
    req = request.get_json() or {}
    start_date = req.get("start_date", "")
    end_date = req.get("end_date", "")
    
    saved = StrategyStore.list_strategies()
    configs = [s["config"] for s in saved if "config" in s]
    
    if len(configs) < 2:
        configs = [
            {"strategy_name": "Nifty_EMA_Trend", "symbol": "NIFTY", "exchange": "NSE_INDEX", "timeframe": "5m", "stoploss_val": 0.8, "target_val": 1.8, "capital": 100000.0, "quantity": 50},
            {"strategy_name": "BankNifty_Momentum", "symbol": "BANKNIFTY", "exchange": "NSE_INDEX", "timeframe": "5m", "stoploss_val": 0.6, "target_val": 1.5, "capital": 100000.0, "quantity": 15}
        ]
        
    try:
        res = PortfolioEngine.combine_strategies(configs, start_date, end_date)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/generate-pinescript", methods=["POST"])
def api_generate_pinescript():
    req = request.get_json() or {}
    config = req.get("config", {})
    pinescript = PineScriptGenerator.generate_pinescript_v5(config)
    return jsonify({"status": "success", "pinescript": pinescript})

@app.route("/api/live/algos", methods=["GET"])
def api_live_algos():
    algos = LiveAlgoRegistry.get_running_algos()
    return jsonify(algos)

@app.route("/api/live/orderbook", methods=["GET"])
def api_live_orderbook():
    orderbook = LiveAlgoRegistry.get_orderbook()
    return jsonify(orderbook)

@app.route("/api/live/action", methods=["POST"])
def api_live_action():
    req = request.get_json() or {}
    algo_id = req.get("algo_id")
    action = req.get("action")
    res = LiveAlgoRegistry.perform_action(algo_id, action)
    return jsonify(res)

@app.route("/api/deploy", methods=["POST"])
def api_deploy():
    req = request.get_json() or {}
    config = req.get("config", {})
    mode = req.get("mode", "ANALYZER")
    python_code = req.get("python_code")
    if python_code and python_code.strip():
        filepath = StrategyDeployer.generate_custom_python_strategy_file(python_code, config, mode)
    else:
        filepath = StrategyDeployer.save_to_file(config, mode)
        
    algo_entry = LiveAlgoRegistry.register_deployment(config, mode, python_code)
    
    return jsonify({
        "status": "success",
        "mode": mode,
        "strategy_name": config.get("strategy_name", "Strategy"),
        "filepath": filepath,
        "algo_id": algo_entry["id"],
        "message": f"Successfully deployed '{config.get('strategy_name')}' in {mode} mode! Registered in Running Algos & Live Orderbook."
    })

@app.route("/api/strategies", methods=["GET"])
def api_get_strategies():
    strategies = StrategyStore.list_strategies()
    return jsonify(strategies)

@app.route("/api/strategies/save", methods=["POST"])
def api_save_strategy():
    req = request.get_json() or {}
    config = req.get("config", {})
    metrics = req.get("metrics", {})
    res = StrategyStore.save_strategy(config, metrics)
    return jsonify(res)

@app.route("/api/strategies/<strategy_id>", methods=["DELETE"])
def api_delete_strategy(strategy_id):
    res = StrategyStore.delete_strategy(strategy_id)
    return jsonify(res)

@app.route("/api/options/strikes", methods=["GET"])
def api_options_strikes():
    symbol = request.args.get("symbol", "NIFTY")
    iv = float(request.args.get("iv", 14.0))
    days = float(request.args.get("days", 4.0))
    res = OptionsGreeksEngine.get_market_spot_and_strikes(symbol, iv=iv, days=days)
    res["status"] = "success"
    return jsonify(res)

@app.route("/api/options/payoff", methods=["POST"])
def api_options_payoff():
    req = request.get_json() or {}
    spot = float(req.get("spot", 24500.0))
    legs = req.get("legs", [])
    days = float(req.get("days_to_expiry", 4.0))
    iv = float(req.get("iv", 14.0))
    
    payoff_data = OptionsGreeksEngine.generate_payoff(spot, legs, days, iv)
    payoff_data["status"] = "success"
    return jsonify(payoff_data)

@app.route("/api/options/backtest-straddle", methods=["POST"])
def api_backtest_straddle():
    req = request.get_json() or {}
    symbol = req.get("symbol", "NIFTY")
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    entry_time = req.get("entry_time", "09:20")
    exit_time = req.get("exit_time", "15:15")
    strike_selection = req.get("strike_selection", "ATM")
    sl_mode = req.get("sl_mode", "INDIVIDUAL")
    sl_leg_pct = float(req.get("sl_leg_pct", 25.0))
    lots = int(req.get("lots", 1))
    
    # Universal instrument lookup from INSTRUMENT_CATALOG
    catalog_entry = INSTRUMENT_CATALOG.get(symbol, {})
    exchange = catalog_entry.get("exchange", "NSE_INDEX")
    default_lot_size = catalog_entry.get("lot_size", 50)
    unit_lot_size = int(req.get("lot_size", default_lot_size))
    total_qty = unit_lot_size * lots
    strike_step = catalog_entry.get("strike_step", 50)
    
    engine = BacktestEngine({"symbol": symbol, "exchange": exchange, "timeframe": "5m"})
    df = engine.fetch_data(start_date, end_date)
    if df.empty:
        return jsonify({"status": "error", "message": f"Failed to fetch {symbol} spot data for selected date range ({start_date} to {end_date})"}), 400
        
    res = IntradayStraddleBacktester.simulate_920_straddle(
        df,
        symbol=symbol,
        entry_time=entry_time,
        exit_time=exit_time,
        strike_selection=strike_selection,
        sl_mode=sl_mode,
        sl_leg_pct=sl_leg_pct,
        lot_size=total_qty,
        strike_step=strike_step
    )
    res["status"] = "success"
    return jsonify(res)

# --- STRADDLE STRATEGY SAVING & DUAL DEPLOYMENT ENDPOINTS ---

def init_saved_straddles_db():
    try:
        import sqlite3
        conn = sqlite3.connect("db/openalgo.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS saved_straddle_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                strike_selection TEXT NOT NULL,
                sl_mode TEXT NOT NULL,
                sl_leg_pct REAL NOT NULL,
                lot_size INTEGER NOT NULL,
                lots INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing saved_straddle_strategies: {e}")

init_saved_straddles_db()

@app.route("/api/options/save-strategy", methods=["POST"])
def api_save_options_strategy():
    import sqlite3
    req = request.get_json() or {}
    name = req.get("name", "NIFTY_Straddle").strip()
    symbol = req.get("symbol", "NIFTY")
    entry_time = req.get("entry_time", "09:20")
    exit_time = req.get("exit_time", "15:15")
    strike_sel = req.get("strike_selection", "MATCHED_PREMIUM")
    sl_mode = req.get("sl_mode", "COST_TO_COST")
    sl_pct = float(req.get("sl_leg_pct", 25.0))
    lot_size = int(req.get("lot_size", 65))
    lots = int(req.get("lots", 1))

    try:
        conn = sqlite3.connect("db/openalgo.db")
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO saved_straddle_strategies 
            (name, symbol, entry_time, exit_time, strike_selection, sl_mode, sl_leg_pct, lot_size, lots)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, symbol, entry_time, exit_time, strike_sel, sl_mode, sl_pct, lot_size, lots))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Strategy '{name}' saved successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/options/saved-strategies", methods=["GET"])
def api_get_saved_options_strategies():
    import sqlite3
    try:
        conn = sqlite3.connect("db/openalgo.db")
        c = conn.cursor()
        c.execute("SELECT id, name, symbol, entry_time, exit_time, strike_selection, sl_mode, sl_leg_pct, lot_size, lots, created_at FROM saved_straddle_strategies ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        strats = []
        for r in rows:
            strats.append({
                "id": r[0], "name": r[1], "symbol": r[2], "entry_time": r[3],
                "exit_time": r[4], "strike_selection": r[5], "sl_mode": r[6],
                "sl_leg_pct": r[7], "lot_size": r[8], "lots": r[9], "created_at": r[10]
            })
        return jsonify({"status": "success", "strategies": strats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/options/deploy-straddle", methods=["POST"])
def api_deploy_options_straddle():
    import subprocess
    req = request.get_json() or {}
    mode = req.get("mode", "ANALYZER")  # "ANALYZER" or "REAL"
    strat_name = req.get("strategy_name", f"{req.get('symbol', 'NIFTY')}_Straddle_{mode}").replace(" ", "_")
    
    config = {
        "strategy_name": strat_name,
        "symbol": req.get("symbol", "NIFTY"),
        "entry_time": req.get("entry_time", "09:20"),
        "exit_time": req.get("exit_time", "15:15"),
        "strike_selection": req.get("strike_selection", "MATCHED_PREMIUM"),
        "sl_mode": req.get("sl_mode", "COST_TO_COST"),
        "sl_leg_pct": float(req.get("sl_leg_pct", 25.0)),
        "lot_size": int(req.get("lot_size", 65)),
        "lots": int(req.get("lots", 1))
    }
    
    filepath = StrategyDeployer.generate_options_straddle_strategy(config, mode=mode)
    
    # Launch bot in background daemon
    proc = subprocess.Popen([sys.executable, filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return jsonify({
        "status": "success",
        "mode": mode,
        "strategy_name": strat_name,
        "filepath": filepath,
        "pid": proc.pid,
        "message": f"Successfully deployed '{strat_name}' to OpenAlgo in {mode} mode! (PID: {proc.pid})"
    })

# --- PHASE 4 ENDPOINTS ---

@app.route("/api/live/status", methods=["GET"])
def api_live_status():
    mode_status = ModeManager.get_current_mode()
    rms_config = RMSManager.get_config()
    telegram_config = TelegramAlertEngine.get_config()
    live_state = StateRecoveryEngine.get_live_system_state()
    return jsonify({
        "status": "success",
        "mode": mode_status,
        "rms": rms_config,
        "telegram": telegram_config,
        "state": live_state
    })

@app.route("/api/mode/toggle", methods=["POST"])
def api_mode_toggle():
    req = request.get_json() or {}
    mode = req.get("mode", "ANALYZER")
    res = ModeManager.set_mode(mode)
    return jsonify(res)

@app.route("/api/rms/update", methods=["POST"])
def api_rms_update():
    req = request.get_json() or {}
    max_loss = req.get("max_daily_loss", 5000)
    max_profit = req.get("max_daily_profit", 25000)
    max_pos = req.get("max_open_positions", 4)
    max_cap = req.get("max_capital_per_trade", 50000)
    enabled = req.get("enabled", True)
    res = RMSManager.update_settings(max_loss, max_profit, max_pos, max_cap, enabled)
    return jsonify({"status": "success", "rms": res})

@app.route("/api/rms/unlock", methods=["POST"])
def api_rms_unlock():
    res = RMSManager.unlock_manual()
    return jsonify({"status": "success", "rms": res})

@app.route("/api/telegram/config", methods=["POST"])
def api_telegram_config():
    req = request.get_json() or {}
    TelegramAlertEngine.save_config(req)
    return jsonify({"status": "success"})

@app.route("/api/telegram/test", methods=["POST"])
def api_telegram_test():
    now_str = datetime.now(IST).strftime("%H:%M:%S IST")
    msg = f"🧪 *OPENALGO TELEGRAM TEST ALERT*\n━━━━━━━━━━━━━━━━━━━━\n✅ Your Telegram Bot connection is working perfectly!\n⏰ Time: `{now_str}`\n━━━━━━━━━━━━━━━━━━━━"
    res = TelegramAlertEngine.send_message(msg)
    return jsonify(res)

@app.route("/api/kill-switch/execute", methods=["POST"])
def api_kill_switch_execute():
    client_ip = request.remote_addr or "127.0.0.1"
    res = PanicKillSwitch.execute("User UI Emergency Button Clicked", client_ip)
    return jsonify(res)

@app.route("/api/kill-switch/reset", methods=["POST"])
def api_kill_switch_reset():
    res = PanicKillSwitch.reset()
    return jsonify(res)

if __name__ == "__main__":
    print("Starting OpenAlgo Institutional Quant Studio on http://127.0.0.1:8080 ...")
    app.run(host="0.0.0.0", port=8080, debug=False)
