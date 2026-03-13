"""Overpass provider for utility infrastructure proxies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from .common import BBox


class OverpassUtilityProvider:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=35.0)

    def fetch_utilities(self, bbox: BBox) -> dict[str, Any]:
        min_lng, min_lat, max_lng, max_lat = bbox
        south, west, north, east = min_lat, min_lng, max_lat, max_lng
        query = f"""
[out:json][timeout:25];
(
  way["power"~"line|minor_line|cable"]({south},{west},{north},{east});
  node["power"="substation"]({south},{west},{north},{east});
  way["man_made"="pipeline"]["substance"~"water|sewage|wastewater|gas"]({south},{west},{north},{east});
  relation["man_made"="pipeline"]["substance"~"water|sewage|wastewater|gas"]({south},{west},{north},{east});
  way["utility"~"water|sewer|gas|electricity"]({south},{west},{north},{east});
  node["utility"~"water|sewer|gas|electricity"]({south},{west},{north},{east});
);
out center tags;
"""
        res = self.client.post(self.OVERPASS_URL, data=query.strip())
        res.raise_for_status()
        payload = res.json()

        features: list[dict[str, Any]] = []
        for element in payload.get("elements", []):
            normalized = self.normalize_element(element)
            if normalized is not None:
                features.append(normalized)
        return {"type": "FeatureCollection", "features": features}

    @classmethod
    def normalize_element(cls, element: dict[str, Any]) -> dict[str, Any] | None:
        lon, lat = cls._point_for_element(element)
        if lon is None or lat is None:
            return None

        tags = element.get("tags") or {}
        utility_type = cls._utility_type(tags)
        if utility_type is None:
            return None

        capacity = cls._capacity(tags, utility_type)
        age_years = cls._age_years(tags)
        condition = cls._condition(tags, age_years)

        element_id = element.get("id")
        if element_id is None:
            return None
        utility_id = f"osm_{element.get('type', 'feature')}_{element_id}"

        props = {
            "id": utility_id,
            "utility_type": utility_type,
            "capacity": capacity,
            "age_years": age_years,
            "condition": condition,
            "source": "OpenStreetMap Overpass",
            "is_proxy": True,
        }
        return {
            "type": "Feature",
            "id": utility_id,
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        }

    @staticmethod
    def _point_for_element(element: dict[str, Any]) -> tuple[float | None, float | None]:
        if "lon" in element and "lat" in element:
            return float(element["lon"]), float(element["lat"])
        center = element.get("center")
        if center and "lon" in center and "lat" in center:
            return float(center["lon"]), float(center["lat"])
        geom = element.get("geometry")
        if isinstance(geom, list) and geom:
            first = geom[0]
            if "lon" in first and "lat" in first:
                return float(first["lon"]), float(first["lat"])
        return None, None

    @staticmethod
    def _utility_type(tags: dict[str, Any]) -> str | None:
        power = str(tags.get("power") or "").lower()
        utility = str(tags.get("utility") or "").lower()
        substance = str(tags.get("substance") or "").lower()
        pipeline = str(tags.get("pipeline") or "").lower()

        if power in {"line", "minor_line", "cable", "substation"} or utility == "electricity":
            return "electrical"
        if substance in {"gas", "natural_gas"} or utility == "gas":
            return "gas"
        if substance in {"sewage", "wastewater"} or utility in {"sewer", "wastewater"}:
            return "sewer"
        if substance == "water" or utility == "water" or pipeline == "water":
            return "water_main"
        return None

    @staticmethod
    def _capacity(tags: dict[str, Any], utility_type: str) -> str:
        diameter_raw = str(tags.get("diameter") or "").lower().replace("mm", "").strip()
        pressure_raw = str(tags.get("pressure") or "").lower().strip()
        voltage_raw = str(tags.get("voltage") or "").lower().strip()
        power = str(tags.get("power") or "").lower()

        try:
            diameter = float(diameter_raw)
        except Exception:
            diameter = 0.0

        try:
            voltage = float(voltage_raw.split(";")[0]) if voltage_raw else 0.0
        except Exception:
            voltage = 0.0

        if utility_type == "electrical":
            if power == "line" or voltage >= 69000:
                return "high"
            if power in {"minor_line", "cable", "substation"}:
                return "medium"
            return "low"

        if utility_type == "water_main":
            if diameter >= 500:
                return "high"
            if diameter >= 250:
                return "medium"
            return "low"

        if utility_type == "sewer":
            if diameter >= 700:
                return "high"
            if diameter >= 350:
                return "medium"
            return "low"

        if utility_type == "gas":
            if "high" in pressure_raw:
                return "high"
            if pressure_raw:
                return "medium"
            return "low"

        return "medium"

    @staticmethod
    def _age_years(tags: dict[str, Any]) -> int:
        start_date = str(tags.get("start_date") or "").strip()
        if len(start_date) >= 4 and start_date[:4].isdigit():
            year = int(start_date[:4])
            return max(1, min(120, datetime.now().year - year))
        return 35

    @staticmethod
    def _condition(tags: dict[str, Any], age_years: int) -> str:
        explicit = str(tags.get("condition") or "").lower()
        if explicit in {"excellent", "good", "fair", "poor"}:
            if explicit == "excellent":
                return "good"
            return explicit

        if age_years <= 25:
            return "good"
        if age_years <= 55:
            return "fair"
        return "poor"

