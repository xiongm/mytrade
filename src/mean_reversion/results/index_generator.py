from pathlib import Path
import json
from datetime import datetime

def update_global_index(root_dir: Path) -> None:
    history_records = []
    latest_results = []
    
    # Walk the directory to find history and latest results
    if not root_dir.exists():
        return

    for strategy_dir in root_dir.iterdir():
        if not strategy_dir.is_dir(): continue
        for bucket_dir in strategy_dir.iterdir():
            if not bucket_dir.is_dir(): continue
            
            # Collect history for Recent Activity
            hist_dir = bucket_dir / "history"
            if hist_dir.exists():
                for h_file in hist_dir.glob("*.json"):
                    try:
                        data = json.loads(h_file.read_text())
                        # Get metrics from bundle
                        bundle_summary_path = bucket_dir / "bundles" / data["bundle_fingerprint"] / "summary.json"
                        if bundle_summary_path.exists():
                            summary = json.loads(bundle_summary_path.read_text())
                            data["metrics"] = summary.get("base", {})
                            data["market_full"] = bucket_dir.name
                            data["report_path"] = f"{strategy_dir.name}/{bucket_dir.name}/bundles/{data['bundle_fingerprint']}/report.html"
                            history_records.append(data)
                    except Exception: continue

            # Collect latest for Leaderboard
            latest_path = bucket_dir / "latest" / "latest.json"
            if latest_path.exists():
                try:
                    l_data = json.loads(latest_path.read_text())
                    bundle_summary_path = bucket_dir / "bundles" / l_data["bundle_fingerprint"] / "summary.json"
                    if bundle_summary_path.exists():
                        summary = json.loads(bundle_summary_path.read_text())
                        l_data["metrics"] = summary.get("base", {})
                        l_data["market_full"] = bucket_dir.name
                        l_data["report_path"] = f"{strategy_dir.name}/{bucket_dir.name}/latest/report.html"
                        latest_results.append(l_data)
                except Exception: continue

    # Sort data
    recent_activity = sorted(history_records, key=lambda x: x["timestamp"], reverse=True)[:5]
    leaderboard = sorted(latest_results, key=lambda x: x["metrics"].get("total_return", 0), reverse=True)

    # Generate HTML
    html = _generate_html(recent_activity, leaderboard)
    (root_dir / "index.html").write_text(html)

def _generate_html(recent, leaderboard):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Stub for Step 3, Task 1
    recent_list = "".join([f"<li>{r['strategy']} - {r['metrics'].get('total_return', 0):.2%}</li>" for r in recent])
    return f"<html><body><h1>Results Portal</h1><p>Updated: {now}</p><ul>{recent_list}</ul></body></html>"
