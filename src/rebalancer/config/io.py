"""Load and validate portfolio and positions YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from rebalancer.config.models import (
    DriftConfig,
    HoldingConfig,
    PortfolioConfig,
    RebalanceConfig,
)
from rebalancer.config.validation import VALID_DRIFT_MODES, VALID_SCHEDULES


def _load_yaml_file(path: Path | str) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return raw


def _normalize_ticker(value: object) -> str:
    ticker = str(value).strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty")
    return ticker


def load_config(path: Path | str) -> PortfolioConfig:
    """Load and validate a portfolio configuration from a YAML file."""
    raw = _load_yaml_file(path)

    try:
        portfolio_raw = raw["portfolio"]
        rebalance_raw = raw["rebalance"]
        drift_raw = rebalance_raw["drift"]
    except KeyError as exc:
        raise ValueError(f"Missing required config key: {exc.args[0]}") from exc

    holdings_raw = portfolio_raw.get("holdings", [])
    if not holdings_raw:
        raise ValueError("Portfolio must define at least one holding")

    holdings: list[HoldingConfig] = []
    seen_tickers: set[str] = set()
    for holding_raw in holdings_raw:
        ticker = _normalize_ticker(holding_raw["ticker"])
        if ticker in seen_tickers:
            raise ValueError(f"Duplicate ticker in portfolio config: {ticker}")

        target_weight = float(holding_raw["target_weight"])
        if not 0.0 < target_weight <= 1.0:
            raise ValueError(
                f"Target weight for {ticker} must be between 0 and 1, got {target_weight}"
            )

        holdings.append(
            HoldingConfig(
                ticker=ticker,
                label=holding_raw["label"],
                target_weight=target_weight,
            )
        )
        seen_tickers.add(ticker)

    total_weight = sum(h.target_weight for h in holdings)
    if abs(total_weight - 1.0) >= 1e-6:
        raise ValueError(f"Target weights must sum to 1.0, but got {total_weight:.6f}")

    mode = drift_raw["mode"]
    if mode not in VALID_DRIFT_MODES:
        raise ValueError(
            f"Unsupported drift mode: {mode}. Expected one of {sorted(VALID_DRIFT_MODES)}"
        )

    threshold = float(drift_raw["threshold"])
    if threshold <= 0:
        raise ValueError(f"Drift threshold must be positive, got {threshold}")

    schedule = rebalance_raw["schedule"]
    if schedule not in VALID_SCHEDULES:
        raise ValueError(
            f"Unsupported rebalance schedule: {schedule}. Expected one of {sorted(VALID_SCHEDULES)}"
        )

    min_days_between_rebalances = int(rebalance_raw["min_days_between_rebalances"])
    if min_days_between_rebalances < 0:
        raise ValueError(
            "min_days_between_rebalances must be greater than or equal to 0"
        )

    drift = DriftConfig(
        mode=mode,
        threshold=threshold,
    )
    rebalance = RebalanceConfig(
        schedule=schedule,
        min_days_between_rebalances=min_days_between_rebalances,
        drift=drift,
    )

    return PortfolioConfig(
        name=portfolio_raw["name"],
        holdings=holdings,
        rebalance=rebalance,
    )


def load_positions(
    path: Path | str,
    *,
    allowed_tickers: set[str] | None = None,
) -> dict[str, float]:
    """Load current portfolio share counts from a YAML file."""
    raw = _load_yaml_file(path)
    positions_raw = raw.get("positions", [])
    if not positions_raw:
        raise ValueError("Positions file must define at least one position")

    normalized_allowed_tickers = (
        {_normalize_ticker(ticker) for ticker in allowed_tickers}
        if allowed_tickers is not None
        else None
    )

    positions: dict[str, float] = {}
    for position_raw in positions_raw:
        ticker = _normalize_ticker(position_raw["ticker"])
        shares = float(position_raw["shares"])
        if shares < 0:
            raise ValueError(f"Position shares for {ticker} must be non-negative")
        if ticker in positions:
            raise ValueError(f"Duplicate ticker in positions file: {ticker}")
        if (
            normalized_allowed_tickers is not None
            and ticker not in normalized_allowed_tickers
        ):
            raise ValueError(f"Ticker {ticker} is not defined in the portfolio config")
        positions[ticker] = shares

    return positions


def dump_positions(path: Path | str, positions: dict[str, float]) -> None:
    """Write portfolio share counts to a YAML file."""
    payload = {
        "positions": [
            {"ticker": ticker, "shares": round(float(shares), 6)}
            for ticker, shares in positions.items()
        ]
    }
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False))
