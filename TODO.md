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

status: open
class: bug

task lint:precommit (all files) reformats packages/*/data, packages/typescript/dist, web/*.json and Python sources (prettier, ruff format), touching about 80 files that must not be hand-edited; exclude generated paths in .pre-commit-config.yaml. Pre-existing failures on all files at Crepidoma v0.6.1 with unchanged configs: crepidoma-long-files flags generated JSON and two plan docs as new long files (no baseline), ruff (UP006/UP035/PTH/E501 in packages/python/qc2c/core.py, E501/I001 in workflow/tests, 123 in task lint:check), yamllint line-length >120 in tasks/workflow.yml, tasks/local.yml, tasks/pr.yml, zizmor cache-poisoning high at .github/workflows/release.yml:85 and :106 (actions/setup-node without package-manager-cache: false).

## 4 eslint hook cannot find @eslint/js after the npx --no-install switch

status: open
class: bug

Crepidoma v0.6.1 migration changes the eslint hook to npx --no-install eslint --config .crepidoma/configs/eslint.config.js, which now resolves its imports; there is no root package.json, so @eslint/js is not found and any staged JS/TS commit fails. Add a root package.json with devDependencies eslint, @eslint/js, typescript-eslint (docs/migration.md, ESLint hook and globals) and install it.
