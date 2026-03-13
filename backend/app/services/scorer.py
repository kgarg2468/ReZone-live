"""Scorer — combines factor scores into an overall 0-100 feasibility score."""

from __future__ import annotations


# Weights for each factor
WEIGHTS = {
    "zoning": 0.30,
    "utilities": 0.25,
    "transit": 0.20,
    "structural": 0.25,
}

TIERS = [
    (80, "Excellent", "Ideal candidate for residential conversion"),
    (60, "Good", "Viable conversion with moderate investment"),
    (40, "Moderate", "Conversion possible but with significant challenges"),
    (0, "Poor", "Major obstacles — conversion may not be cost-effective"),
]


def compute_score(factor_scores: dict[str, float]) -> tuple[int, str, str]:
    """Return (overall_score, tier_label, tier_description)."""
    total = 0.0
    for factor, weight in WEIGHTS.items():
        total += factor_scores.get(factor, 0) * weight

    score = int(round(min(100, max(0, total))))

    for threshold, label, desc in TIERS:
        if score >= threshold:
            return score, label, desc

    return score, "Poor", TIERS[-1][2]
