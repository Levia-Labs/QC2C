"""Read source borders, apply code overrides and dissolve features that share a code."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .config import BuildConfig, ConfigError
from .geom import clamp_to_world, make_coverage, polygonal

NO_CODE = "-99"
# State-file entries that duplicate an ISO country entry in countries.json.
US_TERRITORIES = {"PR": "PRI", "VI": "VIR", "GU": "GUM", "AS": "ASM", "MP": "MNP"}

Feature = tuple[str, BaseGeometry]


class MissingOverride(ConfigError):
    """A source feature has no ISO code and no entry in the override file."""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_code(properties: dict, overrides: dict[str, str]) -> str:
    """Overrides win over ISO_A3, so the override file may remap any area."""
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
        grouped[code].append(clamp_to_world(shape(item["geometry"])))
    if cfg.us_states:
        for item in read_json(cfg.input_file("us_states.json"))["features"]:
            code = item["properties"].get("ISO_A3")
            if code is None:
                name = item["properties"].get("ADMIN", "")
                raise ConfigError(f"state feature {name!r} has no ISO_A3")
            if code not in US_TERRITORIES:
                grouped[code].append(clamp_to_world(shape(item["geometry"])))
    features = [(code, polygonal(shapely.union_all(grouped[code]))) for code in sorted(grouped)]
    return _remove_overlaps([(code, geom) for code, geom in features if not geom.is_empty])


def _remove_overlaps(features: list[Feature]) -> list[Feature]:
    """Earlier codes keep overlapped area; the result is a valid coverage."""
    return make_coverage(features)
