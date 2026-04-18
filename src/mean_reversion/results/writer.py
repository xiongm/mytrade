from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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
        _write_canonical_bundle(canonical_dir, context, base_summary, slippage_summary, comparison, trades, equity_curve)

    _write_history_record(root_dir, context, fingerprint, deduplicated)
    _refresh_latest_view(latest_view, context, fingerprint, canonical_dir)
    update_global_index(root_dir)

    return WriteResult(fingerprint=fingerprint, bundle_dir=canonical_dir, latest_dir=latest_view, deduplicated=deduplicated)


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
        "base": base_summary,
        "slippage": slippage_summary,
        "delta": delta_summary,
    }
    llm_review = _build_llm_review_json(context, base_summary, slippage_summary, comparison)
    summary_md = _build_summary_markdown(context, base_summary, slippage_summary, comparison)
    llm_md = _build_llm_review_markdown(llm_review)
    charts = _build_charts_payload(equity_curve)
    report_html = _build_report_html(context, base_summary, slippage_summary, comparison, charts)

    (canonical_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))
    (canonical_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (canonical_dir / "summary.md").write_text(summary_md)
    (canonical_dir / "llm_review.json").write_text(json.dumps(llm_review, indent=2))
    (canonical_dir / "llm_review.md").write_text(llm_md)
    trades.to_csv(canonical_dir / "trades.csv", index=False)
    equity_curve.to_csv(canonical_dir / "equity_curve.csv")
    comparison.to_csv(canonical_dir / "comparison.csv")
    (canonical_dir / "charts.json").write_text(json.dumps(charts, indent=2))
    (canonical_dir / "report.html").write_text(report_html)


def _write_history_record(root_dir: Path, context: RunContext, fingerprint: str, deduplicated: bool) -> None:
    path = history_file(root_dir, context)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": context.timestamp,
        "strategy": context.strategy,
        "market": context.market,
        "instrument_type": context.instrument_type,
        "source": context.source,
        "bundle_fingerprint": fingerprint,
        "deduplicated": deduplicated,
        "code_commit": context.code_commit,
    }
    path.write_text(json.dumps(payload, indent=2))


def _refresh_latest_view(latest_view: Path, context: RunContext, fingerprint: str, canonical_dir: Path) -> None:
    latest_view.mkdir(parents=True, exist_ok=True)
    payload = {
        "strategy": context.strategy,
        "timestamp": context.timestamp,
        "bundle_fingerprint": fingerprint,
    }
    (latest_view / "latest.json").write_text(json.dumps(payload, indent=2))
    (latest_view / "summary.md").write_text((canonical_dir / "summary.md").read_text())
    (latest_view / "report.html").write_text((canonical_dir / "report.html").read_text())


def _format_percentage(value: float) -> str:
    return f"{value:.2%}"


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
            "slippage_material": abs(float(slippage_summary.get("total_return", 0.0)) - float(base_summary.get("total_return", 0.0))) >= 0.01,
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


def _build_charts_payload(equity_curve: pd.DataFrame) -> dict:
    equity = equity_curve["equity"]
    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1
    return {
        "equity_curve": {
            "dates": [str(index.date()) for index in equity_curve.index],
            "values": [float(value) for value in equity],
        },
        "drawdown_curve": {
            "dates": [str(index.date()) for index in equity_curve.index],
            "values": [float(value) for value in drawdown],
        },
    }


def _build_report_html(context: RunContext, base_summary: dict, slippage_summary: dict, comparison: pd.DataFrame, charts: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{context.strategy} Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{ border: 1px solid #ddd; padding: 16px; border-radius: 8px; background: #fafafa; }}
    pre {{ background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
  <h1>{context.strategy}</h1>
  <p>Market: {context.market} | Instrument: {context.instrument_type} | Source: {context.source}</p>
  <div class="grid">
    <div class="card">
      <h2>Base</h2>
      <p>Total Return: {_format_percentage(float(base_summary.get('total_return', 0.0)))}</p>
      <p>Win Rate: {_format_percentage(float(base_summary.get('win_rate', 0.0)))}</p>
      <p>Max Drawdown: {_format_percentage(float(base_summary.get('max_drawdown', 0.0)))}</p>
    </div>
    <div class="card">
      <h2>Slippage</h2>
      <p>Total Return: {_format_percentage(float(slippage_summary.get('total_return', 0.0)))}</p>
      <p>Win Rate: {_format_percentage(float(slippage_summary.get('win_rate', 0.0)))}</p>
      <p>Max Drawdown: {_format_percentage(float(slippage_summary.get('max_drawdown', 0.0)))}</p>
    </div>
  </div>
  <h2>Comparison</h2>
  {comparison.to_html()}
  <h2>Equity Curve</h2>
  <pre>{json.dumps(charts["equity_curve"], indent=2)}</pre>
  <h2>Drawdown Curve</h2>
  <pre>{json.dumps(charts["drawdown_curve"], indent=2)}</pre>
</body>
</html>"""
