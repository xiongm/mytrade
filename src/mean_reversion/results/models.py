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
