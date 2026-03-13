"""NYC PLUTO building provider."""

from __future__ import annotations

import math
import os
from typing import Any

import httpx
from shapely.geometry import shape

from .common import BBox, clamp, to_float, to_int


class NYCPlutoProvider:
    """Fetches NYC office-likely buildings from PLUTO via Socrata."""

    DATASET_URL = "https://data.cityofnewyork.us/resource/64uk-42ks.geojson"

    def __init__(
        self,
        client: httpx.Client | None = None,
        app_token: str | None = None,
    ):
        self.client = client or httpx.Client(timeout=25.0)
        self.app_token = app_token or os.getenv("SOCRATA_APP_TOKEN", "")

    def fetch_buildings(
        self,
        bbox: BBox,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        min_lng, min_lat, max_lng, max_lat = bbox
        where = (
            f"latitude between {min_lat} and {max_lat} "
            f"AND longitude between {min_lng} and {max_lng} "
            "AND (officearea > 0 OR landuse='05' OR landuse='5') "
            "AND bldgarea > 25000"
        )

        params = {
            "$where": where,
            "$limit": str(limit),
            "$offset": str(offset),
            "$order": "bbl",
        }
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        res = self.client.get(self.DATASET_URL, params=params, headers=headers)
        res.raise_for_status()
        payload = res.json()

        raw_features = payload.get("features", [])
        features: list[dict[str, Any]] = []
        for raw in raw_features:
            normalized = self.normalize_feature(raw)
            if normalized is not None:
                features.append(normalized)

        return {"type": "FeatureCollection", "features": features}

    def fetch_building_by_id(self, building_id: str) -> dict[str, Any] | None:
        quoted_id = building_id if building_id.isdigit() else f"'{building_id}'"
        params = {
            "$where": f"bbl={quoted_id}",
            "$limit": "1",
        }
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        res = self.client.get(self.DATASET_URL, params=params, headers=headers)
        res.raise_for_status()
        payload = res.json()
        features = payload.get("features", [])
        if not features:
            return None
        return self.normalize_feature(features[0])

    @classmethod
    def normalize_feature(cls, feature: dict[str, Any]) -> dict[str, Any] | None:
        props = feature.get("properties", {})
        bbl_raw = props.get("bbl") or feature.get("id")
        if not bbl_raw:
            return None
        building_id = cls._canonical_id(str(bbl_raw).strip())

        sqft = max(0, to_int(props.get("bldgarea"), 0))
        geometry = feature.get("geometry")
        if not geometry:
            lat = to_float(props.get("latitude"), 0.0)
            lng = to_float(props.get("longitude"), 0.0)
            if not lat or not lng:
                return None
            geometry = cls._synthetic_polygon(lat, lng, sqft or 45000)

        geom = shape(geometry)
        centroid = geom.centroid
        lng = round(float(centroid.x), 6)
        lat = round(float(centroid.y), 6)

        floors = max(1, to_int(props.get("numfloors"), 1))
        year_built = max(1850, min(2026, to_int(props.get("yearbuilt"), 1970)))

        address = cls._address(props)
        city = cls._city(props)
        current_use = cls._current_use(props)
        structural_type = cls._structural_type(year_built, floors)
        has_elevator = floors >= 6
        ceiling_height = cls._ceiling_height(floors)
        vacancy_pct = cls._vacancy_proxy(building_id, sqft, floors, year_built)

        parking_spaces = to_int(
            props.get("parking") or props.get("parkingspaces") or props.get("parkingspots"),
            0,
        )

        name = props.get("address") or f"{address} Office Property"

        normalized_props = {
            "id": building_id,
            "name": name,
            "address": address,
            "city": city,
            "sqft": sqft,
            "floors": floors,
            "year_built": year_built,
            "vacancy_pct": vacancy_pct,
            "current_use": current_use,
            "structural_type": structural_type,
            "parking_spaces": max(0, parking_spaces),
            "has_elevator": has_elevator,
            "ceiling_height_ft": ceiling_height,
            "lat": lat,
            "lng": lng,
            "data_source": "NYC PLUTO",
            "vacancy_is_proxy": True,
            "structural_type_is_proxy": True,
            "ceiling_height_is_proxy": True,
            "has_elevator_is_proxy": True,
        }

        return {
            "type": "Feature",
            "id": building_id,
            "properties": normalized_props,
            "geometry": geometry,
        }

    @staticmethod
    def _canonical_id(value: str) -> str:
        text = value.strip()
        if text.endswith(".00000000"):
            text = text.replace(".00000000", "")
        if text.endswith(".0"):
            text = text[:-2]
        if text.replace(".", "", 1).isdigit() and "." in text:
            try:
                return str(int(float(text)))
            except Exception:
                return text
        return text

    @staticmethod
    def _address(props: dict[str, Any]) -> str:
        direct = str(props.get("address") or "").strip()
        if direct:
            return direct

        number = str(props.get("housenum_lo") or props.get("housenumber") or "").strip()
        street = str(props.get("streetname") or props.get("stname") or "").strip()
        if number and street:
            return f"{number} {street}"
        if street:
            return street
        return "Unknown Address"

    @staticmethod
    def _city(props: dict[str, Any]) -> str:
        borough = str(props.get("borough") or props.get("borocode") or "").strip().upper()
        mapping = {
            "MN": "New York",
            "1": "New York",
            "BK": "Brooklyn",
            "2": "Bronx",
            "3": "Brooklyn",
            "4": "Queens",
            "5": "Staten Island",
        }
        return mapping.get(borough, "New York")

    @staticmethod
    def _current_use(props: dict[str, Any]) -> str:
        landuse = str(props.get("landuse") or "").zfill(2)
        if landuse == "05":
            return "Commercial/Office"
        if landuse == "04":
            return "Mixed Commercial"
        return "Office"

    @staticmethod
    def _structural_type(year_built: int, floors: int) -> str:
        if floors >= 20 or year_built >= 1960:
            return "steel-frame"
        if floors >= 9:
            return "concrete"
        return "masonry"

    @staticmethod
    def _ceiling_height(floors: int) -> int:
        if floors >= 20:
            return 13
        if floors >= 10:
            return 12
        return 11

    @staticmethod
    def _vacancy_proxy(
        building_id: str,
        sqft: int,
        floors: int,
        year_built: int,
    ) -> int:
        base = 30.0
        if sqft >= 250000:
            base += 14
        elif sqft >= 120000:
            base += 9
        elif sqft >= 80000:
            base += 5

        if floors >= 20:
            base += 8
        elif floors >= 12:
            base += 4

        age = 2026 - year_built
        if age >= 70:
            base += 14
        elif age >= 45:
            base += 10
        elif age >= 25:
            base += 5

        numeric_tail = "".join(ch for ch in building_id if ch.isdigit())[-2:]
        seed = to_float(numeric_tail, 7.0)
        base += (seed % 11.0) - 5.0

        return int(round(clamp(base, 18, 88)))

    @staticmethod
    def _synthetic_polygon(lat: float, lng: float, sqft: int) -> dict[str, Any]:
        # Approximate footprint from area proxy to keep polygons renderable on map.
        footprint_sqft = max(2500, min(35000, sqft * 0.18))
        side_ft = math.sqrt(footprint_sqft)
        side_m = side_ft * 0.3048
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
