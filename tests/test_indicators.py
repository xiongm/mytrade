import pandas as pd

from mean_reversion.indicators import compute_rsi, enrich_symbol_frame


def test_compute_rsi_returns_expected_series_shape():
    closes = pd.Series([100, 99, 98, 99, 100, 101], dtype=float)

    rsi = compute_rsi(closes, period=2)

    assert len(rsi) == len(closes)
    assert rsi.index.equals(closes.index)
    assert rsi.iloc[-1] > 50


def test_enrich_symbol_frame_adds_trend_rsi_and_two_down_days():
    frame = pd.DataFrame(
        {
            "open": [10, 10, 9, 8, 9],
            "high": [10, 10, 9, 9, 10],
            "low": [9, 9, 8, 7, 8],
            "close": [10, 9, 8, 9, 10],
            "volume": [100] * 5,
        },
        index=pd.date_range("2026-01-01", periods=5, freq="D", name="date"),
    )

    enriched = enrich_symbol_frame(frame, ma_window=3, rsi_window=2)

    assert "ma_3" in enriched.columns
    assert "rsi_2" in enriched.columns
    assert "two_down_closes" in enriched.columns
    assert bool(enriched.iloc[2]["two_down_closes"]) is True
