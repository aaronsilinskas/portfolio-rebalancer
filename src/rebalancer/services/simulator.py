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
) -> SimulationRunResult:
    """Run historical simulation and persist report outputs."""
    cfg = load_config(config_path)
    prices = price_fetcher(cfg.tickers(), start_date, end_date)

    snapshots = run_simulation(cfg, prices, initial_cash=cash)
    rebalance_count = sum(1 for snapshot in snapshots if snapshot.rebalanced)
    final_value = snapshots[-1].total_value

    write_csv(snapshots, output_dir)
    write_html_report(snapshots, output_dir)

    return SimulationRunResult(
        output_dir=output_dir,
        rebalance_count=rebalance_count,
        final_value=final_value,
        snapshots=snapshots,
    )


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
