"""Check a build against the source borders; write validation.json and the library fixture."""
from __future__ import annotations

import gzip
import json
import math
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
    geoms_src = np.array([geom for _, geom in features], dtype=object)
    tree = shapely.STRtree(geoms_src)
    geoms = shapely.points(points.xy)
    kind = np.full(len(geoms), CORE, dtype=np.int8)
    point_index, geom_index = tree.query(geoms, predicate="dwithin", distance=width)
    other = codes[geom_index] != points.code[point_index]
    point_index, geom_index = point_index[other], geom_index[other]
    kind[point_index] = BORDER
    touching = shapely.distance(geoms[point_index], geoms_src[geom_index]) <= 1e-9
    kind[point_index[touching]] = AMBIGUOUS
    return kind


def _read(path: Path) -> dict:
    try:
        data = json.loads(gzip.decompress(path.read_bytes()))
    except (OSError, EOFError, ValueError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError(f"{path.name} is not a JSON object")
    return data


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_manifest_entry(key: str, entry) -> None:
    if not isinstance(entry, dict):
        raise ValidationError(f"manifest entry {key} is not an object")
    bounds = entry.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 4 or not all(_number(b) for b in bounds):
        raise ValidationError(f"manifest entry {key} has no valid bounds")
    if not isinstance(entry.get("center"), dict):
        raise ValidationError(f"manifest entry {key} has no valid center")


def _check_sector(key: str, sector: dict) -> None:
    for code, rings in sector.items():
        if not isinstance(rings, list):
            raise ValidationError(f"{key}: {code} is not a list of rings")
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 3:
                raise ValidationError(f"{key}: {code} has a ring that is not a list of at least 3 points")
            for pair in ring:
                if not isinstance(pair, list) or len(pair) != 2 or not all(_number(v) for v in pair):
                    raise ValidationError(f"{key}: {code} has a point that is not a [lat, lng] number pair")


def load_output(build_dir: Path) -> tuple[dict, dict[str, dict]]:
    manifest = _read(build_dir / "world_sectors.json.gz")
    for key, entry in manifest.items():
        _check_manifest_entry(key, entry)
    sector_files = {key: _read(build_dir / key) for key in manifest}
    for key, sector in sector_files.items():
        _check_sector(key, sector)
    return manifest, sector_files


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


def _by_code(index: np.ndarray, codes: np.ndarray) -> dict[str, np.ndarray]:
    names, inverse = np.unique(codes[index], return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    groups = np.split(index[order], np.cumsum(np.bincount(inverse))[:-1])
    return dict(zip(names.tolist(), groups))


def fixture(points: PointSet, kind: np.ndarray, sectors: Sectors, seed: int, size: int = 500,
            got: np.ndarray | None = None) -> list[dict]:
    """Seeded core points, one per code first, none on a sector edge (TypeScript checks one sector).

    A code without a core point falls back to one border point the build resolves to that code (needs got).
    """
    lat, lng = points.xy[:, 1], points.xy[:, 0]
    edges = np.array(list(sectors.values()), dtype=float)
    on_lat = np.isclose(lat[:, None], edges[:, [0, 2]].reshape(1, -1), atol=1e-9).any(axis=1)
    on_lng = np.isclose(lng[:, None], edges[:, [1, 3]].reshape(1, -1), atol=1e-9).any(axis=1)
    free = ~on_lat & ~on_lng
    pool = np.flatnonzero((kind == CORE) & free)
    rng = np.random.default_rng(seed)
    by_core = _by_code(pool, points.code)
    chosen = [int(rng.choice(group)) for _, group in sorted(by_core.items())]
    if got is not None:
        fallback = np.flatnonzero((kind == BORDER) & free & (got == points.code))
        chosen += [int(rng.choice(group)) for code, group in sorted(_by_code(fallback, points.code).items())
                   if code not in by_core]
    rest = np.setdiff1d(pool, chosen)
    extra = rng.choice(rest, size=min(max(size - len(chosen), 0), len(rest)), replace=False)
    picked = sorted(set(chosen) | {int(i) for i in extra})
    return [{"lat": round(float(lat[i]), 6), "lng": round(float(lng[i]), 6), "code": str(points.code[i])}
            for i in picked]


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
    names, inverse = np.unique(points.code, return_inverse=True)
    totals = np.bincount(inverse, weights=scored, minlength=len(names))
    hits = np.bincount(inverse, weights=scored & correct, minlength=len(names))
    per_code = {str(name): {"points": int(total), "accuracy": round(float(hit / total) if total else 1.0, 6)}
                for name, total, hit in zip(names, totals, hits)}
    chosen = fixture(points, kind, sectors, cfg.seed, got=got)
    report = {
        "passed": not failures,
        "failures": failures,
        "band": band(cfg),
        "counts": {"total": len(kind), "core": int(core.sum()), "border": int(border.sum()),
                   "ambiguous": int((kind == AMBIGUOUS).sum())},
        "accuracy": {"overall": _accuracy(correct, scored), "core": _accuracy(correct, core),
                     "border": border_accuracy},
        "worst": sorted(per_code, key=lambda c: (per_code[c]["accuracy"], c))[:10],
        "fixture_size": len(chosen),
        "fixture_missing": sorted(source_codes - {entry["code"] for entry in chosen}),
        "per_code": per_code,
    }
    cfg.build_dir.mkdir(parents=True, exist_ok=True)
    (cfg.build_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    points_json = json.dumps(chosen, separators=(",", ":")) + "\n"
    (cfg.build_dir / "points.json").write_text(points_json, encoding="utf-8")
    return report
