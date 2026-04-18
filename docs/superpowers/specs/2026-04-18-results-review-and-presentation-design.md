# Results Review And Presentation Design

**Date:** 2026-04-18

**Status:** Proposed

## Goal

Add a durable results-saving model that stores strategy backtest outputs in a way that supports both fast text review and static visual presentation without bloating storage when repeated runs produce identical results. The first version should save canonical run bundles on disk, keep a lightweight audit history for every execution attempt, organize results primarily by strategy, and generate both human-readable summaries and a browser-openable HTML report from the same underlying run data.

## Why This Change

The current project writes a single set of artifacts under `artifacts/mean_reversion/`. That is fine for one-off local testing, but it does not scale well once you have:

- multiple strategies
- multiple markets
- multiple instrument types
- multiple data sources
- repeated runs over time

Even if a strategy’s rules stay fixed, results can still change because of:

- different data sources
- source data revisions
- date-range changes
- engine or reporting fixes
- different local datasets

So the system needs a durable way to preserve and review runs, not just overwrite the same output files each time.

## Scope

### In Scope

- Save each unique result as a canonical bundle on disk
- Record every execution attempt in lightweight audit history
- Organize results by strategy first
- Use a composite second-level bucket of `market__instrument_type__source`
- Generate both structured and human-readable outputs for each run
- Generate a static HTML report for local visual review
- Maintain a `latest/` snapshot per bucket for quick access

### Out of Scope

- Database-backed results storage
- Multi-run interactive dashboard
- Live filtering UI
- React or frontend framework app
- Cloud-hosted reporting
- PDF export
- Ranking or optimization engine

## Chosen Approach

Use the filesystem as the source of truth.

Each unique result should produce a self-contained canonical bundle that includes:

- run metadata
- structured summary metrics
- raw CSV outputs
- a markdown summary for text review
- a static HTML report for visual review

Each execution attempt should also produce a lightweight audit record so reruns are visible without forcing duplicate bundles to be written.

This keeps the first version simple, transparent, and easy to inspect with normal tools while avoiding unnecessary storage growth from identical reruns.

## Storage Hierarchy

Results should be stored under a new top-level `results/` directory with this hierarchy:

```text
results/
  <strategy>/
    <market>__<instrument_type>__<source>/
      bundles/
        <fingerprint>/
      history/
        <timestamp>.json
      latest/
```

Example:

```text
results/
  mean_reversion_v1/
    us__etf__yfinance/
      bundles/
        a1b2c3d4/
      history/
        2026-04-18T14-10-00.json
      latest/
    us__etf__csv/
      bundles/
        e5f6g7h8/
      history/
        2026-04-18T15-00-00.json
      latest/
    cn__equity__parquet/
      bundles/
        i9j0k1l2/
      history/
        2026-04-19T09-00-00.json
      latest/
```

## Why This Hierarchy

- `strategy` is the top-level key because that is the main research unit you will browse by.
- `market__instrument_type__source` defines the comparable run bucket.
- `bundles/` holds canonical unique result payloads.
- `history/` provides immutable execution history within that bucket.
- `latest/` gives a fast view of the latest resolved result.

This avoids a deeper nested tree like `strategy/market/instrument/source/timestamp`, which would add directory depth without providing much extra value at the current scale.

## Composite Bucket Naming

The second-level bucket should be a flat composite name:

```text
<market>__<instrument_type>__<source>
```

Examples:

- `us__etf__yfinance`
- `us__equity__csv`
- `global__crypto__parquet`
- `cn__etf__vendor_x`

This keeps the filesystem layout easy to scan while allowing the metadata file to preserve the same fields separately for filtering or later indexing.

## Run Bundle Structure

Each canonical bundle directory should contain:

```text
<fingerprint>/
  run_meta.json
  summary.json
  summary.md
  trades.csv
  equity_curve.csv
  comparison.csv
  charts.json
  report.html
```

### File Responsibilities

- `run_meta.json`
  Canonical run identity and provenance.
- `summary.json`
  Machine-readable metrics for later automation or aggregation.
- `summary.md`
  Compact text review for terminal and editor workflows.
- `trades.csv`
  Raw trade log.
- `equity_curve.csv`
  Raw equity time series.
- `comparison.csv`
  Base vs slippage comparison.
- `charts.json`
  Precomputed chart series and display metadata for the HTML report.
- `report.html`
  Self-contained static visual report that can be opened locally in a browser.

## Audit History

Each execution attempt should write a lightweight timestamped record under `history/`:

```text
history/
  2026-04-18T14-10-00.json
  2026-04-18T14-20-00.json
```

Example:

```json
{
  "timestamp": "2026-04-18T14:20:00-05:00",
  "strategy": "mean_reversion_v1",
  "market": "us",
  "instrument_type": "etf",
  "source": "yfinance",
  "bundle_fingerprint": "a1b2c3d4",
  "deduplicated": true,
  "code_commit": "2a954a7"
}
```

This preserves auditability without forcing a full duplicate bundle for every run.

## Fingerprinting

A canonical bundle fingerprint should be derived from the meaningful run identity and results, including:

- strategy
- market
- instrument type
- source
- symbols
- date range
- slippage setting
- code commit
- structured result payload hash

If a new execution resolves to an existing fingerprint, no new full bundle should be written. Only a new audit record should be added to `history/`.

## Latest Snapshot

Each composite bucket should also contain a `latest/` directory:

```text
results/
  mean_reversion_v1/
    us__etf__yfinance/
      bundles/
        a1b2c3d4/
      history/
        2026-04-18T14-10-00.json
        2026-04-18T14-20-00.json
      latest/
```

`latest/` should represent the latest resolved result for that bucket, not necessarily a newly created bundle.

Recommended contents:

```text
latest/
  latest.json
  summary.md
  report.html
```

`latest/` should not duplicate all raw files from the canonical bundle. It should store:

- a small metadata record such as `latest.json` pointing to the active fingerprint
- convenience presentation assets such as `summary.md` and `report.html`

Reason:

- simpler cross-platform behavior
- easier inspection and sharing
- avoids symlink edge cases on different shells, Git clients, or archive tools
- avoids reintroducing large duplicate raw data files into the `latest/` view

## Metadata Requirements

At minimum, `run_meta.json` should include:

```json
{
  "strategy": "mean_reversion_v1",
  "market": "us",
  "instrument_type": "etf",
  "source": "yfinance",
  "timestamp": "2026-04-18T14:10:00-05:00",
  "symbols": ["SPY", "IVV", "QQQ"],
  "slippage_bps": 10.0,
  "date_range": {
    "start": "2021-03-22",
    "end": "2026-04-17"
  },
  "code_commit": "2a954a7"
}
```

### Why These Fields Matter

They let you answer:

- what strategy ran
- on what market
- on what instrument type
- from what data source
- against which symbols
- over what date range
- under which code revision

Without this metadata, a run can become hard to trust once you have many saved results.

## Text Review Output

`summary.md` should be optimized for fast human review. Recommended shape:

```md
# mean_reversion_v1

- Market: us
- Instrument: etf
- Source: yfinance
- Symbols: SPY, IVV, QQQ
- Date Range: 2021-03-22 to 2026-04-17
- Commit: 2a954a7

## Base
- Total Return: 14.01%
- Max Drawdown: -2.54%
- Win Rate: 79.10%
- Average Trade Return: 0.55%
- Number of Trades: 67

## Slippage
- Total Return: 8.39%
- Max Drawdown: -3.64%
- Win Rate: 74.63%
- Average Trade Return: 0.33%
- Number of Trades: 67

## Delta
- Total Return Delta: -5.62%
- Max Drawdown Delta: -1.10%
```

This should be generated from the same structured results used by the visual report so the text and visual outputs cannot drift from each other.

## Visual Review Output

`report.html` should be a static single-run report designed for local browser opening.

Recommended contents:

- run header with metadata
- metric cards for base and slippage summaries
- equity curve chart
- drawdown chart
- comparison table
- compact trade preview table

Important design rule:

The HTML page should be generated from saved result data such as `summary.json`, `equity_curve.csv`, and `charts.json`. The page is not the source of truth; it is a presentation layer over the canonical run bundle.

## Chart Payload

`charts.json` should exist so the visualization layer does not need to recompute every series in-browser from raw CSV files.

Good first-version contents:

- equity curve series
- drawdown series
- comparison metrics
- optional trade-return histogram values

This keeps the report generation deterministic and makes the HTML easier to render with minimal JavaScript.

## Write Timing

Results should be written only after a run completes successfully enough to produce coherent outputs.

Recommended behavior:

- compute the run fingerprint
- create the canonical bundle only if the fingerprint is new
- always write a timestamped audit record
- refresh the bucket’s `latest/` view last

If a run fails midway, it should not silently overwrite `latest/`.

## Relationship To Existing `artifacts/`

The new `results/` tree should become the durable long-lived result store.

The existing `artifacts/mean_reversion/` path can either:

- remain as a simple scratch/output area for ad hoc runs
- or be replaced by the new result bundle path once the migration is complete

For the first implementation, it is acceptable to generate the new bundle directly and stop relying on a single shared artifacts directory for durable review.

## Error Handling

The results-saving layer should fail clearly on:

- invalid or missing required metadata fields
- missing summary inputs
- failure to compute a stable fingerprint
- failure to create the canonical bundle directory
- failure to write the history record
- failure to refresh the `latest/` snapshot

If presentation generation fails after structured data is already written, that failure should be explicit rather than silently ignored.

## Testing Strategy

Coverage should include:

- correct results path construction from strategy, market, instrument type, source, and timestamp
- canonical bundle contains all expected files
- duplicate runs resolve to the same canonical fingerprint
- duplicate runs still produce distinct history records
- `latest/` is refreshed after a successful run
- `summary.md` contains the expected human-readable sections
- `report.html` contains key metric values and metadata
- `run_meta.json` includes required provenance fields

## Future Growth

This design intentionally leaves room for future additions without requiring them now:

- index page across all strategies
- multi-run comparison view
- database or SQLite indexing layer
- richer visual dashboard
- ranking or leaderboard generation

Because the filesystem bundle is structured and self-contained, those later features can be built on top of the saved run directories instead of replacing them.

## Recommendation

Proceed with a filesystem-first results model that:

- saves canonical bundles once per unique fingerprint
- records every execution attempt in timestamped history
- organizes results by `strategy / market__instrument_type__source`
- writes both structured and human-readable outputs
- includes a static HTML report per unique bundle
- maintains a lightweight `latest/` view for quick review

Do not introduce a database or frontend application in the same first pass.
