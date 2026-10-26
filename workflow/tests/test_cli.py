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


def test_cli_compare_reports_difference(world):
    main(["build", *args(world)])
    assert main(["compare", *args(world)]) == 1


def test_cli_bad_setting_exits_2(world, capsys):
    assert main(["build", *args(world, "--sea", "ocean")]) == 2
    assert "sea must be one of" in capsys.readouterr().err


def test_cli_missing_input_exits_2(world, tmp_path, capsys):
    assert main(["build", *args(world, "--input-dir", str(tmp_path / "missing"))]) == 2
    assert "qc2c-build:" in capsys.readouterr().err


def test_cli_us_states_flag(world):
    assert main(["build", *args(world, "--us-states")]) == 0
