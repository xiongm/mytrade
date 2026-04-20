from dataclasses import dataclass

from .entry_20 import MeanReversionEntry20Strategy


@dataclass(frozen=True)
class MeansREversionsFixedExit6Strategy(MeanReversionEntry20Strategy):
    name: str = "mean_reversion_exit_6"
    max_hold_days: int = 6
    use_rsi_exit: bool = False
