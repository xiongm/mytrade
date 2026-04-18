from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100.0)


def enrich_symbol_frame(frame: pd.DataFrame, ma_window: int, rsi_window: int) -> pd.DataFrame:
    enriched = frame.copy()
    enriched[f"ma_{ma_window}"] = enriched["close"].rolling(ma_window, min_periods=ma_window).mean()
    enriched[f"rsi_{rsi_window}"] = compute_rsi(enriched["close"], period=rsi_window)
    enriched["two_down_closes"] = (
        enriched["close"].lt(enriched["close"].shift(1))
        & enriched["close"].shift(1).lt(enriched["close"].shift(2))
    )
    return enriched
