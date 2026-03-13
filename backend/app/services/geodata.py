"""GeoDataService — loads GeoJSON layers and provides spatial queries via Shapely."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from shapely.geometry import shape, Point


DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "layers"


class GeoDataService:
    """Loads all GeoJSON layer files and exposes spatial query helpers."""

    def __init__(self):
        self.layers: dict[str, dict] = {}
        self._geometries: dict[str, list[tuple[dict, object]]] = {}

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Read every .geojson file from the data/layers directory."""
        for path in sorted(DATA_DIR.glob("*.geojson")):
            layer_name = path.stem  # e.g. "office_buildings"
            with open(path) as f:
                geojson = json.load(f)
            self.layers[layer_name] = geojson

            entries: list[tuple[dict, object]] = []
            for feat in geojson.get("features", []):
                try:
                    geom = shape(feat["geometry"])
                    entries.append((feat, geom))
                except Exception:
                    continue
            self._geometries[layer_name] = entries

    # ------------------------------------------------------------------
    def get_layer(self, name: str) -> Optional[dict]:
        return self.layers.get(name)

    def layer_names(self) -> list[str]:
        return list(self.layers.keys())

    def layer_counts(self) -> dict[str, int]:
        return {k: len(v.get("features", [])) for k, v in self.layers.items()}

    # ------------------------------------------------------------------
    # Spatial queries
    # ------------------------------------------------------------------
    def get_building_by_id(self, building_id: str) -> Optional[tuple[dict, object]]:
        for feat, geom in self._geometries.get("office_buildings", []):
            props = feat.get("properties", {})
            if props.get("id") == building_id:
                return feat, geom
        return None

    def nearest_building(self, point: Point) -> Optional[tuple[dict, object, float]]:
        """Return the nearest office building to *point* with distance in km."""
        best_feat: Optional[dict] = None
        best_geom: Optional[object] = None
        best_dist = float("inf")
        for feat, geom in self._geometries.get("office_buildings", []):
            dist_km = point.distance(geom) * 111.0  # rough km conversion
            if dist_km < best_dist:
                best_dist = dist_km
                best_feat = feat
                best_geom = geom
        if best_feat is None or best_geom is None:
            return None
        return best_feat, best_geom, round(best_dist, 3)

    def get_all_buildings(self) -> list[dict]:
        results = []
        for feat, geom in self._geometries.get("office_buildings", []):
            props = feat["properties"]
            centroid = geom.centroid
            results.append({
                **props,
                "lat": centroid.y,
                "lng": centroid.x,
            })
        return results

    def features_within_radius(
        self, layer_name: str, center: Point, radius_km: float
    ) -> list[tuple[dict, object, float]]:
        """Return features whose geometry is within *radius_km* of *center*.

        Returns list of (feature_dict, shapely_geom, distance_km).
        """
        # Rough degree conversion (1° lat ≈ 111 km)
        radius_deg = radius_km / 111.0
        results: list[tuple[dict, object, float]] = []
        for feat, geom in self._geometries.get(layer_name, []):
            dist_deg = center.distance(geom)
            dist_km = dist_deg * 111.0
            if dist_km <= radius_km:
                results.append((feat, geom, round(dist_km, 3)))
        results.sort(key=lambda x: x[2])
        return results

    def find_containing_zone(self, point: Point) -> Optional[tuple[dict, object]]:
        """Return the zoning district polygon that contains *point*."""
        for feat, geom in self._geometries.get("zoning_districts", []):
            if geom.contains(point):
                return feat, geom
        return None

    def nearest_feature(
        self, layer_name: str, point: Point
    ) -> Optional[tuple[dict, float]]:
        """Return the single nearest feature in *layer_name* to *point*."""
        best = None
        best_dist = float("inf")
        for feat, geom in self._geometries.get(layer_name, []):
            d = point.distance(geom) * 111.0  # approx km
            if d < best_dist:
                best_dist = d
                best = feat
        if best is not None:
            return best, round(best_dist, 3)
        return None
