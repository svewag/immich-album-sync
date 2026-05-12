from __future__ import annotations

import math
from dataclasses import dataclass

from .config import GeoLocation


EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_M * c


@dataclass(frozen=True)
class GeoMatch:
    location: GeoLocation
    distance_m: float


def match_location(
    lat: float, lon: float, locations: list[GeoLocation]
) -> GeoMatch | None:
    """Return the closest location whose radius contains (lat, lon), else None."""
    best: GeoMatch | None = None
    for loc in locations:
        d = haversine_m(lat, lon, loc.lat, loc.lon)
        if d > loc.radius_m:
            continue
        if best is None or d < best.distance_m:
            best = GeoMatch(location=loc, distance_m=d)
    return best


def year_from_iso(value: str | None) -> str | None:
    """Extract a 4-digit year prefix from an ISO timestamp."""
    if not value or len(value) < 4:
        return None
    head = value[:4]
    if not head.isdigit():
        return None
    return head
