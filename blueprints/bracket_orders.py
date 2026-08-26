"""
TradingView-Style Position & Bracket SL/TP Blueprint for OpenAlgo
Direct Native Endpoint: http://127.0.0.1:5000/bracket
"""

from flask import Blueprint, render_template_string, request, jsonify, session
from database.auth_db import get_auth_token, get_api_key_for_tradingview
from database.settings_db import get_analyze_mode
from database.bracket_db import get_active_brackets, save_or_update_bracket, update_bracket_status
from services.bracket_service import BracketManager
from services.positionbook_service import get_positionbook
from utils.session import check_session_validity
from utils.logging import get_logger

logger = get_logger(__name__)

bracket_orders_bp = Blueprint("bracket_orders_bp", __name__, url_prefix="/")

BRACKET_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenAlgo - TradingView Position & Bracket SL/TP Controller</title>
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
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        body { background-color: #0b0f19; color: #f1f5f9; font-family: system-ui, -apple-system, sans-serif; }
    </style>
</head>
<body class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="border-b border-bordercolor bg-cardbg/90 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-500 flex items-center justify-center font-bold text-xl text-white shadow-lg shadow-emerald-500/25">
                    🛡️
                </div>
                <div>
                    <h1 class="text-xl font-bold text-white flex items-center gap-2">
                        OpenAlgo <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">TradingView Bracket SL/TP Manager</span>
                    </h1>
                    <p class="text-xs text-slate-400">Live Positions &bull; OCO Bracket Orders &bull; Trailing Stoploss Protection</p>
                </div>
            </div>
            
            <div class="flex items-center space-x-3">
                <a href="/dashboard" class="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">
                    &larr; Back to OpenAlgo Dashboard
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        
        <!-- Header Actions -->
        <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
                <h2 class="text-lg font-bold text-white">Active Open Positions & Live Protection</h2>
                <p class="text-xs text-slate-400">Set exact Stop Loss and Target prices or percentages with automated One-Cancels-Other (OCO) execution.</p>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="openCustomModal()" class="px-3.5 py-2 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5 shadow-lg shadow-emerald-600/20 transition">
                    <i data-lucide="plus-circle" class="h-4 w-4"></i> Custom Protection
                </button>
                <button onclick="loadPositions()" class="px-3.5 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                    <i data-lucide="refresh-cw" class="h-4 w-4"></i> Refresh
                </button>
            </div>
        </div>

        <!-- Active Brackets Monitoring Banner -->
        <div id="active-brackets-banner" class="hidden space-y-3">
            <h3 class="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <span class="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Active OCO Protected Positions
            </h3>
            <div id="active-brackets-list" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"></div>
        </div>

        <!-- Positions List Container -->
        <div id="positions-container" class="space-y-4">
            <div class="text-center py-12 text-slate-500">Loading positions...</div>
        </div>

    </main>

    <!-- Custom Modal -->
    <div id="custom-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="text-base font-bold text-white flex items-center gap-2">
                    <span>🛡️</span> Set Custom Bracket Protection
                </h3>
                <button onclick="closeCustomModal()" class="text-slate-400 hover:text-white">&times;</button>
            </div>
            <div class="space-y-3 text-xs">
                <div>
                    <label class="block text-slate-300 font-semibold mb-1">Symbol (e.g. NIFTY26AUGFUT, CRUDEOIL21SEPFUT)</label>
                    <input type="text" id="cust-symbol" placeholder="Symbol name" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono uppercase">
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-slate-300 font-semibold mb-1">Exchange</label>
                        <select id="cust-exch" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono">
                            <option value="NSE">NSE</option>
                            <option value="NFO" selected>NFO</option>
                            <option value="MCX">MCX</option>
                            <option value="BSE">BSE</option>
                            <option value="BFO">BFO</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-slate-300 font-semibold mb-1">Direction</label>
                        <select id="cust-pos" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono">
                            <option value="BUY">BUY (Long)</option>
                            <option value="SELL">SELL (Short)</option>
                        </select>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-slate-300 font-semibold mb-1">Quantity</label>
                        <input type="number" id="cust-qty" value="50" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono">
                    </div>
                    <div>
                        <label class="block text-slate-300 font-semibold mb-1">Entry Price (₹)</label>
                        <input type="number" step="0.05" id="cust-entry" placeholder="100.00" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-rose-400 font-semibold mb-1">🛡️ Stop Loss (₹)</label>
                        <input type="number" step="0.05" id="cust-sl" placeholder="90.00" class="w-full bg-slate-950 border border-rose-500/40 rounded-xl px-3 py-2 text-rose-300 font-mono">
                    </div>
                    <div>
                        <label class="block text-emerald-400 font-semibold mb-1">🎯 Target (₹)</label>
                        <input type="number" step="0.05" id="cust-tg" placeholder="120.00" class="w-full bg-slate-950 border border-emerald-500/40 rounded-xl px-3 py-2 text-emerald-300 font-mono">
                    </div>
                </div>
                <div class="p-3 bg-purple-950/30 rounded-xl border border-purple-500/30 flex items-center justify-between">
                    <label class="flex items-center gap-2 text-purple-300 cursor-pointer">
                        <input type="checkbox" id="cust-trail" class="rounded border-purple-500 text-purple-600">
                        <span>⚡ Trailing Stop Loss</span>
                    </label>
                    <input type="number" step="0.5" id="cust-step" value="5.0" placeholder="Step ₹" class="w-24 bg-slate-950 border border-purple-500/40 rounded-lg px-2 py-1 text-purple-300 font-mono text-xs">
                </div>
            </div>
            <div class="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button onclick="closeCustomModal()" class="px-4 py-2 rounded-xl text-slate-400 hover:text-white text-xs">Cancel</button>
                <button onclick="saveCustomBracket()" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs">Save Protection</button>
            </div>
        </div>
    </div>

    <footer class="border-t border-bordercolor py-4 text-center text-xs text-slate-500">
        OpenAlgo Native Position Bracket Manager &bull; Real-time OCO Protection Engine
    </footer>

    <script>
        lucide.createIcons();

        function openCustomModal() {
            document.getElementById('custom-modal').classList.remove('hidden');
        }
        function closeCustomModal() {
            document.getElementById('custom-modal').classList.add('hidden');
        }

        async function saveCustomBracket() {
            const symbol = document.getElementById('cust-symbol').value.trim().toUpperCase();
            const exchange = document.getElementById('cust-exch').value;
            const posType = document.getElementById('cust-pos').value;
            const qty = parseInt(document.getElementById('cust-qty').value) || 1;
            const entry = parseFloat(document.getElementById('cust-entry').value) || 0;
            const sl = parseFloat(document.getElementById('cust-sl').value);
            const tg = parseFloat(document.getElementById('cust-tg').value) || 0;
            const trail = document.getElementById('cust-trail').checked;
            const step = parseFloat(document.getElementById('cust-step').value) || 5.0;

            if (!symbol || !sl || sl <= 0) {
                alert("Please enter Symbol and valid Stop Loss price.");
                return;
            }

            const res = await fetch('/api/v1/bracket/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    exchange: exchange,
                    product: 'MIS',
                    position_type: posType,
                    quantity: qty,
                    entry_price: entry,
                    stoploss_price: sl,
                    target_price: tg,
                    trailing_sl: trail,
                    trailing_step: step
                })
            });
            const data = await res.json();
            if (data.status === 'success') {
                closeCustomModal();
                loadPositions();
            } else {
                alert(data.message || 'Failed to set bracket');
            }
        }

        async function loadPositions() {
            const container = document.getElementById('positions-container');
            const banner = document.getElementById('active-brackets-banner');
            const list = document.getElementById('active-brackets-list');
            container.innerHTML = '<div class="text-center py-12 text-slate-500"><div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-emerald-500 border-t-transparent"></div><p class="mt-2 text-xs">Fetching live positions & brackets...</p></div>';

            try {
                const res = await fetch('/api/v1/bracket/positions');
                const data = await res.json();
                const positions = data.positions || [];
                const activeBrackets = (data.brackets || []).filter(b => b.status === 'ACTIVE');

                if (activeBrackets.length > 0) {
                    banner.classList.remove('hidden');
                    list.innerHTML = activeBrackets.map(b => `
                        <div class="bg-cardbg border border-emerald-500/30 rounded-xl p-3 shadow-lg flex items-center justify-between text-xs">
                            <div>
                                <div class="font-bold text-white font-mono">${b.symbol}</div>
                                <div class="text-slate-400 font-mono text-[11px]">${b.position_type} (${b.quantity} Qty) &bull; ${b.exchange}</div>
                            </div>
                            <div class="text-right font-mono">
                                <div class="text-rose-400 font-semibold">SL: ₹${b.stoploss_price}</div>
                                <div class="text-emerald-400 font-semibold">TP: ₹${b.target_price || '-'}</div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    banner.classList.add('hidden');
                }

                if (positions.length === 0 && activeBrackets.length === 0) {
                    container.innerHTML = `
                        <div class="bg-cardbg border border-bordercolor rounded-2xl p-12 text-center space-y-3">
                            <div class="text-4xl">📭</div>
                            <h3 class="font-bold text-white text-base">No Open Positions Currently</h3>
                            <p class="text-xs text-slate-400 max-w-md mx-auto">Positions will appear automatically when you trade. You can also click <b>"Custom Protection"</b> above to set Stop Loss & Target on any contract anytime.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = positions.map(pos => {
                    const qty = parseInt(pos.quantity || 0);
                    const isClosed = qty === 0;
                    const isLong = qty > 0;
                    const posType = isLong ? 'BUY' : (qty < 0 ? 'SELL' : 'CLOSED');
                    const avgPrice = parseFloat(pos.average_price || pos.buy_price || pos.ltp || 0);
                    const ltp = parseFloat(pos.ltp || avgPrice);
                    const pnl = parseFloat(pos.pnl || pos.today_realized_pnl || 0);
                    
                    const existingBracket = activeBrackets.find(b => b.symbol.toUpperCase() === pos.symbol.toUpperCase() && b.status === 'ACTIVE');
                    
                    const defSl = existingBracket ? existingBracket.stoploss_price : (avgPrice > 0 ? (avgPrice * 0.99).toFixed(2) : (ltp * 0.99).toFixed(2));
                    const defTg = existingBracket ? existingBracket.target_price : (avgPrice > 0 ? (avgPrice * 1.02).toFixed(2) : (ltp * 1.02).toFixed(2));
                    const isTrailing = existingBracket ? existingBracket.trailing_sl : false;

                    return `
                        <div class="bg-cardbg border ${existingBracket ? 'border-emerald-500/40 ring-1 ring-emerald-500/20' : 'border-bordercolor'} rounded-2xl p-5 shadow-xl space-y-4">
                            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                                <div class="flex items-center space-x-3">
                                    <span class="px-2.5 py-1 rounded-lg text-xs font-bold ${isLong ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : (qty < 0 ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' : 'bg-slate-700/50 text-slate-400 border border-slate-600')}">
                                        ${posType} ${!isClosed ? `(${Math.abs(qty)} Qty)` : ''}
                                    </span>
                                    <h3 class="text-base font-bold text-white font-mono">${pos.symbol}</h3>
                                    <span class="text-xs text-slate-400 font-mono">${pos.exchange || 'NSE'} &bull; ${pos.product || 'MIS'}</span>
                                    ${existingBracket ? '<span class="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono border border-emerald-500/30">🛡️ OCO ACTIVE</span>' : ''}
                                </div>

                                <div class="flex items-center space-x-4 font-mono text-sm">
                                    <div>
                                        <span class="text-xs text-slate-400 block">Avg Price</span>
                                        <span class="text-white font-bold">₹${avgPrice.toFixed(2)}</span>
                                    </div>
                                    <div>
                                        <span class="text-xs text-slate-400 block">LTP</span>
                                        <span class="text-indigo-400 font-bold">₹${ltp.toFixed(2)}</span>
                                    </div>
                                    <div>
                                        <span class="text-xs text-slate-400 block">${isClosed ? 'Realized P&L' : 'Unrealized P&L'}</span>
                                        <span class="${pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}">
                                            ${pnl >= 0 ? '+₹' : '-₹'}${Math.abs(pnl).toFixed(2)}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <!-- Bracket Controls Form -->
                            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                                <div>
                                    <label class="block text-xs font-semibold text-rose-400 mb-1 flex items-center justify-between">
                                        <span>🛡️ Stop Loss Price (SL)</span>
                                        <span class="text-slate-500 text-[10px]" id="sl-pts-${pos.symbol}"></span>
                                    </label>
                                    <input type="number" step="0.05" id="sl-${pos.symbol}" value="${defSl}" 
                                        oninput="updatePts('${pos.symbol}', ${avgPrice || ltp}, ${isLong ? 1 : -1})"
                                        class="w-full bg-slate-900 border border-rose-500/40 rounded-xl px-3 py-2 text-sm text-rose-300 font-mono focus:ring-1 focus:ring-rose-500 focus:outline-none">
                                </div>

                                <div>
                                    <label class="block text-xs font-semibold text-emerald-400 mb-1 flex items-center justify-between">
                                        <span>🎯 Target Price (TP)</span>
                                        <span class="text-slate-500 text-[10px]" id="tg-pts-${pos.symbol}"></span>
                                    </label>
                                    <input type="number" step="0.05" id="tg-${pos.symbol}" value="${defTg}"
                                        oninput="updatePts('${pos.symbol}', ${avgPrice || ltp}, ${isLong ? 1 : -1})"
                                        class="w-full bg-slate-900 border border-emerald-500/40 rounded-xl px-3 py-2 text-sm text-emerald-300 font-mono focus:ring-1 focus:ring-emerald-500 focus:outline-none">
                                </div>

                                <div>
                                    <label class="block text-xs font-semibold text-purple-400 mb-1">
                                        ⚡ Trailing SL (Trail Step ₹)
                                    </label>
                                    <div class="flex items-center space-x-2">
                                        <input type="checkbox" id="trail-chk-${pos.symbol}" ${isTrailing ? 'checked' : ''} class="rounded border-slate-700 text-purple-600 focus:ring-0">
                                        <input type="number" step="0.5" id="trail-step-${pos.symbol}" value="5.0" placeholder="Step ₹"
                                            class="w-full bg-slate-900 border border-purple-500/40 rounded-xl px-3 py-2 text-sm text-purple-300 font-mono">
                                    </div>
                                </div>

                                <div class="flex items-center space-x-2">
                                    <button onclick="setBracket('${pos.symbol}', '${pos.exchange || 'NSE'}', '${pos.product || 'MIS'}', '${isLong ? 'BUY' : 'SELL'}', ${Math.abs(qty) || 1}, ${avgPrice || ltp})"
                                        class="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:opacity-90 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-emerald-500/20 transition">
                                        <i data-lucide="shield-check" class="h-4 w-4"></i> ${existingBracket ? 'Update Bracket' : 'Set Protection'}
                                    </button>
                                    ${!isClosed ? `
                                    <button onclick="closePositionDirect('${pos.symbol}', '${pos.exchange || 'NSE'}', '${pos.product || 'MIS'}')"
                                        class="px-3 py-2.5 rounded-xl bg-rose-600/30 hover:bg-rose-600 text-rose-200 border border-rose-500/40 font-semibold text-xs whitespace-nowrap">
                                        Close Market
                                    </button>` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');

                lucide.createIcons();

            } catch (err) {
                container.innerHTML = `<div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">Error loading positions: ${err.message}</div>`;
            }
        }

        function updatePts(symbol, entryPrice, direction) {
            const sl = parseFloat(document.getElementById(`sl-${symbol}`).value);
            const tg = parseFloat(document.getElementById(`tg-${symbol}`).value);
            
            if (sl > 0) {
                const slDiff = Math.abs(entryPrice - sl).toFixed(2);
                const slPct = ((slDiff / entryPrice) * 100).toFixed(1);
                document.getElementById(`sl-pts-${symbol}`).innerText = `-${slDiff} pts (-${slPct}%)`;
            }
            if (tg > 0) {
                const tgDiff = Math.abs(tg - entryPrice).toFixed(2);
                const tgPct = ((tgDiff / entryPrice) * 100).toFixed(1);
                document.getElementById(`tg-pts-${symbol}`).innerText = `+${tgDiff} pts (+${tgPct}%)`;
            }
        }

        async function setBracket(symbol, exchange, product, posType, quantity, entryPrice) {
            const sl = parseFloat(document.getElementById(`sl-${symbol}`).value);
            const tg = parseFloat(document.getElementById(`tg-${symbol}`).value);
            const trailing = document.getElementById(`trail-chk-${symbol}`).checked;
            const trailStep = parseFloat(document.getElementById(`trail-step-${symbol}`).value);

            if (!sl || sl <= 0) {
                alert("Please enter a valid Stop Loss price.");
                return;
            }

            const res = await fetch('/api/v1/bracket/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    exchange: exchange,
                    product: product,
                    position_type: posType,
                    quantity: quantity,
                    entry_price: entryPrice,
                    stoploss_price: sl,
                    target_price: tg,
                    trailing_sl: trailing,
                    trailing_step: trailStep
                })
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert(`🛡️ TradingView-Style Bracket Protection Activated for ${symbol}!\\n\\nSL: ₹${sl}\\nTarget: ₹${tg}\\nOCO Monitoring: Active`);
                loadPositions();
            } else {
                alert(`Error: ${data.message}`);
            }
        }

        async function closePositionDirect(symbol, exchange, product) {
            if (!confirm(`Are you sure you want to close position in ${symbol} at Market Price?`)) return;
            const res = await fetch('/close_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: symbol, exchange: exchange, product: product })
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert(`Position in ${symbol} closed.`);
                loadPositions();
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            loadPositions();
        });
    </script>
</body>
</html>
"""

bracket_orders_bp = Blueprint("bracket_orders_bp", __name__, url_prefix="/")

@bracket_orders_bp.route("/bracket-orders")
@bracket_orders_bp.route("/bracket")
def bracket_dashboard():
    return render_template_string(BRACKET_HTML_TEMPLATE)

@bracket_orders_bp.route("/api/v1/bracket/positions", methods=["GET"])
def api_get_bracket_positions():
    try:
        import sqlite3
        login_username = session.get("user")
        if not login_username:
            con = sqlite3.connect("db/openalgo.db")
            row = con.cursor().execute("SELECT name, broker FROM auth WHERE is_revoked=0 LIMIT 1").fetchone()
            con.close()
            if row:
                login_username, broker = row
            else:
                login_username, broker = "sahilkhan", "fyers"
        else:
            broker = session.get("broker", "fyers")

        auth_token = get_auth_token(login_username)
        positions = []
        
        if get_analyze_mode():
            api_key = get_api_key_for_tradingview(login_username)
            if api_key:
                success, response, _ = get_positionbook(api_key=api_key)
                if success:
                    positions = response.get("data", [])
        else:
            if auth_token and broker:
                success, response, _ = get_positionbook(auth_token=auth_token, broker=broker)
                if success:
                    positions = response.get("data", [])
                    
        active_brackets = get_active_brackets()
        return jsonify({"status": "success", "positions": positions, "brackets": active_brackets})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bracket_orders_bp.route("/api/v1/bracket/set", methods=["POST"])
def api_set_bracket():
    try:
        data = request.json or {}
        bracket_id = save_or_update_bracket(data)
        logger.info(f"[BRACKET SET] Created bracket #{bracket_id} for {data.get('symbol')}")
        return jsonify({"status": "success", "bracket_id": bracket_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
