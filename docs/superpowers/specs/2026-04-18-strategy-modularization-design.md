# Strategy Modularization Design

**Date:** 2026-04-18

**Status:** Proposed

## Goal

Refactor the current backtester so strategy logic is swappable via a CLI flag while keeping the execution engine, portfolio rules, and reporting fixed. The immediate target is support for simple rule variants with hardcoded defaults, not a fully modular trading platform.

## Why This Change

The current codebase hardcodes the mean reversion rules in [`src/mean_reversion/strategy.py`](/Users/xm401/projects/mytrade/src/mean_reversion/strategy.py), and the backtest engine in [`src/mean_reversion/backtest.py`](/Users/xm401/projects/mytrade/src/mean_reversion/backtest.py) assumes that exact signal shape. That is workable for one strategy, but it makes future rule variants awkward because each change risks touching shared engine code.

This refactor should make these workflows cheap:

- run the current strategy by name from the CLI
- add a stricter or looser mean reversion variant without modifying the engine
- keep portfolio sizing, stops, cash rules, and reporting stable while comparing strategy rules
- preserve a clean path to reuse strategy logic later in paper or live trading

## Scope

### In Scope

- Introduce a strategy abstraction layer
- Select strategies via CLI flag such as `--strategy mean_reversion_v1`
- Give each strategy its own hardcoded defaults
- Move the current strategy logic into a strategy module under a new `strategies/` package
- Keep the current backtest engine as the single execution path
- Keep the current portfolio constraints, slippage behavior, and reporting model

### Out of Scope

- CLI parameter overrides such as `--entry-rsi 10`
- Multiple strategies running in one portfolio
- Swappable sizing policies
- Swappable portfolio models
- Vendor API integration
- Live or paper trading runtime
- Plugin discovery or dynamic loading from outside the codebase

## Chosen Approach

Use Option 1: make only the strategy layer swappable.

The architecture will keep one fixed backtest engine and one fixed execution model. Strategy modules will be responsible for preparing indicator-enriched frames and producing standard signal columns. The engine will consume a stable signal contract and will not know or care how those signals were generated.

This is the smallest refactor that solves the immediate problem without prematurely building a framework around sizing, portfolio coordination, or broker execution.

## High-Level Architecture

```text
python -m mean_reversion.cli --strategy <name>
                 |
                 v
         +-------------------+
         | Strategy Registry |
         +-------------------+
                 |
                 v
         +-------------------+
         | Selected Strategy |
         | - hardcoded rules |
         | - indicator prep  |
         | - signal building |
         +-------------------+
                 |
                 v
         +-------------------+
         | Fixed Engine      |
         | - next-open fills |
         | - stop handling   |
         | - cash rules      |
         | - max positions   |
         +-------------------+
                 |
                 v
         +-------------------+
         | Reporting         |
         +-------------------+
```

## Package Structure

The refactor should move the project toward this layout:

```text
src/mean_reversion/
  backtest.py
  cli.py
  config.py
  data.py
  indicators.py
  reporting.py

  strategies/
    __init__.py
    base.py
    registry.py
    mean_reversion_v1.py
    mean_reversion_strict.py
    mean_reversion_fast_exit.py
```

### Responsibilities

- `backtest.py`
  Keeps the execution loop, portfolio state, stops, slippage, cash tracking, and trade accounting.
- `cli.py`
  Parses `--strategy`, resolves it through the registry, downloads data, prepares frames, runs the engine, and writes reports.
- `indicators.py`
  Remains a shared library of reusable indicator helpers.
- `strategies/base.py`
  Defines the strategy contract.
- `strategies/registry.py`
  Maps CLI names to strategy implementations.
- `strategies/mean_reversion_v1.py`
  Contains the current ETF mean reversion logic as the baseline strategy.
- Other files in `strategies/`
  Contain named rule variants with different hardcoded defaults or rule details.

## Strategy Contract

The strategy boundary should stay narrow so it can later be reused outside backtesting.

Recommended interface:

```python
class Strategy(Protocol):
    name: str

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...
```

### Contract Semantics

- `prepare_frames(...)`
  Adds the indicators and derived columns required by the strategy.
- `build_signals(...)`
  Returns frames containing the standard execution columns expected by the engine.

The fixed engine contract should remain:

- `entry_signal`
- `exit_signal`

If needed later, the strategy can add extra informational columns for debugging or reporting, but the engine should depend only on the standard signal columns plus price data.

## CLI Behavior

The CLI should change from one implicit strategy to an explicit strategy selection model.

Examples:

```text
python -m mean_reversion.cli --strategy mean_reversion_v1
python -m mean_reversion.cli --strategy mean_reversion_strict
python -m mean_reversion.cli --strategy mean_reversion_fast_exit
```

Expected CLI behavior:

- `--strategy` is required unless a clear default is intentionally chosen
- invalid strategy names fail with a helpful error listing valid strategies
- each strategy runs with its own hardcoded defaults
- no per-run threshold overrides are supported in this phase

Recommended default behavior:

- allow a default of `mean_reversion_v1` for convenience
- still expose `--strategy` so explicit selection is easy and scriptable

## Data Flow

The runtime flow should become:

```text
CLI
  -> select strategy from registry
  -> download and normalize bars
  -> strategy.prepare_frames(...)
  -> strategy.build_signals(...)
  -> fixed backtest engine
  -> reporting
```

This keeps the engine generic within the current scope. The engine receives signalized daily-bar frames and applies execution/portfolio logic. The strategy owns indicator prep and signal definition.

## Backward Compatibility

The baseline behavior should remain the current strategy rules:

- market filter: `SPY.close > SPY.200DMA`
- entry filter for `IVV` and `QQQ`:
  - `close > 50DMA`
  - last 2 closes down
  - `RSI(2) < 15`
- exit when:
  - `RSI(2) > 60`
  - 4 trading days held
  - 3% stop approximation using daily low

The initial strategy module should encode exactly those defaults so the baseline CLI run continues to match the current backtest behavior.

## Error Handling

The refactor should make failure modes explicit:

- unknown strategy name:
  raise a user-facing CLI error with valid strategy names
- strategy output missing required signal columns:
  raise a validation error before the engine runs
- missing required symbols or indicator columns:
  fail fast in strategy preparation rather than inside the engine loop

This is important because once strategies are modular, the engine should not silently assume every module returns valid frames.

## Testing Strategy

Tests should shift from “one strategy file exists” to “the engine can run any strategy that satisfies the contract.”

New coverage should include:

- registry resolves known strategy names
- CLI selects the requested strategy
- baseline strategy reproduces the current signal behavior
- at least one variant strategy produces a different signal profile
- engine validation fails cleanly if a strategy omits `entry_signal` or `exit_signal`
- existing engine tests continue passing unchanged once fed standard signal frames

## Path To Paper/Live Trading Later

This refactor is not a broker integration project, but it should preserve a useful seam for one later.

The reusable part is the strategy layer:

```text
market data -> strategy -> intent/signal
```

That means later work can reuse strategy modules in:

- backtest runner
- paper-trading runner
- live-trading runner

without reusing the current backtest engine as-is. The engine remains a simulation engine; the strategy contract becomes the portable part.

## Tradeoffs

### Benefits

- cheap addition of simple rule variants
- no need to rewrite engine logic for every new strategy
- CLI-driven comparison workflow
- better separation between rules and execution
- cleaner long-term path toward paper/live reuse

### Costs

- one more layer of indirection in the codebase
- some duplication across simple strategy variants with hardcoded defaults
- no flexibility yet for sizing or multi-strategy portfolios

These costs are acceptable because they directly support the current need without over-generalizing.

## Open Decisions Resolved

- Strategy switching mechanism:
  CLI flag
- Strategy parameterization:
  hardcoded defaults inside each strategy
- Scope level:
  Option 1 only, not full policy modularization

## Recommendation

Proceed with a focused refactor that introduces:

- a `strategies/` package
- a small strategy interface
- a strategy registry
- CLI `--strategy` selection
- extraction of the current strategy into `mean_reversion_v1`

Do not change sizing, portfolio rules, execution semantics, or reporting structure in the same refactor unless required by the new strategy boundary.
