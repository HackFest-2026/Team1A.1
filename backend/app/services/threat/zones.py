"""Threat-zone geometry shared by routing, monitoring and exposure analysis.

Zones are circles (centre + radius) derived from active threats. Distances are
computed on a local equirectangular projection centred on the zone centre,
which is accurate to well under 1% over the few-kilometre extents used here.
Coordinates are EPSG:4326; line coordinates are GeoJSON order [lon, lat].
"""
import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from app.config import routing_policy
from app.repositories.threat_repository import threat_repository

EARTH_RADIUS_M = 6371000.0
METRES_PER_DEG_LAT = 111320.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_point_to_line_m(lat: float, lon: float, coords: Sequence[Sequence[float]]) -> float:
    """Minimum distance in metres from (lat, lon) to a polyline of [lon, lat] points."""
    if not coords:
        return float("inf")
    if len(coords) == 1:
        return haversine_m(lat, lon, coords[0][1], coords[0][0])

    cos_lat = math.cos(math.radians(lat))

    def to_xy(pt):
        return (math.radians(pt[0] - lon) * EARTH_RADIUS_M * cos_lat,
                math.radians(pt[1] - lat) * EARTH_RADIUS_M)

    best = float("inf")
    ax, ay = to_xy(coords[0])
    for pt in coords[1:]:
        bx, by = to_xy(pt)
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        t = 0.0 if seg_len2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg_len2))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
        ax, ay = bx, by
    return best


def normalize_severity(severity: Optional[str]) -> str:
    sev = (severity or "").upper()
    if sev in routing_policy.BLOCKING_SEVERITIES or sev in routing_policy.SEVERITY_MULTIPLIERS:
        return sev
    return routing_policy.UNKNOWN_SEVERITY


@dataclass
class ThreatZone:
    threat_id: str
    severity: str
    lat: float
    lon: float
    radius_m: float
    title: str = ""
    effective_radius_m: float = field(init=False)
    bbox: Tuple[float, float, float, float] = field(init=False)  # min_lon, min_lat, max_lon, max_lat

    def __post_init__(self):
        self.effective_radius_m = self.radius_m + routing_policy.THREAT_SAFETY_BUFFER_M
        dlat = self.effective_radius_m / METRES_PER_DEG_LAT
        dlon = self.effective_radius_m / (METRES_PER_DEG_LAT * max(math.cos(math.radians(self.lat)), 1e-6))
        self.bbox = (self.lon - dlon, self.lat - dlat, self.lon + dlon, self.lat + dlat)

    @property
    def is_blocking(self) -> bool:
        return self.severity in routing_policy.BLOCKING_SEVERITIES

    def contains_point(self, lat: float, lon: float) -> bool:
        return haversine_m(lat, lon, self.lat, self.lon) <= self.effective_radius_m

    def distance_to_line_m(self, coords: Sequence[Sequence[float]]) -> float:
        return distance_point_to_line_m(self.lat, self.lon, coords)


def zone_from_threat(threat: dict) -> Optional[ThreatZone]:
    """Zone for an active threat with valid geometry, else None."""
    if (threat.get("status") or "").upper() in routing_policy.INACTIVE_THREAT_STATUSES:
        return None
    lat, lon = threat.get("latitude"), threat.get("longitude")
    radius = threat.get("radius_m")
    if lat is None or lon is None or radius is None or float(radius) <= 0:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return ThreatZone(
        threat_id=threat.get("incident_id") or threat.get("threat_id"),
        severity=normalize_severity(threat.get("severity")),
        lat=float(lat), lon=float(lon), radius_m=float(radius),
        title=threat.get("title") or "",
    )


def active_threat_zones(threat_ids: Optional[Iterable[str]] = None) -> List[ThreatZone]:
    wanted = set(threat_ids) if threat_ids else None
    zones = []
    for threat in threat_repository.get_all():
        if wanted is not None and threat.get("incident_id") not in wanted:
            continue
        zone = zone_from_threat(threat)
        if zone is not None:
            zones.append(zone)
    return zones


def edge_multiplier(hits: List[Tuple["ThreatZone", float]], endpoint_zone_ids=frozenset()) -> Optional[float]:
    """Travel-time multiplier for an edge touched by the given zones, or None if blocked.

    - Any blocking (CRITICAL) zone blocks the edge, unless that zone contains the
      route origin/destination, in which case ENDPOINT_ZONE_MULTIPLIER applies.
    - Overlapping non-blocking zones do not compound: the strongest single multiplier
      applies, so duplicate reports of one hazard are not double-counted.
    """
    multiplier = 1.0
    for zone, _dist in hits:
        if zone.is_blocking:
            if zone.threat_id not in endpoint_zone_ids:
                return None
            factor = routing_policy.ENDPOINT_ZONE_MULTIPLIER
        else:
            factor = routing_policy.SEVERITY_MULTIPLIERS[zone.severity]
        multiplier = max(multiplier, factor)
    return multiplier


class ThreatZoneIndex:
    """Bounding-box prefiltered lookup of zones intersecting line geometries."""

    def __init__(self, zones: List[ThreatZone]):
        self.zones = zones

    def __bool__(self):
        return bool(self.zones)

    def intersecting(self, coords: Sequence[Sequence[float]]) -> List[Tuple[ThreatZone, float]]:
        """Zones whose effective radius reaches the line, with the distance in metres."""
        if not self.zones or not coords:
            return []
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        min_lon, max_lon, min_lat, max_lat = min(lons), max(lons), min(lats), max(lats)
        hits = []
        for zone in self.zones:
            z_min_lon, z_min_lat, z_max_lon, z_max_lat = zone.bbox
            if max_lon < z_min_lon or min_lon > z_max_lon or max_lat < z_min_lat or min_lat > z_max_lat:
                continue
            dist = zone.distance_to_line_m(coords)
            if dist <= zone.effective_radius_m:
                hits.append((zone, dist))
        return hits
