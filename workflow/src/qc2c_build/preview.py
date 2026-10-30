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
                axes.add_patch(
                    Polygon(
                        [(lng, lat) for lat, lng in ring],
                        closed=True,
                        facecolor=_color(code),
                        edgecolor="black",
                        linewidth=0.1,
                    )
                )
        lat_min, lng_min, lat_max, lng_max = entry["bounds"]
        axes.add_patch(
            Rectangle(
                (lng_min, lat_min),
                lng_max - lng_min,
                lat_max - lat_min,
                fill=False,
                edgecolor="red",
                linewidth=0.8,
            )
        )
    axes.set_xlim(-180, 180)
    axes.set_ylim(-90, 90)
    axes.set_aspect("equal")
    axes.axis("off")
    out = build / "preview.png"
    figure.savefig(out, bbox_inches="tight")
    plt.close(figure)
    return out
