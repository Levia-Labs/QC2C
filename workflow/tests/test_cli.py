import sys

from qc2c_build.cli import main


def args(cfg, *extra):
    return ["--config", "none.toml", "--input-dir", str(cfg.input_dir), "--output-dir", str(cfg.output_dir),
            "--packages-dir", str(cfg.packages_dir), "--presimplify", "0", "--voronoi-spacing", "1", "--samples", "10", *extra]


def test_cli_build_validate_publish_compare(world, capsys):
    assert main(["build", *args(world)]) == 0
    assert main(["validate", *args(world)]) == 0
    assert main(["publish", *args(world)]) == 0
    assert main(["compare", *args(world)]) == 0
    assert "built" in capsys.readouterr().out


def test_cli_compare_reports_difference(world, capsys):
    for command in ("build", "validate", "publish"):
        assert main([command, *args(world)]) == 0
    shipped = next(p for p in world.packages_dir.rglob("world_sector*") if p.suffix == ".json")
    shipped.write_bytes(shipped.read_bytes() + b" ")
    capsys.readouterr()
    assert main(["compare", *args(world)]) == 1
    assert "differs:" in capsys.readouterr().out


def test_cli_malformed_config_exits_2(world, tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text("sea = [", encoding="utf-8")
    argv = args(world)
    argv[1] = str(bad)
    assert main(["build", *argv]) == 2
    assert "qc2c-build:" in capsys.readouterr().err


def test_cli_preview_without_matplotlib_exits_2(world, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "qc2c_build.preview", None)
    assert main(["preview", *args(world)]) == 2
    assert "preview needs the 'preview' extra" in capsys.readouterr().err


def test_cli_bad_setting_exits_2(world, capsys):
    assert main(["build", *args(world, "--sea", "ocean")]) == 2
    assert "sea must be one of" in capsys.readouterr().err


def test_cli_missing_input_exits_2(world, tmp_path, capsys):
    assert main(["build", *args(world, "--input-dir", str(tmp_path / "missing"))]) == 2
    assert "qc2c-build:" in capsys.readouterr().err


def test_cli_us_states_flag(world):
    assert main(["build", *args(world, "--us-states")]) == 0
