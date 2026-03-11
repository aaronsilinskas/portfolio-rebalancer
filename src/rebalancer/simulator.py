"""
simulator.py — Backtesting engine: walk through a date range, check drift and schedule,
and apply rebalances as needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from rebalancer.config import PortfolioConfig
from rebalancer.portfolio import Portfolio
from rebalancer.rebalancer import Trade, apply_trades, compute_trades


def is_second_wednesday(d: date) -> bool:
    """Return True if `d` is the 2nd Wednesday of its month."""
    if d.weekday() != 2:  # Wednesday == 2
        return False
    # Count how many Wednesdays have occurred in the month up to and including d
    wednesday_count = sum(
        1 for day in range(1, d.day + 1) if date(d.year, d.month, day).weekday() == 2
    )
    return wednesday_count == 2


@dataclass
class DailySnapshot:
    date: date
    total_value: float
    weights: dict[str, float]
    rebalanced: bool
    trades: list[Trade] = field(default_factory=list)


def run_simulation(
    config: PortfolioConfig,
    prices: pd.DataFrame,
    initial_cash: float,
) -> list[DailySnapshot]:
    """
    Run a backtest over the full range of `prices`.

    Parameters
    ----------
    config : PortfolioConfig
        Portfolio settings (targets, drift rules, schedule).
    prices : pd.DataFrame
        Date-indexed DataFrame of adjusted closing prices per ticker.
    initial_cash : float
        Starting cash to allocate across holdings.

    Returns
    -------
    list[DailySnapshot]
        One snapshot per trading day.
    """
    snapshots: list[DailySnapshot] = []
    last_rebalance_date: date | None = None
    min_gap = timedelta(days=config.rebalance.min_days_between_rebalances)

    # Initialise portfolio on the first available day
    first_prices = {
        ticker: float(prices.loc[prices.index[0], ticker])
        for ticker in config.tickers()
    }
    portfolio = Portfolio.from_cash(config, initial_cash, first_prices)

    for ts in prices.index:
        today = ts.date()
        day_prices = {
            ticker: float(prices.loc[ts, ticker]) for ticker in config.tickers()
        }
        portfolio.update_prices(day_prices)

        # Determine whether to rebalance today
        rebalanced = False
        trades: list[Trade] = []
        cooldown_ok = (
            last_rebalance_date is None or (today - last_rebalance_date) >= min_gap
        )

        if cooldown_ok:
            scheduled = (
                config.rebalance.schedule == "2nd_wednesday"
                and is_second_wednesday(today)
            )
            drift_breach = portfolio.has_drift_breach()

            if scheduled or drift_breach:
                trades = compute_trades(portfolio)
                if trades:
                    apply_trades(portfolio, trades)
                    last_rebalance_date = today
                    rebalanced = True

        snapshots.append(
            DailySnapshot(
                date=today,
                total_value=portfolio.total_value,
                weights=portfolio.current_weights(),
                rebalanced=rebalanced,
                trades=trades,
            )
        )

    return snapshots
