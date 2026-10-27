# Task 8: Command line

**Files:**
- Create: `workflow/src/qc2c_build/cli.py`, `workflow/tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `ConfigError`, `run_build`, `run_validation`, `publish`, `compare`, `PublishError`, `render`, `DEFAULTS`.
- Produces: `cli.main(argv: list[str] | None = None) -> int` (0 ok, 1 check failed, 2 usage or input error); console script `qc2c-build`.

- [ ] **Step 1: Write the failing tests `workflow/tests/test_cli.py`**

```python
from qc2c_build.cli import main


def args(cfg, *extra):
    return ["--config", "none.toml", "--input-dir", str(cfg.input_dir), "--output-dir", str(cfg.output_dir),
            "--packages-dir", str(cfg.packages_dir), "--presimplify", "0", "--voronoi-spacing", "1", "--samples", "10", *extra]


def test_cli_build_validate_publish_compare(world, capsys):
    assert main(["build", *args(world)]) == 0
    assert main(["validate", *args(world)]) == 0
    assert main(["publish", *args(world)]) == 0
    assert main(["compare", *args(world)]) == 0
    assert "built" in capsys.readouterr().out


def test_cli_compare_reports_difference(world):
    main(["build", *args(world)])
    assert main(["compare", *args(world)]) == 1


def test_cli_bad_setting_exits_2(world, capsys):
    assert main(["build", *args(world, "--sea", "ocean")]) == 2
    assert "sea must be one of" in capsys.readouterr().err


def test_cli_missing_input_exits_2(world, tmp_path, capsys):
    assert main(["build", *args(world, "--input-dir", str(tmp_path / "missing"))]) == 2
    assert "qc2c-build:" in capsys.readouterr().err


def test_cli_us_states_flag(world):
    assert main(["build", *args(world, "--us-states")]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project workflow pytest workflow/tests/test_cli.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'qc2c_build.cli'`

- [ ] **Step 3: Implement `workflow/src/qc2c_build/cli.py`**

```python
"""qc2c-build: build, validate, publish, compare or preview QC2C sector data."""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import fields
from pathlib import Path

from .config import DEFAULTS, BuildConfig, ConfigError, load_config
from .pipeline import run_build
from .publish import PublishError, compare, publish
from .validate import run_validation


def _build(cfg: BuildConfig) -> int:
    meta = run_build(cfg)
    seconds = sum(meta["seconds"].values())
    print(f"built {cfg.build_dir}: {meta['codes']} codes, {meta['points']} points, "
          f"{meta['gzip_total'] / 1024:.0f} KB gzip in {seconds:.0f}s")
    return 0


def _validate(cfg: BuildConfig) -> int:
    report = run_validation(cfg)
    accuracy = report["accuracy"]
    print(f"validated {cfg.build_dir}: core {accuracy['core']:.4%}, border {accuracy['border']:.4%}, "
          f"overall {accuracy['overall']:.4%}; worst {', '.join(report['worst'][:5])}")
    for failure in report["failures"]:
        print(f"FAIL {failure}")
    return 0 if report["passed"] else 1


def _publish(cfg: BuildConfig) -> int:
    print(f"published {len(publish(cfg))} files into {cfg.packages_dir}")
    return 0


def _compare(cfg: BuildConfig) -> int:
    diffs = compare(cfg)
    for path in diffs:
        print(f"differs: {path}")
    print("package data matches the build" if not diffs else f"{len(diffs)} files differ")
    return 1 if diffs else 0


def _preview(cfg: BuildConfig) -> int:
    from .preview import render

    print(f"preview written to {render(cfg)}")
    return 0


COMMANDS = {"build": _build, "validate": _validate, "publish": _publish, "compare": _compare, "preview": _preview}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="qc2c-build", description=__doc__)
    result.add_argument("command", choices=sorted(COMMANDS))
    result.add_argument("--config", type=Path, default=Path(os.environ.get("QC2C_CONFIG", "qc2c.toml")))
    for field in fields(BuildConfig):
        flag = "--" + field.name.replace("_", "-")
        if isinstance(getattr(DEFAULTS, field.name), bool):
            result.add_argument(flag, dest=field.name, action=argparse.BooleanOptionalAction, default=None)
        else:
            result.add_argument(flag, dest=field.name, default=None, metavar=field.name.upper())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    cli = {field.name: getattr(args, field.name) for field in fields(BuildConfig)}
    try:
        cfg = load_config(args.config, cli=cli)
        return COMMANDS[args.command](cfg)
    except (ConfigError, PublishError, FileNotFoundError) as error:
        print(f"qc2c-build: {error}", file=sys.stderr)
        return 2
```

`test_cli_missing_input_exits_2` relies on `read_sectors` raising `FileNotFoundError` for the missing folder.

- [ ] **Step 4: Run all pipeline tests**

Run: `uv run --project workflow --all-extras pytest workflow/tests`
Expected: all PASS in a few seconds.

- [ ] **Step 5: Commit**

```bash
task git:commit -- "feat(workflow): add qc2c-build command line"
```

Overview, constraints and review focus: [00-overview.md](00-overview.md).
