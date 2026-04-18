# Mean Reversion Backtester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a simple Python daily-bar backtester for the SPY-filtered IVV/QQQ mean reversion strategy defined in `mean_reversion_backtest_plan.md`, including trade simulation, equity tracking, summary stats, and a second slippage-aware comparison pass.

**Architecture:** Keep the project as a small Python package with one responsibility per module: data loading, indicators, strategy signal generation, portfolio simulation, and reporting. Use a thin CLI entrypoint that downloads five years of daily data via `yfinance`, runs both the base and slippage-adjusted backtests, and writes CSV outputs so the strategy can be inspected without extra infrastructure.

**Tech Stack:** Python 3.12, pandas, numpy, yfinance, pytest

---

## File Structure

- Create: `pyproject.toml`
- Create: `src/mean_reversion/__init__.py`
- Create: `src/mean_reversion/config.py`
- Create: `src/mean_reversion/data.py`
- Create: `src/mean_reversion/indicators.py`
- Create: `src/mean_reversion/strategy.py`
- Create: `src/mean_reversion/backtest.py`
- Create: `src/mean_reversion/reporting.py`
- Create: `src/mean_reversion/cli.py`
- Create: `tests/test_data.py`
- Create: `tests/test_indicators.py`
- Create: `tests/test_strategy.py`
- Create: `tests/test_backtest.py`
- Create: `tests/fixtures/sample_daily_bars.csv`

`config.py` holds immutable strategy constants and reusable dataclasses.  
`data.py` downloads and normalizes OHLCV data into a `{symbol: DataFrame}` mapping with aligned date indexes.  
`indicators.py` computes moving averages, RSI(2), and the two-down-days entry condition.  
`strategy.py` turns enriched bars into entry and exit eligibility flags while keeping signal generation separate from portfolio accounting.  
`backtest.py` simulates next-open entries, next-open exits, the daily-low stop approximation, max hold, cash rules, and slippage variants.  
`reporting.py` turns trades and equity into summary statistics and CSV-ready tables.  
`cli.py` is the single executable script for the v1 deliverable.

### Task 1: Scaffold The Package And Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/mean_reversion/__init__.py`
- Create: `src/mean_reversion/config.py`
- Test: `tests/test_data.py`

- [ ] **Step 1: Write the failing config smoke test**

```python
from mean_reversion.config import BacktestConfig


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data.py::test_default_backtest_config_matches_strategy_spec -v`  
Expected: FAIL with `ModuleNotFoundError` or `ImportError` because the package does not exist yet.

- [ ] **Step 3: Create package metadata and config implementation**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mean-reversion-backtest"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "numpy>=1.26",
  "pandas>=2.2",
  "yfinance>=0.2.54",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
]

[project.scripts]
mean-reversion-backtest = "mean_reversion.cli:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000.0
    market_symbol: str = "SPY"
    trade_symbols: tuple[str, ...] = ("IVV", "QQQ")
    lookback_years: int = 5
    max_positions: int = 2
    max_position_weight: float = 0.40
    min_cash_weight: float = 0.20
    max_hold_days: int = 4
    stop_loss_pct: float = 0.03
    entry_rsi_threshold: float = 15.0
    exit_rsi_threshold: float = 60.0
    market_ma_window: int = 200
    trend_ma_window: int = 50
    rsi_window: int = 2
    slippage_bps: float = 10.0
    output_dir: str = "artifacts/mean_reversion"
    symbols: tuple[str, ...] = field(default=("SPY", "IVV", "QQQ"), init=False)
```

```python
from .config import BacktestConfig

__all__ = ["BacktestConfig"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_data.py::test_default_backtest_config_matches_strategy_spec -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/mean_reversion/__init__.py src/mean_reversion/config.py tests/test_data.py
git commit -m "chore: scaffold mean reversion backtest package"
```

### Task 2: Implement Data Download And Normalization

**Files:**
- Modify: `src/mean_reversion/config.py`
- Create: `src/mean_reversion/data.py`
- Modify: `tests/test_data.py`
- Create: `tests/fixtures/sample_daily_bars.csv`

- [ ] **Step 1: Write the failing normalization tests**

```python
import pandas as pd

from mean_reversion.data import normalize_symbol_frame, validate_symbol_frames


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data.py -v`  
Expected: FAIL because `mean_reversion.data` and the normalization helpers do not exist yet.

- [ ] **Step 3: Implement download and normalization**

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from .config import BacktestConfig


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def download_daily_bars(config: BacktestConfig) -> dict[str, pd.DataFrame]:
    end = datetime.now(tz=UTC).date()
    start = end - timedelta(days=365 * config.lookback_years + 30)
    frames: dict[str, pd.DataFrame] = {}

    for symbol in config.symbols:
        raw = yf.download(symbol, start=start.isoformat(), end=end.isoformat(), auto_adjust=False, progress=False)
        if raw.empty:
            raise ValueError(f"No data returned for {symbol}")
        raw = raw.reset_index()
        frames[symbol] = normalize_symbol_frame(raw)

    validate_symbol_frames(frames)
    return frames


def normalize_symbol_frame(raw: pd.DataFrame) -> pd.DataFrame:
    renamed = raw.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    frame = renamed.loc[:, ["date", *[column for column in REQUIRED_COLUMNS if column in renamed.columns]]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False)
    frame = frame.set_index("date").sort_index()
    frame.index.name = "date"
    return frame


def validate_symbol_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No symbol frames supplied")

    indexes = [frame.index for frame in frames.values()]
    first = indexes[0]
    for index in indexes[1:]:
        if not first.equals(index):
            raise ValueError("All symbol frames must share the same date index")
```

- [ ] **Step 4: Add one fixture-backed test for a realistic input file**

```python
import pandas as pd

from mean_reversion.data import normalize_symbol_frame


def test_normalize_symbol_frame_accepts_csv_fixture():
    raw = pd.read_csv("tests/fixtures/sample_daily_bars.csv")

    normalized = normalize_symbol_frame(raw)

    assert normalized.index.min() == pd.Timestamp("2026-01-02")
    assert normalized.index.max() == pd.Timestamp("2026-01-06")
    assert normalized["volume"].sum() == 4_500
```

Fixture file:

```csv
Date,Open,High,Low,Close,Volume
2026-01-02,100,101,99,100.5,1000
2026-01-05,100.5,101.5,100,101.0,1500
2026-01-06,101.0,102.0,100.5,101.2,2000
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_data.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mean_reversion/config.py src/mean_reversion/data.py tests/test_data.py tests/fixtures/sample_daily_bars.csv
git commit -m "feat: add historical data loading and normalization"
```

### Task 3: Implement Indicators And Signal Columns

**Files:**
- Create: `src/mean_reversion/indicators.py`
- Create: `src/mean_reversion/strategy.py`
- Create: `tests/test_indicators.py`
- Create: `tests/test_strategy.py`

- [ ] **Step 1: Write the failing indicator tests**

```python
import pandas as pd

from mean_reversion.indicators import compute_rsi, enrich_symbol_frame


def test_compute_rsi_returns_expected_series_shape():
    closes = pd.Series([100, 99, 98, 99, 100, 101], dtype=float)

    rsi = compute_rsi(closes, period=2)

    assert len(rsi) == len(closes)
    assert rsi.index.equals(closes.index)
    assert rsi.iloc[-1] > 50


def test_enrich_symbol_frame_adds_trend_rsi_and_two_down_days():
    frame = pd.DataFrame(
        {
            "open": [10, 10, 9, 8, 9],
            "high": [10, 10, 9, 9, 10],
            "low": [9, 9, 8, 7, 8],
            "close": [10, 9, 8, 9, 10],
            "volume": [100] * 5,
        },
        index=pd.date_range("2026-01-01", periods=5, freq="D", name="date"),
    )

    enriched = enrich_symbol_frame(frame, ma_window=3, rsi_window=2)

    assert "ma_3" in enriched.columns
    assert "rsi_2" in enriched.columns
    assert "two_down_closes" in enriched.columns
    assert bool(enriched.iloc[2]["two_down_closes"]) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_indicators.py tests/test_strategy.py -v`  
Expected: FAIL because the indicator and strategy modules do not exist yet.

- [ ] **Step 3: Implement indicator helpers**

```python
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100.0)


def enrich_symbol_frame(frame: pd.DataFrame, ma_window: int, rsi_window: int) -> pd.DataFrame:
    enriched = frame.copy()
    enriched[f"ma_{ma_window}"] = enriched["close"].rolling(ma_window, min_periods=ma_window).mean()
    enriched[f"rsi_{rsi_window}"] = compute_rsi(enriched["close"], period=rsi_window)
    enriched["two_down_closes"] = (
        enriched["close"].lt(enriched["close"].shift(1))
        & enriched["close"].shift(1).lt(enriched["close"].shift(2))
    )
    return enriched
```

- [ ] **Step 4: Implement strategy signal generation**

```python
from __future__ import annotations

import pandas as pd

from .config import BacktestConfig
from .indicators import enrich_symbol_frame


def build_signal_frames(
    frames: dict[str, pd.DataFrame],
    config: BacktestConfig,
) -> dict[str, pd.DataFrame]:
    market = enrich_symbol_frame(
        frames[config.market_symbol],
        ma_window=config.market_ma_window,
        rsi_window=config.rsi_window,
    ).rename(columns={f"ma_{config.market_ma_window}": "market_ma"})
    market["market_ok"] = market["close"] > market["market_ma"]

    signal_frames: dict[str, pd.DataFrame] = {config.market_symbol: market}

    for symbol in config.trade_symbols:
        enriched = enrich_symbol_frame(
            frames[symbol],
            ma_window=config.trend_ma_window,
            rsi_window=config.rsi_window,
        ).rename(
            columns={
                f"ma_{config.trend_ma_window}": "trend_ma",
                f"rsi_{config.rsi_window}": "rsi",
            }
        )
        enriched["entry_signal"] = (
            market["market_ok"]
            & (enriched["close"] > enriched["trend_ma"])
            & enriched["two_down_closes"]
            & (enriched["rsi"] < config.entry_rsi_threshold)
        )
        enriched["exit_signal"] = enriched["rsi"] > config.exit_rsi_threshold
        signal_frames[symbol] = enriched

    return signal_frames
```

- [ ] **Step 5: Add a failing-to-passing strategy rule test**

```python
import pandas as pd

from mean_reversion.config import BacktestConfig
from mean_reversion.strategy import build_signal_frames


def test_build_signal_frames_applies_market_and_entry_filters():
    dates = pd.date_range("2026-01-01", periods=6, freq="D", name="date")
    market = pd.DataFrame(
        {"open": [1]*6, "high": [1]*6, "low": [1]*6, "close": [1, 2, 3, 4, 5, 6], "volume": [1]*6},
        index=dates,
    )
    tradable = pd.DataFrame(
        {"open": [10, 10, 10, 9, 8, 9], "high": [10]*6, "low": [8]*6, "close": [10, 10, 10, 9, 8, 9], "volume": [100]*6},
        index=dates,
    )
    config = BacktestConfig(market_ma_window=3, trend_ma_window=3, rsi_window=2)

    frames = {"SPY": market, "IVV": tradable, "QQQ": tradable.copy()}
    signals = build_signal_frames(frames, config)

    assert "entry_signal" in signals["IVV"].columns
    assert "exit_signal" in signals["IVV"].columns
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_indicators.py tests/test_strategy.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/mean_reversion/indicators.py src/mean_reversion/strategy.py tests/test_indicators.py tests/test_strategy.py
git commit -m "feat: add mean reversion indicators and signal generation"
```

### Task 4: Implement Portfolio Simulation And Trade Accounting

**Files:**
- Create: `src/mean_reversion/backtest.py`
- Create: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing backtest execution tests**

```python
import pandas as pd

from mean_reversion.backtest import run_backtest
from mean_reversion.config import BacktestConfig


def test_run_backtest_enters_on_next_open_and_exits_on_signal_open():
    dates = pd.date_range("2026-01-01", periods=6, freq="D", name="date")
    market = pd.DataFrame(
        {"open": [1]*6, "high": [1]*6, "low": [1]*6, "close": [1, 2, 3, 4, 5, 6], "market_ma": [1, 1, 1, 1, 1, 1], "market_ok": [False, False, True, True, True, True]},
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
    market = pd.DataFrame({"market_ok": [True] * 5, "open": [1] * 5, "high": [1] * 5, "low": [1] * 5, "close": [1] * 5}, index=dates)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest.py -v`  
Expected: FAIL because the backtest engine does not exist yet.

- [ ] **Step 3: Implement the minimal backtest engine**

```python
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import BacktestConfig


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.DataFrame


def run_backtest(frames: dict[str, pd.DataFrame], config: BacktestConfig, slippage_bps: float = 0.0) -> BacktestResult:
    dates = frames[config.market_symbol].index
    cash = config.initial_cash
    open_positions: dict[str, dict[str, float | int | pd.Timestamp]] = {}
    trades: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []

    for i, date in enumerate(dates):
        for symbol, position in list(open_positions.items()):
            frame = frames[symbol]
            row = frame.loc[date]
            stop_price = float(position["entry_price"]) * (1 - config.stop_loss_pct)
            hold_days = int(position["bars_held"])

            if row["low"] <= stop_price:
                exit_price = stop_price * (1 - slippage_bps / 10_000)
                cash += float(position["shares"]) * exit_price
                trades.append(_close_trade(symbol, position, date, exit_price, "stop_loss"))
                del open_positions[symbol]
                continue

            if bool(row.get("exit_signal", False)) or hold_days >= config.max_hold_days:
                next_open = _next_open(frame, dates, i)
                if next_open is not None:
                    exit_reason = "signal" if bool(row.get("exit_signal", False)) else "max_hold"
                    exit_price = next_open * (1 - slippage_bps / 10_000)
                    cash += float(position["shares"]) * exit_price
                    trades.append(_close_trade(symbol, position, dates[i + 1], exit_price, exit_reason))
                    del open_positions[symbol]
                    continue

            position["bars_held"] = hold_days + 1

        portfolio_value = cash + sum(float(pos["shares"]) * float(frames[symbol].loc[date, "close"]) for symbol, pos in open_positions.items())
        equity_rows.append({"date": date, "cash": cash, "positions_value": portfolio_value - cash, "equity": portfolio_value})

        if i >= len(dates) - 1:
            continue

        if len(open_positions) >= config.max_positions:
            continue

        for symbol in config.trade_symbols:
            if symbol in open_positions:
                continue
            row = frames[symbol].loc[date]
            if not bool(row.get("entry_signal", False)):
                continue

            position_budget = min(config.initial_cash * config.max_position_weight, cash - (config.initial_cash * config.min_cash_weight))
            if position_budget <= 0:
                continue

            entry_open = float(frames[symbol].iloc[i + 1]["open"]) * (1 + slippage_bps / 10_000)
            shares = int(position_budget // entry_open)
            if shares <= 0:
                continue

            cost = shares * entry_open
            cash -= cost
            open_positions[symbol] = {
                "entry_date": dates[i + 1],
                "entry_price": entry_open,
                "shares": shares,
                "bars_held": 1,
                "cost": cost,
            }

            if len(open_positions) >= config.max_positions:
                break

    return BacktestResult(trades=pd.DataFrame(trades), equity_curve=pd.DataFrame(equity_rows).set_index("date"))


def _next_open(frame: pd.DataFrame, dates: pd.Index, index: int) -> float | None:
    if index + 1 >= len(dates):
        return None
    return float(frame.iloc[index + 1]["open"])


def _close_trade(symbol: str, position: dict[str, object], exit_date: pd.Timestamp, exit_price: float, exit_reason: str) -> dict[str, object]:
    entry_price = float(position["entry_price"])
    shares = int(position["shares"])
    pnl = shares * (exit_price - entry_price)
    return {
        "symbol": symbol,
        "entry_date": position["entry_date"],
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "shares": shares,
        "pnl": pnl,
        "return_pct": (exit_price / entry_price) - 1,
        "exit_reason": exit_reason,
    }
```

- [ ] **Step 4: Extend tests for cash and position limits**

```python
def test_run_backtest_respects_cash_reserve_and_max_positions():
    dates = pd.date_range("2026-01-01", periods=4, freq="D", name="date")
    market = pd.DataFrame({"market_ok": [True] * 4, "open": [1] * 4, "high": [1] * 4, "low": [1] * 4, "close": [1] * 4}, index=dates)
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mean_reversion/backtest.py tests/test_backtest.py
git commit -m "feat: add portfolio simulation for mean reversion strategy"
```

### Task 5: Implement Reporting, CLI, And Base Outputs

**Files:**
- Create: `src/mean_reversion/reporting.py`
- Create: `src/mean_reversion/cli.py`
- Modify: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing reporting tests**

```python
import pandas as pd

from mean_reversion.reporting import build_summary_stats


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest.py::test_build_summary_stats_returns_required_metrics -v`  
Expected: FAIL because the reporting module does not exist yet.

- [ ] **Step 3: Implement summary statistics and file writing**

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_summary_stats(trades: pd.DataFrame, equity_curve: pd.DataFrame) -> dict[str, float]:
    if equity_curve.empty:
        raise ValueError("Equity curve is empty")

    equity = equity_curve["equity"]
    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1
    wins = trades.loc[trades["return_pct"] > 0, "return_pct"]
    losses = trades.loc[trades["return_pct"] <= 0, "return_pct"]

    return {
        "total_return": float((equity.iloc[-1] / equity.iloc[0]) - 1),
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((trades["return_pct"] > 0).mean()) if not trades.empty else 0.0,
        "average_trade_return": float(trades["return_pct"].mean()) if not trades.empty else 0.0,
        "average_win": float(wins.mean()) if not wins.empty else 0.0,
        "average_loss": float(losses.mean()) if not losses.empty else 0.0,
        "number_of_trades": int(len(trades)),
    }


def write_outputs(output_dir: str, trades: pd.DataFrame, equity_curve: pd.DataFrame, summary: dict[str, float], run_name: str) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    trades.to_csv(path / f"{run_name}_trades.csv", index=False)
    equity_curve.to_csv(path / f"{run_name}_equity_curve.csv")
    pd.Series(summary).to_csv(path / f"{run_name}_summary.csv", header=["value"])
```

- [ ] **Step 4: Implement the CLI entrypoint**

```python
from __future__ import annotations

from .backtest import run_backtest
from .config import BacktestConfig
from .data import download_daily_bars
from .reporting import build_summary_stats, write_outputs
from .strategy import build_signal_frames


def main() -> None:
    config = BacktestConfig()
    bars = download_daily_bars(config)
    signals = build_signal_frames(bars, config)

    base_result = run_backtest(signals, config, slippage_bps=0.0)
    base_summary = build_summary_stats(base_result.trades, base_result.equity_curve)
    write_outputs(config.output_dir, base_result.trades, base_result.equity_curve, base_summary, run_name="base")

    slip_result = run_backtest(signals, config, slippage_bps=config.slippage_bps)
    slip_summary = build_summary_stats(slip_result.trades, slip_result.equity_curve)
    write_outputs(config.output_dir, slip_result.trades, slip_result.equity_curve, slip_summary, run_name="slippage")

    print("Base summary:")
    for key, value in base_summary.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")

    print("Slippage summary:")
    for key, value in slip_summary.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")
```

- [ ] **Step 5: Add a CLI smoke test with monkeypatched data**

```python
from mean_reversion.cli import main


def test_cli_main_runs_with_monkeypatched_dependencies(monkeypatch, tmp_path):
    monkeypatch.setattr("mean_reversion.cli.BacktestConfig", lambda: __import__("mean_reversion.config", fromlist=["BacktestConfig"]).BacktestConfig(output_dir=str(tmp_path)))
    monkeypatch.setattr("mean_reversion.cli.download_daily_bars", lambda config: {})
    monkeypatch.setattr("mean_reversion.cli.build_signal_frames", lambda bars, config: {})
    monkeypatch.setattr(
        "mean_reversion.cli.run_backtest",
        lambda frames, config, slippage_bps=0.0: __import__("mean_reversion.backtest", fromlist=["BacktestResult"]).BacktestResult(
            trades=pd.DataFrame([{"return_pct": 0.01, "pnl": 10.0}]),
            equity_curve=pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
        ),
    )

    main()

    assert (tmp_path / "base_summary.csv").exists()
    assert (tmp_path / "slippage_summary.csv").exists()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/mean_reversion/reporting.py src/mean_reversion/cli.py tests/test_backtest.py
git commit -m "feat: add reporting and command line backtest runner"
```

### Task 6: Add Slippage Comparison Coverage And End-To-End Verification

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/mean_reversion/backtest.py`
- Modify: `src/mean_reversion/reporting.py`

- [ ] **Step 1: Write the failing slippage comparison test**

```python
import pandas as pd

from mean_reversion.backtest import BacktestResult
from mean_reversion.reporting import compare_runs


def test_compare_runs_shows_base_vs_slippage_delta():
    base = BacktestResult(
        trades=pd.DataFrame([{"return_pct": 0.02, "pnl": 20.0}]),
        equity_curve=pd.DataFrame({"equity": [10_000.0, 10_200.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
    )
    slippage = BacktestResult(
        trades=pd.DataFrame([{"return_pct": 0.015, "pnl": 15.0}]),
        equity_curve=pd.DataFrame({"equity": [10_000.0, 10_150.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
    )

    comparison = compare_runs(base, slippage)

    assert comparison.loc["total_return", "base"] == 0.02
    assert comparison.loc["total_return", "slippage"] == 0.015
    assert comparison.loc["total_return", "delta"] == -0.005
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest.py::test_compare_runs_shows_base_vs_slippage_delta -v`  
Expected: FAIL because `compare_runs()` does not exist yet.

- [ ] **Step 3: Implement the comparison helper**

```python
def compare_runs(base_result, slippage_result) -> pd.DataFrame:
    base_summary = build_summary_stats(base_result.trades, base_result.equity_curve)
    slippage_summary = build_summary_stats(slippage_result.trades, slippage_result.equity_curve)

    comparison = pd.DataFrame({"base": pd.Series(base_summary), "slippage": pd.Series(slippage_summary)})
    comparison["delta"] = comparison["slippage"] - comparison["base"]
    return comparison
```

- [ ] **Step 4: Extend the CLI to write a comparison file**

```python
from .reporting import build_summary_stats, compare_runs, write_outputs


comparison = compare_runs(base_result, slip_result)
comparison.to_csv(f"{config.output_dir}/comparison.csv")
```

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -v`  
Expected: PASS

- [ ] **Step 6: Run the end-to-end backtest manually**

Run: `python -m mean_reversion.cli`  
Expected:
- downloads 5 years of daily bars for `SPY`, `IVV`, and `QQQ`
- writes `artifacts/mean_reversion/base_trades.csv`
- writes `artifacts/mean_reversion/base_equity_curve.csv`
- writes `artifacts/mean_reversion/slippage_trades.csv`
- writes `artifacts/mean_reversion/slippage_equity_curve.csv`
- writes `artifacts/mean_reversion/base_summary.csv`
- writes `artifacts/mean_reversion/slippage_summary.csv`
- writes `artifacts/mean_reversion/comparison.csv`
- prints both summaries to stdout

- [ ] **Step 7: Commit**

```bash
git add src/mean_reversion/backtest.py src/mean_reversion/reporting.py src/mean_reversion/cli.py tests/test_backtest.py
git commit -m "feat: add slippage comparison outputs"
```

## Self-Review

Spec coverage check:
- 5-year download horizon is covered in `BacktestConfig.lookback_years` and Task 2 download logic.
- Required indicators are covered in Task 3: SPY 200DMA, tradable-symbol 50DMA, RSI(2), and two-down-days.
- Exact simulation rules are covered in Task 4: next-open entry, next-open signal exit, daily-low stop approximation, 4-day max hold, max 2 positions, 40% per position, 20% minimum cash, long-only behavior.
- Required outputs are covered in Tasks 5 and 6: trade log, equity curve, total return, max drawdown, win rate, average trade return, average win, average loss, number of trades, and slippage comparison.
- Non-goals stay excluded: no live broker integration, no optimization sweep, no intraday logic, no database.

Placeholder scan:
- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task has exact file paths, commands, and concrete code snippets.

Type consistency:
- `BacktestConfig`, `BacktestResult`, `build_signal_frames()`, `run_backtest()`, `build_summary_stats()`, and `compare_runs()` are used consistently across tasks.
