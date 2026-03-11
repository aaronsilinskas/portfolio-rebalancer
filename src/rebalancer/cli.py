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

from rebalancer.config import load_config, load_positions
from rebalancer.data import fetch_latest_prices, fetch_prices
from rebalancer.portfolio import Portfolio
from rebalancer.rebalancer import compute_trades, project_shares_after_trades
from rebalancer.report import write_csv, write_daily_check_files, write_html_report
from rebalancer.simulator import is_second_wednesday, run_simulation


DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "portfolio.yaml"
DEFAULT_POSITIONS = Path(__file__).parent.parent.parent / "config" / "positions.yaml"
DEFAULT_DAILY_OUTPUT = Path("output") / "daily"


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
@click.option(
    "--positions",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_POSITIONS,
    show_default=True,
    help="Path to current positions YAML file.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DEFAULT_DAILY_OUTPUT,
    show_default=True,
    help="Directory to write dated daily-check output files.",
)
def daily_check(config: Path, positions: Path, output: Path) -> None:
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

    shares_by_ticker = load_positions(positions, allowed_tickers=set(cfg.tickers()))
    portfolio = Portfolio.from_shares(cfg, shares_by_ticker, prices)
    current_positions = portfolio.share_counts()
    if portfolio.total_value <= 0:
        output_path = write_daily_check_files(
            as_of=today,
            portfolio=portfolio,
            drifts=None,
            trades=[],
            reasons=["positions file contains zero market value; update shares when holdings are established"],
            status="skipped_no_positions",
            output_dir=output,
            current_positions=current_positions,
        )
        click.echo("Positions file has zero market value. Daily check skipped until holdings are set.")
        click.echo(f"Daily output written to {output_path}/")
        return

    scheduled = is_second_wednesday(today)
    drifts = portfolio.drifts()
    threshold = cfg.rebalance.drift.threshold
    breaches = {t: d for t, d in drifts.items() if abs(d) > threshold}
    drift_breach = bool(breaches)

    if not scheduled and not drift_breach:
        output_path = write_daily_check_files(
            as_of=today,
            portfolio=portfolio,
            drifts=drifts,
            trades=[],
            reasons=["no rebalance trigger detected"],
            status="no_action",
            output_dir=output,
            current_positions=current_positions,
        )
        click.echo("No rebalancing needed today.")
        click.echo(f"Daily output written to {output_path}/")
        return

    reason = []
    if scheduled:
        reason.append("scheduled (2nd Wednesday)")
    if drift_breach:
        reason.append(f"drift breach: {breaches}")

    trades = compute_trades(portfolio)
    if not trades:
        output_path = write_daily_check_files(
            as_of=today,
            portfolio=portfolio,
            drifts=drifts,
            trades=[],
            reasons=reason + ["portfolio is already at target weights"],
            status="no_action",
            output_dir=output,
            current_positions=current_positions,
        )
        click.echo("Rebalance trigger detected, but the portfolio is already at target weights.")
        click.echo(f"Daily output written to {output_path}/")
        return

    projected_positions = project_shares_after_trades(current_positions, trades)
    output_path = write_daily_check_files(
        as_of=today,
        portfolio=portfolio,
        drifts=drifts,
        trades=trades,
        reasons=reason,
        status="action_required",
        output_dir=output,
        current_positions=current_positions,
        projected_positions=projected_positions,
    )

    click.echo(f"Rebalance triggered: {', '.join(reason)}")
    click.echo("\nRequired trades:")
    for trade in trades:
        click.echo(
            f"  {trade.action:4s} {trade.shares:.4f} shares of {trade.ticker} @ ${trade.price:.2f}  (${trade.value:,.2f})"
        )
    click.echo(f"Daily output written to {output_path}/")
