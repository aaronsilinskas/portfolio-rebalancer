"""
cli.py — Click-based CLI entry points for the rebalancer.

Commands
--------
rebalancer-simulate   Run a backtest over a historical date range.
rebalancer-daily      Run the daily drift/schedule check and print any required trades.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from rebalancer.config import load_config
from rebalancer.data import fetch_latest_prices, fetch_prices
from rebalancer.portfolio import Portfolio
from rebalancer.rebalancer import compute_trades
from rebalancer.report import write_csv, write_html_report
from rebalancer.simulator import is_second_wednesday, run_simulation


DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "portfolio.yaml"


@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to portfolio YAML config.",
)
@click.option(
    "--start",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Simulation start date (YYYY-MM-DD).",
)
@click.option(
    "--end",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Simulation end date (YYYY-MM-DD).",
)
@click.option(
    "--cash", required=True, type=float, help="Starting portfolio value in USD."
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("output"),
    show_default=True,
    help="Directory to write CSV and HTML report.",
)
def simulate(config: Path, start, end, cash: float, output: Path) -> None:
    """Run a backtest simulation over a historical date range."""
    cfg = load_config(config)
    click.echo(f"Fetching price data for {cfg.tickers()} ...")
    prices = fetch_prices(cfg.tickers(), start=start.date(), end=end.date())

    click.echo(
        f"Running simulation from {start.date()} to {end.date()} with ${cash:,.2f} ..."
    )
    snapshots = run_simulation(cfg, prices, initial_cash=cash)

    rebalance_count = sum(1 for s in snapshots if s.rebalanced)
    final_value = snapshots[-1].total_value
    click.echo(f"Done. Rebalances: {rebalance_count}. Final value: ${final_value:,.2f}")

    write_csv(snapshots, output)
    write_html_report(snapshots, output)
    click.echo(f"Results written to {output}/")
    click.echo(f"HTML report: {output}/report.html")


@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to portfolio YAML config.",
)
def daily_check(config: Path) -> None:
    """
    Run the daily drift and schedule check.

    Prints a trade list if rebalancing is needed today, or a confirmation
    that no action is required. Does NOT execute trades automatically.
    """
    cfg = load_config(config)
    today = date.today()

    click.echo(f"Daily check — {today}")
    click.echo(f"Fetching latest prices for {cfg.tickers()} ...")
    prices = fetch_latest_prices(cfg.tickers())

    # NOTE: share counts are unknown without a live positions file.
    # For now, this command checks drift based on a hypothetically equal-weighted
    # portfolio at current prices (a placeholder until positions tracking is added).
    portfolio = Portfolio.from_cash(cfg, total_cash=1_000_000.0, prices=prices)

    scheduled = is_second_wednesday(today)
    drift_breach = portfolio.has_drift_breach()

    if not scheduled and not drift_breach:
        click.echo("No rebalancing needed today.")
        return

    reason = []
    if scheduled:
        reason.append("scheduled (2nd Wednesday)")
    if drift_breach:
        drifts = portfolio.drifts()
        breaches = {
            t: d for t, d in drifts.items() if abs(d) > cfg.rebalance.drift.threshold
        }
        reason.append(f"drift breach: {breaches}")

    click.echo(f"Rebalance triggered: {', '.join(reason)}")
    trades = compute_trades(portfolio)
    click.echo("\nRequired trades:")
    for trade in trades:
        click.echo(
            f"  {trade.action:4s} {trade.shares:.4f} shares of {trade.ticker} @ ${trade.price:.2f}  (${trade.value:,.2f})"
        )
