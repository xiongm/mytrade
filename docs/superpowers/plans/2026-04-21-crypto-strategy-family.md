# Crypto Strategy Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first daily-only crypto mean reversion strategy family that reuses the shared backtest engine and reporting stack without changing equity strategy behavior.

**Architecture:** Introduce a new `mean_reversion_crypto` strategy family beside the existing equity `mean_reversion` family. Keep the engine, CLI, data-source contract, and results pipeline shared; limit code changes to new strategy-family files, top-level strategy registration, and focused tests that prove registry exposure, crypto signal behavior, and end-to-end CLI execution.

**Tech Stack:** Python 3.12, pandas, pytest, existing OHLCV normalization and signal-driven backtest engine

---

## File Map

**Existing files to modify**

- Modify: `src/mean_reversion/strategies/registry.py`
  - aggregate equity and crypto `STRATEGY_TYPES`
- Modify: `tests/test_strategy.py`
  - cover crypto strategy registration, metadata, and signal semantics
- Modify: `tests/test_cli.py`
  - cover end-to-end CLI execution for the crypto strategy with stubbed data
- Modify: `tests/test_data_sources.py`
  - prove `YFinanceDataSource` accepts crypto symbols like `BTC-USD` and `ETH-USD`

**New files to create**

- Create: `src/mean_reversion/strategies/mean_reversion_crypto/base.py`
  - crypto-family base dataclass with shared defaults and signal-building logic
- Create: `src/mean_reversion/strategies/mean_reversion_crypto/v1.py`
  - first concrete crypto strategy class
- Create: `src/mean_reversion/strategies/mean_reversion_crypto/__init__.py`
  - export crypto strategy types for registry aggregation

## First-Cut Crypto v1 Semantics

The implementation should encode the following first-cut rules:

- strategy name: `mean_reversion_crypto_v1`
- market: `crypto`
- instrument type: `spot`
- market symbol: `BTC-USD`
- trade symbols: `("ETH-USD",)`
- daily bars only
- trend MA window: `50`
- RSI window: `2`
- entry RSI threshold: `15`
- exit RSI threshold: `60`
- `require_two_down_closes = False`
- `use_rsi_exit = True`
- `use_market_filter = False`

When `use_market_filter = False`, the crypto family should still produce a `market_ok` column on the market frame, but it should evaluate to `True` for all rows so the shared signal pattern remains uniform.

### Task 1: Add Failing Tests For Crypto Symbols, Registry, and Signal Semantics

**Files:**
- Modify: `tests/test_data_sources.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write the failing yfinance crypto-symbol test**

Add this test to `tests/test_data_sources.py`:

```python
def test_yfinance_source_accepts_crypto_symbols(monkeypatch):
    raw = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-03"],
            "Open": [40_000.0, 40_500.0],
            "High": [40_500.0, 41_000.0],
            "Low": [39_500.0, 40_000.0],
            "Close": [40_200.0, 40_800.0],
            "Volume": [1_000, 1_100],
        }
    )

    source = YFinanceDataSource()
    monkeypatch.setattr(source, "_download_symbol", lambda symbol: raw)

    frames = source.load_bars(("BTC-USD", "ETH-USD"))

    assert sorted(frames) == ["BTC-USD", "ETH-USD"]
    assert frames["BTC-USD"].index.name == "date"
    assert list(frames["ETH-USD"].columns) == ["open", "high", "low", "close", "volume"]
```

- [ ] **Step 2: Write the failing crypto strategy registration tests**

Add these tests to `tests/test_strategy.py`:

```python
from mean_reversion.strategies.mean_reversion_crypto.v1 import MeanReversionCryptoV1Strategy


def test_mean_reversion_crypto_v1_declares_required_symbols():
    strategy = MeanReversionCryptoV1Strategy()

    assert strategy.required_symbols() == ("BTC-USD", "ETH-USD")
    assert strategy.market == "crypto"
    assert strategy.instrument_type == "spot"


def test_strategy_registry_exposes_mean_reversion_crypto_v1():
    assert "mean_reversion_crypto_v1" in list_strategy_names()
    assert get_strategy("mean_reversion_crypto_v1").trade_symbols == ("ETH-USD",)
```

- [ ] **Step 3: Write the failing crypto signal-semantics test**

Add this test to `tests/test_strategy.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python -m pytest \
  tests/test_data_sources.py::test_yfinance_source_accepts_crypto_symbols \
  tests/test_strategy.py::test_mean_reversion_crypto_v1_declares_required_symbols \
  tests/test_strategy.py::test_strategy_registry_exposes_mean_reversion_crypto_v1 \
  tests/test_strategy.py::test_mean_reversion_crypto_v1_can_enter_without_market_filter \
  -v
```

Expected:

- import failure for `mean_reversion.strategies.mean_reversion_crypto...`
- registry failure because the strategy name is not exposed yet

- [ ] **Step 5: Commit**

Do not commit yet. These tests should remain failing until Task 2 is complete.

### Task 2: Implement The Crypto Strategy Family And Registry Aggregation

**Files:**
- Create: `src/mean_reversion/strategies/mean_reversion_crypto/base.py`
- Create: `src/mean_reversion/strategies/mean_reversion_crypto/v1.py`
- Create: `src/mean_reversion/strategies/mean_reversion_crypto/__init__.py`
- Modify: `src/mean_reversion/strategies/registry.py`

- [ ] **Step 1: Create the crypto-family base class**

Create `src/mean_reversion/strategies/mean_reversion_crypto/base.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...indicators import enrich_symbol_frame


@dataclass(frozen=True)
class MeanReversionCryptoStrategyBase:
    name: str = "mean_reversion_crypto_base"
    market: str = "crypto"
    instrument_type: str = "spot"
    market_symbol: str = "BTC-USD"
    trade_symbols: tuple[str, ...] = ("ETH-USD",)
    market_ma_window: int = 200
    trend_ma_window: int = 50
    rsi_window: int = 2
    entry_rsi_threshold: float = 15.0
    exit_rsi_threshold: float = 60.0
    require_two_down_closes: bool = False
    use_rsi_exit: bool = True
    use_market_filter: bool = False

    def required_symbols(self) -> tuple[str, ...]:
        return (self.market_symbol, *self.trade_symbols)

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        market = enrich_symbol_frame(
            frames[self.market_symbol],
            ma_window=self.market_ma_window,
            rsi_window=self.rsi_window,
        ).rename(columns={f"ma_{self.market_ma_window}": "market_ma"})
        market["market_ok"] = (
            market["close"] > market["market_ma"] if self.use_market_filter else True
        )

        prepared = {self.market_symbol: market}
        for symbol in self.trade_symbols:
            prepared[symbol] = enrich_symbol_frame(
                frames[symbol],
                ma_window=self.trend_ma_window,
                rsi_window=self.rsi_window,
            ).rename(
                columns={
                    f"ma_{self.trend_ma_window}": "trend_ma",
                    f"rsi_{self.rsi_window}": "rsi",
                }
            )
        return prepared

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        market = frames[self.market_symbol].copy()
        signal_frames = {self.market_symbol: market}

        for symbol in self.trade_symbols:
            enriched = frames[symbol].copy()
            entry_signal = (
                market["market_ok"]
                & (enriched["close"] > enriched["trend_ma"])
                & (enriched["rsi"] < self.entry_rsi_threshold)
            )
            if self.require_two_down_closes:
                entry_signal = entry_signal & enriched["two_down_closes"]
            enriched["entry_signal"] = entry_signal
            enriched["exit_signal"] = (
                enriched["rsi"] > self.exit_rsi_threshold if self.use_rsi_exit else False
            )
            signal_frames[symbol] = enriched

        return signal_frames
```

- [ ] **Step 2: Create the first concrete crypto strategy**

Create `src/mean_reversion/strategies/mean_reversion_crypto/v1.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from .base import MeanReversionCryptoStrategyBase


@dataclass(frozen=True)
class MeanReversionCryptoV1Strategy(MeanReversionCryptoStrategyBase):
    name: str = "mean_reversion_crypto_v1"
    market_symbol: str = "BTC-USD"
    trade_symbols: tuple[str, ...] = ("ETH-USD",)
    require_two_down_closes: bool = False
    use_market_filter: bool = False
```

- [ ] **Step 3: Export crypto strategy types**

Create `src/mean_reversion/strategies/mean_reversion_crypto/__init__.py` with:

```python
from .base import MeanReversionCryptoStrategyBase
from .v1 import MeanReversionCryptoV1Strategy

STRATEGY_TYPES = [
    MeanReversionCryptoV1Strategy,
]

__all__ = [
    "MeanReversionCryptoStrategyBase",
    "MeanReversionCryptoV1Strategy",
    "STRATEGY_TYPES",
]
```

- [ ] **Step 4: Aggregate equity and crypto strategy types in the top-level registry**

Update `src/mean_reversion/strategies/registry.py` to:

```python
from .mean_reversion import STRATEGY_TYPES as EQUITY_STRATEGY_TYPES
from .mean_reversion_crypto import STRATEGY_TYPES as CRYPTO_STRATEGY_TYPES


STRATEGY_FACTORIES = {
    strategy_type.name: strategy_type
    for strategy_type in [*EQUITY_STRATEGY_TYPES, *CRYPTO_STRATEGY_TYPES]
}
```

Keep `list_strategy_names()` and `get_strategy()` unchanged.

- [ ] **Step 5: Run focused tests to verify they pass**

Run:

```bash
./.venv/bin/python -m pytest \
  tests/test_data_sources.py::test_yfinance_source_accepts_crypto_symbols \
  tests/test_strategy.py::test_mean_reversion_crypto_v1_declares_required_symbols \
  tests/test_strategy.py::test_strategy_registry_exposes_mean_reversion_crypto_v1 \
  tests/test_strategy.py::test_mean_reversion_crypto_v1_can_enter_without_market_filter \
  -v
```

Expected:

- all four tests PASS

- [ ] **Step 6: Commit**

```bash
git add \
  src/mean_reversion/strategies/registry.py \
  src/mean_reversion/strategies/mean_reversion_crypto/base.py \
  src/mean_reversion/strategies/mean_reversion_crypto/v1.py \
  src/mean_reversion/strategies/mean_reversion_crypto/__init__.py \
  tests/test_data_sources.py \
  tests/test_strategy.py
git commit -m "feat: add crypto strategy family"
```

### Task 3: Add CLI Smoke Coverage For The Crypto Strategy

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Add this test to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails or exposes missing assumptions**

Run:

```bash
./.venv/bin/python -m pytest tests/test_cli.py::test_cli_runs_mean_reversion_crypto_v1_and_writes_crypto_results -v
```

Expected:

- if Task 2 is complete, this may already PASS
- if it fails, the failure should point to a concrete crypto-family integration mismatch

- [ ] **Step 3: Make the minimal code adjustment only if the test fails**

If the test fails because the crypto strategy does not expose `market`, `instrument_type`, `required_symbols()`, or signal columns in a way the CLI depends on, fix only the smallest necessary gap in:

- `src/mean_reversion/strategies/mean_reversion_crypto/base.py`
- `src/mean_reversion/strategies/mean_reversion_crypto/v1.py`

Do not modify equity strategy files.

- [ ] **Step 4: Run the focused CLI test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest tests/test_cli.py::test_cli_runs_mean_reversion_crypto_v1_and_writes_crypto_results -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py src/mean_reversion/strategies/mean_reversion_crypto/base.py src/mean_reversion/strategies/mean_reversion_crypto/v1.py
git commit -m "test: cover crypto strategy CLI flow"
```

### Task 4: Run Broader Verification And Confirm Equity Isolation

**Files:**
- No new files

- [ ] **Step 1: Run the focused strategy/data/CLI suites**

Run:

```bash
./.venv/bin/python -m pytest tests/test_strategy.py tests/test_data_sources.py tests/test_cli.py -q
```

Expected:

- all targeted suites PASS

- [ ] **Step 2: Run the full test suite**

Run:

```bash
./.venv/bin/python -m pytest -q
```

Expected:

- full suite PASS

- [ ] **Step 3: Manually smoke the new strategy with the default crypto source**

Run:

```bash
python -m mean_reversion.cli --strategy mean_reversion_crypto_v1
```

Expected:

- no traceback
- base/slippage summaries print normally
- a results bundle appears under:

```text
results/mean_reversion_crypto_v1/crypto__spot__yfinance/
```

- [ ] **Step 4: Verify equity-side behavior still works**

Run:

```bash
python -m mean_reversion.cli --strategy mean_reversion_v1
```

Expected:

- no traceback
- equity results still write under:

```text
results/mean_reversion_v1/us__etf__yfinance/
```

- [ ] **Step 5: Commit**

If no code changed during verification, do not create an extra commit.

If verification required a tiny follow-up code fix, commit it with:

```bash
git add <exact files changed>
git commit -m "fix: stabilize crypto strategy integration"
```
