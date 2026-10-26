# Workflow

Data pipeline that turns raw country borders into the compact sector files shipped by the [Python](../packages/python/README.md) and [TypeScript](../packages/typescript/README.md) packages.

## Stages

Each stage reads the previous stage's output from [data/output](data/output) and writes its own folder.

| Stage | Status | What it does |
| --- | --- | --- |
| [1](scripts/stage_1/README.md) | done | Builds the base map, simplifies each country with convex hull and `simplify`, merges non-intersecting countries and splits the world into sectors. |
| [2](scripts/stage_2/README.md) | done | Removes border points that change neither area nor intersections. |
| [3](scripts/stage_3/README.md) | done | Minifies the JSON to ASCII and gzips it. |
| [4](scripts/stage_4/README.md) | done | Adds each country's center to the sector manifest. |
| [5](scripts/stage_5/README.md) | planned | Merges self-overlapping polygons within each country. |
| [6](scripts/stage_6/README.md) | planned | Simplifies with Voronoi diagrams so every piece of land belongs to a country. |

Stages 3 and later produce `.json.gz` files. Gzip was chosen because browsers decompress it natively; Brotli might be smaller but is less widely supported for this use.

## Run

Inputs live in [data/input](data/input): `countries.json`, `us_states.json` and the `world_sectors.json` manifest. Stage scripts need `shapely` and `tqdm`; the preview also needs `geopandas` and `matplotlib`.

```bash
python workflow/scripts/stage_1/main.py
python workflow/scripts/preview_world_sectors.py  # optional: check the sector map for artifacts
```

Stage 1 took about 900 seconds on 2023-12-24.

## Roadmap

1. Represent islands as rectangles or triangles when they intersect nothing else, and straighten shore lines.
2. Use Voronoi diagrams to build separation regions between countries (stage 6).
3. Verify output against input: every coordinate assigned to a country in the input must map to the same country in the output. Build the test set from tricky pairs (enclaves, irregular borders) and from a grid of land points.

Done: shore line reduction (stage 2).
