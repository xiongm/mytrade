from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    name: str
    market_symbol: str
    trade_symbols: tuple[str, ...]

    def required_symbols(self) -> tuple[str, ...]:
        ...

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...


def validate_signal_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No strategy frames supplied")
    for symbol, frame in frames.items():
        missing = [column for column in ("entry_signal", "exit_signal") if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol} is missing required signal columns: {missing}")
