# Data Source And Strategy Modularization Design

**Date:** 2026-04-18

**Status:** Proposed

## Goal

Refactor the current backtester so it supports both pluggable data sources and pluggable strategies, while keeping the execution engine, portfolio rules, and reporting fixed. The first version must support CLI-driven data-source selection, file-based and API-based sources, required CLI strategy selection, and strategies that hardcode their own symbol universe.

## Why This Change

The current codebase assumes one data backend (`yfinance`) and one built-in strategy layout. That is too narrow for the stated use case:

- US market backtesting
- China market backtesting
- remote vendor APIs
- local file-based research data such as CSV and parquet

If only strategy modularization is added, the code will still be constrained by a single data-fetching path. The right boundary for this stage is two seams:

1. data-source adapters
2. strategy modules

The engine should stay stable and consume normalized bars plus standard signal columns.

## Scope

### In Scope

- Add a data-source abstraction layer
- Add a strategy abstraction layer
- Select data source from the CLI with `yfinance` as the default
- Require `--strategy` from the CLI
- Support file-based data sources from the start
- Keep symbols hardcoded inside each strategy for now
- Normalize all sources into the same daily OHLCV frame structure
- Keep the current execution engine, sizing rules, stop logic, and reporting flow

### Out of Scope

- Runtime symbol selection from CLI or config
- Multiple strategies in one portfolio
- Swappable sizing policies
- Swappable portfolio models
- Broker API execution
- Live or paper trading runtime
- Cross-market symbol-role abstraction

## Chosen Approach

Use Option 1 from the expanded design discussion:

- pluggable data sources
- pluggable strategies
- fixed engine

The data source is responsible for fetching or loading bars and normalizing them. The strategy is responsible for declaring which symbols it needs, preparing indicator-enriched frames, and producing standard `entry_signal` / `exit_signal` columns. The engine remains responsible for execution simulation, stops, slippage, cash accounting, and reporting.

This keeps the current working simulator intact while opening the two extension points that matter most for the next stage of research.

## High-Level Architecture

```text
python -m mean_reversion.cli \
  --data-source <name> \
  --strategy <name>

            |
            v
   +-------------------+
   | Data Source       |
   | Registry          |
   +-------------------+
            |
            v
   +-------------------+
   | Data Source       |
   | Adapter           |
   | - yfinance        |
   | - csv             |
   | - parquet         |
   | - china vendor    |
   +-------------------+
            |
            v
   +-------------------+
   | Normalized Bars   |
   +-------------------+
            |
            v
   +-------------------+
   | Strategy Registry |
   +-------------------+
            |
            v
   +-------------------+
   | Strategy          |
   | - symbols         |
   | - indicator prep  |
   | - signal building |
   +-------------------+
            |
            v
   +-------------------+
   | Fixed Engine      |
   +-------------------+
            |
            v
   +-------------------+
   | Reporting         |
   +-------------------+
```

## Responsibilities By Layer

### Data Source Layer

Owns:

- source-specific symbol handling
- API fetch logic
- CSV/parquet loading
- vendor column normalization
- normalized daily OHLCV output

Does not own:

- indicator logic
- entry and exit rules
- portfolio simulation

### Strategy Layer

Owns:

- strategy name
- hardcoded market symbol
- hardcoded trade symbols
- indicator preparation
- signal generation

Does not own:

- broker or vendor fetch details
- cash accounting
- fills, slippage, or stops

### Engine Layer

Owns:

- position lifecycle
- next-open fills
- low-based stop approximation
- max positions
- cash reserve logic
- trade log and equity accounting

Does not own:

- source backend specifics
- strategy-specific indicator logic
- symbol selection policy beyond using the strategy-provided frames

## Package Structure

```text
src/mean_reversion/
  backtest.py
  cli.py
  config.py
  indicators.py
  reporting.py

  data_sources/
    __init__.py
    base.py
    registry.py
    yfinance_source.py
    csv_source.py
    parquet_source.py
    china_vendor.py

  strategies/
    __init__.py
    registry.py

    mean_reversion/
      __init__.py
      base.py
      v1.py
      strict.py
      fast_exit.py
```

### Notes On The Structure

- `data_sources/base.py`
  Defines the source contract and shared validation helpers.
- `data_sources/registry.py`
  Maps CLI names to concrete source adapters.
- `yfinance_source.py`
  Becomes the default source and absorbs the current downloader logic.
- `csv_source.py` and `parquet_source.py`
  Load local daily-bar data and normalize it into the common structure.
- `china_vendor.py`
  Can start as a stub or placeholder if the exact vendor is not chosen yet, but the interface should reserve a slot for that family.
- `strategies/mean_reversion/`
  Keeps internal organization by strategy family while CLI names stay flat and simple.

## Normalized Data Contract

Every data source must return:

```python
dict[str, pd.DataFrame]
```

Each frame must contain:

- date index
- `open`
- `high`
- `low`
- `close`
- `volume`

Each frame must also be:

- daily bars only
- sorted by date
- normalized to the same schema regardless of source

The engine should not care whether the bars came from Yahoo, a broker export, a parquet dataset, or a China-market vendor. It should only care that the returned frames satisfy the normalized contract.

## Symbol Ownership

For this first version, symbols are hardcoded inside each strategy.

Example:

- `MeanReversionV1Strategy`
  - market symbol: `SPY`
  - trade symbols: `IVV`, `QQQ`

That means runtime flow becomes:

```text
CLI picks strategy
  -> strategy declares required symbols
  -> selected data source loads those symbols
  -> strategy prepares signals
  -> engine runs
```

This is intentionally simpler than a reusable cross-market symbol-role mapping system. It keeps strategy modules market-specific for now, which is acceptable at this stage.

## Strategy Contract

Recommended interface:

```python
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
```

Recommended semantics:

- `required_symbols()`
  Returns the exact symbols the selected data source must load.
- `prepare_frames(...)`
  Adds indicators and derived columns.
- `build_signals(...)`
  Returns signalized frames with the standard engine contract.

Required engine-facing columns for tradable symbols:

- `entry_signal`
- `exit_signal`

## Data Source Contract

Recommended interface:

```python
class DataSource(Protocol):
    name: str

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        ...
```

Recommended semantics:

- `load_bars(...)`
  Fetches or loads raw source data for the requested symbols and returns normalized daily OHLCV frames.

File-based adapters may require additional configuration such as a directory path or file mapping. That configuration can live in source-specific constructor defaults for now instead of adding a broad CLI surface immediately.

## CLI Behavior

Examples:

```text
python -m mean_reversion.cli --strategy mean_reversion_v1
python -m mean_reversion.cli --data-source yfinance --strategy mean_reversion_v1
python -m mean_reversion.cli --data-source csv --strategy mean_reversion_v1
python -m mean_reversion.cli --data-source parquet --strategy mean_reversion_strict
```

Expected behavior:

- `--strategy` is required
- omitting `--strategy` fails clearly and suggests `mean_reversion_v1` as the first strategy to try
- `--data-source` is optional
- omitting `--data-source` defaults to `yfinance`
- invalid strategy names fail with valid choices
- invalid data-source names fail with valid choices

## Data Flow

```text
CLI
  -> resolve data source
  -> resolve strategy
  -> strategy.required_symbols()
  -> data_source.load_bars(symbols)
  -> strategy.prepare_frames(...)
  -> strategy.build_signals(...)
  -> fixed engine
  -> reporting
```

This is the critical difference from the prior strategy-only design: the strategy does not receive whatever the downloader happened to fetch. Instead, the selected strategy declares its symbol universe first, and the selected source is responsible for supplying those bars.

## Backward Compatibility

The first built strategy should preserve current behavior:

- source default: `yfinance`
- strategy: `mean_reversion_v1`
- market symbol: `SPY`
- trade symbols: `IVV`, `QQQ`
- same entry, exit, stop, and portfolio rules as the current implementation

That means this command should remain equivalent to the current baseline run:

```text
python -m mean_reversion.cli --strategy mean_reversion_v1
```

## File-Based Source Expectations

The first file-based adapters should favor explicit conventions over magic autodetection.

Reasonable first-version assumptions:

- CSV source:
  one file per symbol with expected columns like `date,open,high,low,close,volume`
- parquet source:
  one file per symbol or one partitioned dataset with the same normalized column names

If a file-based adapter needs source-specific root paths or symbol-to-file mapping, keep those rules simple and documented in code rather than building a full metadata system in the first pass.

## Error Handling

The refactor should make these failures explicit:

- unknown data source
- unknown strategy
- source cannot load one or more required symbols
- loaded frames missing required OHLCV columns
- strategy output missing required signal columns
- frames not aligned or not daily-bar shaped when alignment is required by the engine

All of these should fail before the backtest loop starts.

## Testing Strategy

Coverage should include:

- data-source registry resolves valid names
- strategy registry resolves valid names
- CLI default data source is `yfinance`
- CLI requires `--strategy`
- `yfinance` source normalization still works
- CSV source loads normalized data from fixture files
- parquet source loads normalized data from fixture files
- baseline strategy reproduces the current signal behavior
- at least one strategy variant differs from baseline
- engine validation still fails cleanly on missing signal columns

## Path To Future Growth

This design deliberately leaves several future steps open without implementing them now:

- China-market strategy families under `strategies/china/`
- additional data vendors under `data_sources/`
- later broker execution and paper/live runtime
- later symbol-role abstraction if the same strategy family should run across multiple universes

The portable seams from this refactor are:

```text
source -> normalized bars
strategy -> signalized frames
engine -> simulation results
```

That is enough structure for the next stage without turning the project into a framework prematurely.

## Recommendation

Proceed with a combined refactor that introduces:

- a `data_sources/` package with registry and normalized contract
- a `strategies/` package with registry and family-based layout
- CLI `--data-source` selection defaulting to `yfinance`
- CLI `--strategy` selection as a required argument
- strategy-owned hardcoded symbol universes

Do not add runtime symbol configuration, portfolio-policy abstraction, or broker integration in the same change.
