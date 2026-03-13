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
