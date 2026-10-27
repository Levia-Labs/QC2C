import json
import shutil
from dataclasses import replace

import pytest

pytest.importorskip("matplotlib")  # publish renders web/preview.png

from qc2c_build.pipeline import run_build
from qc2c_build.publish import PublishError, compare, publish
from qc2c_build.validate import run_validation


def _published(world):
    run_build(world)
    run_validation(world)
    return publish(world)


def test_publish_then_compare(world):
    written = _published(world)
    assert (world.packages_dir / "python/qc2c/data/gz/world_sectors.json.gz") in written
    assert (world.packages_dir / "typescript/src/data/json/world_sector_1.json").is_file()
    assert (world.packages_dir / "fixtures/points.json").is_file()
    assert compare(world) == []
    (world.packages_dir / "python/qc2c/data/json/world_sector_1.json").write_text("{}", encoding="utf-8")
    assert compare(world) == ["python/qc2c/data/json/world_sector_1.json"]


def test_publish_keeps_other_files(world):
    keep = world.packages_dir / "python/qc2c/data/json/__init__.py"
    keep.parent.mkdir(parents=True)
    keep.write_text("", encoding="utf-8")
    world.web_dir.mkdir()
    readme = world.web_dir / "README.md"
    readme.write_text("docs", encoding="utf-8")
    _published(world)
    assert keep.is_file()
    assert readme.read_text(encoding="utf-8") == "docs"
    assert compare(world) == []


def test_publish_refuses_failed_validation(world):
    run_build(world)
    (world.build_dir / "validation.json").write_text(json.dumps({"passed": False}), encoding="utf-8")
    with pytest.raises(PublishError, match="validation failed"):
        publish(world)


def test_preview_writes_png(world):
    from qc2c_build.preview import render

    run_build(world)
    assert render(world).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_publish_refuses_stale_validation(world):
    run_build(world)
    run_validation(world)
    run_build(world)
    with pytest.raises(PublishError, match="run validate first"):
        publish(world)


def test_publish_missing_source_leaves_packages_intact(world):
    _published(world)
    target = world.packages_dir / "python/qc2c/data/json/world_sector_1.json"
    before = target.read_bytes()
    (world.build_dir / "points.json").unlink()
    with pytest.raises(PublishError, match="points.json"):
        publish(world)
    assert target.read_bytes() == before


@pytest.mark.parametrize("text", ["{not json", json.dumps({"passed": "false"}), json.dumps([True])])
def test_publish_rejects_bad_validation(world, text):
    run_build(world)
    (world.build_dir / "validation.json").write_text(text, encoding="utf-8")
    with pytest.raises(PublishError):
        publish(world)


def test_compare_flags_and_publish_removes_stale_sector(world):
    _published(world)
    stale = world.packages_dir / "typescript/src/data/json/world_sector_99.json"
    stale.write_text("{}", encoding="utf-8")
    assert compare(world) == ["typescript/src/data/json/world_sector_99.json"]
    publish(world)
    assert not stale.exists()
    assert compare(world) == []


def test_web_bundle_contents(world):
    _published(world)
    build = world.build_dir
    web = world.web_dir
    names = {p.name for p in web.iterdir()}
    sectors = sorted(p.name for p in build.glob("world_sector_*.json"))
    assert names == {"world_sectors.json", "world_sectors.json.gz", "qc2c.json", "preview.png",
                     *sectors, *(f"{n}.gz" for n in sectors)}
    assert (web / "preview.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    for name in (*sectors, *(f"{n}.gz" for n in sectors), "world_sectors.json.gz"):
        assert (web / name).read_bytes() == (build / name).read_bytes()
    plain = json.loads((web / "world_sectors.json").read_text(encoding="utf-8"))
    original = json.loads((build / "world_sectors.json").read_text(encoding="utf-8"))
    assert list(plain) == [key.removesuffix(".gz") for key in original]
    assert all(key.endswith(".json") for key in plain)
    assert list(plain.values()) == list(original.values())
    assert set(plain) == set(sectors)


def test_web_metadata(world):
    _published(world)
    raw = (world.web_dir / "qc2c.json").read_text(encoding="utf-8")
    meta = json.loads(raw)
    build = json.loads((world.build_dir / "build.json").read_text(encoding="utf-8"))
    validation = json.loads((world.build_dir / "validation.json").read_text(encoding="utf-8"))
    assert raw == json.dumps(meta, indent=2, sort_keys=True) + "\n"
    assert meta["name"] == "qc2c" and meta["version"] == "0.0.0-test"
    assert (meta["codes"], meta["points"], meta["gzip_total"]) == (build["codes"], build["points"], build["gzip_total"])
    assert meta["inputs"] == build["inputs"]
    assert meta["validation"]["passed"] is True
    assert meta["validation"]["overall"] == validation["accuracy"]["overall"]
    assert meta["validation"]["counts"] == validation["counts"]
    assert set(meta["settings"]) == {"tolerance", "decimals", "presimplify", "voronoi_spacing", "sea",
                                     "sea_distance_km", "us_states"}
    assert meta["files"]["world_sectors.json"] == (world.web_dir / "world_sectors.json").stat().st_size
    assert set(meta["files"]) == {p.name for p in world.web_dir.iterdir()} - {"qc2c.json"}
    assert "seconds" not in raw


def test_web_metadata_is_deterministic(world):
    _published(world)
    first = (world.web_dir / "qc2c.json").read_bytes()
    publish(world)
    assert (world.web_dir / "qc2c.json").read_bytes() == first


def test_compare_flags_web_changes(world):
    _published(world)
    (world.web_dir / "world_sectors.json").write_text("{}", encoding="utf-8")
    (world.web_dir / "extra.json").write_text("{}", encoding="utf-8")
    assert compare(world) == ["web/extra.json", "web/world_sectors.json"]
    publish(world)
    assert not (world.web_dir / "extra.json").exists()
    assert compare(world) == []


def test_publish_needs_package_version(world):
    run_build(world)
    run_validation(world)
    (world.packages_dir / "typescript/package.json").unlink()
    with pytest.raises(PublishError, match="package.json"):
        publish(world)


@pytest.mark.parametrize("fail_on", [1, 5, 13, 19])
def test_publish_failure_midway_keeps_previous_files(world, monkeypatch, fail_on):
    _published(world)
    tracked = [*world.packages_dir.rglob("*"), *world.web_dir.rglob("*")]
    before = {p: p.read_bytes() for p in tracked if p.is_file()}
    # a different build, so a mixed result would be visible
    other = replace(world, tolerance=0.2, decimals=1)
    run_build(other)
    run_validation(other)
    calls = []
    real = shutil.copyfile

    def flaky(source, destination, *args, **kwargs):
        calls.append(destination)
        if len(calls) == fail_on:
            raise OSError("disk full")
        return real(source, destination, *args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", flaky)
    with pytest.raises(OSError, match="disk full"):
        publish(world)
    assert len(calls) == fail_on
    after = {p: p.read_bytes() for p in [*world.packages_dir.rglob("*"), *world.web_dir.rglob("*")] if p.is_file()}
    assert after == before
    assert not [p for p in after if p.name.endswith(".tmp")]


def test_compare_requires_preview_in_build(world):
    _published(world)
    (world.build_dir / "preview.png").unlink()
    assert "web/preview.png" in compare(world)
    assert compare(world).count("web/preview.png") == 1
