# Generation Pipeline Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `workflow/scripts` with a parametrized, validated `qc2c-build` pipeline that runs in Docker Compose and publishes sector data into both packages.

**Architecture:** A uv project in `workflow/` holds the package `qc2c_build`: load source borders, give sea to the nearest country, simplify shared borders once, split into hole-free rings per sector, write JSON and gzip, validate against the source, publish into the packages. Docker Compose services run every command and test suite; Task wraps Compose.

**Tech Stack:** Python 3.12, shapely 2.1+, numpy, pytest, hypothesis, matplotlib (preview only), Docker Compose v2, Task, Node 24 with jest for the TypeScript package.

**Spec:** `docs/superpowers/specs/2026-10-26-generation-pipeline-design.md`

## Global Constraints

1. Python 3.12+, managed with uv; pass `encoding="utf-8"` to every text read and write.
2. Runtime dependencies: `shapely>=2.1,<3`, `numpy`; optional `preview` extra: `matplotlib`; `dev` group: `pytest`, `hypothesis`.
3. Every source file stays under 300 lines.
4. Output format is unchanged: manifest `{"world_sector_N.json.gz": {"bounds": [lat_min, lng_min, lat_max, lng_max], "center": {code: [lat, lng]}}}`, sector file `{code: [[[lat, lng], ...], ...]}`, outer rings only.
5. Defaults: tolerance 0.05, decimals 3, presimplify 0.01, voronoi spacing 0.25, sea `nearest`, sea distance 200 km, USA (not states), seed 1, 40 samples per country.
6. Sea points return the nearest country; US points return `USA`; `-99` entries take codes from `workflow/data/input/code_overrides.json`.
7. Docker images and GitHub Actions are pinned by digest or commit SHA.
8. Generated data in `packages/*/data` and `packages/typescript/dist` is written only by `qc2c-build publish` and `npm run build`, never by hand.
9. Commit with `task git:commit -- "<message>"` from the repo root, Conventional Commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
10. Packages ship as 2.0.0.

## Spec amendments made by this plan

1. **Core band.** The spec's band `presimplify + tolerance + 10^-decimals + 0.001` does not cover the Voronoi step: sea next to country A can go to country B when B is within about one boundary spacing. The plan uses `2 * (presimplify + tolerance + 10^-decimals + 0.001) + voronoi_spacing / 2`, measured as the distance to the nearest _other_ code's source geometry. Task 1 updates the spec.
2. **Holes.** Instead of relying on area ordering for enclaves, the writer cuts every polygon with holes into hole-free pieces, so first-match lookup is exact whatever the order. Area ordering stays.
3. **Task names.** The Crepidoma submodule already owns the `test` namespace, so the parallel test task is `task workflow:test`, not `task test`. `task workflow:check` compares the latest build with the shipped package data instead of building a second copy.
4. **Modules.** Three small modules are added to the spec's list: `geom.py` (shared polygon helpers), `pipeline.py` (build orchestration) and a `compare` command inside `publish.py`.

## Review Focus

1. Microstates (Vatican, Monaco, San Marino) collapsing under simplification: the code must survive with its own area. Pinned in Task 4 (`test_restore_lost_puts_tiny_code_back`) and by validation check 2.
2. Points exactly on a sector edge: the TypeScript library checks only the first matching sector, so fixture points must avoid sector edges. Pinned in Task 7 (`test_fixture_avoids_sector_edges`).
3. Countries touching the antimeridian (Russia, Fiji, Kiribati) are split at ±180 in the source; both halves must survive partition and clipping. Pinned in Task 3 (`test_antimeridian_halves_survive`).
4. Invalid source geometry (self-intersections) must be repaired, not crash the build. Pinned in Task 2 (`test_invalid_geometry_is_repaired`).
5. A wrong setting or a missing input folder must exit with status 2 and one readable line, not a traceback. Pinned in Task 8 (`test_cli_missing_input_exits_2`, `test_cli_bad_setting_exits_2`).

## File structure

| Path                                                                                 | Responsibility                                              |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| `workflow/pyproject.toml`, `workflow/uv.lock`                                        | Build project, dependencies, `qc2c-build` script            |
| `workflow/qc2c.toml`                                                                 | Checked-in default settings                                 |
| `workflow/src/qc2c_build/config.py`                                                  | `BuildConfig`, settings precedence, validation              |
| `workflow/src/qc2c_build/geom.py`                                                    | `polygonal`, `hole_free`                                    |
| `workflow/src/qc2c_build/load.py`                                                    | Source loading, overrides, USA or states, overlap removal   |
| `workflow/src/qc2c_build/partition.py`                                               | Nearest-country sea partition                               |
| `workflow/src/qc2c_build/simplify.py`                                                | Coverage simplification, grid snapping, microstate restore  |
| `workflow/src/qc2c_build/sectors.py`                                                 | Sector file reading, tiling check, clipping, rings, centers |
| `workflow/src/qc2c_build/write.py`                                                   | JSON, gzip and `build.json` output                          |
| `workflow/src/qc2c_build/pipeline.py`                                                | `run_build`                                                 |
| `workflow/src/qc2c_build/validate.py`                                                | Point set, classification, lookup, report, fixture          |
| `workflow/src/qc2c_build/publish.py`                                                 | `publish`, `compare`                                        |
| `workflow/src/qc2c_build/preview.py`                                                 | Headless PNG preview                                        |
| `workflow/src/qc2c_build/cli.py`                                                     | `qc2c-build` subcommands                                    |
| `workflow/tests/*.py`                                                                | Synthetic-world unit, property and end-to-end tests         |
| `workflow/data/input/code_overrides.json`                                            | `-99` code overrides                                        |
| `workflow/Dockerfile`, `workflow/.dockerignore`, `compose.yaml`                      | Engine                                                      |
| `tasks/workflow.yml`                                                                 | Task wrappers                                               |
| `packages/fixtures/points.json`                                                      | Shared library fixture, written by publish                  |
| `packages/python/tests/test_fixture.py`, `packages/typescript/tests/fixture.test.js` | Library fixture tests                                       |
| `.github/workflows/ci.yml`                                                           | Pull request gate                                           |
| `CHANGELOG.md`                                                                       | 2.0.0 notes                                                 |

Removed: `workflow/scripts/`, `workflow/test/`, `workflow/data/output/stage_1..4/`, `workflow/.gitignore` (replaced).

---

## Tasks

Each task is its own file; execute them in order.

1. [Task 1: Project scaffold and settings](01-project-scaffold-and-settings.md)
2. [Task 2: Geometry helpers and source loading](02-geometry-helpers-and-source-loading.md)
3. [Task 3: Sea partition](03-sea-partition.md)
4. [Task 4: Simplification and microstate restore](04-simplification-and-microstate-restore.md)
5. [Task 5: Sectors, rings and output files](05-sectors-rings-and-output-files.md)
6. [Task 6: Validation of output](06-validation-of-output.md)
7. [Task 7: Publish, compare and preview](07-publish-compare-and-preview.md)
8. [Task 8: Command line](08-command-line.md)
9. [Task 9: Docker engine and Task wrappers](09-docker-engine-and-task-wrappers.md)
10. [Task 10: First full build, publish data, library fixtures, 2.0.0](10-first-full-build-publish-data-library-fixtures-2-0-0.md)
11. [Task 11: CI and release gates](11-ci-and-release-gates.md)
12. [Task 12: Documentation](12-documentation.md)
