from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from qc2c_build.config import DEFAULTS, BuildConfig, ConfigError, load_config


def test_defaults():
    assert DEFAULTS.tolerance == 0.05
    assert DEFAULTS.decimals == 3
    assert DEFAULTS.sea == "nearest"
    assert DEFAULTS.us_states is False


def test_precedence(tmp_path: Path):
    toml = tmp_path / "qc2c.toml"
    toml.write_text("tolerance = 0.1\n", encoding="utf-8")
    assert load_config(toml, env={}).tolerance == 0.1
    assert load_config(toml, env={"QC2C_TOLERANCE": "0.2"}).tolerance == 0.2
    assert load_config(toml, env={"QC2C_TOLERANCE": "0.2"}, cli={"tolerance": "0.3"}).tolerance == 0.3


def test_cli_none_keeps_lower_layers():
    assert load_config(None, env={"QC2C_DECIMALS": "4"}, cli={"decimals": None}).decimals == 4


def test_bool_from_env():
    assert load_config(None, env={"QC2C_US_STATES": "yes"}).us_states is True
    with pytest.raises(ConfigError, match="true or false"):
        load_config(None, env={"QC2C_US_STATES": "maybe"})


def test_unknown_toml_key(tmp_path: Path):
    toml = tmp_path / "qc2c.toml"
    toml.write_text("tolerence = 0.1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown setting: tolerence"):
        load_config(toml, env={})


def test_malformed_toml_is_config_error(tmp_path: Path):
    toml = tmp_path / "qc2c.toml"
    toml.write_text("sea = [", encoding="utf-8")
    with pytest.raises(ConfigError, match="qc2c.toml"):
        load_config(toml, env={})


@pytest.mark.parametrize("bad", [{"sea": "ocean"}, {"out": "../x"}, {"decimals": 9}, {"tolerance": -1},
                                 {"samples": 0}, {"min_border_accuracy": 1.5}])
def test_invalid_values(bad):
    with pytest.raises(ConfigError):
        BuildConfig(**bad)


def test_paths(tmp_path: Path):
    cfg = BuildConfig(input_dir=tmp_path / "in", output_dir=tmp_path / "out", out="trial")
    assert cfg.build_dir == tmp_path / "out" / "trial"
    assert cfg.input_file("world_sectors.json") == tmp_path / "in" / "world_sectors.json"
    assert cfg.input_file(str(tmp_path / "abs.json")) == tmp_path / "abs.json"
    assert cfg.as_dict()["input_dir"] == str(tmp_path / "in")


@given(st.floats(min_value=0, max_value=10, allow_nan=False))
def test_tolerance_roundtrips_from_text(value):
    assert load_config(None, env={}, cli={"tolerance": repr(value)}).tolerance == value


FLOAT_FIELDS = ["tolerance", "presimplify", "voronoi_spacing", "sea_distance_km", "min_border_accuracy"]


@pytest.mark.parametrize("field", FLOAT_FIELDS)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_rejected(field, bad):
    with pytest.raises(ConfigError, match=field):
        BuildConfig(**{field: bad})


@pytest.mark.parametrize("text", ["nan", "inf"])
def test_non_finite_text_rejected(text):
    with pytest.raises(ConfigError, match="tolerance"):
        load_config(None, env={}, cli={"tolerance": text})


def test_int_fields_reject_bool_and_fractions():
    assert load_config(None, env={}, cli={"decimals": 3.0}).decimals == 3
    with pytest.raises(ConfigError, match="decimals"):
        load_config(None, env={}, cli={"decimals": 3.9})
    with pytest.raises(ConfigError, match="samples"):
        load_config(None, env={}, cli={"samples": True})
