import shapely
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import LineString, Polygon, box

from qc2c_build.geom import hole_free, make_coverage, polygonal


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
