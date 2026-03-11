"""
report.py — Generate CSV and HTML (with Plotly charts) output from simulation results.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from rebalancer.config import dump_positions
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
    for s in snapshots:
        row = {"date": s.date, "total_value": s.total_value, "rebalanced": s.rebalanced}
        row.update({f"weight_{ticker}": w for ticker, w in s.weights.items()})
        rows.append(row)
    return pd.DataFrame(rows).set_index("date")


def build_trades_df(snapshots: list[DailySnapshot]) -> pd.DataFrame:
    """Extract all trades from snapshots into a flat DataFrame."""
    rows = []
    for s in snapshots:
        for t in s.trades:
            rows.append(
                {
                    "date": s.date,
                    "ticker": t.ticker,
                    "action": t.action,
                    "shares": round(t.shares, 6),
                    "price": round(t.price, 4),
                    "value": round(t.value, 2),
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


def write_daily_check_files(
    *,
    as_of: date,
    portfolio: Portfolio,
    drifts: dict[str, float] | None,
    trades: list[Trade],
    reasons: list[str],
    status: str,
    output_dir: Path,
    current_positions: dict[str, float],
    projected_positions: dict[str, float] | None = None,
) -> Path:
    """Write dated daily-check outputs for manual review and position updates."""
    day_dir = output_dir / as_of.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = [
        "Daily Rebalance Check",
        f"Date: {as_of.isoformat()}",
        f"Status: {status}",
        f"Total market value: ${portfolio.total_value:,.2f}",
        f"Trade count: {len(trades)}",
        "Reasons:",
    ]
    summary_lines.extend(f"- {reason}" for reason in reasons or ["none"])
    if projected_positions is not None:
        summary_lines.append("Projected post-trade positions: positions_after.yaml")

    (day_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n")
    build_holdings_df(portfolio, drifts=drifts).to_csv(day_dir / "holdings.csv", index=False)
    build_trade_list_df(trades, as_of).to_csv(day_dir / "trades.csv", index=False)
    dump_positions(day_dir / "positions_current.yaml", current_positions)
    if projected_positions is not None:
        dump_positions(day_dir / "positions_after.yaml", projected_positions)

    return day_dir


def write_csv(snapshots: list[DailySnapshot], output_dir: Path) -> None:
    """Write portfolio snapshots and trade log to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    build_snapshots_df(snapshots).to_csv(output_dir / "snapshots.csv")
    build_trades_df(snapshots).to_csv(output_dir / "trades.csv", index=False)


def write_html_report(snapshots: list[DailySnapshot], output_dir: Path) -> None:
    """Write a self-contained HTML report with interactive Plotly charts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    snap_df = build_snapshots_df(snapshots)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Portfolio Value Over Time", "Holding Weights Over Time"),
        vertical_spacing=0.12,
    )

    # --- Portfolio value ---
    rebalance_dates = snap_df[snap_df["rebalanced"]].index
    fig.add_trace(
        go.Scatter(
            x=snap_df.index,
            y=snap_df["total_value"],
            name="Portfolio Value",
            line={"color": "steelblue"},
        ),
        row=1,
        col=1,
    )
    for rd in rebalance_dates:
        fig.add_vline(
            x=str(rd),
            line_width=1,
            line_dash="dot",
            line_color="orange",
            row=1,  # type: ignore[call-arg]
            col=1,  # type: ignore[call-arg]
        )

    # --- Weights ---
    weight_cols = [c for c in snap_df.columns if c.startswith("weight_")]
    for col in weight_cols:
        ticker = col.removeprefix("weight_")
        fig.add_trace(
            go.Scatter(
                x=snap_df.index,
                y=snap_df[col],
                name=ticker,
                stackgroup="weights",
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title="Rebalancer Backtest Report",
        height=800,
        legend={"orientation": "h", "y": -0.15},
    )
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="Weight", tickformat=".0%", row=2, col=1)

    html_path = output_dir / "report.html"
    fig.write_html(str(html_path), include_plotlyjs="cdn")
