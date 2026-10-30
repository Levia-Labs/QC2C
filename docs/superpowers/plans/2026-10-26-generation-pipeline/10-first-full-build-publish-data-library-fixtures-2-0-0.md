# Task 10: First full build, publish data, library fixtures, 2.0.0

**Files:**
- Modify: `workflow/qc2c.toml` (`min_border_accuracy`), `packages/python/tests/test_qc2c.py:36,39`, `packages/typescript/tests/index.test.js:47-50`, `packages/python/pyproject.toml:7`, `packages/typescript/package.json`, `packages/typescript/package-lock.json`
- Create: `packages/python/tests/test_fixture.py`, `packages/typescript/tests/fixture.test.js`, `CHANGELOG.md`
- Generated: `packages/python/qc2c/data/**`, `packages/typescript/src/data/**`, `packages/typescript/dist/**`, `packages/fixtures/points.json`

**Interfaces:**
- Consumes: all `workflow:*` tasks (Task 9).
- Produces: shipped 2.0.0 data and fixture.

- [ ] **Step 1: Write the failing library fixture tests**

`packages/python/tests/test_fixture.py`:

```python
"""Every fixture point written by qc2c-build must resolve to its expected code."""

import json
from pathlib import Path

from qc2c import coordinates_to_country

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "points.json"


def test_fixture_points_match_pipeline():
    points = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(points) >= 250
    wrong = [
        (p, coordinates_to_country({"lat": p["lat"], "lng": p["lng"]}))
        for p in points
        if coordinates_to_country({"lat": p["lat"], "lng": p["lng"]}) != p["code"]
    ]
    assert not wrong, wrong[:10]
```

`packages/typescript/tests/fixture.test.js`:

```javascript
// Every fixture point written by qc2c-build must resolve to its expected code.
const fs = require("fs");
const path = require("path");
const { getSector, getCountry } = require("../dist/index");

const dataDir = path.join(__dirname, "..", "src", "data", "json");
const load = (name) => JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));
const points = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "fixtures", "points.json"), "utf8"));

test("fixture points match the pipeline", () => {
  const manifest = load("world_sectors.json");
  const wrong = points.filter(({ lat, lng, code }) => {
    const key = getSector(manifest, { lat, lng });
    return key === null || getCountry(load(key.replace(/\.gz$/, "")), { lat, lng }) !== code;
  });
  expect(points.length).toBeGreaterThanOrEqual(250);
  expect(wrong.slice(0, 10)).toEqual([]);
});
```

Update the city cases. In `packages/python/tests/test_qc2c.py` replace lines 36 and 39:

```python
((40.71, -74.0, "USA"),)
```

and

```python
((0, -140, "PYF"),)  # open ocean returns the nearest country (Marquesas)
```

In `packages/typescript/tests/index.test.js` replace lines 47 to 48 and line 52:

```javascript
    [40.71, -74.0, "USA"],
```

and

```javascript
    // Open ocean returns the nearest country (Marquesas).
    [0, -140, "PYF"],
```

If the first build shows a different nearest country for `(0, -140)`, use the code `qc2c-build` produces and say so in the commit message; the case pins ocean behaviour, not a particular island.

- [ ] **Step 2: Run them to verify they fail**

Run: `task workflow:test-python`
Expected: FAIL with `FileNotFoundError` for `packages/fixtures/points.json` and `"NY" != "USA"`.

- [ ] **Step 3: Build and measure**

Run: `task workflow:build`
Expected: last line `built /data/output/latest: ... codes, ... points, ... KB gzip in ...s`; gzip total within 15% of 222 KB.

Run: `task workflow:validate`
Expected: exit 0 with `core 100.0000%`. Note the `border` percentage.

- [ ] **Step 4: Record the border threshold**

In `workflow/qc2c.toml` set `min_border_accuracy` to the border accuracy from Step 3 rounded down to a whole percent, for example `0.93` for `93.6%`. Rerun `task workflow:validate`; expected exit 0.

- [ ] **Step 5: Publish and rebuild packages**

Run: `task workflow:publish`
Expected: `published 29 files into /packages`, then the Node suite runs. `npm test` now passes including `fixture.test.js`.

Run: `task workflow:test` and `task workflow:check`
Expected: all three suites PASS; `package data matches the build`.

- [ ] **Step 6: Bump versions and write the changelog**

In `packages/python/pyproject.toml` set `version = "2.0.0"`. Run `npm version 2.0.0 --no-git-tag-version --prefix packages/typescript`.

`CHANGELOG.md`:

```markdown
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
```

- [ ] **Step 7: Gate and commit**

Run: `task quality:gate`
Expected: all PASS.

```bash
task git:commit -- "feat!: ship 2.0.0 data from qc2c-build

Sea returns the nearest country, US points return USA, microstates resolve
to themselves. Both library suites check the shared pipeline fixture."
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
