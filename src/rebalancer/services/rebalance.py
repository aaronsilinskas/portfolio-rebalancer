"""Service workflows for daily rebalancing operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from rebalancer.config import dump_positions, load_config, load_positions
from rebalancer.portfolio import Portfolio
from rebalancer.rebalancer import Trade, compute_trades, project_shares_after_trades
from rebalancer.report import write_daily_check_files


@dataclass
class DailyCheckResult:
    status: str
    output_path: Path
    reasons: list[str]
    trades: list[Trade]


@dataclass
class SyncPositionsResult:
    positions_path: Path
    added: list[str]
    dropped: list[str]
    synced_positions: dict[str, float]


def run_daily_check(
    *,
    config_path: Path,
    positions_path: Path,
    output_dir: Path,
    as_of: date,
    latest_price_fetcher: Callable[[list[str]], dict[str, float]],
    schedule_checker: Callable[[date], bool],
) -> DailyCheckResult:
    """Run daily schedule/drift checks and write review artifacts."""
    cfg = load_config(config_path)
    prices = latest_price_fetcher(cfg.tickers())

    shares_by_ticker = load_positions(
        positions_path, allowed_tickers=set(cfg.tickers())
    )
    portfolio = Portfolio.from_shares(cfg, shares_by_ticker, prices)
    current_positions = portfolio.share_counts()

    if portfolio.total_value <= 0:
        reasons = [
            "positions file contains zero market value; update shares when holdings are established"
        ]
        output_path = write_daily_check_files(
            as_of=as_of,
            portfolio=portfolio,
            drifts=None,
            trades=[],
            reasons=reasons,
            status="skipped_no_positions",
            output_dir=output_dir,
            current_positions=current_positions,
        )
        return DailyCheckResult(
            status="skipped_no_positions",
            output_path=output_path,
            reasons=reasons,
            trades=[],
        )

    scheduled = schedule_checker(as_of)
    drifts = portfolio.drifts()
    threshold = cfg.rebalance.drift.threshold
    breaches = {
        ticker: drift for ticker, drift in drifts.items() if abs(drift) > threshold
    }
    drift_breach = bool(breaches)

    if not scheduled and not drift_breach:
        reasons = ["no rebalance trigger detected"]
        output_path = write_daily_check_files(
            as_of=as_of,
            portfolio=portfolio,
            drifts=drifts,
            trades=[],
            reasons=reasons,
            status="no_action",
            output_dir=output_dir,
            current_positions=current_positions,
        )
        return DailyCheckResult(
            status="no_action",
            output_path=output_path,
            reasons=reasons,
            trades=[],
        )

    reasons: list[str] = []
    if scheduled:
        reasons.append("scheduled (2nd Wednesday)")
    if drift_breach:
        reasons.append(f"drift breach: {breaches}")

    trades = compute_trades(portfolio)
    if not trades:
        reasons = reasons + ["portfolio is already at target weights"]
        output_path = write_daily_check_files(
            as_of=as_of,
            portfolio=portfolio,
            drifts=drifts,
            trades=[],
            reasons=reasons,
            status="no_action",
            output_dir=output_dir,
            current_positions=current_positions,
        )
        return DailyCheckResult(
            status="no_action",
            output_path=output_path,
            reasons=reasons,
            trades=[],
        )

    projected_positions = project_shares_after_trades(current_positions, trades)
    output_path = write_daily_check_files(
        as_of=as_of,
        portfolio=portfolio,
        drifts=drifts,
        trades=trades,
        reasons=reasons,
        status="action_required",
        output_dir=output_dir,
        current_positions=current_positions,
        projected_positions=projected_positions,
    )
    return DailyCheckResult(
        status="action_required",
        output_path=output_path,
        reasons=reasons,
        trades=trades,
    )


def sync_positions_file(
    *,
    config_path: Path,
    positions_path: Path,
    default_shares: float,
) -> SyncPositionsResult:
    """Sync position tickers to current portfolio config."""
    cfg = load_config(config_path)

    existing_positions: dict[str, float] = {}
    if positions_path.exists():
        existing_positions = load_positions(positions_path)

    target_tickers = cfg.tickers()
    synced_positions = {
        ticker: float(existing_positions.get(ticker, default_shares))
        for ticker in target_tickers
    }

    dropped = sorted(set(existing_positions) - set(target_tickers))
    added = [ticker for ticker in target_tickers if ticker not in existing_positions]

    dump_positions(positions_path, synced_positions)
    return SyncPositionsResult(
        positions_path=positions_path,
        added=added,
        dropped=dropped,
        synced_positions=synced_positions,
    )
