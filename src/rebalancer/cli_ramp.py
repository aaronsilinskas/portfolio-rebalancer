"""Ramp planning and staged backtest CLI commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from rebalancer.cli_defaults import DEFAULT_RAMP_BACKTEST_OUTPUT, DEFAULT_RAMP_OUTPUT
from rebalancer.cli_options import (
    with_config_option,
    with_output_option,
    with_positions_option,
)
from rebalancer.data import fetch_latest_prices, fetch_prices
from rebalancer.services.ramp import (
    create_ramp_backtest,
    create_ramp_plan,
)


@click.command()
@with_config_option()
@with_positions_option()
@click.option(
    "--contribution",
    type=float,
    required=True,
    help="Contribution amount in USD to allocate.",
)
@click.option(
    "--stage",
    type=click.Choice(["stage1", "stage2", "final"], case_sensitive=False),
    help="Ramp stage to apply directly.",
)
@click.option(
    "--funded-ratio",
    type=float,
    help="Current funded ratio in [0,1] used to infer stage (<=0.30 stage1, <=0.70 stage2, else final).",
)
@with_output_option(
    default=DEFAULT_RAMP_OUTPUT,
    help_text="Directory to write ramp plan output files.",
)
def ramp_plan(
    config: Path,
    positions: Path,
    contribution: float,
    stage: str | None,
    funded_ratio: float | None,
    output: Path,
) -> None:
    """Build a buy-only contribution plan for ramping into target allocations."""
    try:
        result = create_ramp_plan(
            config_path=config,
            positions_path=positions,
            contribution=contribution,
            stage=stage,
            funded_ratio=funded_ratio,
            output_root=output,
            as_of=date.today(),
            latest_price_fetcher=fetch_latest_prices,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        f"Ramp plan ({result.stage}) for ${result.contribution:,.2f} written to {result.plan_path}"
    )
    click.echo("Suggested buys:")
    buys = result.plan[result.plan["buy_value"] > 0]
    for _, row in buys.iterrows():
        click.echo(
            f"  {row['ticker']}: ${row['buy_value']:,.2f} ({row['buy_shares']:.6f} shares)"
        )


@click.command()
@with_config_option()
@with_positions_option()
@click.option(
    "--step",
    "steps",
    multiple=True,
    required=True,
    help="Funding step in format YYYY-MM:stage:amount (e.g., 2026-01:stage1:10000).",
)
@click.option(
    "--valuation-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=date.today().isoformat(),
    show_default=True,
    help="Date to value the portfolio (YYYY-MM-DD).",
)
@with_output_option(
    default=DEFAULT_RAMP_BACKTEST_OUTPUT,
    help_text="Directory to write ramp backtest output files.",
)
def ramp_backtest(
    config: Path,
    positions: Path,
    steps: tuple[str, ...],
    valuation_date,
    output: Path,
) -> None:
    """Backtest staged monthly contributions using ramp stages."""
    try:
        result = create_ramp_backtest(
            config_path=config,
            positions_path=positions,
            steps=steps,
            valuation_date=valuation_date.date(),
            output_root=output,
            historical_price_fetcher=lambda tickers, start, end: fetch_prices(
                tickers,
                start=start,
                end=end,
            ),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Ramp backtest written to {result.output_dir}/")
    click.echo(f"Total contributed: ${result.total_contributed:,.2f}")
    click.echo(f"Final value: ${result.final_value:,.2f}")
    click.echo(f"Total return: {result.total_return_pct:.4f}%")
