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
    return result
