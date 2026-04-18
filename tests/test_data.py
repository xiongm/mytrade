import pandas as pd

from mean_reversion.config import BacktestConfig
from mean_reversion.data import normalize_symbol_frame, validate_symbol_frames


def test_default_backtest_config_matches_strategy_spec():
    config = BacktestConfig()

    assert config.initial_cash == 10_000.0
    assert config.market_symbol == "SPY"
    assert config.trade_symbols == ("IVV", "QQQ")
    assert config.max_positions == 2
    assert config.max_position_weight == 0.40
    assert config.min_cash_weight == 0.20
    assert config.max_hold_days == 4
    assert config.stop_loss_pct == 0.03
    assert config.entry_rsi_threshold == 15.0
    assert config.exit_rsi_threshold == 60.0


def test_normalize_symbol_frame_standardizes_columns_and_index():
    raw = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-03"],
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1_000, 2_000],
        }
    )

    normalized = normalize_symbol_frame(raw)

    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert normalized.index.name == "date"
    assert normalized.loc[pd.Timestamp("2026-01-02"), "close"] == 100.5


def test_validate_symbol_frames_requires_same_trading_calendar():
    shared = pd.DatetimeIndex(["2026-01-02", "2026-01-03"], name="date")
    shifted = pd.DatetimeIndex(["2026-01-03", "2026-01-06"], name="date")

    frames = {
        "SPY": pd.DataFrame({"close": [1, 2]}, index=shared),
        "IVV": pd.DataFrame({"close": [1, 2]}, index=shared),
        "QQQ": pd.DataFrame({"close": [1, 2]}, index=shifted),
    }

    try:
        validate_symbol_frames(frames)
    except ValueError as exc:
        assert "same date index" in str(exc)
    else:
        raise AssertionError("Expected validate_symbol_frames() to reject misaligned data")


def test_normalize_symbol_frame_accepts_csv_fixture():
    raw = pd.read_csv("tests/fixtures/sample_daily_bars.csv")

    normalized = normalize_symbol_frame(raw)

    assert normalized.index.min() == pd.Timestamp("2026-01-02")
    assert normalized.index.max() == pd.Timestamp("2026-01-06")
    assert normalized["volume"].sum() == 4_500


def test_normalize_symbol_frame_accepts_yfinance_style_multiindex_columns():
    raw = pd.DataFrame(
        {
            ("Date", ""): ["2026-01-02", "2026-01-03"],
            ("Open", "SPY"): [100.0, 101.0],
            ("High", "SPY"): [101.0, 102.0],
            ("Low", "SPY"): [99.0, 100.0],
            ("Close", "SPY"): [100.5, 101.5],
            ("Volume", "SPY"): [1_000, 2_000],
        }
    )

    normalized = normalize_symbol_frame(raw)

    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert normalized.loc[pd.Timestamp("2026-01-02"), "open"] == 100.0
