# requires-python is >=3.8: keep builtin generics and X | None annotations lazy.
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _bounds_of(value: Any) -> list[float]:
    """Accept a bare bounds list or a dict carrying a 'bounds' entry."""
    if isinstance(value, dict):
        return value["bounds"]
    return value


def _polygons_of(value: Any) -> list[list[list[float]]]:
    """Normalise a country value (one polygon or a list of polygons) to a list of polygons."""
    if value and isinstance(value[0][0], (int, float)):
        return [value]
    return value


def get_sector(sectors_manifest: dict[str, Any], coordinates: dict[str, float]) -> str | None:
    """
    Find which sector a coordinate falls into based on bounding boxes.

    Args:
        sectors_manifest: Dict mapping sector keys to bounding box lists
            [lat_min, lng_min, lat_max, lng_max].
        coordinates: Dict with 'lat' and 'lng' keys.

    Returns:
        Sector key if found, else None.
    """
    lat = coordinates["lat"]
    lng = coordinates["lng"]

    for key, bounds in sectors_manifest.items():
        lat_min, lng_min, lat_max, lng_max = _bounds_of(bounds)
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return key
    return None


def point_in_polygon(point: list[float], polygon: list[list[float]]) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm.

    Args:
        point: [lat, lng]
        polygon: List of [lat, lng] points defining polygon vertices.

    Returns:
        True if point is inside polygon, else False.
    """
    x, y = point
    inside = False
    n = len(polygon)

    for i in range(n):
        j = (i - 1) % n
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi)
        if intersect:
            inside = not inside
    return inside


def get_country(sector_manifest: dict[str, Any], coordinates: dict[str, float]) -> str | None:
    """
    Determine the country within a sector by testing polygons.

    Args:
        sector_manifest: Dict mapping country keys to polygons (list of coordinate lists).
        coordinates: Dict with 'lat' and 'lng' keys.

    Returns:
        Country key if found, else None.
    """
    point = [coordinates["lat"], coordinates["lng"]]

    for key, value in sector_manifest.items():
        for polygon in _polygons_of(value):
            if point_in_polygon(point, polygon):
                return key
    return None


def _load(name: str) -> Any:
    """Load a bundled data file (name without extension), preferring gz over json."""
    gz_path = _DATA_DIR / "gz" / (name + ".json.gz")
    if gz_path.exists():
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with (_DATA_DIR / "json" / (name + ".json")).open(encoding="utf-8") as f:
        return json.load(f)


def _stem(key: str) -> str:
    for suffix in (".json.gz", ".json"):
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def coordinates_to_country(coordinates: dict[str, float]) -> str | None:
    """
    Convert coordinates to an ISO3 country code using the bundled data.

    Args:
        coordinates: Dict with 'lat' and 'lng' keys.

    Returns:
        ISO3 country code if found, else None.
    """
    manifest = _load("world_sectors")
    lat = coordinates["lat"]
    lng = coordinates["lng"]
    # Sector bounds may overlap, so try every sector containing the point.
    for key, value in manifest.items():
        lat_min, lng_min, lat_max, lng_max = _bounds_of(value)
        if not (lat_min <= lat <= lat_max and lng_min <= lng <= lng_max):
            continue
        country = get_country(_load(_stem(key)), coordinates)
        if country:
            return country
    return None
