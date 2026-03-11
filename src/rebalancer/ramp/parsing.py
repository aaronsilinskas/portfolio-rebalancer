"""Ramp input parsing and validation helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rebalancer.ramp.models import RampStep


def validate_contribution_amount(
    amount: float | str,
    *,
    field_name: str = "contribution",
) -> float:
    """Validate a positive contribution amount with cent precision."""
    try:
        value = Decimal(str(amount))
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be numeric") from exc

    if value <= 0:
        raise ValueError(f"{field_name} must be positive")

    if value != value.quantize(Decimal("0.01")):
        raise ValueError(f"{field_name} must not include sub-cent precision")

    return float(value)


def infer_ramp_stage(funded_ratio: float) -> str:
    """Infer stage from funded ratio in [0, 1]."""
    if funded_ratio < 0.0 or funded_ratio > 1.0:
        raise ValueError("funded_ratio must be between 0.0 and 1.0")
    if funded_ratio <= 0.30:
        return "stage1"
    if funded_ratio <= 0.70:
        return "stage2"
    return "final"


def parse_ramp_steps(step_specs: list[str] | tuple[str, ...]) -> list[RampStep]:
    """Parse user-provided step specs in the form YYYY-MM:stage:amount."""
    if not step_specs:
        raise ValueError("At least one step is required")

    parsed: list[RampStep] = []

    for spec in step_specs:
        parts = [p.strip() for p in spec.split(":")]
        if len(parts) != 3:
            raise ValueError(
                f"Invalid step '{spec}'. Expected format YYYY-MM:stage:amount"
            )

        month_part, stage_part, amount_part = parts
        stage = stage_part.lower()
        if stage not in {"stage1", "stage2", "final"}:
            raise ValueError(
                f"Invalid stage in '{spec}'. Stage must be one of stage1, stage2, final"
            )

        try:
            year_s, month_s = month_part.split("-")
            year = int(year_s)
            month = int(month_s)
        except ValueError as exc:
            raise ValueError(f"Invalid month in '{spec}'. Expected YYYY-MM") from exc

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month in '{spec}'. Month must be in 01..12")

        try:
            contribution = validate_contribution_amount(
                amount_part,
                field_name=f"Contribution in '{spec}'",
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        parsed.append(
            RampStep(
                year=year,
                month=month,
                stage=stage,
                contribution=contribution,
            )
        )

    parsed = sorted(parsed, key=lambda s: (s.year, s.month))

    seen_months: set[tuple[int, int]] = set()
    for step in parsed:
        key = (step.year, step.month)
        if key in seen_months:
            raise ValueError(f"Duplicate month in step list: {step.month_key}")
        seen_months.add(key)

    return parsed
