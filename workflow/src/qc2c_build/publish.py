"""Copy a validated build into both packages and the website folder, or report how they differ from it."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .config import BuildConfig
from .write import dump

TARGETS = ("python/qc2c/data", "typescript/src/data")
FIXTURE = "fixtures/points.json"
WEB = "web"
WEB_KEEP = ("README.md",)
WEB_SETTINGS = ("tolerance", "decimals", "presimplify", "voronoi_spacing", "sea", "sea_distance_km", "us_states")

Content = Path | bytes


class PublishError(Exception):
    """The build is missing, unvalidated or failed validation."""


def _read_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise PublishError(f"no {path.name} in {path.parent}; {what}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise PublishError(f"malformed {path.name}: {error}") from error
    if not isinstance(data, dict):
        raise PublishError(f"malformed {path.name}: expected an object")
    return data


def _version(cfg: BuildConfig) -> str:
    path = cfg.packages_dir / "typescript" / "package.json"
    try:
        version = json.loads(path.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise PublishError(f"cannot read the version from {path}") from error
    if not isinstance(version, str):
        raise PublishError(f"package.json version in {path} is not a string")
    return version


def _web_plan(cfg: BuildConfig, with_metadata: bool) -> list[tuple[Content, str]]:
    """(content, file name) for everything publish writes into web_dir."""
    build = cfg.build_dir
    plan: list[tuple[Content, str]] = []
    manifest = json.loads((build / "world_sectors.json").read_text(encoding="utf-8"))
    renamed = {key.removesuffix(".gz"): value for key, value in manifest.items()}
    plan.append((dump(renamed), "world_sectors.json"))
    for source in sorted(build.glob("world_sector*")):
        if source.name != "world_sectors.json" and source.suffix in (".json", ".gz"):
            plan.append((source, source.name))
    if (build / "preview.png").is_file():
        plan.append((build / "preview.png", "preview.png"))
    if with_metadata:
        plan.append((_metadata(cfg, plan), "qc2c.json"))
    return plan


def _size(content: Content) -> int:
    return len(content) if isinstance(content, bytes) else content.stat().st_size


def _metadata(cfg: BuildConfig, plan: list[tuple[Content, str]]) -> bytes:
    build = _read_json(cfg.build_dir / "build.json", "run build first")
    report = _read_json(cfg.build_dir / "validation.json", "run validate first")
    accuracy = report.get("accuracy", {})
    meta = {
        "name": "qc2c",
        "version": _version(cfg),
        "codes": build.get("codes"),
        "points": build.get("points"),
        "gzip_total": build.get("gzip_total"),
        "files": {name: _size(content) for content, name in plan},
        "settings": {key: build.get("settings", {}).get(key) for key in WEB_SETTINGS},
        "validation": {
            "passed": report.get("passed"),
            "core": accuracy.get("core"),
            "border": accuracy.get("border"),
            "overall": accuracy.get("overall"),
            "counts": report.get("counts"),
        },
        "inputs": build.get("inputs"),
    }
    return (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _planned(cfg: BuildConfig) -> list[tuple[Content, Path, str]]:
    """(content, destination, label) for everything publish writes; labels are relative to the repo's packages."""
    sources = sorted(p for p in cfg.build_dir.glob("world_sector*") if p.suffix in (".json", ".gz"))
    plan: list[tuple[Content, Path, str]] = []
    for target in TARGETS:
        for source in sources:
            folder = "gz" if source.suffix == ".gz" else "json"
            label = f"{target}/{folder}/{source.name}"
            plan.append((source, cfg.packages_dir / label, label))
    plan.append((cfg.build_dir / "points.json", cfg.packages_dir / FIXTURE, FIXTURE))
    return plan


def _web_labelled(cfg: BuildConfig, with_metadata: bool = True) -> list[tuple[Content, Path, str]]:
    return [(content, cfg.web_dir / name, f"{WEB}/{name}") for content, name in _web_plan(cfg, with_metadata)]


def _atomic_copy(items: list[tuple[Content, Path]]) -> None:
    """Write every item to <dest>.tmp, then rename all into place; on failure remove the temporaries."""
    temporaries: list[tuple[Path, Path]] = []
    try:
        for content, destination in items:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".tmp")
            temporaries.append((temporary, destination))
            if isinstance(content, bytes):
                temporary.write_bytes(content)
            else:
                shutil.copyfile(content, temporary)
    except BaseException:
        for temporary, _ in temporaries:
            temporary.unlink(missing_ok=True)
        raise
    for temporary, destination in temporaries:
        os.replace(temporary, destination)


def _stale_files(cfg: BuildConfig, kept: set[Path]) -> list[Path]:
    stale = []
    for target in TARGETS:
        for folder in ("json", "gz"):
            stale += [old for old in (cfg.packages_dir / target / folder).glob("world_sector*") if old not in kept]
    if cfg.web_dir.is_dir():
        stale += [old for old in cfg.web_dir.iterdir()
                  if old.is_file() and old.name not in WEB_KEEP and old not in kept]
    return stale


def publish(cfg: BuildConfig) -> list[Path]:
    report = _read_json(cfg.build_dir / "validation.json", "run validate first")
    if report.get("passed") is not True:
        raise PublishError("validation failed; not publishing")
    planned = _planned(cfg)
    for source, _, _ in planned:
        if isinstance(source, Path) and not source.is_file():
            raise PublishError(f"build file missing: {source}")
    _version(cfg)
    from .preview import render

    try:
        render(cfg)
    except ImportError as error:
        raise PublishError(f"publish renders preview.png and needs matplotlib: {error}") from error
    planned += _web_labelled(cfg)
    _atomic_copy([(content, destination) for content, destination, _ in planned])
    written = [destination for _, destination, _ in planned]
    for old in _stale_files(cfg, set(written)):
        old.unlink()
    return written


def compare(cfg: BuildConfig) -> list[str]:
    """Package and web paths whose bytes differ from the build, plus shipped files the build lacks."""
    planned = _planned(cfg)
    # a build without a preview says nothing about web/preview.png
    web_known = (cfg.build_dir / "preview.png").is_file()
    planned += _web_labelled(cfg)
    diffs = []
    for content, destination, label in planned:
        expected = content if isinstance(content, bytes) else content.read_bytes()
        if not destination.is_file() or destination.read_bytes() != expected:
            diffs.append(label)
    expected_labels = {label for _, _, label in planned}
    for old in _stale_files(cfg, {destination for _, destination, _ in planned}):
        label = (f"{WEB}/{old.name}" if old.parent == cfg.web_dir
                 else old.relative_to(cfg.packages_dir).as_posix())
        if label == f"{WEB}/preview.png" and not web_known:
            continue
        if label not in expected_labels:
            diffs.append(label)
    return sorted(diffs)
