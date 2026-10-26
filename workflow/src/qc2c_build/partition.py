"""Give sea to the nearest country, so the output covers the whole plane."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import MultiPoint, box
from shapely.geometry.base import BaseGeometry

from .config import BuildConfig
from .geom import make_coverage, polygonal
from .load import Feature

WORLD = box(-180, -90, 180, 90)
KM_PER_DEGREE = 111.32  # at the equator; distance mode is approximate by design
SNAP = 1e-3  # Voronoi snapping tolerance in degrees; the validation band includes it


def presimplified(features: list[Feature], tolerance: float) -> list[Feature]:
    geoms = [geom for _, geom in features]
    if tolerance > 0:
        geoms = list(shapely.coverage_simplify(geoms, tolerance))
    return [(code, polygonal(geom)) for (code, _), geom in zip(features, geoms)]


def nearest_owner_cells(land: list[BaseGeometry], spacing: float) -> dict[int, list[BaseGeometry]]:
    """Voronoi cells of densified boundary points, grouped by the land index owning each point."""
    coords, owners = [], []
    for index, geom in enumerate(land):
        points = shapely.get_coordinates(shapely.segmentize(geom.boundary, spacing))
        coords.append(points)
        owners.append(np.full(len(points), index))
    xy, first = np.unique(np.round(np.vstack(coords), 4), axis=0, return_index=True)
    owner = np.concatenate(owners)[first]
    cells = shapely.get_parts(shapely.voronoi_polygons(MultiPoint(xy), extend_to=WORLD, tolerance=SNAP))
    # A point inside a cell is nearest to that cell's generator, which survives snapping.
    nearest = shapely.STRtree(shapely.points(xy)).query_nearest(shapely.point_on_surface(cells))
    grouped: dict[int, list[BaseGeometry]] = defaultdict(list)
    for cell_index, point_index in zip(*nearest):
        grouped[int(owner[point_index])].append(cells[cell_index])
    return grouped


def build_partition(features: list[Feature], cfg: BuildConfig) -> list[Feature]:
    land = presimplified(features, cfg.presimplify)
    land_union = shapely.union_all([geom for _, geom in land])
    sea = WORLD.difference(land_union)
    if cfg.sea == "distance":
        sea = sea.intersection(land_union.buffer(cfg.sea_distance_km / KM_PER_DEGREE))
    cells = nearest_owner_cells([geom for _, geom in land], cfg.voronoi_spacing)
    result = []
    for index, (code, geom) in enumerate(land):
        owned_sea = shapely.intersection(shapely.union_all(cells.get(index, [])), sea)
        result.append((code, polygonal(shapely.union(geom, owned_sea))))
    return make_coverage(result)
