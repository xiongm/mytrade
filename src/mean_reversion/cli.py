from __future__ import annotations

import argparse

from .backtest import run_backtest
from .config import BacktestConfig
from .data_sources.registry import get_data_source, list_data_source_names
from .reporting import build_summary_stats, compare_runs, write_outputs
from .strategies.mean_reversion import validate_signal_frames
from .strategies.registry import get_strategy, list_strategy_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-source",
        default="yfinance",
        help=f"Data source name. Valid choices: {', '.join(list_data_source_names())}",
    )
    parser.add_argument(
        "--strategy",
        required=True,
        help=f"Strategy name. Try mean_reversion_v1 first. Valid choices: {', '.join(list_strategy_names())}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_source = get_data_source(args.data_source)
    strategy = get_strategy(args.strategy)

    config = BacktestConfig()
    bars = data_source.load_bars(strategy.required_symbols())
    prepared = strategy.prepare_frames(bars)
    signals = strategy.build_signals(prepared)
    validate_signal_frames({symbol: signals[symbol] for symbol in strategy.trade_symbols})

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
