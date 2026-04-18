from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from .config import BacktestConfig


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def download_daily_bars(config: BacktestConfig) -> dict[str, pd.DataFrame]:
    end = datetime.now(tz=UTC).date()
    start = end - timedelta(days=(365 * config.lookback_years) + 30)
    frames: dict[str, pd.DataFrame] = {}

    for symbol in config.symbols:
        raw = yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            progress=False,
        )
        if raw.empty:
            raise ValueError(f"No data returned for {symbol}")

        frames[symbol] = normalize_symbol_frame(raw.reset_index())

    validate_symbol_frames(frames)
    return frames


def normalize_symbol_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        flattened_columns = []
        for first, second in raw.columns.to_flat_index():
            if first == "Date":
                flattened_columns.append("Date")
            elif isinstance(first, str) and first:
                flattened_columns.append(first)
            elif isinstance(second, str) and second:
                flattened_columns.append(second)
            else:
                flattened_columns.append(str(first))
        raw = raw.copy()
        raw.columns = flattened_columns

    renamed = raw.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    frame = renamed.loc[:, ["date", *[column for column in REQUIRED_COLUMNS if column in renamed.columns]]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False)
    frame = frame.set_index("date").sort_index()
    frame.index.name = "date"

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return frame


def validate_symbol_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No symbol frames supplied")

    indexes = [frame.index for frame in frames.values()]
    first = indexes[0]
    for index in indexes[1:]:
        if not first.equals(index):
            raise ValueError("All symbol frames must share the same date index")
