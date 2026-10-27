# Workflow

`qc2c-build` turns source country borders into the sector files shipped by the [Python](../packages/python/README.md) and [TypeScript](../packages/typescript/README.md) packages, then checks that the result still matches the source.

## Run

Everything runs in Docker Compose; you need Docker and [Task](https://taskfile.dev).

```bash
task workflow:build                  # writes workflow/data/output/latest
task workflow:validate               # checks it against the source borders
task workflow:publish                # copies it into both packages and rebuilds dist
task workflow:test                   # pipeline, Python and Node suites in parallel
task workflow:preview                # draws latest/preview.png
```

Pass settings after `--`, for example `task workflow:build -- --tolerance 0.1 --out coarse`, then `task workflow:validate -- --tolerance 0.1 --out coarse`.

## Stages

1. **Load.** Reads `countries.json`, applies [code_overrides.json](data/input/code_overrides.json) to areas without an ISO code, repairs invalid shapes, clamps coordinates to the world and builds an exact coverage, so neighbours share identical borders.
2. **Partition.** Gives every sea point to the nearest country through Voronoi cells of the coastlines, so coastlines disappear from the data.
3. **Simplify.** Simplifies shared borders once, so neighbours never gap or overlap, snaps to the output grid and restores the land of microstates that simplification would swallow.
4. **Sectors.** Clips to the sector boxes in [world_sectors.json](data/input/world_sectors.json), cuts holes so first-match lookup is exact, and computes country centers.
5. **Write.** Writes JSON and gzip files plus `build.json` with the settings, input hashes and library versions.

## Settings

Defaults live in [qc2c.toml](qc2c.toml). Environment variables `QC2C_<NAME>` override them, and flags override both.

| Meaning | Flag | Default |
| --- | --- | --- |
| Border simplification in degrees | `--tolerance` | 0.05 |
| Coordinate decimals in the output | `--decimals` | 3 |
| Simplification before the sea partition | `--presimplify` | 0.01 |
| Coastline sampling for the sea partition, degrees | `--voronoi-spacing` | 0.25 |
| Sea mode: `nearest`, or `distance` to return no country far from land | `--sea` | nearest |
| Distance limit for `--sea distance` | `--sea-distance-km` | 200 |
| Return US state codes instead of `USA` | `--us-states` / `--no-us-states` | off |
| Sector boxes, which must tile the world | `--sectors` | world_sectors.json |
| Codes for areas without an ISO code | `--overrides` | code_overrides.json |
| Output folder name | `--out` | latest |
| Random interior test points per country | `--samples` | 40 |
| Required accuracy near borders | `--min-border-accuracy` | see qc2c.toml |
| Seed for test points | `--seed` | 1 |

## Validation

Every source vertex and a number of random interior points per country (`samples`, default 40) are looked up in the output. Points farther from any other country than `2 * (presimplify + tolerance + grid + 0.001) + voronoi_spacing / 2` degrees must return their own code; points on a shared border are not scored; points in between must reach `min_border_accuracy`. Every source code must appear in the output. Results go to `validation.json`, and up to 500 safe fixture points go to `points.json`, which both library test suites check.

## Website bundle

`task workflow:publish` also writes the top-level `web/` folder (plain-JSON manifest, gz copies, `qc2c.json` metadata, `preview.png`) that the Levia Labs website copies; see `web/README.md`.

## Without Docker

```bash
uv run --project workflow --all-extras qc2c-build build --input-dir workflow/data/input --output-dir workflow/data/output --config workflow/qc2c.toml
```

Only the Docker build is the reference; `task workflow:check` compares the package data with it.
