"""Live GeoDataService backed by NYC public APIs."""

from __future__ import annotations

import math
from typing import Any, Optional

from shapely.geometry import Point, shape

from .cache import TTLCache
from .providers import (
    NYCPlutoProvider,
    NYCZoningProvider,
    TransitlandProvider,
    OverpassUtilityProvider,
)
from .providers.common import BBox, MANHATTAN_BBOX, bbox_to_key


LAYER_NAMES = [
    "office_buildings",
    "zoning_districts",
    "utility_infrastructure",
    "transit_stops",
]

MOCK_BUILDING_SEEDS: list[dict[str, Any]] = [
    {
        "id": "mock-good-001",
        "name": "Hudson Exchange",
        "address": "410 7th Ave",
        "city": "New York",
        "lat": 40.7528,
        "lng": -73.9875,
        "sqft": 165000,
        "floors": 16,
        "year_built": 1998,
        "vacancy_pct": 4,
        "structural_type": "steel-frame",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-002",
        "name": "Bryant Square Tower",
        "address": "40 W 40th St",
        "city": "New York",
        "lat": 40.7549,
        "lng": -73.9840,
        "sqft": 142000,
        "floors": 14,
        "year_built": 2004,
        "vacancy_pct": 6,
        "structural_type": "steel-frame",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-003",
        "name": "Midtown Core",
        "address": "18 W 34th St",
        "city": "New York",
        "lat": 40.7484,
        "lng": -73.9857,
        "sqft": 118000,
        "floors": 12,
        "year_built": 1992,
        "vacancy_pct": 2,
        "structural_type": "concrete",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-004",
        "name": "Times Annex",
        "address": "155 W 47th St",
        "city": "New York",
        "lat": 40.7580,
        "lng": -73.9855,
        "sqft": 126000,
        "floors": 15,
        "year_built": 2001,
        "vacancy_pct": 8,
        "structural_type": "steel-frame",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-005",
        "name": "Lexington Plaza",
        "address": "400 Lexington Ave",
        "city": "New York",
        "lat": 40.7608,
        "lng": -73.9795,
        "sqft": 172000,
        "floors": 18,
        "year_built": 2008,
        "vacancy_pct": 7,
        "structural_type": "steel-frame",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-006",
        "name": "Grand Hub",
        "address": "327 Park Ave S",
        "city": "New York",
        "lat": 40.7448,
        "lng": -73.9808,
        "sqft": 98000,
        "floors": 11,
        "year_built": 1996,
        "vacancy_pct": 5,
        "structural_type": "concrete",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-007",
        "name": "Flatiron House",
        "address": "41 E 22nd St",
        "city": "New York",
        "lat": 40.7412,
        "lng": -73.9897,
        "sqft": 89000,
        "floors": 10,
        "year_built": 1990,
        "vacancy_pct": 1,
        "structural_type": "concrete",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-008",
        "name": "Upper East Office",
        "address": "152 E 79th St",
        "city": "New York",
        "lat": 40.7712,
        "lng": -73.9742,
        "sqft": 76000,
        "floors": 9,
        "year_built": 1988,
        "vacancy_pct": 9,
        "structural_type": "concrete",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-009",
        "name": "SoHo Works",
        "address": "182 Spring St",
        "city": "New York",
        "lat": 40.7295,
        "lng": -73.9980,
        "sqft": 67000,
        "floors": 8,
        "year_built": 1999,
        "vacancy_pct": 3,
        "structural_type": "steel-frame",
        "mock_profile": "great",
    },
    {
        "id": "mock-good-010",
        "name": "Financial Green",
        "address": "88 Greenwich St",
        "city": "New York",
        "lat": 40.7168,
        "lng": -74.0002,
        "sqft": 101000,
        "floors": 13,
        "year_built": 2007,
        "vacancy_pct": 10,
        "structural_type": "steel-frame",
        "mock_profile": "great",
    },
    {
        "id": "mock-poor-001",
        "name": "Legacy Annex",
        "address": "24 Broad St",
        "city": "New York",
        "lat": 40.7058,
        "lng": -74.0132,
        "sqft": 54000,
        "floors": 27,
        "year_built": 1915,
        "vacancy_pct": 6,
        "structural_type": "masonry",
        "mock_profile": "poor",
    },
    {
        "id": "mock-poor-002",
        "name": "River Terminal",
        "address": "245 South St",
        "city": "New York",
        "lat": 40.7099,
        "lng": -73.9915,
        "sqft": 61000,
        "floors": 30,
        "year_built": 1922,
        "vacancy_pct": 8,
        "structural_type": "masonry",
        "mock_profile": "poor",
    },
]


def _bbox_contains_lat_lng(bbox: BBox, lat: float, lng: float) -> bool:
    min_lng, min_lat, max_lng, max_lat = bbox
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat


def _mock_polygon(lat: float, lng: float, side_m: float = 34.0) -> dict[str, Any]:
    dlat = side_m / 111_000.0
    dlng = side_m / (111_000.0 * max(0.2, math.cos(math.radians(lat))))
    return {
        "type": "Polygon",
        "coordinates": [[
            [lng - dlng, lat - dlat],
            [lng + dlng, lat - dlat],
            [lng + dlng, lat + dlat],
            [lng - dlng, lat + dlat],
            [lng - dlng, lat - dlat],
        ]],
    }


def _mock_building_feature(seed: dict[str, Any]) -> dict[str, Any]:
    floors = int(seed["floors"])
    props = {
        "id": seed["id"],
        "name": seed["name"],
        "address": seed["address"],
        "city": seed["city"],
        "sqft": int(seed["sqft"]),
        "floors": floors,
        "year_built": int(seed["year_built"]),
        "vacancy_pct": int(seed["vacancy_pct"]),
        "current_use": "Office",
        "structural_type": seed["structural_type"],
        "parking_spaces": 0,
        "has_elevator": floors >= 7,
        "ceiling_height_ft": 12 if floors >= 12 else 11,
        "lat": float(seed["lat"]),
        "lng": float(seed["lng"]),
        "data_source": "HomeX Mock Data",
        "vacancy_is_proxy": False,
        "structural_type_is_proxy": False,
        "ceiling_height_is_proxy": False,
        "has_elevator_is_proxy": False,
        "mock_profile": seed["mock_profile"],
    }
    return {
        "type": "Feature",
        "id": seed["id"],
        "properties": props,
        "geometry": _mock_polygon(props["lat"], props["lng"]),
    }


def _mock_buildings_for_bbox(bbox: BBox) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for seed in MOCK_BUILDING_SEEDS:
        if _bbox_contains_lat_lng(bbox, float(seed["lat"]), float(seed["lng"])):
            features.append(_mock_building_feature(seed))
    return features


def _mock_building_by_id(building_id: str) -> dict[str, Any] | None:
    for seed in MOCK_BUILDING_SEEDS:
        if seed["id"] == building_id:
            return _mock_building_feature(seed)
    return None


class GeoDataService:
    """Loads live geo layers on demand and exposes spatial query helpers."""

    def __init__(self):
        self.pluto = NYCPlutoProvider()
        self.zoning = NYCZoningProvider()
        self.transit = TransitlandProvider()
        self.utilities = OverpassUtilityProvider()

        self._layer_cache: TTLCache[dict[str, Any]] = TTLCache(ttl_seconds=300)

    def load(self) -> None:
        """Warm cache for default bbox; failures are non-fatal in demo mode."""
        try:
            self.fetch_layers(MANHATTAN_BBOX, layer_names=LAYER_NAMES)
        except Exception as exc:
            print(f"[HomeX] Live cache warmup skipped: {exc}")

    def layer_names(self) -> list[str]:
        return list(LAYER_NAMES)

    def layer_counts(self) -> dict[str, int]:
        layers = self.fetch_layers(MANHATTAN_BBOX, layer_names=LAYER_NAMES)
        return {name: len(layer.get("features", [])) for name, layer in layers.items()}

    def get_layer(
        self,
        name: str,
        bbox: BBox = MANHATTAN_BBOX,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> Optional[dict[str, Any]]:
        if name not in LAYER_NAMES:
            return None
        return self._fetch_layer(name, bbox, limit=limit, offset=offset)

    def fetch_layers(
        self,
        bbox: BBox,
        layer_names: list[str],
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for layer_name in layer_names:
            layer = self.get_layer(layer_name, bbox=bbox)
            if layer is not None:
                result[layer_name] = layer
        return result

    def get_building_by_id(self, building_id: str) -> Optional[tuple[dict, object]]:
        mock_feature = _mock_building_by_id(building_id)
        if mock_feature is not None:
            try:
                geom = shape(mock_feature["geometry"])
            except Exception:
                return None
            return mock_feature, geom

        try:
            feature = self.pluto.fetch_building_by_id(building_id)
        except Exception as exc:
            print(f"[HomeX] Building lookup failed ({building_id}): {exc}")
            return None
        if not feature:
            return None
        try:
            geom = shape(feature["geometry"])
        except Exception:
            return None
        return feature, geom

    def nearest_building(self, point: Point) -> Optional[tuple[dict, object, float]]:
        # A 2.5km window is usually enough for dense NYC office inventory.
        bbox = bbox_around_point(point.y, point.x, radius_km=2.5)
        layer = self._fetch_layer("office_buildings", bbox, limit=600, offset=0)
        features = layer.get("features", []) if layer else []

        best_feat: Optional[dict] = None
        best_geom: Optional[object] = None
        best_dist = float("inf")
        for feat in features:
            try:
                geom = shape(feat["geometry"])
            except Exception:
                continue
            dist_km = haversine_km(point.y, point.x, geom.centroid.y, geom.centroid.x)
            if dist_km < best_dist:
                best_dist = dist_km
                best_feat = feat
                best_geom = geom

        if best_feat is None or best_geom is None:
            return None
        return best_feat, best_geom, round(best_dist, 3)

    def get_all_buildings(
        self,
        bbox: BBox = MANHATTAN_BBOX,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        layer = self._fetch_layer("office_buildings", bbox, limit=limit, offset=offset)
        if not layer:
            return []
        results: list[dict[str, Any]] = []
        for feat in layer.get("features", []):
            props = feat.get("properties", {})
            results.append(
                {
                    **props,
                    "lat": props.get("lat", 0.0),
                    "lng": props.get("lng", 0.0),
                }
            )
        return results

    def features_within_radius(
        self,
        layer_name: str,
        center: Point,
        radius_km: float,
    ) -> list[tuple[dict, object, float]]:
        bbox = bbox_around_point(center.y, center.x, radius_km=radius_km)
        layer = self._fetch_layer(layer_name, bbox, limit=800, offset=0)
        if not layer:
            return []

        results: list[tuple[dict, object, float]] = []
        for feat in layer.get("features", []):
            try:
                geom = shape(feat["geometry"])
            except Exception:
                continue
            dist_km = haversine_km(center.y, center.x, geom.centroid.y, geom.centroid.x)
            if dist_km <= radius_km:
                results.append((feat, geom, round(dist_km, 3)))

        results.sort(key=lambda x: x[2])
        return results

    def find_containing_zone(self, point: Point) -> Optional[tuple[dict, object]]:
        bbox = bbox_around_point(point.y, point.x, radius_km=1.8)
        layer = self._fetch_layer("zoning_districts", bbox, limit=2500, offset=0)
        if not layer:
            return None
        fallback: Optional[tuple[dict, object, float]] = None

        for feat in layer.get("features", []):
            try:
                geom = shape(feat["geometry"])
            except Exception:
                continue
            if geom.contains(point):
                return feat, geom
            dist_km = haversine_km(point.y, point.x, geom.centroid.y, geom.centroid.x)
            if fallback is None or dist_km < fallback[2]:
                fallback = (feat, geom, dist_km)

        if fallback:
            return fallback[0], fallback[1]
        return None

    def nearest_feature(self, layer_name: str, point: Point) -> Optional[tuple[dict, float]]:
        bbox = bbox_around_point(point.y, point.x, radius_km=2.0)
        layer = self._fetch_layer(layer_name, bbox, limit=1200, offset=0)
        if not layer:
            return None

        best = None
        best_dist = float("inf")
        for feat in layer.get("features", []):
            try:
                geom = shape(feat["geometry"])
            except Exception:
                continue
            d = haversine_km(point.y, point.x, geom.centroid.y, geom.centroid.x)
            if d < best_dist:
                best_dist = d
                best = feat
        if best is not None:
            return best, round(best_dist, 3)
        return None

    def _fetch_layer(
        self,
        layer_name: str,
        bbox: BBox,
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        cache_key = f"{layer_name}:{bbox_to_key(bbox)}:{limit}:{offset}"
        cached = self._layer_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            if layer_name == "office_buildings":
                layer = self.pluto.fetch_buildings(bbox, limit=limit, offset=offset)
                if offset == 0:
                    mock_features = _mock_buildings_for_bbox(bbox)
                    if mock_features:
                        live_features = layer.get("features", [])
                        known_ids = {
                            str(feature.get("id") or feature.get("properties", {}).get("id"))
                            for feature in live_features
                        }
                        for mock_feature in mock_features:
                            mock_id = str(
                                mock_feature.get("id")
                                or mock_feature.get("properties", {}).get("id")
                            )
                            if mock_id in known_ids:
                                continue
                            live_features.append(mock_feature)
                            known_ids.add(mock_id)
                        layer["features"] = live_features
            elif layer_name == "zoning_districts":
                layer = self.zoning.fetch_zones(bbox, limit=max(limit, 1200))
            elif layer_name == "transit_stops":
                layer = self.transit.fetch_stops(bbox, limit=max(limit, 300))
            elif layer_name == "utility_infrastructure":
                layer = self.utilities.fetch_utilities(bbox)
            else:
                layer = {"type": "FeatureCollection", "features": []}
        except Exception as exc:
            print(f"[HomeX] Layer fetch failed ({layer_name}): {exc}")
            layer = {"type": "FeatureCollection", "features": []}

        self._layer_cache.set(cache_key, layer)
        return layer


def bbox_around_point(lat: float, lng: float, radius_km: float) -> BBox:
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
    return (
        round(lng - lng_delta, 6),
        round(lat - lat_delta, 6),
        round(lng + lng_delta, 6),
        round(lat + lat_delta, 6),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c
