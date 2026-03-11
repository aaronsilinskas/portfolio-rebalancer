from datetime import date
from pathlib import Path

import pandas as pd

from rebalancer.compare import (
    SUMMARY_COLUMNS,
    build_normalized_prices,
    build_performance_summary,
    write_comparison_outputs,
)


def test_build_normalized_prices_starts_each_series_at_100():
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 110.0, 121.0],
            "VOO": [50.0, 55.0, 60.5],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    normalized = build_normalized_prices(prices)

    assert normalized.loc[pd.Timestamp("2024-01-01"), "SPY"] == 100.0
    assert normalized.loc[pd.Timestamp("2024-01-01"), "VOO"] == 100.0


def test_build_performance_summary_sorts_by_total_return():
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 110.0, 120.0],
            "VOO": [100.0, 105.0, 108.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    summary = build_performance_summary(prices)

    assert list(summary.columns) == SUMMARY_COLUMNS
    assert list(summary["ticker"]) == ["SPY", "VOO"]
    assert summary.iloc[0]["total_return_pct"] > summary.iloc[1]["total_return_pct"]


def test_write_comparison_outputs_creates_files(tmp_path: Path):
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 102.0, 101.0],
            "VOO": [100.0, 101.0, 103.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    result = write_comparison_outputs(
        category="US Large Cap",
        start=date(2024, 1, 1).isoformat(),
        end=date(2024, 1, 3).isoformat(),
        prices=prices,
        output_root=tmp_path,
    )

    assert result.prices_csv.exists()
    assert result.normalized_csv.exists()
    assert result.summary_csv.exists()
    assert result.html_report.exists()
