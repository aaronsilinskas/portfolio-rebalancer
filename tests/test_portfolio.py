"""
Tests for portfolio weight calculation and drift detection.
"""

from rebalancer.config import (
    DriftConfig,
    HoldingConfig,
    PortfolioConfig,
    RebalanceConfig,
)
from rebalancer.portfolio import Holding, Portfolio


def _make_config(mode: str = "absolute", threshold: float = 0.075) -> PortfolioConfig:
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


def _make_portfolio(
    spy_price: float,
    bnd_price: float,
    spy_shares: float = 60.0,
    bnd_shares: float = 40.0,
) -> Portfolio:
    config = _make_config()
    holdings = {
        "SPY": Holding(ticker="SPY", shares=spy_shares, price=spy_price),
        "BND": Holding(ticker="BND", shares=bnd_shares, price=bnd_price),
    }
    return Portfolio(config=config, holdings=holdings)


class TestWeights:
    def test_weights_sum_to_one(self):
        portfolio = _make_portfolio(spy_price=100.0, bnd_price=100.0)
        weights = portfolio.current_weights()
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_equal_price_weights_match_shares(self):
        # 60 SPY @ $100 = $6000, 40 BND @ $100 = $4000 → 60% / 40%
        portfolio = _make_portfolio(spy_price=100.0, bnd_price=100.0)
        weights = portfolio.current_weights()
        assert abs(weights["SPY"] - 0.60) < 1e-9
        assert abs(weights["BND"] - 0.40) < 1e-9


class TestDrift:
    def test_no_drift_when_on_target(self):
        portfolio = _make_portfolio(spy_price=100.0, bnd_price=100.0)
        assert not portfolio.has_drift_breach()

    def test_drift_breach_absolute(self):
        # SPY goes up so much that its weight exceeds 60% + 7.5% = 67.5%
        # 60 SPY @ $200 = $12000, 40 BND @ $100 = $4000 → SPY weight = 75%
        portfolio = _make_portfolio(spy_price=200.0, bnd_price=100.0)
        assert portfolio.has_drift_breach()

    def test_no_drift_breach_within_threshold(self):
        # SPY slightly up: 60 @ $110 = $6600, 40 BND @ $100 = $4000 → SPY = 62.3%
        portfolio = _make_portfolio(spy_price=110.0, bnd_price=100.0)
        assert not portfolio.has_drift_breach()


class TestFromCash:
    def test_from_cash_allocates_correctly(self):
        config = _make_config()
        prices = {"SPY": 400.0, "BND": 100.0}
        portfolio = Portfolio.from_cash(config, total_cash=10_000.0, prices=prices)

        assert abs(portfolio.total_value - 10_000.0) < 0.01
        weights = portfolio.current_weights()
        assert abs(weights["SPY"] - 0.60) < 1e-6
        assert abs(weights["BND"] - 0.40) < 1e-6
