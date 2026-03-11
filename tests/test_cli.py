from datetime import date
from pathlib import Path

from click.testing import CliRunner

from rebalancer.cli import daily_check
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


def test_daily_check_skips_cleanly_when_positions_are_empty(
    tmp_path: Path, monkeypatch
):
    config_path = tmp_path / "portfolio.yaml"
    positions_path = tmp_path / "positions.yaml"
    output_dir = tmp_path / "output"

    _write_config(config_path)
    _write_positions(positions_path, spy_shares=0.0, bnd_shares=0.0)

    monkeypatch.setattr(
        "rebalancer.cli.fetch_latest_prices",
        lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )
    monkeypatch.setattr("rebalancer.cli.is_second_wednesday", lambda _: False)
    monkeypatch.setattr("rebalancer.cli.date", FixedDate)

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
        "rebalancer.cli.fetch_latest_prices",
        lambda tickers: {"SPY": 100.0, "BND": 100.0},
    )
    monkeypatch.setattr("rebalancer.cli.is_second_wednesday", lambda _: False)
    monkeypatch.setattr("rebalancer.cli.date", FixedDate)

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
