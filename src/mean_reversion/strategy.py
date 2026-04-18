from __future__ import annotations

import pandas as pd

from .config import BacktestConfig
from .indicators import enrich_symbol_frame


def build_signal_frames(
    frames: dict[str, pd.DataFrame],
    config: BacktestConfig,
) -> dict[str, pd.DataFrame]:
    market = enrich_symbol_frame(
        frames[config.market_symbol],
        ma_window=config.market_ma_window,
        rsi_window=config.rsi_window,
    ).rename(columns={f"ma_{config.market_ma_window}": "market_ma"})
    market["market_ok"] = market["close"] > market["market_ma"]

    signal_frames: dict[str, pd.DataFrame] = {config.market_symbol: market}

    for symbol in config.trade_symbols:
        enriched = enrich_symbol_frame(
            frames[symbol],
            ma_window=config.trend_ma_window,
            rsi_window=config.rsi_window,
        ).rename(
            columns={
                f"ma_{config.trend_ma_window}": "trend_ma",
                f"rsi_{config.rsi_window}": "rsi",
            }
        )
        enriched["entry_signal"] = (
            market["market_ok"]
            & (enriched["close"] > enriched["trend_ma"])
            & enriched["two_down_closes"]
            & (enriched["rsi"] < config.entry_rsi_threshold)
        )
        enriched["exit_signal"] = enriched["rsi"] > config.exit_rsi_threshold
        signal_frames[symbol] = enriched

    return signal_frames
