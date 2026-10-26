# Task 11: CI and release gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `workflow:test`, `workflow:build`, `workflow:validate`, `workflow:check`.

- [ ] **Step 1: Resolve pinned actions**

```bash
gh api repos/go-task/setup-task/releases/latest -q .tag_name
gh api repos/go-task/setup-task/commits/<tag from previous command> -q .sha
```

The checkout pin already in `release.yml` is `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`.

- [ ] **Step 2: Write `.github/workflows/ci.yml`** (substitute the setup-task SHA and tag)

```yaml
# Runs every test suite in Docker, rebuilds the data and checks the packages ship that build.
name: ci

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: true
      - uses: go-task/setup-task@<SETUP_TASK_SHA> # <SETUP_TASK_TAG>
      - run: task workflow:test
      - run: task workflow:build
      - run: task workflow:validate
      - run: task workflow:check
```

- [ ] **Step 3: Gate publishing on validation in `release.yml`**

Add this job after `permissions:` / before `build-python:`:

```yaml
  validate-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: true
      - uses: go-task/setup-task@<SETUP_TASK_SHA> # <SETUP_TASK_TAG>
      - run: task workflow:build
      - run: task workflow:validate
      - run: task workflow:check
```

Change `publish-pypi` to `needs: [build-python, validate-data]` and `publish-npm` to `needs: [build-npm, validate-data]`. Add `.github/workflows` file purpose `"ci.yml" = "Pull request gate: Docker test suites, data build, validation and package data check."` to `docs/folder-purposes.toml`, then refresh READMEs with the folder README tool.

- [ ] **Step 4: Verify locally and commit**

Run: `task quality:gate`
Expected: all PASS. The workflows themselves run on the pull request.

```bash
task git:commit -- "ci: run Docker test suites and data validation on pull requests and releases"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
