"""DataFrame builders used by reporting outputs."""

from __future__ import annotations

from datetime import date

import pandas as pd

from rebalancer.portfolio import Portfolio
from rebalancer.rebalancer import Trade
from rebalancer.simulator import DailySnapshot


TRADE_COLUMNS = ["date", "ticker", "action", "shares", "price", "value"]
HOLDING_COLUMNS = [
    "ticker",
    "shares",
    "price",
    "market_value",
    "current_weight",
    "target_weight",
    "drift",
]


def build_snapshots_df(snapshots: list[DailySnapshot]) -> pd.DataFrame:
    """Convert simulation snapshots into a flat DataFrame."""
    rows = []
    for snapshot in snapshots:
        row = {
            "date": snapshot.date,
            "total_value": snapshot.total_value,
            "rebalanced": snapshot.rebalanced,
        }
        row.update(
            {f"weight_{ticker}": weight for ticker, weight in snapshot.weights.items()}
        )
        rows.append(row)
    return pd.DataFrame(rows).set_index("date")


def build_trades_df(snapshots: list[DailySnapshot]) -> pd.DataFrame:
    """Extract all trades from snapshots into a flat DataFrame."""
    rows = []
    for snapshot in snapshots:
        for trade in snapshot.trades:
            rows.append(
                {
                    "date": snapshot.date,
                    "ticker": trade.ticker,
                    "action": trade.action,
                    "shares": round(trade.shares, 6),
                    "price": round(trade.price, 4),
                    "value": round(trade.value, 2),
                }
            )
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


def build_trade_list_df(trades: list[Trade], as_of: date) -> pd.DataFrame:
    """Convert a list of proposed trades into a flat DataFrame."""
    rows = [
        {
            "date": as_of,
            "ticker": trade.ticker,
            "action": trade.action,
            "shares": round(trade.shares, 6),
            "price": round(trade.price, 4),
            "value": round(trade.value, 2),
        }
        for trade in trades
    ]
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


def build_holdings_df(
    portfolio: Portfolio,
    *,
    drifts: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Convert the current portfolio into a flat holdings DataFrame."""
    current_weights = portfolio.current_weights()
    target_weights = portfolio.config.target_weights()

    rows = []
    for ticker, holding in portfolio.holdings.items():
        rows.append(
            {
                "ticker": ticker,
                "shares": round(holding.shares, 6),
                "price": round(holding.price, 4),
                "market_value": round(holding.market_value, 2),
                "current_weight": round(current_weights.get(ticker, 0.0), 6),
                "target_weight": round(target_weights[ticker], 6),
                "drift": None if drifts is None else round(drifts.get(ticker, 0.0), 6),
            }
        )

    return pd.DataFrame(rows, columns=HOLDING_COLUMNS)
