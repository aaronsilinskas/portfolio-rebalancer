# Rebalancing Stock Trader

This project will automatically rebalance funds across a set of stock indexes, where each index will have a target percentage of the total fund. It should be able to look at past stock data to report on what would've happened each month and if any stock drifts would've triggered rebalancing. Ideally, it would take a total fund amount and a date range to simulate, and then report on the total fund amount at the end date.

## High Level Notes

- Python scripts, run daily within an hour of market open on a local always-on machine
- **Scheduled rebalance:** 2nd Wednesday of each month
- **Drift rebalance:** configurable threshold (absolute or relative), defaulting to +/- 7.5% absolute from target weight
- Scheduled and drift rebalances merge into a single trade event; no more than one rebalance trade per week to reduce noise
- When rebalancing, stocks above target weight are sold to fund purchases of stocks below target weight until all are restored to targets
- **Tax considerations:** standard taxable account — no wash-sale or tax-lot optimization is built in initially, but trades should be logged clearly for manual review
- Balance across 10 configurable slots in a portfolio. Tickers and target weights are fully configurable. Default starting weights are 10% each. First-pass defaults:

  | #   | Category                  | Default Ticker | Description                                       |
  | --- | ------------------------- | -------------- | ------------------------------------------------- |
  | 1   | US Large-Cap Equities     | SPY            | S&P 500 — core US market exposure                 |
  | 2   | US Small/Mid-Cap Equities | VB             | Russell 2000 — smaller US firms for growth tilt   |
  | 3   | Developed ex-US Equities  | VEA            | FTSE Developed Markets — Europe, Japan, etc.      |
  | 4   | Emerging Markets Equities | VWO            | MSCI Emerging — China, India, Brazil growth       |
  | 5   | Global Real Estate        | VNQ            | US/Global REITs — property/income diversification |
  | 6   | Precious Metals/Gold      | GLD            | Gold — inflation hedge, low stock correlation     |
  | 7   | Broad Commodities         | DBC            | Commodity Basket — energy, metals, agriculture    |
  | 8   | Energy/Resources          | XLE            | Energy Select — oil/gas producers                 |
  | 9   | Bonds/Fixed Income        | BND            | Total Bond — defensive ballast                    |
  | 10  | Cash/Short-Term           | BIL            | T-Bills/Money Market — liquidity buffer           |

## Data & Execution

- **Price data:** Yahoo Finance (via `yfinance`)
- **Live trading:** manual execution — the system generates trade instructions but does not place orders automatically until confidence is high enough to automate via broker API
- **Daily checks:** use a local positions file with current fractional share counts so drift is measured against actual holdings, not a synthetic portfolio
- **Manual workflow:** the daily command writes dated output files with a summary, current holdings snapshot, trade instructions, and a projected `positions_after.yaml` file when rebalancing is needed

## Backtesting / Simulation

- Accepts a total fund amount and a date range
- Simulates monthly snapshots, drift checks, and rebalance events
- Does not model transaction costs or commissions
- Fractional shares are used throughout (both simulation and trade output); no rounding to whole shares
- **Output:** CSV of trades and portfolio state over time, plus an HTML report with charts

## Configuration

Key parameters that should be configurable per portfolio:

- Tickers (one per slot, swappable — e.g., SPY vs VOO)
- Target weights per ticker
- Current share counts for each ticker in a separate positions file used by the daily check
- Drift threshold value
- Drift threshold mode: `absolute` (percentage points) or `relative` (percentage of target weight)
- Rebalance schedule (default: 2nd Wednesday monthly)
- Minimum days between rebalance events (default: 7)

## Manual Daily Workflow

1. After any ticker changes, run `uv run rebalancer-sync-positions` to align `config/positions.yaml` with your portfolio config while preserving existing shares.
2. Keep [config/positions.yaml](/Users/AaronH/dev/finance/rebalancer/config/positions.yaml) updated manually as you establish positions.
3. Run `uv run rebalancer-daily`.
4. Review the dated folder under `output/daily/YYYY-MM-DD/`.
5. If trades are required, execute them manually and then update `config/positions.yaml` to match the projected `positions_after.yaml` output.
6. If positions are still zero while you are designing the portfolio, the daily command will skip rebalancing cleanly and still write a summary file.

## Ticker Comparison

Use the comparison command to evaluate multiple candidate tickers in the same category over a date range.

Example:

```bash
uv run rebalancer-compare \
  --category "US Large-Cap Equities" \
  --ticker SPY \
  --ticker VOO \
  --ticker IVV \
  --start 2024-01-01 \
  --end 2024-12-31
```

Outputs are written under `output/comparisons/<category>-<start>-to-<end>/`:

- `summary.csv` with return and risk metrics per ticker
- `prices.csv` with raw adjusted close prices
- `normalized_prices.csv` with each series normalized to 100 at its first date
- `comparison.html` with an interactive normalized performance chart
