# Task 4: Simplification and microstate restore

**Files:**
- Create: `workflow/src/qc2c_build/simplify.py`, `workflow/tests/test_simplify.py`

**Interfaces:**
- Consumes: `Feature`, `polygonal`, `build_partition`, `BuildConfig`.
- Produces: `simplify.simplify_partition(parts, cfg) -> list[Feature]`, `simplify.restore_lost(original, simplified, grid, keep=0.5) -> list[Feature]`.

- [ ] **Step 1: Write the failing tests `workflow/tests/test_simplify.py`**

```python
from shapely.geometry import box

from qc2c_build.geom import EMPTY
from qc2c_build.load import load_features
from qc2c_build.partition import build_partition
from qc2c_build.simplify import restore_lost, simplify_partition


def test_coordinates_on_grid_and_no_overlap(world):
    parts = simplify_partition(build_partition(load_features(world), world), world)
    for _, geom in parts:
        for x, y in geom.exterior.coords if geom.geom_type == "Polygon" else []:
            assert abs(round(x * 1000) - x * 1000) < 1e-6
            assert abs(round(y * 1000) - y * 1000) < 1e-6
    total = sum(g.area for _, g in parts)
    assert abs(total - 360 * 180) < 1e-3


def test_restore_lost_puts_tiny_code_back():
    big = box(0, 0, 10, 10).difference(box(5, 5, 5.004, 5.004))
    tiny = box(5, 5, 5.004, 5.004)
    original = [("BIG", big), ("TNY", tiny)]
    simplified = [("BIG", box(0, 0, 10, 10)), ("TNY", EMPTY)]
    restored = dict(restore_lost(original, simplified, grid=0.001))
    assert abs(restored["TNY"].area - tiny.area) < 1e-9
    assert restored["BIG"].intersection(restored["TNY"]).area < 1e-12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_simplify.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.simplify'`

- [ ] **Step 3: Implement `workflow/src/qc2c_build/simplify.py`**

```python
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
    grid = 10.0**-cfg.decimals
    # The same grid for every geometry keeps shared vertices identical.
    snapped = [polygonal(shapely.set_precision(geom, grid)) for geom in geoms]
    return restore_lost(parts, [(code, geom) for (code, _), geom in zip(parts, snapped)], grid)


def restore_lost(
    original: list[Feature], simplified: list[Feature], grid: float, keep: float = 0.5
) -> list[Feature]:
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
```

- [ ] **Step 4: Run tests**

Run: `uv run --project workflow pytest workflow/tests/test_simplify.py`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
task git:commit -- "feat(workflow): simplify shared borders and restore microstates"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
