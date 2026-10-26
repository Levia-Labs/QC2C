from dataclasses import replace

from conftest import feature, square, write_inputs
from shapely.geometry import Point

from qc2c_build.load import load_features
from qc2c_build.partition import WORLD, build_partition


def code_at(parts, lng, lat):
    point = Point(lng, lat)
    hits = [code for code, geom in parts if geom.covers(point)]
    return hits[0] if hits else None


def test_nearest_covers_world_without_overlap(world):
    parts = build_partition(load_features(world), world)
    assert abs(sum(g.area for _, g in parts) - WORLD.area) < 1e-6 * WORLD.area
    assert code_at(parts, -150, -60) is not None


def test_land_keeps_its_code(world):
    parts = build_partition(load_features(world), world)
    assert code_at(parts, -30, 30) == "ENC"
    assert code_at(parts, -38, 38) == "HST"
    assert code_at(parts, 5, 25) == "WST"
    assert code_at(parts, 15, 25) == "EST"


def test_strait_goes_to_nearest(world):
    parts = build_partition(load_features(world), world)
    assert code_at(parts, 20.4, 23) == "ISL"
    assert code_at(parts, 20.1, 21) == "EST"


def test_distance_mode_leaves_open_sea_empty(world):
    cfg = replace(world, sea="distance", sea_distance_km=111.32)
    parts = build_partition(load_features(cfg), cfg)
    assert code_at(parts, 5, 30.5) == "WST"
    assert code_at(parts, 5, 35) is None


def test_antimeridian_halves_survive(world):
    write_inputs(world.input_dir, [feature("RUS", "Russia", [square(175, 60, 180, 65)], [square(-180, 60, -175, 65)])])
    parts = build_partition(load_features(world), world)
    assert code_at(parts, 178, 62) == "RUS"
    assert code_at(parts, -178, 62) == "RUS"
