"""Simplify shared borders once, snap to the output grid and keep every code alive."""
from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry

from .config import BuildConfig
from .geom import EMPTY, make_coverage, polygonal
from .load import Feature


def simplify_partition(parts: list[Feature], land: list[Feature], cfg: BuildConfig) -> list[Feature]:
    """Simplify the partition `parts`; `land` is the source land per code, used to restore lost land."""
    geoms = [geom for _, geom in parts]
    if cfg.tolerance > 0:
        geoms = list(shapely.coverage_simplify(geoms, cfg.tolerance))
    grid = 10.0 ** -cfg.decimals
    # The same grid for every geometry keeps shared vertices identical.
    snapped = [polygonal(shapely.set_precision(geom, grid)) for geom in geoms]
    return restore_lost(land, [(code, geom) for (code, _), geom in zip(parts, snapped)], grid)


def overlap_area(a: BaseGeometry, b: BaseGeometry) -> float:
    """Exact intersection area. Overlay results inherit the fixed precision of
    geometries from set_precision, which would round the overlap onto the grid;
    grid size 0 drops that precision model first."""
    return shapely.intersection(shapely.set_precision(a, 0), shapely.set_precision(b, 0)).area


def snapped_land(geom: BaseGeometry, grid: float, keep: float) -> BaseGeometry:
    """`geom` on the grid. Snapping a land smaller than a few cells can drop most of it,
    so then every grid cell that touches the land is used instead."""
    patch = polygonal(shapely.set_precision(geom, grid))
    if overlap_area(patch, geom) >= keep * geom.area:
        return patch
    min_x, min_y, max_x, max_y = geom.bounds
    xs = np.arange(math.floor(min_x / grid), math.ceil(max_x / grid)) * grid
    ys = np.arange(math.floor(min_y / grid), math.ceil(max_y / grid)) * grid
    if len(xs) * len(ys) > 10_000:
        return patch  # not a microstate; the snapped land is what there is
    cells = shapely.box(*np.meshgrid(xs, ys), *np.meshgrid(xs + grid, ys + grid))
    touching = shapely.intersects(cells, geom).ravel()
    cover = polygonal(shapely.set_precision(shapely.union_all(cells.ravel()[touching]), grid))
    return cover if not cover.is_empty else geom


def restore_lost(land: list[Feature], simplified: list[Feature], grid: float,
                 keep: float = 0.9) -> list[Feature]:
    """Put back the land of codes that simplification shrank below `keep` of their source land.

    The criterion is land, not partition area: a microstate such as the Vatican
    is smaller than the tolerance and its host can swallow all of its land while
    the sea it owns survives. The land comes back unsimplified (on the grid), is
    added to the code and cut out of whatever now covers it. Neighbours of a
    restored code may carry off-grid nodes from re-noding, which the writer rounds.
    """
    result = list(simplified)
    index_of = {code: index for index, (code, _) in enumerate(result)}
    restored = False
    for code, geom in land:
        if geom.is_empty:
            continue
        index = index_of.get(code)
        current = result[index][1] if index is not None else EMPTY
        if overlap_area(current, geom) >= keep * geom.area:
            continue
        patch = snapped_land(geom, grid, keep)
        for other, (other_code, other_geom) in enumerate(result):
            if other_code != code and other_geom.intersects(patch):
                result[other] = (other_code, polygonal(
                    shapely.set_precision(other_geom.difference(patch), grid)))
        merged = polygonal(shapely.union(current, patch))
        if index is None:
            index_of[code] = len(result)
            result.append((code, merged))
        else:
            result[index] = (code, merged)
        restored = True
    kept = [(code, geom) for code, geom in result if not geom.is_empty]
    # Cutting snapped neighbours leaves slivers; re-noding keeps the coverage valid.
    return make_coverage(kept) if restored else kept
