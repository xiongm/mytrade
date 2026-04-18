from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess

from .backtest import run_backtest
from .config import BacktestConfig
from .data_sources.registry import get_data_source, list_data_source_names
from .reporting import build_summary_stats, compare_runs, write_outputs
from .results.models import RunContext
from .results.writer import write_results_bundle
from .strategies.mean_reversion import validate_signal_frames
from .strategies.registry import get_strategy, list_strategy_names

RESULTS_ROOT = Path("results")


PERCENTAGE_KEYS = {
    "total_return",
    "max_drawdown",
    "win_rate",
    "average_trade_return",
    "average_win",
    "average_loss",
}


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

    context = RunContext(
        strategy=strategy.name,
        market=getattr(strategy, "market", "us"),
        instrument_type=getattr(strategy, "instrument_type", "etf"),
        source=data_source.name,
        timestamp=datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S"),
        symbols=strategy.required_symbols(),
        date_start=str(signals[strategy.market_symbol].index.min().date()),
        date_end=str(signals[strategy.market_symbol].index.max().date()),
        slippage_bps=config.slippage_bps,
        code_commit=_git_head_short(),
    )
    write_results_bundle(
        root_dir=RESULTS_ROOT,
        context=context,
        base_summary=base_summary,
        slippage_summary=slippage_summary,
        comparison=comparison,
        trades=base_result.trades,
        equity_curve=base_result.equity_curve,
    )

    print("Base summary:")
    _print_summary(base_summary)

    print("Slippage summary:")
    _print_summary(slippage_summary)


def _print_summary(summary: dict[str, float]) -> None:
    for key, value in summary.items():
        label = key.replace("_", " ").title()
        if key in PERCENTAGE_KEYS:
            print(f"  {label}: {value:.2%}")
        else:
            print(f"  {label}: {value}")


def _git_head_short() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
