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
    simplified = simplify_partition(parts, features, cfg)
    mark("simplify")
    files, manifest = split_into_sectors(simplified, features, sectors, cfg.decimals)
    mark("sectors")
    inputs = ["countries.json", cfg.overrides, cfg.sectors] + (
        ["us_states.json"] if cfg.us_states else []
    )
    meta = {
        "settings": cfg.as_dict(),
        "inputs": {name: _sha256(cfg.input_file(name)) for name in inputs},
        "versions": {
            "shapely": shapely.__version__,
            "geos": shapely.geos_version_string,
            "numpy": numpy.__version__,
        },
        "codes": len({code for sector in files.values() for code in sector}),
        "points": sum(
            len(ring) for sector in files.values() for rings in sector.values() for ring in rings
        ),
        "seconds": timings,
    }
    return write_build(cfg, files, manifest, meta)
