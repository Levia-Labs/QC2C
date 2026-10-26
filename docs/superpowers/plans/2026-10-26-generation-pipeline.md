# Generation Pipeline Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `workflow/scripts` with a parametrized, validated `qc2c-build` pipeline that runs in Docker Compose and publishes sector data into both packages.

**Architecture:** A uv project in `workflow/` holds the package `qc2c_build`: load source borders, give sea to the nearest country, simplify shared borders once, split into hole-free rings per sector, write JSON and gzip, validate against the source, publish into the packages. Docker Compose services run every command and test suite; Task wraps Compose.

**Tech Stack:** Python 3.12, shapely 2.1+, numpy, pytest, hypothesis, matplotlib (preview only), Docker Compose v2, Task, Node 24 with jest for the TypeScript package.

**Spec:** `docs/superpowers/specs/2026-10-26-generation-pipeline-design.md`

## Global Constraints

1. Python 3.12+, managed with uv; pass `encoding="utf-8"` to every text read and write.
2. Runtime dependencies: `shapely>=2.1,<3`, `numpy`; optional `preview` extra: `matplotlib`; `dev` group: `pytest`, `hypothesis`.
3. Every source file stays under 300 lines.
4. Output format is unchanged: manifest `{"world_sector_N.json.gz": {"bounds": [lat_min, lng_min, lat_max, lng_max], "center": {code: [lat, lng]}}}`, sector file `{code: [[[lat, lng], ...], ...]}`, outer rings only.
5. Defaults: tolerance 0.05, decimals 3, presimplify 0.01, voronoi spacing 0.25, sea `nearest`, sea distance 200 km, USA (not states), seed 1, 40 samples per country.
6. Sea points return the nearest country; US points return `USA`; `-99` entries take codes from `workflow/data/input/code_overrides.json`.
7. Docker images and GitHub Actions are pinned by digest or commit SHA.
8. Generated data in `packages/*/data` and `packages/typescript/dist` is written only by `qc2c-build publish` and `npm run build`, never by hand.
9. Commit with `task git:commit -- "<message>"` from the repo root, Conventional Commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
10. Packages ship as 2.0.0.

## Spec amendments made by this plan

1. **Core band.** The spec's band `presimplify + tolerance + 10^-decimals + 0.001` does not cover the Voronoi step: sea next to country A can go to country B when B is within about one boundary spacing. The plan uses `2 * (presimplify + tolerance + 10^-decimals + 0.001) + voronoi_spacing / 2`, measured as the distance to the nearest *other* code's source geometry. Task 1 updates the spec.
2. **Holes.** Instead of relying on area ordering for enclaves, the writer cuts every polygon with holes into hole-free pieces, so first-match lookup is exact whatever the order. Area ordering stays.
3. **Task names.** The Crepidoma submodule already owns the `test` namespace, so the parallel test task is `task workflow:test`, not `task test`. `task workflow:check` compares the latest build with the shipped package data instead of building a second copy.
4. **Modules.** Three small modules are added to the spec's list: `geom.py` (shared polygon helpers), `pipeline.py` (build orchestration) and a `compare` command inside `publish.py`.

## Review Focus

1. Microstates (Vatican, Monaco, San Marino) collapsing under simplification: the code must survive with its own area. Pinned in Task 4 (`test_restore_lost_puts_tiny_code_back`) and by validation check 2.
2. Points exactly on a sector edge: the TypeScript library checks only the first matching sector, so fixture points must avoid sector edges. Pinned in Task 7 (`test_fixture_avoids_sector_edges`).
3. Countries touching the antimeridian (Russia, Fiji, Kiribati) are split at ±180 in the source; both halves must survive partition and clipping. Pinned in Task 3 (`test_antimeridian_halves_survive`).
4. Invalid source geometry (self-intersections) must be repaired, not crash the build. Pinned in Task 2 (`test_invalid_geometry_is_repaired`).
5. A wrong setting or a missing input folder must exit with status 2 and one readable line, not a traceback. Pinned in Task 8 (`test_cli_missing_input_exits_2`, `test_cli_bad_setting_exits_2`).

## File structure

| Path | Responsibility |
| --- | --- |
| `workflow/pyproject.toml`, `workflow/uv.lock` | Build project, dependencies, `qc2c-build` script |
| `workflow/qc2c.toml` | Checked-in default settings |
| `workflow/src/qc2c_build/config.py` | `BuildConfig`, settings precedence, validation |
| `workflow/src/qc2c_build/geom.py` | `polygonal`, `hole_free` |
| `workflow/src/qc2c_build/load.py` | Source loading, overrides, USA or states, overlap removal |
| `workflow/src/qc2c_build/partition.py` | Nearest-country sea partition |
| `workflow/src/qc2c_build/simplify.py` | Coverage simplification, grid snapping, microstate restore |
| `workflow/src/qc2c_build/sectors.py` | Sector file reading, tiling check, clipping, rings, centers |
| `workflow/src/qc2c_build/write.py` | JSON, gzip and `build.json` output |
| `workflow/src/qc2c_build/pipeline.py` | `run_build` |
| `workflow/src/qc2c_build/validate.py` | Point set, classification, lookup, report, fixture |
| `workflow/src/qc2c_build/publish.py` | `publish`, `compare` |
| `workflow/src/qc2c_build/preview.py` | Headless PNG preview |
| `workflow/src/qc2c_build/cli.py` | `qc2c-build` subcommands |
| `workflow/tests/*.py` | Synthetic-world unit, property and end-to-end tests |
| `workflow/data/input/code_overrides.json` | `-99` code overrides |
| `workflow/Dockerfile`, `workflow/.dockerignore`, `compose.yaml` | Engine |
| `tasks/workflow.yml` | Task wrappers |
| `packages/fixtures/points.json` | Shared library fixture, written by publish |
| `packages/python/tests/test_fixture.py`, `packages/typescript/tests/fixture.test.js` | Library fixture tests |
| `.github/workflows/ci.yml` | Pull request gate |
| `CHANGELOG.md` | 2.0.0 notes |

Removed: `workflow/scripts/`, `workflow/test/`, `workflow/data/output/stage_1..4/`, `workflow/.gitignore` (replaced).

---

### Task 1: Project scaffold and settings

**Files:**
- Create: `workflow/pyproject.toml`, `workflow/qc2c.toml`, `workflow/src/qc2c_build/__init__.py`, `workflow/src/qc2c_build/config.py`, `workflow/tests/conftest.py`, `workflow/tests/test_config.py`
- Modify: `docs/superpowers/specs/2026-10-26-generation-pipeline-design.md` (Validation section band formula, Tasks table)

**Interfaces:**
- Produces: `BuildConfig` (frozen dataclass, fields below, properties `build_dir`, methods `input_file(name) -> Path`, `as_dict() -> dict`), `ConfigError(ValueError)`, `DEFAULTS: BuildConfig`, `load_config(toml_path: Path | None, env: Mapping[str, str] | None = None, cli: Mapping[str, Any] | None = None) -> BuildConfig`. Test helpers in `conftest.py`: `square`, `feature`, `write_inputs`, `TWO_SECTORS`, fixture `world -> BuildConfig`.

- [ ] **Step 1: Write `workflow/pyproject.toml`**

```toml
[project]
name = "qc2c-build"
version = "2.0.0"
description = "Builds the QC2C sector data from source country borders."
requires-python = ">=3.12"
dependencies = ["shapely>=2.1,<3", "numpy>=2"]

[project.optional-dependencies]
preview = ["matplotlib>=3.9"]

[project.scripts]
qc2c-build = "qc2c_build.cli:main"

[dependency-groups]
dev = ["pytest>=8", "hypothesis>=6"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/qc2c_build"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q -p no:cacheprovider"
```

`workflow/src/qc2c_build/__init__.py`:

```python
"""Build pipeline for the QC2C sector data."""
```

`workflow/qc2c.toml`:

```toml
# Default build settings. Precedence: these values, then QC2C_<NAME> environment
# variables, then qc2c-build command-line flags.
tolerance = 0.05
decimals = 3
presimplify = 0.01
voronoi_spacing = 0.25
sea = "nearest"
sea_distance_km = 200.0
us_states = false
samples = 40
seed = 1
# Set from the first full default build (Task 10); only ever raise it.
min_border_accuracy = 0.0
```

- [ ] **Step 2: Write the shared test helpers `workflow/tests/conftest.py`**

```python
"""Synthetic world shared by the pipeline tests. Coordinates are GeoJSON [lng, lat]."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import settings

from qc2c_build.config import BuildConfig

# The Docker test service mounts the source read-only; keep Hypothesis from writing its example database.
settings.register_profile("readonly", database=None)
settings.load_profile("readonly")

TWO_SECTORS = {"world_sector_1.json": [0, -180, 90, 180], "world_sector_2.json": [-90, -180, 0, 180]}


def square(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def feature(code: str, name: str, *polygons: list[list[list[float]]]) -> dict:
    """One GeoJSON feature; each polygon is a list of rings, the first one outer."""
    if len(polygons) == 1:
        geometry = {"type": "Polygon", "coordinates": polygons[0]}
    else:
        geometry = {"type": "MultiPolygon", "coordinates": list(polygons)}
    return {"type": "Feature", "properties": {"ADMIN": name, "ISO_A3": code}, "geometry": geometry}


def write_inputs(folder: Path, countries: list[dict], states: list[dict] | None = None,
                 overrides: dict | None = None, sectors: dict | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    collections = {"countries.json": countries, "us_states.json": states or []}
    for name, features in collections.items():
        body = {"type": "FeatureCollection", "features": features}
        (folder / name).write_text(json.dumps(body), encoding="utf-8")
    (folder / "code_overrides.json").write_text(json.dumps(overrides or {}), encoding="utf-8")
    (folder / "world_sectors.json").write_text(json.dumps(sectors or TWO_SECTORS), encoding="utf-8")


WORLD_FEATURES = [
    feature("HST", "Host", [square(-40, 20, -20, 40), square(-32, 28, -28, 32)]),
    feature("ENC", "Enclave", [square(-32, 28, -28, 32)]),
    feature("WST", "West", [square(0, 20, 10, 30)]),
    feature("EST", "East", [square(10, 20, 20, 30)]),
    feature("ISL", "Island", [square(20.5, 22, 22, 24)]),
    feature("SPN", "Span", [square(40, -10, 50, 10)]),
    feature("-99", "Nowhere", [square(60, 50, 62, 52)]),
]


@pytest.fixture
def world(tmp_path: Path) -> BuildConfig:
    """Host with an enclave, two neighbours sharing x=10, an island across a strait,
    a country spanning the equator (the sector edge) and a '-99' entry."""
    inputs = tmp_path / "input"
    write_inputs(inputs, WORLD_FEATURES, overrides={"Nowhere": "NWH"})
    return BuildConfig(input_dir=inputs, output_dir=tmp_path / "output", packages_dir=tmp_path / "packages",
                       presimplify=0.0, voronoi_spacing=1.0, samples=10)
```

- [ ] **Step 3: Write the failing tests `workflow/tests/test_config.py`**

```python
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from qc2c_build.config import DEFAULTS, BuildConfig, ConfigError, load_config


def test_defaults():
    assert DEFAULTS.tolerance == 0.05
    assert DEFAULTS.decimals == 3
    assert DEFAULTS.sea == "nearest"
    assert DEFAULTS.us_states is False


def test_precedence(tmp_path: Path):
    toml = tmp_path / "qc2c.toml"
    toml.write_text("tolerance = 0.1\n", encoding="utf-8")
    assert load_config(toml, env={}).tolerance == 0.1
    assert load_config(toml, env={"QC2C_TOLERANCE": "0.2"}).tolerance == 0.2
    assert load_config(toml, env={"QC2C_TOLERANCE": "0.2"}, cli={"tolerance": "0.3"}).tolerance == 0.3


def test_cli_none_keeps_lower_layers():
    assert load_config(None, env={"QC2C_DECIMALS": "4"}, cli={"decimals": None}).decimals == 4


def test_bool_from_env():
    assert load_config(None, env={"QC2C_US_STATES": "yes"}).us_states is True
    with pytest.raises(ConfigError, match="true or false"):
        load_config(None, env={"QC2C_US_STATES": "maybe"})


def test_unknown_toml_key(tmp_path: Path):
    toml = tmp_path / "qc2c.toml"
    toml.write_text("tolerence = 0.1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown setting: tolerence"):
        load_config(toml, env={})


@pytest.mark.parametrize("bad", [{"sea": "ocean"}, {"out": "../x"}, {"decimals": 9}, {"tolerance": -1},
                                 {"samples": 0}, {"min_border_accuracy": 1.5}])
def test_invalid_values(bad):
    with pytest.raises(ConfigError):
        BuildConfig(**bad)


def test_paths(tmp_path: Path):
    cfg = BuildConfig(input_dir=tmp_path / "in", output_dir=tmp_path / "out", out="trial")
    assert cfg.build_dir == tmp_path / "out" / "trial"
    assert cfg.input_file("world_sectors.json") == tmp_path / "in" / "world_sectors.json"
    assert cfg.input_file(str(tmp_path / "abs.json")) == tmp_path / "abs.json"
    assert cfg.as_dict()["input_dir"] == str(tmp_path / "in")


@given(st.floats(min_value=0, max_value=10, allow_nan=False))
def test_tolerance_roundtrips_from_text(value):
    assert load_config(None, env={}, cli={"tolerance": repr(value)}).tolerance == value
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_config.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.config'`

- [ ] **Step 5: Implement `workflow/src/qc2c_build/config.py`**

```python
"""Build settings: defaults, then qc2c.toml, then QC2C_* environment variables, then CLI flags."""
from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

SEA_MODES = ("nearest", "distance")


class ConfigError(ValueError):
    """A setting is unknown, unreadable or out of range."""


@dataclass(frozen=True)
class BuildConfig:
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    packages_dir: Path = Path("../packages")
    tolerance: float = 0.05
    decimals: int = 3
    presimplify: float = 0.01
    voronoi_spacing: float = 0.25
    sea: str = "nearest"
    sea_distance_km: float = 200.0
    us_states: bool = False
    sectors: str = "world_sectors.json"
    overrides: str = "code_overrides.json"
    out: str = "latest"
    samples: int = 40
    min_border_accuracy: float = 0.0
    seed: int = 1

    def __post_init__(self) -> None:
        if self.tolerance < 0 or self.presimplify < 0:
            raise ConfigError("tolerance and presimplify must be >= 0")
        if not 0 <= self.decimals <= 7:
            raise ConfigError("decimals must be between 0 and 7")
        if self.voronoi_spacing <= 0:
            raise ConfigError("voronoi_spacing must be > 0")
        if self.sea not in SEA_MODES:
            raise ConfigError(f"sea must be one of {', '.join(SEA_MODES)}")
        if self.sea_distance_km <= 0:
            raise ConfigError("sea_distance_km must be > 0")
        if self.samples < 1:
            raise ConfigError("samples must be >= 1")
        if not 0 <= self.min_border_accuracy <= 1:
            raise ConfigError("min_border_accuracy must be between 0 and 1")
        if not self.out or self.out.startswith(".") or "/" in self.out or "\\" in self.out:
            raise ConfigError("out must be a plain folder name")

    @property
    def build_dir(self) -> Path:
        return self.output_dir / self.out

    def input_file(self, name: str) -> Path:
        path = Path(name)
        return path if path.is_absolute() else self.input_dir / path

    def as_dict(self) -> dict[str, Any]:
        return {k: str(v) if isinstance(v, Path) else v for k, v in asdict(self).items()}


FIELDS = {f.name for f in fields(BuildConfig)}
DEFAULTS = BuildConfig()


def _coerce(name: str, value: Any) -> Any:
    if name not in FIELDS:
        raise ConfigError(f"unknown setting: {name}")
    default = getattr(DEFAULTS, name)
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "on"):
            return True
        if text in ("0", "false", "no", "off"):
            return False
        raise ConfigError(f"{name} must be true or false, got {value!r}")
    try:
        return type(default)(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{name}: cannot read {value!r}") from error


def load_config(toml_path: Path | None = None, env: Mapping[str, str] | None = None,
                cli: Mapping[str, Any] | None = None) -> BuildConfig:
    values: dict[str, Any] = {}
    if toml_path is not None and toml_path.is_file():
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        values.update({key: _coerce(key, value) for key, value in data.items()})
    env = os.environ if env is None else env
    for name in FIELDS:
        key = f"QC2C_{name.upper()}"
        if key in env:
            values[name] = _coerce(name, env[key])
    for name, value in (cli or {}).items():
        if value is not None:
            values[name] = _coerce(name, value)
    return BuildConfig(**values)
```

- [ ] **Step 6: Lock and run tests**

Run: `uv lock --project workflow` then `uv run --project workflow pytest workflow/tests/test_config.py`
Expected: all PASS.

- [ ] **Step 7: Amend the spec**

In `docs/superpowers/specs/2026-10-26-generation-pipeline-design.md`, Validation section, replace the paragraph that starts `Each point is classified by its distance` and its three-item list with:

```markdown
Each point is classified by its distance `d` to the nearest source geometry of a *different* code (source coverage after overrides):

1. "Ambiguous" when `d < 1e-9`: the point lies on a shared border and belongs to both codes. Not scored.
2. "Core" when `d` exceeds `2 * (presimplify + tolerance + 10^-decimals + 0.001) + voronoi_spacing / 2`. The doubling and the spacing term cover sea that the Voronoi step can hand to a neighbour within one boundary spacing.
3. "Border band" otherwise.
```

In the Tasks table replace `task workflow:check` row text with `compare the latest build with the published package data` and replace `task test` with `task workflow:test`. Under Data flow step 4 add: `Polygons with holes are cut into hole-free pieces, so first-match lookup is exact in any order.`

- [ ] **Step 8: Commit**

```bash
task git:commit -- "feat(workflow): add qc2c-build project and settings"
```

### Task 2: Geometry helpers and source loading

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
    countries = [feature("USA", "United States", [square(-100, 30, -80, 40)]),
                 feature("PRI", "Puerto Rico", [square(-67, 18, -65, 19)])]
    states = [feature("NY", "New York", [square(-80, 35, -75, 40)]),
              feature("PR", "Puerto Rico", [square(-67, 18, -65, 19)])]
    write_inputs(world.input_dir, countries, states=states)
    assert codes(world) == ["PRI", "USA"]
    assert codes(replace(world, us_states=True)) == ["NY", "PRI"]


def test_same_code_dissolves(world):
    write_inputs(world.input_dir, [feature("AAA", "A1", [square(0, 0, 1, 1)]),
                                   feature("AAA", "A2", [square(5, 5, 6, 6)])])
    [(code, geom)] = load_features(world)
    assert code == "AAA" and abs(geom.area - 2) < 1e-9


def test_overlaps_removed(world):
    write_inputs(world.input_dir, [feature("AAA", "A", [square(0, 0, 2, 2)]),
                                   feature("BBB", "B", [square(1, 1, 3, 3)])])
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

### Task 3: Sea partition

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

### Task 4: Simplification and microstate restore

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
```

- [ ] **Step 4: Run tests**

Run: `uv run --project workflow pytest workflow/tests/test_simplify.py`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
task git:commit -- "feat(workflow): simplify shared borders and restore microstates"
```

### Task 5: Sectors, rings and output files

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

### Task 6: Validation of output

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

### Task 7: Publish, compare and preview

**Files:**
- Create: `workflow/src/qc2c_build/publish.py`, `workflow/src/qc2c_build/preview.py`, `workflow/tests/test_publish.py`

**Interfaces:**
- Consumes: `BuildConfig`, `run_build`, `run_validation`.
- Produces: `publish.PublishError(Exception)`, `publish.TARGETS: tuple[str, ...]` (`"python/qc2c/data"`, `"typescript/src/data"`), `publish.publish(cfg) -> list[Path]`, `publish.compare(cfg) -> list[str]`; `preview.render(cfg) -> Path`.

- [ ] **Step 1: Write the failing tests `workflow/tests/test_publish.py`**

```python
import json

import pytest

from qc2c_build.pipeline import run_build
from qc2c_build.publish import PublishError, compare, publish
from qc2c_build.validate import run_validation


def test_publish_then_compare(world):
    run_build(world)
    run_validation(world)
    written = publish(world)
    assert (world.packages_dir / "python/qc2c/data/gz/world_sectors.json.gz") in written
    assert (world.packages_dir / "typescript/src/data/json/world_sector_1.json").is_file()
    assert (world.packages_dir / "fixtures/points.json").is_file()
    assert compare(world) == []
    (world.packages_dir / "python/qc2c/data/json/world_sector_1.json").write_text("{}", encoding="utf-8")
    assert compare(world) == ["python/qc2c/data/json/world_sector_1.json"]


def test_publish_keeps_other_files(world):
    keep = world.packages_dir / "python/qc2c/data/json/__init__.py"
    keep.parent.mkdir(parents=True)
    keep.write_text("", encoding="utf-8")
    run_build(world)
    run_validation(world)
    publish(world)
    assert keep.is_file()


def test_publish_refuses_failed_validation(world):
    run_build(world)
    (world.build_dir / "validation.json").write_text(json.dumps({"passed": False}), encoding="utf-8")
    with pytest.raises(PublishError, match="validation failed"):
        publish(world)


def test_preview_writes_png(world):
    pytest.importorskip("matplotlib")
    from qc2c_build.preview import render

    run_build(world)
    assert render(world).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project workflow --all-extras pytest workflow/tests/test_publish.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.publish'`

- [ ] **Step 3: Implement `workflow/src/qc2c_build/publish.py`**

```python
"""Copy a validated build into both packages, or report how they differ from it."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import BuildConfig

TARGETS = ("python/qc2c/data", "typescript/src/data")
FIXTURE = "fixtures/points.json"


class PublishError(Exception):
    """The build is missing, unvalidated or failed validation."""


def _planned(cfg: BuildConfig) -> list[tuple[Path, str]]:
    """(source file, path relative to packages_dir) for everything publish writes."""
    sources = sorted(p for p in cfg.build_dir.glob("world_sector*") if p.suffix in (".json", ".gz"))
    plan = []
    for target in TARGETS:
        for source in sources:
            folder = "gz" if source.suffix == ".gz" else "json"
            plan.append((source, f"{target}/{folder}/{source.name}"))
    plan.append((cfg.build_dir / "points.json", FIXTURE))
    return plan


def publish(cfg: BuildConfig) -> list[Path]:
    report_path = cfg.build_dir / "validation.json"
    if not report_path.is_file():
        raise PublishError(f"no validation.json in {cfg.build_dir}; run validate first")
    if not json.loads(report_path.read_text(encoding="utf-8")).get("passed"):
        raise PublishError("validation failed; not publishing")
    for target in TARGETS:
        for folder in ("json", "gz"):
            for old in (cfg.packages_dir / target / folder).glob("world_sector*"):
                old.unlink()
    written = []
    for source, relative in _planned(cfg):
        destination = cfg.packages_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        written.append(destination)
    return written


def compare(cfg: BuildConfig) -> list[str]:
    """Package paths whose bytes differ from the build, plus shipped sector files the build lacks."""
    planned = _planned(cfg)
    diffs = [rel for src, rel in planned
             if not (cfg.packages_dir / rel).is_file() or (cfg.packages_dir / rel).read_bytes() != src.read_bytes()]
    expected = {rel for _, rel in planned}
    for target in TARGETS:
        for folder in ("json", "gz"):
            for shipped in (cfg.packages_dir / target / folder).glob("world_sector*"):
                rel = shipped.relative_to(cfg.packages_dir).as_posix()
                if rel not in expected:
                    diffs.append(rel)
    return sorted(diffs)
```

- [ ] **Step 4: Implement `workflow/src/qc2c_build/preview.py`**

```python
"""Draw a build as a PNG with sector boxes, without a display."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .config import BuildConfig


def _color(code: str) -> tuple[float, float, float]:
    digest = hashlib.sha256(code.encode("utf-8")).digest()
    return tuple(0.3 + digest[i] / 365 for i in range(3))


def render(cfg: BuildConfig) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    build = cfg.build_dir
    manifest = json.loads(gzip.decompress((build / "world_sectors.json.gz").read_bytes()))
    figure, axes = plt.subplots(figsize=(18, 9), dpi=100)
    for key, entry in manifest.items():
        sector = json.loads(gzip.decompress((build / key).read_bytes()))
        for code, rings in sector.items():
            for ring in rings:
                axes.add_patch(Polygon([(lng, lat) for lat, lng in ring], closed=True,
                                       facecolor=_color(code), edgecolor="black", linewidth=0.1))
        lat_min, lng_min, lat_max, lng_max = entry["bounds"]
        axes.add_patch(Rectangle((lng_min, lat_min), lng_max - lng_min, lat_max - lat_min,
                                 fill=False, edgecolor="red", linewidth=0.8))
    axes.set_xlim(-180, 180)
    axes.set_ylim(-90, 90)
    axes.set_aspect("equal")
    axes.axis("off")
    out = build / "preview.png"
    figure.savefig(out, bbox_inches="tight")
    plt.close(figure)
    return out
```

- [ ] **Step 5: Run tests**

Run: `uv run --project workflow --all-extras pytest workflow/tests/test_publish.py`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
task git:commit -- "feat(workflow): publish, compare and preview builds"
```

### Task 8: Command line

**Files:**
- Create: `workflow/src/qc2c_build/cli.py`, `workflow/tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `ConfigError`, `run_build`, `run_validation`, `publish`, `compare`, `PublishError`, `render`, `DEFAULTS`.
- Produces: `cli.main(argv: list[str] | None = None) -> int` (0 ok, 1 check failed, 2 usage or input error); console script `qc2c-build`.

- [ ] **Step 1: Write the failing tests `workflow/tests/test_cli.py`**

```python
from qc2c_build.cli import main


def args(cfg, *extra):
    return ["--config", "none.toml", "--input-dir", str(cfg.input_dir), "--output-dir", str(cfg.output_dir),
            "--packages-dir", str(cfg.packages_dir), "--presimplify", "0", "--voronoi-spacing", "1", "--samples", "10", *extra]


def test_cli_build_validate_publish_compare(world, capsys):
    assert main(["build", *args(world)]) == 0
    assert main(["validate", *args(world)]) == 0
    assert main(["publish", *args(world)]) == 0
    assert main(["compare", *args(world)]) == 0
    assert "built" in capsys.readouterr().out


def test_cli_compare_reports_difference(world):
    main(["build", *args(world)])
    assert main(["compare", *args(world)]) == 1


def test_cli_bad_setting_exits_2(world, capsys):
    assert main(["build", *args(world, "--sea", "ocean")]) == 2
    assert "sea must be one of" in capsys.readouterr().err


def test_cli_missing_input_exits_2(world, tmp_path, capsys):
    assert main(["build", *args(world, "--input-dir", str(tmp_path / "missing"))]) == 2
    assert "qc2c-build:" in capsys.readouterr().err


def test_cli_us_states_flag(world):
    assert main(["build", *args(world, "--us-states")]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_cli.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.cli'`

- [ ] **Step 3: Implement `workflow/src/qc2c_build/cli.py`**

```python
"""qc2c-build: build, validate, publish, compare or preview QC2C sector data."""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import fields
from pathlib import Path

from .config import DEFAULTS, BuildConfig, ConfigError, load_config
from .pipeline import run_build
from .publish import PublishError, compare, publish
from .validate import run_validation


def _build(cfg: BuildConfig) -> int:
    meta = run_build(cfg)
    seconds = sum(meta["seconds"].values())
    print(f"built {cfg.build_dir}: {meta['codes']} codes, {meta['points']} points, "
          f"{meta['gzip_total'] / 1024:.0f} KB gzip in {seconds:.0f}s")
    return 0


def _validate(cfg: BuildConfig) -> int:
    report = run_validation(cfg)
    accuracy = report["accuracy"]
    print(f"validated {cfg.build_dir}: core {accuracy['core']:.4%}, border {accuracy['border']:.4%}, "
          f"overall {accuracy['overall']:.4%}; worst {', '.join(report['worst'][:5])}")
    for failure in report["failures"]:
        print(f"FAIL {failure}")
    return 0 if report["passed"] else 1


def _publish(cfg: BuildConfig) -> int:
    print(f"published {len(publish(cfg))} files into {cfg.packages_dir}")
    return 0


def _compare(cfg: BuildConfig) -> int:
    diffs = compare(cfg)
    for path in diffs:
        print(f"differs: {path}")
    print("package data matches the build" if not diffs else f"{len(diffs)} files differ")
    return 1 if diffs else 0


def _preview(cfg: BuildConfig) -> int:
    from .preview import render

    print(f"preview written to {render(cfg)}")
    return 0


COMMANDS = {"build": _build, "validate": _validate, "publish": _publish, "compare": _compare, "preview": _preview}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="qc2c-build", description=__doc__)
    result.add_argument("command", choices=sorted(COMMANDS))
    result.add_argument("--config", type=Path, default=Path(os.environ.get("QC2C_CONFIG", "qc2c.toml")))
    for field in fields(BuildConfig):
        flag = "--" + field.name.replace("_", "-")
        if isinstance(getattr(DEFAULTS, field.name), bool):
            result.add_argument(flag, dest=field.name, action=argparse.BooleanOptionalAction, default=None)
        else:
            result.add_argument(flag, dest=field.name, default=None, metavar=field.name.upper())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    cli = {field.name: getattr(args, field.name) for field in fields(BuildConfig)}
    try:
        cfg = load_config(args.config, cli=cli)
        return COMMANDS[args.command](cfg)
    except (ConfigError, PublishError, FileNotFoundError) as error:
        print(f"qc2c-build: {error}", file=sys.stderr)
        return 2
```

`test_cli_missing_input_exits_2` relies on `read_sectors` raising `FileNotFoundError` for the missing folder.

- [ ] **Step 4: Run all pipeline tests**

Run: `uv run --project workflow --all-extras pytest workflow/tests`
Expected: all PASS in a few seconds.

- [ ] **Step 5: Commit**

```bash
task git:commit -- "feat(workflow): add qc2c-build command line"
```

### Task 9: Docker engine and Task wrappers

**Files:**
- Create: `workflow/Dockerfile`, `workflow/.dockerignore`, `compose.yaml`, `tasks/workflow.yml`, `workflow/data/output/.gitignore`
- Modify: `Taskfile.yml` (includes), `docs/folder-purposes.toml`
- Delete: `workflow/scripts/`, `workflow/test/`, `workflow/data/output/stage_1/` to `stage_4/`, `workflow/.gitignore`

**Interfaces:**
- Consumes: console script `qc2c-build` (Task 8).
- Produces: Compose services `build`, `validate`, `publish`, `preview`, `test-pipeline`, `test-python`, `test-node`; tasks `workflow:image`, `workflow:build`, `workflow:validate`, `workflow:publish`, `workflow:check`, `workflow:preview`, `workflow:test`, `workflow:test-pipeline`, `workflow:test-python`, `workflow:test-node`.

- [ ] **Step 1: Resolve pinned images**

Run each and keep the digest it prints:

```bash
docker buildx imagetools inspect python:3.12-slim --format '{{json .Manifest.Digest}}'
gh api repos/astral-sh/uv/releases/latest -q .tag_name
docker buildx imagetools inspect ghcr.io/astral-sh/uv:<tag from previous command> --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect node:24-slim --format '{{json .Manifest.Digest}}'
```

- [ ] **Step 2: Write `workflow/Dockerfile`** (substitute the three digests and the uv tag)

```dockerfile
# Reference engine for qc2c-build. Pinned images and uv.lock make builds byte-identical
# across machines of the same architecture (linux/amd64 in CI).
FROM ghcr.io/astral-sh/uv:<UV_TAG>@<UV_DIGEST> AS uv

FROM python:3.12-slim@<PYTHON_DIGEST>
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    QC2C_INPUT_DIR=/data/input \
    QC2C_OUTPUT_DIR=/data/output \
    QC2C_PACKAGES_DIR=/packages \
    QC2C_CONFIG=/app/qc2c.toml
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --all-extras --group dev
COPY src ./src
COPY qc2c.toml ./
RUN uv sync --frozen --all-extras --group dev --no-editable \
    && useradd --uid 1000 --create-home builder
USER 1000
ENTRYPOINT ["qc2c-build"]
```

`workflow/.dockerignore`:

```
data
tests
.venv
**/__pycache__
```

- [ ] **Step 3: Write `compose.yaml`** (substitute the node digest)

```yaml
# Docker engine for the QC2C pipeline. Run through Task: `task --list | grep workflow`.
name: qc2c

x-pipeline: &pipeline
  build:
    context: workflow
  image: qc2c-build:local
  user: "${QC2C_UID:-1000}:${QC2C_GID:-1000}"

x-data: &data
  - ./workflow/data/input:/data/input:ro
  - ./workflow/data/output:/data/output
  - ./workflow/qc2c.toml:/app/qc2c.toml:ro

services:
  build:
    <<: *pipeline
    volumes: *data
    command: ["build"]

  validate:
    <<: *pipeline
    volumes: *data
    command: ["validate"]

  preview:
    <<: *pipeline
    volumes: *data
    command: ["preview"]

  publish:
    <<: *pipeline
    volumes:
      - ./workflow/data/input:/data/input:ro
      - ./workflow/data/output:/data/output:ro
      - ./workflow/qc2c.toml:/app/qc2c.toml:ro
      - ./packages/python/qc2c/data:/packages/python/qc2c/data
      - ./packages/typescript/src/data:/packages/typescript/src/data
      - ./packages/fixtures:/packages/fixtures
    command: ["publish"]

  test-pipeline:
    <<: *pipeline
    volumes:
      - ./workflow:/app:ro
    environment:
      PYTHONPATH: /app/src
    entrypoint: ["python", "-m", "pytest"]
    command: []

  test-python:
    <<: *pipeline
    volumes:
      - ./packages/python:/packages/python:ro
      - ./packages/fixtures:/packages/fixtures:ro
    working_dir: /packages/python
    environment:
      PYTHONPATH: /packages/python
    entrypoint: ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    command: []

  test-node:
    image: node:24-slim@<NODE_DIGEST>
    user: "${QC2C_UID:-1000}:${QC2C_GID:-1000}"
    volumes:
      - ./packages/typescript:/packages/typescript
      - ./packages/fixtures:/packages/fixtures:ro
    working_dir: /packages/typescript
    environment:
      npm_config_cache: /tmp/npm-cache
      HOME: /tmp
    entrypoint: ["sh", "-c", "npm ci --no-audit --no-fund && npm run build && npm test"]
```

`workflow/data/output/.gitignore`:

```
*
!.gitignore
!README.md
```

- [ ] **Step 4: Write `tasks/workflow.yml`**

```yaml
version: "3"

env:
  QC2C_UID:
    sh: id -u
  QC2C_GID:
    sh: id -g

tasks:
  image:
    desc: "Build the pipeline image. Usage: task workflow:image"
    run: once
    cmds:
      - docker compose build build

  build:
    desc: "Build sector data into workflow/data/output/<out> in Docker. Usage: task workflow:build -- [--tolerance 0.1] [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm build build {{.CLI_ARGS}}

  validate:
    desc: "Validate a build against the source borders. Usage: task workflow:validate -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm validate validate {{.CLI_ARGS}}

  publish:
    desc: "Copy a validated build into both packages and rebuild dist. Usage: task workflow:publish -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm publish publish {{.CLI_ARGS}}
      - task: test-node

  check:
    desc: "Fail when package data differs from the build. Usage: task workflow:check -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm publish compare {{.CLI_ARGS}}

  preview:
    desc: "Render a build to preview.png in its output folder. Usage: task workflow:preview -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm preview preview {{.CLI_ARGS}}

  test:
    desc: "Run pipeline, Python and Node suites in parallel. Usage: task workflow:test"
    deps: [test-pipeline, test-python, test-node]

  test-pipeline:
    desc: "Run the pipeline unit tests in Docker. Usage: task workflow:test-pipeline -- [pytest args]"
    deps: [image]
    cmds:
      - docker compose run --rm test-pipeline {{.CLI_ARGS}}

  test-python:
    desc: "Run the Python package tests in Docker. Usage: task workflow:test-python"
    deps: [image]
    cmds:
      - docker compose run --rm test-python

  test-node:
    desc: "Install, build and test the TypeScript package in Docker. Usage: task workflow:test-node"
    cmds:
      - docker compose run --rm test-node
```

In `Taskfile.yml`, add under `includes:` after `setup: .crepidoma/taskfiles/setup`:

```yaml
  workflow: ./tasks/workflow.yml
```

- [ ] **Step 5: Remove the old pipeline**

```bash
git rm -r -q workflow/scripts workflow/test workflow/data/output/stage_1 workflow/data/output/stage_2 workflow/data/output/stage_3 workflow/data/output/stage_4 workflow/.gitignore
```

- [ ] **Step 6: Update `docs/folder-purposes.toml`**

Delete the `[folders]` entries for `workflow/data/output/stage_1` to `stage_4`, `workflow/scripts` and `workflow/test`, and the `[files]` entries `main.py`, `preview_world_sectors.py`, `__main__.py`. Change `"workflow/data/output"` to `"Build outputs, one folder per --out name; ignored by git."`. Add:

```toml
"tasks" = "Task namespaces owned by this repo."
"workflow/src" = "Source of the qc2c-build package."
"workflow/src/qc2c_build" = "Pipeline modules: load, partition, simplify, sectors, write, validate, publish, preview, cli."
"workflow/tests" = "Pipeline tests on a synthetic world."
"packages/fixtures" = "Points with expected codes, written by qc2c-build publish and used by both library test suites."
```

and under `[files]`:

```toml
"Dockerfile" = "Pipeline image: pinned Python and uv, locked dependencies, qc2c-build entry point."
"compose.yaml" = "Docker Compose services for building, validating, publishing and testing."
"qc2c.toml" = "Default build settings."
"code_overrides.json" = "Output codes for source areas without an ISO code."
"points.json" = "Fixture points with expected country codes."
"workflow.yml" = "Task wrappers around the Compose services."
"uv.lock" = "Locked pipeline dependencies."
```

Then run `uv run --no-project python .crepidoma/tools/folder_readme.py update`.

- [ ] **Step 7: Run the suites through Docker**

Run: `task workflow:test-pipeline`
Expected: all pipeline tests PASS inside the container.

Run: `task workflow:test-python`
Expected: existing Python package tests PASS (the fixture test arrives in Task 10).

- [ ] **Step 8: Gate and commit**

Run: `task quality:gate`
Expected: all PASS. If `quality:long-files` flags `workflow/uv.lock`, add it to `.ratchet/long-files.baseline` with the reason `generated lockfile`.

```bash
task git:commit -- "feat(workflow): run the pipeline in Docker Compose and drop staged scripts"
```

### Task 10: First full build, publish data, library fixtures, 2.0.0

**Files:**
- Modify: `workflow/qc2c.toml` (`min_border_accuracy`), `packages/python/tests/test_qc2c.py:36,39`, `packages/typescript/tests/index.test.js:47-50`, `packages/python/pyproject.toml:7`, `packages/typescript/package.json`, `packages/typescript/package-lock.json`
- Create: `packages/python/tests/test_fixture.py`, `packages/typescript/tests/fixture.test.js`, `CHANGELOG.md`
- Generated: `packages/python/qc2c/data/**`, `packages/typescript/src/data/**`, `packages/typescript/dist/**`, `packages/fixtures/points.json`

**Interfaces:**
- Consumes: all `workflow:*` tasks (Task 9).
- Produces: shipped 2.0.0 data and fixture.

- [ ] **Step 1: Write the failing library fixture tests**

`packages/python/tests/test_fixture.py`:

```python
"""Every fixture point written by qc2c-build must resolve to its expected code."""
import json
from pathlib import Path

from qc2c import coordinates_to_country

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "points.json"


def test_fixture_points_match_pipeline():
    points = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(points) >= 250
    wrong = [(p, coordinates_to_country({"lat": p["lat"], "lng": p["lng"]})) for p in points
             if coordinates_to_country({"lat": p["lat"], "lng": p["lng"]}) != p["code"]]
    assert not wrong, wrong[:10]
```

`packages/typescript/tests/fixture.test.js`:

```javascript
// Every fixture point written by qc2c-build must resolve to its expected code.
const fs = require("fs");
const path = require("path");
const { getSector, getCountry } = require("../dist/index");

const dataDir = path.join(__dirname, "..", "src", "data", "json");
const load = (name) => JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));
const points = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "fixtures", "points.json"), "utf8"));

test("fixture points match the pipeline", () => {
  const manifest = load("world_sectors.json");
  const wrong = points.filter(({ lat, lng, code }) => {
    const key = getSector(manifest, { lat, lng });
    return key === null || getCountry(load(key.replace(/\.gz$/, "")), { lat, lng }) !== code;
  });
  expect(points.length).toBeGreaterThanOrEqual(250);
  expect(wrong.slice(0, 10)).toEqual([]);
});
```

Update the city cases. In `packages/python/tests/test_qc2c.py` replace lines 36 and 39:

```python
        (40.71, -74.0, "USA"),
```

and

```python
        (0, -140, "PYF"),  # open ocean returns the nearest country (Marquesas)
```

In `packages/typescript/tests/index.test.js` replace lines 47 to 48 and line 52:

```javascript
    [40.71, -74.0, "USA"],
```

and

```javascript
    // Open ocean returns the nearest country (Marquesas).
    [0, -140, "PYF"],
```

If the first build shows a different nearest country for `(0, -140)`, use the code `qc2c-build` produces and say so in the commit message; the case pins ocean behaviour, not a particular island.

- [ ] **Step 2: Run them to verify they fail**

Run: `task workflow:test-python`
Expected: FAIL with `FileNotFoundError` for `packages/fixtures/points.json` and `"NY" != "USA"`.

- [ ] **Step 3: Build and measure**

Run: `task workflow:build`
Expected: last line `built /data/output/latest: ... codes, ... points, ... KB gzip in ...s`; gzip total within 15% of 222 KB.

Run: `task workflow:validate`
Expected: exit 0 with `core 100.0000%`. Note the `border` percentage.

- [ ] **Step 4: Record the border threshold**

In `workflow/qc2c.toml` set `min_border_accuracy` to the border accuracy from Step 3 rounded down to a whole percent, for example `0.93` for `93.6%`. Rerun `task workflow:validate`; expected exit 0.

- [ ] **Step 5: Publish and rebuild packages**

Run: `task workflow:publish`
Expected: `published 29 files into /packages`, then the Node suite runs. `npm test` now passes including `fixture.test.js`.

Run: `task workflow:test` and `task workflow:check`
Expected: all three suites PASS; `package data matches the build`.

- [ ] **Step 6: Bump versions and write the changelog**

In `packages/python/pyproject.toml` set `version = "2.0.0"`. Run `npm version 2.0.0 --no-git-tag-version --prefix packages/typescript`.

`CHANGELOG.md`:

```markdown
# Changelog

## 2.0.0

Data rebuilt by the new `qc2c-build` pipeline (`workflow/`), validated against the source borders.

1. Points at sea return the nearest country instead of `None`.
2. United States points return `USA` instead of state codes.
3. Small countries (Vatican, San Marino, Monaco, Liechtenstein) resolve to themselves instead of their neighbour.
4. Areas without an ISO code use the codes in `workflow/data/input/code_overrides.json`, for example `XKX` for Kosovo.
5. Alaska is back.

## 1.1.0

Libraries read the bundled manifest and multipolygon sector files correctly; Python gained `coordinates_to_country`. Not published.
```

- [ ] **Step 7: Gate and commit**

Run: `task quality:gate`
Expected: all PASS.

```bash
task git:commit -- "feat!: ship 2.0.0 data from qc2c-build

Sea returns the nearest country, US points return USA, microstates resolve
to themselves. Both library suites check the shared pipeline fixture."
```

### Task 11: CI and release gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `workflow:test`, `workflow:build`, `workflow:validate`, `workflow:check`.

- [ ] **Step 1: Resolve pinned actions**

```bash
gh api repos/go-task/setup-task/releases/latest -q .tag_name
gh api repos/go-task/setup-task/commits/<tag from previous command> -q .sha
```

The checkout pin already in `release.yml` is `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`.

- [ ] **Step 2: Write `.github/workflows/ci.yml`** (substitute the setup-task SHA and tag)

```yaml
# Runs every test suite in Docker, rebuilds the data and checks the packages ship that build.
name: ci

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: true
      - uses: go-task/setup-task@<SETUP_TASK_SHA> # <SETUP_TASK_TAG>
      - run: task workflow:test
      - run: task workflow:build
      - run: task workflow:validate
      - run: task workflow:check
```

- [ ] **Step 3: Gate publishing on validation in `release.yml`**

Add this job after `permissions:` / before `build-python:`:

```yaml
  validate-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: true
      - uses: go-task/setup-task@<SETUP_TASK_SHA> # <SETUP_TASK_TAG>
      - run: task workflow:build
      - run: task workflow:validate
      - run: task workflow:check
```

Change `publish-pypi` to `needs: [build-python, validate-data]` and `publish-npm` to `needs: [build-npm, validate-data]`. Add `.github/workflows` file purpose `"ci.yml" = "Pull request gate: Docker test suites, data build, validation and package data check."` to `docs/folder-purposes.toml`, then refresh READMEs with the folder README tool.

- [ ] **Step 4: Verify locally and commit**

Run: `task quality:gate`
Expected: all PASS. The workflows themselves run on the pull request.

```bash
task git:commit -- "ci: run Docker test suites and data validation on pull requests and releases"
```

### Task 12: Documentation

**Files:**
- Modify: `README.md`, `workflow/README.md`, `packages/python/README.md`, `packages/typescript/README.md`, `workflow/data/input/README.md`, `workflow/data/output/README.md`, `CLAUDE.md`

- [ ] **Step 1: Root README**

Replace the `## Limits` section body with:

```markdown
QC2C approximates borders. Every point on Earth returns a country: points at sea return the nearest one. Results can be wrong close to a border; the build validates that points farther than about a quarter of a degree from any other country always resolve correctly, and reports accuracy near borders in `validation.json`.

The project takes no political position. It does not move borders or decide who owns disputed land; it follows its source data, and areas without an ISO code use the codes in [code_overrides.json](workflow/data/input/code_overrides.json). Keep political views out of issues, commits and pull requests.
```

In `## How it works`, replace the last paragraph with:

```markdown
The data comes from the [build pipeline](workflow/README.md), which gives sea to the nearest country, simplifies shared borders once so neighbours never gap or overlap, and checks the result against the source borders before anything ships.
```

In `## Repository`, replace the Task paragraph with:

```markdown
Everything runs in Docker through [Task](https://taskfile.dev): `task workflow:build`, `task workflow:validate`, `task workflow:publish` and `task workflow:test`. A machine needs only Docker and Task. Shared tooling comes from Crepidoma, checked out as a submodule:
```

In `## Quick start`, change the Python ocean example comment to `# nearest country for open ocean` and its value to the code from Task 10.

- [ ] **Step 2: Rewrite `workflow/README.md`**

```markdown
# Workflow

`qc2c-build` turns source country borders into the sector files shipped by the [Python](../packages/python/README.md) and [TypeScript](../packages/typescript/README.md) packages, then proves the result still matches the source.

## Run

Everything runs in Docker Compose; you need Docker and [Task](https://taskfile.dev).

```bash
task workflow:build                  # writes workflow/data/output/latest
task workflow:validate               # checks it against the source borders
task workflow:publish                # copies it into both packages and rebuilds dist
task workflow:test                   # pipeline, Python and Node suites in parallel
task workflow:preview                # draws latest/preview.png
```

Pass settings after `--`, for example `task workflow:build -- --tolerance 0.1 --out coarse`, then `task workflow:validate -- --tolerance 0.1 --out coarse`.

## Stages

1. **Load.** Reads `countries.json`, applies [code_overrides.json](data/input/code_overrides.json) to areas without an ISO code, repairs invalid shapes and dissolves entries that share a code.
2. **Partition.** Gives every sea point to the nearest country through Voronoi cells of the coastlines, so coastlines disappear from the data.
3. **Simplify.** Simplifies shared borders once, so neighbours never gap or overlap, snaps to the output grid and restores microstates that would vanish.
4. **Sectors.** Clips to the sector boxes in [world_sectors.json](data/input/world_sectors.json), cuts holes so first-match lookup is exact, and computes country centers.
5. **Write.** Writes JSON and gzip files plus `build.json` with the settings, input hashes and library versions.

## Settings

Defaults live in [qc2c.toml](qc2c.toml). Environment variables `QC2C_<NAME>` override them, and flags override both.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--tolerance` | 0.05 | Border simplification in degrees |
| `--decimals` | 3 | Coordinate decimals in the output |
| `--presimplify` | 0.01 | Simplification before the sea partition |
| `--voronoi-spacing` | 0.25 | Coastline sampling for the sea partition, degrees |
| `--sea` | nearest | `nearest`, or `distance` to return no country far from land |
| `--sea-distance-km` | 200 | Distance limit for `--sea distance` |
| `--us-states` / `--no-us-states` | off | Return US state codes instead of `USA` |
| `--sectors` | world_sectors.json | Sector boxes, which must tile the world |
| `--overrides` | code_overrides.json | Codes for areas without an ISO code |
| `--out` | latest | Output folder name |
| `--samples` | 40 | Random interior test points per country |
| `--min-border-accuracy` | see qc2c.toml | Required accuracy near borders |
| `--seed` | 1 | Seed for test points |

## Validation

Every source vertex and 40 random interior points per country are looked up in the output. Points farther from any other country than `2 * (presimplify + tolerance + grid + 0.001) + voronoi_spacing / 2` degrees must return their own code; points on a shared border are not scored; points in between must reach `min_border_accuracy`. Every source code must appear in the output. Results go to `validation.json`, and a sample of 500 safe points goes to `points.json`, which both library test suites check.

## Without Docker

```bash
uv run --project workflow --all-extras qc2c-build build --input-dir workflow/data/input --output-dir workflow/data/output --config workflow/qc2c.toml
```

Only the Docker build is the reference; `task workflow:check` compares the package data with it.
```

- [ ] **Step 3: Package READMEs**

In both `packages/python/README.md` and `packages/typescript/README.md`, replace note 2 under `## Notes` with:

```markdown
2. Points at sea return the nearest country, and United States points return `USA`.
```

and add note 4:

```markdown
4. The data is built and validated by the [workflow](https://github.com/Levia-Labs/QC2C/tree/main/workflow).
```

Change the Python README ocean example line to `coordinates_to_country({"lat": 0.0, "lng": -140.0})     # nearest country for open ocean`.

- [ ] **Step 4: CLAUDE.md**

Replace `## Stack` item 1 with `1. Python (setuptools package, uv-managed qc2c-build pipeline), TypeScript (npm); Docker Compose runs the pipeline and all test suites.` and add to `## Commands`: `2. task workflow:test, workflow:build, workflow:validate, workflow:publish, workflow:check.`

- [ ] **Step 5: Humanize, gate, commit**

Run the humanizer skill over the changed README prose. Run `uv run --no-project python .crepidoma/tools/folder_readme.py update`, then `task quality:gate`.
Expected: all PASS.

```bash
task git:commit -- "docs: describe the qc2c-build pipeline, Docker tasks and 2.0.0 behaviour"
```

- [ ] **Step 6: Open the pull request**

```bash
gh pr create --base main --head pipeline-rebuild --fill
```

Expected: PR URL printed; `ci` runs on it.
