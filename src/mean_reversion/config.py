from dataclasses import dataclass, field


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000.0
    market_symbol: str = "SPY"
    trade_symbols: tuple[str, ...] = ("IVV", "QQQ")
    lookback_years: int = 5
    max_positions: int = 2
    max_position_weight: float = 0.40
    min_cash_weight: float = 0.20
    max_hold_days: int = 4
    stop_loss_pct: float = 0.03
    entry_rsi_threshold: float = 15.0
    exit_rsi_threshold: float = 60.0
    market_ma_window: int = 200
    trend_ma_window: int = 50
    rsi_window: int = 2
    slippage_bps: float = 10.0
    output_dir: str = "artifacts/mean_reversion"
    symbols: tuple[str, ...] = field(default=("SPY", "IVV", "QQQ"), init=False)
