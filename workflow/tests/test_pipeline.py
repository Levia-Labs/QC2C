import gzip
import json

from qc2c_build.pipeline import run_build


def test_build_writes_files(world):
    meta = run_build(world)
    names = sorted(p.name for p in world.build_dir.iterdir())
    assert names == ["build.json", "world_sector_1.json", "world_sector_1.json.gz", "world_sector_2.json",
                     "world_sector_2.json.gz", "world_sectors.json", "world_sectors.json.gz"]
    manifest = json.loads(gzip.decompress((world.build_dir / "world_sectors.json.gz").read_bytes()))
    assert list(manifest) == ["world_sector_1.json.gz", "world_sector_2.json.gz"]
    assert meta["codes"] == 7 and meta["gzip_total"] > 0


def test_build_is_deterministic(world):
    run_build(world)
    first = {p.name: p.read_bytes() for p in world.build_dir.glob("world_sector*")}
    run_build(world)
    second = {p.name: p.read_bytes() for p in world.build_dir.glob("world_sector*")}
    assert first == second
