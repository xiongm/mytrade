# Results Report UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the per-run HTML report so it shows summary metrics, explicit run setup, intuitive trade-behavior visuals, portfolio charts, and a full trade audit table.

**Architecture:** Extend the existing results bundle writer instead of creating a separate reporting pipeline. Persist the actual run setup alongside existing bundle metadata, enrich `charts.json` with trade-behavior inputs, and replace the current raw-data HTML with a structured report template that renders charts and a full trade table from self-contained bundle artifacts.

**Tech Stack:** Python 3.12, pandas, existing HTML string templating in `src/mean_reversion/results/writer.py`, pytest

---

### File Map

**Existing files to modify**
- Modify: `src/mean_reversion/cli.py`
  - pass strategy/config parameters into the persisted run context so reports can show the exact run setup later
- Modify: `src/mean_reversion/results/models.py`
  - extend `RunContext` with explicit strategy setup fields required by the report
- Modify: `src/mean_reversion/results/writer.py`
  - persist setup metadata
  - compute trade behavior payloads
  - replace raw `<pre>` curve dumps with structured report sections
- Modify: `tests/test_cli.py`
  - update any `RunContext`/writer expectations affected by persisted setup fields
- Modify: `tests/test_results_writer.py`
  - add coverage for setup persistence, chart payload enrichment, report sections, and full trade table rendering

**Optional existing files to inspect while implementing**
- Inspect: `src/mean_reversion/backtest.py`
  - confirm trade columns available for the full trade table and holding-period calculations
- Inspect: `src/mean_reversion/reporting.py`
  - reuse any existing summary metrics rather than recomputing them differently

---

### Task 1: Extend RunContext With Persisted Setup Fields

**Files:**
- Modify: `src/mean_reversion/results/models.py`
- Modify: `tests/test_results_writer.py`
- Modify: `tests/test_results_fingerprint.py`
- Modify: `tests/test_results_paths.py`

- [ ] **Step 1: Write the failing tests**

Add required setup fields to every `RunContext(...)` fixture in:

`tests/test_results_writer.py`
```python
context = RunContext(
    strategy="mean_reversion_v1",
    market="us",
    instrument_type="etf",
    source="yfinance",
    timestamp="2026-04-18T14-10-00",
    symbols=("SPY", "IVV", "QQQ"),
    date_start="2021-03-22",
    date_end="2026-04-17",
    slippage_bps=10.0,
    code_commit="2a954a7",
    entry_rsi_threshold=15.0,
    exit_rsi_threshold=60.0,
    max_hold_days=4,
    require_two_down_closes=True,
    use_rsi_exit=True,
    stop_loss_pct=0.03,
)
```

Apply the same pattern to the `RunContext(...)` fixtures in:

`tests/test_results_fingerprint.py`
```python
context = RunContext(
    strategy="mean_reversion_v1",
    market="us",
    instrument_type="etf",
    source="yfinance",
    timestamp="2026-04-18T14-10-00",
    symbols=("SPY", "IVV", "QQQ"),
    date_start="2021-03-22",
    date_end="2026-04-17",
    slippage_bps=10.0,
    code_commit="2a954a7",
    entry_rsi_threshold=15.0,
    exit_rsi_threshold=60.0,
    max_hold_days=4,
    require_two_down_closes=True,
    use_rsi_exit=True,
    stop_loss_pct=0.03,
)
```

`tests/test_results_paths.py`
```python
context = RunContext(
    strategy="mean_reversion_v1",
    market="us",
    instrument_type="etf",
    source="yfinance",
    timestamp="2026-04-18T14-10-00",
    symbols=("SPY", "IVV", "QQQ"),
    date_start="2021-03-22",
    date_end="2026-04-17",
    slippage_bps=10.0,
    code_commit="2a954a7",
    entry_rsi_threshold=15.0,
    exit_rsi_threshold=60.0,
    max_hold_days=4,
    require_two_down_closes=True,
    use_rsi_exit=True,
    stop_loss_pct=0.03,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py tests/test_results_fingerprint.py tests/test_results_paths.py -v
```

Expected:

- FAIL with `TypeError` complaining that `RunContext` does not accept the new setup fields yet

- [ ] **Step 3: Implement the RunContext fields**

Update `src/mean_reversion/results/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    strategy: str
    market: str
    instrument_type: str
    source: str
    timestamp: str
    symbols: tuple[str, ...]
    date_start: str
    date_end: str
    slippage_bps: float
    code_commit: str
    entry_rsi_threshold: float
    exit_rsi_threshold: float
    max_hold_days: int
    require_two_down_closes: bool
    use_rsi_exit: bool
    stop_loss_pct: float
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py tests/test_results_fingerprint.py tests/test_results_paths.py -v
```

Expected:

- PASS or move to the next missing-field failure in `cli.py` call sites

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/models.py tests/test_results_writer.py tests/test_results_fingerprint.py tests/test_results_paths.py
git commit -m "feat: persist strategy setup fields in run context"
```

### Task 2: Pass Strategy Setup Into RunContext From The CLI

**Files:**
- Modify: `src/mean_reversion/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Add a new CLI test in `tests/test_cli.py`:

```python
def test_cli_persists_strategy_setup_in_latest_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "BacktestConfig",
        lambda **kwargs: BacktestConfig(**{**kwargs, "output_dir": str(tmp_path / "artifacts")}),
    )
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
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
        market = "us"
        instrument_type = "etf"
        entry_rsi_threshold = 20.0
        exit_rsi_threshold = 70.0
        max_hold_days = 6
        require_two_down_closes = False
        use_rsi_exit = False

        def required_symbols(self):
            return ("SPY", "IVV", "QQQ")

        def prepare_frames(self, frames):
            return frames

        def build_signals(self, frames):
            return frames

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())
    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())
    monkeypatch.setattr(cli, "_git_head_short", lambda: "2a954a7")
    monkeypatch.setattr(
        cli,
        "run_backtest",
        lambda frames, config, slippage_bps=0.0: BacktestResult(
            trades=pd.DataFrame([{"symbol": "IVV", "entry_date": "2026-01-01", "exit_date": "2026-01-02", "entry_price": 100.0, "exit_price": 101.0, "shares": 10, "pnl": 10.0, "return_pct": 0.01, "exit_reason": "signal"}]),
            equity_curve=pd.DataFrame({"cash": [10000.0, 0.0], "positions_value": [0.0, 10100.0], "equity": [10000.0, 10100.0]}, index=idx),
        ),
    )

    cli.main(["--strategy", "mean_reversion_v1"])

    run_meta = json.loads(next((tmp_path / "results").glob("**/run_meta.json")).read_text())
    assert run_meta["entry_rsi_threshold"] == 20.0
    assert run_meta["exit_rsi_threshold"] == 70.0
    assert run_meta["max_hold_days"] == 6
    assert run_meta["require_two_down_closes"] is False
    assert run_meta["use_rsi_exit"] is False
    assert run_meta["stop_loss_pct"] == 0.03
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest tests/test_cli.py::test_cli_persists_strategy_setup_in_latest_bundle -v
```

Expected:

- FAIL because `RunContext(...)` call in `cli.py` does not pass the new fields yet

- [ ] **Step 3: Implement the CLI RunContext setup mapping**

Update the `RunContext(...)` call in `src/mean_reversion/cli.py`:

```python
    context = RunContext(
        strategy=strategy.name,
        market=getattr(strategy, "market", "us"),
        instrument_type=getattr(strategy, "instrument_type", "etf"),
        source=data_source.name,
        timestamp=datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S"),
        symbols=strategy.required_symbols(),
        date_start=str(signals[strategy.market_symbol].index.min().date()),
        date_end=str(signals[strategy.market_symbol].index.max().date()),
        slippage_bps=config.slippage_bps,
        code_commit=_git_head_short(),
        entry_rsi_threshold=config.entry_rsi_threshold,
        exit_rsi_threshold=config.exit_rsi_threshold,
        max_hold_days=config.max_hold_days,
        require_two_down_closes=getattr(strategy, "require_two_down_closes", True),
        use_rsi_exit=getattr(strategy, "use_rsi_exit", True),
        stop_loss_pct=config.stop_loss_pct,
    )
```

- [ ] **Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest tests/test_cli.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/cli.py tests/test_cli.py
git commit -m "feat: persist report setup metadata from cli runs"
```

### Task 3: Add Trade Behavior Data To charts.json

**Files:**
- Modify: `src/mean_reversion/results/writer.py`
- Modify: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing tests**

Extend `tests/test_results_writer.py` with:

```python
def test_charts_json_contains_trade_return_and_holding_period_inputs(tmp_path):
    result = _make_written_result(tmp_path)
    charts = json.loads((result.bundle_dir / "charts.json").read_text())

    assert "trade_return_distribution" in charts
    assert charts["trade_return_distribution"]["returns"]
    assert "holding_period_distribution" in charts
    assert charts["holding_period_distribution"]["days"]
```

Update `_make_written_result(tmp_path)` to use a realistic trade fixture:

```python
trades = pd.DataFrame(
    [
        {
            "symbol": "IVV",
            "entry_date": "2026-01-02",
            "exit_date": "2026-01-06",
            "entry_price": 100.0,
            "exit_price": 101.0,
            "shares": 10,
            "pnl": 10.0,
            "return_pct": 0.01,
            "exit_reason": "signal",
        },
        {
            "symbol": "QQQ",
            "entry_date": "2026-01-03",
            "exit_date": "2026-01-04",
            "entry_price": 200.0,
            "exit_price": 196.0,
            "shares": 5,
            "pnl": -20.0,
            "return_pct": -0.02,
            "exit_reason": "stop_loss",
        },
    ]
)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py::test_charts_json_contains_trade_return_and_holding_period_inputs -v
```

Expected:

- FAIL because `charts.json` only contains equity and drawdown

- [ ] **Step 3: Implement minimal chart payload enrichment**

Update `_build_charts_payload(...)` in `src/mean_reversion/results/writer.py`:

```python
def _build_charts_payload(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict:
    equity = equity_curve["equity"]
    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1

    holding_days = []
    if {"entry_date", "exit_date"}.issubset(trades.columns):
        entry_dates = pd.to_datetime(trades["entry_date"])
        exit_dates = pd.to_datetime(trades["exit_date"])
        holding_days = [int(value) for value in (exit_dates - entry_dates).dt.days]

    returns = [float(value) for value in trades["return_pct"]] if "return_pct" in trades.columns else []

    return {
        "equity_curve": {
            "dates": [str(index.date()) for index in equity_curve.index],
            "values": [float(value) for value in equity],
        },
        "drawdown_curve": {
            "dates": [str(index.date()) for index in equity_curve.index],
            "values": [float(value) for value in drawdown],
        },
        "trade_return_distribution": {
            "returns": returns,
        },
        "holding_period_distribution": {
            "days": holding_days,
        },
    }
```

Update every call site from:

```python
charts = _build_charts_payload(equity_curve)
```

to:

```python
charts = _build_charts_payload(equity_curve, trades)
```

For `_refresh_latest_view(...)`, pass `trades` down so the same chart payload is reused:

```python
_refresh_latest_view(latest_view, context, fingerprint, base_summary, slippage_summary, comparison, charts, trades)
```

- [ ] **Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: add trade behavior chart payloads"
```

### Task 4: Persist Setup Metadata In Bundle Files

**Files:**
- Modify: `src/mean_reversion/results/writer.py`
- Modify: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing tests**

Add this test in `tests/test_results_writer.py`:

```python
def test_summary_json_includes_run_setup_block(tmp_path):
    result = _make_written_result(tmp_path)
    payload = json.loads((result.bundle_dir / "summary.json").read_text())

    assert "setup" in payload
    assert payload["setup"]["entry_rsi_threshold"] == 15.0
    assert payload["setup"]["exit_rsi_threshold"] == 60.0
    assert payload["setup"]["max_hold_days"] == 4
    assert payload["setup"]["require_two_down_closes"] is True
    assert payload["setup"]["use_rsi_exit"] is True
    assert payload["setup"]["stop_loss_pct"] == 0.03
    assert payload["setup"]["slippage_bps"] == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py::test_summary_json_includes_run_setup_block -v
```

Expected:

- FAIL because `summary.json` does not contain a `setup` block

- [ ] **Step 3: Implement setup persistence**

Add a helper to `src/mean_reversion/results/writer.py`:

```python
def _build_setup_payload(context: RunContext) -> dict:
    return {
        "entry_rsi_threshold": float(context.entry_rsi_threshold),
        "exit_rsi_threshold": float(context.exit_rsi_threshold),
        "max_hold_days": int(context.max_hold_days),
        "require_two_down_closes": bool(context.require_two_down_closes),
        "use_rsi_exit": bool(context.use_rsi_exit),
        "stop_loss_pct": float(context.stop_loss_pct),
        "slippage_bps": float(context.slippage_bps),
    }
```

Update `_write_canonical_bundle(...)` so `summary.json` becomes:

```python
summary = {
    "identity": {
        "strategy": context.strategy,
        "market": context.market,
        "instrument_type": context.instrument_type,
        "source": context.source,
        "symbols": list(context.symbols),
        "date_range": {"start": context.date_start, "end": context.date_end},
        "code_commit": context.code_commit,
    },
    "setup": _build_setup_payload(context),
    "base": base_summary,
    "slippage": slippage_summary,
    "delta": delta_summary,
}
```

Update `_build_llm_review_json(...)` to reuse the same setup payload:

```python
        "setup": _build_setup_payload(context),
```

- [ ] **Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: persist report setup metadata in bundles"
```

### Task 5: Replace Raw Report Dumps With Structured Report Sections

**Files:**
- Modify: `src/mean_reversion/results/writer.py`
- Modify: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing tests**

Add this test in `tests/test_results_writer.py`:

```python
def test_report_html_contains_summary_setup_charts_and_full_trade_table(tmp_path):
    result = _make_written_result(tmp_path)
    html = (result.bundle_dir / "report.html").read_text()

    assert "Performance Summary" in html
    assert "Run Setup" in html
    assert "Trade Outcome Distribution" in html
    assert "Trade Behavior" in html
    assert "Portfolio Path" in html
    assert "Full Trade Log" in html
    assert "Entry Price" in html
    assert "Exit Price" in html
    assert "Exit Reason" in html
    assert "entry_rsi_threshold" not in html
```

The last assertion is a guard against rendering a raw JSON dump instead of a human-formatted setup panel.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py::test_report_html_contains_summary_setup_charts_and_full_trade_table -v
```

Expected:

- FAIL because the current report only contains base/slippage cards, a comparison table, and raw `<pre>` chart dumps

- [ ] **Step 3: Implement the structured report template**

Replace `_build_report_html(...)` in `src/mean_reversion/results/writer.py` with a structured template that renders:

```python
def _build_report_html(
    context: RunContext,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    charts: dict,
    trades: pd.DataFrame,
) -> str:
    setup = _build_setup_payload(context)
    holding_days = charts["holding_period_distribution"]["days"]
    avg_hold = sum(holding_days) / len(holding_days) if holding_days else 0.0
    median_hold = pd.Series(holding_days).median() if holding_days else 0.0
    max_hold = max(holding_days) if holding_days else 0

    trade_table_columns = [
        "symbol",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "shares",
        "pnl",
        "return_pct",
        "exit_reason",
    ]
    trade_table = trades.loc[:, [col for col in trade_table_columns if col in trades.columns]].to_html(index=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{context.strategy} Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(5, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .card {{ border: 1px solid #ddd; padding: 16px; border-radius: 8px; background: #fafafa; }}
    .section {{ margin-top: 32px; }}
    .setup-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 8px 16px; }}
    .chart-card {{ border: 1px solid #ddd; padding: 16px; border-radius: 8px; background: #fff; margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; display: block; overflow-x: auto; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; white-space: nowrap; }}
    .mono {{ font-family: monospace; }}
  </style>
</head>
<body>
  <h1>{context.strategy}</h1>

  <div class="section">
    <h2>Performance Summary</h2>
    <div class="summary-grid">
      <div class="card"><strong>Total Return</strong><br>{_format_percentage(float(base_summary.get('total_return', 0.0)))}</div>
      <div class="card"><strong>Max Drawdown</strong><br>{_format_percentage(float(base_summary.get('max_drawdown', 0.0)))}</div>
      <div class="card"><strong>Win Rate</strong><br>{_format_percentage(float(base_summary.get('win_rate', 0.0)))}</div>
      <div class="card"><strong>Average Trade Return</strong><br>{_format_percentage(float(base_summary.get('average_trade_return', 0.0)))}</div>
      <div class="card"><strong>Number of Trades</strong><br>{int(base_summary.get('number_of_trades', 0))}</div>
    </div>
  </div>

  <div class="section">
    <h2>Run Setup</h2>
    <div class="setup-grid">
      <div><strong>Strategy</strong>: {context.strategy}</div>
      <div><strong>Symbols</strong>: {", ".join(context.symbols)}</div>
      <div><strong>Market</strong>: {context.market}</div>
      <div><strong>Instrument Type</strong>: {context.instrument_type}</div>
      <div><strong>Source</strong>: {context.source}</div>
      <div><strong>Date Range</strong>: {context.date_start} to {context.date_end}</div>
      <div><strong>Entry RSI</strong>: {setup['entry_rsi_threshold']}</div>
      <div><strong>Exit RSI</strong>: {setup['exit_rsi_threshold']}</div>
      <div><strong>Max Hold Days</strong>: {setup['max_hold_days']}</div>
      <div><strong>Require Two Down Closes</strong>: {"Yes" if setup['require_two_down_closes'] else "No"}</div>
      <div><strong>Use RSI Exit</strong>: {"Yes" if setup['use_rsi_exit'] else "No"}</div>
      <div><strong>Stop Loss</strong>: {_format_percentage(setup['stop_loss_pct'])}</div>
      <div><strong>Slippage</strong>: {setup['slippage_bps']} bps</div>
      <div><strong>Commit</strong>: <span class="mono">{context.code_commit}</span></div>
    </div>
  </div>

  <div class="section">
    <h2>Trade Outcome Distribution</h2>
    <div class="chart-card"><pre>{json.dumps(charts["trade_return_distribution"], indent=2)}</pre></div>
  </div>

  <div class="section">
    <h2>Trade Behavior</h2>
    <div class="chart-card">
      <p><strong>Average Hold</strong>: {avg_hold:.2f} days</p>
      <p><strong>Median Hold</strong>: {median_hold:.2f} days</p>
      <p><strong>Max Hold</strong>: {max_hold} days</p>
      <pre>{json.dumps(charts["holding_period_distribution"], indent=2)}</pre>
    </div>
  </div>

  <div class="section">
    <h2>Portfolio Path</h2>
    <div class="chart-card"><h3>Equity Curve</h3><pre>{json.dumps(charts["equity_curve"], indent=2)}</pre></div>
    <div class="chart-card"><h3>Drawdown Curve</h3><pre>{json.dumps(charts["drawdown_curve"], indent=2)}</pre></div>
  </div>

  <div class="section">
    <h2>Details</h2>
    <h3>Full Trade Log</h3>
    {trade_table}
    <h3>Comparison</h3>
    {comparison.to_html()}
  </div>
</body>
</html>"""
```

Also update call sites to pass `trades` into `_build_report_html(...)`.

- [ ] **Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: redesign results report layout"
```

### Task 6: Preserve Latest View And Bundle Refresh Behavior

**Files:**
- Modify: `src/mean_reversion/results/writer.py`
- Test: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing test**

Add this test in `tests/test_results_writer.py`:

```python
def test_latest_report_html_contains_run_setup_and_full_trade_log(tmp_path):
    result = _make_written_result(tmp_path)
    html = (result.latest_dir / "report.html").read_text()

    assert "Run Setup" in html
    assert "Full Trade Log" in html
    assert "Trade Outcome Distribution" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py::test_latest_report_html_contains_run_setup_and_full_trade_log -v
```

Expected:

- FAIL if latest view is still being rendered without the enriched `trades`/setup inputs

- [ ] **Step 3: Implement the latest-view propagation**

Update `_refresh_latest_view(...)` in `src/mean_reversion/results/writer.py`:

```python
def _refresh_latest_view(
    latest_view: Path,
    context: RunContext,
    fingerprint: str,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    charts: dict,
    trades: pd.DataFrame,
) -> None:
    latest_view.mkdir(parents=True, exist_ok=True)
    payload = {
        "strategy": context.strategy,
        "timestamp": context.timestamp,
        "symbols": list(context.symbols),
        "bundle_fingerprint": fingerprint,
    }
    summary_md = _build_summary_markdown(context, base_summary, slippage_summary, comparison)
    report_html = _build_report_html(context, base_summary, slippage_summary, comparison, charts, trades)

    (latest_view / "latest.json").write_text(json.dumps(payload, indent=2))
    (latest_view / "summary.md").write_text(summary_md)
    (latest_view / "report.html").write_text(report_html)
```

Update the caller in `write_results_bundle(...)` to pass `trades`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: refresh latest reports with structured report content"
```

### Task 7: Full Verification

**Files:**
- Modify: none
- Test: `tests/test_cli.py`
- Test: `tests/test_results_writer.py`
- Test: `tests/test_strategy.py`

- [ ] **Step 1: Run the focused suite**

Run:

```bash
./.venv/bin/python -m pytest tests/test_results_writer.py tests/test_cli.py tests/test_strategy.py -v
```

Expected:

- PASS

- [ ] **Step 2: Run the full suite**

Run:

```bash
./.venv/bin/python -m pytest -v
```

Expected:

- PASS

- [ ] **Step 3: Manual smoke test with a real report**

Run:

```bash
cd /Users/xm401/projects/mytrade
./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1
open /Users/xm401/projects/mytrade/results/mean_reversion_v1/us__etf__yfinance/latest/report.html
```

Verify manually:

- top summary cards exist
- `Run Setup` panel shows strategy parameters
- `Trade Outcome Distribution` section exists
- `Trade Behavior` section exists
- `Portfolio Path` section exists
- `Full Trade Log` contains entry/exit date, prices, shares, pnl, return pct, and exit reason

- [ ] **Step 4: Commit**

```bash
git add src/mean_reversion/cli.py src/mean_reversion/results/models.py src/mean_reversion/results/writer.py tests/test_cli.py tests/test_results_writer.py tests/test_strategy.py
git commit -m "feat: redesign results report for strategy review"
```

---

## Self-Review

### Spec coverage

- summary-first layout: Task 5
- separate run setup panel: Tasks 4 and 5
- trade outcome distribution first: Tasks 3 and 5
- holding-period distribution and stats: Tasks 3 and 5
- portfolio path later in report: Task 5
- full trade table with required columns: Task 5
- persisted setup metadata for historical traceability: Tasks 1, 2, and 4
- latest view consistency: Task 6

### Placeholder scan

- no `TBD`, `TODO`, or “implement later” placeholders remain
- every task includes explicit file paths, commands, and concrete code blocks

### Type consistency

- `RunContext` setup fields are introduced in Task 1 and then referenced consistently in Tasks 2, 4, 5, and 6
- `_build_charts_payload(equity_curve, trades)` is introduced once and reused consistently
- `_build_report_html(..., charts, trades)` is introduced once and reused consistently

