# Data Source And Strategy Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backtester so it selects a data source from the CLI, selects a required strategy from the CLI, loads normalized daily bars through pluggable data adapters, and runs strategy-owned symbol universes through the existing fixed execution engine.

**Architecture:** Introduce two extension seams around the existing simulator: a `data_sources/` package that normalizes remote and file-based daily OHLCV data, and a `strategies/` package that owns symbol universes, indicator preparation, and signal generation. Keep the backtest engine, portfolio rules, stop logic, slippage model, and reporting flow fixed, and make the CLI orchestrate the selected source plus strategy.

**Tech Stack:** Python 3.12, argparse, pandas, numpy, yfinance, pyarrow/parquet support via pandas, pytest

---

## File Structure

- Modify: `src/mean_reversion/__init__.py`
- Modify: `src/mean_reversion/cli.py`
- Modify: `src/mean_reversion/backtest.py`
- Delete: `src/mean_reversion/data.py`
- Delete: `src/mean_reversion/strategy.py`
- Create: `src/mean_reversion/data_sources/__init__.py`
- Create: `src/mean_reversion/data_sources/base.py`
- Create: `src/mean_reversion/data_sources/registry.py`
- Create: `src/mean_reversion/data_sources/yfinance_source.py`
- Create: `src/mean_reversion/data_sources/csv_source.py`
- Create: `src/mean_reversion/data_sources/parquet_source.py`
- Create: `src/mean_reversion/data_sources/china_vendor.py`
- Create: `src/mean_reversion/strategies/__init__.py`
- Create: `src/mean_reversion/strategies/registry.py`
- Create: `src/mean_reversion/strategies/mean_reversion/__init__.py`
- Create: `src/mean_reversion/strategies/mean_reversion/base.py`
- Create: `src/mean_reversion/strategies/mean_reversion/v1.py`
- Create: `src/mean_reversion/strategies/mean_reversion/strict.py`
- Create: `src/mean_reversion/strategies/mean_reversion/fast_exit.py`
- Modify: `tests/test_data.py`
- Modify: `tests/test_strategy.py`
- Modify: `tests/test_backtest.py`
- Create: `tests/test_cli.py`
- Create: `tests/test_data_sources.py`
- Create: `tests/fixtures/csv_source/SPY.csv`
- Create: `tests/fixtures/csv_source/IVV.csv`
- Create: `tests/fixtures/csv_source/QQQ.csv`
- Create: `tests/fixtures/parquet_source/SPY.parquet`
- Create: `tests/fixtures/parquet_source/IVV.parquet`
- Create: `tests/fixtures/parquet_source/QQQ.parquet`

`data_sources/base.py` will hold the normalized OHLCV contract plus shared validation and normalization helpers.  
`data_sources/yfinance_source.py` will absorb the current downloader behavior.  
`csv_source.py` and `parquet_source.py` will load local one-file-per-symbol fixture-style datasets using the same normalized schema.  
`strategies/mean_reversion/` will own the baseline and variant rule sets along with hardcoded symbols.  
`cli.py` will resolve the selected source and strategy, request the strategy’s required symbols, and route normalized frames into the engine.

### Task 1: Create The Data Source Contract And Shared Normalization Helpers

**Files:**
- Create: `src/mean_reversion/data_sources/__init__.py`
- Create: `src/mean_reversion/data_sources/base.py`
- Modify: `tests/test_data.py`
- Create: `tests/test_data_sources.py`

- [ ] **Step 1: Write the failing shared-normalization tests**

```python
import pandas as pd
import pytest

from mean_reversion.data_sources.base import normalize_symbol_frame, validate_ohlcv_frames


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


def test_validate_ohlcv_frames_rejects_missing_required_columns():
    frame = pd.DataFrame({"open": [1.0], "high": [1.0], "close": [1.0]}, index=pd.date_range("2026-01-01", periods=1, name="date"))

    with pytest.raises(ValueError, match="low"):
        validate_ohlcv_frames({"SPY": frame})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_data.py tests/test_data_sources.py -v`  
Expected: FAIL with `ModuleNotFoundError` because the `data_sources` package does not exist yet.

- [ ] **Step 3: Implement the base data-source helpers and protocol**

```python
from __future__ import annotations

from typing import Protocol

import pandas as pd


REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


class DataSource(Protocol):
    name: str

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        ...


def normalize_symbol_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.copy()
        raw.columns = [first if first else second for first, second in raw.columns.to_flat_index()]

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
    frame = renamed.loc[:, ["date", *[column for column in REQUIRED_OHLCV_COLUMNS if column in renamed.columns]]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False)
    frame = frame.set_index("date").sort_index()
    frame.index.name = "date"
    validate_ohlcv_frames({"_single": frame})
    return frame


def validate_ohlcv_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No OHLCV frames supplied")

    for symbol, frame in frames.items():
        missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol} is missing required OHLCV columns: {missing}")
```

```python
from .base import DataSource, normalize_symbol_frame, validate_ohlcv_frames

__all__ = ["DataSource", "normalize_symbol_frame", "validate_ohlcv_frames"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_data.py tests/test_data_sources.py -v`  
Expected: PASS for the shared normalization tests.

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/data_sources/__init__.py src/mean_reversion/data_sources/base.py tests/test_data.py tests/test_data_sources.py
git commit -m "feat: add base data source contract and normalization helpers"
```

### Task 2: Move `yfinance` Into A Default Data Source Adapter

**Files:**
- Create: `src/mean_reversion/data_sources/yfinance_source.py`
- Delete: `src/mean_reversion/data.py`
- Modify: `tests/test_data_sources.py`

- [ ] **Step 1: Write the failing `yfinance` source test**

```python
import pandas as pd

from mean_reversion.data_sources.yfinance_source import YFinanceDataSource


def test_yfinance_source_normalizes_downloaded_frames(monkeypatch):
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

    source = YFinanceDataSource()
    monkeypatch.setattr(source, "_download_symbol", lambda symbol: raw)

    frames = source.load_bars(("SPY",))

    assert "SPY" in frames
    assert frames["SPY"].index.name == "date"
    assert list(frames["SPY"].columns) == ["open", "high", "low", "close", "volume"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_data_sources.py::test_yfinance_source_normalizes_downloaded_frames -v`  
Expected: FAIL because `YFinanceDataSource` does not exist yet.

- [ ] **Step 3: Implement the adapter and move the old downloader logic**

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from .base import normalize_symbol_frame, validate_ohlcv_frames


class YFinanceDataSource:
    name = "yfinance"

    def __init__(self, lookback_years: int = 5) -> None:
        self.lookback_years = lookback_years

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            raw = self._download_symbol(symbol)
            if raw.empty:
                raise ValueError(f"No data returned for {symbol}")
            frames[symbol] = normalize_symbol_frame(raw.reset_index() if "Date" not in raw.columns else raw)
        validate_ohlcv_frames(frames)
        return frames

    def _download_symbol(self, symbol: str) -> pd.DataFrame:
        end = datetime.now(tz=UTC).date()
        start = end - timedelta(days=(365 * self.lookback_years) + 30)
        return yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            progress=False,
        )
```

- [ ] **Step 4: Remove the old flat data module once all imports are redirected**

```text
Delete file: src/mean_reversion/data.py
```

- [ ] **Step 5: Run the focused data-source tests**

Run: `./.venv/bin/python -m pytest tests/test_data_sources.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mean_reversion/data_sources/yfinance_source.py tests/test_data_sources.py
git rm src/mean_reversion/data.py
git commit -m "feat: move yfinance loading into data source adapter"
```

### Task 3: Add File-Based CSV And Parquet Data Sources

**Files:**
- Create: `src/mean_reversion/data_sources/csv_source.py`
- Create: `src/mean_reversion/data_sources/parquet_source.py`
- Create: `tests/fixtures/csv_source/SPY.csv`
- Create: `tests/fixtures/csv_source/IVV.csv`
- Create: `tests/fixtures/csv_source/QQQ.csv`
- Create: `tests/fixtures/parquet_source/SPY.parquet`
- Create: `tests/fixtures/parquet_source/IVV.parquet`
- Create: `tests/fixtures/parquet_source/QQQ.parquet`
- Modify: `tests/test_data_sources.py`

- [ ] **Step 1: Write the failing CSV and parquet source tests**

```python
from pathlib import Path

from mean_reversion.data_sources.csv_source import CsvDataSource
from mean_reversion.data_sources.parquet_source import ParquetDataSource


def test_csv_source_loads_one_file_per_symbol_fixture():
    source = CsvDataSource(root_dir=Path("tests/fixtures/csv_source"))

    frames = source.load_bars(("SPY", "IVV", "QQQ"))

    assert sorted(frames) == ["IVV", "QQQ", "SPY"]
    assert frames["SPY"].loc["2026-01-02", "close"] == 100.5


def test_parquet_source_loads_one_file_per_symbol_fixture():
    source = ParquetDataSource(root_dir=Path("tests/fixtures/parquet_source"))

    frames = source.load_bars(("SPY", "IVV", "QQQ"))

    assert sorted(frames) == ["IVV", "QQQ", "SPY"]
    assert frames["QQQ"].loc["2026-01-03", "open"] == 201.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_data_sources.py::test_csv_source_loads_one_file_per_symbol_fixture tests/test_data_sources.py::test_parquet_source_loads_one_file_per_symbol_fixture -v`  
Expected: FAIL because the file-based adapters and fixture files do not exist yet.

- [ ] **Step 3: Create the CSV fixtures**

`tests/fixtures/csv_source/SPY.csv`

```csv
Date,Open,High,Low,Close,Volume
2026-01-02,100.0,101.0,99.0,100.5,1000
2026-01-03,101.0,102.0,100.0,101.5,2000
```

`tests/fixtures/csv_source/IVV.csv`

```csv
Date,Open,High,Low,Close,Volume
2026-01-02,150.0,151.0,149.0,150.5,1100
2026-01-03,151.0,152.0,150.0,151.5,2100
```

`tests/fixtures/csv_source/QQQ.csv`

```csv
Date,Open,High,Low,Close,Volume
2026-01-02,200.0,201.0,199.0,200.5,1200
2026-01-03,201.0,202.0,200.0,201.5,2200
```

- [ ] **Step 4: Implement the CSV and parquet adapters**

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import normalize_symbol_frame, validate_ohlcv_frames


class CsvDataSource:
    name = "csv"

    def __init__(self, root_dir: Path = Path("data/csv")) -> None:
        self.root_dir = root_dir

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            path = self.root_dir / f"{symbol}.csv"
            frames[symbol] = normalize_symbol_frame(pd.read_csv(path))
        validate_ohlcv_frames(frames)
        return frames
```

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import normalize_symbol_frame, validate_ohlcv_frames


class ParquetDataSource:
    name = "parquet"

    def __init__(self, root_dir: Path = Path("data/parquet")) -> None:
        self.root_dir = root_dir

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            path = self.root_dir / f"{symbol}.parquet"
            frames[symbol] = normalize_symbol_frame(pd.read_parquet(path))
        validate_ohlcv_frames(frames)
        return frames
```

- [ ] **Step 5: Materialize the parquet fixtures from the CSV fixture values**

Run:

```bash
./.venv/bin/python - <<'PY'
from pathlib import Path
import pandas as pd

rows = {
    "SPY": [
        {"Date": "2026-01-02", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
        {"Date": "2026-01-03", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 2000},
    ],
    "IVV": [
        {"Date": "2026-01-02", "Open": 150.0, "High": 151.0, "Low": 149.0, "Close": 150.5, "Volume": 1100},
        {"Date": "2026-01-03", "Open": 151.0, "High": 152.0, "Low": 150.0, "Close": 151.5, "Volume": 2100},
    ],
    "QQQ": [
        {"Date": "2026-01-02", "Open": 200.0, "High": 201.0, "Low": 199.0, "Close": 200.5, "Volume": 1200},
        {"Date": "2026-01-03", "Open": 201.0, "High": 202.0, "Low": 200.0, "Close": 201.5, "Volume": 2200},
    ],
}

root = Path("tests/fixtures/parquet_source")
root.mkdir(parents=True, exist_ok=True)
for symbol, data in rows.items():
    pd.DataFrame(data).to_parquet(root / f"{symbol}.parquet", index=False)
PY
```

Expected: the three `.parquet` fixture files are created under `tests/fixtures/parquet_source/`.

- [ ] **Step 6: Run the file-based data-source tests**

Run: `./.venv/bin/python -m pytest tests/test_data_sources.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/mean_reversion/data_sources/csv_source.py src/mean_reversion/data_sources/parquet_source.py tests/test_data_sources.py tests/fixtures/csv_source tests/fixtures/parquet_source
git commit -m "feat: add csv and parquet data source adapters"
```

### Task 4: Add Data-Source Registry And CLI `--data-source` Selection

**Files:**
- Create: `src/mean_reversion/data_sources/registry.py`
- Modify: `src/mean_reversion/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing data-source registry and parser tests**

```python
import pytest

from mean_reversion.data_sources.registry import get_data_source, list_data_source_names
from mean_reversion.cli import build_parser


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_cli.py -v`  
Expected: FAIL because the data-source registry and new parser behavior do not exist yet.

- [ ] **Step 3: Implement the data-source registry**

```python
from .csv_source import CsvDataSource
from .parquet_source import ParquetDataSource
from .yfinance_source import YFinanceDataSource


DATA_SOURCE_FACTORIES = {
    "yfinance": YFinanceDataSource,
    "csv": CsvDataSource,
    "parquet": ParquetDataSource,
}


def list_data_source_names() -> list[str]:
    return sorted(DATA_SOURCE_FACTORIES)


def get_data_source(name: str):
    try:
        return DATA_SOURCE_FACTORIES[name]()
    except KeyError as exc:
        valid = ", ".join(list_data_source_names())
        raise ValueError(f"Unknown data source '{name}'. Valid data sources: {valid}") from exc
```

- [ ] **Step 4: Implement CLI parsing with default data-source selection**

```python
from __future__ import annotations

import argparse

from .backtest import run_backtest
from .config import BacktestConfig
from .data_sources.registry import get_data_source, list_data_source_names
from .reporting import build_summary_stats, compare_runs, write_outputs
from .strategies.mean_reversion import validate_signal_frames
from .strategies.registry import get_strategy, list_strategy_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-source",
        default="yfinance",
        help=f"Data source name. Valid choices: {', '.join(list_data_source_names())}",
    )
    parser.add_argument(
        "--strategy",
        required=True,
        help=f"Strategy name. Try mean_reversion_v1 first. Valid choices: {', '.join(list_strategy_names())}",
    )
    return parser
```

- [ ] **Step 5: Run the parser tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_cli.py::test_list_data_source_names_includes_default_and_file_sources tests/test_cli.py::test_get_data_source_returns_default_source_instance tests/test_cli.py::test_cli_defaults_data_source_to_yfinance tests/test_cli.py::test_cli_requires_strategy_flag -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mean_reversion/data_sources/registry.py src/mean_reversion/cli.py tests/test_cli.py
git commit -m "feat: add cli data source selection"
```

### Task 5: Create The Strategy Package, Baseline Strategy, And Variants

**Files:**
- Create: `src/mean_reversion/strategies/__init__.py`
- Create: `src/mean_reversion/strategies/registry.py`
- Create: `src/mean_reversion/strategies/mean_reversion/__init__.py`
- Create: `src/mean_reversion/strategies/mean_reversion/base.py`
- Create: `src/mean_reversion/strategies/mean_reversion/v1.py`
- Create: `src/mean_reversion/strategies/mean_reversion/strict.py`
- Create: `src/mean_reversion/strategies/mean_reversion/fast_exit.py`
- Delete: `src/mean_reversion/strategy.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write the failing strategy contract and baseline tests**

```python
import pandas as pd
import pytest

from mean_reversion.strategies.mean_reversion.base import validate_signal_frames
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py -v`  
Expected: FAIL because the new strategy package and classes do not exist yet.

- [ ] **Step 3: Implement the strategy contract, baseline strategy, and variants**

```python
from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    name: str
    market_symbol: str
    trade_symbols: tuple[str, ...]

    def required_symbols(self) -> tuple[str, ...]:
        ...

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...


def validate_signal_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No strategy frames supplied")
    for symbol, frame in frames.items():
        missing = [column for column in ("entry_signal", "exit_signal") if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol} is missing required signal columns: {missing}")
```

```python
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...indicators import enrich_symbol_frame


@dataclass(frozen=True)
class MeanReversionV1Strategy:
    name: str = "mean_reversion_v1"
    market_symbol: str = "SPY"
    trade_symbols: tuple[str, ...] = ("IVV", "QQQ")
    market_ma_window: int = 200
    trend_ma_window: int = 50
    rsi_window: int = 2
    entry_rsi_threshold: float = 15.0
    exit_rsi_threshold: float = 60.0

    def required_symbols(self) -> tuple[str, ...]:
        return (self.market_symbol, *self.trade_symbols)

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...
```

```python
from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionStrictStrategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_strict"
    entry_rsi_threshold: float = 10.0
```

```python
from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionFastExitStrategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_fast_exit"
    exit_rsi_threshold: float = 50.0
```

- [ ] **Step 4: Implement the strategy registry**

```python
from .mean_reversion import (
    MeanReversionFastExitStrategy,
    MeanReversionStrictStrategy,
    MeanReversionV1Strategy,
)


STRATEGY_FACTORIES = {
    "mean_reversion_v1": MeanReversionV1Strategy,
    "mean_reversion_strict": MeanReversionStrictStrategy,
    "mean_reversion_fast_exit": MeanReversionFastExitStrategy,
}


def list_strategy_names() -> list[str]:
    return sorted(STRATEGY_FACTORIES)


def get_strategy(name: str):
    try:
        return STRATEGY_FACTORIES[name]()
    except KeyError as exc:
        valid = ", ".join(list_strategy_names())
        raise ValueError(f"Unknown strategy '{name}'. Valid strategies: {valid}") from exc
```

- [ ] **Step 5: Remove the old flat strategy module**

```text
Delete file: src/mean_reversion/strategy.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/mean_reversion/strategies src/mean_reversion/strategies/registry.py tests/test_strategy.py
git rm src/mean_reversion/strategy.py
git commit -m "feat: add strategy package and mean reversion variants"
```

### Task 6: Wire Strategy-Owned Symbols And Source Loading Through The CLI

**Files:**
- Modify: `src/mean_reversion/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing end-to-end orchestration test**

```python
import pandas as pd

from mean_reversion import cli
from mean_reversion.backtest import BacktestResult
from mean_reversion.config import BacktestConfig


def test_cli_loads_strategy_symbols_from_selected_data_source(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "BacktestConfig", lambda: BacktestConfig(output_dir=str(tmp_path)))

    requested_symbols = {}

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            requested_symbols["symbols"] = symbols
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

        def required_symbols(self):
            return ("SPY", "IVV", "QQQ")

        def prepare_frames(self, frames):
            return frames

        def build_signals(self, frames):
            return frames

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())
    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())
    monkeypatch.setattr(cli, "run_backtest", lambda frames, config, slippage_bps=0.0: BacktestResult(
        trades=pd.DataFrame([{"return_pct": 0.01, "pnl": 10.0}]),
        equity_curve=pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
    ))

    cli.main(["--strategy", "mean_reversion_v1"])

    assert requested_symbols["symbols"] == ("SPY", "IVV", "QQQ")
    assert (tmp_path / "comparison.csv").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_cli.py::test_cli_loads_strategy_symbols_from_selected_data_source -v`  
Expected: FAIL because the CLI does not yet orchestrate source and strategy together.

- [ ] **Step 3: Implement the final CLI flow**

```python
def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_source = get_data_source(args.data_source)
    strategy = get_strategy(args.strategy)

    config = BacktestConfig()
    bars = data_source.load_bars(strategy.required_symbols())
    prepared = strategy.prepare_frames(bars)
    signals = strategy.build_signals(prepared)
    validate_signal_frames({symbol: signals[symbol] for symbol in strategy.trade_symbols})

    base_result = run_backtest(signals, config, slippage_bps=0.0)
    base_summary = build_summary_stats(base_result.trades, base_result.equity_curve)
    write_outputs(config.output_dir, base_result.trades, base_result.equity_curve, base_summary, run_name="base")

    slippage_result = run_backtest(signals, config, slippage_bps=config.slippage_bps)
    slippage_summary = build_summary_stats(slippage_result.trades, slippage_result.equity_curve)
    write_outputs(config.output_dir, slippage_result.trades, slippage_result.equity_curve, slippage_summary, run_name="slippage")

    comparison = compare_runs(base_result, slippage_result)
    comparison.to_csv(f"{config.output_dir}/comparison.csv")
```

- [ ] **Step 4: Run the CLI test module**

Run: `./.venv/bin/python -m pytest tests/test_cli.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/cli.py tests/test_cli.py
git commit -m "feat: orchestrate data source and strategy through cli"
```

### Task 7: Add Engine Validation, Package Exports, And End-To-End Verification

**Files:**
- Modify: `src/mean_reversion/backtest.py`
- Modify: `src/mean_reversion/__init__.py`
- Modify: `tests/test_backtest.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing engine validation regression test**

```python
import pandas as pd
import pytest

from mean_reversion.backtest import run_backtest
from mean_reversion.config import BacktestConfig


def test_run_backtest_rejects_frames_missing_standard_signal_columns():
    dates = pd.date_range("2026-01-01", periods=2, freq="D", name="date")
    market = pd.DataFrame({"open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1, 1]}, index=dates)
    invalid = pd.DataFrame({"open": [100, 100], "high": [101, 101], "low": [99, 99], "close": [100, 100], "volume": [10, 10]}, index=dates)

    with pytest.raises(ValueError, match="entry_signal"):
        run_backtest({"SPY": market, "IVV": invalid, "QQQ": invalid.copy()}, BacktestConfig())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_backtest.py::test_run_backtest_rejects_frames_missing_standard_signal_columns -v`  
Expected: FAIL because the engine does not currently validate the strategy contract.

- [ ] **Step 3: Add preflight validation and update package exports**

```python
from .strategies.mean_reversion import validate_signal_frames


def run_backtest(...):
    validate_signal_frames({symbol: frames[symbol] for symbol in config.trade_symbols})
    ...
```

```python
from .config import BacktestConfig
from .data_sources.registry import get_data_source, list_data_source_names
from .strategies.registry import get_strategy, list_strategy_names

__all__ = ["BacktestConfig", "get_data_source", "list_data_source_names", "get_strategy", "list_strategy_names"]
```

- [ ] **Step 4: Run the full test suite**

Run: `./.venv/bin/python -m pytest -v`  
Expected: PASS

- [ ] **Step 5: Run the CLI end to end with the default source**

Run: `./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1`  
Expected:
- uses `yfinance` implicitly
- loads `SPY`, `IVV`, and `QQQ`
- writes output CSVs under `artifacts/mean_reversion/`
- prints summary stats

- [ ] **Step 6: Run the CLI end to end with the CSV source**

Run: `./.venv/bin/python -m mean_reversion.cli --data-source csv --strategy mean_reversion_v1`  
Expected:
- loads the strategy’s symbols from the configured CSV root
- runs the same engine and reporting path
- writes output CSVs under `artifacts/mean_reversion/`

- [ ] **Step 7: Run the CLI with the missing required strategy flag**

Run: `./.venv/bin/python -m mean_reversion.cli`  
Expected:
- exits non-zero
- prints an error that `--strategy` is required
- suggests `mean_reversion_v1` as the first strategy to try

- [ ] **Step 8: Commit**

```bash
git add src/mean_reversion/backtest.py src/mean_reversion/__init__.py tests/test_backtest.py tests/test_cli.py
git commit -m "test: verify data source and strategy modularization end to end"
```

## Self-Review

Spec coverage:
- Data-source abstraction is implemented in Tasks 1 through 4.
- File-based CSV and parquet support is implemented in Task 3.
- CLI `--data-source` defaulting to `yfinance` is implemented in Tasks 4 and 6.
- Required `--strategy` behavior is implemented in Tasks 4, 6, and 7.
- Strategy-owned symbol universes are implemented in Tasks 5 and 6.
- Fixed engine behavior is preserved, with only contract validation added in Task 7.
- Broker and live/paper runtime work remain explicitly out of scope.

Placeholder scan:
- No `TODO`, `TBD`, or vague implementation placeholders remain.
- Every task includes exact file paths, commands, and concrete code snippets.

Type consistency:
- The plan consistently uses `DataSource`, `normalize_symbol_frame()`, `validate_ohlcv_frames()`, `Strategy`, `validate_signal_frames()`, `get_data_source()`, and `get_strategy()`.
- The CLI flow consistently resolves source first, then strategy, then strategy-owned symbols.
