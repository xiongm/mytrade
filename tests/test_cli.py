import pytest
import pandas as pd
import json

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


def test_cli_reports_unknown_strategy_without_traceback(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--strategy", "does_not_exist"])

    captured = capsys.readouterr()
    assert "Unknown strategy 'does_not_exist'" in captured.err


def test_cli_loads_strategy_symbols_from_selected_data_source(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path)}),
    )

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
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")
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


def test_cli_writes_results_bundle_after_successful_run(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path / "artifacts")}),
    )
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            idx = pd.date_range("2026-01-01", periods=2, name="date")
            return {
                "SPY": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1]}, index=idx),
                "IVV": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1], "entry_signal": [True, False], "exit_signal": [False, True]}, index=idx),
                "QQQ": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1], "entry_signal": [False, False], "exit_signal": [False, False]}, index=idx),
            }

    class StubStrategy:
        name = "mean_reversion_v1"
        market_symbol = "SPY"
        trade_symbols = ("IVV", "QQQ")
        market = "us"
        instrument_type = "etf"

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
            trades=pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01, "pnl": 10.0}]),
            equity_curve=pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
        ),
    )
    monkeypatch.setattr(cli, "_git_head_short", lambda: "2a954a7")

    cli.main(["--strategy", "mean_reversion_v1"])

    history_files = list((tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "history").glob("*.json"))
    assert len(history_files) == 1
    latest_json = json.loads((tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "latest" / "latest.json").read_text())
    assert latest_json["bundle_fingerprint"]
    assert (tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "latest" / "summary.md").exists()
    assert (tmp_path / "results" / "index.html").exists()
    index_content = (tmp_path / "results" / "index.html").read_text()
    assert "mean_reversion_v1" in index_content


def test_cli_persists_strategy_setup_in_latest_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path / "artifacts")}),
    )
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")

    idx = pd.date_range("2026-01-01", periods=2, name="date")

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            return {
                "SPY": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1]}, index=idx),
                "IVV": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1], "entry_signal": [True, False], "exit_signal": [False, True]}, index=idx),
                "QQQ": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1], "entry_signal": [False, False], "exit_signal": [False, False]}, index=idx),
            }

    class StubStrategy:
        name = "mean_reversion_v1"
        market_symbol = "SPY"
        trade_symbols = ("IVV", "QQQ")
        market = "us"
        instrument_type = "etf"
        entry_rsi_threshold = 20.0
        exit_rsi_threshold = 70.0
        max_hold_days = 6
        require_two_down_closes = False
        use_rsi_exit = False

        def required_symbols(self):
            return ("SPY", "IVV", "QQQ")

        def prepare_frames(self, frames):
            return frames

        def build_signals(self, frames):
            return frames

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())
    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())
    monkeypatch.setattr(cli, "_git_head_short", lambda: "2a954a7")
    monkeypatch.setattr(
        cli,
        "run_backtest",
        lambda frames, config, slippage_bps=0.0: BacktestResult(
            trades=pd.DataFrame(
                [
                    {
                        "symbol": "IVV",
                        "entry_date": "2026-01-01",
                        "exit_date": "2026-01-02",
                        "entry_price": 100.0,
                        "exit_price": 101.0,
                        "shares": 10,
                        "pnl": 10.0,
                        "return_pct": 0.01,
                        "exit_reason": "signal",
                    }
                ]
            ),
            equity_curve=pd.DataFrame(
                {"cash": [10_000.0, 0.0], "positions_value": [0.0, 10_100.0], "equity": [10_000.0, 10_100.0]},
                index=idx,
            ),
        ),
    )

    cli.main(["--strategy", "mean_reversion_v1"])

    run_meta = json.loads(next((tmp_path / "results").glob("**/run_meta.json")).read_text())
    assert run_meta["entry_rsi_threshold"] == 20.0
    assert run_meta["exit_rsi_threshold"] == 70.0
    assert run_meta["max_hold_days"] == 6
    assert run_meta["require_two_down_closes"] is False
    assert run_meta["use_rsi_exit"] is False
    assert run_meta["stop_loss_pct"] == 0.03


def test_cli_runs_mean_reversion_crypto_v1_and_writes_crypto_results(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path / "artifacts")}),
    )
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(cli, "_git_head_short", lambda: "2a954a7")

    idx = pd.date_range("2026-01-01", periods=3, name="date")

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            assert symbols == ("BTC-USD", "ETH-USD")
            return {
                "BTC-USD": pd.DataFrame(
                    {
                        "open": [40_000.0, 40_200.0, 40_100.0],
                        "high": [40_300.0, 40_400.0, 40_500.0],
                        "low": [39_800.0, 39_900.0, 40_000.0],
                        "close": [40_100.0, 40_000.0, 40_200.0],
                        "volume": [1_000, 1_100, 1_050],
                    },
                    index=idx,
                ),
                "ETH-USD": pd.DataFrame(
                    {
                        "open": [2_000.0, 1_980.0, 2_010.0],
                        "high": [2_020.0, 2_000.0, 2_030.0],
                        "low": [1_970.0, 1_960.0, 2_000.0],
                        "close": [1_990.0, 1_970.0, 2_020.0],
                        "volume": [500, 550, 525],
                    },
                    index=idx,
                ),
            }

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())

    cli.main(["--strategy", "mean_reversion_crypto_v1"])

    latest_json = json.loads(
        (
            tmp_path
            / "results"
            / "mean_reversion_crypto_v1"
            / "crypto__spot__yfinance"
            / "latest"
            / "latest.json"
        ).read_text()
    )
    assert latest_json["strategy"] == "mean_reversion_crypto_v1"


def test_cli_runs_mean_reversion_crypto_btc_v1_and_writes_crypto_results(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path / "artifacts")}),
    )
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(cli, "_git_head_short", lambda: "2a954a7")

    idx = pd.date_range("2026-01-01", periods=3, name="date")

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            assert symbols == ("BTC-USD", "BTC-USD")
            return {
                "BTC-USD": pd.DataFrame(
                    {
                        "open": [40_000.0, 40_200.0, 40_100.0],
                        "high": [40_300.0, 40_400.0, 40_500.0],
                        "low": [39_800.0, 39_900.0, 40_000.0],
                        "close": [40_100.0, 40_000.0, 40_200.0],
                        "volume": [1_000, 1_100, 1_050],
                    },
                    index=idx,
                ),
            }

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())

    cli.main(["--strategy", "mean_reversion_crypto_btc_v1"])

    latest_json = json.loads(
        (
            tmp_path
            / "results"
            / "mean_reversion_crypto_btc_v1"
            / "crypto__spot__yfinance"
            / "latest"
            / "latest.json"
        ).read_text()
    )
    assert latest_json["strategy"] == "mean_reversion_crypto_btc_v1"


def test_cli_passes_fractional_share_config_for_crypto_strategy(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path / "artifacts")}),
    )
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")
    monkeypatch.setattr(cli, "_git_head_short", lambda: "2a954a7")

    idx = pd.date_range("2026-01-01", periods=2, name="date")
    seen = {}

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            return {
                "BTC-USD": pd.DataFrame(
                    {
                        "open": [40_000.0, 40_500.0],
                        "high": [40_300.0, 40_800.0],
                        "low": [39_800.0, 40_200.0],
                        "close": [40_100.0, 40_600.0],
                        "volume": [1_000, 1_100],
                        "entry_signal": [True, False],
                        "exit_signal": [False, True],
                    },
                    index=idx,
                ),
            }

    class StubStrategy:
        name = "mean_reversion_crypto_btc_v1"
        market = "crypto"
        instrument_type = "spot"
        market_symbol = "BTC-USD"
        trade_symbols = ("BTC-USD",)
        allow_fractional_shares = True
        entry_rsi_threshold = 15.0
        exit_rsi_threshold = 60.0
        max_hold_days = 4
        require_two_down_closes = False
        use_rsi_exit = True

        def required_symbols(self):
            return ("BTC-USD", "BTC-USD")

        def prepare_frames(self, frames):
            return frames

        def build_signals(self, frames):
            return frames

    def fake_run_backtest(frames, config, slippage_bps=0.0):
        seen["allow_fractional_shares"] = config.allow_fractional_shares
        return BacktestResult(
            trades=pd.DataFrame([{"symbol": "BTC-USD", "shares": 0.1, "return_pct": 0.01, "pnl": 10.0}]),
            equity_curve=pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=idx),
        )

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())
    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())
    monkeypatch.setattr(cli, "run_backtest", fake_run_backtest)

    cli.main(["--strategy", "mean_reversion_crypto_btc_v1"])

    assert seen["allow_fractional_shares"] is True
