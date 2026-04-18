from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionFastExitStrategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_fast_exit"
    exit_rsi_threshold: float = 50.0
