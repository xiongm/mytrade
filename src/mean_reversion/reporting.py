from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_summary_stats(trades: pd.DataFrame, equity_curve: pd.DataFrame) -> dict[str, float]:
    if equity_curve.empty:
        raise ValueError("Equity curve is empty")

    equity = equity_curve["equity"]
    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1
    wins = trades.loc[trades["return_pct"] > 0, "return_pct"]
    losses = trades.loc[trades["return_pct"] <= 0, "return_pct"]

    return {
        "total_return": float((equity.iloc[-1] / equity.iloc[0]) - 1),
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((trades["return_pct"] > 0).mean()) if not trades.empty else 0.0,
        "average_trade_return": float(trades["return_pct"].mean()) if not trades.empty else 0.0,
        "average_win": float(wins.mean()) if not wins.empty else 0.0,
        "average_loss": float(losses.mean()) if not losses.empty else 0.0,
        "number_of_trades": int(len(trades)),
    }


def write_outputs(
    output_dir: str,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    summary: dict[str, float],
    run_name: str,
) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    trades.to_csv(path / f"{run_name}_trades.csv", index=False)
    equity_curve.to_csv(path / f"{run_name}_equity_curve.csv")
    pd.Series(summary).to_csv(path / f"{run_name}_summary.csv", header=["value"])


def compare_runs(base_result, slippage_result) -> pd.DataFrame:
    base_summary = build_summary_stats(base_result.trades, base_result.equity_curve)
    slippage_summary = build_summary_stats(slippage_result.trades, slippage_result.equity_curve)

    comparison = pd.DataFrame(
        {
            "base": pd.Series(base_summary),
            "slippage": pd.Series(slippage_summary),
        }
    )
    comparison["delta"] = comparison["slippage"] - comparison["base"]
    return comparison
