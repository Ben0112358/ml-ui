from typing import Any

import pandas as pd

STAT_LABELS = {
    "mean_cagr": "Mean CAGR",
    "mean_terminal_return": "Mean terminal return",
    "median_terminal_return": "Median terminal return",
    "annualized_volatility": "Ann. volatility",
    "p1_terminal_return": "P1 terminal return",
    "p5_terminal_return": "P5 terminal return",
    "p95_terminal_return": "P95 terminal return",
    "prob_loss": "Prob. loss",
    "median_max_drawdown": "Median max drawdown",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
}


def weights_dataframe(weights: dict[str, float]) -> pd.DataFrame:
    rows = [{"asset": k, "weight": v} for k, v in sorted(weights.items())]
    return pd.DataFrame(rows)


def comparison_stats_table(
    result: dict[str, Any],
) -> pd.DataFrame:
    optimal = result.get("stats") or {}
    benchmark = result.get("benchmark_stats") or {}
    bench_label = result.get("benchmark_label", "benchmark")
    rows = []
    for key, label in STAT_LABELS.items():
        rows.append(
            {
                "metric": label,
                "optimal": optimal.get(key),
                f"100% {bench_label}": benchmark.get(key),
            }
        )
    return pd.DataFrame(rows)


def history_dataframe(history: list[dict[str, float]]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame(columns=["trial", "value", "best_value"])
    return pd.DataFrame(history)
