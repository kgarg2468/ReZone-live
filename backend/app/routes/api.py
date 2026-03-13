"""API routes for HomeX."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from shapely.geometry import Point

from ..models import (
    FeasibilityRequest,
    FeasibilityResponse,
    BuildingSummary,
    BuildingDetail,
    LayerInfo,
)
from ..services.geodata import GeoDataService
from ..services.feasibility_engine import FeasibilityEngine
from ..services.scorer import compute_score
from ..services.recommender import recommend

router = APIRouter()

# Singletons — set at startup by main.py
_geo: GeoDataService | None = None
_engine: FeasibilityEngine | None = None


def init(geo: GeoDataService) -> None:
    global _geo, _engine
    _geo = geo
    _engine = FeasibilityEngine(geo)


# ------------------------------------------------------------------
@router.get("/health")
def health():
    assert _geo is not None
    return {
        "status": "ok",
        "layers_loaded": _geo.layer_counts(),
        "total_buildings": len(_geo.get_all_buildings()),
    }


# ------------------------------------------------------------------
@router.get("/api/layers")
def get_layers() -> dict[str, LayerInfo]:
    assert _geo is not None
    result = {}
    sources = {
        "office_buildings": "HomeX Mock Data — Office Buildings",
        "zoning_districts": "HomeX Mock Data — City Zoning",
        "utility_infrastructure": "HomeX Mock Data — Utility Lines",
        "transit_stops": "HomeX Mock Data — Transit Stops",
    }
    for name in _geo.layer_names():
        layer = _geo.get_layer(name)
        if layer:
            result[name] = LayerInfo(
                name=name,
                source=sources.get(name, "HomeX"),
                feature_count=len(layer.get("features", [])),
                geojson=layer,
            )
    return result


# ------------------------------------------------------------------
@router.get("/api/buildings")
def list_buildings() -> list[BuildingSummary]:
    assert _geo is not None
    raw = _geo.get_all_buildings()
    return [BuildingSummary(**b) for b in raw]


# ------------------------------------------------------------------
@router.get("/api/buildings/{building_id}")
def get_building(building_id: str):
    assert _geo is not None
    result = _geo.get_building_by_id(building_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Building not found")
    feat, geom = result
    centroid = geom.centroid
    return BuildingDetail(
        **feat["properties"],
        lat=centroid.y,
        lng=centroid.x,
        geometry=feat["geometry"],
    )


def _resolve_target_building(req: FeasibilityRequest) -> tuple[dict, object]:
    assert _geo is not None
    if req.building_id:
        result = _geo.get_building_by_id(req.building_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Building not found")
        return result

    # Coordinates path: use nearest building, constrained by request radius.
    assert req.lat is not None and req.lng is not None
    nearest = _geo.nearest_building(Point(req.lng, req.lat))
    if nearest is None:
        raise HTTPException(status_code=404, detail="No office buildings available")

    feat, geom, dist_km = nearest
    if dist_km > req.radius_km:
        raise HTTPException(
            status_code=404,
            detail=f"No building found within {req.radius_km} km of provided coordinates",
        )
    return feat, geom


# ------------------------------------------------------------------
@router.post("/api/feasibility-check")
def feasibility_check(req: FeasibilityRequest) -> FeasibilityResponse:
    assert _geo is not None
    assert _engine is not None

    feat, geom = _resolve_target_building(req)
    props = feat["properties"]
    center = geom.centroid

    # Run assessments
    zoning = _engine.assess_zoning(center)
    utilities = _engine.assess_utilities(center, req.radius_km)
    transit = _engine.assess_transit(center, req.radius_km)
    structural = _engine.assess_structural(props)

    # Average utility scores
    util_avg = sum(u.score for u in utilities) / len(utilities) if utilities else 0

    # Compute overall score
    factor_scores = {
        "zoning": zoning.score,
        "utilities": util_avg,
        "transit": transit.score,
        "structural": structural.score,
    }
    score, tier, tier_desc = compute_score(factor_scores)

    # Get recommendation
    rec = recommend(props, zoning, transit, structural, score)

    conflicts: list[str] = []
    if zoning.requires_rezoning:
        conflicts.append("Zoning does not currently allow residential use; rezoning required.")
    for utility in utilities:
        if utility.score < 40:
            conflicts.append(
                f"{utility.utility_type.replace('_', ' ').title()} access is constrained "
                f"(condition: {utility.condition}, capacity: {utility.capacity})."
            )
    if transit.score < 40:
        conflicts.append("Transit accessibility is weak for residential conversion.")
    if structural.conversion_difficulty == "hard":
        conflicts.append("Structural characteristics indicate a high conversion difficulty.")

    return FeasibilityResponse(
        building_id=props.get("id", req.building_id or ""),
        building_name=props.get("name", "Unknown"),
        address=props.get("address", ""),
        score=score,
        tier=tier,
        tier_description=tier_desc,
        conflicts=conflicts,
        zoning=zoning,
        utilities=utilities,
        transit=transit,
        structural=structural,
        recommendation=rec,
        factor_scores=factor_scores,
    )
