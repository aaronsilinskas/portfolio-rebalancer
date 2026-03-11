"""
report.py — Generate CSV and HTML (with Plotly charts) output from simulation results.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from rebalancer.simulator import DailySnapshot


TRADE_COLUMNS = ["date", "ticker", "action", "shares", "price", "value"]


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
