import shapely
from conftest import WORLD_FEATURES, feature, square, write_inputs
from qc2c_build import simplify
from qc2c_build.geom import EMPTY
from qc2c_build.load import load_features
from qc2c_build.partition import build_partition
from qc2c_build.simplify import restore_lost, simplify_partition, snapped_land
from shapely.geometry import LineString, Polygon, box


def assert_on_grid(parts, grid):
    for _, geom in parts:
        for poly in shapely.get_parts(geom):
            rings = [poly.exterior, *poly.interiors]
            for ring in rings:
                for x, y in ring.coords:
                    assert abs(round(x / grid) - x / grid) < 1e-6
                    assert abs(round(y / grid) - y / grid) < 1e-6


def test_no_restore_path_is_on_grid_and_a_valid_coverage(world):
    features = load_features(world)
    parts = simplify_partition(build_partition(features, world), features, world)
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


def test_restore_lost_keeps_valid_coverage():
    tiny = box(5, 3.65, 5.004, 3.654)
    below = Polygon([(0, 0), (10, 0), (10, 7.3)])
    above = Polygon([(0, 0), (10, 7.3), (10, 10), (0, 10)])
    original = [("LOW", below.difference(tiny)), ("UP", above.difference(tiny)), ("TNY", tiny)]
    simplified = [("LOW", below), ("UP", above), ("TNY", EMPTY)]
    restored = restore_lost(original, simplified, grid=0.001)
    assert shapely.coverage_is_valid([g for _, g in restored])
    assert abs(dict(restored)["TNY"].area - tiny.area) < 1e-9
    union = shapely.union_all([g for _, g in restored])
    assert abs(union.area - 100) < 1e-9


def test_restore_lost_uses_land_not_partition_area():
    # The host swallowed the microstate's land; the microstate keeps only sea,
    # which alone is far above half of its partition area.
    land_host = box(0, 0, 10, 10).difference(box(4, 4, 4.01, 4.01))
    land_micro = box(4, 4, 4.01, 4.01)
    sea_micro = box(4.01, 4, 4.5, 4.01)
    simplified = [("HST", box(0, 0, 10, 10).difference(sea_micro)), ("MIC", sea_micro)]
    restored = dict(restore_lost([("HST", land_host), ("MIC", land_micro)], simplified, grid=0.001))
    assert restored["MIC"].contains(land_micro.buffer(-1e-6))
    assert restored["MIC"].intersects(sea_micro.buffer(-1e-6))  # sea kept
    assert restored["HST"].intersection(land_micro).area < 1e-9
    assert shapely.coverage_is_valid([restored["HST"], restored["MIC"]])
    assert abs(sum(g.area for g in restored.values()) - 100) < 1e-9


def test_restore_lost_leaves_intact_land_alone():
    land = [("A", box(0, 0, 5, 10)), ("B", box(5, 0, 10, 10))]
    simplified = [("A", box(0, 0, 5.2, 10)), ("B", box(5.2, 0, 10, 10))]
    assert restore_lost(land, simplified, grid=0.001) == simplified


def test_world_edges_covered_after_simplify(world):
    features = load_features(world)
    parts = simplify_partition(build_partition(features, world), features, world)
    union = shapely.union_all([g for _, g in parts])
    for line in (
        [(-180, -90), (180, -90)],
        [(-180, 90), (180, 90)],
        [(-180, -90), (-180, 90)],
        [(180, -90), (180, 90)],
    ):
        assert LineString(line).difference(union).length == 0


def test_restore_lost_covers_land_smaller_than_a_cell():
    # One grid cell holds less than 70% of this land when snapped to the nearest vertices.
    land = box(10.0004, 20.0004, 10.0014, 20.0014)
    host = box(0, 0, 30, 30).difference(land)
    restored = dict(
        restore_lost(
            [("HST", host), ("MIC", land)], [("HST", box(0, 0, 30, 30)), ("MIC", EMPTY)], grid=0.001
        )
    )
    assert restored["MIC"].intersection(land).area >= 0.9 * land.area
    assert shapely.coverage_is_valid([g for g in restored.values()])
    assert_on_grid(list(restored.items()), 0.001)


def test_snapped_land_ignores_cells_that_only_touch():
    # 0.7 / 0.001 is a hair under 700, so floor() starts one row below the land;
    # that row only touches it.
    land = box(0.7004, 0.7, 0.7014, 0.7004)
    cover = snapped_land(land, 0.001, 0.9)
    assert cover.bounds == (0.7, 0.7, 0.702, 0.701)
    assert abs(cover.area - 2e-6) < 1e-12


def test_restore_lost_later_restore_keeps_earlier_restored_land():
    # Both lands are smaller than a cell and the cells covering them overlap in one cell.
    land_a = box(10.0004, 20.0004, 10.0014, 20.0014)
    land_b = box(10.0016, 20.0004, 10.0026, 20.0014)
    host = box(0, 0, 30, 30).difference(land_a).difference(land_b)
    land = [("HST", host), ("MCA", land_a), ("MCB", land_b)]
    simplified = [("HST", box(0, 0, 30, 30)), ("MCA", EMPTY), ("MCB", EMPTY)]
    restored = dict(restore_lost(land, simplified, grid=0.001))
    assert restored["MCA"].intersection(land_a).area >= land_a.area - 1e-12
    assert restored["MCB"].intersection(land_b).area >= land_b.area - 1e-12
    assert shapely.coverage_is_valid(list(restored.values()))
    assert abs(sum(g.area for g in restored.values()) - 900) < 1e-9


def test_restore_lost_adds_a_land_code_missing_from_the_simplified_list():
    tiny = box(5, 5, 5.004, 5.004)
    host = box(0, 0, 10, 10).difference(tiny)
    restored = dict(
        restore_lost([("HST", host), ("TNY", tiny)], [("HST", box(0, 0, 10, 10))], grid=0.001)
    )
    assert abs(restored["TNY"].area - tiny.area) < 1e-9
    assert restored["HST"].intersection(restored["TNY"]).area < 1e-12


def test_synthetic_world_restores_a_microstate_end_to_end(world, monkeypatch):
    micro = square(-39, 21, -38.996, 21.004)
    write_inputs(
        world.input_dir,
        [*WORLD_FEATURES, feature("AAA", "Micro", [micro])],
        overrides={"Nowhere": "NWH"},
    )
    calls = []
    original = simplify.snapped_land
    monkeypatch.setattr(
        simplify, "snapped_land", lambda *args: calls.append(args) or original(*args)
    )
    features = load_features(world)
    parts = simplify_partition(build_partition(features, world), features, world)
    land = dict(features)["AAA"]
    assert calls, "the restore path did not run"
    assert dict(parts)["AAA"].intersection(land).area >= 0.9 * land.area
    assert shapely.coverage_is_valid([g for _, g in parts])
    assert_on_grid(parts, 0.001)
