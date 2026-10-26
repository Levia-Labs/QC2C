<p align="center">
  <img src="https://raw.githubusercontent.com/Levia-Labs/QC2C/main/assets/logo.svg" alt="QC2C, Quick Coordinates To Country" width="360">
</p>

# qc2c for Python

Offline lookup from latitude and longitude to an ISO 3166-1 alpha-3 country code. Border data ships inside the package, so lookups work without a network connection, and the package depends only on the standard library.

## Install

```bash
pip install qc2c
```

## Use

```python
from qc2c import coordinates_to_country

coordinates_to_country({"lat": 52.23, "lng": 21.01})    # "POL"
coordinates_to_country({"lat": 35.68, "lng": 139.69})   # "JPN"
coordinates_to_country({"lat": 0.0, "lng": -140.0})     # "PYF", nearest country for open ocean
```

To use your own copy of the data, call the steps directly:

```python
from qc2c import get_sector, get_country

sector_key = get_sector(manifest, {"lat": 52.23, "lng": 21.01})  # "world_sector_2.json.gz"
code = get_country(sectors[sector_key], {"lat": 52.23, "lng": 21.01})
```

## API

| Function | Returns |
| --- | --- |
| `coordinates_to_country(coordinates)` | Country code from the bundled data, or `None` when the coordinates fall outside [-90, 90] latitude or [-180, 180] longitude. |
| `get_sector(manifest, coordinates)` | Key of the first sector whose bounding box contains the point, or `None`. |
| `get_country(sector, coordinates)` | Key of the first country polygon in the sector that contains the point, or `None`. |
| `point_in_polygon(point, polygon)` | `True` when `[lat, lng]` lies inside the polygon (ray casting). |

`coordinates` is a dict with `lat` and `lng` keys in decimal degrees.

## Notes

1. Borders are approximate and can be wrong close to a border.
2. Points at sea return the nearest country, and United States points return `USA`.
3. Data and algorithm match the [npm package](https://www.npmjs.com/package/qc2c).
4. The data is built and validated by the [workflow](https://github.com/Levia-Labs/QC2C/tree/main/workflow).

Source, data pipeline and issues: [github.com/Levia-Labs/QC2C](https://github.com/Levia-Labs/QC2C). MIT licensed.
