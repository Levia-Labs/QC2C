import pytest
from qc2c import coordinates_to_country, get_country, get_sector, point_in_polygon

SQUARE = [[0, 0], [0, 2], [2, 2], [2, 0]]


def test_point_in_polygon():
    assert point_in_polygon([1, 1], SQUARE)
    assert not point_in_polygon([3, 3], SQUARE)


def test_get_sector_bare_and_dict():
    bare = {"a": [0, 0, 5, 5], "b": [6, 6, 10, 10]}
    wrapped = {k: {"bounds": v, "center": {}} for k, v in bare.items()}
    for manifest in (bare, wrapped):
        assert get_sector(manifest, {"lat": 3, "lng": 3}) == "a"
        assert get_sector(manifest, {"lat": 7, "lng": 7}) == "b"
        assert get_sector(manifest, {"lat": 11, "lng": 11}) is None


def test_get_country_polygon_and_multipolygon():
    far = [[6, 6], [6, 10], [10, 10], [10, 6]]
    single = {"A": SQUARE, "B": far}
    multi = {"A": [SQUARE], "B": [[[20, 20], [20, 21], [21, 21]], far]}
    for manifest in (single, multi):
        assert get_country(manifest, {"lat": 1, "lng": 1}) == "A"
        assert get_country(manifest, {"lat": 7, "lng": 7}) == "B"
        assert get_country(manifest, {"lat": 15, "lng": 15}) is None


@pytest.mark.parametrize(
    "lat,lng,expected",
    [
        (52.23, 21.01, "POL"),
        (40.71, -74.0, "USA"),
        (-33.87, 151.21, "AUS"),
        (35.68, 139.69, "JPN"),
        (0, -140, "PYF"),  # open ocean returns the nearest country (Marquesas)
    ],
)
def test_coordinates_to_country(lat, lng, expected):
    assert coordinates_to_country({"lat": lat, "lng": lng}) == expected
