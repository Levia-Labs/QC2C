# Task 12: Documentation

**Files:**

- Modify: `README.md`, `workflow/README.md`, `packages/python/README.md`, `packages/typescript/README.md`, `workflow/data/input/README.md`, `workflow/data/output/README.md`, `CLAUDE.md`

- [ ] **Step 1: Root README**

Replace the `## Limits` section body with:

```markdown
QC2C approximates borders. Every point on Earth returns a country: points at sea return the nearest one. Results can be wrong close to a border; the build validates that points farther than about a quarter of a degree from any other country always resolve correctly, and reports accuracy near borders in `validation.json`.

The project takes no political position. It does not move borders or decide who owns disputed land; it follows its source data, and areas without an ISO code use the codes in [code_overrides.json](workflow/data/input/code_overrides.json). Keep political views out of issues, commits and pull requests.
```

In `## How it works`, replace the last paragraph with:

```markdown
The data comes from the [build pipeline](workflow/README.md), which gives sea to the nearest country, simplifies shared borders once so neighbours never gap or overlap, and checks the result against the source borders before anything ships.
```

In `## Repository`, replace the Task paragraph with:

```markdown
Everything runs in Docker through [Task](https://taskfile.dev): `task workflow:build`, `task workflow:validate`, `task workflow:publish` and `task workflow:test`. A machine needs only Docker and Task. Shared tooling comes from Crepidoma, checked out as a submodule:
```

In `## Quick start`, change the Python ocean example comment to `# nearest country for open ocean` and its value to the code from Task 10.

- [ ] **Step 2: Rewrite `workflow/README.md`**

````markdown
# Workflow

`qc2c-build` turns source country borders into the sector files shipped by the [Python](../packages/python/README.md) and [TypeScript](../packages/typescript/README.md) packages, then proves the result still matches the source.

## Run

Everything runs in Docker Compose; you need Docker and [Task](https://taskfile.dev).

```bash
task workflow:build                  # writes workflow/data/output/latest
task workflow:validate               # checks it against the source borders
task workflow:publish                # copies it into both packages and rebuilds dist
task workflow:test                   # pipeline, Python and Node suites in parallel
task workflow:preview                # draws latest/preview.png
```
````

Pass settings after `--`, for example `task workflow:build -- --tolerance 0.1 --out coarse`, then `task workflow:validate -- --tolerance 0.1 --out coarse`.

## Stages

1. **Load.** Reads `countries.json`, applies [code_overrides.json](data/input/code_overrides.json) to areas without an ISO code, repairs invalid shapes and dissolves entries that share a code.
2. **Partition.** Gives every sea point to the nearest country through Voronoi cells of the coastlines, so coastlines disappear from the data.
3. **Simplify.** Simplifies shared borders once, so neighbours never gap or overlap, snaps to the output grid and restores microstates that would vanish.
4. **Sectors.** Clips to the sector boxes in [world_sectors.json](data/input/world_sectors.json), cuts holes so first-match lookup is exact, and computes country centers.
5. **Write.** Writes JSON and gzip files plus `build.json` with the settings, input hashes and library versions.

## Settings

Defaults live in [qc2c.toml](qc2c.toml). Environment variables `QC2C_<NAME>` override them, and flags override both.

| Flag                             | Default             | Meaning                                                     |
| -------------------------------- | ------------------- | ----------------------------------------------------------- |
| `--tolerance`                    | 0.05                | Border simplification in degrees                            |
| `--decimals`                     | 3                   | Coordinate decimals in the output                           |
| `--presimplify`                  | 0.01                | Simplification before the sea partition                     |
| `--voronoi-spacing`              | 0.25                | Coastline sampling for the sea partition, degrees           |
| `--sea`                          | nearest             | `nearest`, or `distance` to return no country far from land |
| `--sea-distance-km`              | 200                 | Distance limit for `--sea distance`                         |
| `--us-states` / `--no-us-states` | off                 | Return US state codes instead of `USA`                      |
| `--sectors`                      | world_sectors.json  | Sector boxes, which must tile the world                     |
| `--overrides`                    | code_overrides.json | Codes for areas without an ISO code                         |
| `--out`                          | latest              | Output folder name                                          |
| `--samples`                      | 40                  | Random interior test points per country                     |
| `--min-border-accuracy`          | see qc2c.toml       | Required accuracy near borders                              |
| `--seed`                         | 1                   | Seed for test points                                        |

## Validation

Every source vertex and 40 random interior points per country are looked up in the output. Points farther from any other country than `2 * (presimplify + tolerance + grid + 0.001) + voronoi_spacing / 2` degrees must return their own code; points on a shared border are not scored; points in between must reach `min_border_accuracy`. Every source code must appear in the output. Results go to `validation.json`, and a sample of 500 safe points goes to `points.json`, which both library test suites check.

## Without Docker

```bash
uv run --project workflow --all-extras qc2c-build build --input-dir workflow/data/input --output-dir workflow/data/output --config workflow/qc2c.toml
```

Only the Docker build is the reference; `task workflow:check` compares the package data with it.

````

- [ ] **Step 3: Package READMEs**

In both `packages/python/README.md` and `packages/typescript/README.md`, replace note 2 under `## Notes` with:

```markdown
2. Points at sea return the nearest country, and United States points return `USA`.
````

and add note 4:

```markdown
4. The data is built and validated by the [workflow](https://github.com/Levia-Labs/QC2C/tree/main/workflow).
```

Change the Python README ocean example line to `coordinates_to_country({"lat": 0.0, "lng": -140.0})     # nearest country for open ocean`.

- [ ] **Step 4: CLAUDE.md**

Replace `## Stack` item 1 with `1. Python (setuptools package, uv-managed qc2c-build pipeline), TypeScript (npm); Docker Compose runs the pipeline and all test suites.` and add to `## Commands`: `2. task workflow:test, workflow:build, workflow:validate, workflow:publish, workflow:check.`

- [ ] **Step 5: Humanize, gate, commit**

Run the humanizer skill over the changed README prose. Run `uv run --no-project python .crepidoma/tools/folder_readme.py update`, then `task quality:gate`.
Expected: all PASS.

```bash
task git:commit -- "docs: describe the qc2c-build pipeline, Docker tasks and 2.0.0 behaviour"
```

- [ ] **Step 6: Open the pull request**

```bash
gh pr create --base main --head pipeline-rebuild --fill
```

Expected: PR URL printed; `ci` runs on it.

Overview, constraints and review focus: [00-overview.md](00-overview.md).
