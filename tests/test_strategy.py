import pandas as pd
import pytest

from mean_reversion.strategies.mean_reversion.base import validate_signal_frames
from mean_reversion.strategies.mean_reversion.fast_exit import MeanReversionFastExitStrategy
from mean_reversion.strategies.mean_reversion.strict import MeanReversionStrictStrategy
from mean_reversion.strategies.mean_reversion.v1 import MeanReversionV1Strategy


def test_mean_reversion_v1_declares_required_symbols():
    strategy = MeanReversionV1Strategy()

    assert strategy.required_symbols() == ("SPY", "IVV", "QQQ")


def test_validate_signal_frames_rejects_missing_entry_signal():
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [100], "exit_signal": [False]},
        index=pd.date_range("2026-01-01", periods=1, name="date"),
    )

    with pytest.raises(ValueError, match="entry_signal"):
        validate_signal_frames({"IVV": frame})


def test_mean_reversion_strict_uses_tighter_entry_threshold_than_v1():
    strategy = MeanReversionStrictStrategy()

    assert strategy.entry_rsi_threshold < 15.0


def test_mean_reversion_fast_exit_uses_faster_exit_threshold_than_v1():
    strategy = MeanReversionFastExitStrategy()

    assert strategy.exit_rsi_threshold < 60.0
