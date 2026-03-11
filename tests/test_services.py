from datetime import date
from pathlib import Path

import pandas as pd

from rebalancer.config import load_positions
from rebalancer.services.ramp import create_ramp_backtest, create_ramp_plan
from rebalancer.services.rebalance import run_daily_check, sync_positions_file
from rebalancer.services.simulator import (
    run_historical_simulation,
    run_ticker_comparison,
)


def _write_config(path: Path) -> None:
    path.write_text(
        """
portfolio:
  name: Test
  holdings:
    - ticker: SPY
      label: US Large-Cap Equities
      target_weight: 0.6
    - ticker: BND
      label: Bonds/Fixed Income
      target_weight: 0.4
rebalance:
  schedule: 2nd_wednesday
  min_days_between_rebalances: 7
  drift:
    mode: absolute
    threshold: 0.075
""".strip()
    )


def _write_positions(path: Path, spy_shares: float, bnd_shares: float) -> None:
    path.write_text(
        f"""
positions:
  - ticker: SPY
    shares: {spy_shares}
  - ticker: BND
    shares: {bnd_shares}
""".strip()
    )


def _prices_for_months() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SPY": [100.0, 102.0, 103.0],
            "BND": [100.0, 101.0, 102.0],
        },
        index=pd.to_datetime(["2026-01-02", "2026-02-03", "2026-03-10"]),
    )


def test_sync_positions_file_returns_metadata_and_writes(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"

    _write_config(config_path)
    positions_path.write_text(
        """
positions:
  - ticker: SPY
    shares: 10
  - ticker: TLT
    shares: 5
""".strip()
    )

    result = sync_positions_file(
        config_path=config_path,
        positions_path=positions_path,
        default_shares=0.0,
    )

    assert result.added == ["BND"]
    assert result.dropped == ["TLT"]
    assert load_positions(positions_path) == {"SPY": 10.0, "BND": 0.0}


def test_run_daily_check_returns_no_action_when_no_trigger(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "daily"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=60.0, bnd_shares=40.0)

    result = run_daily_check(
        config_path=config_path,
        positions_path=positions_path,
        output_dir=output_dir,
        as_of=date(2024, 1, 10),
        latest_price_fetcher=lambda tickers: {"SPY": 100.0, "BND": 100.0},
        schedule_checker=lambda _: False,
    )

    assert result.status == "no_action"
    assert result.reasons == ["no rebalance trigger detected"]
    assert result.trades == []
    assert (result.output_path / "summary.txt").exists()


def test_run_daily_check_returns_action_required_on_drift(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "daily"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=75.0, bnd_shares=25.0)

    result = run_daily_check(
        config_path=config_path,
        positions_path=positions_path,
        output_dir=output_dir,
        as_of=date(2024, 1, 10),
        latest_price_fetcher=lambda tickers: {"SPY": 100.0, "BND": 100.0},
        schedule_checker=lambda _: False,
    )

    assert result.status == "action_required"
    assert result.trades
    assert any(reason.startswith("drift breach") for reason in result.reasons)
    assert (result.output_path / "positions_after.yaml").exists()


def test_create_ramp_plan_writes_plan_and_returns_stage(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_root = tmp_path / "ramp-plans"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    result = create_ramp_plan(
        config_path=config_path,
        positions_path=positions_path,
        contribution=1000.0,
        stage=None,
        funded_ratio=0.2,
        output_root=output_root,
        as_of=date(2024, 1, 10),
        latest_price_fetcher=lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )

    assert result.stage == "stage1"
    assert result.contribution == 1000.0
    assert result.plan_path.exists()


def test_create_ramp_backtest_writes_outputs_and_summary(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_root = tmp_path / "ramp-backtests"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    result = create_ramp_backtest(
        config_path=config_path,
        positions_path=positions_path,
        steps=("2026-01:stage1:10000", "2026-02:stage2:10000"),
        valuation_date=date(2026, 3, 10),
        output_root=output_root,
        historical_price_fetcher=lambda tickers, start, end: _prices_for_months(),
    )

    assert result.progression_path.exists()
    assert result.final_positions_path.exists()
    assert result.summary_path.exists()
    assert result.total_contributed == 20000.0
    assert result.final_value > 0.0


def test_create_ramp_backtest_rejects_valuation_before_first_step(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    try:
        create_ramp_backtest(
            config_path=config_path,
            positions_path=positions_path,
            steps=("2026-02:stage1:10000",),
            valuation_date=date(2026, 1, 31),
            output_root=tmp_path / "ramp-backtests",
            historical_price_fetcher=lambda tickers, start, end: _prices_for_months(),
        )
        raise AssertionError("Expected ValueError for valuation date ordering")
    except ValueError as exc:
        assert "--valuation-date" in str(exc)


def test_run_historical_simulation_returns_summary_and_writes_files(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    output_dir = tmp_path / "sim-output"

    _write_config(config_path)

    prices = pd.DataFrame(
        {
            "SPY": [100.0, 101.0],
            "BND": [100.0, 100.5],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    result = run_historical_simulation(
        config_path=config_path,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
        cash=10_000.0,
        output_dir=output_dir,
        price_fetcher=lambda tickers, start, end: prices,
    )

    assert result.rebalance_count >= 0
    assert result.final_value > 0
    assert (output_dir / "snapshots.csv").exists()
    assert (output_dir / "trades.csv").exists()
    assert (output_dir / "report.html").exists()


def test_run_ticker_comparison_returns_output_and_writes_files(tmp_path: Path):
    output_root = tmp_path / "comparisons"

    prices = pd.DataFrame(
        {
            "SPY": [100.0, 102.0, 101.0],
            "VOO": [100.0, 101.0, 103.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    result = run_ticker_comparison(
        category="US Large Cap",
        tickers=("SPY", "VOO"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
        output_root=output_root,
        price_fetcher=lambda tickers, start, end: prices,
    )

    assert result.tickers == ["SPY", "VOO"]
    assert result.output.summary_csv.exists()
    assert result.output.prices_csv.exists()
    assert result.output.normalized_csv.exists()
    assert result.output.html_report.exists()
