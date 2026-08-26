"""
OpenAlgo Strategy Parameter Optimizer & 2D Heatmap Engine
Performs fast grid search optimization over historical data to identify robust parameter sets.
"""

import copy
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from quant_engine.backtester import BacktestEngine

class StrategyOptimizer:
    @staticmethod
    def run_grid_search(
        base_config: Dict[str, Any],
        start_date: str,
        end_date: str,
        param_grid: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Executes parameter sweep over pre-fetched historical candle data.
        """
        engine = BacktestEngine(base_config)
        df = engine.fetch_data(start_date, end_date)
        if df.empty or len(df) < 50:
            return {"status": "error", "message": "Insufficient historical data for optimization"}

        fast_emas = param_grid.get("fast_ema", [10, 15, 20, 25])
        slow_emas = param_grid.get("slow_ema", [30, 40, 50, 60])
        stoplosses = param_grid.get("stoploss_val", [0.8, 1.0, 1.5])
        targets = param_grid.get("target_val", [1.5, 2.0, 3.0])

        results = []
        heatmap_matrix = {}

        for fast in fast_emas:
            for slow in slow_emas:
                if fast >= slow:
                    continue
                for sl in stoplosses:
                    for tg in targets:
                        cfg = copy.deepcopy(base_config)
                        cfg["indicators"] = cfg.get("indicators", {})
                        cfg["indicators"]["fast_ema"] = fast
                        cfg["indicators"]["slow_ema"] = slow
                        cfg["stoploss_val"] = sl
                        cfg["target_val"] = tg

                        inst_engine = BacktestEngine(cfg)
                        backtest_res = inst_engine.run_simulation(df.copy())

                        res_item = {
                            "fast_ema": fast,
                            "slow_ema": slow,
                            "stoploss_val": sl,
                            "target_val": tg,
                            "net_pnl": backtest_res.get("total_net_pnl", 0.0),
                            "win_rate": backtest_res.get("win_rate", 0.0),
                            "profit_factor": backtest_res.get("profit_factor", 0.0),
                            "max_drawdown": backtest_res.get("max_drawdown_pct", 0.0),
                            "sharpe_ratio": backtest_res.get("sharpe_ratio", 0.0),
                            "total_trades": backtest_res.get("total_trades", 0)
                        }
                        results.append(res_item)

                        cell_key = f"{fast}_{slow}"
                        if cell_key not in heatmap_matrix:
                            heatmap_matrix[cell_key] = {
                                "fast_ema": fast,
                                "slow_ema": slow,
                                "pnls": [],
                                "sharpes": []
                            }
                        heatmap_matrix[cell_key]["pnls"].append(backtest_res.get("total_net_pnl", 0.0))
                        heatmap_matrix[cell_key]["sharpes"].append(backtest_res.get("sharpe_ratio", 0.0))

        results_sorted = sorted(results, key=lambda x: (x["profit_factor"], x["net_pnl"]), reverse=True)
        top_candidates = results_sorted[:15]

        x_axis_slow = sorted(list(set(slow_emas)))
        y_axis_fast = sorted(list(set(fast_emas)))
        z_pnl = []
        for f in y_axis_fast:
            row = []
            for s in x_axis_slow:
                key = f"{f}_{s}"
                if key in heatmap_matrix and heatmap_matrix[key]["pnls"]:
                    avg_pnl = float(np.mean(heatmap_matrix[key]["pnls"]))
                    row.append(round(avg_pnl, 2))
                else:
                    row.append(None)
            z_pnl.append(row)

        return {
            "status": "success",
            "total_iterations": len(results),
            "top_candidates": top_candidates,
            "best_param": top_candidates[0] if top_candidates else None,
            "heatmap": {
                "x_slow": x_axis_slow,
                "y_fast": y_axis_fast,
                "z_pnl": z_pnl
            }
        }
