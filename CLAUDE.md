# QC2C

Directives, agents and hooks come from the crepidoma plugin (github.com/Levia-Labs/Crepidoma).

## Project

1. Coordinate-to-country lookup library, published as Python (`packages/python`) and TypeScript (`packages/typescript`) packages.

## Stack

1. Python (setuptools), TypeScript (npm); world sector data as JSON and gzip.

## Repo-specific rules

1. `packages/typescript/dist` and `packages/*/data` are generated or bundled data; do not hand-edit.

## Commands

1. `task --list`; `claude:` and `lint:` come from the Crepidoma submodule.
