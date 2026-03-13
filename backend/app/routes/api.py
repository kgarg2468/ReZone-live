"""API routes for HomeX."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from shapely.geometry import Point

from ..models import (
    FeasibilityRequest,
    FeasibilityResponse,
    BuildingSummary,
    BuildingDetail,
    LayerInfo,
    DataConfidence,
)
from ..services.geodata import GeoDataService
from ..services.feasibility_engine import FeasibilityEngine
from ..services.scorer import compute_score
from ..services.recommender import recommend
from ..services.providers.common import BBox, MANHATTAN_BBOX

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


def _parse_bbox(bbox: str | None) -> BBox:
    if not bbox:
        return MANHATTAN_BBOX
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=400,
            detail="bbox must be formatted as minLng,minLat,maxLng,maxLat",
        )
    try:
        min_lng, min_lat, max_lng, max_lat = [float(p) for p in parts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bbox values must be valid numbers") from exc

    if min_lng >= max_lng or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="bbox coordinates are invalid")
    return (min_lng, min_lat, max_lng, max_lat)


def _parse_layers(layers_param: str | None) -> list[str]:
    if not layers_param:
        return [
            "office_buildings",
            "zoning_districts",
            "utility_infrastructure",
            "transit_stops",
        ]
    requested = [name.strip() for name in layers_param.split(",") if name.strip()]
    valid = {"office_buildings", "zoning_districts", "utility_infrastructure", "transit_stops"}
    invalid = [name for name in requested if name not in valid]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown layers requested: {', '.join(invalid)}",
        )
    return requested


# ------------------------------------------------------------------
@router.get("/api/layers")
def get_layers(
    bbox: str | None = Query(default=None),
    layers: str | None = Query(default=None),
) -> dict[str, LayerInfo]:
    assert _geo is not None
    bbox_tuple = _parse_bbox(bbox)
    requested_layers = _parse_layers(layers)
    result = {}
    sources = {
        "office_buildings": "NYC PLUTO",
        "zoning_districts": "NYC Zoning Districts (ArcGIS FeatureServer)",
        "utility_infrastructure": "OpenStreetMap Overpass (Proxy)",
        "transit_stops": "Transitland (Proxy Ridership)",
    }
    for name in requested_layers:
        layer = _geo.get_layer(name, bbox=bbox_tuple)
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
def list_buildings(
    bbox: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[BuildingSummary]:
    assert _geo is not None
    bbox_tuple = _parse_bbox(bbox)
    raw = _geo.get_all_buildings(bbox=bbox_tuple, limit=limit, offset=offset)
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


def _confidence_score(
    props: dict,
    zoning,
    utilities,
    transit,
) -> DataConfidence:
    zoning_conf = 0.88 if zoning.zone_name != "Unknown" else 0.35
    if zoning.requires_rezoning:
        zoning_conf -= 0.08
    zoning_conf = max(0.1, min(0.95, zoning_conf))

    covered_utilities = sum(1 for u in utilities if u.score > 20)
    utility_conf = 0.28 + covered_utilities * 0.14
    has_non_proxy = any(not bool(u.is_proxy) for u in utilities if u.is_proxy is not None)
    if has_non_proxy:
        utility_conf += 0.1
    utility_conf = max(0.15, min(0.85, utility_conf))

    station_count = len(transit.nearest_stations)
    transit_conf = 0.35 + min(0.35, station_count * 0.08)
    if not transit.nearest_stations:
        transit_conf = 0.2
    transit_conf = max(0.2, min(0.82, transit_conf))

    proxy_flags = [
        bool(props.get("structural_type_is_proxy", False)),
        bool(props.get("ceiling_height_is_proxy", False)),
        bool(props.get("has_elevator_is_proxy", False)),
    ]
    proxy_ratio = sum(1 for flag in proxy_flags if flag) / len(proxy_flags) if proxy_flags else 1.0
    structural_conf = 0.9 - proxy_ratio * 0.25
    if not props.get("year_built"):
        structural_conf -= 0.1
    if not props.get("sqft"):
        structural_conf -= 0.1
    structural_conf = max(0.25, min(0.9, structural_conf))

    overall = (
        zoning_conf * 0.30
        + utility_conf * 0.25
        + transit_conf * 0.20
        + structural_conf * 0.25
    )
    return DataConfidence(
        overall=round(overall, 2),
        zoning=round(zoning_conf, 2),
        utilities=round(utility_conf, 2),
        transit=round(transit_conf, 2),
        structural=round(structural_conf, 2),
    )


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
    confidence = _confidence_score(props, zoning, utilities, transit)

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
        data_confidence=confidence,
    )
