from datetime import date
from pathlib import Path

from rebalancer.report import (
    HOLDING_COLUMNS,
    TRADE_COLUMNS,
    build_holdings_df,
    build_trades_df,
    write_daily_check_files,
    write_html_report,
)
from rebalancer.simulator import DailySnapshot
from tests.helpers import make_portfolio


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


def test_build_holdings_df_has_stable_columns():
    portfolio = make_portfolio(spy_price=100.0, bnd_price=100.0)

    holdings_df = build_holdings_df(portfolio, drifts=portfolio.drifts())

    assert list(holdings_df.columns) == HOLDING_COLUMNS


def test_write_daily_check_files_creates_expected_outputs(tmp_path: Path):
    portfolio = make_portfolio(
        spy_price=100.0, bnd_price=100.0, spy_shares=75.0, bnd_shares=25.0
    )
    drifts = portfolio.drifts()
    day_dir = write_daily_check_files(
        as_of=date(2024, 1, 10),
        portfolio=portfolio,
        drifts=drifts,
        trades=[],
        reasons=["no rebalance trigger detected"],
        status="no_action",
        output_dir=tmp_path,
        current_positions=portfolio.share_counts(),
    )

    assert (day_dir / "summary.txt").exists()
    assert (day_dir / "holdings.csv").exists()
    assert (day_dir / "trades.csv").exists()
    assert (day_dir / "positions_current.yaml").exists()


def test_write_html_report_includes_rebalance_event_marker(tmp_path: Path):
    snapshots = [
        DailySnapshot(
            date=date(2024, 1, 9),
            total_value=10_000.0,
            weights={"SPY": 0.6, "BND": 0.4},
            rebalanced=False,
            trades=[],
        ),
        DailySnapshot(
            date=date(2024, 1, 10),
            total_value=10_100.0,
            weights={"SPY": 0.59, "BND": 0.41},
            rebalanced=True,
            trades=[],
        ),
    ]

    write_html_report(snapshots, tmp_path)

    html = (tmp_path / "report.html").read_text()
    assert "Rebalance Event" in html
