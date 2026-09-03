import pandas as pd
import streamlit as st
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.test import GOOG

# ══════════════════════════════════════════════════════════════════════════════
# ⚡ QUICK QUANT BACKTESTER (Streamlit + Backtesting.py)
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Quick Quant Backtester", page_icon="⚡", layout="wide")
st.title("⚡ Quick Quant Backtester")

# Sidebar Controls
st.sidebar.header("📊 Parameters")
fast_ma = st.sidebar.slider("Fast MA Length", 5, 50, 10)
slow_ma = st.sidebar.slider("Slow MA Length", 20, 200, 50)
initial_cash = st.sidebar.number_input("Initial Capital", min_value=10000, max_value=10000000, value=100000, step=10000)
commission = st.sidebar.number_input("Commission (%)", min_value=0.0, max_value=2.0, value=0.001, step=0.0005, format="%.4f")

# Define SMA Calculation Function
def get_sma(series, n):
    return pd.Series(series).rolling(n).mean()

# Strategy Definition
class SmaCross(Strategy):
    n1 = 10
    n2 = 50
    
    def init(self):
        self.fast = self.I(get_sma, self.data.Close, self.n1)
        self.slow = self.I(get_sma, self.data.Close, self.n2)

    def next(self):
        if self.fast[-1] > self.slow[-1]:
            if not self.position:
                self.buy()
        elif self.fast[-1] < self.slow[-1]:
            if self.position:
                self.position.close()

# Pass dynamic slider parameters to Strategy class
SmaCross.n1 = fast_ma
SmaCross.n2 = slow_ma

# Run Backtest
bt = Backtest(GOOG, SmaCross, cash=initial_cash, commission=commission, exclusive_orders=True)
stats = bt.run()

# Metrics Display Layout
col1, col2, col3, col4 = st.columns(4)
col1.metric("Return (%)", f"{stats['Return [%]']:.2f}%")
col2.metric("Win Rate (%)", f"{stats['Win Rate [%]']:.2f}%" if not np.isnan(stats['Win Rate [%]']) else "0.0%")
col3.metric("Profit Factor", f"{stats['Profit Factor']:.2f}" if not np.isnan(stats['Profit Factor']) else "0.0")
col4.metric("Max Drawdown (%)", f"{stats['Max. Drawdown [%]']:.2f}%")

st.divider()

# Tab Layout for Detailed Stats & Chart
tab1, tab2 = st.tabs(["📊 Interactive Bokeh Chart", "📋 Complete Performance Stats"])

with tab1:
    st.subheader("Strategy Equity Curve & Trade Signals")
    # Streamlit Bokeh renderer
    fig = bt.plot(open_browser=False)
    st.bokeh_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Detailed Backtest Metrics")
    # Clean dataframe view for stats
    stats_df = pd.DataFrame(stats).astype(str)
    st.dataframe(stats_df, use_container_width=True)
