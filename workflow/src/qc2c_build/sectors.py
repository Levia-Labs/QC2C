"""Clip the partition to sector boxes and turn it into the shipped JSON shape."""
from __future__ import annotations

import json
from pathlib import Path

import shapely
from shapely.geometry import Polygon, box

from .config import ConfigError
from .geom import hole_free, polygonal
from .load import Feature

Sectors = dict[str, list[float]]  # file name -> [lat_min, lng_min, lat_max, lng_max]
WORLD_AREA = 360.0 * 180.0


def sector_box(bounds: list[float]) -> Polygon:
    lat_min, lng_min, lat_max, lng_max = bounds
    return box(lng_min, lat_min, lng_max, lat_max)


def read_sectors(path: Path) -> Sectors:
    data = json.loads(path.read_text(encoding="utf-8"))
    for name, bounds in data.items():
        if not name.endswith(".json") or len(bounds) != 4 or not all(isinstance(v, int | float) for v in bounds):
            raise ConfigError(f"bad sector entry {name!r}: {bounds!r}")
    check_tiling(data)
    return data


def check_tiling(sectors: Sectors) -> None:
    boxes = [sector_box(bounds) for bounds in sectors.values()]
    if any(b.area <= 0 for b in boxes):
        raise ConfigError("a sector box has no area")
    union = shapely.union_all(boxes).intersection(box(-180, -90, 180, 90))
    if sum(b.area for b in boxes) > union.area + 1e-9:
        raise ConfigError("sector boxes overlap")
    if union.area < WORLD_AREA - 1e-9:
        raise ConfigError("sector boxes leave gaps in the world")


def ring_coords(polygon: Polygon, decimals: int) -> list[list[float]]:
    """Outer ring as [lat, lng] pairs on the output grid, open, without repeats; [] if degenerate."""
    ring: list[list[float]] = []
    for x, y in polygon.exterior.coords[:-1]:
        point = [round(y, decimals) + 0.0, round(x, decimals) + 0.0]  # + 0.0 turns -0.0 into 0.0
        if not ring or ring[-1] != point:
            ring.append(point)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    return ring if len(ring) >= 3 else []


def _center(land: dict, code: str, clipped, area: Polygon, decimals: int) -> list[float]:
    inside = polygonal(shapely.intersection(land[code], area)) if code in land else clipped
    point = (inside if not inside.is_empty else clipped).representative_point()
    return [round(point.y, decimals) + 0.0, round(point.x, decimals) + 0.0]


def split_into_sectors(parts: list[Feature], land: list[Feature], sectors: Sectors,
                       decimals: int) -> tuple[dict[str, dict[str, list]], dict[str, dict]]:
    land_by_code = dict(land)
    tree = shapely.STRtree([geom for _, geom in parts])
    files: dict[str, dict[str, list]] = {}
    manifest: dict[str, dict] = {}
    for name, bounds in sectors.items():
        area = sector_box(bounds)
        entries = []
        for index in tree.query(area, predicate="intersects"):
            code, geom = parts[index]
            clipped = polygonal(shapely.intersection(geom, area))
            pieces = hole_free(clipped)
            rings = [ring for ring in (ring_coords(p, decimals) for p in pieces) if ring]
            if rings:
                entries.append((sum(Polygon(p.exterior).area for p in pieces), code, rings, clipped))
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        files[name] = {code: rings for _, code, rings, _ in entries}
        centers = {code: _center(land_by_code, code, clipped, area, decimals) for _, code, _, clipped in entries}
        manifest[f"{name}.gz"] = {"bounds": bounds, "center": dict(sorted(centers.items()))}
    return files, manifest
