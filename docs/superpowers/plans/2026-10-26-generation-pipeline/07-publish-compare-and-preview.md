# Task 7: Publish, compare and preview

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

Overview, constraints and review focus: [00-overview.md](00-overview.md).
