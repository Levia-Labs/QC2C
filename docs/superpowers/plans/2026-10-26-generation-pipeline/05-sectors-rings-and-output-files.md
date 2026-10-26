# Task 5: Sectors, rings and output files

**Files:**
- Create: `workflow/src/qc2c_build/sectors.py`, `workflow/src/qc2c_build/write.py`, `workflow/src/qc2c_build/pipeline.py`, `workflow/tests/test_sectors.py`, `workflow/tests/test_pipeline.py`

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: `sectors.Sectors = dict[str, list[float]]`, `sectors.read_sectors(path) -> Sectors` (raises `ConfigError`), `sectors.check_tiling(sectors)`, `sectors.sector_box(bounds) -> Polygon`, `sectors.ring_coords(polygon, decimals) -> list[list[float]]`, `sectors.split_into_sectors(parts, land, sectors, decimals) -> tuple[dict[str, dict[str, list]], dict[str, dict]]`; `write.dump(data) -> bytes`, `write.write_build(cfg, files, manifest, meta) -> dict`; `pipeline.run_build(cfg) -> dict` (the `build.json` content).

- [ ] **Step 1: Write the failing tests `workflow/tests/test_sectors.py`**

```python
import pytest
from conftest import TWO_SECTORS
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import Polygon, box

from qc2c_build.config import ConfigError
from qc2c_build.sectors import check_tiling, ring_coords, sector_box, split_into_sectors


def test_tiling_ok():
    check_tiling(TWO_SECTORS)


def test_tiling_overlap_and_gap():
    with pytest.raises(ConfigError, match="overlap"):
        check_tiling({"a.json": [-90, -180, 90, 180], "b.json": [0, 0, 10, 10]})
    with pytest.raises(ConfigError, match="gaps"):
        check_tiling({"a.json": [0, -180, 90, 180]})


def test_ring_coords_order_and_dedup():
    polygon = Polygon([(1.00001, 2.0), (1.00002, 2.0), (3.0, 2.0), (3.0, 4.0)])
    assert ring_coords(polygon, 3) == [[2.0, 1.0], [2.0, 3.0], [4.0, 3.0]]
    assert ring_coords(Polygon([(0, 0), (0.0001, 0), (0, 0.0001)]), 3) == []


@given(st.floats(-180, 180), st.floats(-90, 90), st.integers(0, 6))
def test_rounding_moves_at_most_half_a_unit(x, y, decimals):
    polygon = Polygon([(x, y), (x + 1, y), (x + 1, y + 1)])
    ring = ring_coords(polygon, decimals)
    half = 0.5 * 10.0 ** -decimals + 1e-9
    if ring:
        assert abs(ring[0][0] - y) <= half and abs(ring[0][1] - x) <= half


@given(st.floats(-170, 160), st.floats(-80, 70), st.floats(0.1, 10), st.floats(0.1, 10))
def test_clipping_preserves_area(x, y, w, h):
    shape = box(x, y, x + w, y + h)
    total = sum(shape.intersection(sector_box(b)).area for b in TWO_SECTORS.values())
    assert abs(total - shape.area) < 1e-9


def test_split_spans_sectors_and_cuts_holes():
    host = box(-40, 20, -20, 40).difference(box(-32, 28, -28, 32))
    parts = [("ENC", box(-32, 28, -28, 32)), ("HST", host), ("SPN", box(40, -10, 50, 10))]
    files, manifest = split_into_sectors(parts, parts, TWO_SECTORS, 3)
    assert "SPN" in files["world_sector_1.json"] and "SPN" in files["world_sector_2.json"]
    assert list(files["world_sector_1.json"])[0] == "ENC"
    assert all(len(ring) >= 3 for ring in files["world_sector_1.json"]["HST"])
    assert manifest["world_sector_1.json.gz"]["bounds"] == [0, -180, 90, 180]
    assert manifest["world_sector_1.json.gz"]["center"]["ENC"] == [30.0, -30.0]
```

The enclave center `[30.0, -30.0]` holds because `representative_point` of a square returns its center.

- [ ] **Step 2: Write the failing tests `workflow/tests/test_pipeline.py`**

```python
import gzip
import json

from qc2c_build.pipeline import run_build


def test_build_writes_files(world):
    meta = run_build(world)
    names = sorted(p.name for p in world.build_dir.iterdir())
    assert names == ["build.json", "world_sector_1.json", "world_sector_1.json.gz", "world_sector_2.json",
                     "world_sector_2.json.gz", "world_sectors.json", "world_sectors.json.gz"]
    manifest = json.loads(gzip.decompress((world.build_dir / "world_sectors.json.gz").read_bytes()))
    assert list(manifest) == ["world_sector_1.json.gz", "world_sector_2.json.gz"]
    assert meta["codes"] == 7 and meta["gzip_total"] > 0


def test_build_is_deterministic(world):
    run_build(world)
    first = {p.name: p.read_bytes() for p in world.build_dir.glob("world_sector*")}
    run_build(world)
    second = {p.name: p.read_bytes() for p in world.build_dir.glob("world_sector*")}
    assert first == second
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_sectors.py workflow/tests/test_pipeline.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.sectors'`

- [ ] **Step 4: Implement `workflow/src/qc2c_build/sectors.py`**

```python
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
```

- [ ] **Step 5: Implement `workflow/src/qc2c_build/write.py`**

```python
"""Write sector files and the manifest as JSON and gzip, plus build.json."""
from __future__ import annotations

import gzip
import json

from .config import BuildConfig


def dump(data: object) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def write_build(cfg: BuildConfig, files: dict[str, dict], manifest: dict[str, dict], meta: dict) -> dict:
    out = cfg.build_dir
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("world_sector*"):
        old.unlink()
    sizes: dict[str, int] = {}
    for name, data in [*files.items(), ("world_sectors.json", manifest)]:
        raw = dump(data)
        packed = gzip.compress(raw, compresslevel=9, mtime=0)  # mtime=0 keeps builds byte-identical
        (out / name).write_bytes(raw)
        (out / f"{name}.gz").write_bytes(packed)
        sizes[name], sizes[f"{name}.gz"] = len(raw), len(packed)
    meta = {**meta, "sizes": sizes, "gzip_total": sum(v for k, v in sizes.items() if k.endswith(".gz"))}
    (out / "build.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta
```

- [ ] **Step 6: Implement `workflow/src/qc2c_build/pipeline.py`**

```python
"""Run the build stages in order and record what was built."""
from __future__ import annotations

import hashlib
import sys
import time

import numpy
import shapely

from .config import BuildConfig
from .load import load_features
from .partition import build_partition
from .sectors import read_sectors, split_into_sectors
from .simplify import simplify_partition
from .write import write_build


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run_build(cfg: BuildConfig) -> dict:
    timings: dict[str, float] = {}
    start = time.perf_counter()

    def mark(stage: str) -> None:
        timings[stage] = round(time.perf_counter() - start - sum(timings.values()), 2)
        _log(f"{stage}: {timings[stage]}s")

    sectors = read_sectors(cfg.input_file(cfg.sectors))
    features = load_features(cfg)
    mark("load")
    parts = build_partition(features, cfg)
    mark("partition")
    simplified = simplify_partition(parts, cfg)
    mark("simplify")
    files, manifest = split_into_sectors(simplified, features, sectors, cfg.decimals)
    mark("sectors")
    inputs = ["countries.json", cfg.overrides, cfg.sectors] + (["us_states.json"] if cfg.us_states else [])
    meta = {
        "settings": cfg.as_dict(),
        "inputs": {name: _sha256(cfg.input_file(name)) for name in inputs},
        "versions": {"shapely": shapely.__version__, "geos": shapely.geos_version_string, "numpy": numpy.__version__},
        "codes": len({code for sector in files.values() for code in sector}),
        "points": sum(len(ring) for sector in files.values() for rings in sector.values() for ring in rings),
        "seconds": timings,
    }
    return write_build(cfg, files, manifest, meta)
```

- [ ] **Step 7: Run tests**

Run: `uv run --project workflow pytest workflow/tests`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
task git:commit -- "feat(workflow): split partition into sector files"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
