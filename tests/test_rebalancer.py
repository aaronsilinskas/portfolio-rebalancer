"""
Tests for rebalancing trade computation.
"""

from rebalancer.config import (
    DriftConfig,
    HoldingConfig,
    PortfolioConfig,
    RebalanceConfig,
)
from rebalancer.portfolio import Holding, Portfolio
from rebalancer.rebalancer import apply_trades, compute_trades


def _make_two_asset_portfolio(spy_value: float, bnd_value: float) -> Portfolio:
    holdings_cfg = [
        HoldingConfig(ticker="SPY", label="US Large-Cap", target_weight=0.60),
        HoldingConfig(ticker="BND", label="Bonds", target_weight=0.40),
    ]
    config = PortfolioConfig(
        name="Test",
        holdings=holdings_cfg,
        rebalance=RebalanceConfig(
            schedule="2nd_wednesday",
            min_days_between_rebalances=7,
            drift=DriftConfig(mode="absolute", threshold=0.075),
        ),
    )
    holdings = {
        "SPY": Holding(ticker="SPY", shares=spy_value / 100.0, price=100.0),
        "BND": Holding(ticker="BND", shares=bnd_value / 100.0, price=100.0),
    }
    return Portfolio(config=config, holdings=holdings)


def test_compute_trades_restores_target_weights():
    # SPY drifted to 75%, BND to 25% — should sell SPY and buy BND
    portfolio = _make_two_asset_portfolio(spy_value=7500.0, bnd_value=2500.0)
    trades = compute_trades(portfolio)

    actions = {t.ticker: t.action for t in trades}
    assert actions["SPY"] == "SELL"
    assert actions["BND"] == "BUY"


def test_apply_trades_restores_weights():
    portfolio = _make_two_asset_portfolio(spy_value=7500.0, bnd_value=2500.0)
    trades = compute_trades(portfolio)
    apply_trades(portfolio, trades)

    weights = portfolio.current_weights()
    assert abs(weights["SPY"] - 0.60) < 1e-6
    assert abs(weights["BND"] - 0.40) < 1e-6


def test_no_trades_when_on_target():
    portfolio = _make_two_asset_portfolio(spy_value=6000.0, bnd_value=4000.0)
    trades = compute_trades(portfolio)
    assert trades == []
