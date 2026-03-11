"""Service workflows for ramp planning and staged backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from rebalancer.config import dump_positions, load_config, load_positions
from rebalancer.ramp import (
    build_ramp_plan,
    infer_ramp_stage,
    parse_ramp_steps,
    run_ramp_progression,
    validate_contribution_amount,
)


@dataclass
class RampPlanResult:
    stage: str
    contribution: float
    output_dir: Path
    plan_path: Path
    plan: pd.DataFrame


@dataclass
class RampBacktestResult:
    output_dir: Path
    progression_path: Path
    final_positions_path: Path
    summary_path: Path
    total_contributed: float
    final_value: float
    total_return_pct: float


def resolve_ramp_stage(*, stage: str | None, funded_ratio: float | None) -> str:
    """Resolve the selected stage from explicit value or funded ratio."""
    if stage and funded_ratio is not None:
        raise ValueError("Use either --stage or --funded-ratio, not both.")

    if funded_ratio is not None:
        return infer_ramp_stage(funded_ratio)
    if stage is not None:
        return stage.lower()
    return "stage1"


def create_ramp_plan(
    *,
    config_path: Path,
    positions_path: Path,
    contribution: float,
    stage: str | None,
    funded_ratio: float | None,
    output_root: Path,
    as_of: date,
    latest_price_fetcher: Callable[[list[str]], dict[str, float]],
) -> RampPlanResult:
    """Create and persist a buy-only ramp plan."""
    validated_contribution = validate_contribution_amount(
        contribution,
        field_name="Contribution",
    )
    selected_stage = resolve_ramp_stage(stage=stage, funded_ratio=funded_ratio)

    cfg = load_config(config_path)
    shares_by_ticker = load_positions(
        positions_path, allowed_tickers=set(cfg.tickers())
    )
    prices = latest_price_fetcher(cfg.tickers())

    plan = build_ramp_plan(
        config=cfg,
        shares_by_ticker=shares_by_ticker,
        prices=prices,
        contribution=validated_contribution,
        stage=selected_stage,
    )

    output_dir = output_root / f"{as_of.isoformat()}-{selected_stage}"
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "ramp_plan.csv"
    plan.to_csv(plan_path, index=False)

    return RampPlanResult(
        stage=selected_stage,
        contribution=validated_contribution,
        output_dir=output_dir,
        plan_path=plan_path,
        plan=plan,
    )


def create_ramp_backtest(
    *,
    config_path: Path,
    positions_path: Path,
    steps: tuple[str, ...],
    valuation_date: date,
    output_root: Path,
    historical_price_fetcher: Callable[[list[str], date, date], pd.DataFrame],
) -> RampBacktestResult:
    """Run and persist staged ramp backtest outputs."""
    parsed_steps = parse_ramp_steps(list(steps))

    cfg = load_config(config_path)
    shares_by_ticker = load_positions(
        positions_path, allowed_tickers=set(cfg.tickers())
    )

    first_step = parsed_steps[0]
    start_date = date(first_step.year, first_step.month, 1)
    if valuation_date < start_date:
        raise ValueError("--valuation-date must be on or after the first step month")

    prices = historical_price_fetcher(cfg.tickers(), start_date, valuation_date)
    progression_result = run_ramp_progression(
        config=cfg,
        steps=parsed_steps,
        prices=prices,
        initial_shares=shares_by_ticker,
    )

    if progression_result.total_contributed <= 0:
        raise ValueError("Total contributed value is zero; unable to compute return")

    total_return_pct = (
        (progression_result.final_value / progression_result.total_contributed) - 1.0
    ) * 100.0

    output_dir = (
        output_root / f"{progression_result.valuation_date.isoformat()}-ramp-backtest"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    progression_path = output_dir / "progression.csv"
    final_positions_path = output_dir / "positions_after.yaml"
    summary_path = output_dir / "summary.txt"

    progression_result.progression.to_csv(progression_path, index=False)
    dump_positions(final_positions_path, progression_result.final_shares)
    summary_path.write_text(
        "\n".join(
            [
                "Ramp Backtest Summary",
                f"Valuation date: {progression_result.valuation_date.isoformat()}",
                f"Total contributed: ${progression_result.total_contributed:,.2f}",
                f"Final value: ${progression_result.final_value:,.2f}",
                f"Total return: {total_return_pct:.4f}%",
            ]
        )
        + "\n"
    )

    return RampBacktestResult(
        output_dir=output_dir,
        progression_path=progression_path,
        final_positions_path=final_positions_path,
        summary_path=summary_path,
        total_contributed=progression_result.total_contributed,
        final_value=progression_result.final_value,
        total_return_pct=total_return_pct,
    )
