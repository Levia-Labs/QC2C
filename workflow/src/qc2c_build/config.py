"""Build settings: defaults, then qc2c.toml, then QC2C_* environment variables, then CLI flags."""

from __future__ import annotations

import math
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
    web_dir: Path = Path("../web")

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, float) and not math.isfinite(value):
                raise ConfigError(f"{field.name} must be a finite number, got {value!r}")
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
    if (
        isinstance(default, int)
        and isinstance(value, bool | float)
        and (isinstance(value, bool) or not value.is_integer())
    ):
        raise ConfigError(f"{name} must be a whole number, got {value!r}")
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
        try:
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as error:
            raise ConfigError(f"cannot read {toml_path}: {error}") from error
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
