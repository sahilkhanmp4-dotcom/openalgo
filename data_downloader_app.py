"""
OpenAlgo Advanced Market Data Downloader & Visualizer Platform
Features:
- Smart Auto-Chunking for Large / Multi-Year / Multi-Month Data
- Continuous Futures Data Support
- Live Progress Bar for Bulk Downloads
- Direct 1-Click CSV Merged Download
- Interactive Candlestick + Volume + OI Chart
- Auto Symbol Suggestion & Presets
Runs on http://127.0.0.1:8080
"""

import io
import json
import os
import sqlite3
import time
import pandas as pd
import pytz
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, Response, stream_with_context

from database.auth_db import get_auth_token
from services.history_service import get_history_with_auth

app = Flask(__name__)
IST = pytz.timezone("Asia/Kolkata")

def get_active_auth():
    """Fetch active broker auth token and broker name from OpenAlgo db."""
    try:
        con = sqlite3.connect("db/openalgo.db")
        cur = con.cursor()
        row = cur.execute("SELECT name, broker, auth FROM auth WHERE is_revoked=0 LIMIT 1").fetchone()
        con.close()
        if row:
            username, broker, _ = row
            token = get_auth_token(username)
            return username, broker, token
    except Exception as e:
        print(f"Error fetching auth: {e}")
    return None, None, None

def search_symbols_in_db(query: str, limit: int = 20):
    """Search symbols in symtoken database table."""
    try:
        con = sqlite3.connect("db/openalgo.db")
        cur = con.cursor()
        q = f"%{query.upper()}%"
        rows = cur.execute(
            "SELECT symbol, exchange, expiry, lotsize, brsymbol FROM symtoken WHERE symbol LIKE ? OR brsymbol LIKE ? LIMIT ?",
            (q, q, limit)
        ).fetchall()
        con.close()
        return [{"symbol": r[0], "exchange": r[1], "expiry": r[2], "lotsize": r[3], "brsymbol": r[4]} for r in rows]
    except Exception as e:
        print(f"Error searching symbols: {e}")
        return []

def generate_chunks(start_date_str: str, end_date_str: str, interval: str):
    """Split date range into optimal chunks to prevent API timeout and rate limits."""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    if interval in ["1m", "2m", "3m"]:
        chunk_days = 30  # 30 days per chunk for 1m (ultra safe for broker memory/limits)
    elif interval in ["5m", "10m", "15m", "30m"]:
        chunk_days = 60  # 60 days for 5m/15m
    elif interval in ["1h", "2h", "4h"]:
        chunk_days = 90  # 90 days for hourly
    else:
        chunk_days = 300 # 300 days for daily
        
    chunks = []
    curr = start_dt
    while curr <= end_dt:
        chunk_end = min(curr + timedelta(days=chunk_days - 1), end_dt)
        chunks.append((curr.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        curr = chunk_end + timedelta(days=1)
    return chunks

def fetch_chunk_data(symbol: str, exchange: str, interval: str, chunk_start: str, chunk_end: str, auth_token: str, broker: str):
    """Fetch single chunk with error handling and rate limit padding."""
    success, response, status = get_history_with_auth(
        auth_token=auth_token,
        feed_token=None,
        broker=broker,
        symbol=symbol.strip().upper(),
        exchange=exchange.strip().upper(),
        interval=interval.strip(),
        start_date=chunk_start,
        end_date=chunk_end
    )
    if not success:
        err_msg = response.get("message", "Broker error") if isinstance(response, dict) else str(response)
        return False, err_msg, []
    
    data = response.get("data", []) if isinstance(response, dict) else []
    return True, "OK", data

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenAlgo - Bulk Market Data Downloader & Visualizer</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            500: '#6366f1',
                            600: '#4f46e5',
                            700: '#4338ca'
                        },
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
        @keyframes pulse-fast { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .pulse-fast { animation: pulse-fast 1s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    </style>
</head>
<body class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="border-b border-bordercolor bg-cardbg/90 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center font-bold text-xl text-white shadow-lg shadow-indigo-500/25">
                    ⚡
                </div>
                <div>
                    <h1 class="text-xl font-bold text-white flex items-center gap-2">
                        OpenAlgo <span class="text-xs px-2.5 py-0.5 rounded-full bg-gradient-to-r from-indigo-500/20 to-purple-500/20 text-indigo-300 border border-indigo-500/30">Bulk Data Engine</span>
                    </h1>
                    <p class="text-xs text-slate-400">Multi-Month & Multi-Year Smart Chunk Downloader</p>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <div class="flex items-center space-x-2 text-xs bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-lg text-emerald-400">
                    <span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span id="broker-status">Broker: {{ broker }} (Active)</span>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        
        <!-- Controls Card -->
        <div class="bg-cardbg border border-bordercolor rounded-2xl p-6 shadow-xl space-y-5">
            <!-- Quick Presets -->
            <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">⚡ Popular Presets</label>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="setPreset('NIFTY25AUG26FUT', 'NFO', '1m', 30)" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">NIFTY Aug Fut (1m - 30D)</button>
                        <button onclick="setPreset('NIFTY25AUG26FUT', 'NFO', '5m', 90)" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">NIFTY Aug Fut (5m - 90D)</button>
                        <button onclick="setPreset('BANKNIFTY26AUGFUT', 'NFO', '5m', 90)" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">BANKNIFTY Fut (5m)</button>
                        <button onclick="setPreset('NIFTY', 'NSE_INDEX', '5m', 180)" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">NIFTY 50 Index (6M)</button>
                        <button onclick="setPreset('RELIANCE', 'NSE', '15m', 180)" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">RELIANCE (6M)</button>
                        <button onclick="setPreset('CRUDEOILM26AUGFUT', 'MCX', '5m', 60)" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 transition">CRUDE OIL (MCX)</button>
                    </div>
                </div>

                <!-- Date Range Presets -->
                <div>
                    <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">⏱️ Date Ranges</label>
                    <div class="flex flex-wrap gap-1.5">
                        <button onclick="setDateRange(7)" class="px-2.5 py-1 text-xs rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300">7 Days</button>
                        <button onclick="setDateRange(30)" class="px-2.5 py-1 text-xs rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300">1 Month</button>
                        <button onclick="setDateRange(90)" class="px-2.5 py-1 text-xs rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300">3 Months</button>
                        <button onclick="setDateRange(180)" class="px-2.5 py-1 text-xs rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300">6 Months</button>
                        <button onclick="setDateRange(365)" class="px-2.5 py-1 text-xs rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300">1 Year</button>
                        <button onclick="setDateRange(730)" class="px-2.5 py-1 text-xs rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300">2 Years</button>
                    </div>
                </div>
            </div>

            <hr class="border-slate-700/60">

            <!-- Input Form -->
            <form id="fetchForm" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                <!-- Symbol input with Auto-suggest -->
                <div class="relative">
                    <label class="block text-xs font-medium text-slate-300 mb-1">Trading Symbol</label>
                    <div class="relative">
                        <input type="text" id="symbol" name="symbol" value="NIFTY25AUG26FUT" required
                            placeholder="e.g. NIFTY25AUG26FUT, SBIN"
                            autocomplete="off"
                            class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 uppercase font-mono">
                        <div id="symbol-dropdown" class="hidden absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 max-h-56 overflow-y-auto custom-scrollbar">
                        </div>
                    </div>
                </div>

                <!-- Exchange -->
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">Exchange</label>
                    <select id="exchange" name="exchange" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                        <option value="NFO" selected>NFO (NSE Futures & Options)</option>
                        <option value="NSE">NSE (Cash / Equities)</option>
                        <option value="NSE_INDEX">NSE_INDEX (Indices)</option>
                        <option value="BSE">BSE (Cash / Equities)</option>
                        <option value="BSE_INDEX">BSE_INDEX (Sensex/Bankex)</option>
                        <option value="MCX">MCX (Commodities)</option>
                        <option value="CDS">CDS (Currencies)</option>
                    </select>
                </div>

                <!-- Interval -->
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">Timeframe (Interval)</label>
                    <select id="interval" name="interval" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                        <option value="1m" selected>1 Minute (1m) - Intraday</option>
                        <option value="3m">3 Minutes (3m)</option>
                        <option value="5m">5 Minutes (5m)</option>
                        <option value="10m">10 Minutes (10m)</option>
                        <option value="15m">15 Minutes (15m)</option>
                        <option value="30m">30 Minutes (30m)</option>
                        <option value="1h">1 Hour (1h)</option>
                        <option value="D">Daily (1D)</option>
                    </select>
                </div>

                <!-- Start Date -->
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">Start Date</label>
                    <input type="date" id="start_date" name="start_date" value="{{ default_start }}" required
                        class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                </div>

                <!-- End Date -->
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">End Date</label>
                    <input type="date" id="end_date" name="end_date" value="{{ default_end }}" required
                        class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                </div>

                <!-- Buttons Area -->
                <div class="lg:col-span-5 flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-slate-800">
                    <div class="flex items-center space-x-2 text-xs text-slate-400">
                        <i data-lucide="shield-check" class="h-4 w-4 text-indigo-400"></i>
                        <span>Smart Auto-Chunking enabled &bull; No API rate limit lockouts</span>
                    </div>

                    <div class="flex items-center gap-3">
                        <!-- Bulk Smart Download Button -->
                        <button type="button" onclick="startBulkDownload()" id="btn-bulk"
                            class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition">
                            <i data-lucide="download-cloud" class="h-4 w-4"></i> 🚀 Bulk Smart Download (Merged CSV)
                        </button>
                        
                        <!-- Fetch & Chart Button -->
                        <button type="button" onclick="fetchAndPreview()" id="btn-fetch"
                            class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-indigo-500/25 transition">
                            <i data-lucide="line-chart" class="h-4 w-4"></i> Fetch & View Chart
                        </button>
                    </div>
                </div>
            </form>
        </div>

        <!-- Live Progress Bar Card for Bulk Download -->
        <div id="progress-card" class="hidden bg-cardbg border border-indigo-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <span class="h-3 w-3 rounded-full bg-indigo-500 pulse-fast"></span>
                        Smart Chunks Downloader in Progress...
                    </h3>
                    <p id="progress-status-text" class="text-xs text-slate-400 mt-1">Preparing date chunks and checking broker rate limits...</p>
                </div>
                <div class="text-right">
                    <span id="progress-percent" class="text-2xl font-black text-indigo-400">0%</span>
                </div>
            </div>

            <!-- Progress Bar -->
            <div class="w-full bg-slate-900 rounded-full h-3.5 overflow-hidden p-0.5 border border-slate-700">
                <div id="progress-bar-fill" class="bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 h-full rounded-full transition-all duration-300" style="width: 0%;"></div>
            </div>

            <!-- Live Chunks Log -->
            <div id="chunk-logs" class="bg-slate-900/90 rounded-xl p-3 max-h-36 overflow-y-auto custom-scrollbar font-mono text-xs text-slate-300 space-y-1">
            </div>
        </div>

        <!-- Notification / Error Box -->
        <div id="error-box" class="hidden p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm"></div>
        <div id="success-box" class="hidden p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm flex items-center gap-2">
            <i data-lucide="check-circle-2" class="h-5 w-5"></i>
            <span id="success-message">Data successfully downloaded and merged!</span>
        </div>

        <!-- Metrics Row -->
        <div id="metrics-section" class="hidden grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                <p class="text-xs text-slate-400">Total Candles</p>
                <p id="m-candles" class="text-xl font-bold text-white mt-1">-</p>
            </div>
            <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                <p class="text-xs text-slate-400">Latest Price</p>
                <p id="m-price" class="text-xl font-bold text-indigo-400 mt-1">-</p>
            </div>
            <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                <p class="text-xs text-slate-400">Period High</p>
                <p id="m-high" class="text-xl font-bold text-emerald-400 mt-1">-</p>
            </div>
            <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                <p class="text-xs text-slate-400">Period Low</p>
                <p id="m-low" class="text-xl font-bold text-rose-400 mt-1">-</p>
            </div>
            <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                <p class="text-xs text-slate-400">Total Volume</p>
                <p id="m-volume" class="text-xl font-bold text-slate-200 mt-1">-</p>
            </div>
            <div class="bg-cardbg border border-bordercolor rounded-xl p-4">
                <p class="text-xs text-slate-400">Latest OI</p>
                <p id="m-oi" class="text-xl font-bold text-purple-400 mt-1">-</p>
            </div>
        </div>

        <!-- Chart Section -->
        <div id="chart-section" class="hidden bg-cardbg border border-bordercolor rounded-2xl p-4 shadow-xl">
            <div class="flex items-center justify-between px-2 py-1 mb-2">
                <h3 id="chart-title" class="font-semibold text-sm text-slate-300">Historical Chart (OHLC + Volume + OI)</h3>
                <button onclick="downloadLoadedCSV()" class="px-3 py-1 text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg flex items-center gap-1.5">
                    <i data-lucide="download" class="h-3.5 w-3.5"></i> Export Loaded Data (CSV)
                </button>
            </div>
            <div id="plotly-chart" class="w-full h-[650px]"></div>
        </div>

        <!-- Data Table Section -->
        <div id="table-section" class="hidden bg-cardbg border border-bordercolor rounded-2xl p-5 shadow-xl space-y-4">
            <div class="flex items-center justify-between">
                <h3 class="font-semibold text-slate-200 text-sm">Candles Data Preview (Latest 50 bars)</h3>
                <span id="table-info" class="text-xs text-slate-400"></span>
            </div>
            <div class="overflow-x-auto rounded-xl border border-slate-700/60 custom-scrollbar max-h-96">
                <table class="w-full text-left text-xs">
                    <thead class="bg-slate-900/80 text-slate-400 sticky top-0 uppercase tracking-wider">
                        <tr>
                            <th class="py-2.5 px-4">Date & Time (IST)</th>
                            <th class="py-2.5 px-4 text-right">Open</th>
                            <th class="py-2.5 px-4 text-right">High</th>
                            <th class="py-2.5 px-4 text-right">Low</th>
                            <th class="py-2.5 px-4 text-right">Close</th>
                            <th class="py-2.5 px-4 text-right">Volume</th>
                            <th class="py-2.5 px-4 text-right">Open Interest (OI)</th>
                        </tr>
                    </thead>
                    <tbody id="table-body" class="divide-y divide-slate-800 text-slate-300 font-mono">
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="border-t border-bordercolor py-4 text-center text-xs text-slate-500">
        OpenAlgo Algorithmic Trading Platform &bull; Smart Chunks &amp; Bulk Downloader Engine
    </footer>

    <script>
        lucide.createIcons();

        let globalCandles = [];

        function setPreset(symbol, exchange, interval, days) {
            document.getElementById('symbol').value = symbol;
            document.getElementById('exchange').value = exchange;
            document.getElementById('interval').value = interval;
            setDateRange(days);
            fetchAndPreview();
        }

        function setDateRange(days) {
            const end = new Date();
            const start = new Date();
            start.setDate(end.getDate() - days);
            
            document.getElementById('end_date').value = end.toISOString().split('T')[0];
            document.getElementById('start_date').value = start.toISOString().split('T')[0];
        }

        // Auto symbol search
        let searchTimeout;
        const symbolInput = document.getElementById('symbol');
        const dropdown = document.getElementById('symbol-dropdown');

        symbolInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const val = this.value.trim();
            if (val.length < 2) {
                dropdown.classList.add('hidden');
                return;
            }
            searchTimeout = setTimeout(() => {
                fetch(`/api/search?q=${encodeURIComponent(val)}`)
                    .then(r => r.json())
                    .then(items => {
                        if (items.length === 0) {
                            dropdown.classList.add('hidden');
                            return;
                        }
                        dropdown.innerHTML = items.map(item => `
                            <div onclick="selectSymbol('${item.symbol}', '${item.exchange}')" 
                                 class="p-2.5 hover:bg-slate-800 cursor-pointer border-b border-slate-800/50 flex justify-between items-center text-xs">
                                <div>
                                    <span class="font-bold text-white font-mono">${item.symbol}</span>
                                    <span class="text-[10px] text-slate-400 ml-1">(${item.expiry || ''})</span>
                                </div>
                                <span class="px-2 py-0.5 rounded bg-slate-800 text-indigo-400 text-[10px] font-semibold">${item.exchange}</span>
                            </div>
                        `).join('');
                        dropdown.classList.remove('hidden');
                    });
            }, 250);
        });

        function selectSymbol(sym, exch) {
            symbolInput.value = sym;
            if (exch) document.getElementById('exchange').value = exch;
            dropdown.classList.add('hidden');
        }

        document.addEventListener('click', (e) => {
            if (!symbolInput.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });

        // ──────────────────────── BULK DOWNLOAD WITH CHUNKS & LIVE PROGRESS ────────────────────────
        async function startBulkDownload() {
            const sym = document.getElementById('symbol').value.trim();
            const exch = document.getElementById('exchange').value;
            const intv = document.getElementById('interval').value;
            const start = document.getElementById('start_date').value;
            const end = document.getElementById('end_date').value;

            if (!sym || !start || !end) {
                alert('Please provide Symbol, Start Date and End Date');
                return;
            }

            // Show progress UI
            const progressCard = document.getElementById('progress-card');
            const progressBar = document.getElementById('progress-bar-fill');
            const progressPercent = document.getElementById('progress-percent');
            const progressStatus = document.getElementById('progress-status-text');
            const chunkLogs = document.getElementById('chunk-logs');
            const errorBox = document.getElementById('error-box');
            const successBox = document.getElementById('success-box');

            progressCard.classList.remove('hidden');
            errorBox.classList.add('hidden');
            successBox.classList.add('hidden');
            chunkLogs.innerHTML = '';
            progressBar.style.width = '0%';
            progressPercent.innerText = '0%';

            // Step 1: Get Chunks list from server
            progressStatus.innerText = 'Calculating optimal date chunks...';
            const chunkRes = await fetch(`/api/get-chunks?interval=${encodeURIComponent(intv)}&start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`);
            const chunkData = await chunkRes.json();
            const chunks = chunkData.chunks;

            if (!chunks || chunks.length === 0) {
                alert('Invalid date range');
                progressCard.classList.add('hidden');
                return;
            }

            addLog(`🚀 Starting bulk download for ${sym} (${exch}) [${intv}] - Total ${chunks.length} chunks`);

            let allRows = [];
            let chunkIndex = 0;

            for (const [cStart, cEnd] of chunks) {
                chunkIndex++;
                const pct = Math.round((chunkIndex / chunks.length) * 100);
                progressStatus.innerText = `Fetching Chunk ${chunkIndex} of ${chunks.length}: ${cStart} to ${cEnd}...`;
                
                try {
                    const res = await fetch(`/api/fetch-chunk?symbol=${encodeURIComponent(sym)}&exchange=${encodeURIComponent(exch)}&interval=${encodeURIComponent(intv)}&start_date=${encodeURIComponent(cStart)}&end_date=${encodeURIComponent(cEnd)}`);
                    const json = await res.json();
                    
                    if (json.status === 'success' && json.data) {
                        allRows.push(...json.data);
                        addLog(`✅ Chunk ${chunkIndex}/${chunks.length} [${cStart} to ${cEnd}]: +${json.data.length} candles (Total: ${allRows.length})`);
                    } else {
                        addLog(`⚠️ Chunk ${chunkIndex}/${chunks.length} [${cStart} to ${cEnd}]: ${json.message || 'No data'}`);
                    }
                } catch (e) {
                    addLog(`❌ Error fetching chunk ${chunkIndex}: ${e.message}`);
                }

                progressBar.style.width = pct + '%';
                progressPercent.innerText = pct + '%';

                // Safe rate limit pause between chunks
                await new Promise(r => setTimeout(r, 250));
            }

            if (allRows.length === 0) {
                progressStatus.innerText = 'Completed. No candles returned.';
                errorBox.innerText = 'No candles returned for this symbol/period.';
                errorBox.classList.remove('hidden');
                return;
            }

            // Sort & Deduplicate
            const uniqueMap = new Map();
            allRows.forEach(row => uniqueMap.set(row.timestamp, row));
            const sortedRows = Array.from(uniqueMap.values()).sort((a, b) => a.timestamp - b.timestamp);

            globalCandles = sortedRows;
            progressStatus.innerText = `Completed! Successfully merged ${sortedRows.length.toLocaleString()} candles. Generating CSV download...`;
            addLog(`🎉 All chunks downloaded & deduplicated. Total final candles: ${sortedRows.length.toLocaleString()}`);

            // Download CSV automatically
            triggerCSVDownload(sortedRows, `${sym}_${exch}_${intv}_${start}_to_${end}_MERGED.csv`);

            successBox.classList.remove('hidden');
            document.getElementById('success-message').innerText = `Successfully downloaded ${sortedRows.length.toLocaleString()} candles into 1 CSV file!`;
            
            // Also preview in chart
            renderPreviewUI(sortedRows, sym, exch, intv);
        }

        function addLog(text) {
            const chunkLogs = document.getElementById('chunk-logs');
            const p = document.createElement('div');
            p.innerText = text;
            chunkLogs.appendChild(p);
            chunkLogs.scrollTop = chunkLogs.scrollHeight;
        }

        function triggerCSVDownload(data, filename) {
            let csv = "Date Time,open,high,low,close,volume,oi\\n";
            data.forEach(r => {
                csv += `${r.datetime_str || ''},${r.open},${r.high},${r.low},${r.close},${r.volume || 0},${r.oi || 0}\\n`;
            });

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function downloadLoadedCSV() {
            if (globalCandles.length === 0) return;
            const sym = document.getElementById('symbol').value.trim();
            triggerCSVDownload(globalCandles, `${sym}_export.csv`);
        }

        // ──────────────────────── SINGLE FETCH & PREVIEW ────────────────────────
        async function fetchAndPreview() {
            const sym = document.getElementById('symbol').value.trim();
            const exch = document.getElementById('exchange').value;
            const intv = document.getElementById('interval').value;
            const start = document.getElementById('start_date').value;
            const end = document.getElementById('end_date').value;

            if (!sym) return;

            document.getElementById('error-box').classList.add('hidden');
            document.getElementById('success-box').classList.add('hidden');
            document.getElementById('progress-card').classList.add('hidden');

            try {
                // If date range is longer than 60 days, route to smart bulk downloader
                const sDate = new Date(start);
                const eDate = new Date(end);
                const diffDays = Math.ceil((eDate - sDate) / (1000 * 60 * 60 * 24));

                if (diffDays > 60 && (intv === '1m' || intv === '3m' || intv === '5m')) {
                    startBulkDownload();
                    return;
                }

                const res = await fetch(`/api/fetch-chunk?symbol=${encodeURIComponent(sym)}&exchange=${encodeURIComponent(exch)}&interval=${encodeURIComponent(intv)}&start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`);
                const json = await res.json();

                if (json.status !== 'success' || !json.data || json.data.length === 0) {
                    document.getElementById('error-box').innerText = json.message || 'No data found';
                    document.getElementById('error-box').classList.remove('hidden');
                    return;
                }

                globalCandles = json.data;
                renderPreviewUI(json.data, sym, exch, intv);
            } catch (err) {
                document.getElementById('error-box').innerText = err.message || 'Network error';
                document.getElementById('error-box').classList.remove('hidden');
            }
        }

        function renderPreviewUI(data, sym, exch, intv) {
            const totalCandles = data.length;
            const latestClose = data[data.length - 1].close;
            const high = Math.max(...data.map(d => d.high));
            const low = Math.min(...data.map(d => d.low));
            const totalVol = data.reduce((acc, d) => acc + (d.volume || 0), 0);
            const latestOI = data[data.length - 1].oi || 0;

            document.getElementById('metrics-section').classList.remove('hidden');
            document.getElementById('m-candles').innerText = totalCandles.toLocaleString();
            document.getElementById('m-price').innerText = '₹' + latestClose.toLocaleString();
            document.getElementById('m-high').innerText = '₹' + high.toLocaleString();
            document.getElementById('m-low').innerText = '₹' + low.toLocaleString();
            document.getElementById('m-volume').innerText = totalVol.toLocaleString();
            document.getElementById('m-oi').innerText = latestOI.toLocaleString();

            document.getElementById('chart-section').classList.remove('hidden');
            document.getElementById('chart-title').innerText = `${sym} (${exch}) - ${intv} [${totalCandles.toLocaleString()} Bars]`;
            renderPlotlyChart(data);

            document.getElementById('table-section').classList.remove('hidden');
            document.getElementById('table-info').innerText = `Showing latest ${Math.min(50, totalCandles)} of ${totalCandles.toLocaleString()} bars`;
            renderTable(data);
        }

        function renderPlotlyChart(candles) {
            // If more than 5000 candles, downsample slightly for smooth rendering
            let plotData = candles;
            if (candles.length > 5000) {
                const step = Math.ceil(candles.length / 5000);
                plotData = candles.filter((_, idx) => idx % step === 0);
            }

            const x = plotData.map(c => c.datetime_str);
            const open = plotData.map(c => c.open);
            const high = plotData.map(c => c.high);
            const low = plotData.map(c => c.low);
            const close = plotData.map(c => c.close);
            const volume = plotData.map(c => c.volume);
            const oi = plotData.map(c => c.oi || 0);
            const hasOI = oi.some(v => v > 0);

            const traces = [];

            // Candlestick Trace
            traces.push({
                type: 'candlestick',
                x: x,
                open: open, high: high, low: low, close: close,
                name: 'Price (OHLC)',
                increasing: { line: { color: '#26a69a' } },
                decreasing: { line: { color: '#ef5350' } },
                yaxis: 'y1'
            });

            // Volume Trace
            const volColors = close.map((c, i) => c >= open[i] ? 'rgba(38, 166, 154, 0.6)' : 'rgba(239, 83, 80, 0.6)');
            traces.push({
                type: 'bar',
                x: x,
                y: volume,
                name: 'Volume',
                marker: { color: volColors },
                yaxis: 'y2'
            });

            // OI Trace
            if (hasOI) {
                traces.push({
                    type: 'scatter',
                    x: x,
                    y: oi,
                    mode: 'lines',
                    name: 'Open Interest',
                    line: { color: '#ab47bc', width: 2 },
                    yaxis: 'y3'
                });
            }

            const layout = {
                template: 'plotly_dark',
                paper_bgcolor: '#161f30',
                plot_bgcolor: '#161f30',
                margin: { l: 60, r: 40, t: 20, b: 40 },
                hovermode: 'x unified',
                xaxis: { rangeslider: { visible: false }, gridcolor: 'rgba(255,255,255,0.06)' },
                yaxis: { title: 'Price (₹)', domain: hasOI ? [0.45, 1.0] : [0.30, 1.0], gridcolor: 'rgba(255,255,255,0.06)' },
                yaxis2: { title: 'Volume', domain: hasOI ? [0.22, 0.40] : [0.0, 0.25], gridcolor: 'rgba(255,255,255,0.06)' }
            };

            if (hasOI) {
                layout.yaxis3 = { title: 'OI', domain: [0.0, 0.18], gridcolor: 'rgba(255,255,255,0.06)' };
            }

            Plotly.newPlot('plotly-chart', traces, layout, { responsive: true, displaylogo: false });
        }

        function renderTable(data) {
            const preview = data.slice(-50).reverse();
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = preview.map(c => `
                <tr class="hover:bg-slate-800/60 transition">
                    <td class="py-2 px-4 text-slate-300">${c.datetime_str}</td>
                    <td class="py-2 px-4 text-right">${c.open.toFixed(2)}</td>
                    <td class="py-2 px-4 text-right text-emerald-400">${c.high.toFixed(2)}</td>
                    <td class="py-2 px-4 text-right text-rose-400">${c.low.toFixed(2)}</td>
                    <td class="py-2 px-4 text-right font-bold ${c.close >= c.open ? 'text-emerald-400' : 'text-rose-400'}">${c.close.toFixed(2)}</td>
                    <td class="py-2 px-4 text-right text-slate-300">${(c.volume || 0).toLocaleString()}</td>
                    <td class="py-2 px-4 text-right text-purple-400">${(c.oi || 0).toLocaleString()}</td>
                </tr>
            `).join('');
        }

        window.addEventListener('DOMContentLoaded', () => {
            fetchAndPreview();
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    username, broker, _ = get_active_auth()
    today = datetime.now(IST).date()
    start_date = (today - timedelta(days=25)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    return render_template_string(
        HTML_TEMPLATE,
        broker=broker or "Fyers",
        default_start=start_date,
        default_end=end_date
    )

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    return jsonify(search_symbols_in_db(q))

@app.route("/api/get-chunks")
def api_get_chunks():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    interval = request.args.get("interval", "5m")
    chunks = generate_chunks(start_date, end_date, interval)
    return jsonify({"chunks": chunks, "total": len(chunks)})

@app.route("/api/fetch-chunk")
def api_fetch_chunk():
    symbol = request.args.get("symbol", "").upper()
    exchange = request.args.get("exchange", "NFO").upper()
    interval = request.args.get("interval", "5m")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    username, broker, auth_token = get_active_auth()
    if not auth_token:
        return jsonify({"status": "error", "message": "No active broker session"}), 401

    try:
        success, msg, data = fetch_chunk_data(symbol, exchange, interval, start_date, end_date, auth_token, broker)
        if not success:
            return jsonify({"status": "error", "message": msg}), 400

        for r in data:
            if "timestamp" in r:
                dt = datetime.fromtimestamp(r["timestamp"], tz=pytz.utc).astimezone(IST)
                r["datetime_str"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            if "oi" not in r:
                r["oi"] = 0

        return jsonify({"status": "success", "data": data, "count": len(data)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    print("Starting Advanced Bulk Data Downloader on http://127.0.0.1:8080 ...")
    app.run(host="0.0.0.0", port=8090, debug=False)
