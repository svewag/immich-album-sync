"""Tests for config loading, especially the optional geo block."""
from __future__ import annotations

from pathlib import Path

import pytest

from immich_alben.config import load_config


_VALID_BASE = """
immich:
  base_url: "http://example:2283"
library_roots:
  - "/mnt/photos"
patterns:
  - "{root}/{year}/{album}"
state_file: "/data/state.json"
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(text)
    return p


# --- baseline (geo absent) -----------------------------------------------

def test_no_geo_block_yields_empty_locations(tmp_path: Path):
    cfg = load_config(_write(tmp_path, _VALID_BASE))
    assert cfg.geo.locations == []
    assert cfg.geo.enabled is False


def test_empty_locations_list_disables_geo(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations: []
"""
    cfg = load_config(_write(tmp_path, text))
    assert cfg.geo.enabled is False


# --- valid geo block -----------------------------------------------------

def test_geo_block_with_default_radius(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations:
    - name: "Marienplatz"
      lat: 48.1374
      lon: 11.5755
"""
    cfg = load_config(_write(tmp_path, text))
    assert cfg.geo.enabled
    assert len(cfg.geo.locations) == 1
    loc = cfg.geo.locations[0]
    assert loc.name == "Marienplatz"
    assert loc.radius_m == 500.0


def test_geo_per_location_radius_override(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations:
    - name: "Marienplatz"
      lat: 48.1374
      lon: 11.5755
    - name: "Tegernsee"
      lat: 47.7113
      lon: 11.7553
      radius_m: 3000
"""
    cfg = load_config(_write(tmp_path, text))
    radii = {loc.name: loc.radius_m for loc in cfg.geo.locations}
    assert radii == {"Marienplatz": 500.0, "Tegernsee": 3000.0}


# --- invalid geo configurations -----------------------------------------

def test_geo_locations_without_default_radius_raises(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  locations:
    - name: "Marienplatz"
      lat: 48.1374
      lon: 11.5755
"""
    with pytest.raises(ValueError, match="default_radius_m"):
        load_config(_write(tmp_path, text))


def test_geo_invalid_latitude_raises(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations:
    - name: "Nordpol+1"
      lat: 91
      lon: 0
"""
    with pytest.raises(ValueError, match=r"lat"):
        load_config(_write(tmp_path, text))


def test_geo_invalid_longitude_raises(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations:
    - name: "Off"
      lat: 0
      lon: 200
"""
    with pytest.raises(ValueError, match=r"lon"):
        load_config(_write(tmp_path, text))


def test_geo_empty_name_raises(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations:
    - name: ""
      lat: 48
      lon: 11
"""
    with pytest.raises(ValueError, match="name"):
        load_config(_write(tmp_path, text))


def test_geo_zero_default_radius_raises(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 0
  locations:
    - name: "X"
      lat: 48
      lon: 11
"""
    with pytest.raises(ValueError, match="default_radius_m"):
        load_config(_write(tmp_path, text))


def test_geo_negative_location_radius_raises(tmp_path: Path):
    text = _VALID_BASE + """
geo:
  default_radius_m: 500
  locations:
    - name: "X"
      lat: 48
      lon: 11
      radius_m: -10
"""
    with pytest.raises(ValueError, match="radius_m"):
        load_config(_write(tmp_path, text))
