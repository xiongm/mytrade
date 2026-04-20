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
