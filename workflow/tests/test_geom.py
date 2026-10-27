import pytest
import shapely
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import LineString, Polygon, box

from qc2c_build.config import ConfigError
from qc2c_build.geom import clamp_to_world, hole_free, make_coverage, polygonal


def test_polygonal_drops_lines_and_repairs():
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
    fixed = polygonal(bowtie)
    assert fixed.is_valid and fixed.area > 0
    assert polygonal(LineString([(0, 0), (1, 1)])).is_empty


def test_hole_free_cuts_every_hole():
    host = box(0, 0, 10, 10).difference(box(2, 2, 3, 3)).difference(box(6, 6, 8, 7))
    pieces = hole_free(host)
    assert all(not p.interiors for p in pieces)
    assert abs(sum(p.area for p in pieces) - host.area) < 1e-9


@given(st.floats(0.5, 4), st.floats(0.5, 4))
def test_hole_free_preserves_area(x, y):
    host = box(0, 0, 10, 10).difference(box(x, y, x + 1, y + 1))
    assert abs(sum(p.area for p in hole_free(host)) - host.area) < 1e-9


def test_make_coverage_overlap_earlier_wins():
    result = make_coverage([("A", box(0, 0, 2, 2)), ("B", box(1, 0, 3, 2))])
    areas = dict(result)
    assert shapely.coverage_is_valid([g for _, g in result])
    assert abs(areas["A"].area - 4) < 1e-9 and abs(areas["B"].area - 2) < 1e-9


def test_make_coverage_nodes_shared_edges():
    left = Polygon([(0, 0), (1, 0), (1, 1), (1, 2), (0, 2)])
    right = Polygon([(1, 0), (2, 0), (2, 2), (1, 2), (1, 1.0000001)])
    result = make_coverage([("L", left), ("R", right)])
    assert [c for c, _ in result] == ["L", "R"]
    assert shapely.coverage_is_valid([g for _, g in result])
    assert abs(sum(g.area for _, g in result) - 4) < 1e-6


@given(st.floats(-181, 181), st.floats(-91, 91), st.floats(0.01, 5))
def test_clamp_to_world_stays_inside_or_raises(x, y, size):
    overshoot = max(x + size - 180, -180 - x, y + size - 90, -90 - y)
    if overshoot > 1e-6:
        with pytest.raises(ConfigError):
            clamp_to_world(box(x, y, x + size, y + size))
        return
    clamped = clamp_to_world(box(x, y, x + size, y + size))
    if not clamped.is_empty:
        min_x, min_y, max_x, max_y = clamped.bounds
        assert -180 <= min_x and max_x <= 180 and -90 <= min_y and max_y <= 90
    width = max(0.0, min(x + size, 180) - max(x, -180))
    height = max(0.0, min(y + size, 90) - max(y, -90))
    assert abs(clamped.area - width * height) < 1e-6


def test_clamp_to_world_pulls_edge_drift_back():
    clamped = clamp_to_world(box(170, 50, 180.0000000002, 60))
    assert clamped.bounds == (170.0, 50.0, 180.0, 60.0)


@pytest.mark.parametrize("shape", [box(170, 50, 180.001, 60), box(-181, 0, -170, 10), box(0, 80, 10, 91),
                                   box(0, -95, 10, -80)])
def test_clamp_to_world_rejects_far_outside_coordinates(shape):
    with pytest.raises(ConfigError, match="outside the world"):
        clamp_to_world(shape)


def test_make_coverage_names_vanished_codes():
    with pytest.raises(ConfigError, match="BBB"):
        make_coverage([("AAA", box(0, 0, 2, 2)), ("BBB", box(0.5, 0.5, 1.5, 1.5))])
