from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionExit70Strategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_exit_70"
    exit_rsi_threshold: float = 70.0
