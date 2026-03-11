from datetime import date

import pandas as pd

from rebalancer.simulator import is_second_wednesday, run_simulation
from tests.helpers import make_config


def test_is_second_wednesday_detects_expected_dates():
    assert is_second_wednesday(date(2024, 1, 10))
    assert not is_second_wednesday(date(2024, 1, 17))
    assert not is_second_wednesday(date(2024, 1, 9))


def test_run_simulation_respects_cooldown_between_rebalances():
    config = make_config(threshold=0.075)
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 100.0, 150.0, 150.0, 250.0, 250.0, 250.0],
            "BND": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
        },
        index=pd.to_datetime(
            [
                "2024-01-08",
                "2024-01-09",
                "2024-01-10",
                "2024-01-11",
                "2024-01-12",
                "2024-01-16",
                "2024-01-17",
            ]
        ),
    )

    snapshots = run_simulation(config, prices, initial_cash=10_000.0)
    rebalanced_dates = [snapshot.date for snapshot in snapshots if snapshot.rebalanced]

    assert rebalanced_dates == [date(2024, 1, 10), date(2024, 1, 17)]

    jan_12_snapshot = next(
        snapshot for snapshot in snapshots if snapshot.date == date(2024, 1, 12)
    )
    assert not jan_12_snapshot.rebalanced
