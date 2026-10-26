"""Simplify shared borders once, snap to the output grid and keep every code alive."""
from __future__ import annotations

import shapely

from .config import BuildConfig
from .geom import polygonal
from .load import Feature


def simplify_partition(parts: list[Feature], cfg: BuildConfig) -> list[Feature]:
    geoms = [geom for _, geom in parts]
    if cfg.tolerance > 0:
        geoms = list(shapely.coverage_simplify(geoms, cfg.tolerance))
    grid = 10.0 ** -cfg.decimals
    # The same grid for every geometry keeps shared vertices identical.
    snapped = [polygonal(shapely.set_precision(geom, grid)) for geom in geoms]
    return restore_lost(parts, [(code, geom) for (code, _), geom in zip(parts, snapped)], grid)


def restore_lost(original: list[Feature], simplified: list[Feature], grid: float,
                 keep: float = 0.5) -> list[Feature]:
    """Put back codes that simplification shrank below `keep` of their area.

    Microstates such as the Vatican are smaller than the tolerance and would
    otherwise vanish into their host; they come back unsimplified and are cut
    out of whatever now covers them.
    """
    result = list(simplified)
    for index, (code, geom) in enumerate(original):
        if result[index][1].area >= keep * geom.area:
            continue
        patch = polygonal(shapely.set_precision(geom, grid))
        if patch.is_empty:
            patch = geom  # smaller than one grid cell: ship it unsnapped
        for other, (other_code, other_geom) in enumerate(result):
            if other != index and other_geom.intersects(patch):
                result[other] = (other_code, polygonal(other_geom.difference(patch)))
        result[index] = (code, patch)
    return [(code, geom) for code, geom in result if not geom.is_empty]
