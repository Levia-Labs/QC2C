# Task 6: Validation of output

**Files:**
- Create: `workflow/src/qc2c_build/validate.py`, `workflow/tests/test_validate.py`

**Interfaces:**
- Consumes: `load_features`, `read_sectors`, `sector_box`, `SNAP`, `run_build`, `BuildConfig`.
- Produces: `validate.ValidationError(Exception)`, `validate.band(cfg) -> float`, `validate.PointSet(xy: np.ndarray, code: np.ndarray)`, `validate.source_points(features, samples, seed) -> PointSet`, `validate.classify(points, features, width) -> np.ndarray` (int8: 0 core, 1 border, 2 ambiguous), `validate.load_output(build_dir) -> tuple[dict, dict[str, dict]]`, `validate.lookup(manifest, sector_files, xy) -> np.ndarray`, `validate.fixture(points, kind, sectors, seed, size=500) -> list[dict]`, `validate.run_validation(cfg) -> dict`. Writes `validation.json` and `points.json` into `cfg.build_dir`.

- [ ] **Step 1: Write the failing tests `workflow/tests/test_validate.py`**

```python
import json
from dataclasses import replace

import numpy as np

from qc2c_build.load import load_features
from qc2c_build.pipeline import run_build
from qc2c_build.sectors import read_sectors
from qc2c_build.validate import PointSet, classify, fixture, run_validation, source_points


def test_classify_border_core_ambiguous(world):
    features = load_features(world)
    points = PointSet(np.array([[10.0, 25.0], [9.9, 25.0], [5.0, 25.0]]), np.array(["WST", "WST", "WST"], dtype=object))
    assert classify(points, features, 0.5).tolist() == [2, 1, 0]


def test_every_code_gets_interior_samples(world):
    features = load_features(world)
    points = source_points(features, 10, 1)
    assert set(points.code) == {code for code, _ in features}


def test_validation_passes_on_synthetic_world(world):
    run_build(world)
    report = run_validation(world)
    assert report["passed"], report["failures"]
    assert report["counts"]["core"] > 0
    assert report["accuracy"]["core"] == 1.0
    saved = json.loads((world.build_dir / "validation.json").read_text(encoding="utf-8"))
    assert saved["passed"] is True
    points = json.loads((world.build_dir / "points.json").read_text(encoding="utf-8"))
    assert {"lat", "lng", "code"} <= set(points[0])


def test_missing_sector_file_fails(world):
    run_build(world)
    (world.build_dir / "world_sector_2.json.gz").unlink()
    report = run_validation(world)
    assert not report["passed"]
    assert any("world_sector_2.json.gz" in f for f in report["failures"])


def test_border_threshold_enforced(world):
    cfg = replace(world, tolerance=3.0, min_border_accuracy=1.0)
    run_build(cfg)
    report = run_validation(cfg)
    assert report["accuracy"]["core"] == 1.0
    if report["accuracy"]["border"] < 1.0:
        assert any("border" in f for f in report["failures"])


def test_fixture_avoids_sector_edges(world):
    features = load_features(world)
    sectors = read_sectors(world.input_file(world.sectors))
    xy = np.array([[45.0, 0.0], [45.0, 5.0], [5.0, 25.0]])
    points = PointSet(xy, np.array(["SPN", "SPN", "WST"], dtype=object))
    kind = classify(points, features, 0.5)
    chosen = fixture(points, kind, sectors, 1)
    assert all(p["lat"] != 0.0 for p in chosen)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_validate.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.validate'`

- [ ] **Step 3: Implement `workflow/src/qc2c_build/validate.py`**

```python
"""Check a build against the source borders; write validation.json and the library fixture."""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon

from .config import BuildConfig
from .geom import polygonal
from .load import Feature, load_features
from .partition import SNAP
from .sectors import Sectors, read_sectors

CORE, BORDER, AMBIGUOUS = 0, 1, 2


class ValidationError(Exception):
    """The build output is missing or unreadable."""


@dataclass
class PointSet:
    xy: np.ndarray  # (n, 2) as lng, lat
    code: np.ndarray  # (n,) source code per point, dtype object


def band(cfg: BuildConfig) -> float:
    step = cfg.presimplify + cfg.tolerance + 10.0 ** -cfg.decimals + SNAP
    return 2 * step + cfg.voronoi_spacing / 2


def _interior(geom, count: int, rng: np.random.Generator) -> np.ndarray:
    shapely.prepare(geom)
    min_x, min_y, max_x, max_y = geom.bounds
    found = [np.array(geom.representative_point().coords)]
    need = count
    for _ in range(50):
        candidates = rng.uniform((min_x, min_y), (max_x, max_y), size=(count * 4, 2))
        hits = candidates[shapely.contains_xy(geom, candidates[:, 0], candidates[:, 1])][:need]
        found.append(hits)
        need -= len(hits)
        if need <= 0:
            break
    return np.vstack(found)


def source_points(features: list[Feature], samples: int, seed: int) -> PointSet:
    """Every source vertex plus seeded interior samples, so microstates are always covered."""
    rng = np.random.default_rng(seed)
    xy, codes = [], []
    for code, geom in features:
        points = np.vstack([shapely.get_coordinates(geom), _interior(geom, samples, rng)])
        xy.append(points)
        codes.append(np.full(len(points), code, dtype=object))
    return PointSet(np.vstack(xy), np.concatenate(codes))


def classify(points: PointSet, features: list[Feature], width: float) -> np.ndarray:
    codes = np.array([code for code, _ in features], dtype=object)
    tree = shapely.STRtree([geom for _, geom in features])
    geoms = shapely.points(points.xy)
    kind = np.full(len(geoms), CORE, dtype=np.int8)
    for label, distance in ((BORDER, width), (AMBIGUOUS, 1e-9)):
        point_index, geom_index = tree.query(geoms, predicate="dwithin", distance=distance)
        other = codes[geom_index] != points.code[point_index]
        kind[np.unique(point_index[other])] = label
    return kind


def _read(path: Path) -> object:
    try:
        return json.loads(gzip.decompress(path.read_bytes()))
    except (OSError, ValueError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error


def load_output(build_dir: Path) -> tuple[dict, dict[str, dict]]:
    manifest = _read(build_dir / "world_sectors.json.gz")
    return manifest, {key: _read(build_dir / key) for key in manifest}


def lookup(manifest: dict, sector_files: dict[str, dict], xy: np.ndarray) -> np.ndarray:
    """First match in manifest order, then file order: the libraries' lookup semantics."""
    polygons, owners, ranks, boxes = [], [], [], []
    for sector_index, (key, entry) in enumerate(manifest.items()):
        for order, (code, rings) in enumerate(sector_files[key].items()):
            for ring in rings:
                polygons.append(polygonal(Polygon([(lng, lat) for lat, lng in ring])))
                owners.append(code)
                ranks.append(sector_index * 1_000_000 + order)
                boxes.append(entry["bounds"])
    owners_arr, ranks_arr, boxes_arr = np.array(owners, dtype=object), np.array(ranks), np.array(boxes, dtype=float)
    point_index, poly_index = shapely.STRtree(polygons).query(shapely.points(xy), predicate="intersects")
    lat, lng = xy[point_index, 1], xy[point_index, 0]
    b = boxes_arr[poly_index]
    inside = (b[:, 0] <= lat) & (lat <= b[:, 2]) & (b[:, 1] <= lng) & (lng <= b[:, 3])
    point_index, poly_index = point_index[inside], poly_index[inside]
    order = np.lexsort((ranks_arr[poly_index], point_index))
    point_index, poly_index = point_index[order], poly_index[order]
    _, first = np.unique(point_index, return_index=True)
    result = np.full(len(xy), None, dtype=object)
    result[point_index[first]] = owners_arr[poly_index[first]]
    return result


def fixture(points: PointSet, kind: np.ndarray, sectors: Sectors, seed: int, size: int = 500) -> list[dict]:
    """Seeded core points, one per code first, none on a sector edge (TypeScript checks one sector)."""
    lat, lng = points.xy[:, 1], points.xy[:, 0]
    edges = np.array(list(sectors.values()), dtype=float)
    on_lat = np.isclose(lat[:, None], edges[:, [0, 2]][None, :, :].reshape(1, -1), atol=1e-9).any(axis=1)
    on_lng = np.isclose(lng[:, None], edges[:, [1, 3]][None, :, :].reshape(1, -1), atol=1e-9).any(axis=1)
    pool = np.flatnonzero((kind == CORE) & ~on_lat & ~on_lng)
    rng = np.random.default_rng(seed)
    chosen = [int(rng.choice(pool[points.code[pool] == code])) for code in sorted(set(points.code[pool]))]
    rest = np.setdiff1d(pool, chosen)
    extra = rng.choice(rest, size=min(max(size - len(chosen), 0), len(rest)), replace=False)
    picked = sorted(set(chosen) | {int(i) for i in extra})
    return [{"lat": round(float(lat[i]), 6), "lng": round(float(lng[i]), 6), "code": str(points.code[i])} for i in picked]


def _accuracy(correct: np.ndarray, mask: np.ndarray) -> float:
    return float(correct[mask].mean()) if mask.any() else 1.0


def run_validation(cfg: BuildConfig) -> dict:
    features = load_features(cfg)
    sectors = read_sectors(cfg.input_file(cfg.sectors))
    points = source_points(features, cfg.samples, cfg.seed)
    kind = classify(points, features, band(cfg))
    failures: list[str] = []
    try:
        manifest, sector_files = load_output(cfg.build_dir)
    except ValidationError as error:
        manifest, sector_files = {}, {}
        failures.append(str(error))
    if manifest and [entry["bounds"] for entry in manifest.values()] != list(sectors.values()):
        failures.append("manifest bounds differ from the sector file")
    got = lookup(manifest, sector_files, points.xy) if sector_files else np.full(len(kind), None, dtype=object)
    correct = got == points.code
    core, border, scored = kind == CORE, kind == BORDER, kind != AMBIGUOUS
    if not correct[core].all():
        failures.append(f"{int((~correct[core]).sum())} core points return the wrong code")
    source_codes = {code for code, _ in features}
    output_codes = {code for sector in sector_files.values() for code in sector}
    if missing := sorted(source_codes - output_codes):
        failures.append(f"codes missing from output: {missing}")
    if extra := sorted(output_codes - source_codes):
        failures.append(f"codes not in source: {extra}")
    border_accuracy = _accuracy(correct, border)
    if border_accuracy < cfg.min_border_accuracy:
        failures.append(f"border accuracy {border_accuracy:.4f} below {cfg.min_border_accuracy}")
    per_code = {}
    for code in sorted(source_codes):
        mask = scored & (points.code == code)
        per_code[code] = {"points": int(mask.sum()), "accuracy": round(_accuracy(correct, mask), 6)}
    report = {
        "passed": not failures,
        "failures": failures,
        "band": band(cfg),
        "counts": {"total": len(kind), "core": int(core.sum()), "border": int(border.sum()),
                   "ambiguous": int((kind == AMBIGUOUS).sum())},
        "accuracy": {"overall": _accuracy(correct, scored), "core": _accuracy(correct, core), "border": border_accuracy},
        "worst": sorted(per_code, key=lambda c: (per_code[c]["accuracy"], c))[:10],
        "per_code": per_code,
    }
    cfg.build_dir.mkdir(parents=True, exist_ok=True)
    (cfg.build_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    points_json = json.dumps(fixture(points, kind, sectors, cfg.seed), separators=(",", ":")) + "\n"
    (cfg.build_dir / "points.json").write_text(points_json, encoding="utf-8")
    return report
```

- [ ] **Step 4: Run tests**

Run: `uv run --project workflow pytest workflow/tests/test_validate.py`
Expected: all PASS. If the file passes 300 lines, move `fixture` and `_accuracy` into `workflow/src/qc2c_build/fixture.py` and import them.

- [ ] **Step 5: Commit**

```bash
task git:commit -- "feat(workflow): validate builds against source borders"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
