"""
portfolio.py — Portfolio state: current holdings, market values, weights, and drift detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rebalancer.config import PortfolioConfig


@dataclass
class Holding:
    ticker: str
    shares: float
    price: float

    @property
    def market_value(self) -> float:
        return self.shares * self.price


@dataclass
class Portfolio:
    config: PortfolioConfig
    holdings: dict[str, Holding] = field(default_factory=dict)

    @property
    def total_value(self) -> float:
        return sum(h.market_value for h in self.holdings.values())

    def current_weights(self) -> dict[str, float]:
        total = self.total_value
        if total == 0:
            return {ticker: 0.0 for ticker in self.holdings}
        return {ticker: h.market_value / total for ticker, h in self.holdings.items()}

    def share_counts(self) -> dict[str, float]:
        """Return current share counts keyed by ticker."""
        return {ticker: holding.shares for ticker, holding in self.holdings.items()}

    def drifts(self) -> dict[str, float]:
        """
        Return the drift of each holding from its target weight.

        With mode="absolute": drift = current_weight - target_weight (in percentage points)
        With mode="relative": drift = (current_weight - target_weight) / target_weight
        """
        target_weights = self.config.target_weights()
        current = self.current_weights()
        drift_cfg = self.config.rebalance.drift

        result: dict[str, float] = {}
        for ticker, target in target_weights.items():
            current_w = current.get(ticker, 0.0)
            if drift_cfg.mode == "absolute":
                result[ticker] = current_w - target
            else:  # relative
                result[ticker] = (current_w - target) / target if target else 0.0
        return result

    def has_drift_breach(self) -> bool:
        """Return True if any holding has drifted beyond the configured threshold."""
        threshold = self.config.rebalance.drift.threshold
        return any(abs(d) > threshold for d in self.drifts().values())

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update the price for each holding."""
        for ticker, price in prices.items():
            if ticker in self.holdings:
                self.holdings[ticker].price = price

    @classmethod
    def from_cash(
        cls,
        config: PortfolioConfig,
        total_cash: float,
        prices: dict[str, float],
    ) -> "Portfolio":
        """
        Initialise a portfolio by allocating total_cash according to target weights.
        """
        holdings: dict[str, Holding] = {}
        for h in config.holdings:
            allocation = total_cash * h.target_weight
            price = prices[h.ticker]
            shares = allocation / price
            holdings[h.ticker] = Holding(ticker=h.ticker, shares=shares, price=price)
        return cls(config=config, holdings=holdings)

    @classmethod
    def from_shares(
        cls,
        config: PortfolioConfig,
        shares_by_ticker: dict[str, float],
        prices: dict[str, float],
    ) -> "Portfolio":
        """Initialise a portfolio from current share counts and latest prices."""
        holdings: dict[str, Holding] = {}
        for holding_config in config.holdings:
            price = prices[holding_config.ticker]
            shares = shares_by_ticker.get(holding_config.ticker, 0.0)
            holdings[holding_config.ticker] = Holding(
                ticker=holding_config.ticker,
                shares=shares,
                price=price,
            )
        return cls(config=config, holdings=holdings)
