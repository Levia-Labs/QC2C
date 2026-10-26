# Workflows

- GitHub Actions: publishing a GitHub release publishes both packages to PyPI and npm through trusted publishing.

## Contents

<!-- contents:start -->

- [`ci.yml`](ci.yml) - Pull request gate: Docker test suites, data build, validation and package data check.
- [`release.yml`](release.yml) - Builds, tests and publishes both packages on a published GitHub release.

<!-- contents:end -->
