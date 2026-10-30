# Task 9: Docker engine and Task wrappers

**Files:**

- Create: `workflow/Dockerfile`, `workflow/.dockerignore`, `compose.yaml`, `tasks/workflow.yml`, `workflow/data/output/.gitignore`
- Modify: `Taskfile.yml` (includes), `docs/folder-purposes.toml`
- Delete: `workflow/scripts/`, `workflow/test/`, `workflow/data/output/stage_1/` to `stage_4/`, `workflow/.gitignore`

**Interfaces:**

- Consumes: console script `qc2c-build` (Task 8).
- Produces: Compose services `build`, `validate`, `publish`, `preview`, `test-pipeline`, `test-python`, `test-node`; tasks `workflow:image`, `workflow:build`, `workflow:validate`, `workflow:publish`, `workflow:check`, `workflow:preview`, `workflow:test`, `workflow:test-pipeline`, `workflow:test-python`, `workflow:test-node`.

- [ ] **Step 1: Resolve pinned images**

Run each and keep the digest it prints:

```bash
docker buildx imagetools inspect python:3.12-slim --format '{{json .Manifest.Digest}}'
gh api repos/astral-sh/uv/releases/latest -q .tag_name
docker buildx imagetools inspect ghcr.io/astral-sh/uv:<tag from previous command> --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect node:24-slim --format '{{json .Manifest.Digest}}'
```

- [ ] **Step 2: Write `workflow/Dockerfile`** (substitute the three digests and the uv tag)

```dockerfile
# Reference engine for qc2c-build. Pinned images and uv.lock make builds byte-identical
# across machines of the same architecture (linux/amd64 in CI).
FROM ghcr.io/astral-sh/uv:<UV_TAG>@<UV_DIGEST> AS uv

FROM python:3.12-slim@<PYTHON_DIGEST>
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    QC2C_INPUT_DIR=/data/input \
    QC2C_OUTPUT_DIR=/data/output \
    QC2C_PACKAGES_DIR=/packages \
    QC2C_CONFIG=/app/qc2c.toml
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --all-extras --group dev
COPY src ./src
COPY qc2c.toml ./
RUN uv sync --frozen --all-extras --group dev --no-editable \
    && useradd --uid 1000 --create-home builder
USER 1000
ENTRYPOINT ["qc2c-build"]
```

`workflow/.dockerignore`:

```
data
tests
.venv
**/__pycache__
```

- [ ] **Step 3: Write `compose.yaml`** (substitute the node digest)

```yaml
# Docker engine for the QC2C pipeline. Run through Task: `task --list | grep workflow`.
name: qc2c

x-pipeline: &pipeline
  build:
    context: workflow
  image: qc2c-build:local
  user: "${QC2C_UID:-1000}:${QC2C_GID:-1000}"

x-data: &data
  - ./workflow/data/input:/data/input:ro
  - ./workflow/data/output:/data/output
  - ./workflow/qc2c.toml:/app/qc2c.toml:ro

services:
  build:
    <<: *pipeline
    volumes: *data
    command: ["build"]

  validate:
    <<: *pipeline
    volumes: *data
    command: ["validate"]

  preview:
    <<: *pipeline
    volumes: *data
    command: ["preview"]

  publish:
    <<: *pipeline
    volumes:
      - ./workflow/data/input:/data/input:ro
      - ./workflow/data/output:/data/output:ro
      - ./workflow/qc2c.toml:/app/qc2c.toml:ro
      - ./packages/python/qc2c/data:/packages/python/qc2c/data
      - ./packages/typescript/src/data:/packages/typescript/src/data
      - ./packages/fixtures:/packages/fixtures
    command: ["publish"]

  test-pipeline:
    <<: *pipeline
    volumes:
      - ./workflow:/app:ro
    environment:
      PYTHONPATH: /app/src
    entrypoint: ["python", "-m", "pytest"]
    command: []

  test-python:
    <<: *pipeline
    volumes:
      - ./packages/python:/packages/python:ro
      - ./packages/fixtures:/packages/fixtures:ro
    working_dir: /packages/python
    environment:
      PYTHONPATH: /packages/python
    entrypoint: ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    command: []

  test-node:
    image: node:24-slim@<NODE_DIGEST>
    user: "${QC2C_UID:-1000}:${QC2C_GID:-1000}"
    volumes:
      - ./packages/typescript:/packages/typescript
      - ./packages/fixtures:/packages/fixtures:ro
    working_dir: /packages/typescript
    environment:
      npm_config_cache: /tmp/npm-cache
      HOME: /tmp
    entrypoint: ["sh", "-c", "npm ci --no-audit --no-fund && npm run build && npm test"]
```

`workflow/data/output/.gitignore`:

```
*
!.gitignore
!README.md
```

- [ ] **Step 4: Write `tasks/workflow.yml`**

```yaml
version: "3"

env:
  QC2C_UID:
    sh: id -u
  QC2C_GID:
    sh: id -g

tasks:
  image:
    desc: "Build the pipeline image. Usage: task workflow:image"
    run: once
    cmds:
      - docker compose build build

  build:
    desc: "Build sector data into workflow/data/output/<out> in Docker. Usage: task workflow:build -- [--tolerance 0.1] [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm build build {{.CLI_ARGS}}

  validate:
    desc: "Validate a build against the source borders. Usage: task workflow:validate -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm validate validate {{.CLI_ARGS}}

  publish:
    desc: "Copy a validated build into both packages and rebuild dist. Usage: task workflow:publish -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm publish publish {{.CLI_ARGS}}
      - task: test-node

  check:
    desc: "Fail when package data differs from the build. Usage: task workflow:check -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm publish compare {{.CLI_ARGS}}

  preview:
    desc: "Render a build to preview.png in its output folder. Usage: task workflow:preview -- [--out name]"
    deps: [image]
    cmds:
      - docker compose run --rm preview preview {{.CLI_ARGS}}

  test:
    desc: "Run pipeline, Python and Node suites in parallel. Usage: task workflow:test"
    deps: [test-pipeline, test-python, test-node]

  test-pipeline:
    desc: "Run the pipeline unit tests in Docker. Usage: task workflow:test-pipeline -- [pytest args]"
    deps: [image]
    cmds:
      - docker compose run --rm test-pipeline {{.CLI_ARGS}}

  test-python:
    desc: "Run the Python package tests in Docker. Usage: task workflow:test-python"
    deps: [image]
    cmds:
      - docker compose run --rm test-python

  test-node:
    desc: "Install, build and test the TypeScript package in Docker. Usage: task workflow:test-node"
    cmds:
      - docker compose run --rm test-node
```

In `Taskfile.yml`, add under `includes:` after `setup: .crepidoma/taskfiles/setup`:

```yaml
workflow: ./tasks/workflow.yml
```

- [ ] **Step 5: Remove the old pipeline**

```bash
git rm -r -q workflow/scripts workflow/test workflow/data/output/stage_1 workflow/data/output/stage_2 workflow/data/output/stage_3 workflow/data/output/stage_4 workflow/.gitignore
```

- [ ] **Step 6: Update `docs/folder-purposes.toml`**

Delete the `[folders]` entries for `workflow/data/output/stage_1` to `stage_4`, `workflow/scripts` and `workflow/test`, and the `[files]` entries `main.py`, `preview_world_sectors.py`, `__main__.py`. Change `"workflow/data/output"` to `"Build outputs, one folder per --out name; ignored by git."`. Add:

```toml
"tasks" = "Task namespaces owned by this repo."
"workflow/src" = "Source of the qc2c-build package."
"workflow/src/qc2c_build" = "Pipeline modules: load, partition, simplify, sectors, write, validate, publish, preview, cli."
"workflow/tests" = "Pipeline tests on a synthetic world."
"packages/fixtures" = "Points with expected codes, written by qc2c-build publish and used by both library test suites."
```

and under `[files]`:

```toml
"Dockerfile" = "Pipeline image: pinned Python and uv, locked dependencies, qc2c-build entry point."
"compose.yaml" = "Docker Compose services for building, validating, publishing and testing."
"qc2c.toml" = "Default build settings."
"code_overrides.json" = "Output codes for source areas without an ISO code."
"points.json" = "Fixture points with expected country codes."
"workflow.yml" = "Task wrappers around the Compose services."
"uv.lock" = "Locked pipeline dependencies."
```

Then run `uv run --no-project python .crepidoma/tools/folder_readme.py update`.

- [ ] **Step 7: Run the suites through Docker**

Run: `task workflow:test-pipeline`
Expected: all pipeline tests PASS inside the container.

Run: `task workflow:test-python`
Expected: existing Python package tests PASS (the fixture test arrives in Task 10).

- [ ] **Step 8: Gate and commit**

Run: `task quality:gate`
Expected: all PASS. If `quality:long-files` flags `workflow/uv.lock`, add it to `.ratchet/long-files.baseline` with the reason `generated lockfile`.

```bash
task git:commit -- "feat(workflow): run the pipeline in Docker Compose and drop staged scripts"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
