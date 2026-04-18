import pandas as pd
import json

from mean_reversion.results.models import RunContext
from mean_reversion.results.writer import write_results_bundle


def test_write_results_bundle_creates_canonical_bundle_and_latest_view(tmp_path):
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
    )
    base_summary = {"total_return": 0.14, "max_drawdown": -0.02, "win_rate": 0.79, "average_trade_return": 0.005, "average_win": 0.01, "average_loss": -0.013, "number_of_trades": 67}
    slippage_summary = {"total_return": 0.08, "max_drawdown": -0.03, "win_rate": 0.74, "average_trade_return": 0.003, "average_win": 0.009, "average_loss": -0.014, "number_of_trades": 67}
    comparison = pd.DataFrame({"base": [0.14], "slippage": [0.08], "delta": [-0.06]}, index=["total_return"])
    trades = pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01}])
    equity_curve = pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date"))

    result = write_results_bundle(
        root_dir=tmp_path / "results",
        context=context,
        base_summary=base_summary,
        slippage_summary=slippage_summary,
        comparison=comparison,
        trades=trades,
        equity_curve=equity_curve,
    )

    assert result.bundle_dir.exists()
    assert (result.bundle_dir / "run_meta.json").exists()
    assert (result.bundle_dir / "summary.md").exists()
    assert (result.bundle_dir / "llm_review.json").exists()
    assert (result.bundle_dir / "report.html").exists()
    assert (result.latest_dir / "latest.json").exists()
    assert (result.latest_dir / "summary.md").exists()
    assert (result.latest_dir / "report.html").exists()


def test_write_results_bundle_deduplicates_identical_second_run(tmp_path):
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
    )
    payload = {
        "base_summary": {"total_return": 0.14, "number_of_trades": 67},
        "slippage_summary": {"total_return": 0.08, "number_of_trades": 67},
        "comparison": pd.DataFrame({"base": [0.14], "slippage": [0.08], "delta": [-0.06]}, index=["total_return"]),
        "trades": pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01}]),
        "equity_curve": pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
    }

    first = write_results_bundle(root_dir=tmp_path / "results", context=context, **payload)
    second_context = RunContext(**{**context.__dict__, "timestamp": "2026-04-18T14-20-00"})
    second = write_results_bundle(root_dir=tmp_path / "results", context=second_context, **payload)

    assert first.fingerprint == second.fingerprint
    assert second.deduplicated is True
    history_dir = tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "history"
    assert len(list(history_dir.glob("*.json"))) == 2


def _make_written_result(tmp_path):
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
    )
    base_summary = {"total_return": 0.14, "max_drawdown": -0.02, "win_rate": 0.79, "average_trade_return": 0.005, "average_win": 0.01, "average_loss": -0.013, "number_of_trades": 67}
    slippage_summary = {"total_return": 0.08, "max_drawdown": -0.03, "win_rate": 0.74, "average_trade_return": 0.003, "average_win": 0.009, "average_loss": -0.014, "number_of_trades": 67}
    comparison = pd.DataFrame({"base": [0.14, -0.02], "slippage": [0.08, -0.03], "delta": [-0.06, -0.01]}, index=["total_return", "max_drawdown"])
    trades = pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01}])
    equity_curve = pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date"))
    return write_results_bundle(
        root_dir=tmp_path / "results",
        context=context,
        base_summary=base_summary,
        slippage_summary=slippage_summary,
        comparison=comparison,
        trades=trades,
        equity_curve=equity_curve,
    )


def test_summary_md_contains_human_review_sections(tmp_path):
    result = _make_written_result(tmp_path)
    text = (result.bundle_dir / "summary.md").read_text()

    assert "# mean_reversion_v1" in text
    assert "## Base" in text
    assert "## Slippage" in text
    assert "## Delta" in text


def test_llm_review_json_contains_identity_metrics_flags_and_artifact_refs(tmp_path):
    result = _make_written_result(tmp_path)
    payload = json.loads((result.bundle_dir / "llm_review.json").read_text())

    assert payload["run_identity"]["strategy"] == "mean_reversion_v1"
    assert "base" in payload["metrics"]
    assert "slippage" in payload["metrics"]
    assert "delta" in payload["metrics"]
    assert "artifacts" in payload
    assert "flags" in payload


def test_charts_json_contains_equity_and_drawdown_series(tmp_path):
    result = _make_written_result(tmp_path)
    charts = json.loads((result.bundle_dir / "charts.json").read_text())

    assert "equity_curve" in charts
    assert "drawdown_curve" in charts


def test_report_html_contains_key_metrics_and_metadata(tmp_path):
    result = _make_written_result(tmp_path)
    html = (result.bundle_dir / "report.html").read_text()

    assert "mean_reversion_v1" in html
    assert "Total Return" in html
    assert "Win Rate" in html
    assert "yfinance" in html


def test_latest_json_points_to_latest_resolved_fingerprint(tmp_path):
    _make_written_result(tmp_path)
    result = _make_written_result(tmp_path)

    latest = json.loads((result.latest_dir / "latest.json").read_text())

    assert latest["bundle_fingerprint"] == result.fingerprint
    assert latest["timestamp"] == "2026-04-18T14-10-00"
