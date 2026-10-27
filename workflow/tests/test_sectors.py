import json

import pytest
from conftest import TWO_SECTORS
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import Point, Polygon, box

from qc2c_build.config import ConfigError
from qc2c_build.sectors import check_tiling, read_sectors, ring_coords, sector_box, split_into_sectors


def test_tiling_ok():
    check_tiling(TWO_SECTORS)


def test_tiling_overlap_and_gap():
    with pytest.raises(ConfigError, match="overlap"):
        check_tiling({"a.json": [-90, -180, 90, 180], "b.json": [0, 0, 10, 10]})
    with pytest.raises(ConfigError, match="gaps"):
        check_tiling({"a.json": [0, -180, 90, 180]})


def test_ring_coords_order_and_dedup():
    polygon = Polygon([(1.00001, 2.0), (1.00002, 2.0), (3.0, 2.0), (3.0, 4.0)])
    assert ring_coords(polygon, 3) == [[2.0, 1.0], [2.0, 3.0], [4.0, 3.0]]
    assert ring_coords(Polygon([(0, 0), (0.0001, 0), (0, 0.0001)]), 3) == []


@given(st.floats(-180, 180), st.floats(-90, 90), st.integers(0, 6))
def test_rounding_moves_at_most_half_a_unit(x, y, decimals):
    polygon = Polygon([(x, y), (x + 1, y), (x + 1, y + 1)])
    ring = ring_coords(polygon, decimals)
    half = 0.5 * 10.0 ** -decimals + 1e-9
    if ring:
        assert abs(ring[0][0] - y) <= half and abs(ring[0][1] - x) <= half


@given(st.floats(-170, 160), st.floats(-80, 70), st.floats(0.1, 10), st.floats(0.1, 10))
def test_clipping_preserves_area(x, y, w, h):
    shape = box(x, y, x + w, y + h)
    total = sum(shape.intersection(sector_box(b)).area for b in TWO_SECTORS.values())
    assert abs(total - shape.area) < 1e-9


def test_split_spans_sectors_and_cuts_holes():
    host = box(-40, 20, -20, 40).difference(box(-32, 28, -28, 32))
    parts = [("ENC", box(-32, 28, -28, 32)), ("HST", host), ("SPN", box(40, -10, 50, 10))]
    files, manifest = split_into_sectors(parts, parts, TWO_SECTORS, 3)
    assert "SPN" in files["world_sector_1.json"] and "SPN" in files["world_sector_2.json"]
    assert list(files["world_sector_1.json"])[0] == "ENC"
    assert all(len(ring) >= 3 for ring in files["world_sector_1.json"]["HST"])
    assert manifest["world_sector_1.json.gz"]["bounds"] == [0, -180, 90, 180]
    assert manifest["world_sector_1.json.gz"]["center"]["ENC"] == [30.0, -30.0]


def write_sectors(tmp_path, data):
    path = tmp_path / "world_sectors.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("data", [
    [1, 2],
    {"a.json": "abcd"},
    {"a.json": 5},
    {"a.json": None},
    {"a.json": [0, 1, 2]},
    {"a.json": [0, 0, "x", 10]},
    {"a.json": [0, 0, True, 10]},
    {"a.json": [10, 0, 0, 10]},
    {"a.json": [0, 10, 10, 0]},
    {"a.json": [0, 0, 0, 10]},
    {"world_sectors.json": [-90, -180, 90, 180]},
    {"a.json": [-90, -180, 90, float("nan")]},
])
def test_read_sectors_rejects_bad_input_with_config_error(tmp_path, data):
    with pytest.raises(ConfigError):
        read_sectors(write_sectors(tmp_path, data))


def test_read_sectors_names_reserved_manifest(tmp_path):
    with pytest.raises(ConfigError, match="reserved"):
        read_sectors(write_sectors(tmp_path, {"world_sectors.json": [-90, -180, 90, 180]}))


def test_box_outside_world_is_not_reported_as_overlap():
    with pytest.raises(ConfigError, match="outside the world"):
        check_tiling({"a.json": [-90, -180, 90, 180], "b.json": [90, 0, 100, 10]})
    with pytest.raises(ConfigError, match="outside the world"):
        check_tiling({"a.json": [-90, -180, 90, 190]})


def test_read_sectors_accepts_valid_file(tmp_path):
    assert read_sectors(write_sectors(tmp_path, TWO_SECTORS)) == TWO_SECTORS


def test_center_lies_inside_written_rings_of_thin_country():
    # The land is a thin sliver; simplification moved the written geometry off the land point.
    land = box(0, 0, 10, 0.2)
    simplified = box(0, 0.3, 10, 1.0)
    sectors = {"world_sector_1.json": [-90, -180, 90, 180]}
    _, manifest = split_into_sectors([("THN", simplified)], [("THN", land)], sectors, 3)
    lat, lng = manifest["world_sector_1.json.gz"]["center"]["THN"]
    assert simplified.covers(Point(lng, lat))


def test_split_enclave_first_match_and_hole_free_host():
    host = box(-40, 20, -20, 40).difference(box(-32, 28, -28, 32))
    parts = [("HST", host), ("ENC", box(-32, 28, -28, 32))]
    files, _ = split_into_sectors(parts, parts, TWO_SECTORS, 3)
    rings = [(code, ring) for code, code_rings in files["world_sector_1.json"].items() for ring in code_rings]
    polygons = [(code, Polygon([(lng, lat) for lat, lng in ring])) for code, ring in rings]
    inside = Point(-30, 30)
    first = next(code for code, polygon in polygons if polygon.covers(inside))
    assert first == "ENC"
    assert not any(polygon.covers(inside) for code, polygon in polygons if code == "HST")
    assert abs(sum(p.area for c, p in polygons if c == "HST") - host.area) < 1e-9
