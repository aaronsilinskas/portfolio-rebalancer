"""
cli.py — Click-based CLI entry points for the rebalancer.

Commands
--------
rebalancer-simulate   Run a backtest over a historical date range.
rebalancer-daily      Run the daily drift/schedule check and print any required trades.
rebalancer-sync-positions  Align positions file with configured tickers.
rebalancer-compare    Compare ticker performance over a date range.
rebalancer-ramp-plan  Build a buy-only ramp contribution plan.
rebalancer-ramp-backtest  Replay staged monthly ramp contributions.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from rebalancer.compare import write_comparison_outputs
from rebalancer.config import dump_positions, load_config, load_positions
from rebalancer.data import fetch_latest_prices, fetch_prices
from rebalancer.portfolio import Portfolio
from rebalancer.ramp import (
    build_ramp_plan,
    infer_ramp_stage,
    parse_ramp_steps,
    run_ramp_progression,
    validate_contribution_amount,
)
from rebalancer.rebalancer import compute_trades, project_shares_after_trades
from rebalancer.report import write_csv, write_daily_check_files, write_html_report
from rebalancer.simulator import is_second_wednesday, run_simulation


DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "portfolio.yaml"
DEFAULT_POSITIONS = Path(__file__).parent.parent.parent / "config" / "positions.yaml"
DEFAULT_DAILY_OUTPUT = Path("output") / "daily"
DEFAULT_COMPARE_OUTPUT = Path("output") / "comparisons"
DEFAULT_RAMP_OUTPUT = Path("output") / "ramp-plans"
DEFAULT_RAMP_BACKTEST_OUTPUT = Path("output") / "ramp-backtests"


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
            reasons=[
                "positions file contains zero market value; update shares when holdings are established"
            ],
            status="skipped_no_positions",
            output_dir=output,
            current_positions=current_positions,
        )
        click.echo(
            "Positions file has zero market value. Daily check skipped until holdings are set."
        )
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
        click.echo(
            "Rebalance trigger detected, but the portfolio is already at target weights."
        )
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
    type=click.Path(path_type=Path),
    default=DEFAULT_POSITIONS,
    show_default=True,
    help="Path to positions YAML file to create/update.",
)
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
    cfg = load_config(config)

    existing_positions: dict[str, float] = {}
    if positions.exists():
        try:
            existing_positions = load_positions(positions)
        except ValueError as exc:
            raise click.ClickException(f"Invalid positions file: {exc}") from exc

    target_tickers = cfg.tickers()
    synced_positions = {
        ticker: float(existing_positions.get(ticker, default_shares))
        for ticker in target_tickers
    }

    dropped = sorted(set(existing_positions) - set(target_tickers))
    added = [ticker for ticker in target_tickers if ticker not in existing_positions]

    dump_positions(positions, synced_positions)

    click.echo(f"Synced positions written to {positions}")
    if added:
        click.echo(f"Added missing tickers: {', '.join(added)}")
    if dropped:
        click.echo(f"Dropped tickers not in config: {', '.join(dropped)}")


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
@click.option(
    "--start",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Comparison start date (YYYY-MM-DD).",
)
@click.option(
    "--end",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Comparison end date (YYYY-MM-DD).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DEFAULT_COMPARE_OUTPUT,
    show_default=True,
    help="Directory to write comparison output files.",
)
def compare_tickers(
    category: str,
    tickers: tuple[str, ...],
    start,
    end,
    output: Path,
) -> None:
    """Compare a set of tickers over a date range."""
    unique_tickers = list(dict.fromkeys(t.upper() for t in tickers))
    if len(unique_tickers) < 2:
        raise click.ClickException("At least two unique tickers are required.")

    start_date = start.date()
    end_date = end.date()
    click.echo(
        f"Comparing {len(unique_tickers)} tickers in '{category}' from {start_date} to {end_date} ..."
    )

    prices = fetch_prices(unique_tickers, start=start_date, end=end_date)
    result = write_comparison_outputs(
        category=category,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        prices=prices,
        output_root=output,
    )

    click.echo("Comparison complete. Output files:")
    click.echo(f"  Summary CSV: {result.summary_csv}")
    click.echo(f"  Prices CSV: {result.prices_csv}")
    click.echo(f"  Normalized CSV: {result.normalized_csv}")
    click.echo(f"  HTML report: {result.html_report}")


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
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DEFAULT_RAMP_OUTPUT,
    show_default=True,
    help="Directory to write ramp plan output files.",
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
        contribution = validate_contribution_amount(
            contribution,
            field_name="Contribution",
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if stage and funded_ratio is not None:
        raise click.ClickException("Use either --stage or --funded-ratio, not both.")

    selected_stage: str
    if funded_ratio is not None:
        try:
            selected_stage = infer_ramp_stage(funded_ratio)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    elif stage is not None:
        selected_stage = stage.lower()
    else:
        selected_stage = "stage1"

    cfg = load_config(config)
    shares_by_ticker = load_positions(positions, allowed_tickers=set(cfg.tickers()))
    prices = fetch_latest_prices(cfg.tickers())

    plan = build_ramp_plan(
        config=cfg,
        shares_by_ticker=shares_by_ticker,
        prices=prices,
        contribution=contribution,
        stage=selected_stage,
    )

    output_dir = output / f"{date.today().isoformat()}-{selected_stage}"
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "ramp_plan.csv"
    plan.to_csv(plan_path, index=False)

    click.echo(
        f"Ramp plan ({selected_stage}) for ${contribution:,.2f} written to {plan_path}"
    )
    click.echo("Suggested buys:")
    buys = plan[plan["buy_value"] > 0]
    for _, row in buys.iterrows():
        click.echo(
            f"  {row['ticker']}: ${row['buy_value']:,.2f} ({row['buy_shares']:.6f} shares)"
        )


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
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=DEFAULT_RAMP_BACKTEST_OUTPUT,
    show_default=True,
    help="Directory to write ramp backtest output files.",
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
        parsed_steps = parse_ramp_steps(list(steps))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    cfg = load_config(config)
    shares_by_ticker = load_positions(positions, allowed_tickers=set(cfg.tickers()))

    first_step = parsed_steps[0]
    start_date = date(first_step.year, first_step.month, 1)
    end_date = valuation_date.date()
    if end_date < start_date:
        raise click.ClickException(
            "--valuation-date must be on or after the first step month"
        )

    prices = fetch_prices(cfg.tickers(), start=start_date, end=end_date)

    result = run_ramp_progression(
        config=cfg,
        steps=parsed_steps,
        prices=prices,
        initial_shares=shares_by_ticker,
    )

    if result.total_contributed <= 0:
        raise click.ClickException(
            "Total contributed value is zero; unable to compute return"
        )

    total_return_pct = ((result.final_value / result.total_contributed) - 1.0) * 100.0

    output_dir = output / f"{result.valuation_date.isoformat()}-ramp-backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    progression_path = output_dir / "progression.csv"
    final_positions_path = output_dir / "positions_after.yaml"
    summary_path = output_dir / "summary.txt"

    result.progression.to_csv(progression_path, index=False)
    dump_positions(final_positions_path, result.final_shares)
    summary_path.write_text(
        "\n".join(
            [
                "Ramp Backtest Summary",
                f"Valuation date: {result.valuation_date.isoformat()}",
                f"Total contributed: ${result.total_contributed:,.2f}",
                f"Final value: ${result.final_value:,.2f}",
                f"Total return: {total_return_pct:.4f}%",
            ]
        )
        + "\n"
    )

    click.echo(f"Ramp backtest written to {output_dir}/")
    click.echo(f"Total contributed: ${result.total_contributed:,.2f}")
    click.echo(f"Final value: ${result.final_value:,.2f}")
    click.echo(f"Total return: {total_return_pct:.4f}%")


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
