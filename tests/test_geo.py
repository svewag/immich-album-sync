"""Tests for the geo helpers (Haversine distance + nearest-location match)."""
from __future__ import annotations

import pytest

from immich_alben.config import GeoLocation
from immich_alben.geo import haversine_m, match_location, year_from_iso


# --- haversine_m ---------------------------------------------------------

def test_haversine_zero_distance():
    assert haversine_m(48.1374, 11.5755, 48.1374, 11.5755) == pytest.approx(0.0, abs=1e-6)


def test_haversine_marienplatz_to_stachus():
    # Marienplatz (48.1374, 11.5755) <-> Stachus (48.1394, 11.5660)
    # Real-world distance ~ 750-800 m
    d = haversine_m(48.1374, 11.5755, 48.1394, 11.5660)
    assert 700.0 < d < 850.0


def test_haversine_symmetric():
    a = haversine_m(50.0, 8.0, 51.0, 9.0)
    b = haversine_m(51.0, 9.0, 50.0, 8.0)
    assert a == pytest.approx(b, rel=1e-9)


def test_haversine_antipodes_roughly_half_earth_circumference():
    # Antipode of (0,0) is (0,180); great-circle distance ~ 20015 km
    d = haversine_m(0.0, 0.0, 0.0, 180.0)
    assert 20_000_000.0 < d < 20_100_000.0


# --- match_location ------------------------------------------------------

MARIENPLATZ = GeoLocation(name="Marienplatz", lat=48.1374, lon=11.5755, radius_m=500.0)
STACHUS = GeoLocation(name="Stachus", lat=48.1394, lon=11.5660, radius_m=500.0)
TEGERNSEE = GeoLocation(name="Tegernsee", lat=47.7113, lon=11.7553, radius_m=3000.0)


def test_match_returns_none_when_no_locations():
    assert match_location(48.1374, 11.5755, []) is None


def test_match_returns_none_when_outside_all_radii():
    # Hamburg far from all configured Munich locations
    assert match_location(53.5511, 9.9937, [MARIENPLATZ, STACHUS, TEGERNSEE]) is None


def test_match_single_location_within_radius():
    result = match_location(48.1374, 11.5755, [MARIENPLATZ])
    assert result is not None
    assert result.location.name == "Marienplatz"
    assert result.distance_m == pytest.approx(0.0, abs=1e-6)


def test_match_picks_nearest_when_multiple_within_radius():
    # Point very close to Marienplatz but inside a (hypothetical) wider Stachus
    big_stachus = GeoLocation(name="Stachus", lat=48.1394, lon=11.5660, radius_m=5000.0)
    big_marienplatz = GeoLocation(
        name="Marienplatz", lat=48.1374, lon=11.5755, radius_m=5000.0
    )
    # Query point: right on Marienplatz
    result = match_location(48.1374, 11.5755, [big_stachus, big_marienplatz])
    assert result is not None
    assert result.location.name == "Marienplatz"


def test_match_respects_per_location_radius_override():
    # Point ~1.5 km from Tegernsee center: outside default 500m, inside 3000m override
    # Use Marienplatz + Tegernsee (override radius_m=3000)
    # Query ~1.5km from Tegernsee:
    result = match_location(47.7220, 11.7553, [MARIENPLATZ, TEGERNSEE])
    assert result is not None
    assert result.location.name == "Tegernsee"


def test_match_just_outside_radius_returns_none():
    # Place the search point 600m from Marienplatz; default radius is 500
    # Walk ~0.0054° in latitude ≈ 600m north.
    result = match_location(48.1374 + 0.0054, 11.5755, [MARIENPLATZ])
    assert result is None


# --- year_from_iso -------------------------------------------------------

def test_year_from_iso_extracts_year_prefix():
    assert year_from_iso("2024-06-12T10:00:00.000Z") == "2024"


def test_year_from_iso_handles_none():
    assert year_from_iso(None) is None


def test_year_from_iso_handles_empty_or_invalid():
    assert year_from_iso("") is None
    assert year_from_iso("abc") is None
    assert year_from_iso("12") is None
