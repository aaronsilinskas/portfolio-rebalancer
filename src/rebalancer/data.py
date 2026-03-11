"""
data.py — Fetch historical and current price data from Yahoo Finance via yfinance.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf


def fetch_prices(
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Fetch adjusted closing prices for a list of tickers over a date range.

    Returns a DataFrame with dates as the index and tickers as columns.
    Raises ValueError if any ticker returns no data.
    """
    raw = yf.download(
        tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
    )

    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        # Single ticker — yfinance returns a flat DataFrame
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        raise ValueError(f"No price data returned for tickers: {missing}")

    return prices.dropna(how="all")


def fetch_latest_prices(tickers: list[str]) -> dict[str, float]:
    """
    Fetch the most recent closing price for each ticker.

    Uses a 5-day window to handle weekends and market holidays.
    Returns a dict mapping ticker -> price.
    """
    raw = yf.download(tickers, period="5d", auto_adjust=True, progress=False)
    prices = (
        raw["Close"]
        if isinstance(raw.columns, pd.MultiIndex)
        else raw[["Close"]].rename(columns={"Close": tickers[0]})
    )
    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        raise ValueError(f"No price data returned for tickers: {missing}")
    return {ticker: float(prices[ticker].dropna().iloc[-1]) for ticker in tickers}
