"""Simulation and comparison CLI commands."""

from __future__ import annotations

from pathlib import Path

import click

from rebalancer.cli_defaults import DEFAULT_COMPARE_OUTPUT
from rebalancer.cli_options import (
    with_config_option,
    with_end_date_option,
    with_output_option,
    with_start_date_option,
)
from rebalancer.config import load_config
from rebalancer.market_data import fetch_prices
from rebalancer.services.simulator import (
    run_historical_simulation,
    run_ticker_comparison,
)


@click.command()
@with_config_option()
@with_start_date_option(help_text="Simulation start date (YYYY-MM-DD).")
@with_end_date_option(help_text="Simulation end date (YYYY-MM-DD).")
@click.option(
    "--cash", required=True, type=float, help="Starting portfolio value in USD."
)
@click.option(
    "--benchmark",
    "benchmarks",
    multiple=True,
    default=("^GSPC", "^IXIC"),
    show_default=True,
    help="Benchmark ticker to include in report (pass multiple times).",
)
@click.option(
    "--no-benchmarks",
    is_flag=True,
    help="Disable benchmark overlays in simulation outputs.",
)
@with_output_option(
    default=Path("output"),
    help_text="Directory to write CSV and HTML report.",
)
def simulate(
    config: Path,
    start,
    end,
    cash: float,
    benchmarks: tuple[str, ...],
    no_benchmarks: bool,
    output: Path,
) -> None:
    """Run a backtest simulation over a historical date range."""
    cfg = load_config(config)
    click.echo(f"Fetching price data for {cfg.tickers()} ...")

    selected_benchmarks: tuple[str, ...] = ()
    if not no_benchmarks:
        selected_benchmarks = tuple(
            dict.fromkeys(ticker.upper() for ticker in benchmarks)
        )
        if selected_benchmarks:
            click.echo(f"Including benchmarks: {list(selected_benchmarks)}")

    click.echo(
        f"Running simulation from {start.date()} to {end.date()} with ${cash:,.2f} ..."
    )
    result = run_historical_simulation(
        config_path=config,
        start_date=start.date(),
        end_date=end.date(),
        cash=cash,
        output_dir=output,
        price_fetcher=lambda tickers, start_date, end_date: fetch_prices(
            tickers,
            start=start_date,
            end=end_date,
        ),
        benchmark_tickers=selected_benchmarks,
        benchmark_price_fetcher=lambda tickers, start_date, end_date: fetch_prices(
            tickers,
            start=start_date,
            end=end_date,
        ),
    )

    click.echo(
        f"Done. Rebalances: {result.rebalance_count}. Final value: ${result.final_value:,.2f}"
    )

    click.echo(f"Results written to {output}/")
    if result.benchmark_tickers:
        click.echo(f"Benchmark CSV: {output}/benchmark_values.csv")
    click.echo(f"HTML report: {output}/report.html")


@click.command()
@click.option(
    "--category",
    required=True,
    type=str,
    help="Category label for this comparison set (for display and output naming).",
)
@click.option(
    "--ticker",
    "tickers",
    multiple=True,
    required=True,
    help="Ticker to include in comparison. Pass this option multiple times.",
)
@with_start_date_option(help_text="Comparison start date (YYYY-MM-DD).")
@with_end_date_option(help_text="Comparison end date (YYYY-MM-DD).")
@with_output_option(
    default=DEFAULT_COMPARE_OUTPUT,
    help_text="Directory to write comparison output files.",
)
def compare_tickers(
    category: str,
    tickers: tuple[str, ...],
    start,
    end,
    output: Path,
) -> None:
    """Compare a set of tickers over a date range."""
    start_date = start.date()
    end_date = end.date()
    unique_tickers = list(dict.fromkeys(t.upper() for t in tickers))
    click.echo(
        f"Comparing {len(unique_tickers)} tickers in '{category}' from {start_date} to {end_date} ..."
    )

    try:
        result = run_ticker_comparison(
            category=category,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            output_root=output,
            price_fetcher=lambda symbols, start_day, end_day: fetch_prices(
                symbols,
                start=start_day,
                end=end_day,
            ),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Comparison complete. Output files:")
    click.echo(f"  Summary CSV: {result.output.summary_csv}")
    click.echo(f"  Prices CSV: {result.output.prices_csv}")
    click.echo(f"  Normalized CSV: {result.output.normalized_csv}")
    click.echo(f"  HTML report: {result.output.html_report}")
