"""Simulation CSV and HTML report writers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from rebalancer.report.frames import build_snapshots_df, build_trades_df
from rebalancer.simulator import DailySnapshot


def write_csv(
    snapshots: list[DailySnapshot],
    output_dir: Path,
    benchmark_values: pd.DataFrame | None = None,
) -> None:
    """Write portfolio snapshots and trade log to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    build_snapshots_df(snapshots).to_csv(output_dir / "snapshots.csv")
    build_trades_df(snapshots).to_csv(output_dir / "trades.csv", index=False)
    if benchmark_values is not None and not benchmark_values.empty:
        benchmark_values.to_csv(output_dir / "benchmark_values.csv")


def write_html_report(
    snapshots: list[DailySnapshot],
    output_dir: Path,
    benchmark_values: pd.DataFrame | None = None,
) -> None:
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
    if benchmark_values is not None and not benchmark_values.empty:
        for ticker in benchmark_values.columns:
            fig.add_trace(
                go.Scatter(
                    x=benchmark_values.index,
                    y=benchmark_values[ticker],
                    name=f"Benchmark {ticker}",
                    line={"dash": "dash"},
                ),
                row=1,
                col=1,
            )
    if len(rebalance_dates) > 0:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                name="Rebalance Event",
                line={"color": "orange", "dash": "dot"},
            ),
            row=1,
            col=1,
        )

    for rebalance_date in rebalance_dates:
        fig.add_shape(
            type="line",
            x0=rebalance_date,
            x1=rebalance_date,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={"color": "orange", "width": 1, "dash": "dot"},
            layer="above",
        )

    weight_cols = [col for col in snap_df.columns if col.startswith("weight_")]
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
        title="Portfolio Rebalancer Backtest Report",
        height=800,
        legend={"orientation": "h", "y": -0.15},
    )
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="Weight", tickformat=".0%", row=2, col=1)

    html_path = output_dir / "report.html"
    fig.write_html(str(html_path), include_plotlyjs="cdn")
