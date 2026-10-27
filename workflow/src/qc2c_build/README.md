# Qc2c_build

- The qc2c_build package: settings and the sector data build pipeline.

## Contents

<!-- contents:start -->

- [`__init__.py`](__init__.py) - Package marker.
- [`cli.py`](cli.py) - qc2c-build: build, validate, publish, compare or preview QC2C sector data.
- [`config.py`](config.py) - Build settings: defaults, then qc2c.toml, then QC2C_* environment variables, then CLI flags.
- [`geom.py`](geom.py) - Polygon helpers shared by the build stages.
- [`load.py`](load.py) - Read source borders, apply code overrides and dissolve features that share a code.
- [`partition.py`](partition.py) - Give sea to the nearest country, so the output covers the whole plane.
- [`pipeline.py`](pipeline.py) - Run the build stages in order and record what was built.
- [`preview.py`](preview.py) - Draw a build as a PNG with sector boxes, without a display.
- [`publish.py`](publish.py) - Copy a validated build into both packages and the website folder, or report how they differ from it.
- [`sectors.py`](sectors.py) - Clip the partition to sector boxes and turn it into the shipped JSON shape.
- [`simplify.py`](simplify.py) - Simplify shared borders once, snap to the output grid and keep every code alive.
- [`validate.py`](validate.py) - Check a build against the source borders; write validation.json and the library fixture.
- [`write.py`](write.py) - Write sector files and the manifest as JSON and gzip, plus build.json.

<!-- contents:end -->
