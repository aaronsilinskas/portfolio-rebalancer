"""compare.py — Compare ticker performance over a date range."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


SUMMARY_COLUMNS = [
    "ticker",
    "start_date",
    "end_date",
    "start_price",
    "end_price",
    "total_return_pct",
    "annualized_return_pct",
    "volatility_pct",
    "max_drawdown_pct",
]


@dataclass
class ComparisonOutput:
    directory: Path
    prices_csv: Path
    normalized_csv: Path
    summary_csv: Path
    html_report: Path


def _slugify(value: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in value)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "comparison"


def build_normalized_prices(prices: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Normalize each ticker series to `base` at its first valid observation."""
    normalized = pd.DataFrame(index=prices.index)
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if series.empty:
            continue
        normalized.loc[series.index, ticker] = (series / series.iloc[0]) * base
    return normalized


def build_performance_summary(prices: pd.DataFrame) -> pd.DataFrame:
    """Build per-ticker return and risk summary statistics."""
    rows: list[dict[str, object]] = []
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 2:
            continue

        start_price = float(series.iloc[0])
        end_price = float(series.iloc[-1])
        total_return = (end_price / start_price) - 1.0

        start_date = series.index[0].date()
        end_date = series.index[-1].date()
        num_days = (end_date - start_date).days

        annualized_return = None
        if num_days > 0:
            years = num_days / 365.25
            annualized_return = ((1 + total_return) ** (1 / years)) - 1

        daily_returns = series.pct_change().dropna()
        volatility = None
        if not daily_returns.empty:
            volatility = daily_returns.std() * (252**0.5)

        drawdowns = (series / series.cummax()) - 1.0
        max_drawdown = float(drawdowns.min())

        rows.append(
            {
                "ticker": ticker,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "start_price": round(start_price, 4),
                "end_price": round(end_price, 4),
                "total_return_pct": round(total_return * 100.0, 4),
                "annualized_return_pct": (
                    None
                    if annualized_return is None
                    else round(float(annualized_return) * 100.0, 4)
                ),
                "volatility_pct": (
                    None if volatility is None else round(float(volatility) * 100.0, 4)
                ),
                "max_drawdown_pct": round(max_drawdown * 100.0, 4),
            }
        )

    summary = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    if not summary.empty:
        summary = summary.sort_values(
            by="total_return_pct", ascending=False
        ).reset_index(drop=True)
    return summary


def write_comparison_outputs(
    *,
    category: str,
    start: str,
    end: str,
    prices: pd.DataFrame,
    output_root: Path,
) -> ComparisonOutput:
    """Write CSV and HTML outputs for a ticker comparison run."""
    directory = output_root / f"{_slugify(category)}-{start}-to-{end}"
    directory.mkdir(parents=True, exist_ok=True)

    normalized = build_normalized_prices(prices)
    summary = build_performance_summary(prices)

    prices_csv = directory / "prices.csv"
    normalized_csv = directory / "normalized_prices.csv"
    summary_csv = directory / "summary.csv"
    html_report = directory / "comparison.html"

    prices.to_csv(prices_csv)
    normalized.to_csv(normalized_csv)
    summary.to_csv(summary_csv, index=False)

    fig = go.Figure()
    for ticker in normalized.columns:
        fig.add_trace(
            go.Scatter(
                x=normalized.index,
                y=normalized[ticker],
                mode="lines",
                name=ticker,
            )
        )

    fig.update_layout(
        title=f"Ticker Comparison: {category}",
        xaxis_title="Date",
        yaxis_title="Normalized Price (Base 100)",
        legend={"orientation": "h", "y": -0.2},
        height=650,
    )
    fig.write_html(str(html_report), include_plotlyjs="cdn")

    return ComparisonOutput(
        directory=directory,
        prices_csv=prices_csv,
        normalized_csv=normalized_csv,
        summary_csv=summary_csv,
        html_report=html_report,
    )
