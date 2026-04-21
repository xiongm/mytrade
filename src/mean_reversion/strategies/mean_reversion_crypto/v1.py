from __future__ import annotations

from dataclasses import dataclass

from .base import MeanReversionCryptoStrategyBase


@dataclass(frozen=True)
class MeanReversionCryptoV1Strategy(MeanReversionCryptoStrategyBase):
    name: str = "mean_reversion_crypto_v1"
    market_symbol: str = "BTC-USD"
    trade_symbols: tuple[str, ...] = ("ETH-USD",)
    require_two_down_closes: bool = False
    use_market_filter: bool = False
