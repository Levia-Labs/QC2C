import shapely
from shapely.geometry import Polygon, box

from qc2c_build.geom import EMPTY
from qc2c_build.load import load_features
from qc2c_build.partition import build_partition
from qc2c_build.simplify import restore_lost, simplify_partition


def assert_on_grid(parts, grid):
    for _, geom in parts:
        for poly in shapely.get_parts(geom):
            rings = [poly.exterior, *poly.interiors]
            for ring in rings:
                for x, y in ring.coords:
                    assert abs(round(x / grid) - x / grid) < 1e-6
                    assert abs(round(y / grid) - y / grid) < 1e-6


def test_coordinates_on_grid_and_no_overlap(world):
    parts = simplify_partition(build_partition(load_features(world), world), world)
    assert_on_grid(parts, 0.001)
    total = sum(g.area for _, g in parts)
    assert abs(total - 360 * 180) < 1e-3
    assert shapely.coverage_is_valid([g for _, g in parts])


def test_restore_lost_puts_tiny_code_back():
    big = box(0, 0, 10, 10).difference(box(5, 5, 5.004, 5.004))
    tiny = box(5, 5, 5.004, 5.004)
    original = [("BIG", big), ("TNY", tiny)]
    simplified = [("BIG", box(0, 0, 10, 10)), ("TNY", EMPTY)]
    restored = dict(restore_lost(original, simplified, grid=0.001))
    assert abs(restored["TNY"].area - tiny.area) < 1e-9
    assert restored["BIG"].intersection(restored["TNY"]).area < 1e-12


def test_restore_lost_keeps_neighbours_on_grid():
    tiny = box(5, 3.5, 5.004, 3.504)
    below = Polygon([(0, 0), (10, 0), (10, 7)])
    above = Polygon([(0, 0), (10, 7), (10, 10), (0, 10)])
    original = [("LOW", below.difference(tiny)), ("UP", above.difference(tiny)), ("TNY", tiny)]
    simplified = [("LOW", below), ("UP", above), ("TNY", EMPTY)]
    restored = restore_lost(original, simplified, grid=0.001)
    assert_on_grid(restored, 0.001)
    assert shapely.coverage_is_valid([g for _, g in restored])
    assert abs(dict(restored)["TNY"].area - tiny.area) < 1e-9
