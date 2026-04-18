import pandas as pd

from mean_reversion.config import BacktestConfig
from mean_reversion.strategy import build_signal_frames


def test_build_signal_frames_applies_market_and_entry_filters():
    dates = pd.date_range("2026-01-01", periods=6, freq="D", name="date")
    market = pd.DataFrame(
        {
            "open": [1] * 6,
            "high": [1] * 6,
            "low": [1] * 6,
            "close": [1, 2, 3, 4, 5, 6],
            "volume": [1] * 6,
        },
        index=dates,
    )
    tradable = pd.DataFrame(
        {
            "open": [10, 10, 10, 9, 8, 9],
            "high": [10] * 6,
            "low": [8] * 6,
            "close": [10, 10, 10, 9, 8, 9],
            "volume": [100] * 6,
        },
        index=dates,
    )
    config = BacktestConfig(market_ma_window=3, trend_ma_window=3, rsi_window=2)

    frames = {"SPY": market, "IVV": tradable, "QQQ": tradable.copy()}
    signals = build_signal_frames(frames, config)

    assert "entry_signal" in signals["IVV"].columns
    assert "exit_signal" in signals["IVV"].columns
