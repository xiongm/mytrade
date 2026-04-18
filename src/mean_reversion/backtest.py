from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import BacktestConfig


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.DataFrame


def run_backtest(
    frames: dict[str, pd.DataFrame],
    config: BacktestConfig,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    dates = frames[config.market_symbol].index
    cash = config.initial_cash
    open_positions: dict[str, dict[str, object]] = {}
    trades: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []

    for i, date in enumerate(dates):
        for symbol, position in list(open_positions.items()):
            frame = frames[symbol]
            row = frame.loc[date]
            stop_price = float(position["entry_price"]) * (1 - config.stop_loss_pct)
            bars_held = int(position["bars_held"])

            if row["low"] <= stop_price:
                exit_price = stop_price * (1 - slippage_bps / 10_000)
                cash += float(position["shares"]) * exit_price
                trades.append(_close_trade(symbol, position, date, exit_price, "stop_loss"))
                del open_positions[symbol]
                continue

            if bool(row.get("exit_signal", False)) or bars_held >= config.max_hold_days:
                next_open = _next_open(frame, i)
                if next_open is not None:
                    exit_reason = "signal" if bool(row.get("exit_signal", False)) else "max_hold"
                    exit_price = next_open * (1 - slippage_bps / 10_000)
                    cash += float(position["shares"]) * exit_price
                    trades.append(_close_trade(symbol, position, dates[i + 1], exit_price, exit_reason))
                    del open_positions[symbol]
                    continue

            position["bars_held"] = bars_held + 1

        positions_value = sum(
            float(position["shares"]) * float(frames[symbol].loc[date, "close"])
            for symbol, position in open_positions.items()
        )
        equity_rows.append(
            {
                "date": date,
                "cash": cash,
                "positions_value": positions_value,
                "equity": cash + positions_value,
            }
        )

        if i >= len(dates) - 1:
            continue

        if len(open_positions) >= config.max_positions:
            continue

        cash_floor = config.initial_cash * config.min_cash_weight
        max_position_dollars = config.initial_cash * config.max_position_weight

        for symbol in config.trade_symbols:
            if len(open_positions) >= config.max_positions:
                break
            if symbol in open_positions:
                continue

            row = frames[symbol].loc[date]
            if not bool(row.get("entry_signal", False)):
                continue

            available_for_position = min(max_position_dollars, cash - cash_floor)
            if available_for_position <= 0:
                continue

            entry_open = float(frames[symbol].iloc[i + 1]["open"]) * (1 + slippage_bps / 10_000)
            shares = int(available_for_position // entry_open)
            if shares <= 0:
                continue

            cost = shares * entry_open
            cash -= cost
            open_positions[symbol] = {
                "entry_date": dates[i + 1],
                "entry_price": entry_open,
                "shares": shares,
                "bars_held": 1,
                "cost": cost,
            }

    trades_frame = pd.DataFrame(trades)
    equity_curve = pd.DataFrame(equity_rows).set_index("date")
    return BacktestResult(trades=trades_frame, equity_curve=equity_curve)


def _next_open(frame: pd.DataFrame, index: int) -> float | None:
    if index + 1 >= len(frame):
        return None
    return float(frame.iloc[index + 1]["open"])


def _close_trade(
    symbol: str,
    position: dict[str, object],
    exit_date: pd.Timestamp,
    exit_price: float,
    exit_reason: str,
) -> dict[str, object]:
    entry_price = float(position["entry_price"])
    shares = int(position["shares"])
    pnl = shares * (exit_price - entry_price)
    return {
        "symbol": symbol,
        "entry_date": position["entry_date"],
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "shares": shares,
        "pnl": pnl,
        "return_pct": (exit_price / entry_price) - 1,
        "exit_reason": exit_reason,
    }
