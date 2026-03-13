"""NYC zoning districts provider (ArcGIS FeatureServer)."""

from __future__ import annotations

from typing import Any

import httpx

from .common import BBox, clamp, to_float


class NYCZoningProvider:
    QUERY_URL = (
        "https://services1.arcgis.com/3yPqaPHdDzXwd0QH/arcgis/rest/services/"
        "NYC_Zoning_Districts/FeatureServer/0/query"
    )

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=25.0)

    def fetch_zones(self, bbox: BBox, limit: int = 2500) -> dict[str, Any]:
        min_lng, min_lat, max_lng, max_lat = bbox
        params = {
            "where": "1=1",
            "geometry": f"{min_lng},{min_lat},{max_lng},{max_lat}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": str(limit),
        }
        res = self.client.get(self.QUERY_URL, params=params)
        res.raise_for_status()
        payload = res.json()

        features: list[dict[str, Any]] = []
        for index, raw in enumerate(payload.get("features", [])):
            normalized = self.normalize_feature(raw, index=index)
            if normalized is not None:
                features.append(normalized)
        return {"type": "FeatureCollection", "features": features}

    @classmethod
    def normalize_feature(
        cls,
        feature: dict[str, Any],
        index: int = 0,
    ) -> dict[str, Any] | None:
        geometry = feature.get("geometry")
        if not geometry:
            return None
        props = feature.get("properties", {})

        zone_name = str(
            props.get("ZONEDIST")
            or props.get("zonedist")
            or props.get("zone_name")
            or "Unknown"
        ).strip()
        zone_name = zone_name or "Unknown"
        zone_type = cls._zone_type(zone_name)
        allows_residential = cls._allows_residential(zone_name, zone_type)
        max_density = cls._density_proxy(zone_name, zone_type)
        max_height_ft = cls._height_proxy(max_density, zone_type)

        object_id = props.get("OBJECTID") or props.get("objectid") or index
        zone_id = str(object_id)

        normalized_props = {
            "id": f"nyc_zone_{zone_id}",
            "zone_type": zone_type,
            "allows_residential": allows_residential,
            "max_density": max_density,
            "max_height_ft": max_height_ft,
            "name": zone_name,
            "jurisdiction": "NYC DCP",
            "source": "NYC Zoning FeatureServer",
        }
        return {
            "type": "Feature",
            "id": normalized_props["id"],
            "properties": normalized_props,
            "geometry": geometry,
        }

    @staticmethod
    def _zone_type(zone_name: str) -> str:
        up = zone_name.upper()
        if "MX" in up:
            return "mixed-use"
        if up.startswith("R"):
            return "residential"
        if up.startswith("C"):
            return "commercial"
        if up.startswith("M"):
            return "industrial"
        return "unknown"

    @staticmethod
    def _allows_residential(zone_name: str, zone_type: str) -> bool:
        up = zone_name.upper()
        if zone_type in {"residential", "mixed-use"}:
            return True
        if up.startswith("C") and ("R" in up or "MX" in up):
            return True
        return False

    @staticmethod
    def _density_proxy(zone_name: str, zone_type: str) -> float:
        up = zone_name.upper()
        numeric_part = ""
        for char in up:
            if char.isdigit() or char == ".":
                numeric_part += char
            elif numeric_part:
                break

        znum = to_float(numeric_part, 0.0)

        if zone_type == "residential":
            base = 3.0 + znum * 0.9 if znum else 5.5
        elif zone_type == "mixed-use":
            base = 6.0 + znum * 0.7 if znum else 8.0
        elif zone_type == "commercial":
            base = 5.0 + znum * 0.85 if znum else 7.0
        elif zone_type == "industrial":
            base = 2.0 + znum * 0.4 if znum else 3.0
        else:
            base = 4.0

        return round(clamp(base, 1.5, 20.0), 1)

    @staticmethod
    def _height_proxy(max_density: float, zone_type: str) -> int:
        factor = {
            "residential": 26,
            "mixed-use": 30,
            "commercial": 34,
            "industrial": 20,
            "unknown": 22,
        }.get(zone_type, 22)
        return int(round(clamp(55 + max_density * factor, 55, 600)))

