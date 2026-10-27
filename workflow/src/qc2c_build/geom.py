"""Polygon helpers shared by the build stages."""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import split

from .config import ConfigError

EMPTY = MultiPolygon()
EDGE_TOLERANCE = 1e-6  # how far past the world edge a source vertex may drift and still be pulled back


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


def clamp_to_world(geom: BaseGeometry) -> BaseGeometry:
    """Pull coordinates within EDGE_TOLERANCE of the world edge onto lng [-180, 180], lat [-90, 90].

    Source borders carry vertices such as 180.0000000000002 on the antimeridian;
    they fall outside every sector box and would match no ring. Coordinates
    farther out are bad data, not drift, and raise ConfigError.
    """
    low = np.array((-180.0, -90.0))
    high = np.array((180.0, 90.0))

    def clamp(xy: np.ndarray) -> np.ndarray:
        bad = (xy < low - EDGE_TOLERANCE) | (xy > high + EDGE_TOLERANCE)
        if bad.any():
            x, y = xy[np.argmax(bad.any(axis=1))]
            raise ConfigError(f"coordinate ({x}, {y}) lies outside the world [-180, 180] x [-90, 90]")
        return np.clip(xy, low, high)

    return polygonal(shapely.transform(geom, clamp))


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


def make_coverage(features: list[tuple[str, BaseGeometry]]) -> list[tuple[str, BaseGeometry]]:
    """Re-cut features into a valid coverage: no overlaps and node-identical shared edges.

    coverage_simplify needs neighbours to share the same vertices along a border;
    source data has near-coincident but unnoded edges. All boundaries are noded
    together, faces are polygonized, and each face goes to the first feature
    (input order) that contains it. Unowned faces are dropped.
    """
    geoms = [geom for _, geom in features]
    if not geoms:
        return []
    noded = shapely.union_all(shapely.boundary(geoms))
    faces = shapely.get_parts(shapely.polygonize([noded]))
    tree = shapely.STRtree(geoms)
    points = shapely.point_on_surface(faces)
    # query order is arbitrary, so pick the lowest owner per face
    best: dict[int, int] = {}
    for point_index, geom_index in zip(*tree.query(points, predicate="within")):
        best[int(point_index)] = min(best.get(int(point_index), int(geom_index)), int(geom_index))
    owned: dict[int, list[BaseGeometry]] = {}
    for point_index, geom_index in best.items():
        owned.setdefault(geom_index, []).append(faces[point_index])
    result = []
    for index, (code, _) in enumerate(features):
        if index in owned:
            merged = polygonal(shapely.union_all(owned[index]))
            if not merged.is_empty:
                result.append((code, merged))
    kept = {code for code, _ in result}
    vanished = sorted({code for code, _ in features} - kept)
    if vanished:
        raise ConfigError(f"no area left after removing overlaps for: {', '.join(vanished)}")
    return result
