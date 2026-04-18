from __future__ import annotations

import hashlib
import json

from .models import RunContext


def build_bundle_fingerprint(context: RunContext, payload: dict) -> str:
    fingerprint_payload = {
        "context": {
            "strategy": context.strategy,
            "market": context.market,
            "instrument_type": context.instrument_type,
            "source": context.source,
            "symbols": list(context.symbols),
            "date_start": context.date_start,
            "date_end": context.date_end,
            "slippage_bps": context.slippage_bps,
            "code_commit": context.code_commit,
        },
        "payload": payload,
    }
    encoded = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
