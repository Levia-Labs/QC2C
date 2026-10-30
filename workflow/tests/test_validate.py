import gzip
import json
from dataclasses import replace

import numpy as np
from conftest import WORLD_FEATURES, feature, square, write_inputs
from qc2c_build import validate
from qc2c_build.load import load_features
from qc2c_build.pipeline import run_build
from qc2c_build.sectors import read_sectors
from qc2c_build.validate import (
    PointSet,
    classify,
    fixture,
    load_output,
    lookup,
    run_validation,
    source_points,
)


def test_classify_border_core_ambiguous(world):
    features = load_features(world)
    points = PointSet(
        np.array([[10.0, 25.0], [9.9, 25.0], [5.0, 25.0]]),
        np.array(["WST", "WST", "WST"], dtype=object),
    )
    assert classify(points, features, 0.5).tolist() == [2, 1, 0]


def test_every_code_gets_interior_samples(world):
    features = load_features(world)
    points = source_points(features, 10, 1)
    assert set(points.code) == {code for code, _ in features}


def test_validation_passes_on_synthetic_world(world):
    run_build(world)
    report = run_validation(world)
    assert report["passed"], report["failures"]
    assert report["counts"]["core"] > 0
    assert report["accuracy"]["core"] == 1.0
    saved = json.loads((world.build_dir / "validation.json").read_text(encoding="utf-8"))
    assert saved["passed"] is True
    points = json.loads((world.build_dir / "points.json").read_text(encoding="utf-8"))
    assert {"lat", "lng", "code"} <= set(points[0])


def test_missing_sector_file_fails(world):
    run_build(world)
    (world.build_dir / "world_sector_2.json.gz").unlink()
    report = run_validation(world)
    assert not report["passed"]
    assert any("world_sector_2.json.gz" in f for f in report["failures"])


def test_border_threshold_enforced(world, monkeypatch):
    cfg = replace(world, min_border_accuracy=1.0)
    run_build(cfg)
    monkeypatch.setattr(
        validate, "lookup", lambda manifest, files, xy: np.full(len(xy), None, dtype=object)
    )
    report = run_validation(cfg)
    assert report["counts"]["border"] > 0
    assert report["accuracy"]["border"] == 0.0
    assert any("border accuracy" in f for f in report["failures"])


def test_fixture_avoids_sector_edges(world):
    features = load_features(world)
    sectors = read_sectors(world.input_file(world.sectors))
    xy = np.array([[45.0, 0.0], [45.0, 5.0], [5.0, 25.0]])
    points = PointSet(xy, np.array(["SPN", "SPN", "WST"], dtype=object))
    kind = classify(points, features, 0.5)
    chosen = fixture(points, kind, sectors, 1)
    assert all(p["lat"] != 0.0 for p in chosen)


def test_fixture_avoids_longitude_edges():
    sectors = {"a": [0, -180, 90, 0], "b": [0, 0, 90, 180]}
    points = PointSet(
        np.array([[0.0, 10.0], [5.0, 10.0], [-5.0, 10.0]]),
        np.array(["AAA", "AAA", "AAA"], dtype=object),
    )
    chosen = fixture(points, np.zeros(3, dtype=np.int8), sectors, 1)
    assert chosen and all(p["lng"] != 0.0 for p in chosen)


def test_fixture_falls_back_to_border_point_for_code_without_core():
    sectors = {"a": [0, -180, 90, 180]}
    codes = np.array(["BIG", "TIN", "TIN", "LST"], dtype=object)
    points = PointSet(np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]]), codes)
    kind = np.array([0, 1, 1, 1], dtype=np.int8)
    got = np.array(["BIG", "TIN", "OTH", "OTH"], dtype=object)
    chosen = fixture(points, kind, sectors, 1, got=got)
    assert sorted((p["code"], p["lng"]) for p in chosen) == [("BIG", 1.0), ("TIN", 2.0)]


def test_synthetic_world_reports_fixture_missing(world):
    run_build(world)
    report = run_validation(world)
    assert report["fixture_missing"] == []


def test_truncated_gzip_fails_without_raising(world):
    run_build(world)
    path = world.build_dir / "world_sector_1.json.gz"
    path.write_bytes(path.read_bytes()[:-10])
    report = run_validation(world)
    assert not report["passed"]
    assert any("world_sector_1.json.gz" in f for f in report["failures"])


def test_non_object_manifest_fails_without_raising(world):
    run_build(world)
    (world.build_dir / "world_sectors.json.gz").write_bytes(gzip.compress(b"[1, 2]"))
    report = run_validation(world)
    assert not report["passed"]
    assert any("not a JSON object" in f for f in report["failures"])


def test_manifest_bounds_mismatch_fails(world):
    run_build(world)
    path = world.build_dir / "world_sectors.json.gz"
    manifest = json.loads(gzip.decompress(path.read_bytes()))
    manifest["world_sector_1.json.gz"]["bounds"][0] += 1
    path.write_bytes(gzip.compress(json.dumps(manifest).encode("utf-8")))
    report = run_validation(world)
    assert not report["passed"]
    assert any("manifest bounds differ" in f for f in report["failures"])


def _corrupt_manifest(world, edit):
    run_build(world)
    path = world.build_dir / "world_sectors.json.gz"
    manifest = json.loads(gzip.decompress(path.read_bytes()))
    edit(manifest["world_sector_1.json.gz"])
    path.write_bytes(gzip.compress(json.dumps(manifest).encode("utf-8")))
    return run_validation(world)


def _corrupt_sector(world, edit):
    run_build(world)
    path = world.build_dir / "world_sector_1.json.gz"
    sector = json.loads(gzip.decompress(path.read_bytes()))
    edit(sector)
    path.write_bytes(gzip.compress(json.dumps(sector).encode("utf-8")))
    return run_validation(world)


def _assert_failed(report, text):
    assert not report["passed"]
    assert any(text in f for f in report["failures"])


def test_non_numeric_bound_fails_without_raising(world):
    _assert_failed(
        _corrupt_manifest(world, lambda e: e["bounds"].__setitem__(0, "x")), "no valid bounds"
    )


def test_non_finite_bound_fails_without_raising(world):
    _assert_failed(
        _corrupt_manifest(world, lambda e: e["bounds"].__setitem__(0, 1e999)), "no valid bounds"
    )


def test_non_object_center_fails_without_raising(world):
    _assert_failed(
        _corrupt_manifest(world, lambda e: e.__setitem__("center", [1, 2])), "no valid center"
    )


def test_ring_not_a_list_fails_without_raising(world):
    def edit(sector):
        sector[next(iter(sector))][0] = "ring"

    _assert_failed(_corrupt_sector(world, edit), "world_sector_1.json.gz")


def test_pair_with_three_numbers_fails_without_raising(world):
    def edit(sector):
        sector[next(iter(sector))][0][0] = [1, 2, 3]

    _assert_failed(_corrupt_sector(world, edit), "world_sector_1.json.gz")


def test_ring_with_two_points_fails_without_raising(world):
    def edit(sector):
        ring = sector[next(iter(sector))][0]
        del ring[2:]

    _assert_failed(_corrupt_sector(world, edit), "world_sector_1.json.gz")


def test_sector_not_mapping_to_rings_fails_without_raising(world):
    _assert_failed(
        _corrupt_sector(world, lambda s: s.__setitem__("AAA", 5)), "world_sector_1.json.gz"
    )


def test_world_edge_vertices_resolve(world):
    # Real borders carry 180.0000000000002 on the antimeridian; every such vertex must resolve.
    edge = [
        feature("EDG", "Edge", [square(170, 50, 180.0000000000002, 60)]),
        feature("TRI", "Tri", [[[175, -60], [180.0000000000002, -55], [175, -50], [175, -60]]]),
    ]
    write_inputs(world.input_dir, WORLD_FEATURES + edge, overrides={"Nowhere": "NWH"})
    run_build(world)
    report = run_validation(world)
    assert report["passed"], report["failures"]
    manifest, sector_files = load_output(world.build_dir)
    xy = np.array(
        [[180.0, 50.0], [180.0, 60.0], [180.0, -55.0], [-180.0, 0.0], [180.0, 90.0], [0.0, -90.0]]
    )
    found = lookup(manifest, sector_files, xy).tolist()
    assert None not in found
    assert found[2] == "TRI"
