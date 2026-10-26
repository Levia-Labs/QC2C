import json
from dataclasses import replace

import numpy as np
from conftest import WORLD_FEATURES, feature, square, write_inputs

from qc2c_build.load import load_features
from qc2c_build.pipeline import run_build
from qc2c_build.sectors import read_sectors
from qc2c_build.validate import PointSet, load_output, lookup, classify, fixture, run_validation, source_points


def test_classify_border_core_ambiguous(world):
    features = load_features(world)
    points = PointSet(np.array([[10.0, 25.0], [9.9, 25.0], [5.0, 25.0]]), np.array(["WST", "WST", "WST"], dtype=object))
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


def test_border_threshold_enforced(world):
    cfg = replace(world, tolerance=3.0, min_border_accuracy=1.0)
    run_build(cfg)
    report = run_validation(cfg)
    assert report["accuracy"]["core"] == 1.0
    if report["accuracy"]["border"] < 1.0:
        assert any("border" in f for f in report["failures"])


def test_fixture_avoids_sector_edges(world):
    features = load_features(world)
    sectors = read_sectors(world.input_file(world.sectors))
    xy = np.array([[45.0, 0.0], [45.0, 5.0], [5.0, 25.0]])
    points = PointSet(xy, np.array(["SPN", "SPN", "WST"], dtype=object))
    kind = classify(points, features, 0.5)
    chosen = fixture(points, kind, sectors, 1)
    assert all(p["lat"] != 0.0 for p in chosen)


def test_world_edge_vertices_resolve(world):
    # Real borders carry 180.0000000000002 on the antimeridian; every such vertex must resolve.
    edge = [feature("EDG", "Edge", [square(170, 50, 180.0000000000002, 60)]),
            feature("TRI", "Tri", [[[175, -60], [180.0000000000002, -55], [175, -50], [175, -60]]])]
    write_inputs(world.input_dir, WORLD_FEATURES + edge, overrides={"Nowhere": "NWH"})
    run_build(world)
    report = run_validation(world)
    assert report["passed"], report["failures"]
    manifest, sector_files = load_output(world.build_dir)
    xy = np.array([[180.0, 50.0], [180.0, 60.0], [180.0, -55.0], [-180.0, 0.0], [180.0, 90.0], [0.0, -90.0]])
    found = lookup(manifest, sector_files, xy).tolist()
    assert None not in found
    assert found[2] == "TRI"
