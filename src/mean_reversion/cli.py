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
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data_source = get_data_source(args.data_source)
        strategy = get_strategy(args.strategy)
    except ValueError as exc:
        parser.error(str(exc))

    default_config = BacktestConfig()
    config = BacktestConfig(
        initial_cash=default_config.initial_cash,
        market_symbol=strategy.market_symbol,
        trade_symbols=strategy.trade_symbols,
        lookback_years=default_config.lookback_years,
        max_positions=default_config.max_positions,
        max_position_weight=default_config.max_position_weight,
        min_cash_weight=default_config.min_cash_weight,
        max_hold_days=getattr(strategy, "max_hold_days", default_config.max_hold_days),
        stop_loss_pct=default_config.stop_loss_pct,
        entry_rsi_threshold=getattr(strategy, "entry_rsi_threshold", default_config.entry_rsi_threshold),
        exit_rsi_threshold=getattr(strategy, "exit_rsi_threshold", default_config.exit_rsi_threshold),
        market_ma_window=getattr(strategy, "market_ma_window", default_config.market_ma_window),
        trend_ma_window=getattr(strategy, "trend_ma_window", default_config.trend_ma_window),
        rsi_window=getattr(strategy, "rsi_window", default_config.rsi_window),
        slippage_bps=default_config.slippage_bps,
        output_dir=default_config.output_dir,
    )
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
