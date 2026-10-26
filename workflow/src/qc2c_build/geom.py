"""Polygon helpers shared by the build stages."""
from __future__ import annotations

import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import split

EMPTY = MultiPolygon()


def _polygons(geom: BaseGeometry) -> list[Polygon]:
    if geom.geom_type == "Polygon":
        return [] if geom.is_empty else [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for part in geom.geoms for p in _polygons(part)]
    return []


def polygonal(geom: BaseGeometry | None) -> BaseGeometry:
    """The polygon parts of a geometry, repaired; EMPTY when none remain."""
    if geom is None or geom.is_empty:
        return EMPTY
    if not geom.is_valid:
        geom = shapely.make_valid(geom)
    polygons = _polygons(geom)
    if not polygons:
        return EMPTY
    return polygons[0] if len(polygons) == 1 else shapely.union_all(polygons)


def hole_free(geom: BaseGeometry) -> list[Polygon]:
    """Cut polygons along vertical lines through their holes until no holes remain.

    Rings without holes make first-match lookup exact whatever order countries are
    listed in, because the shipped format keeps outer rings only.
    """
    done: list[Polygon] = []
    stack = _polygons(geom)
    while stack:
        polygon = stack.pop()
        if not polygon.interiors:
            done.append(polygon)
            continue
        # A point strictly inside the hole, so the cut always crosses it.
        x = Polygon(polygon.interiors[0]).representative_point().x
        _, min_y, _, max_y = polygon.bounds
        stack.extend(_polygons(split(polygon, LineString([(x, min_y - 1), (x, max_y + 1)]))))
    return done
