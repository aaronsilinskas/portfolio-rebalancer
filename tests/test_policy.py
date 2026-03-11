from tests.helpers import make_config, make_portfolio


def test_relative_drift_mode_detects_breach():
    config = make_config(mode="relative", threshold=0.20)
    portfolio = make_portfolio(spy_price=200.0, bnd_price=100.0)
    portfolio.config = config

    assert portfolio.has_drift_breach()


def test_relative_drift_mode_stays_within_threshold():
    config = make_config(mode="relative", threshold=0.30)
    portfolio = make_portfolio(spy_price=170.0, bnd_price=100.0)
    portfolio.config = config

    assert not portfolio.has_drift_breach()
