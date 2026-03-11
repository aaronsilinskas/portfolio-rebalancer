"""Service workflows for simulation and comparison commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from rebalancer.compare import ComparisonOutput, write_comparison_outputs
from rebalancer.config import load_config
from rebalancer.report import write_csv, write_html_report
from rebalancer.simulator import DailySnapshot, run_simulation


@dataclass(frozen=True)
class SimulationRunResult:
    output_dir: Path
    rebalance_count: int
    final_value: float
    snapshots: list[DailySnapshot]
    benchmark_tickers: tuple[str, ...]


@dataclass(frozen=True)
class TickerComparisonResult:
    tickers: list[str]
    output: ComparisonOutput


def run_historical_simulation(
    *,
    config_path: Path,
    start_date: date,
    end_date: date,
    cash: float,
    output_dir: Path,
    price_fetcher: Callable[[list[str], date, date], pd.DataFrame],
    benchmark_tickers: tuple[str, ...] = (),
    benchmark_price_fetcher: (
        Callable[[list[str], date, date], pd.DataFrame] | None
    ) = None,
) -> SimulationRunResult:
    """Run historical simulation and persist report outputs."""
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")

    cfg = load_config(config_path)
    prices = price_fetcher(cfg.tickers(), start_date, end_date)

    snapshots = run_simulation(cfg, prices, initial_cash=cash)
    rebalance_count = sum(1 for snapshot in snapshots if snapshot.rebalanced)
    final_value = snapshots[-1].total_value

    benchmark_values: pd.DataFrame | None = None
    if benchmark_tickers and benchmark_price_fetcher is not None:
        benchmark_prices = benchmark_price_fetcher(
            list(dict.fromkeys(benchmark_tickers)),
            start_date,
            end_date,
        )
        benchmark_values = _build_benchmark_values(
            benchmark_prices=benchmark_prices,
            snapshot_dates=pd.to_datetime([snapshot.date for snapshot in snapshots]),
            initial_cash=cash,
        )

    write_csv(snapshots, output_dir, benchmark_values=benchmark_values)
    write_html_report(snapshots, output_dir, benchmark_values=benchmark_values)

    return SimulationRunResult(
        output_dir=output_dir,
        rebalance_count=rebalance_count,
        final_value=final_value,
        snapshots=snapshots,
        benchmark_tickers=(
            tuple(benchmark_values.columns) if benchmark_values is not None else ()
        ),
    )


def _build_benchmark_values(
    *,
    benchmark_prices: pd.DataFrame,
    snapshot_dates: pd.DatetimeIndex,
    initial_cash: float,
) -> pd.DataFrame:
    """Convert benchmark prices into value-series comparable to portfolio value."""
    if benchmark_prices.empty:
        return pd.DataFrame(index=snapshot_dates)

    # Forward-fill only: avoids fabricating pre-inception history for benchmarks.
    aligned = benchmark_prices.sort_index().reindex(snapshot_dates).ffill()
    if aligned.empty:
        return pd.DataFrame(index=snapshot_dates)

    first_row = aligned.iloc[0]
    valid_columns = [
        column
        for column in aligned.columns
        if pd.notna(first_row[column]) and first_row[column] > 0
    ]
    if not valid_columns:
        return pd.DataFrame(index=snapshot_dates)

    normalized = aligned[valid_columns].div(first_row[valid_columns], axis=1)
    return normalized * initial_cash


def run_ticker_comparison(
    *,
    category: str,
    tickers: tuple[str, ...],
    start_date: date,
    end_date: date,
    output_root: Path,
    price_fetcher: Callable[[list[str], date, date], pd.DataFrame],
) -> TickerComparisonResult:
    """Run ticker comparison and persist output artifacts."""
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")

    unique_tickers = list(dict.fromkeys(t.upper() for t in tickers))
    if len(unique_tickers) < 2:
        raise ValueError("At least two unique tickers are required.")

    prices = price_fetcher(unique_tickers, start_date, end_date)
    output = write_comparison_outputs(
        category=category,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        prices=prices,
        output_root=output_root,
    )

    return TickerComparisonResult(
        tickers=unique_tickers,
        output=output,
    )
