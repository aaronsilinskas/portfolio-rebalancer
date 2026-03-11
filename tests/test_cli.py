from datetime import date
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from rebalancer.cli import main
from rebalancer.cli_ramp import ramp_backtest, ramp_plan
from rebalancer.cli_rebalance import daily_check, sync_positions
from rebalancer.cli_simulator import compare_tickers
from rebalancer.config import load_positions


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2024, 1, 10)


def _write_config(path: Path) -> None:
    path.write_text(
        """
portfolio:
  name: Test
  holdings:
    - ticker: SPY
      label: US Large-Cap
      target_weight: 0.6
    - ticker: BND
      label: Bonds
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


def _write_three_ticker_config(path: Path) -> None:
    path.write_text(
        """
portfolio:
  name: Test
  holdings:
    - ticker: SPY
      label: US Large-Cap
      target_weight: 0.4
    - ticker: BND
      label: Bonds
      target_weight: 0.4
    - ticker: GLD
      label: Gold
      target_weight: 0.2
rebalance:
  schedule: 2nd_wednesday
  min_days_between_rebalances: 7
  drift:
    mode: absolute
    threshold: 0.075
""".strip()
    )


def test_daily_check_skips_cleanly_when_positions_are_empty(
    tmp_path: Path, monkeypatch
):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "output"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    monkeypatch.setattr(
        "rebalancer.cli_rebalance.fetch_latest_prices",
        lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )
    monkeypatch.setattr("rebalancer.cli_rebalance.is_second_wednesday", lambda _: False)
    monkeypatch.setattr("rebalancer.cli_rebalance.date", FixedDate)

    result = CliRunner().invoke(
        daily_check,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Daily check skipped until holdings are set" in result.output
    assert (output_dir / "2024-01-10" / "summary.txt").exists()


def test_daily_check_writes_projected_positions_when_action_is_required(
    tmp_path: Path, monkeypatch
):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "output"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=75.0, bnd_shares=25.0)

    monkeypatch.setattr(
        "rebalancer.cli_rebalance.fetch_latest_prices",
        lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )
    monkeypatch.setattr("rebalancer.cli_rebalance.is_second_wednesday", lambda _: False)
    monkeypatch.setattr("rebalancer.cli_rebalance.date", FixedDate)

    result = CliRunner().invoke(
        daily_check,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--output",
            str(output_dir),
        ],
    )

    projected_positions = load_positions(
        output_dir / "2024-01-10" / "positions_after.yaml"
    )

    assert result.exit_code == 0
    assert "Required trades:" in result.output
    assert projected_positions == {"SPY": 60.0, "BND": 40.0}


def test_sync_positions_preserves_known_adds_missing_and_drops_unknown(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"

    _write_three_ticker_config(config_path)
    positions_path.write_text(
        """
positions:
  - ticker: SPY
    shares: 10
  - ticker: TLT
    shares: 5
""".strip()
    )

    result = CliRunner().invoke(
        sync_positions,
        ["--config", str(config_path), "--positions", str(positions_path)],
    )

    synced = load_positions(positions_path)

    assert result.exit_code == 0
    assert synced == {"SPY": 10.0, "BND": 0.0, "GLD": 0.0}
    assert "Dropped tickers not in config: TLT" in result.output


def test_sync_positions_can_bootstrap_new_file_with_default_shares(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"

    _write_config(config_path)

    result = CliRunner().invoke(
        sync_positions,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--default-shares",
            "1.25",
        ],
    )

    synced = load_positions(positions_path)

    assert result.exit_code == 0
    assert synced == {"SPY": 1.25, "BND": 1.25}


def test_compare_tickers_requires_two_unique_tickers():
    result = CliRunner().invoke(
        compare_tickers,
        [
            "--category",
            "US Large Cap",
            "--ticker",
            "SPY",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
        ],
    )

    assert result.exit_code != 0
    assert "At least two unique tickers are required" in result.output


def test_compare_tickers_writes_outputs(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "compare-output"

    prices = pd.DataFrame(
        {
            "SPY": [100.0, 102.0, 101.0],
            "VOO": [100.0, 101.0, 103.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    monkeypatch.setattr(
        "rebalancer.cli_simulator.fetch_prices", lambda tickers, start, end: prices
    )

    result = CliRunner().invoke(
        compare_tickers,
        [
            "--category",
            "US Large Cap",
            "--ticker",
            "SPY",
            "--ticker",
            "VOO",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-03",
            "--output",
            str(output_dir),
        ],
    )

    expected_dir = output_dir / "us-large-cap-2024-01-01-to-2024-01-03"
    assert result.exit_code == 0
    assert "Comparison complete. Output files:" in result.output
    assert (expected_dir / "summary.csv").exists()
    assert (expected_dir / "prices.csv").exists()
    assert (expected_dir / "normalized_prices.csv").exists()
    assert (expected_dir / "comparison.html").exists()


def test_ramp_plan_writes_output_for_selected_stage(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "ramp-output"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=50.0, bnd_shares=50.0)

    monkeypatch.setattr(
        "rebalancer.cli_ramp.fetch_latest_prices",
        lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )
    monkeypatch.setattr("rebalancer.cli_ramp.date", FixedDate)

    result = CliRunner().invoke(
        ramp_plan,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--contribution",
            "1000",
            "--stage",
            "final",
            "--output",
            str(output_dir),
        ],
    )

    expected_csv = output_dir / "2024-01-10-final" / "ramp_plan.csv"

    assert result.exit_code == 0
    assert expected_csv.exists()
    assert "Ramp plan (final)" in result.output


def test_ramp_plan_inferrs_stage_from_funded_ratio(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "ramp-output"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=50.0, bnd_shares=50.0)

    monkeypatch.setattr(
        "rebalancer.cli_ramp.fetch_latest_prices",
        lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )
    monkeypatch.setattr("rebalancer.cli_ramp.date", FixedDate)

    result = CliRunner().invoke(
        ramp_plan,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--contribution",
            "1000",
            "--funded-ratio",
            "0.2",
            "--output",
            str(output_dir),
        ],
    )

    expected_csv = output_dir / "2024-01-10-stage1" / "ramp_plan.csv"

    assert result.exit_code == 0
    assert expected_csv.exists()
    assert "Ramp plan (stage1)" in result.output


def test_ramp_plan_rejects_sub_cent_contribution(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    result = CliRunner().invoke(
        ramp_plan,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--contribution",
            "1000.001",
            "--stage",
            "stage1",
        ],
    )

    assert result.exit_code != 0
    assert "sub-cent" in result.output


def test_ramp_backtest_writes_progression_positions_and_summary(
    tmp_path: Path, monkeypatch
):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "ramp-backtests"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    prices = pd.DataFrame(
        {
            "SPY": [100.0, 102.0, 103.0],
            "BND": [100.0, 101.0, 102.0],
        },
        index=pd.to_datetime(["2026-01-02", "2026-02-03", "2026-03-10"]),
    )
    monkeypatch.setattr(
        "rebalancer.cli_ramp.fetch_prices", lambda *args, **kwargs: prices
    )

    result = CliRunner().invoke(
        ramp_backtest,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--step",
            "2026-01:stage1:10000",
            "--step",
            "2026-02:stage2:10000",
            "--valuation-date",
            "2026-03-10",
            "--output",
            str(output_dir),
        ],
    )

    expected_dir = output_dir / "2026-03-10-ramp-backtest"
    assert result.exit_code == 0
    assert (expected_dir / "progression.csv").exists()
    assert (expected_dir / "positions_after.yaml").exists()
    assert (expected_dir / "summary.txt").exists()
    assert "Total contributed: $20,000.00" in result.output


def test_ramp_backtest_rejects_valuation_date_before_first_step_month(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    result = CliRunner().invoke(
        ramp_backtest,
        [
            "--config",
            str(config_path),
            "--positions",
            str(positions_path),
            "--step",
            "2026-02:stage1:10000",
            "--valuation-date",
            "2026-01-31",
        ],
    )

    assert result.exit_code != 0
    assert "--valuation-date must be on or after the first step month" in result.output


def test_main_group_exposes_expected_subcommand_categories():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "rebalance" in result.output
    assert "ramp" in result.output
    assert "simulator" in result.output
