# Changelog

## 2.0.0

Data rebuilt by the new `qc2c-build` pipeline (`workflow/`), validated against the source borders.

1. Points at sea return the nearest country instead of `None`.
2. United States points return `USA` instead of state codes.
3. Small countries (Vatican, San Marino, Monaco, Liechtenstein) resolve to themselves instead of their neighbour.
4. Areas without an ISO code use the codes in `workflow/data/input/code_overrides.json`, for example `XKX` for Kosovo.
5. Alaska is back.

## 1.1.0

Libraries read the bundled manifest and multipolygon sector files correctly; Python gained `coordinates_to_country`. Not published.
