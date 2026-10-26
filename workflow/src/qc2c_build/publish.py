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
