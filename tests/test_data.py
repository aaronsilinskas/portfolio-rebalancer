from datetime import date

import pandas as pd
import pytest

from rebalancer.data import fetch_prices


def test_fetch_prices_uses_inclusive_end_date(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, str] = {}

    def fake_download(*args, **kwargs):
        captured["end"] = kwargs["end"]
        return pd.DataFrame(
            {"Close": [100.0, 101.0]},
            index=pd.to_datetime(["2024-01-30", "2024-01-31"]),
        )

    monkeypatch.setattr("rebalancer.data.yf.download", fake_download)

    prices = fetch_prices(["SPY"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    assert captured["end"] == "2024-02-01"
    assert list(prices.columns) == ["SPY"]


def test_fetch_prices_rejects_end_before_start():
    with pytest.raises(ValueError, match="End date must be on or after start date"):
        fetch_prices(["SPY"], start=date(2024, 1, 31), end=date(2024, 1, 1))
