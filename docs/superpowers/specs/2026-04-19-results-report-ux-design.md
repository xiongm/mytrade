# Results Report UX Design

## Purpose

Improve the per-run results report so it is easier for the strategy author to interpret quickly.

The current report exposes raw data in a developer-friendly way, but it is not intuitive for fast review. The redesign should make the report answer three questions in order:

1. What setup did this run use?
2. How did the trades behave?
3. What was the portfolio path through time?

## Audience

Primary audience:

- the strategy author

This report is not primarily optimized for outside presentation or non-technical storytelling. It should support fast evaluation, parameter traceability, and trade-behavior diagnosis.

## Design Goals

- keep high-signal summary metrics at the top
- make strategy setup explicit and traceable
- make trade behavior visually intuitive
- make the equity curve a supporting view, not the first thing a reader must decode
- replace raw JSON dumps with charts and compact structured panels

## Report Structure

The report should follow this order:

1. `Performance Summary`
2. `Run Setup`
3. `Trade Outcome Distribution`
4. `Trade Behavior`
5. `Portfolio Path`
6. `Details`

## Section Design

### 1. Performance Summary

This remains the top section.

It should show the core outcome metrics as compact cards:

- total return
- max drawdown
- win rate
- average trade return
- number of trades

Optional follow-on metrics may still be shown if already available, but these five are the required top-level metrics.

### 2. Run Setup

This must be a separate panel, not mixed into the summary cards.

The purpose of this section is to show the exact strategy configuration used for the run so the author can immediately tell what variant was tested.

Required fields:

- strategy name
- symbols
- market
- instrument type
- source
- date range
- code commit
- entry RSI threshold
- exit RSI threshold
- max hold days
- require two down closes
- use RSI exit
- stop loss percent
- slippage bps

Design intent:

- this should read like a compact “run recipe”
- values should be easy to compare across multiple runs
- booleans should be rendered as explicit yes/no or enabled/disabled labels

### 3. Trade Outcome Distribution

This should be the first chart section after the summary/setup area.

Primary chart:

- histogram of per-trade returns using `trades.return_pct`

Design intent:

- make it visually obvious whether the strategy wins via many small wins, occasional large wins, frequent losses, or a fat-tail profile
- make gains and losses distinguishable at a glance

Preferred visual features:

- different coloring for positive vs negative bins
- optional mean marker
- optional median marker

This chart should replace the current need to mentally parse the trades CSV for outcome shape.

### 4. Trade Behavior

This section explains how the strategy behaved operationally, separate from pure PnL.

Required visual:

- holding-period distribution

Required supporting stats:

- average hold duration
- median hold duration
- max hold duration

Optional additions:

- win count vs loss count
- exit reason counts if useful later

Design intent:

- help the strategy author understand whether the strategy is behaving as a fast mean reversion system or drifting into longer holds
- make fixed-time-exit variants easier to compare against RSI-exit variants

### 5. Portfolio Path

This section should include:

- equity curve chart
- drawdown curve chart

These remain important, but they should no longer be the first visual shown in the report.

Design intent:

- preserve the portfolio-level path for context
- support review of smoothness and pain periods
- keep this section visually cleaner than the current raw serialized curve output

### 6. Details

This should be the lowest section on the page.

Recommended contents:

- full trades table
- comparison table if still useful for base vs slippage review

Design intent:

- retain auditability
- avoid making raw tables the primary reading experience

The details section must include the full trade table for the run, not just a recent-trades sample.

Required trade table columns:

- symbol
- entry date
- exit date
- entry price
- exit price
- shares
- pnl
- return pct
- exit reason

Presentation requirements:

- the full table should remain on the report page
- column labels should be explicit and stable
- percentage and currency-like fields should be formatted consistently
- the table may be horizontally scrollable if needed, but it should not be truncated to a partial sample by default

## Data Requirements

The redesign requires more explicit report data than the current HTML output uses.

### Existing Data Already Available

Already present:

- `RunContext`
- `base_summary`
- `slippage_summary`
- `comparison`
- `trades`
- `equity_curve`

These are sufficient to build most charts and top-level metrics.

### New Persisted Setup Data Required

To make `Run Setup` reliable, the report generator must persist the actual strategy parameters used for the run.

This should not rely on re-importing strategy classes later, because:

- code may change after the run
- the historical report should reflect what actually ran

Required persisted setup fields:

- entry RSI threshold
- exit RSI threshold
- max hold days
- require two down closes
- use RSI exit
- stop loss percent
- slippage bps

These should be stored in the canonical bundle in a machine-readable form.

## Report Payload Schema

The report generator should move toward an explicit structured payload with the following conceptual shape:

```json
{
  "identity": {
    "strategy": "...",
    "symbols": ["..."],
    "market": "...",
    "instrument_type": "...",
    "source": "...",
    "date_range": {"start": "...", "end": "..."},
    "code_commit": "..."
  },
  "setup": {
    "entry_rsi_threshold": 20.0,
    "exit_rsi_threshold": 60.0,
    "max_hold_days": 4,
    "require_two_down_closes": false,
    "use_rsi_exit": true,
    "stop_loss_pct": 0.03,
    "slippage_bps": 10.0
  },
  "summary": {
    "base": {...},
    "slippage": {...},
    "delta": {...}
  },
  "trade_behavior": {
    "holding_period_stats": {
      "average_days": 0,
      "median_days": 0,
      "max_days": 0
    },
    "outcome_distribution": {...},
    "holding_period_distribution": {...}
  },
  "portfolio_path": {
    "equity_curve": {...},
    "drawdown_curve": {...}
  }
}
```

This is a design target, not a strict serialization contract yet.

## Chart Payload Requirements

`charts.json` should evolve beyond only equity and drawdown.

Required additions:

- trade outcome distribution inputs
- holding period distribution inputs

Minimum chart payload additions:

```json
{
  "trade_return_distribution": {
    "returns": [0.01, -0.02, 0.03]
  },
  "holding_period_distribution": {
    "days": [2, 3, 1, 4]
  }
}
```

The front-end rendering layer can bin these values for display, or the backend can pre-bin them later if necessary.

## HTML Report Changes

The current HTML report should change in these ways:

- remove raw JSON `<pre>` output for equity/drawdown from the main reading path
- add summary cards
- add a structured `Run Setup` panel
- add visual charts for trade return distribution and holding period distribution
- render equity and drawdown as actual charts
- keep raw data tables lower in the page

## Non-Goals

This redesign does not attempt to:

- make the report primarily presentation-ready for outside stakeholders
- turn the report into a general BI dashboard
- redesign the global portal in the same change
- add LLM dependency to reporting

## Implementation Notes

The most likely implementation center is:

- [src/mean_reversion/results/writer.py](/Users/xm401/projects/mytrade/src/mean_reversion/results/writer.py)

Likely work areas:

- enrich persisted bundle metadata with setup fields
- extend chart payload generation
- replace the current minimal HTML template with a more structured template

## Acceptance Criteria

The redesign is successful when:

- the top of the report clearly shows both performance and chosen run parameters
- the first visual after summary is a trade return distribution
- the equity curve is no longer shown only as raw serialized data
- a strategy author can identify setup, trade profile, and portfolio path in under a minute
- historical reports remain self-contained and traceable without depending on current source code state
