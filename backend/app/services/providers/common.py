"""Shared helpers for live providers."""

from __future__ import annotations

from typing import Any


BBox = tuple[float, float, float, float]  # min_lng, min_lat, max_lng, max_lat

MANHATTAN_BBOX: BBox = (-74.03, 40.70, -73.93, 40.89)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def bbox_to_key(bbox: BBox) -> str:
    min_lng, min_lat, max_lng, max_lat = bbox
    return f"{min_lng:.5f},{min_lat:.5f},{max_lng:.5f},{max_lat:.5f}"

