from pathlib import Path

import pytest

from rebalancer.config import load_config, load_positions


def test_load_config_rejects_invalid_drift_mode(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    config_path.write_text(
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
    mode: invalid
    threshold: 0.075
""".strip()
    )

    with pytest.raises(ValueError, match="Unsupported drift mode"):
        load_config(config_path)


def test_load_config_rejects_invalid_schedule(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    config_path.write_text(
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
  schedule: monthly
  min_days_between_rebalances: 7
  drift:
    mode: absolute
    threshold: 0.075
""".strip()
    )

    with pytest.raises(ValueError, match="Unsupported rebalance schedule"):
        load_config(config_path)


def test_load_positions_rejects_unknown_ticker(tmp_path: Path):
    positions_path = tmp_path / "positions.yaml"
    positions_path.write_text(
        """
positions:
  - ticker: SPY
    shares: 10
  - ticker: TLT
    shares: 5
""".strip()
    )

    with pytest.raises(ValueError, match="Ticker TLT is not defined"):
        load_positions(positions_path, allowed_tickers={"SPY", "BND"})
