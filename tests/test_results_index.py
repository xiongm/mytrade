from pathlib import Path
import json
from mean_reversion.results.index_generator import update_global_index

def test_update_global_index_creates_html_with_expected_content(tmp_path):
    results_root = tmp_path / "results"
    strategy_dir = results_root / "mean_reversion_v1" / "us__etf__yfinance"
    
    # Create a mock bundle
    bundle_dir = strategy_dir / "bundles" / "abc123"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "summary.json").write_text(json.dumps({
        "base": {"total_return": 0.14, "win_rate": 0.79, "max_drawdown": -0.02},
        "slippage": {"total_return": 0.08, "win_rate": 0.74, "max_drawdown": -0.03}
    }))
    
    # Create a mock latest pointer
    latest_dir = strategy_dir / "latest"
    latest_dir.mkdir(parents=True)
    (latest_dir / "latest.json").write_text(json.dumps({
        "strategy": "mean_reversion_v1",
        "timestamp": "2026-04-18T14-10-00",
        "bundle_fingerprint": "abc123"
    }))
    
    # Create a mock history record
    history_dir = strategy_dir / "history"
    history_dir.mkdir(parents=True)
    (history_dir / "2026-04-18T14-10-00.json").write_text(json.dumps({
        "timestamp": "2026-04-18T14-10-00",
        "strategy": "mean_reversion_v1",
        "market": "us",
        "instrument_type": "etf",
        "source": "yfinance",
        "bundle_fingerprint": "abc123"
    }))

    update_global_index(results_root)

    index_path = results_root / "index.html"
    assert index_path.exists()
    content = index_path.read_text()
    assert "mean_reversion_v1" in content
    assert "14.00%" in content  # Total return formatted
