"""Daily-check output writers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from rebalancer.config import dump_positions
from rebalancer.portfolio import Portfolio
from rebalancer.rebalancer import Trade
from rebalancer.report.frames import build_holdings_df, build_trade_list_df


def write_daily_check_files(
    *,
    as_of: date,
    portfolio: Portfolio,
    drifts: dict[str, float] | None,
    trades: list[Trade],
    reasons: list[str],
    status: str,
    output_dir: Path,
    current_positions: dict[str, float],
    projected_positions: dict[str, float] | None = None,
) -> Path:
    """Write dated daily-check outputs for manual review and position updates."""
    day_dir = output_dir / as_of.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = [
        "Daily Rebalance Check",
        f"Date: {as_of.isoformat()}",
        f"Status: {status}",
        f"Total market value: ${portfolio.total_value:,.2f}",
        f"Trade count: {len(trades)}",
        "Reasons:",
    ]
    summary_lines.extend(f"- {reason}" for reason in reasons or ["none"])
    if projected_positions is not None:
        summary_lines.append("Projected post-trade positions: positions_after.yaml")

    (day_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n")
    build_holdings_df(portfolio, drifts=drifts).to_csv(
        day_dir / "holdings.csv", index=False
    )
    build_trade_list_df(trades, as_of).to_csv(day_dir / "trades.csv", index=False)
    dump_positions(day_dir / "positions_current.yaml", current_positions)
    if projected_positions is not None:
        dump_positions(day_dir / "positions_after.yaml", projected_positions)

    return day_dir
