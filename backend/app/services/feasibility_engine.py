"""FeasibilityEngine — core analysis engine for office-to-housing conversion."""

from __future__ import annotations

from shapely.geometry import Point

from ..models import (
    ZoningAssessment,
    UtilityAssessment,
    TransitAssessment,
    StructuralAssessment,
)
from .geodata import GeoDataService


class FeasibilityEngine:
    """Analyzes a building against zoning, utilities, transit, and structural factors."""

    def __init__(self, geo: GeoDataService):
        self.geo = geo

    # ------------------------------------------------------------------
    # Zoning
    # ------------------------------------------------------------------
    def assess_zoning(self, center: Point) -> ZoningAssessment:
        result = self.geo.find_containing_zone(center)
        if result is None:
            return ZoningAssessment(
                zone_name="Unknown",
                zone_type="unknown",
                allows_residential=False,
                max_density=0,
                max_height_ft=0,
                requires_rezoning=True,
                score=20.0,
            )
        feat, _ = result
        props = feat["properties"]
        allows = props.get("allows_residential", False)

        score = 0.0
        if allows:
            score = 90.0
            # bonus for higher density allowance
            density = props.get("max_density", 0)
            if density >= 10:
                score = 95.0
        else:
            # Rezoning possible but expensive — not a blocker for scoring
            zone_type = props.get("zone_type", "")
            if zone_type == "commercial":
                score = 40.0  # common target for conversion
            elif zone_type == "industrial":
                score = 25.0  # harder
            else:
                score = 30.0

        return ZoningAssessment(
            zone_name=props.get("name", "Unknown"),
            zone_type=props.get("zone_type", "unknown"),
            allows_residential=allows,
            max_density=props.get("max_density", 0),
            max_height_ft=props.get("max_height_ft", 0),
            requires_rezoning=not allows,
            score=round(score, 1),
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def assess_utilities(self, center: Point, radius_km: float) -> list[UtilityAssessment]:
        nearby = self.geo.features_within_radius("utility_infrastructure", center, radius_km)

        # Group by utility type and pick best
        by_type: dict[str, list] = {}
        for feat, geom, dist in nearby:
            ut = feat["properties"].get("utility_type", "unknown")
            by_type.setdefault(ut, []).append((feat, dist))

        assessments = []
        for utype in ["water_main", "sewer", "electrical", "gas"]:
            entries = by_type.get(utype, [])
            if not entries:
                assessments.append(UtilityAssessment(
                    utility_type=utype,
                    nearest_distance_km=999,
                    capacity="none",
                    condition="unavailable",
                    age_years=0,
                    score=10.0,
                ))
                continue

            best = entries[0]
            feat, dist = best
            props = feat["properties"]

            # Score based on distance, capacity, and condition
            dist_score = max(0, 100 - dist * 100)  # closer = better
            cap_map = {"high": 30, "medium": 20, "low": 10, "none": 0}
            cond_map = {"good": 30, "fair": 20, "poor": 5}

            raw = (
                dist_score * 0.4
                + cap_map.get(props.get("capacity", "none"), 0) * 0.3 / 30 * 100
                + cond_map.get(props.get("condition", "poor"), 0) * 0.3 / 30 * 100
            )
            score = min(100, max(0, raw))

            assessments.append(UtilityAssessment(
                utility_type=utype,
                nearest_distance_km=dist,
                capacity=props.get("capacity", "unknown"),
                condition=props.get("condition", "unknown"),
                age_years=props.get("age_years", 0),
                score=round(score, 1),
            ))

        return assessments

    # ------------------------------------------------------------------
    # Transit
    # ------------------------------------------------------------------
    def assess_transit(self, center: Point, radius_km: float) -> TransitAssessment:
        nearby = self.geo.features_within_radius("transit_stops", center, radius_km)

        if not nearby:
            return TransitAssessment(
                nearest_stations=[],
                avg_distance_km=999,
                total_daily_ridership=0,
                score=15.0,
            )

        stations = []
        total_ridership = 0
        total_dist = 0.0
        for feat, geom, dist in nearby[:5]:  # top 5
            props = feat["properties"]
            stations.append({
                "name": props.get("station_name", "Unknown"),
                "line": props.get("line_name", ""),
                "type": props.get("transit_type", ""),
                "distance_km": dist,
                "daily_ridership": props.get("daily_ridership", 0),
            })
            total_ridership += props.get("daily_ridership", 0)
            total_dist += dist

        avg_dist = total_dist / len(stations) if stations else 999

        # Score: proximity + ridership
        proximity_score = max(0, 100 - avg_dist * 80)
        ridership_score = min(100, total_ridership / 500)  # cap at 100
        score = proximity_score * 0.6 + ridership_score * 0.4

        return TransitAssessment(
            nearest_stations=stations,
            avg_distance_km=round(avg_dist, 3),
            total_daily_ridership=total_ridership,
            score=round(min(100, score), 1),
        )

    # ------------------------------------------------------------------
    # Structural
    # ------------------------------------------------------------------
    def assess_structural(self, building_props: dict) -> StructuralAssessment:
        stype = building_props.get("structural_type", "unknown")
        year = building_props.get("year_built", 1970)
        floors = building_props.get("floors", 1)
        sqft = building_props.get("sqft", 0)
        ceiling = building_props.get("ceiling_height_ft", 10)
        elevator = building_props.get("has_elevator", False)

        # Difficulty heuristic
        difficulty_score = 0.0

        # Structural type
        type_scores = {"steel-frame": 85, "concrete": 70, "masonry": 50}
        difficulty_score += type_scores.get(stype, 40)

        # Age penalty
        age = 2025 - year
        if age < 30:
            difficulty_score += 10
        elif age < 50:
            difficulty_score += 5
        elif age < 80:
            difficulty_score -= 5
        else:
            difficulty_score -= 15

        # Ceiling height bonus (higher = better for splitting into units)
        if ceiling >= 14:
            difficulty_score += 10
        elif ceiling >= 12:
            difficulty_score += 5

        # Elevator
        if elevator:
            difficulty_score += 5

        # Floor count — mid-rise is ideal
        if 4 <= floors <= 15:
            difficulty_score += 5
        elif floors > 25:
            difficulty_score -= 5

        score = min(100, max(0, difficulty_score))

        if score >= 70:
            difficulty = "easy"
        elif score >= 45:
            difficulty = "moderate"
        else:
            difficulty = "hard"

        return StructuralAssessment(
            structural_type=stype,
            year_built=year,
            floors=floors,
            sqft=sqft,
            ceiling_height_ft=ceiling,
            has_elevator=elevator,
            conversion_difficulty=difficulty,
            score=round(score, 1),
        )
