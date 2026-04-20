from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...indicators import enrich_symbol_frame


@dataclass(frozen=True)
class MeanReversionV1Strategy:
    name: str = "mean_reversion_v1"
    market_symbol: str = "SPY"
    trade_symbols: tuple[str, ...] = ("IVV", "QQQ")
    market_ma_window: int = 200
    trend_ma_window: int = 50
    rsi_window: int = 2
    entry_rsi_threshold: float = 15.0
    exit_rsi_threshold: float = 60.0
    require_two_down_closes: bool = True
    use_rsi_exit: bool = True

    def required_symbols(self) -> tuple[str, ...]:
        return (self.market_symbol, *self.trade_symbols)

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        market = enrich_symbol_frame(
            frames[self.market_symbol],
            ma_window=self.market_ma_window,
            rsi_window=self.rsi_window,
        ).rename(columns={f"ma_{self.market_ma_window}": "market_ma"})
        market["market_ok"] = market["close"] > market["market_ma"]

        prepared = {self.market_symbol: market}
        for symbol in self.trade_symbols:
            prepared[symbol] = enrich_symbol_frame(
                frames[symbol],
                ma_window=self.trend_ma_window,
                rsi_window=self.rsi_window,
            ).rename(
                columns={
                    f"ma_{self.trend_ma_window}": "trend_ma",
                    f"rsi_{self.rsi_window}": "rsi",
                }
            )
        return prepared

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        market = frames[self.market_symbol].copy()
        signal_frames = {self.market_symbol: market}

        for symbol in self.trade_symbols:
            enriched = frames[symbol].copy()
            entry_signal = (
                market["market_ok"]
                & (enriched["close"] > enriched["trend_ma"])
                & (enriched["rsi"] < self.entry_rsi_threshold)
            )
            if self.require_two_down_closes:
                entry_signal = entry_signal & enriched["two_down_closes"]
            enriched["entry_signal"] = entry_signal
            enriched["exit_signal"] = (
                enriched["rsi"] > self.exit_rsi_threshold if self.use_rsi_exit else False
            )
            signal_frames[symbol] = enriched

        return signal_frames
