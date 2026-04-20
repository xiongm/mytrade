from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionEntry10Strategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_entry_10"
    entry_rsi_threshold: float = 10.0
    exit_rsi_threshold: float = 60.0
    max_hold_days: int = 4
    require_two_down_closes: bool = False
