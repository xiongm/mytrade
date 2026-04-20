from pathlib import Path

from mean_reversion.results.models import RunContext
from mean_reversion.results.paths import bucket_dir, bundle_dir, history_file, latest_dir


def test_bucket_dir_uses_strategy_and_composite_market_instrument_source():
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
        entry_rsi_threshold=15.0,
        exit_rsi_threshold=60.0,
        max_hold_days=4,
        require_two_down_closes=True,
        use_rsi_exit=True,
        stop_loss_pct=0.03,
    )

    path = bucket_dir(Path("results"), context)

    assert path == Path("results/mean_reversion_v1/us__etf__yfinance")


def test_bundle_and_history_paths_use_fingerprint_and_timestamp():
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
        entry_rsi_threshold=15.0,
        exit_rsi_threshold=60.0,
        max_hold_days=4,
        require_two_down_closes=True,
        use_rsi_exit=True,
        stop_loss_pct=0.03,
    )

    assert bundle_dir(Path("results"), context, "abc123") == Path("results/mean_reversion_v1/us__etf__yfinance/bundles/abc123")
    assert history_file(Path("results"), context) == Path("results/mean_reversion_v1/us__etf__yfinance/history/2026-04-18T14-10-00.json")
    assert latest_dir(Path("results"), context) == Path("results/mean_reversion_v1/us__etf__yfinance/latest")
