from dataclasses import replace

import pytest
import shapely
from conftest import WORLD_FEATURES, feature, square, write_inputs

from qc2c_build.config import ConfigError
from qc2c_build.load import MissingOverride, load_features


def codes(cfg):
    return [code for code, _ in load_features(cfg)]


def test_override_replaces_no_code(world):
    assert "NWH" in codes(world)
    assert "-99" not in codes(world)


def test_missing_override_names_feature(world):
    write_inputs(world.input_dir, WORLD_FEATURES, overrides={})
    with pytest.raises(MissingOverride, match="Nowhere"):
        load_features(world)


def test_usa_or_states(world):
    countries = [feature("USA", "United States", [square(-100, 30, -80, 40)]),
                 feature("PRI", "Puerto Rico", [square(-67, 18, -65, 19)])]
    states = [feature("NY", "New York", [square(-80, 35, -75, 40)]),
              feature("PR", "Puerto Rico", [square(-67, 18, -65, 19)]),
              feature("VI", "Virgin Islands", [square(-65, 17, -64, 18)])]
    write_inputs(world.input_dir, countries, states=states)
    assert codes(world) == ["PRI", "USA"]
    with_states = codes(replace(world, us_states=True))
    assert with_states == ["NY", "PRI"]
    assert "VI" not in with_states


def test_override_wins_over_iso_code(world):
    write_inputs(world.input_dir, [feature("AAA", "Name", [square(0, 0, 1, 1)])],
                 overrides={"Name": "BBB"})
    assert codes(world) == ["BBB"]


def test_state_without_code_names_feature(world):
    state = feature("NY", "Lost State", [square(-80, 35, -75, 40)])
    del state["properties"]["ISO_A3"]
    write_inputs(world.input_dir, [], states=[state])
    with pytest.raises(ConfigError, match="Lost State"):
        load_features(replace(world, us_states=True))


def test_same_code_dissolves(world):
    write_inputs(world.input_dir, [feature("AAA", "A1", [square(0, 0, 1, 1)]),
                                   feature("AAA", "A2", [square(5, 5, 6, 6)])])
    [(code, geom)] = load_features(world)
    assert code == "AAA" and abs(geom.area - 2) < 1e-9


def test_overlaps_removed(world):
    write_inputs(world.input_dir, [feature("AAA", "A", [square(0, 0, 2, 2)]),
                                   feature("BBB", "B", [square(1, 1, 3, 3)])])
    (_, a), (_, b) = load_features(world)
    assert a.intersection(b).area < 1e-12
    assert abs(a.area + b.area - 7) < 1e-9


def test_invalid_geometry_is_repaired(world):
    bowtie = [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]
    write_inputs(world.input_dir, [feature("BOW", "Bowtie", bowtie)])
    [(_, geom)] = load_features(world)
    assert geom.is_valid and geom.area > 0


def test_loaded_features_form_a_coverage(world):
    result = load_features(world)
    assert shapely.coverage_is_valid([g for _, g in result])
