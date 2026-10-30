# Task 1: Project scaffold and settings

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

Write the file exactly as given in [01a-test-world-conftest.md](01a-test-world-conftest.md).

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
    assert (
        load_config(toml, env={"QC2C_TOLERANCE": "0.2"}, cli={"tolerance": "0.3"}).tolerance == 0.3
    )


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


@pytest.mark.parametrize(
    "bad",
    [
        {"sea": "ocean"},
        {"out": "../x"},
        {"decimals": 9},
        {"tolerance": -1},
        {"samples": 0},
        {"min_border_accuracy": 1.5},
    ],
)
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


def load_config(
    toml_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    cli: Mapping[str, Any] | None = None,
) -> BuildConfig:
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
Each point is classified by its distance `d` to the nearest source geometry of a _different_ code (source coverage after overrides):

1. "Ambiguous" when `d < 1e-9`: the point lies on a shared border and belongs to both codes. Not scored.
2. "Core" when `d` exceeds `2 * (presimplify + tolerance + 10^-decimals + 0.001) + voronoi_spacing / 2`. The doubling and the spacing term cover sea that the Voronoi step can hand to a neighbour within one boundary spacing.
3. "Border band" otherwise.
```

In the Tasks table replace `task workflow:check` row text with `compare the latest build with the published package data` and replace `task test` with `task workflow:test`. Under Data flow step 4 add: `Polygons with holes are cut into hole-free pieces, so first-match lookup is exact in any order.`

- [ ] **Step 8: Commit**

```bash
task git:commit -- "feat(workflow): add qc2c-build project and settings"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
