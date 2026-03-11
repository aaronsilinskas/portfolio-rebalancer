"""Shared test helpers for building config and portfolio objects."""

from rebalancer.config import (
    DriftConfig,
    HoldingConfig,
    PortfolioConfig,
    RebalanceConfig,
)
from rebalancer.portfolio import Holding, Portfolio


def make_config(mode: str = "absolute", threshold: float = 0.075) -> PortfolioConfig:
    holdings = [
        HoldingConfig(ticker="SPY", label="US Large-Cap", target_weight=0.60),
        HoldingConfig(ticker="BND", label="Bonds", target_weight=0.40),
    ]
    drift = DriftConfig(mode=mode, threshold=threshold)
    rebalance = RebalanceConfig(
        schedule="2nd_wednesday",
        min_days_between_rebalances=7,
        drift=drift,
    )
    return PortfolioConfig(name="Test", holdings=holdings, rebalance=rebalance)


def make_portfolio(
    spy_price: float,
    bnd_price: float,
    spy_shares: float = 60.0,
    bnd_shares: float = 40.0,
) -> Portfolio:
    config = make_config()
    holdings = {
        "SPY": Holding(ticker="SPY", shares=spy_shares, price=spy_price),
        "BND": Holding(ticker="BND", shares=bnd_shares, price=bnd_price),
    }
    return Portfolio(config=config, holdings=holdings)
