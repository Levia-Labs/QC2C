import json

import pytest

from qc2c_build.pipeline import run_build
from qc2c_build.publish import PublishError, compare, publish
from qc2c_build.validate import run_validation


def test_publish_then_compare(world):
    run_build(world)
    run_validation(world)
    written = publish(world)
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
    run_build(world)
    run_validation(world)
    publish(world)
    assert keep.is_file()


def test_publish_refuses_failed_validation(world):
    run_build(world)
    (world.build_dir / "validation.json").write_text(json.dumps({"passed": False}), encoding="utf-8")
    with pytest.raises(PublishError, match="validation failed"):
        publish(world)


def test_preview_writes_png(world):
    pytest.importorskip("matplotlib")
    from qc2c_build.preview import render

    run_build(world)
    assert render(world).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def _published(world):
    run_build(world)
    run_validation(world)
    publish(world)


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
