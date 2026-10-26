import pytest
from conftest import TWO_SECTORS
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import Polygon, box

from qc2c_build.config import ConfigError
from qc2c_build.sectors import check_tiling, ring_coords, sector_box, split_into_sectors


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
