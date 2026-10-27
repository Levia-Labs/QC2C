# Workflows

- GitHub Actions: `ci.yml` gates pull requests and main; publishing a GitHub release runs `release.yml`, whose `validate-data` job must pass before both packages publish to PyPI and npm through trusted publishing.

## Contents

<!-- contents:start -->

- [`ci.yml`](ci.yml) - Pull request and main gate: Docker test suites, data build, validation and package data check; cancels superseded runs.
- [`release.yml`](release.yml) - On a published release: validate-data gate, then build, test and publish both packages.

<!-- contents:end -->
