from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionEntry20Strategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_entry_20"
    entry_rsi_threshold: float = 20.0
    require_two_down_closes: bool = False
    #exit_rsi_threshold: float = 70.0
    #max_hold_days: int = 5
