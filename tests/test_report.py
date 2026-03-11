from datetime import date

from rebalancer.report import TRADE_COLUMNS, build_trades_df
from rebalancer.simulator import DailySnapshot


def test_build_trades_df_has_stable_columns_when_empty():
    snapshots = [
        DailySnapshot(
            date=date(2024, 1, 10),
            total_value=10_000.0,
            weights={"SPY": 0.6, "BND": 0.4},
            rebalanced=False,
            trades=[],
        )
    ]

    trades_df = build_trades_df(snapshots)

    assert trades_df.empty
    assert list(trades_df.columns) == TRADE_COLUMNS
