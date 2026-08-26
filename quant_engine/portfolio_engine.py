"""
OpenAlgo Multi-Strategy Portfolio & Correlation Engine
Combines multiple quantitative models, analyzes portfolio-level drawdown, and calculates correlation metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from quant_engine.backtester import BacktestEngine
from quant_engine.strategy_store import StrategyStore

class PortfolioEngine:
    @staticmethod
    def combine_strategies(
        strategy_configs: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        capital_allocation: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Runs backtests on all selected strategies, aligns daily returns, and computes combined portfolio metrics.
        """
        if not strategy_configs:
            return {"status": "error", "message": "No strategies provided for portfolio combination"}

        individual_results = []
        daily_series_map = {}
        all_trades = []

        for strat in strategy_configs:
            name = strat.get("strategy_name", "Strategy")
            engine = BacktestEngine(strat)
            try:
                df = engine.fetch_data(start_date, end_date)
                if df.empty:
                    continue
                res = engine.run_simulation(df)
                res["strategy_name"] = name
                res["symbol"] = strat.get("symbol", "NIFTY")
                individual_results.append(res)

                # Process trades for daily return series
                trades = res.get("trades", [])
                for t in trades:
                    t["strategy_name"] = name
                    all_trades.append(t)

                if trades:
                    tdf = pd.DataFrame(trades)
                    tdf["date"] = pd.to_datetime(tdf["entry_time"]).dt.strftime("%Y-%m-%d")
                    daily_pnl = tdf.groupby("date")["net_pnl"].sum()
                    daily_series_map[name] = daily_pnl
                else:
                    daily_series_map[name] = pd.Series(dtype=float)

            except Exception as e:
                print(f"Error backtesting strategy {name} for portfolio: {e}")

        if not individual_results:
            return {"status": "error", "message": "Failed to run backtests for portfolio strategies"}

        # Step 2: Build Combined Daily Return DataFrame
        daily_df = pd.DataFrame(daily_series_map).fillna(0.0)
        daily_df["combined_pnl"] = daily_df.sum(axis=1)
        daily_df = daily_df.sort_index()

        # Cumulative Portfolio Equity Curve
        initial_capital = sum(float(s.get("capital", 100000.0)) for s in strategy_configs)
        daily_df["cumulative_pnl"] = daily_df["combined_pnl"].cumsum()
        daily_df["portfolio_equity"] = initial_capital + daily_df["cumulative_pnl"]
        daily_df["peak"] = daily_df["portfolio_equity"].cummax()
        daily_df["drawdown_pct"] = (daily_df["portfolio_equity"] - daily_df["peak"]) / daily_df["peak"] * 100.0

        portfolio_equity_curve = [
            {"date": d, "equity": round(eq, 2), "pnl": round(pnl, 2)}
            for d, eq, pnl in zip(daily_df.index, daily_df["portfolio_equity"], daily_df["cumulative_pnl"])
        ]

        total_net_pnl = round(float(daily_df["combined_pnl"].sum()), 2)
        portfolio_roi_pct = round((total_net_pnl / initial_capital) * 100.0, 2)
        max_drawdown_pct = round(abs(float(daily_df["drawdown_pct"].min())), 2)

        # Sharpe ratio
        daily_returns = daily_df["combined_pnl"]
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            portfolio_sharpe = round((daily_returns.mean() / daily_returns.std()) * np.sqrt(252), 2)
        else:
            portfolio_sharpe = 0.0

        # Step 3: Compute Correlation Matrix
        if len(daily_series_map) > 1:
            clean_matrix_df = daily_df.drop(columns=["combined_pnl", "cumulative_pnl", "portfolio_equity", "peak", "drawdown_pct"], errors="ignore")
            corr_df = clean_matrix_df.corr().fillna(0.0)
            correlation_matrix = {
                "strategies": list(corr_df.columns),
                "z_values": [[round(val, 2) for val in row] for row in corr_df.values]
            }
        else:
            correlation_matrix = {"strategies": list(daily_series_map.keys()), "z_values": [[1.0]]}

        # Step 4: Summary Comparison Table
        comparison_table = []
        for r in individual_results:
            comparison_table.append({
                "strategy_name": r.get("strategy_name"),
                "symbol": r.get("symbol"),
                "total_trades": r.get("total_trades", 0),
                "win_rate": r.get("win_rate", 0),
                "total_net_pnl": r.get("total_net_pnl", 0.0),
                "profit_factor": r.get("profit_factor", 0.0),
                "max_drawdown_pct": r.get("max_drawdown_pct", 0.0),
                "sharpe_ratio": r.get("sharpe_ratio", 0.0)
            })

        return {
            "status": "success",
            "initial_capital": initial_capital,
            "total_net_pnl": total_net_pnl,
            "roi_pct": portfolio_roi_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": portfolio_sharpe,
            "strategy_count": len(individual_results),
            "portfolio_equity_curve": portfolio_equity_curve,
            "correlation_matrix": correlation_matrix,
            "comparison_table": comparison_table,
            "all_trades_count": len(all_trades)
        }
