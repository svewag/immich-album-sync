from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ImmichConfig:
    base_url: str


@dataclass
class LoggingConfig:
    level: str


@dataclass(frozen=True)
class GeoLocation:
    name: str
    lat: float
    lon: float
    radius_m: float


@dataclass
class GeoConfig:
    locations: list[GeoLocation] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return bool(self.locations)


@dataclass
class Config:
    immich: ImmichConfig
    library_roots: list[str]
    patterns: list[str]
    state_file: Path
    logging: LoggingConfig
    geo: GeoConfig = field(default_factory=GeoConfig)


def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    immich = data.get("immich") or {}
    base_url = immich.get("base_url")
    if not base_url:
        raise ValueError("config: immich.base_url is required")

    library_roots = data.get("library_roots") or []
    if not isinstance(library_roots, list) or not library_roots:
        raise ValueError("config: library_roots must be a non-empty list")

    patterns = data.get("patterns") or []
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("config: patterns must be a non-empty list")

    state_file = data.get("state_file")
    if not state_file:
        raise ValueError("config: state_file is required")

    logging_cfg = data.get("logging") or {}
    level = (logging_cfg.get("level") or "INFO").upper()

    geo = _parse_geo(data.get("geo"))

    return Config(
        immich=ImmichConfig(base_url=base_url.rstrip("/")),
        library_roots=[str(r) for r in library_roots],
        patterns=[str(p) for p in patterns],
        state_file=Path(state_file),
        logging=LoggingConfig(level=level),
        geo=geo,
    )


def _parse_geo(raw: object) -> GeoConfig:
    if raw is None:
        return GeoConfig()
    if not isinstance(raw, dict):
        raise ValueError("config: geo must be a mapping")

    raw_locations = raw.get("locations") or []
    if not isinstance(raw_locations, list):
        raise ValueError("config: geo.locations must be a list")
    if not raw_locations:
        return GeoConfig()

    default_radius = raw.get("default_radius_m")
    if default_radius is None:
        raise ValueError(
            "config: geo.default_radius_m is required when geo.locations is non-empty"
        )
    if not isinstance(default_radius, (int, float)) or default_radius <= 0:
        raise ValueError("config: geo.default_radius_m must be a positive number")

    locations: list[GeoLocation] = []
    for idx, entry in enumerate(raw_locations):
        if not isinstance(entry, dict):
            raise ValueError(f"config: geo.locations[{idx}] must be a mapping")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"config: geo.locations[{idx}].name must be a non-empty string")
        lat = entry.get("lat")
        if not isinstance(lat, (int, float)) or not -90.0 <= float(lat) <= 90.0:
            raise ValueError(f"config: geo.locations[{idx}].lat must be in [-90, 90]")
        lon = entry.get("lon")
        if not isinstance(lon, (int, float)) or not -180.0 <= float(lon) <= 180.0:
            raise ValueError(f"config: geo.locations[{idx}].lon must be in [-180, 180]")
        radius = entry.get("radius_m", default_radius)
        if not isinstance(radius, (int, float)) or radius <= 0:
            raise ValueError(
                f"config: geo.locations[{idx}].radius_m must be a positive number"
            )
        locations.append(
            GeoLocation(
                name=name.strip(),
                lat=float(lat),
                lon=float(lon),
                radius_m=float(radius),
            )
        )

    return GeoConfig(locations=locations)
