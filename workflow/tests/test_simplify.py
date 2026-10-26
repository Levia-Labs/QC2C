import shapely
from shapely.geometry import box

from qc2c_build.geom import EMPTY
from qc2c_build.load import load_features
from qc2c_build.partition import build_partition
from qc2c_build.simplify import restore_lost, simplify_partition


def test_coordinates_on_grid_and_no_overlap(world):
    parts = simplify_partition(build_partition(load_features(world), world), world)
    for _, geom in parts:
        for x, y in geom.exterior.coords if geom.geom_type == "Polygon" else []:
            assert abs(round(x * 1000) - x * 1000) < 1e-6
            assert abs(round(y * 1000) - y * 1000) < 1e-6
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
