import pandas as pd

from tests.helpers import make_config

from rebalancer.ramp import (
    build_ramp_plan,
    infer_ramp_stage,
    parse_ramp_steps,
    run_ramp_progression,
)


def test_infer_ramp_stage_thresholds():
    assert infer_ramp_stage(0.0) == "stage1"
    assert infer_ramp_stage(0.30) == "stage1"
    assert infer_ramp_stage(0.31) == "stage2"
    assert infer_ramp_stage(0.70) == "stage2"
    assert infer_ramp_stage(0.71) == "final"


def test_build_ramp_plan_final_stage_allocates_to_deficit_only():
    config = make_config()
    shares = {"SPY": 50.0, "BND": 50.0}
    prices = {"SPY": 100.0, "BND": 100.0}

    plan = build_ramp_plan(
        config=config,
        shares_by_ticker=shares,
        prices=prices,
        contribution=1_000.0,
        stage="final",
    )

    by_ticker = {row["ticker"]: row for _, row in plan.iterrows()}
    assert by_ticker["SPY"]["buy_value"] == 1_000.0
    assert by_ticker["BND"]["buy_value"] == 0.0


def test_build_ramp_plan_stage1_overweights_large_cap():
    config = make_config()
    shares = {"SPY": 50.0, "BND": 50.0}
    prices = {"SPY": 100.0, "BND": 100.0}

    plan = build_ramp_plan(
        config=config,
        shares_by_ticker=shares,
        prices=prices,
        contribution=1_000.0,
        stage="stage1",
    )

    by_ticker = {row["ticker"]: row for _, row in plan.iterrows()}
    assert by_ticker["SPY"]["buy_value"] > by_ticker["BND"]["buy_value"]
    assert round(plan["buy_value"].sum(), 2) == 1_000.0


def test_parse_ramp_steps_sorts_and_parses_valid_specs():
    steps = parse_ramp_steps(["2026-03:final:10000", "2026-01:stage1:5000"])

    assert [s.month_key for s in steps] == ["2026-01", "2026-03"]
    assert steps[0].stage == "stage1"
    assert steps[0].contribution == 5000.0


def test_parse_ramp_steps_rejects_duplicate_months():
    try:
        parse_ramp_steps(["2026-01:stage1:5000", "2026-01:stage2:5000"])
        raise AssertionError("Expected ValueError for duplicate month")
    except ValueError as exc:
        assert "Duplicate month" in str(exc)


def test_run_ramp_progression_returns_expected_summary_shape():
    config = make_config()
    steps = parse_ramp_steps(["2026-01:stage1:1000", "2026-02:stage2:1000"])

    prices = pd.DataFrame(
        {
            "SPY": [100.0, 102.0, 103.0],
            "BND": [100.0, 101.0, 102.0],
        },
        index=pd.to_datetime(["2026-01-02", "2026-02-02", "2026-03-02"]),
    )

    progression, shares, contributed, final_value, valuation_day = run_ramp_progression(
        config=config,
        steps=steps,
        prices=prices,
        initial_shares={"SPY": 0.0, "BND": 0.0},
    )

    assert list(progression["month"]) == ["2026-01", "2026-02"]
    assert contributed == 2000.0
    assert final_value > 0.0
    assert valuation_day.isoformat() == "2026-03-02"
    assert set(shares) == {"SPY", "BND"}
