# Crypto Strategy Family Design

## Purpose

Add support for crypto mean reversion research without forcing crypto assumptions into the existing equity strategy family.

The goal is to reuse the current backtest engine, indicators, results pipeline, and CLI workflow while introducing a separate crypto-specific strategy family that can evolve on its own market structure.

## Core Decision

Crypto should not be implemented as a small variant of the existing equity `mean_reversion` strategies.

Instead:

- keep the current equity strategy family intact
- add a parallel crypto strategy family
- share only the generic engine and support layers

This preserves clean boundaries and avoids premature abstraction across markets with different structure.

## Scope

This design covers:

- strategy-family structure for crypto
- shared vs crypto-specific responsibilities
- first daily-only crypto research path
- data-source compatibility expectations

This design does not cover:

- live trading integration
- intraday crypto bars
- exchange-specific order routing
- futures, perpetuals, leverage, or funding-rate logic

## Design Goals

- preserve current equity behavior without regression risk
- reuse the existing backtest engine and reporting pipeline
- allow crypto strategy logic to diverge from equity assumptions
- keep the first implementation small and daily-only
- keep data source selection orthogonal to strategy family

## Non-Goals

- building a universal “one mean reversion model for all markets”
- generalizing every current equity assumption into shared abstractions
- introducing exchange-specific runtime dependencies into the strategy layer

## Reuse Boundary

### Shared Layers

These should remain shared across equity and crypto:

- OHLCV data-source contract
- frame normalization
- indicator utilities
- signal-driven backtest engine
- trade/equity reporting
- results bundle generation
- CLI strategy/data-source selection flow

### Market-Specific Layers

These should be strategy-family-specific:

- symbol universe
- regime filter semantics
- entry and exit rules
- interpretation of holding period
- any market-structure assumptions tied to bar calendar behavior

## Architecture

The system should be treated as two layers:

1. Shared engine layer
2. Market-specific strategy family layer

The shared engine layer should remain responsible for:

- consuming prepared frames with `entry_signal` and `exit_signal`
- simulating positions and exits
- producing trades, equity curve, summaries, and reports

The strategy-family layer should remain responsible for:

- selecting symbols
- enriching frames
- deriving signals from normalized bars
- defining strategy-specific defaults and assumptions

## Strategy Family Layout

Keep the existing equity family untouched:

- `src/mean_reversion/strategies/mean_reversion/...`

Add a new parallel crypto family:

- `src/mean_reversion/strategies/mean_reversion_crypto/base.py`
- `src/mean_reversion/strategies/mean_reversion_crypto/v1.py`
- `src/mean_reversion/strategies/mean_reversion_crypto/__init__.py`

Update only the top-level strategy registry to aggregate both families.

This means:

- no equity-side folder reshaping is required
- no engine-level crypto branching is required
- crypto enters through the same top-level `--strategy` interface

## Strategy Contract

The crypto family should implement the existing strategy contract already used by equity strategies:

- `required_symbols()`
- `prepare_frames(...)`
- `build_signals(...)`

That contract is already sufficiently general for crypto because it is based on normalized OHLCV input and explicit signal output.

## Registry Shape

Top-level registry behavior should become:

- import equity `STRATEGY_TYPES`
- import crypto `STRATEGY_TYPES`
- concatenate them into one `STRATEGY_FACTORIES` mapping

The CLI should remain unchanged other than the new strategy names becoming available.

## Data Source Compatibility

The strategy family should not depend on one specific provider.

It should require only:

- normalized daily OHLCV bars
- one frame per requested symbol
- consistent time index alignment across symbols

### Expected Compatible Sources

#### 1. `yfinance`

Recommended as the first research source.

Reasons:

- already implemented in the repo
- matches current default workflow
- can provide daily crypto tickers like `BTC-USD` and `ETH-USD`
- lowest lift for first research iteration

Tradeoff:

- free-source data quality and provider behavior should not be assumed identical to exchange-native feeds

#### 2. File-based data sources

Already aligned with the current design.

Reasons:

- useful for alternate regions or hand-curated crypto datasets
- allows offline, reproducible backtests
- avoids binding strategy behavior to one provider

Tradeoff:

- requires external responsibility for data correctness and schema quality

#### 3. Alpaca crypto

Plausible later source, not required for first implementation.

Research notes:

- Alpaca has official historical crypto bar endpoints
- Alpaca documents that crypto bars can be based on quote mid-prices when no trade occurs

Implication:

- bar semantics are usable, but not identical to pure trade-based bars
- source-specific behavior should be documented if adopted later

Sources:

- [Alpaca historical crypto data](https://docs.alpaca.markets/docs/historical-crypto-data-1)
- [Alpaca crypto API reference](https://docs.alpaca.markets/v1.3/reference/crypto)

#### 4. Coinbase Advanced

Plausible later source, not required for first implementation.

Research notes:

- Coinbase provides official candle endpoints for products such as `BTC-USD`
- daily granularity is supported
- authentication and paging constraints add implementation overhead

Source:

- [Coinbase Get Product Candles](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/products/get-product-candles)

### First-Phase Source Recommendation

Use:

- `yfinance` first

Keep explicit design room for:

- file-based crypto bars
- Alpaca later
- Coinbase later

## Crypto Market-Structure Constraints

The crypto family should explicitly acknowledge:

- daily bars include weekends
- market hours are continuous rather than session-based
- a broad-market proxy is not equivalent to `SPY`
- BTC may act as a regime anchor, but that is a design choice rather than a default truth

Because of that, the first crypto family should not automatically inherit the equity family’s market-filter assumptions.

## First Implementation Scope

The first crypto implementation should stay intentionally small.

Constraints:

- daily bars only
- no intraday support
- no exchange-specific execution logic
- no leverage or futures

## First Crypto Universe

Preferred universe:

- `BTC-USD`
- `ETH-USD`

If a source cannot reliably provide both, fallback is acceptable:

- `BTC-USD` only

## First Crypto v1 Strategy Direction

Recommended first direction:

- create a crypto-native daily mean reversion strategy
- avoid copying the equity `SPY > 200DMA` concept directly unless later evidence supports it

Two valid first research options exist:

### Option A: BTC-Only

- simpler
- no separate market proxy
- clean first experiment

### Option B: BTC + ETH Daily Crypto Family

- supports the desired two-asset research direction
- allows BTC to act as a regime reference if desired later
- still daily-only and small in scope

Recommendation:

- structure the family for both `BTC-USD` and `ETH-USD`
- keep the first concrete v1 implementation conservative and explicit about whether BTC is tradable, a regime proxy, or both

That choice should be encoded in the crypto strategy itself, not generalized into shared engine behavior.

## Strategy Semantics Guidance

For crypto v1, the implementation should treat the following as open design choices owned by the crypto family:

- whether there is a separate regime filter at all
- whether BTC is traded, used as a filter, or both
- whether `two_down_closes` remains useful on 24/7 daily bars
- whether hold duration should remain simple bar-count based

The engine should continue to treat holding time as bar-based unless a future design explicitly changes that rule.

## Recommended Initial Interface Shape

`mean_reversion_crypto/base.py`

- shared defaults for crypto family
- helper methods for frame preparation
- crypto-specific regime helper utilities if needed

`mean_reversion_crypto/v1.py`

- first concrete crypto strategy
- daily-only
- first hardcoded universe
- explicit signal semantics

`mean_reversion_crypto/__init__.py`

- exports crypto strategy types

## Equity Isolation

Equity strategies should remain behaviorally unchanged.

The crypto work should not require:

- rewriting equity strategy files
- changing current equity defaults
- introducing cross-market conditional logic into the equity family

The only expected shared touchpoint should be:

- top-level strategy registration

## Why This Design Is Preferred

This approach avoids a common failure mode:

- over-generalizing early in the name of reuse

That kind of abstraction would force the system to pretend equity and crypto are “the same kind of mean reversion problem” before the research supports that claim.

This design instead reuses what is truly generic:

- data normalization
- indicators
- signal-driven backtesting
- result reporting

while keeping market-specific strategy logic separate.

## Implementation Impact

This should be a moderate-lift feature, not a large refactor.

Expected touchpoints:

- add new crypto strategy-family files
- update top-level strategy registry
- optionally add tests for new strategy registration and data compatibility assumptions

Expected non-touchpoints:

- backtest engine internals
- report UX architecture
- results bundle structure
- equity strategy behavior

## Decision Summary

- reuse the shared backtest engine
- reuse the results and reporting pipeline
- reuse the OHLCV data-source contract
- add a separate `mean_reversion_crypto` strategy family
- keep current equity strategy family intact
- start with daily bars only
- use `yfinance` first, while keeping file-based and provider-specific expansion paths open
