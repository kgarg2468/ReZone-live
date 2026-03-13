from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, model_validator


class FeasibilityRequest(BaseModel):
    building_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: float = 1.0  # search radius for nearby infrastructure

    @model_validator(mode="after")
    def validate_location_input(self) -> "FeasibilityRequest":
        has_building_id = bool(self.building_id)
        has_coordinates = self.lat is not None and self.lng is not None
        if not has_building_id and not has_coordinates:
            raise ValueError("Provide either building_id or both lat/lng")
        return self


class UtilityAssessment(BaseModel):
    utility_type: str
    nearest_distance_km: float
    capacity: str
    condition: str
    age_years: int
    score: float  # 0-100


class ZoningAssessment(BaseModel):
    zone_name: str
    zone_type: str
    allows_residential: bool
    max_density: float
    max_height_ft: int
    requires_rezoning: bool
    score: float  # 0-100


class TransitAssessment(BaseModel):
    nearest_stations: list[dict]
    avg_distance_km: float
    total_daily_ridership: int
    score: float  # 0-100


class StructuralAssessment(BaseModel):
    structural_type: str
    year_built: int
    floors: int
    sqft: int
    ceiling_height_ft: int
    has_elevator: bool
    conversion_difficulty: str  # easy, moderate, hard
    score: float  # 0-100


class CostEstimate(BaseModel):
    category: str
    low_estimate: int
    high_estimate: int
    notes: str


class ConversionRecommendation(BaseModel):
    conversion_type: str  # apartments, condos, townhouses, mixed-use
    confidence: float
    rationale: str
    estimated_units: int
    cost_estimates: list[CostEstimate]
    timeline_months: int


class FeasibilityResponse(BaseModel):
    building_id: str
    building_name: str
    address: str
    score: int  # 0-100
    tier: str  # Excellent, Good, Moderate, Poor
    tier_description: str
    conflicts: list[str]

    zoning: ZoningAssessment
    utilities: list[UtilityAssessment]
    transit: TransitAssessment
    structural: StructuralAssessment

    recommendation: ConversionRecommendation

    factor_scores: dict[str, float]


class BuildingSummary(BaseModel):
    id: str
    name: str
    address: str
    city: str
    sqft: int
    floors: int
    vacancy_pct: int
    structural_type: str
    lat: float
    lng: float


class BuildingDetail(BuildingSummary):
    geometry: dict
    year_built: int
    current_use: str
    parking_spaces: int
    has_elevator: bool
    ceiling_height_ft: int


class LayerInfo(BaseModel):
    name: str
    source: str
    feature_count: int
    geojson: dict
