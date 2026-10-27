# Task 3: Sea partition

**Files:**
- Create: `workflow/src/qc2c_build/partition.py`, `workflow/tests/test_partition.py`

**Interfaces:**
- Consumes: `Feature`, `load_features` (Task 2), `polygonal` (Task 2), `BuildConfig` (Task 1).
- Produces: `partition.WORLD` (box -180..180, -90..90), `partition.SNAP = 1e-3`, `partition.KM_PER_DEGREE = 111.32`, `partition.presimplified(features, tolerance) -> list[Feature]`, `partition.build_partition(features, cfg) -> list[Feature]` (same order and codes as input).

- [ ] **Step 1: Write the failing tests `workflow/tests/test_partition.py`**

```python
from dataclasses import replace

from conftest import feature, square, write_inputs
from shapely.geometry import Point

from qc2c_build.load import load_features
from qc2c_build.partition import WORLD, build_partition


def code_at(parts, lng, lat):
    point = Point(lng, lat)
    hits = [code for code, geom in parts if geom.covers(point)]
    return hits[0] if hits else None


def test_nearest_covers_world_without_overlap(world):
    parts = build_partition(load_features(world), world)
    assert abs(sum(g.area for _, g in parts) - WORLD.area) < 1e-6 * WORLD.area
    assert code_at(parts, -150, -60) is not None


def test_land_keeps_its_code(world):
    parts = build_partition(load_features(world), world)
    assert code_at(parts, -30, 30) == "ENC"
    assert code_at(parts, -38, 38) == "HST"
    assert code_at(parts, 5, 25) == "WST"
    assert code_at(parts, 15, 25) == "EST"


def test_strait_goes_to_nearest(world):
    parts = build_partition(load_features(world), world)
    assert code_at(parts, 20.4, 23) == "ISL"
    assert code_at(parts, 20.1, 21) == "EST"


def test_distance_mode_leaves_open_sea_empty(world):
    cfg = replace(world, sea="distance", sea_distance_km=111.32)
    parts = build_partition(load_features(cfg), cfg)
    assert code_at(parts, 5, 30.5) == "WST"
    assert code_at(parts, 5, 35) is None


def test_antimeridian_halves_survive(world):
    write_inputs(world.input_dir, [feature("RUS", "Russia", [square(175, 60, 180, 65)], [square(-180, 60, -175, 65)])])
    parts = build_partition(load_features(world), world)
    assert code_at(parts, 178, 62) == "RUS"
    assert code_at(parts, -178, 62) == "RUS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_partition.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.partition'`

- [ ] **Step 3: Implement `workflow/src/qc2c_build/partition.py`**

```python
"""Give sea to the nearest country, so the output covers the whole plane."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import MultiPoint, box
from shapely.geometry.base import BaseGeometry

from .config import BuildConfig
from .geom import polygonal
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
    return result
```

- [ ] **Step 4: Run tests**

Run: `uv run --project workflow pytest workflow/tests/test_partition.py`
Expected: all PASS. If `query_nearest` returns a single array for a geometry array input in the installed shapely, it returns shape `(2, n)`; `zip(*nearest)` handles that shape.

- [ ] **Step 5: Commit**

```bash
task git:commit -- "feat(workflow): assign sea to the nearest country"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
