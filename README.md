# Portfolio Rebalancer

Toolkit for designing, testing, and operating a diversified 10-slot ETF portfolio with manual trade execution.

Primary purpose: generate monthly stock rebalancing recommendations so the portfolio stays aligned to target weights over time.

This repository is organized around a practical lifecycle that supports monthly rebalancing operations:

1. Compare candidate tickers for each portfolio slot.
2. Backtest the full target allocation over a historical window.
3. Ramp into the portfolio with staged contributions.
4. Run daily checks and manually apply recommendations.

## Core Assumptions

- Price data source: Yahoo Finance (via `yfinance`)
- Trading model: recommendations only (no broker order placement)
- Rebalance schedule: second Wednesday monthly
- Drift trigger: configurable absolute or relative threshold
- Minimum spacing: at most one rebalance event every 7 days by default
- Fractional shares supported for planning, simulation, and daily recommendations

## Default Portfolio (`config/portfolio.yaml`)

| #   | Category                  | Default Ticker | Description                       |
| --- | ------------------------- | -------------- | --------------------------------- |
| 1   | US Large-Cap Equities     | VOO            | S&P 500 core exposure             |
| 2   | US Small/Mid-Cap Equities | VO             | US mid-cap growth tilt            |
| 3   | Developed ex-US Equities  | VEA            | Developed international markets   |
| 4   | Emerging Markets Equities | IEMG           | Broad emerging markets exposure   |
| 5   | Global Real Estate        | REET           | Global REIT exposure              |
| 6   | Precious Metals/Gold      | GLD            | Gold as diversifier               |
| 7   | Broad Commodities         | BCI            | Diversified commodities exposure  |
| 8   | Energy/Resources          | IXC            | Global energy producers           |
| 9   | Bonds/Fixed Income        | VGIT           | Intermediate US Treasury exposure |
| 10  | Cash/Short-Term           | USFR           | Floating-rate Treasury notes      |

## CLI Surface

Primary grouped command:

- `uv run rebalancer simulator ...`
- `uv run rebalancer ramp ...`
- `uv run rebalancer rebalance ...`

## Phase 1: Ticker Comparison

Use this first whenever you are deciding between alternatives for a category.

```bash
uv run rebalancer simulator compare \
  --category "US Large-Cap Equities" \
  --ticker SPY \
  --ticker VOO \
  --ticker IVV \
  --start 2024-01-01 \
  --end 2024-12-31
```

Output folder pattern:

- `output/comparisons/<category>-<start>-to-<end>/summary.csv`
- `output/comparisons/<category>-<start>-to-<end>/prices.csv`
- `output/comparisons/<category>-<start>-to-<end>/normalized_prices.csv`
- `output/comparisons/<category>-<start>-to-<end>/comparison.html`

When you pick winners, update `config/portfolio.yaml` and sync positions:

```bash
uv run rebalancer rebalance sync-positions
```

## Phase 2: Portfolio Backtest Simulation

After selecting tickers and target weights, validate behavior over time with a full simulation.

By default, simulation also overlays S&P 500 (`^GSPC`) and NASDAQ (`^IXIC`) benchmarks over the same date range.

```bash
uv run rebalancer simulator run \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --cash 100000
```

Review these outputs:

- `output/snapshots.csv` for time-series portfolio state
- `output/trades.csv` for rebalance trade events
- `output/benchmark_values.csv` for benchmark value-series normalized to starting cash
- `output/report.html` for cumulative portfolio behavior

Use this phase to answer:

- How often rebalances trigger under current drift settings
- How portfolio value evolves under your chosen mix
- Whether threshold/schedule settings look operationally realistic

## Phase 3: Ramp-Up to Target Allocation

Use ramp tools while funding the portfolio in stages.

Backtest a staged funding plan first:

```bash
uv run rebalancer ramp backtest \
  --step 2026-01:stage1:10000 \
  --step 2026-02:stage2:10000 \
  --step 2026-03:final:10000 \
  --valuation-date 2026-03-10
```

Output folder pattern:

- `output/ramp-backtests/YYYY-MM-DD-ramp-backtest/progression.csv`
- `output/ramp-backtests/YYYY-MM-DD-ramp-backtest/positions_after.yaml`
- `output/ramp-backtests/YYYY-MM-DD-ramp-backtest/summary.txt`

On contribution day, generate a buy plan:

```bash
uv run rebalancer ramp plan \
  --contribution 5000 \
  --stage stage1
```

Or infer stage from funded ratio:

```bash
uv run rebalancer ramp plan \
  --contribution 5000 \
  --funded-ratio 0.35
```

Stage rules:

- `stage1`: funded ratio `<= 0.30`
- `stage2`: funded ratio `<= 0.70`
- `final`: funded ratio `> 0.70`

Ramp output folder pattern:

- `output/ramp-plans/YYYY-MM-DD-<stage>/ramp_plan.csv`

## Phase 4: Daily Operations and Rebalancing

Once funded, run the daily check near market open.

```bash
uv run rebalancer rebalance daily
```

Daily output folder pattern:

- `output/daily/YYYY-MM-DD/summary.txt`
- `output/daily/YYYY-MM-DD/holdings.csv`
- `output/daily/YYYY-MM-DD/trades.csv` (when action is required)
- `output/daily/YYYY-MM-DD/positions_current.yaml`
- `output/daily/YYYY-MM-DD/positions_after.yaml` (when action is required)

Daily statuses you should expect:

- No action needed
- Trigger detected but already at target
- Rebalance required (trades listed)
- Skipped because positions are unfunded

## Manual Recommendation Application Checklist

Use this checklist after every ramp plan or daily rebalance recommendation.

1. Run the relevant command and open the dated output folder.
2. Review `summary.txt` and `trades.csv` for ticker, action, shares, and dollar amounts.
3. Place orders manually in your broker.
4. Confirm actual fills and adjust for any partial fills.
5. Update `config/positions.yaml` to match actual post-trade shares.
6. Re-run the same command to confirm the recommendation now resolves cleanly.

## Key Configuration Files

- `config/portfolio.yaml`: holdings, labels, target weights, schedule, and drift settings
- `config/positions.yaml`: current shares used for live drift and rebalance calculations

## Practical Notes

- No transaction costs, slippage, taxes, or lot-level optimization are modeled.
- Recommendations are decision support; execution remains manual.
- Keep outputs for auditability and strategy review.
