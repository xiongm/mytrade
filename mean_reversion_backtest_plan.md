# Mean Reversion Backtest Plan

## Goal
Build a **simple daily-bar mean reversion backtest** for a small retail account.  
No broker integration yet. No live trading yet.

## Strategy scope
- Style: **short-term mean reversion**
- Holding period: **2–5 trading days**
- Frequency: **daily bars only**
- Account assumption: **$10,000**
- Instruments for backtest:
  - `SPY` for market regime filter
  - `IVV`
  - `QQQ`
- Reason:
  - `QQQM` is fine for live trading later, but `QQQ` has much longer history for a cleaner 5-year backtest

## Version 1 rules

### Market filter
Only allow new long entries when:
- `SPY.close > SPY.200DMA`

### Entry rules
For each tradable symbol (`IVV`, `QQQ`):
- `close > 50DMA`
- last **2 closes were down**
- `RSI(2) < 15`

If all true on day `t`, enter on **next day open**.

### Exit rules
Exit when any of these is true:
- `RSI(2) > 60`
- holding period reaches **4 trading days**
- hard stop loss at **-3% from entry**

### Portfolio rules
- max **2 open positions**
- max **40% of portfolio per position**
- keep at least **20% cash**
- no leverage
- long only

## Backtest assumptions
- Use **daily OHLCV**
- Signals are computed from **close of day t**
- Entries happen at **open of day t+1**
- Exit by signal happens at **next open**
- Stop loss is approximated using **daily low**
- Ignore IBKR / broker API entirely for now

## Data
Use Python and start with:
- `yfinance`
- `pandas`
- `numpy`

Automate data download later, but for now just make backtest work.

## Minimum backtest horizon
- Use **5 years**
- One year is only enough for debugging, not enough to trust the strategy

## Deliverables for v1
Implement a Python backtest that:

1. Downloads historical daily data for:
   - `SPY`
   - `IVV`
   - `QQQ`

2. Computes indicators:
   - `SPY 200DMA`
   - `50DMA` for `IVV` and `QQQ`
   - `RSI(2)` for `IVV` and `QQQ`

3. Simulates trades with the exact rules above

4. Produces:
   - trade log
   - equity curve
   - total return
   - max drawdown
   - win rate
   - average trade return
   - average win / average loss
   - number of trades

## Engineering constraints
- Keep it **simple**
- No framework unless needed
- No database required for v1
- CSV or in-memory pandas is fine
- No optimization sweep yet
- No broker integration
- No dry run yet

## Validation after v1
Once the first backtest works:

1. Add **basic slippage assumption**
2. Check whether results still hold
3. Compare conservative vs more aggressive settings
4. Do **not** jump to live trading
5. Next step after backtest is:
   - dry run
   - then paper trade
   - then tiny live size

## Non-goals for now
Do **not** implement yet:
- IBKR integration
- live order placement
- paper trading API
- intraday signals
- options
- single-stock trading
- hyperparameter tuning
- portfolio optimizer
- production infra

## Suggested task breakdown for Codex

### Task 1
Create a Python script that downloads 5 years of daily OHLC data for `SPY`, `IVV`, and `QQQ`.

### Task 2
Add indicator calculations:
- 200DMA
- 50DMA
- RSI(2)
- two-down-days condition

### Task 3
Implement the backtest loop:
- next-open entries
- signal-based exits
- 3% stop
- 4-day max hold
- cash reserve and max position constraints

### Task 4
Generate outputs:
- `trades.csv`
- summary stats printed to console
- equity curve series

### Task 5
Add a second pass with simple slippage assumptions and compare results.

## One-line brief for Codex
Build a simple Python daily-bar backtester for a long-only ETF mean reversion strategy using `SPY` as a 200DMA market filter and trading `IVV` + `QQQ` on next-open execution, over 5 years of historical data, with fixed portfolio/risk rules and summary performance outputs.
