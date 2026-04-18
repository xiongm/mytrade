import pytest
import pandas as pd

from mean_reversion.backtest import BacktestResult, run_backtest
from mean_reversion.config import BacktestConfig
from mean_reversion.reporting import build_summary_stats, compare_runs


def test_run_backtest_enters_on_next_open_and_exits_on_signal_open():
    dates = pd.date_range("2026-01-01", periods=6, freq="D", name="date")
    market = pd.DataFrame(
        {
            "open": [1] * 6,
            "high": [1] * 6,
            "low": [1] * 6,
            "close": [1, 2, 3, 4, 5, 6],
            "market_ma": [1, 1, 1, 1, 1, 1],
            "market_ok": [False, False, True, True, True, True],
        },
        index=dates,
    )
    ivv = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 99, 98, 100, 101, 102],
            "entry_signal": [False, False, True, False, False, False],
            "exit_signal": [False, False, False, False, True, False],
        },
        index=dates,
    )

    result = run_backtest({"SPY": market, "IVV": ivv, "QQQ": ivv.copy()}, BacktestConfig())

    assert len(result.trades) >= 1
    first_trade = result.trades.iloc[0]
    assert first_trade["entry_date"] == pd.Timestamp("2026-01-04")
    assert first_trade["exit_date"] == pd.Timestamp("2026-01-06")


def test_run_backtest_triggers_stop_loss_when_daily_low_breaches_threshold():
    dates = pd.date_range("2026-01-01", periods=5, freq="D", name="date")
    market = pd.DataFrame(
        {"market_ok": [True] * 5, "open": [1] * 5, "high": [1] * 5, "low": [1] * 5, "close": [1] * 5},
        index=dates,
    )
    ivv = pd.DataFrame(
        {
            "open": [100, 100, 100, 100, 100],
            "high": [101, 101, 101, 101, 101],
            "low": [99, 99, 96, 99, 99],
            "close": [100, 99, 98, 99, 100],
            "entry_signal": [True, False, False, False, False],
            "exit_signal": [False, False, False, False, False],
        },
        index=dates,
    )

    result = run_backtest({"SPY": market, "IVV": ivv, "QQQ": ivv.copy()}, BacktestConfig())

    assert (result.trades["exit_reason"] == "stop_loss").any()


def test_run_backtest_respects_cash_reserve_and_max_positions():
    dates = pd.date_range("2026-01-01", periods=4, freq="D", name="date")
    market = pd.DataFrame(
        {"market_ok": [True] * 4, "open": [1] * 4, "high": [1] * 4, "low": [1] * 4, "close": [1] * 4},
        index=dates,
    )
    tradable = pd.DataFrame(
        {
            "open": [100, 100, 100, 100],
            "high": [101, 101, 101, 101],
            "low": [99, 99, 99, 99],
            "close": [100, 100, 100, 100],
            "entry_signal": [True, False, False, False],
            "exit_signal": [False, False, False, False],
        },
        index=dates,
    )
    config = BacktestConfig(initial_cash=10_000.0, max_positions=2, max_position_weight=0.40, min_cash_weight=0.20)

    result = run_backtest({"SPY": market, "IVV": tradable, "QQQ": tradable.copy()}, config)

    assert not result.trades.empty or not result.equity_curve.empty
    assert result.equity_curve["cash"].min() >= 2_000.0


def test_build_summary_stats_returns_required_metrics():
    trades = pd.DataFrame(
        [
            {"return_pct": 0.02, "pnl": 20.0},
            {"return_pct": -0.01, "pnl": -10.0},
            {"return_pct": 0.03, "pnl": 30.0},
        ]
    )
    equity = pd.DataFrame({"equity": [10_000, 10_100, 9_950, 10_150]})

    summary = build_summary_stats(trades, equity)

    assert summary["number_of_trades"] == 3
    assert "total_return" in summary
    assert "max_drawdown" in summary
    assert "win_rate" in summary
    assert "average_trade_return" in summary
    assert "average_win" in summary
    assert "average_loss" in summary


def test_cli_main_runs_with_monkeypatched_dependencies(monkeypatch, tmp_path):
    from mean_reversion import cli

    monkeypatch.setattr(cli, "BacktestConfig", lambda: BacktestConfig(output_dir=str(tmp_path)))
    monkeypatch.setattr(cli, "download_daily_bars", lambda config: {})
    monkeypatch.setattr(cli, "build_signal_frames", lambda bars, config: {})
    monkeypatch.setattr(
        cli,
        "run_backtest",
        lambda frames, config, slippage_bps=0.0: BacktestResult(
            trades=pd.DataFrame([{"return_pct": 0.01, "pnl": 10.0}]),
            equity_curve=pd.DataFrame(
                {"equity": [10_000.0, 10_100.0]},
                index=pd.date_range("2026-01-01", periods=2, name="date"),
            ),
        ),
    )

    cli.main()

    assert (tmp_path / "base_summary.csv").exists()
    assert (tmp_path / "slippage_summary.csv").exists()
    assert (tmp_path / "comparison.csv").exists()


def test_compare_runs_shows_base_vs_slippage_delta():
    base = BacktestResult(
        trades=pd.DataFrame([{"return_pct": 0.02, "pnl": 20.0}]),
        equity_curve=pd.DataFrame(
            {"equity": [10_000.0, 10_200.0]},
            index=pd.date_range("2026-01-01", periods=2, name="date"),
        ),
    )
    slippage = BacktestResult(
        trades=pd.DataFrame([{"return_pct": 0.015, "pnl": 15.0}]),
        equity_curve=pd.DataFrame(
            {"equity": [10_000.0, 10_150.0]},
            index=pd.date_range("2026-01-01", periods=2, name="date"),
        ),
    )

    comparison = compare_runs(base, slippage)

    assert comparison.loc["total_return", "base"] == pytest.approx(0.02)
    assert comparison.loc["total_return", "slippage"] == pytest.approx(0.015)
    assert comparison.loc["total_return", "delta"] == pytest.approx(-0.005)
