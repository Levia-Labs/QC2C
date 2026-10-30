# Task 1, Step 2: workflow/tests/conftest.py

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

TWO_SECTORS = {
    "world_sector_1.json": [0, -180, 90, 180],
    "world_sector_2.json": [-90, -180, 0, 180],
}


def square(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def feature(code: str, name: str, *polygons: list[list[list[float]]]) -> dict:
    """One GeoJSON feature; each polygon is a list of rings, the first one outer."""
    if len(polygons) == 1:
        geometry = {"type": "Polygon", "coordinates": polygons[0]}
    else:
        geometry = {"type": "MultiPolygon", "coordinates": list(polygons)}
    return {"type": "Feature", "properties": {"ADMIN": name, "ISO_A3": code}, "geometry": geometry}


def write_inputs(
    folder: Path,
    countries: list[dict],
    states: list[dict] | None = None,
    overrides: dict | None = None,
    sectors: dict | None = None,
) -> None:
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
    return BuildConfig(
        input_dir=inputs,
        output_dir=tmp_path / "output",
        packages_dir=tmp_path / "packages",
        presimplify=0.0,
        voronoi_spacing=1.0,
        samples=10,
    )
```
