"""Transitland provider for NYC transit stops."""

from __future__ import annotations

import csv
import io
import os
import zipfile
from typing import Any

import httpx

from .common import BBox, clamp


class TransitlandProvider:
    STOPS_URL = "https://transit.land/api/v2/rest/stops"
    MTA_SUBWAY_GTFS_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None):
        self.client = client or httpx.Client(timeout=25.0)
        self.api_key = api_key or os.getenv("TRANSITLAND_API_KEY", "")

    def fetch_stops(self, bbox: BBox, limit: int = 400) -> dict[str, Any]:
        min_lng, min_lat, max_lng, max_lat = bbox
        params = {
            "bbox": f"{min_lng},{min_lat},{max_lng},{max_lat}",
            "limit": str(limit),
            "include": "routes,stop_platforms",
        }
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["apikey"] = self.api_key

        try:
            res = self.client.get(self.STOPS_URL, params=params, headers=headers)
            res.raise_for_status()
            payload = res.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                return self.fetch_mta_subway_stops(bbox, limit=limit)
            raise
        except Exception:
            return self.fetch_mta_subway_stops(bbox, limit=limit)

        features: list[dict[str, Any]] = []
        raw_stops = payload.get("stops") or []
        if raw_stops:
            for stop in raw_stops:
                normalized = self.normalize_stop(stop)
                if normalized is not None:
                    features.append(normalized)
        else:
            for feat in payload.get("features", []):
                normalized = self.normalize_feature(feat)
                if normalized is not None:
                    features.append(normalized)

        return {"type": "FeatureCollection", "features": features}

    def fetch_mta_subway_stops(self, bbox: BBox, limit: int = 400) -> dict[str, Any]:
        min_lng, min_lat, max_lng, max_lat = bbox
        res = self.client.get(self.MTA_SUBWAY_GTFS_URL)
        res.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            with zf.open("stops.txt") as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
                features: list[dict[str, Any]] = []
                for row in reader:
                    try:
                        lat = float(row.get("stop_lat") or 0)
                        lon = float(row.get("stop_lon") or 0)
                    except Exception:
                        continue
                    if not (min_lat <= lat <= max_lat and min_lng <= lon <= max_lng):
                        continue

                    location_type = str(row.get("location_type") or "0")
                    # Prefer stations and parent stops for cleaner map symbols.
                    if location_type not in {"0", "1"}:
                        continue

                    stop_id = str(row.get("stop_id") or "")
                    if not stop_id:
                        continue
                    stop_name = row.get("stop_name") or "Unknown Station"
                    route_hint = stop_id[0] if stop_id else "MTA"
                    route_count = 3 if location_type == "1" else 1
                    ridership = self._mta_ridership_proxy(stop_name, location_type)

                    properties = {
                        "id": f"mta_{stop_id}",
                        "transit_type": "subway",
                        "line_name": route_hint,
                        "station_name": stop_name,
                        "daily_ridership": ridership,
                        "route_count": route_count,
                        "source": "MTA GTFS",
                        "is_proxy": True,
                    }
                    features.append(
                        {
                            "type": "Feature",
                            "id": properties["id"],
                            "properties": properties,
                            "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        }
                    )
                    if len(features) >= limit:
                        break

        return {"type": "FeatureCollection", "features": features}

    @classmethod
    def normalize_stop(cls, stop: dict[str, Any]) -> dict[str, Any] | None:
        lon = stop.get("lon") or stop.get("longitude")
        lat = stop.get("lat") or stop.get("latitude")
        if lon is None or lat is None:
            geom = stop.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
        if lon is None or lat is None:
            return None

        stop_id = str(stop.get("onestop_id") or stop.get("id") or stop.get("stop_id") or "")
        if not stop_id:
            return None

        route_names = cls._extract_route_names(stop)
        route_count = len(route_names)
        daily_ridership = cls._ridership_proxy(route_count, stop)
        transit_type = cls._transit_type(stop)

        properties = {
            "id": stop_id,
            "transit_type": transit_type,
            "line_name": "/".join(route_names[:5]) if route_names else "Local Service",
            "station_name": stop.get("name") or "Unknown Station",
            "daily_ridership": daily_ridership,
            "route_count": route_count,
            "source": "Transitland",
            "is_proxy": True,
        }

        return {
            "type": "Feature",
            "id": stop_id,
            "properties": properties,
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
        }

    @classmethod
    def normalize_feature(cls, feature: dict[str, Any]) -> dict[str, Any] | None:
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            return None
        props = feature.get("properties", {})
        stop = {
            "id": props.get("id") or feature.get("id"),
            "name": props.get("name") or props.get("station_name"),
            "routes": props.get("routes") or [],
            "geometry": geometry,
            "vehicle_types": props.get("vehicle_types"),
        }
        normalized = cls.normalize_stop(stop)
        if normalized is None:
            return None
        normalized["properties"]["daily_ridership"] = int(
            props.get("daily_ridership") or normalized["properties"]["daily_ridership"]
        )
        return normalized

    @staticmethod
    def _extract_route_names(stop: dict[str, Any]) -> list[str]:
        route_names: list[str] = []
        routes = stop.get("routes") or []
        for route in routes:
            name = (
                route.get("route_short_name")
                or route.get("short_name")
                or route.get("route_long_name")
                or route.get("name")
            )
            if name:
                route_names.append(str(name))

        # Fallback route hints for sparse payloads.
        rsp = stop.get("route_stop_patterns") or []
        for pattern in rsp:
            route = pattern.get("route") or {}
            name = route.get("route_short_name") or route.get("name")
            if name:
                route_names.append(str(name))

        # Preserve order while de-duplicating.
        seen: set[str] = set()
        ordered: list[str] = []
        for name in route_names:
            if name in seen:
                continue
            seen.add(name)
            ordered.append(name)
        return ordered

    @staticmethod
    def _ridership_proxy(route_count: int, stop: dict[str, Any]) -> int:
        base = 2500 + route_count * 5200
        if stop.get("wheelchair_boarding") in {1, "1", True}:
            base += 1200
        if stop.get("parent_station"):
            base += 1800
        return int(round(clamp(base, 1500, 125000)))

    @staticmethod
    def _transit_type(stop: dict[str, Any]) -> str:
        vehicle_types = stop.get("vehicle_types")
        if isinstance(vehicle_types, list) and vehicle_types:
            first = str(vehicle_types[0]).lower()
            if "rail" in first or "subway" in first:
                return "subway"
            if "bus" in first:
                return "bus"
            if "tram" in first:
                return "tram"
        return "transit"

    @staticmethod
    def _mta_ridership_proxy(station_name: str, location_type: str) -> int:
        base = 9000 if location_type == "1" else 4500
        major_hubs = (
            "Times Sq",
            "Grand Central",
            "Union Sq",
            "Penn Station",
            "Fulton",
            "34 St",
            "Atlantic",
        )
        if any(hub.lower() in station_name.lower() for hub in major_hubs):
            base += 28000
        return int(clamp(base, 3500, 95000))
