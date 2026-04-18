from mean_reversion.results.fingerprint import build_bundle_fingerprint
from mean_reversion.results.models import RunContext


def test_build_bundle_fingerprint_is_stable_for_same_context_and_payload():
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
        "base": {"total_return": 0.14, "number_of_trades": 67},
        "slippage": {"total_return": 0.08, "number_of_trades": 67},
    }

    first = build_bundle_fingerprint(context, payload)
    second = build_bundle_fingerprint(context, payload)

    assert first == second


def test_build_bundle_fingerprint_changes_when_payload_changes():
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

    first = build_bundle_fingerprint(context, {"base": {"total_return": 0.14}})
    second = build_bundle_fingerprint(context, {"base": {"total_return": 0.12}})

    assert first != second
