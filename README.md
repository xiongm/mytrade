# MyTrade

A research-first backtesting project for systematic mean reversion strategies across equities and crypto.

The current codebase is designed around three ideas:

- keep strategy logic modular
- keep data sources swappable
- keep research outputs easy to review

Right now the repo supports:

- US equity / ETF mean reversion variants
- daily crypto mean reversion variants
- `yfinance`, CSV, and Parquet data sources
- HTML and artifact-based result bundles for review

## Status

This is currently a **research and signal-evaluation codebase**, not a production live-trading system.

It is best suited for:

- strategy iteration
- backtesting
- comparing strategy variants
- generating structured results for human review

It does **not** yet include:

- broker/exchange execution integration
- paper trading
- live order management
- position reconciliation against a live venue

## Features

### Strategy families

- Equity mean reversion family under `src/mean_reversion/strategies/mean_reversion/`
- Crypto mean reversion family under `src/mean_reversion/strategies/mean_reversion_crypto/`

### Data sources

- `yfinance`
- `csv`
- `parquet`

### Result outputs

Each run writes:

- base backtest outputs
- slippage-adjusted outputs
- comparison metrics
- a structured result bundle under `results/`
- a reviewable HTML report
- a global results index

### Current crypto support

Crypto strategies are daily-bar based and currently support fractional sizing through a config-gated path so high-priced spot assets like BTC can be researched without changing equity whole-share behavior.

## Repository Layout

```text
src/mean_reversion/
  backtest.py                 core signal-driven backtest engine
  cli.py                      command-line entrypoint
  config.py                   backtest configuration
  indicators.py               RSI / moving-average enrichment helpers
  reporting.py                summary stats and CSV output helpers
  data_sources/               yfinance / csv / parquet loaders
  strategies/
    mean_reversion/           equity strategy family
    mean_reversion_crypto/    crypto strategy family

tests/                        pytest suite
results/                      generated result bundles and latest views
artifacts/                    generated flat output artifacts
docs/                         handoff docs, specs, and implementation plans
```

## Requirements

- Python `3.12+`
- `numpy`
- `pandas`
- `yfinance`
- `pytest` for development

The project metadata lives in [pyproject.toml](./pyproject.toml).

## Quick Start

### 1. Clone and enter the repo

```bash
git clone git@github.com:xiongm/mytrade.git
cd mytrade
```

### 2. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e .
pip install -e ".[dev]"
```

### 4. Run the test suite

```bash
python -m pytest -q
```

## Running Backtests

Run commands from the **repo root**.

General form:

```bash
python -m mean_reversion.cli --strategy <strategy-name> [--data-source <source>]
```

Default data source:

- `yfinance`

### Example: baseline equity strategy

```bash
python -m mean_reversion.cli --strategy mean_reversion_v1
```

### Example: crypto ETH strategy

```bash
python -m mean_reversion.cli --strategy mean_reversion_crypto_v1
```

### Example: crypto BTC strategy

```bash
python -m mean_reversion.cli --strategy mean_reversion_crypto_btc_v1
```

### Example: CSV or Parquet data

```bash
python -m mean_reversion.cli --strategy mean_reversion_v1 --data-source csv
python -m mean_reversion.cli --strategy mean_reversion_v1 --data-source parquet
```

## Available Strategy Names

### Equity

- `mean_reversion_v1`
- `mean_reversion_strict`
- `mean_reversion_fast_exit`
- `mean_reversion_exit_70`
- `mean_reversion_entry_20`
- `mean_reversion_entry_10`
- `mean_reversion_exit_6`

### Crypto

- `mean_reversion_crypto_v1`
  - current shape: `BTC-USD` market anchor, `ETH-USD` traded
- `mean_reversion_crypto_btc_v1`
  - current shape: BTC-only, fractional sizing enabled

## How the Backtest Works

At a high level:

1. Load daily OHLCV bars from a selected data source
2. Let the selected strategy prepare indicator-enriched frames
3. Let the strategy produce `entry_signal` and `exit_signal`
4. Run the shared backtest engine
5. Write base, slippage, comparison, and result-bundle outputs

The engine is shared across markets. Market-specific assumptions live in strategy families.

## Position Sizing Notes

### Equities

Equity strategies use whole-share sizing by default.

### Crypto

Crypto strategies can opt into fractional sizing through:

- `allow_fractional_shares = True`

This is currently enabled for the crypto family so high-priced spot assets like BTC can be traded in research without changing existing equity behavior.

## Results and Reports

A run writes structured outputs under:

```text
results/<strategy>/<market>__<instrument>__<source>/
```

Important locations:

- `bundles/` - canonical result bundles
- `history/` - historical run records
- `latest/` - latest run view for that strategy/source bucket
- `results/index.html` - global results portal

Each result bundle includes:

- `run_meta.json`
- `summary.json`
- `summary.md`
- `charts.json`
- `llm_review.json`
- `trades.csv`
- `equity_curve.csv`
- `comparison.csv`
- `report.html`

The report is designed to make strategy review faster, with sections for:

- performance summary
- run setup
- trade outcome distribution
- trade behavior
- portfolio path
- full trade log

## Data Source Notes

### `yfinance`

- easiest default for quick research
- supports equity/ETF tickers
- supports crypto symbols like `BTC-USD` and `ETH-USD`

### `csv` / `parquet`

Useful when:

- you want reproducible local datasets
- you want to test alternate markets
- you want to control the input data rather than rely on an online provider

The engine expects normalized daily OHLCV bars.

## Development

### Run tests

```bash
python -m pytest -q
```

### Run a focused test

```bash
python -m pytest tests/test_strategy.py -q
```

### Common workflow

```bash
python -m pytest -q
python -m mean_reversion.cli --strategy mean_reversion_v1
open results/mean_reversion_v1/us__etf__yfinance/latest/report.html
```

## Design Principles

This repo intentionally favors:

- separate strategy families over fake universal abstractions
- reusable engine layers over duplicated backtest logic
- explicit result artifacts over notebook-only workflows
- incremental expansion over premature live-trading complexity

In practice that means:

- equity and crypto can share the engine
- equity and crypto do **not** need to share the same strategy assumptions

## Current Limitations

- daily-bar strategies only
- no live execution layer
- no paper trading integration
- no exchange precision / lot-size modeling beyond current research assumptions
- no portfolio-state aware signal-generator mode yet
- no intraday strategy support

## Roadmap

Likely next steps:

- daily signal generator mode for manual execution
- paper/live trading integration behind a separate execution layer
- richer crypto strategy variants
- more data-source adapters
- better position and signal state management for live workflows

The intended progression is:

- research and backtest
- daily signal generation
- manual execution
- optional future automation

## Notes on Signal Generation

This codebase is a good fit for low-frequency signal generation.

A practical next operating model is:

- run once per day after the relevant daily bar closes
- review generated instructions
- execute manually in your broker or exchange terminal

That keeps the strategy systematic without requiring full automation.

## License

No license has been added yet. If you intend to open-source this project for external use, add an explicit license file.
