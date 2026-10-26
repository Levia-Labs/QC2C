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
    try:
        from .preview import render
    except ImportError as error:
        raise ConfigError("preview needs the 'preview' extra: matplotlib") from error

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
