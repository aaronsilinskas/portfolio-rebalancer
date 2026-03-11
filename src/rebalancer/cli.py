"""Top-level CLI wiring for grouped and legacy commands."""

from __future__ import annotations

import click

from rebalancer.cli_ramp import ramp_backtest, ramp_plan
from rebalancer.cli_rebalance import daily_check, sync_positions
from rebalancer.cli_simulator import compare_tickers, simulate


@click.group()
def main() -> None:
    """Portfolio rebalancer command suite."""


@click.group(name="rebalance")
def rebalance_group() -> None:
    """Live/manual rebalancing workflows."""


@click.group(name="ramp")
def ramp_group() -> None:
    """Ramp-up planning and staged backtests."""


@click.group(name="simulator")
def simulator_group() -> None:
    """Historical simulation and comparison tools."""


rebalance_group.add_command(daily_check, name="daily")
rebalance_group.add_command(sync_positions, name="sync-positions")

ramp_group.add_command(ramp_plan, name="plan")
ramp_group.add_command(ramp_backtest, name="backtest")

simulator_group.add_command(simulate, name="run")
simulator_group.add_command(compare_tickers, name="compare")

main.add_command(rebalance_group)
main.add_command(ramp_group)
main.add_command(simulator_group)


__all__ = [
    "compare_tickers",
    "daily_check",
    "main",
    "ramp_backtest",
    "ramp_plan",
    "simulate",
    "sync_positions",
]
