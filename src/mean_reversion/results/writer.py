from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path

import pandas as pd

from .fingerprint import build_bundle_fingerprint
from .index_generator import update_global_index
from .models import RunContext
from .paths import bundle_dir, history_file, latest_dir


@dataclass(frozen=True)
class WriteResult:
    fingerprint: str
    bundle_dir: Path
    latest_dir: Path
    deduplicated: bool


def write_results_bundle(
    root_dir: Path,
    context: RunContext,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> WriteResult:
    payload = {
        "base_summary": base_summary,
        "slippage_summary": slippage_summary,
        "comparison": comparison.to_dict(),
    }
    fingerprint = build_bundle_fingerprint(context, payload)
    canonical_dir = bundle_dir(root_dir, context, fingerprint)
    latest_view = latest_dir(root_dir, context)
    deduplicated = canonical_dir.exists()

    if not deduplicated:
        canonical_dir.mkdir(parents=True, exist_ok=True)
        _write_canonical_bundle(
            canonical_dir,
            context,
            base_summary,
            slippage_summary,
            comparison,
            trades,
            equity_curve,
        )
    else:
        _refresh_bundle_artifacts(
            canonical_dir,
            context,
            base_summary,
            slippage_summary,
            comparison,
            trades,
            equity_curve,
        )

    _write_history_record(root_dir, context, fingerprint, deduplicated)
    charts = _build_charts_payload(equity_curve, trades)
    _refresh_latest_view(
        latest_view,
        context,
        fingerprint,
        base_summary,
        slippage_summary,
        comparison,
        trades,
        charts,
    )
    update_global_index(root_dir)

    return WriteResult(
        fingerprint=fingerprint,
        bundle_dir=canonical_dir,
        latest_dir=latest_view,
        deduplicated=deduplicated,
    )


def _write_canonical_bundle(
    canonical_dir: Path,
    context: RunContext,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> None:
    run_meta = asdict(context)
    delta_summary = comparison["delta"].to_dict() if "delta" in comparison.columns else {}
    summary = {
        "identity": _build_identity_payload(context),
        "setup": _build_setup_payload(context),
        "base": base_summary,
        "slippage": slippage_summary,
        "delta": delta_summary,
    }

    (canonical_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))
    (canonical_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    trades.to_csv(canonical_dir / "trades.csv", index=False)
    equity_curve.to_csv(canonical_dir / "equity_curve.csv")
    comparison.to_csv(canonical_dir / "comparison.csv")
    _refresh_bundle_artifacts(
        canonical_dir,
        context,
        base_summary,
        slippage_summary,
        comparison,
        trades,
        equity_curve,
    )


def _refresh_bundle_artifacts(
    bundle_dir: Path,
    context: RunContext,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> None:
    llm_review = _build_llm_review_json(context, base_summary, slippage_summary, comparison)
    summary_md = _build_summary_markdown(context, base_summary, slippage_summary, comparison)
    llm_md = _build_llm_review_markdown(llm_review)
    charts = _build_charts_payload(equity_curve, trades)
    report_html = _build_report_html(
        context,
        base_summary,
        slippage_summary,
        comparison,
        charts,
        trades,
    )

    (bundle_dir / "summary.md").write_text(summary_md)
    (bundle_dir / "llm_review.json").write_text(json.dumps(llm_review, indent=2))
    (bundle_dir / "llm_review.md").write_text(llm_md)
    (bundle_dir / "charts.json").write_text(json.dumps(charts, indent=2))
    (bundle_dir / "report.html").write_text(report_html)


def _write_history_record(root_dir: Path, context: RunContext, fingerprint: str, deduplicated: bool) -> None:
    path = history_file(root_dir, context)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": context.timestamp,
        "strategy": context.strategy,
        "market": context.market,
        "instrument_type": context.instrument_type,
        "source": context.source,
        "symbols": list(context.symbols),
        "bundle_fingerprint": fingerprint,
        "deduplicated": deduplicated,
        "code_commit": context.code_commit,
    }
    path.write_text(json.dumps(payload, indent=2))


def _refresh_latest_view(
    latest_view: Path,
    context: RunContext,
    fingerprint: str,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    trades: pd.DataFrame,
    charts: dict,
) -> None:
    latest_view.mkdir(parents=True, exist_ok=True)
    payload = {
        "strategy": context.strategy,
        "timestamp": context.timestamp,
        "symbols": list(context.symbols),
        "bundle_fingerprint": fingerprint,
    }
    summary_md = _build_summary_markdown(context, base_summary, slippage_summary, comparison)
    report_html = _build_report_html(
        context,
        base_summary,
        slippage_summary,
        comparison,
        charts,
        trades,
    )

    (latest_view / "latest.json").write_text(json.dumps(payload, indent=2))
    (latest_view / "summary.md").write_text(summary_md)
    (latest_view / "report.html").write_text(report_html)


def _format_percentage(value: float) -> str:
    return f"{value:.2%}"


def _format_decimal(value: float) -> str:
    return f"{value:.2f}"


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _format_bool(value: bool) -> str:
    return "Yes" if value else "No"


def _build_identity_payload(context: RunContext) -> dict:
    return {
        "strategy": context.strategy,
        "market": context.market,
        "instrument_type": context.instrument_type,
        "source": context.source,
        "timestamp": context.timestamp,
        "symbols": list(context.symbols),
        "date_start": context.date_start,
        "date_end": context.date_end,
        "code_commit": context.code_commit,
    }


def _build_setup_payload(context: RunContext) -> dict:
    return {
        "entry_rsi_threshold": context.entry_rsi_threshold,
        "exit_rsi_threshold": context.exit_rsi_threshold,
        "max_hold_days": context.max_hold_days,
        "require_two_down_closes": context.require_two_down_closes,
        "use_rsi_exit": context.use_rsi_exit,
        "stop_loss_pct": context.stop_loss_pct,
        "slippage_bps": context.slippage_bps,
    }


def _build_summary_markdown(context: RunContext, base_summary: dict, slippage_summary: dict, comparison: pd.DataFrame) -> str:
    delta = comparison["delta"].to_dict() if "delta" in comparison.columns else {}
    return "\n".join(
        [
            f"# {context.strategy}",
            "",
            f"- Market: {context.market}",
            f"- Instrument: {context.instrument_type}",
            f"- Source: {context.source}",
            f"- Symbols: {', '.join(context.symbols)}",
            f"- Date Range: {context.date_start} to {context.date_end}",
            f"- Commit: {context.code_commit}",
            "",
            "## Base",
            f"- Total Return: {_format_percentage(float(base_summary.get('total_return', 0.0)))}",
            f"- Max Drawdown: {_format_percentage(float(base_summary.get('max_drawdown', 0.0)))}",
            f"- Win Rate: {_format_percentage(float(base_summary.get('win_rate', 0.0)))}",
            f"- Average Trade Return: {_format_percentage(float(base_summary.get('average_trade_return', 0.0)))}",
            f"- Number of Trades: {int(base_summary.get('number_of_trades', 0))}",
            "",
            "## Slippage",
            f"- Total Return: {_format_percentage(float(slippage_summary.get('total_return', 0.0)))}",
            f"- Max Drawdown: {_format_percentage(float(slippage_summary.get('max_drawdown', 0.0)))}",
            f"- Win Rate: {_format_percentage(float(slippage_summary.get('win_rate', 0.0)))}",
            f"- Average Trade Return: {_format_percentage(float(slippage_summary.get('average_trade_return', 0.0)))}",
            f"- Number of Trades: {int(slippage_summary.get('number_of_trades', 0))}",
            "",
            "## Delta",
            f"- Total Return Delta: {_format_percentage(float(delta.get('total_return', 0.0)))}",
            f"- Max Drawdown Delta: {_format_percentage(float(delta.get('max_drawdown', 0.0)))}",
        ]
    )


def _build_llm_review_json(context: RunContext, base_summary: dict, slippage_summary: dict, comparison: pd.DataFrame) -> dict:
    delta = comparison["delta"].to_dict() if "delta" in comparison.columns else {}
    return {
        "run_identity": {
            "strategy": context.strategy,
            "market": context.market,
            "instrument_type": context.instrument_type,
            "source": context.source,
            "timestamp": context.timestamp,
            "code_commit": context.code_commit,
        },
        "setup": _build_setup_payload(context),
        "universe": {
            "symbols": list(context.symbols),
            "date_range": {"start": context.date_start, "end": context.date_end},
        },
        "metrics": {
            "base": base_summary,
            "slippage": slippage_summary,
            "delta": delta,
        },
        "flags": {
            "has_zero_trades": int(base_summary.get("number_of_trades", 0)) == 0,
            "slippage_material": abs(
                float(slippage_summary.get("total_return", 0.0)) - float(base_summary.get("total_return", 0.0))
            )
            >= 0.01,
        },
        "artifacts": {
            "summary_md": "summary.md",
            "report_html": "report.html",
            "trades_csv": "trades.csv",
            "equity_curve_csv": "equity_curve.csv",
        },
    }


def _build_llm_review_markdown(payload: dict) -> str:
    identity = payload["run_identity"]
    universe = payload["universe"]
    base = payload["metrics"]["base"]
    slippage = payload["metrics"]["slippage"]
    delta = payload["metrics"]["delta"]
    notes = []
    if payload["flags"].get("slippage_material"):
        notes.append("- Slippage materially changes returns.")
    if payload["flags"].get("has_zero_trades"):
        notes.append("- Run produced zero trades.")
    if not notes:
        notes.append("- No notable automatic flags.")

    return "\n".join(
        [
            "# Run Review Package",
            "",
            "## Identity",
            f"- Strategy: {identity['strategy']}",
            f"- Market: {identity['market']}",
            f"- Instrument: {identity['instrument_type']}",
            f"- Source: {identity['source']}",
            f"- Symbols: {', '.join(universe['symbols'])}",
            f"- Date Range: {universe['date_range']['start']} to {universe['date_range']['end']}",
            f"- Commit: {identity['code_commit']}",
            "",
            "## Base Metrics",
            f"- Total Return: {_format_percentage(float(base.get('total_return', 0.0)))}",
            f"- Max Drawdown: {_format_percentage(float(base.get('max_drawdown', 0.0)))}",
            f"- Win Rate: {_format_percentage(float(base.get('win_rate', 0.0)))}",
            f"- Average Trade Return: {_format_percentage(float(base.get('average_trade_return', 0.0)))}",
            f"- Number of Trades: {int(base.get('number_of_trades', 0))}",
            "",
            "## Slippage Metrics",
            f"- Total Return: {_format_percentage(float(slippage.get('total_return', 0.0)))}",
            f"- Max Drawdown: {_format_percentage(float(slippage.get('max_drawdown', 0.0)))}",
            f"- Win Rate: {_format_percentage(float(slippage.get('win_rate', 0.0)))}",
            f"- Average Trade Return: {_format_percentage(float(slippage.get('average_trade_return', 0.0)))}",
            f"- Number of Trades: {int(slippage.get('number_of_trades', 0))}",
            "",
            "## Delta",
            f"- Total Return Delta: {_format_percentage(float(delta.get('total_return', 0.0)))}",
            f"- Max Drawdown Delta: {_format_percentage(float(delta.get('max_drawdown', 0.0)))}",
            "",
            "## Notes",
            *notes,
        ]
    )


def _build_charts_payload(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict:
    equity = equity_curve["equity"]
    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1
    trade_returns = trades.get("return_pct", pd.Series(dtype=float)).fillna(0.0)
    holding_days = _holding_period_days(trades)
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
            "returns": [float(value) for value in trade_returns],
        },
        "holding_period_distribution": {
            "days": holding_days,
        },
    }


def _holding_period_days(trades: pd.DataFrame) -> list[int]:
    if trades.empty or "entry_date" not in trades.columns or "exit_date" not in trades.columns:
        return []

    entry_dates = pd.to_datetime(trades["entry_date"], errors="coerce")
    exit_dates = pd.to_datetime(trades["exit_date"], errors="coerce")
    holding_periods = (exit_dates - entry_dates).dt.days.fillna(0).astype(int)
    return [max(0, int(value)) for value in holding_periods]


def _metric_card(title: str, summary: dict) -> str:
    return f"""
    <div class="card metric-card">
      <h3>{escape(title)}</h3>
      <dl class="metric-list">
        <div><dt>Total Return</dt><dd>{_format_percentage(float(summary.get('total_return', 0.0)))}</dd></div>
        <div><dt>Max Drawdown</dt><dd>{_format_percentage(float(summary.get('max_drawdown', 0.0)))}</dd></div>
        <div><dt>Win Rate</dt><dd>{_format_percentage(float(summary.get('win_rate', 0.0)))}</dd></div>
        <div><dt>Average Trade Return</dt><dd>{_format_percentage(float(summary.get('average_trade_return', 0.0)))}</dd></div>
        <div><dt>Average Win</dt><dd>{_format_percentage(float(summary.get('average_win', 0.0)))}</dd></div>
        <div><dt>Average Loss</dt><dd>{_format_percentage(float(summary.get('average_loss', 0.0)))}</dd></div>
        <div><dt>Number of Trades</dt><dd>{int(summary.get('number_of_trades', 0))}</dd></div>
      </dl>
    </div>
    """


def _svg_polyline(values: list[float], width: int = 720, height: int = 240, color: str = "#0f766e") -> str:
    if not values:
        return '<div class="empty-state">No data available.</div>'

    min_value = min(values)
    max_value = max(values)
    span = max_value - min_value or 1.0
    points = []
    for index, value in enumerate(values):
        x = 0 if len(values) == 1 else (index / (len(values) - 1)) * width
        y = height - (((value - min_value) / span) * height)
        points.append(f"{x:.2f},{y:.2f}")

    return f"""
    <svg viewBox="0 0 {width} {height}" class="line-chart" role="img" aria-label="Time series chart">
      <polyline fill="none" stroke="{color}" stroke-width="3" points="{' '.join(points)}"></polyline>
    </svg>
    """


def _histogram_bars(values: list[float], bucket_count: int = 8) -> str:
    if not values:
        return '<div class="empty-state">No data available.</div>'

    minimum = min(values)
    maximum = max(values)
    span = maximum - minimum
    if span == 0:
        buckets = [len(values)]
        labels = [f"{minimum:.2%}"]
    else:
        bucket_size = span / bucket_count
        buckets = [0] * bucket_count
        labels = []
        for bucket_index in range(bucket_count):
            lower = minimum + (bucket_index * bucket_size)
            upper = lower + bucket_size
            labels.append(f"{lower:.1%} to {upper:.1%}")
        for value in values:
            raw_index = int((value - minimum) / bucket_size)
            bucket_index = min(bucket_count - 1, raw_index)
            buckets[bucket_index] += 1

    max_count = max(buckets) or 1
    bars = []
    for label, count in zip(labels, buckets):
        height_pct = (count / max_count) * 100
        bars.append(
            f"""
            <div class="histogram-item">
              <div class="histogram-bar" style="height:{height_pct:.1f}%"></div>
              <div class="histogram-count">{count}</div>
              <div class="histogram-label">{escape(label)}</div>
            </div>
            """
        )
    return f'<div class="histogram">{"".join(bars)}</div>'


def _bar_chart(values: list[int]) -> str:
    if not values:
        return '<div class="empty-state">No data available.</div>'

    counts: dict[int, int] = {}
    for value in values:
        counts[int(value)] = counts.get(int(value), 0) + 1

    max_count = max(counts.values()) or 1
    bars = []
    for day, count in sorted(counts.items()):
        width_pct = (count / max_count) * 100
        bars.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{day}d</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width_pct:.1f}%"></div></div>
              <div class="bar-value">{count}</div>
            </div>
            """
        )
    return f'<div class="bar-chart">{"".join(bars)}</div>'


def _comparison_table(comparison: pd.DataFrame) -> str:
    if comparison.empty:
        return '<div class="empty-state">No comparison data available.</div>'

    rows = []
    for metric, row in comparison.iterrows():
        base = float(row.get("base", 0.0))
        slippage = float(row.get("slippage", 0.0))
        delta = float(row.get("delta", 0.0))
        rows.append(
            f"""
            <tr>
              <td>{escape(str(metric).replace('_', ' ').title())}</td>
              <td>{_format_percentage(base)}</td>
              <td>{_format_percentage(slippage)}</td>
              <td>{_format_percentage(delta)}</td>
            </tr>
            """
        )
    return f"""
    <table class="comparison-table">
      <thead>
        <tr><th>Metric</th><th>Base</th><th>Slippage</th><th>Delta</th></tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    """


def _setup_table(context: RunContext) -> str:
    rows = [
        ("Entry RSI Threshold", _format_decimal(context.entry_rsi_threshold)),
        ("Exit RSI Threshold", _format_decimal(context.exit_rsi_threshold)),
        ("Max Hold Days", str(context.max_hold_days)),
        ("Require Two Down Closes", _format_bool(context.require_two_down_closes)),
        ("Use RSI Exit", _format_bool(context.use_rsi_exit)),
        ("Stop Loss", _format_percentage(context.stop_loss_pct)),
        ("Slippage", f"{context.slippage_bps:.1f} bps"),
        ("Symbols", ", ".join(context.symbols)),
        ("Date Range", f"{context.date_start} to {context.date_end}"),
        ("Commit", context.code_commit),
    ]
    body = "".join(f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>" for label, value in rows)
    return f'<table class="setup-table"><tbody>{body}</tbody></table>'


def _trade_table(trades: pd.DataFrame) -> str:
    if trades.empty:
        return '<div class="empty-state">No trades available.</div>'

    preferred_columns = [
        ("symbol", "Symbol"),
        ("entry_date", "Entry Date"),
        ("exit_date", "Exit Date"),
        ("entry_price", "Entry Price"),
        ("exit_price", "Exit Price"),
        ("shares", "Shares"),
        ("pnl", "PnL"),
        ("return_pct", "Return"),
        ("exit_reason", "Exit Reason"),
    ]
    header = "".join(f"<th>{label}</th>" for _, label in preferred_columns)
    rows = []
    for _, trade in trades.iterrows():
        cells = []
        for column, _label in preferred_columns:
            value = trade.get(column, "")
            if column in {"entry_price", "exit_price", "pnl"} and value != "":
                rendered = _format_currency(float(value))
            elif column == "return_pct" and value != "":
                rendered = _format_percentage(float(value))
            else:
                rendered = str(value)
            cells.append(f"<td>{escape(rendered)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
    <table class="trade-table">
      <thead><tr>{header}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _build_report_html(
    context: RunContext,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    charts: dict,
    trades: pd.DataFrame,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(context.strategy)} Report</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: #fffdf8;
      --panel-alt: #f2ebe0;
      --border: #d8cdbd;
      --text: #2f261d;
      --muted: #6f6256;
      --accent: #0f766e;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Avenir Next", Avenir, "Helvetica Neue", Helvetica, Arial, sans-serif;
      margin: 0;
      background: linear-gradient(180deg, #f8f4eb 0%, #efe6d9 100%);
      color: var(--text);
    }}
    h1, h2, h3 {{
      font-family: "Avenir Next", Avenir, "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 10px 30px rgba(47, 38, 29, 0.05);
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      font-size: 12px;
      margin: 0 0 8px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px 20px;
      color: var(--muted);
      margin-top: 16px;
      font-size: 14px;
    }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 10px 30px rgba(47, 38, 29, 0.04);
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      align-items: start;
    }}
    .card {{
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      background: var(--panel-alt);
    }}
    .metric-list {{
      margin: 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 16px;
    }}
    .metric-list div {{
      border-top: 1px solid var(--border);
      padding-top: 8px;
    }}
    .metric-list dt {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .metric-list dd {{
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }}
    .line-chart {{
      width: 100%;
      height: auto;
      background: linear-gradient(180deg, #ffffff 0%, #f7f1e7 100%);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 8px;
    }}
    .histogram {{
      height: 220px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(60px, 1fr));
      gap: 10px;
      align-items: end;
    }}
    .histogram-item {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      height: 100%;
    }}
    .histogram-bar {{
      width: 100%;
      max-width: 48px;
      background: linear-gradient(180deg, var(--accent) 0%, #0b5e58 100%);
      border-radius: 10px 10px 4px 4px;
      min-height: 6px;
      margin-top: auto;
    }}
    .histogram-count, .histogram-label {{
      font-size: 12px;
      color: var(--muted);
      text-align: center;
    }}
    .bar-chart {{
      display: grid;
      gap: 10px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 56px 1fr 36px;
      gap: 10px;
      align-items: center;
    }}
    .bar-track {{
      height: 16px;
      background: #ece2d3;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, #b08968 0%, #7f5539 100%);
      border-radius: 999px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .comparison-table td:nth-child(4) {{
      color: var(--danger);
      font-weight: 600;
    }}
    .empty-state {{
      color: var(--muted);
      padding: 16px 0;
      font-style: italic;
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 20px 14px 32px; }}
      .metric-list {{ grid-template-columns: 1fr; }}
      .bar-row {{ grid-template-columns: 44px 1fr 28px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <p class="eyebrow">Backtest Report</p>
      <h1>{escape(context.strategy)}</h1>
      <div class="hero-meta">
        <span>Market: {escape(context.market)}</span>
        <span>Instrument: {escape(context.instrument_type)}</span>
        <span>Source: {escape(context.source)}</span>
        <span>Timestamp: {escape(context.timestamp)}</span>
      </div>
    </section>

    <section class="section">
      <h2>Performance Summary</h2>
      <div class="section-grid">
        {_metric_card("Base", base_summary)}
        {_metric_card("Slippage", slippage_summary)}
      </div>
      <div class="card">
        <h3>Comparison</h3>
        {_comparison_table(comparison)}
      </div>
    </section>

    <section class="section">
      <h2>Run Setup</h2>
      {_setup_table(context)}
    </section>

    <section class="section">
      <h2>Trade Outcome Distribution</h2>
      <div class="card">
        {_histogram_bars(charts["trade_return_distribution"]["returns"])}
      </div>
    </section>

    <section class="section">
      <h2>Trade Behavior</h2>
      <div class="card">
        {_bar_chart(charts["holding_period_distribution"]["days"])}
      </div>
    </section>

    <section class="section">
      <h2>Portfolio Path</h2>
      <div class="chart-grid">
        <div class="card">
          <h3>Equity Curve</h3>
          {_svg_polyline(charts["equity_curve"]["values"], color="#0f766e")}
        </div>
        <div class="card">
          <h3>Drawdown Curve</h3>
          {_svg_polyline(charts["drawdown_curve"]["values"], color="#b42318")}
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Full Trade Log</h2>
      {_trade_table(trades)}
    </section>
  </div>
</body>
</html>"""
