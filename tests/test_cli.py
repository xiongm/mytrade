import pytest
import pandas as pd

from mean_reversion import cli
from mean_reversion.backtest import BacktestResult
from mean_reversion.cli import build_parser
from mean_reversion.config import BacktestConfig
from mean_reversion.data_sources.registry import get_data_source, list_data_source_names


def test_list_data_source_names_includes_default_and_file_sources():
    assert "yfinance" in list_data_source_names()
    assert "csv" in list_data_source_names()
    assert "parquet" in list_data_source_names()


def test_get_data_source_returns_default_source_instance():
    source = get_data_source("yfinance")

    assert source.name == "yfinance"


def test_cli_defaults_data_source_to_yfinance():
    parser = build_parser()
    args = parser.parse_args(["--strategy", "mean_reversion_v1"])

    assert args.data_source == "yfinance"


def test_cli_requires_strategy_flag():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_cli_loads_strategy_symbols_from_selected_data_source(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "BacktestConfig", lambda: BacktestConfig(output_dir=str(tmp_path)))

    requested_symbols = {}

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            requested_symbols["symbols"] = symbols
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

    assert requested_symbols["symbols"] == ("SPY", "IVV", "QQQ")
    assert (tmp_path / "comparison.csv").exists()
