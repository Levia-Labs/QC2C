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
