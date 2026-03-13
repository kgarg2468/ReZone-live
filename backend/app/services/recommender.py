"""Recommender — suggests conversion type, cost estimates, and timeline."""

from __future__ import annotations

from ..models import (
    ConversionRecommendation,
    CostEstimate,
    ZoningAssessment,
    TransitAssessment,
    StructuralAssessment,
)


def recommend(
    building_props: dict,
    zoning: ZoningAssessment,
    transit: TransitAssessment,
    structural: StructuralAssessment,
    overall_score: int,
) -> ConversionRecommendation:
    """Pick the best conversion type and generate cost/timeline estimates."""

    sqft = building_props.get("sqft", 0)
    floors = building_props.get("floors", 1)
    vacancy = building_props.get("vacancy_pct", 0)

    # --- Decide conversion type ---
    candidates: list[tuple[str, float, str]] = []

    # Apartments: best for high-density zones with good transit
    apt_score = 0.0
    if zoning.max_density >= 8:
        apt_score += 40
    if transit.score >= 60:
        apt_score += 30
    if floors >= 6:
        apt_score += 20
    if sqft >= 100000:
        apt_score += 10
    candidates.append(("Apartments", apt_score, "High-density zoning and strong transit access make this building ideal for apartment conversion."))

    # Condos: similar to apartments but for mid-range density
    condo_score = 0.0
    if 5 <= zoning.max_density < 12:
        condo_score += 35
    if transit.score >= 40:
        condo_score += 25
    if floors >= 4:
        condo_score += 20
    if sqft >= 80000:
        condo_score += 10
    if structural.ceiling_height_ft >= 12:
        condo_score += 10
    candidates.append(("Condominiums", condo_score, "Mid-density zoning and building characteristics suit condominium conversion with higher per-unit value."))

    # Mixed-use: if zoning is mixed-use
    mixed_score = 0.0
    if zoning.zone_type == "mixed-use":
        mixed_score += 45
    if transit.score >= 50:
        mixed_score += 25
    if floors >= 3:
        mixed_score += 15
    if sqft >= 60000:
        mixed_score += 15
    candidates.append(("Mixed-Use (Retail + Housing)", mixed_score, "Mixed-use zoning allows retail on ground floor with residential above — maximizing revenue per sqft."))

    # Townhouses: low-rise only
    town_score = 0.0
    if floors <= 5:
        town_score += 40
    if zoning.max_density <= 8:
        town_score += 25
    if sqft <= 120000:
        town_score += 20
    if structural.structural_type == "masonry":
        town_score += 15
    candidates.append(("Townhouses", town_score, "Low-rise structure and moderate density make townhouse subdivision a viable option."))

    # Pick winner
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_type, best_conf, best_rationale = candidates[0]

    # --- Estimate units ---
    avg_unit_sqft = {"Apartments": 750, "Condominiums": 1000, "Mixed-Use (Retail + Housing)": 850, "Townhouses": 1400}
    usable_sqft = int(sqft * 0.75)  # ~25% lost to corridors, mechanical, etc.
    units = max(1, usable_sqft // avg_unit_sqft.get(best_type, 900))

    # --- Cost estimates ---
    cost_per_sqft = {
        "Apartments": (120, 200),
        "Condominiums": (150, 250),
        "Mixed-Use (Retail + Housing)": (140, 230),
        "Townhouses": (100, 180),
    }
    low_rate, high_rate = cost_per_sqft.get(best_type, (130, 220))

    costs = [
        CostEstimate(
            category="Plumbing & Water Systems",
            low_estimate=int(sqft * low_rate * 0.18),
            high_estimate=int(sqft * high_rate * 0.18),
            notes="Kitchen/bathroom rough-in for each unit, water heater installation",
        ),
        CostEstimate(
            category="Electrical & HVAC",
            low_estimate=int(sqft * low_rate * 0.22),
            high_estimate=int(sqft * high_rate * 0.22),
            notes="Individual unit metering, HVAC split systems, panel upgrades",
        ),
        CostEstimate(
            category="Structural Modifications",
            low_estimate=int(sqft * low_rate * 0.25),
            high_estimate=int(sqft * high_rate * 0.25),
            notes="Demising walls, floor reinforcement, fire separation",
        ),
        CostEstimate(
            category="Interior Finish",
            low_estimate=int(sqft * low_rate * 0.20),
            high_estimate=int(sqft * high_rate * 0.20),
            notes="Unit layouts, flooring, kitchens, bathrooms, paint",
        ),
        CostEstimate(
            category="Permits & Soft Costs",
            low_estimate=int(sqft * low_rate * 0.15),
            high_estimate=int(sqft * high_rate * 0.15),
            notes="Architectural, engineering, permits, inspections, legal",
        ),
    ]

    # Timeline
    if sqft <= 80000:
        months = 12
    elif sqft <= 200000:
        months = 18
    else:
        months = 24
    if structural.conversion_difficulty == "hard":
        months += 6
    elif structural.conversion_difficulty == "moderate":
        months += 3

    return ConversionRecommendation(
        conversion_type=best_type,
        confidence=round(min(1.0, best_conf / 100), 2),
        rationale=best_rationale,
        estimated_units=units,
        cost_estimates=costs,
        timeline_months=months,
    )
