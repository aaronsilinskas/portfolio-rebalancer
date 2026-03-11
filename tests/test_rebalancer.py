"""
Tests for rebalancing trade computation.
"""

from rebalancer.rebalancer import apply_trades, compute_trades
from tests.helpers import make_portfolio


def test_compute_trades_restores_target_weights():
    # SPY drifted to 75%, BND to 25% — should sell SPY and buy BND
    portfolio = make_portfolio(
        spy_price=100.0, bnd_price=100.0, spy_shares=75.0, bnd_shares=25.0
    )
    trades = compute_trades(portfolio)

    actions = {t.ticker: t.action for t in trades}
    assert actions["SPY"] == "SELL"
    assert actions["BND"] == "BUY"


def test_apply_trades_restores_weights():
    portfolio = make_portfolio(
        spy_price=100.0, bnd_price=100.0, spy_shares=75.0, bnd_shares=25.0
    )
    trades = compute_trades(portfolio)
    apply_trades(portfolio, trades)

    weights = portfolio.current_weights()
    assert abs(weights["SPY"] - 0.60) < 1e-6
    assert abs(weights["BND"] - 0.40) < 1e-6


def test_no_trades_when_on_target():
    # Default shares (60 SPY, 40 BND) at equal prices → exactly at 60/40 target
    portfolio = make_portfolio(spy_price=100.0, bnd_price=100.0)
    trades = compute_trades(portfolio)
    assert trades == []
