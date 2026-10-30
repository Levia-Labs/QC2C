"""Every fixture point written by qc2c-build must resolve to its expected code."""

import json
from pathlib import Path

from qc2c import coordinates_to_country

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "points.json"


def test_fixture_points_match_pipeline():
    points = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(points) >= 250
    found = [(p, coordinates_to_country({"lat": p["lat"], "lng": p["lng"]})) for p in points]
    wrong = [(p, code) for p, code in found if code != p["code"]]
    assert not wrong, wrong[:10]
