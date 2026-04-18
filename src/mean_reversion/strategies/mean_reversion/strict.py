from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionStrictStrategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_strict"
    entry_rsi_threshold: float = 10.0
