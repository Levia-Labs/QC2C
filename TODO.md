# TODO

## 1 gate_runner quiet crashes with UnicodeEncodeError on cp1250 consoles

status: open
class: bug

Crepidoma scripts/gate_runner.py:77 print(line) raises UnicodeEncodeError for U+25CF under a Windows cp1250 console. QC2C works around it with PYTHONIOENCODING=utf-8 in tasks/local.yml; fix upstream with sys.stdout.reconfigure(errors='replace').

## 2 Host jest cannot resolve jest-circus runner on Windows

status: open
class: bug

node packages/typescript/node_modules/jest/bin/jest.js run from packages/typescript reports 'Module ...jest-circus/build/runner.js in the testRunner option was not found' although the file exists; npm test also lacks .cmd shims after the Docker install. Blocks a host local:node task; TypeScript tests stay on workflow:test-node.

## 3 pre-commit run --all-files rewrites generated data and fails on pre-existing debt

status: done
class: bug

task lint:precommit (all files) reformats packages/*/data, packages/typescript/dist, web/*.json and Python sources (prettier, ruff format), touching about 80 files that must not be hand-edited; exclude generated paths in .pre-commit-config.yaml. Pre-existing failures on all files at Crepidoma v0.6.1 with unchanged configs: crepidoma-long-files flags generated JSON and two plan docs as new long files (no baseline), ruff (UP006/UP035/PTH/E501 in packages/python/qc2c/core.py, E501/I001 in workflow/tests, 123 in task lint:check), yamllint line-length >120 in tasks/workflow.yml, tasks/local.yml, tasks/pr.yml, zizmor cache-poisoning high at .github/workflows/release.yml:85 and :106 (actions/setup-node without package-manager-cache: false).

## 4 eslint hook cannot find @eslint/js after the npx --no-install switch

status: done
class: bug

Crepidoma v0.6.1 migration changes the eslint hook to npx --no-install eslint --config .crepidoma/configs/eslint.config.js, which now resolves its imports; there is no root package.json, so @eslint/js is not found and any staged JS/TS commit fails. Add a root package.json with devDependencies eslint, @eslint/js, typescript-eslint (docs/migration.md, ESLint hook and globals) and install it.

## 5 Shared eslint config lacks jest globals for packages/typescript tests

status: open
class: bug

With the root eslint devDependencies installed, the eslint hook loads .crepidoma/configs/eslint.config.js and reports 28 no-undef errors in packages/typescript/tests/index.test.js (describe, test, expect, global). ESLint 9 flat config ignores /* eslint-env */; fix upstream in Crepidoma by adding jest globals for **/tests/**/*.test.{js,ts} and **/*.test.* in the shared config, then bump the submodule. Any commit staging that test file fails until then.

## 6 ruff markdown formatting pushes two plan docs over the 300-line cap

status: open
class: bug

task lint:python:check reports docs/superpowers/plans/2026-10-26-generation-pipeline/05-sectors-rings-and-output-files.md and 06-validation-of-output.md as unformatted; applying ruff format grows them to 325 and 310 lines, which crepidoma-long-files rejects. The reformat is stashed (git stash list: 'ruff markdown format of plan docs 05 and 06'). Choose: split each plan doc, or exclude completed plan docs from ruff markdown formatting (shared ruff.toml extend-exclude or a lint task arg).
