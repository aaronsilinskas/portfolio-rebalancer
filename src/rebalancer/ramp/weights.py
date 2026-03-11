"""Ramp-stage target weight policy."""

from __future__ import annotations

from rebalancer.config import PortfolioConfig


CATEGORY_RAMP_WEIGHTS = {
    "US Large-Cap Equities": {"stage1": 0.24, "stage2": 0.18},
    "US Small/Mid-Cap Equities": {"stage1": 0.08, "stage2": 0.09},
    "Developed ex-US Equities": {"stage1": 0.10, "stage2": 0.10},
    "Emerging Markets Equities": {"stage1": 0.06, "stage2": 0.08},
    "Global Real Estate": {"stage1": 0.05, "stage2": 0.07},
    "Precious Metals/Gold": {"stage1": 0.07, "stage2": 0.09},
    "Broad Commodities": {"stage1": 0.05, "stage2": 0.08},
    "Energy/Resources": {"stage1": 0.05, "stage2": 0.07},
    "Bonds/Fixed Income": {"stage1": 0.18, "stage2": 0.13},
    "Cash/Short-Term": {"stage1": 0.12, "stage2": 0.11},
}


def _resolve_stage_weight(label: str, stage: str, default_weight: float) -> float:
    label_l = label.lower()
    for category_label, stage_weights in CATEGORY_RAMP_WEIGHTS.items():
        category_l = category_label.lower()
        if category_l in label_l or label_l in category_l:
            return stage_weights[stage]
    # Fallback for custom labels: keep configured target weight.
    return default_weight


def get_ramp_target_weights(config: PortfolioConfig, stage: str) -> dict[str, float]:
    """Get per-ticker ramp target weights for the selected stage."""
    if stage == "final":
        return config.target_weights()

    raw_weights = {
        holding.ticker: _resolve_stage_weight(
            holding.label,
            stage,
            holding.target_weight,
        )
        for holding in config.holdings
    }

    total = sum(raw_weights.values())
    if total <= 0:
        raise ValueError("Ramp stage weights must sum to a positive number")

    # Normalize to exactly 1.0 if fallback labels changed the total.
    return {ticker: weight / total for ticker, weight in raw_weights.items()}
