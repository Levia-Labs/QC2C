# Task 2: Geometry helpers and source loading

**Files:**

- Create: `workflow/src/qc2c_build/geom.py`, `workflow/src/qc2c_build/load.py`, `workflow/data/input/code_overrides.json`, `workflow/tests/test_load.py`, `workflow/tests/test_geom.py`

**Interfaces:**

- Consumes: `BuildConfig`, `ConfigError` (Task 1).
- Produces: `geom.EMPTY`, `geom.polygonal(geom) -> BaseGeometry` (Polygon or MultiPolygon or empty), `geom.hole_free(geom) -> list[Polygon]`; `load.Feature = tuple[str, BaseGeometry]`, `load.MissingOverride(ConfigError)`, `load.US_TERRITORIES: dict[str, str]`, `load.read_json(path) -> dict`, `load.resolve_code(properties, overrides) -> str`, `load.load_features(cfg) -> list[Feature]` (sorted by code, non-overlapping).

- [ ] **Step 1: Write the failing tests `workflow/tests/test_geom.py`**

```python
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import LineString, Polygon, box

from qc2c_build.geom import hole_free, polygonal


def test_polygonal_drops_lines_and_repairs():
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
    fixed = polygonal(bowtie)
    assert fixed.is_valid and fixed.area > 0
    assert polygonal(LineString([(0, 0), (1, 1)])).is_empty


def test_hole_free_cuts_every_hole():
    host = box(0, 0, 10, 10).difference(box(2, 2, 3, 3)).difference(box(6, 6, 8, 7))
    pieces = hole_free(host)
    assert all(not p.interiors for p in pieces)
    assert abs(sum(p.area for p in pieces) - host.area) < 1e-9


@given(st.floats(0.5, 4), st.floats(0.5, 4))
def test_hole_free_preserves_area(x, y):
    host = box(0, 0, 10, 10).difference(box(x, y, x + 1, y + 1))
    assert abs(sum(p.area for p in hole_free(host)) - host.area) < 1e-9
```

- [ ] **Step 2: Write the failing tests `workflow/tests/test_load.py`**

```python
from dataclasses import replace

import pytest
from conftest import WORLD_FEATURES, feature, square, write_inputs

from qc2c_build.load import MissingOverride, load_features


def codes(cfg):
    return [code for code, _ in load_features(cfg)]


def test_override_replaces_no_code(world):
    assert "NWH" in codes(world)
    assert "-99" not in codes(world)


def test_missing_override_names_feature(world):
    write_inputs(world.input_dir, WORLD_FEATURES, overrides={})
    with pytest.raises(MissingOverride, match="Nowhere"):
        load_features(world)


def test_usa_or_states(world):
    countries = [
        feature("USA", "United States", [square(-100, 30, -80, 40)]),
        feature("PRI", "Puerto Rico", [square(-67, 18, -65, 19)]),
    ]
    states = [
        feature("NY", "New York", [square(-80, 35, -75, 40)]),
        feature("PR", "Puerto Rico", [square(-67, 18, -65, 19)]),
    ]
    write_inputs(world.input_dir, countries, states=states)
    assert codes(world) == ["PRI", "USA"]
    assert codes(replace(world, us_states=True)) == ["NY", "PRI"]


def test_same_code_dissolves(world):
    write_inputs(
        world.input_dir,
        [feature("AAA", "A1", [square(0, 0, 1, 1)]), feature("AAA", "A2", [square(5, 5, 6, 6)])],
    )
    [(code, geom)] = load_features(world)
    assert code == "AAA" and abs(geom.area - 2) < 1e-9


def test_overlaps_removed(world):
    write_inputs(
        world.input_dir,
        [feature("AAA", "A", [square(0, 0, 2, 2)]), feature("BBB", "B", [square(1, 1, 3, 3)])],
    )
    (_, a), (_, b) = load_features(world)
    assert a.intersection(b).area < 1e-12
    assert abs(a.area + b.area - 7) < 1e-9


def test_invalid_geometry_is_repaired(world):
    bowtie = [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]
    write_inputs(world.input_dir, [feature("BOW", "Bowtie", bowtie)])
    [(_, geom)] = load_features(world)
    assert geom.is_valid and geom.area > 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_geom.py workflow/tests/test_load.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.geom'`

- [ ] **Step 4: Implement `workflow/src/qc2c_build/geom.py`**

```python
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
```

- [ ] **Step 5: Implement `workflow/src/qc2c_build/load.py`**

```python
"""Read source borders, apply code overrides and dissolve features that share a code."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .config import BuildConfig, ConfigError
from .geom import polygonal

NO_CODE = "-99"
# State-file entries that duplicate an ISO country entry in countries.json.
US_TERRITORIES = {"PR": "PRI", "VI": "VIR", "GU": "GUM", "AS": "ASM", "MP": "MNP"}

Feature = tuple[str, BaseGeometry]


class MissingOverride(ConfigError):
    """A source feature has no ISO code and no entry in the override file."""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_code(properties: dict, overrides: dict[str, str]) -> str:
    name = properties.get("ADMIN", "")
    if name in overrides:
        return overrides[name]
    code = properties.get("ISO_A3", NO_CODE)
    if code == NO_CODE:
        raise MissingOverride(f"no ISO code and no override for {name!r}")
    return code


def load_features(cfg: BuildConfig) -> list[Feature]:
    overrides = read_json(cfg.input_file(cfg.overrides))
    grouped: dict[str, list[BaseGeometry]] = defaultdict(list)
    for item in read_json(cfg.input_file("countries.json"))["features"]:
        code = resolve_code(item["properties"], overrides)
        if cfg.us_states and code == "USA":
            continue
        grouped[code].append(polygonal(shape(item["geometry"])))
    if cfg.us_states:
        for item in read_json(cfg.input_file("us_states.json"))["features"]:
            code = item["properties"]["ISO_A3"]
            if code not in US_TERRITORIES:
                grouped[code].append(polygonal(shape(item["geometry"])))
    features = [(code, polygonal(shapely.union_all(grouped[code]))) for code in sorted(grouped)]
    return _remove_overlaps([(code, geom) for code, geom in features if not geom.is_empty])


def _remove_overlaps(features: list[Feature]) -> list[Feature]:
    """Later codes give up area an earlier code already holds, so the result is a coverage."""
    tree = shapely.STRtree([geom for _, geom in features])
    result: list[Feature] = []
    for index, (code, geom) in enumerate(features):
        for earlier in tree.query(geom, predicate="intersects"):
            if earlier < index:
                geom = polygonal(geom.difference(result[earlier][1]))
        result.append((code, geom))
    return [(code, geom) for code, geom in result if not geom.is_empty]
```

Note: `result[earlier]` stays index-aligned with `features` because empty geometries are filtered only at the end.

- [ ] **Step 6: Write `workflow/data/input/code_overrides.json`**

```json
{
  "Ashmore and Cartier Islands": "AUS",
  "Coral Sea Islands": "AUS",
  "Indian Ocean Territories": "AUS",
  "Clipperton Island": "FRA",
  "Dhekelia Sovereign Base Area": "GBR",
  "Akrotiri Sovereign Base Area": "GBR",
  "Baykonur Cosmodrome": "KAZ",
  "US Naval Base Guantanamo Bay": "CUB",
  "Kosovo": "XKX",
  "Northern Cyprus": "CYN",
  "Cyprus No Mans Area": "CNM",
  "Somaliland": "SOL",
  "Siachen Glacier": "KAS",
  "Spratly Islands": "PGA",
  "Scarborough Reef": "SCR",
  "Bajo Nuevo Bank (Petrel Is.)": "BJN",
  "Serranilla Bank": "SER"
}
```

- [ ] **Step 7: Run tests**

Run: `uv run --project workflow pytest workflow/tests/test_geom.py workflow/tests/test_load.py`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
task git:commit -- "feat(workflow): load source borders with code overrides"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
