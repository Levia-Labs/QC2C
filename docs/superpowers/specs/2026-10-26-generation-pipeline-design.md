# Generation pipeline rebuild

Date: 2026-10-26. Status: approved design, pending spec review.

## Goal

Replace the staged scripts in `workflow/scripts` with one parametrized build that turns the source borders into the sector files shipped by both packages, proves the output still matches the source, and runs the same way on any machine through Docker Compose.

## Decisions

1. Sea points return the nearest country. A `distance` sea mode returns `None` beyond a set distance from land.
2. The United States returns `USA`. A `--us-states` option builds a dataset with state codes instead.
3. Source entries without an ISO code (`ISO_A3 = "-99"`) get codes from an editable override file.
4. Default simplification tolerance is 0.05 degrees with 3 decimal places, about 222 KB gzipped.
5. Docker Compose is the reference engine. Native `uv run` stays available for development.
6. Behavior changes for ocean and US points, so both packages move to 2.0.0.

## Measurements behind the decisions

Taken with throwaway probes on 40 random interior points per source feature (small features count as much as large ones).

| Method | gzip | Sample accuracy | Area-weighted |
| --- | --- | --- | --- |
| Shipped data today | 308 KB | 89.98% | not measured |
| Coverage simplify, real coastlines, tol 0.05 | 543 KB | 92.01% | not measured |
| Nearest-country sea partition, tol 0.05 | 222 KB | 97.80% | 99.962% |
| Nearest-country sea partition, tol 0.1 | 163 KB | 97.29% | 99.936% |

Failures in today's data come from convex-hull merging (San Marino and Vatican return ITA, Monaco FRA, Liechtenstein CHE), 17 `-99` entries overwriting each other, Alaska deleted at `stage_1/main.py:187`, and US territory codes overlapping ISO entries.

## Architecture

`workflow/` becomes a uv project (`workflow/pyproject.toml`, `workflow/uv.lock`) with the package `workflow/src/qc2c_build/` and the console script `qc2c-build`. Runtime dependencies: `shapely>=2.1,<3`, `numpy`. Optional `preview` extra: `matplotlib`. Every module stays under 300 lines.

| Module | Responsibility |
| --- | --- |
| `config.py` | `BuildConfig` dataclass; merges defaults, `workflow/qc2c.toml`, `QC2C_*` environment variables and CLI flags, in that order of increasing precedence; validates that sector boxes tile the world. |
| `load.py` | Reads GeoJSON inputs, applies the override file, chooses USA or states, repairs geometry with `make_valid`, dissolves features sharing a code. |
| `partition.py` | Pre-simplifies the land coverage, assigns sea to the nearest country through Voronoi cells of densified boundary points, optionally clips sea to a distance from land. |
| `simplify.py` | `coverage_simplify` at the configured tolerance, then `set_precision` to the configured decimals, then validity repair. |
| `sectors.py` | Clips the partition to each sector box, orders countries by ascending area so enclaves win first-match lookup, computes one center per country per sector from the representative point of its land. |
| `write.py` | Writes the manifest and sector files as JSON and gzip plus `build.json` to the output folder. |
| `validate.py` | Builds the point set, checks the output, writes `validation.json` and the shared library fixture. |
| `publish.py` | Copies the latest build into both packages. |
| `cli.py` | Subcommands `build`, `validate`, `publish`, `preview`. |

The old `workflow/scripts/`, `workflow/test/` and `workflow/data/output/stage_1..4` are removed; git history keeps them.

## Data flow

1. `load`: `countries.json` (and `us_states.json` with `--us-states`) to a list of `(code, geometry)`.
2. `partition`: land coverage to a full-plane coverage in which every country owns its land plus its nearest sea.
3. `simplify`: shared borders simplified once, so neighbors never gap or overlap.
4. `sectors`: per-sector dictionaries of code to rings. Polygons with holes are cut into hole-free pieces, so first-match lookup is exact in any order.
5. `write`: `workflow/data/output/<name>/` (default `latest`) containing `world_sectors.json`, `world_sectors.json.gz`, `world_sector_N.json`, `world_sector_N.json.gz`, `build.json`.
6. `validate`: reads the output and the source, writes `validation.json` and `fixtures/points.json` into the same folder.
7. `publish`: copies JSON and gzip files into `packages/python/qc2c/data/{json,gz}` and `packages/typescript/src/data/{json,gz}`, and the fixture into `packages/fixtures/points.json`.

## Output format

Unchanged, so the libraries keep working:

1. Manifest: `{"world_sector_N.json.gz": {"bounds": [lat_min, lng_min, lat_max, lng_max], "center": {code: [lat, lng]}}}`.
2. Sector file: `{code: [[[lat, lng], ...], ...]}`, outer rings only.
3. Countries appear in ascending area order. Because the partition covers the plane, every hole in a polygon is filled by another country, so first-match lookup over that order is exact. In `distance` sea mode, enclosed open-sea holes are dropped and validation reports any effect.
4. `build.json` records the settings, the SHA-256 of each input file, shapely and GEOS versions, sizes and point counts.

## Code overrides

`workflow/data/input/code_overrides.json` maps source `ADMIN` names to output codes. Defaults follow the source data: territories of a sovereign state take its ISO code, disputed areas keep Natural Earth's own non-ISO codes, and Kosovo uses `XKX`.

| ADMIN | Code |
| --- | --- |
| Ashmore and Cartier Islands, Coral Sea Islands, Indian Ocean Territories | AUS |
| Clipperton Island | FRA |
| Dhekelia Sovereign Base Area, Akrotiri Sovereign Base Area | GBR |
| Baykonur Cosmodrome | KAZ |
| US Naval Base Guantanamo Bay | CUB |
| Kosovo | XKX |
| Northern Cyprus | CYN |
| Cyprus No Mans Area | CNM |
| Somaliland | SOL |
| Siachen Glacier | KAS |
| Spratly Islands | PGA |
| Scarborough Reef | SCR |
| Bajo Nuevo Bank (Petrel Is.) | BJN |
| Serranilla Bank | SER |

The build fails if any `-99` entry has no override. With `--us-states`, the state file's territory entries (`PR`, `VI`, `GU`, `AS`, `MP`) are dropped in favor of the ISO entries `PRI`, `VIR`, `GUM`, `ASM`, `MNP`, and the `USA` country entry is replaced by the remaining states.

## Settings

| Setting | Flag | Default |
| --- | --- | --- |
| Simplification tolerance (degrees) | `--tolerance` | 0.05 |
| Coordinate decimals | `--decimals` | 3 |
| Pre-simplification before partition | `--presimplify` | 0.01 |
| Boundary densification for Voronoi (degrees) | `--voronoi-spacing` | 0.25 |
| Sea mode | `--sea nearest\|distance` | nearest |
| Sea distance (km), `distance` mode only | `--sea-distance-km` | 200 |
| US states instead of USA | `--us-states` | off |
| Sector boxes | `--sectors <file>` | the six boxes in `workflow/data/input/world_sectors.json` |
| Override file | `--overrides <file>` | `workflow/data/input/code_overrides.json` |
| Output name | `--out` | latest |
| Interior samples per country | `--samples` | 40 |
| Minimum border-band accuracy | `--min-border-accuracy` | measured on the first full build (see Validation) |
| Random seed | `--seed` | 1 |

The same settings are keys in `workflow/qc2c.toml` and `QC2C_<UPPER_NAME>` environment variables.

## Validation

Point set: every vertex of every source polygon, plus `--samples` seeded random interior points per country so microstates are always covered.

Each point is classified by its distance `d` to the nearest source geometry of a *different* code (source coverage after overrides):

1. "Ambiguous" when `d < 1e-9`: the point lies on a shared border and belongs to both codes. Not scored.
2. "Core" when `d` exceeds `2 * (presimplify + tolerance + 10^-decimals + 0.001) + voronoi_spacing / 2`. The doubling and the spacing term cover sea that the Voronoi step can hand to a neighbour within one boundary spacing.
3. "Border band" otherwise.

Hard checks, any failure exits non-zero:

1. Every core point returns its source code.
2. Every output code appears in the source after overrides, and every source code appears in the output.
3. Border-band accuracy is at least `min_border_accuracy`. Its default is set from the first full build with default settings, rounded down to a whole percent, and recorded in `workflow/qc2c.toml`; it may only be raised afterwards.
4. Every sector file and the manifest parse, and sector boxes tile the world without overlap.

Reported in `validation.json`: counts, overall, core and border-band accuracy, per-code accuracy, and the ten worst codes.

The fixture `points.json` holds up to 500 seeded core points with expected codes for the library test suites.

## Docker engine

`workflow/Dockerfile`: `python:3.12-slim` pinned by digest, `uv` copied from `ghcr.io/astral-sh/uv` pinned by digest, `uv sync --frozen` into `UV_PROJECT_ENVIRONMENT=/opt/venv` so source mounts over `/app` do not hide the environment, non-root user, entry point `qc2c-build`. No system packages; shapely wheels bundle GEOS. Dev dependencies (`pytest`, `hypothesis`) live in a `dev` group installed in the same image.

`compose.yaml` at the repo root:

| Service | Image | Mounts | Command |
| --- | --- | --- | --- |
| `build` | workflow | `workflow/data/input:/data/input:ro`, `workflow/data/output:/data/output`, `workflow/qc2c.toml:/app/qc2c.toml:ro` | `build` |
| `validate` | workflow | same as `build` | `validate` |
| `publish` | workflow | output `:ro`, both package `data/` folders, `packages/fixtures` | `publish` |
| `preview` | workflow (preview extra) | output | `preview` (PNG, headless) |
| `test-pipeline` | workflow | `workflow:/app:ro` | `pytest` |
| `test-python` | workflow | `packages/python:/pkg:ro`, `packages/fixtures:ro` | `pytest` |
| `test-node` | `node:24` pinned by digest | `packages/typescript`, `packages/fixtures:ro` | `npm ci && npm run build && npm test` |

Services set `user: "${UID:-1000}:${GID:-1000}"` so Linux hosts get files they own. `workflow/data/output/` is gitignored except its README; the tracked copies of the data live in the packages.

## Tasks

| Task | Runs |
| --- | --- |
| `task workflow:build -- <flags>` | `docker compose run --rm build build <flags>` |
| `task workflow:validate -- <flags>` | `docker compose run --rm validate validate <flags>` |
| `task workflow:publish` | `publish`, then `test-node` to rebuild `dist` |
| `task workflow:preview` | `preview` |
| `task workflow:check` | compare the latest build with the published package data |
| `task workflow:test` | `test-pipeline`, `test-python` and `test-node` in parallel; fails if any fails |

## Testing

1. Pipeline unit tests on synthetic squares, under 2 seconds in total: enclave inside a host, neighbors with a shared border, island across a strait, country spanning a sector edge, override applied, missing override fails, USA versus states, sector boxes that do not tile fail.
2. Property tests with Hypothesis: rounding never moves a point more than half a unit in the last decimal; clipping to a box partition preserves total area within float tolerance.
3. Library suites (pytest and jest) load `packages/fixtures/points.json` and assert every expected code, which proves both libraries agree with the pipeline.
4. Full validation on the real data runs in `ci.yml` and in `release.yml` before publishing.
5. `ci.yml` on pull requests: `task test`, `task workflow:validate` on a fresh build, `task workflow:check`.

## Versioning and docs

1. Both packages move to 2.0.0, with `CHANGELOG.md` entries describing the ocean and USA changes.
2. Root, package and workflow READMEs are updated for sea behavior, USA, overrides, settings and the Docker workflow.
3. The workflow README roadmap closes: the Voronoi separation and tests are implemented; the rectangle idea is superseded by the sea partition.

## Out of scope

1. Changing the library API or file format.
2. Adding languages beyond Python and TypeScript.
3. Updating the source border data.
