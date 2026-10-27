<p align="center">
  <img src="assets/logo.svg" alt="QC2C, Quick Coordinates To Country" width="420">
</p>

<p align="center">
  Offline lookup from latitude and longitude to an ISO 3166-1 alpha-3 country code.<br>
  It needs no API key, network connection or GIS library.
</p>

<p align="center">
  <a href="https://pypi.org/project/qc2c/"><img src="https://img.shields.io/pypi/v/qc2c?label=PyPI&color=2563eb" alt="PyPI version"></a>
  <a href="https://www.npmjs.com/package/qc2c"><img src="https://img.shields.io/npm/v/qc2c?label=npm&color=e11d48" alt="npm version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-64748b" alt="MIT license"></a>
  <a href="https://github.com/Levia-Labs/Crepidoma"><img src="https://img.shields.io/badge/built%20on-Crepidoma-22d3ee" alt="Built on Crepidoma"></a>
</p>

---

## Why QC2C

Reverse geocoding services are slow, rate limited and need a connection. The source border data for this project weighs about 30 MB. QC2C ships the whole world as about 165 KB of gzipped, simplified polygons, split into sectors, so a lookup reads one small file and runs a point-in-polygon test.

The data ships inside the package, so lookups work offline and coordinates never leave the machine. Six gzipped sector files and a manifest are small enough for browsers and mobile apps. A bounding-box check picks the sector first, so each lookup tests only the countries in that sector.

Python and JavaScript or TypeScript share the same data and algorithm, and the Python package depends on nothing outside the standard library.

## Install

```bash
pip install qc2c
```

```bash
npm install qc2c
```

## Quick start

Python:

```python
from qc2c import coordinates_to_country

coordinates_to_country({"lat": 52.23, "lng": 21.01})  # "POL"
coordinates_to_country({"lat": 0.0, "lng": -140.0})   # "PYF", nearest country for open ocean
```

TypeScript in the browser, with the gzipped sector files hosted next to your app:

```ts
import { coordinatesToCountry } from "qc2c";

const code = await coordinatesToCountry(
  { lat: 52.23, lng: 21.01 },
  { manifest: "/qc2c/world_sectors.json.gz", sectors: "/qc2c" },
);
// "POL"
```

Package guides: [Python](packages/python/README.md) and [TypeScript](packages/typescript/README.md).

## How it works

1. The manifest maps each sector file to a bounding box.
2. The sector whose box contains the point is loaded.
3. Each country polygon in that sector is tested with ray casting. The first hit returns its code.

The data comes from the [build pipeline](workflow/README.md), which gives sea to the nearest country, simplifies shared borders once so neighbours never gap or overlap, and checks the result against the source borders before anything ships.

## Limits

QC2C approximates borders. The shipped data assigns every point on Earth to a country: points at sea go to the nearest one. Results can be wrong close to a border. Points farther than about a quarter of a degree from any other country always resolve correctly; accuracy near borders is reported in `validation.json` and enforced by `min_border_accuracy` in [qc2c.toml](workflow/qc2c.toml). Use a proper GIS dataset where precision matters.

The project takes no political position. It does not move borders or decide who owns disputed land; it follows its source data, and areas without an ISO code use the codes in [code_overrides.json](workflow/data/input/code_overrides.json). Keep political views out of issues, commits and pull requests.

## Repository

| Path | What is there |
| --- | --- |
| [packages/python](packages/python) | PyPI package |
| [packages/typescript](packages/typescript) | npm package |
| [workflow](workflow) | Pipeline that builds and validates the sector files |
| [docs](docs) | Repository documentation |

Everything runs in Docker through [Task](https://taskfile.dev): `task workflow:build`, `task workflow:validate`, `task workflow:publish` and `task workflow:test`. A machine needs only Docker and Task. Shared tooling comes from Crepidoma, checked out as a submodule:

```bash
git clone --recurse-submodules https://github.com/Levia-Labs/QC2C.git
```

## Related projects

Other open source work from [Levia Labs](https://github.com/Levia-Labs):

1. [Crepidoma](https://github.com/Levia-Labs/Crepidoma): LLM tooling foundation (task namespaces, configs, Claude Code plugin) shared by all Levia Labs projects.
2. [HumanShortCode](https://github.com/Levia-Labs/HumanShortCode): replace long, unreadable IDs with short, human-readable codes.
3. [saber-tooth](https://github.com/Levia-Labs/saber-tooth): Beat Saber modding API for custom levels.
4. [beat-analyser](https://github.com/Levia-Labs/beat-analyser): read beat data from music files with madmom, packaged for Docker.

## License

[MIT](LICENSE) © 2023 deadsmond
