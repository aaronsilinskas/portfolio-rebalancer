"""Daily rebalancing CLI commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from rebalancer.cli_defaults import DEFAULT_DAILY_OUTPUT
from rebalancer.cli_options import (
    with_config_option,
    with_output_option,
    with_positions_option,
)
from rebalancer.config import load_config
from rebalancer.data import fetch_latest_prices
from rebalancer.services.rebalance import run_daily_check, sync_positions_file
from rebalancer.simulator import is_second_wednesday


@click.command()
@with_config_option()
@with_positions_option()
@with_output_option(
    default=DEFAULT_DAILY_OUTPUT,
    help_text="Directory to write dated daily-check output files.",
)
def daily_check(config: Path, positions: Path, output: Path) -> None:
    """
    Run the daily drift and schedule check.

    Prints a trade list if rebalancing is needed today, or a confirmation
    that no action is required. Does NOT execute trades automatically.
    """
    today = date.today()
    cfg = load_config(config)

    click.echo(f"Daily check — {today}")
    click.echo(f"Fetching latest prices for {cfg.tickers()} ...")

    result = run_daily_check(
        config_path=config,
        positions_path=positions,
        output_dir=output,
        as_of=today,
        latest_price_fetcher=fetch_latest_prices,
        schedule_checker=is_second_wednesday,
    )

    if result.status == "skipped_no_positions":
        click.echo(
            "Positions file has zero market value. Daily check skipped until holdings are set."
        )
        click.echo(f"Daily output written to {result.output_path}/")
        return

    if result.status == "no_action":
        if "no rebalance trigger detected" in result.reasons:
            click.echo("No rebalancing needed today.")
        else:
            click.echo(
                "Rebalance trigger detected, but the portfolio is already at target weights."
            )
        click.echo(f"Daily output written to {result.output_path}/")
        return

    click.echo(f"Rebalance triggered: {', '.join(result.reasons)}")
    click.echo("\nRequired trades:")
    for trade in result.trades:
        click.echo(
            f"  {trade.action:4s} {trade.shares:.4f} shares of {trade.ticker} @ ${trade.price:.2f}  (${trade.value:,.2f})"
        )
    click.echo(f"Daily output written to {result.output_path}/")


@click.command()
@with_config_option()
@with_positions_option(exists=False)
@click.option(
    "--default-shares",
    type=float,
    default=0.0,
    show_default=True,
    help="Default share count for tickers that are in config but missing in positions.",
)
def sync_positions(config: Path, positions: Path, default_shares: float) -> None:
    """
    Sync the positions YAML file with the tickers in portfolio config.

    Existing shares are preserved for matching tickers, missing tickers are added,
    and extra tickers not in the portfolio config are removed.
    """
    try:
        result = sync_positions_file(
            config_path=config,
            positions_path=positions,
            default_shares=default_shares,
        )
    except ValueError as exc:
        raise click.ClickException(f"Invalid positions file: {exc}") from exc

    click.echo(f"Synced positions written to {result.positions_path}")
    if result.added:
        click.echo(f"Added missing tickers: {', '.join(result.added)}")
    if result.dropped:
        click.echo(f"Dropped tickers not in config: {', '.join(result.dropped)}")
