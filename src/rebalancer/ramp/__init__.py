"""Ramp planning and staged progression API."""

from rebalancer.ramp.models import (
    RAMP_COLUMNS,
    STEP_COLUMNS,
    RampProgressionResult,
    RampStep,
)
from rebalancer.ramp.parsing import (
    infer_ramp_stage,
    parse_ramp_steps,
    validate_contribution_amount,
)
from rebalancer.ramp.planning import build_ramp_plan
from rebalancer.ramp.progression import run_ramp_progression
from rebalancer.ramp.weights import CATEGORY_RAMP_WEIGHTS, get_ramp_target_weights


__all__ = [
    "CATEGORY_RAMP_WEIGHTS",
    "RAMP_COLUMNS",
    "STEP_COLUMNS",
    "RampProgressionResult",
    "RampStep",
    "build_ramp_plan",
    "get_ramp_target_weights",
    "infer_ramp_stage",
    "parse_ramp_steps",
    "run_ramp_progression",
    "validate_contribution_amount",
]
