from __future__ import annotations

from .backtest import run_backtest
from .config import BacktestConfig
from .data import download_daily_bars
from .reporting import build_summary_stats, compare_runs, write_outputs
from .strategy import build_signal_frames


def main() -> None:
    config = BacktestConfig()
    bars = download_daily_bars(config)
    signals = build_signal_frames(bars, config)

    base_result = run_backtest(signals, config, slippage_bps=0.0)
    base_summary = build_summary_stats(base_result.trades, base_result.equity_curve)
    write_outputs(config.output_dir, base_result.trades, base_result.equity_curve, base_summary, run_name="base")

    slippage_result = run_backtest(signals, config, slippage_bps=config.slippage_bps)
    slippage_summary = build_summary_stats(slippage_result.trades, slippage_result.equity_curve)
    write_outputs(
        config.output_dir,
        slippage_result.trades,
        slippage_result.equity_curve,
        slippage_summary,
        run_name="slippage",
    )
    comparison = compare_runs(base_result, slippage_result)
    comparison.to_csv(f"{config.output_dir}/comparison.csv")

    print("Base summary:")
    for key, value in base_summary.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")

    print("Slippage summary:")
    for key, value in slippage_summary.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")


if __name__ == "__main__":
    main()
