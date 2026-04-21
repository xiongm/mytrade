from dataclasses import dataclass

import pandas as pd
import pytest

from mean_reversion.strategies.mean_reversion import STRATEGY_TYPES as EQUITY_STRATEGY_TYPES
from mean_reversion.strategies.mean_reversion_crypto import STRATEGY_TYPES as CRYPTO_STRATEGY_TYPES
from mean_reversion.strategies.registry import get_strategy, list_strategy_names
from mean_reversion.strategies.mean_reversion.base import validate_signal_frames
from mean_reversion.strategies.mean_reversion.entry_10 import MeanReversionEntry10Strategy
from mean_reversion.strategies.mean_reversion.entry_20 import MeanReversionEntry20Strategy
from mean_reversion.strategies.mean_reversion.exit_70 import MeanReversionExit70Strategy
from mean_reversion.strategies.mean_reversion.fixed_exit_3 import MeansREversionsFixedExit6Strategy
from mean_reversion.strategies.mean_reversion.fast_exit import MeanReversionFastExitStrategy
from mean_reversion.strategies.mean_reversion.strict import MeanReversionStrictStrategy
from mean_reversion.strategies.mean_reversion.v1 import MeanReversionV1Strategy
from mean_reversion.strategies.mean_reversion_crypto.v1 import MeanReversionCryptoV1Strategy
from mean_reversion.strategies.mean_reversion_crypto.btc_v1 import MeanReversionCryptoBTCV1Strategy


def test_mean_reversion_v1_declares_required_symbols():
    strategy = MeanReversionV1Strategy()

    assert strategy.required_symbols() == ("SPY", "IVV", "QQQ")


def test_mean_reversion_crypto_v1_declares_required_symbols():
    strategy = MeanReversionCryptoV1Strategy()

    assert strategy.required_symbols() == ("BTC-USD", "ETH-USD")
    assert strategy.market == "crypto"
    assert strategy.instrument_type == "spot"


def test_mean_reversion_crypto_btc_v1_declares_required_symbols():
    strategy = MeanReversionCryptoBTCV1Strategy()

    assert strategy.required_symbols() == ("BTC-USD", "BTC-USD")
    assert strategy.trade_symbols == ("BTC-USD",)
    assert strategy.use_market_filter is False


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


def test_mean_reversion_exit_70_uses_looser_exit_threshold_than_v1():
    strategy = MeanReversionExit70Strategy()

    assert strategy.exit_rsi_threshold == 70.0


def test_strategy_registry_exposes_mean_reversion_exit_70():
    assert "mean_reversion_exit_70" in list_strategy_names()
    assert get_strategy("mean_reversion_exit_70").exit_rsi_threshold == 70.0


def test_strategy_registry_exposes_mean_reversion_crypto_v1():
    assert "mean_reversion_crypto_v1" in list_strategy_names()
    assert get_strategy("mean_reversion_crypto_v1").trade_symbols == ("ETH-USD",)


def test_strategy_registry_exposes_mean_reversion_crypto_btc_v1():
    assert "mean_reversion_crypto_btc_v1" in list_strategy_names()
    assert get_strategy("mean_reversion_crypto_btc_v1").trade_symbols == ("BTC-USD",)


def test_mean_reversion_entry_20_uses_looser_entry_threshold_than_v1():
    strategy = MeanReversionEntry20Strategy()

    assert strategy.entry_rsi_threshold == 20.0


def test_mean_reversion_entry_10_uses_stricter_entry_and_simpler_confirmation():
    strategy = MeanReversionEntry10Strategy()

    assert strategy.entry_rsi_threshold == 10.0
    assert strategy.exit_rsi_threshold == 60.0
    assert strategy.max_hold_days == 4
    assert strategy.require_two_down_closes is False


def test_mean_reversion_fixed_exit_3_uses_entry_20_and_time_exit_only():
    strategy = MeansREversionsFixedExit6Strategy()

    assert strategy.entry_rsi_threshold == 20.0
    assert strategy.exit_rsi_threshold == 60.0
    assert strategy.max_hold_days == 6
    assert strategy.require_two_down_closes is False
    assert strategy.use_rsi_exit is False


def test_strategy_registry_derives_names_from_exported_strategy_types():
    expected_names = sorted(
        strategy.name for strategy in [*EQUITY_STRATEGY_TYPES, *CRYPTO_STRATEGY_TYPES]
    )
    assert expected_names == list_strategy_names()
    assert get_strategy("mean_reversion_entry_20").entry_rsi_threshold == 20.0
    assert get_strategy("mean_reversion_entry_10").entry_rsi_threshold == 10.0
    assert get_strategy("mean_reversion_exit_6").max_hold_days == 6


def test_mean_reversion_v1_requires_two_down_closes_by_default():
    strategy = MeanReversionV1Strategy()
    dates = pd.date_range("2026-01-01", periods=1, name="date")
    market = pd.DataFrame({"market_ok": [True]}, index=dates)
    symbol = pd.DataFrame(
        {
            "close": [100.0],
            "trend_ma": [90.0],
            "two_down_closes": [False],
            "rsi": [10.0],
        },
        index=dates,
    )

    signals = strategy.build_signals({"SPY": market, "IVV": symbol, "QQQ": symbol.copy()})

    assert bool(signals["IVV"].iloc[0]["entry_signal"]) is False


def test_strategy_can_disable_two_down_closes_requirement():
    @dataclass(frozen=True)
    class NoTwoDownClosesStrategy(MeanReversionV1Strategy):
        require_two_down_closes: bool = False

    strategy = NoTwoDownClosesStrategy()
    dates = pd.date_range("2026-01-01", periods=1, name="date")
    market = pd.DataFrame({"market_ok": [True]}, index=dates)
    symbol = pd.DataFrame(
        {
            "close": [100.0],
            "trend_ma": [90.0],
            "two_down_closes": [False],
            "rsi": [10.0],
        },
        index=dates,
    )

    signals = strategy.build_signals({"SPY": market, "IVV": symbol, "QQQ": symbol.copy()})

    assert bool(signals["IVV"].iloc[0]["entry_signal"]) is True


def test_mean_reversion_v1_uses_rsi_exit_by_default():
    strategy = MeanReversionV1Strategy()
    dates = pd.date_range("2026-01-01", periods=1, name="date")
    market = pd.DataFrame({"market_ok": [True]}, index=dates)
    symbol = pd.DataFrame(
        {
            "close": [100.0],
            "trend_ma": [90.0],
            "two_down_closes": [True],
            "rsi": [90.0],
        },
        index=dates,
    )

    signals = strategy.build_signals({"SPY": market, "IVV": symbol, "QQQ": symbol.copy()})

    assert bool(signals["IVV"].iloc[0]["exit_signal"]) is True


def test_strategy_can_disable_rsi_exit():
    @dataclass(frozen=True)
    class FixedTimeExitStrategy(MeanReversionV1Strategy):
        use_rsi_exit: bool = False

    strategy = FixedTimeExitStrategy()
    dates = pd.date_range("2026-01-01", periods=1, name="date")
    market = pd.DataFrame({"market_ok": [True]}, index=dates)
    symbol = pd.DataFrame(
        {
            "close": [100.0],
            "trend_ma": [90.0],
            "two_down_closes": [True],
            "rsi": [90.0],
        },
        index=dates,
    )

    signals = strategy.build_signals({"SPY": market, "IVV": symbol, "QQQ": symbol.copy()})

    assert bool(signals["IVV"].iloc[0]["exit_signal"]) is False


def test_mean_reversion_crypto_v1_can_enter_without_market_filter():
    strategy = MeanReversionCryptoV1Strategy()
    dates = pd.date_range("2026-01-01", periods=1, name="date")
    market = pd.DataFrame({"market_ok": [True]}, index=dates)
    eth = pd.DataFrame(
        {
            "close": [100.0],
            "trend_ma": [90.0],
            "two_down_closes": [False],
            "rsi": [10.0],
        },
        index=dates,
    )

    signals = strategy.build_signals({"BTC-USD": market, "ETH-USD": eth})

    assert bool(signals["ETH-USD"].iloc[0]["entry_signal"]) is True
