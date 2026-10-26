<p align="center">
  <img src="https://raw.githubusercontent.com/Levia-Labs/QC2C/main/assets/logo.svg" alt="QC2C, Quick Coordinates To Country" width="360">
</p>

# qc2c for JavaScript and TypeScript

Offline lookup from latitude and longitude to an ISO 3166-1 alpha-3 country code. Ships with type declarations and the border data as JSON.

## Install

```bash
npm install qc2c
```

## Use in Node or a bundler

```ts
import { getSector, getCountry } from "qc2c";
import manifest from "qc2c/dist/data/json/world_sectors.json";

const point = { lat: 52.23, lng: 21.01 };
const sectorKey = getSector(manifest, point);           // "world_sector_2.json.gz"
const file = sectorKey!.replace(/\.gz$/, "");            // sector keys name the gzipped files
const sector = await import(`qc2c/dist/data/json/${file}`);
getCountry(sector.default ?? sector, point);             // "POL"
```

## Use in the browser

Host the gzipped sector files from the [repository](https://github.com/Levia-Labs/QC2C/tree/main/packages/typescript/src/data/gz), served with `Content-Encoding: gzip` so the browser decompresses them, then:

```ts
import { coordinatesToCountry } from "qc2c";

const code = await coordinatesToCountry(
  { lat: 52.23, lng: 21.01 },
  { manifest: "/qc2c/world_sectors.json.gz", sectors: "/qc2c" },
);
// "POL"
```

## API

| Function | Returns |
| --- | --- |
| `coordinatesToCountry(coordinates, urls)` | Fetches the manifest and one sector file, then returns the country code or `null`. |
| `getSector(manifest, coordinates)` | Key of the first sector whose bounding box contains the point, or `null`. |
| `getCountry(sector, coordinates)` | Key of the first country polygon in the sector that contains the point, or `null`. |

`coordinates` is `{ lat, lng }` in decimal degrees.

## Notes

1. Borders are approximate and cover land only; there are no maritime borders.
2. The United States is split into states, so US points return the state code, for example `"NY"`.
3. Data and algorithm match the [PyPI package](https://pypi.org/project/qc2c/).

Source, data pipeline and issues: [github.com/Levia-Labs/QC2C](https://github.com/Levia-Labs/QC2C). MIT licensed.
