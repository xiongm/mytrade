import pytest
import pandas as pd

from mean_reversion.backtest import BacktestResult, run_backtest
from mean_reversion.config import BacktestConfig
from mean_reversion.reporting import build_summary_stats, compare_runs


def test_run_backtest_rejects_frames_missing_standard_signal_columns():
    dates = pd.date_range("2026-01-01", periods=2, freq="D", name="date")
    market = pd.DataFrame({"open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1, 1]}, index=dates)
    invalid = pd.DataFrame(
        {"open": [100, 100], "high": [101, 101], "low": [99, 99], "close": [100, 100], "volume": [10, 10]},
        index=dates,
    )

    config = BacktestConfig(trade_symbols=("IVV", "QQQ"))

    with pytest.raises(ValueError, match="entry_signal"):
        run_backtest({"SPY": market, "IVV": invalid, "QQQ": invalid.copy()}, config)


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

    config = BacktestConfig(trade_symbols=("IVV", "QQQ"))
    result = run_backtest({"SPY": market, "IVV": ivv, "QQQ": ivv.copy()}, config)

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

    config = BacktestConfig(trade_symbols=("IVV", "QQQ"))
    result = run_backtest({"SPY": market, "IVV": ivv, "QQQ": ivv.copy()}, config)

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
    config = BacktestConfig(
        initial_cash=10_000.0,
        max_positions=2,
        max_position_weight=0.40,
        min_cash_weight=0.20,
        trade_symbols=("IVV", "QQQ"),
    )

    result = run_backtest({"SPY": market, "IVV": tradable, "QQQ": tradable.copy()}, config)

    assert not result.trades.empty or not result.equity_curve.empty
    assert result.equity_curve["cash"].min() >= 2_000.0


def test_run_backtest_can_open_fractional_position_when_enabled():
    dates = pd.date_range("2026-01-01", periods=5, freq="D", name="date")
    market = pd.DataFrame(
        {"market_ok": [True] * 5, "open": [1] * 5, "high": [1] * 5, "low": [1] * 5, "close": [1] * 5},
        index=dates,
    )
    btc = pd.DataFrame(
        {
            "open": [40_000, 40_500, 41_000, 42_000, 43_000],
            "high": [40_500, 41_000, 41_500, 42_500, 43_500],
            "low": [39_500, 40_000, 40_500, 41_500, 42_500],
            "close": [40_100, 40_800, 41_200, 42_200, 43_200],
            "entry_signal": [True, False, False, False, False],
            "exit_signal": [False, False, True, False, False],
        },
        index=dates,
    )

    config = BacktestConfig(
        initial_cash=10_000.0,
        max_positions=1,
        max_position_weight=0.40,
        min_cash_weight=0.20,
        trade_symbols=("BTC-USD",),
        allow_fractional_shares=True,
    )

    result = run_backtest({"SPY": market, "BTC-USD": btc}, config)

    assert len(result.trades) == 1
    assert 0 < float(result.trades.iloc[0]["shares"]) < 1


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

    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path)}),
    )

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            idx = pd.date_range("2026-01-01", periods=2, name="date")
            return {
                "SPY": pd.DataFrame(
                    {"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1]},
                    index=idx,
                ),
                "IVV": pd.DataFrame(
                    {
                        "open": [1.0, 1.0],
                        "high": [1.0, 1.0],
                        "low": [1.0, 1.0],
                        "close": [1.0, 1.0],
                        "volume": [1, 1],
                        "entry_signal": [True, False],
                        "exit_signal": [False, True],
                    },
                    index=idx,
                ),
                "QQQ": pd.DataFrame(
                    {
                        "open": [1.0, 1.0],
                        "high": [1.0, 1.0],
                        "low": [1.0, 1.0],
                        "close": [1.0, 1.0],
                        "volume": [1, 1],
                        "entry_signal": [False, False],
                        "exit_signal": [False, False],
                    },
                    index=idx,
                ),
            }

    class StubStrategy:
        name = "mean_reversion_v1"
        market_symbol = "SPY"
        trade_symbols = ("IVV", "QQQ")

        def required_symbols(self):
            return ("SPY", "IVV", "QQQ")

        def prepare_frames(self, frames):
            return frames

        def build_signals(self, frames):
            return frames

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())
    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())
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

    cli.main(["--strategy", "mean_reversion_v1"])

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
