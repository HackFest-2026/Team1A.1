"""Threat-zone geometry in route exposure, routing, monitoring and replacement (ADR-007)."""
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString

from app.config import routing_policy
from app.main import app
from app.repositories.threat_repository import threat_repository
from app.services.route_monitor_service import RouteMonitorService
from app.services.routing_service import routing_service
from app.services.scenario_service import scenario_service
from app.services.threat.models import ThreatEventCreate
from app.services.threat.threat_service import threat_service
from app.services.threat.zones import ThreatZoneIndex, distance_point_to_line_m, zone_from_threat

client = TestClient(app)

ORIGIN = (15.3550, 75.1150)
DEST = (15.3750, 75.1350)


@pytest.fixture(autouse=True)
def _no_active_threats_dry_weather():
    """Each test starts with no active threats and deterministic dry weather.

    Dry weather is set through the (labelled) controlled scenario at 0 mm so the
    hazard component is known and deterministic and only threats drive the outcome.
    """
    for t in threat_repository.get_all():
        if t["status"] not in routing_policy.INACTIVE_THREAT_STATUSES:
            threat_service.close_threat(t["incident_id"])
    scenario_service.update_config({"precipitation_mm": 0.0, "intensity_multiplier": 1.0})
    scenario_service.set_active(True)
    yield
    scenario_service.set_active(False)
    scenario_service.update_config({"precipitation_mm": 50.0})


def _threat(lat, lon, severity="CRITICAL", radius_m=30.0, **extra):
    return threat_service.create_threat(ThreatEventCreate(
        title=f"{severity} test zone", category="Road Obstruction", severity=severity,
        latitude=lat, longitude=lon, radius_m=radius_m, **extra))


def _route(origin=ORIGIN, dest=DEST, **params):
    query = "&".join(f"{k}={str(v).lower()}" for k, v in params.items())
    res = client.get(f"/api/route?origin_lat={origin[0]}&origin_lon={origin[1]}"
                     f"&destination_lat={dest[0]}&destination_lon={dest[1]}&{query}")
    assert res.status_code == 200, res.text
    return res.json()


def _mid_coordinate(route):
    coords = route["route"]["coordinates"]
    lon, lat = coords[len(coords) // 2]
    return lat, lon


def _route_touches_zone(route, threat):
    zone = zone_from_threat(threat)
    edges = routing_service.route_edge_coordinates(route["route_nodes"])
    return bool(ThreatZoneIndex([zone]).intersecting([c for e in edges for c in e]))


# --- Pure geometry -----------------------------------------------------------

def test_point_to_segment_distance_uses_full_segment():
    # Segment ~2.1 km long along lat 15.36; point on it, midway between vertices.
    line = [[75.110, 15.360], [75.130, 15.360]]
    assert distance_point_to_line_m(15.360, 75.120, line) == pytest.approx(0.0, abs=0.5)
    # 0.001 deg north ≈ 111 m.
    assert distance_point_to_line_m(15.361, 75.120, line) == pytest.approx(111.3, abs=1.0)


def test_exposure_detects_segment_crossing_zone_between_vertices():
    """Old implementation measured vertices only and missed this crossing."""
    t = _threat(15.360, 75.120, severity="HIGH", radius_m=100.0)
    res = client.post("/api/threats/assess-exposure", json={
        "route_coordinates": [[75.110, 15.360], [75.130, 15.360]],
        "threat_ids": [t["incident_id"]], "safety_buffer_m": 0.0})
    body = res.json()
    assert body["exposed"] is True
    assert body["details"][0]["distance_to_center_m"] == pytest.approx(0.0, abs=0.5)


# --- Routing -----------------------------------------------------------------

pytestmark_graph = pytest.mark.requires_graph


@pytestmark_graph
def test_baseline_route_unchanged_without_active_threats():
    with_policy = _route()
    without_policy = _route(avoid_threats=False)
    assert with_policy["route_nodes"] == without_policy["route_nodes"]
    assert with_policy["threat_exposure"]["active_zone_count"] == 0
    assert with_policy["threat_exposure"]["exposed"] is False


@pytestmark_graph
def test_critical_zone_is_avoided():
    baseline = _route()
    t = _threat(*_mid_coordinate(baseline))
    assert _route_touches_zone(baseline, t)

    rerouted = _route()
    assert rerouted["status"] == "success"
    assert rerouted["route_nodes"] != baseline["route_nodes"]
    assert not _route_touches_zone(rerouted, t)
    assert rerouted["estimated_time_s"] >= baseline["estimated_time_s"]
    assert t["incident_id"] not in {a["threat_id"] for a in rerouted["threat_exposure"]["affected_threats"]}

    # Opting out of the policy reproduces the baseline.
    assert _route(avoid_threats=False)["route_nodes"] == baseline["route_nodes"]


@pytestmark_graph
def test_closed_threat_has_no_effect():
    baseline = _route()
    t = _threat(*_mid_coordinate(baseline))
    threat_service.close_threat(t["incident_id"])
    assert _route()["route_nodes"] == baseline["route_nodes"]


@pytestmark_graph
def test_unavoidable_high_zone_is_penalized_and_reported():
    baseline = _route()
    end_lon, end_lat = baseline["route"]["coordinates"][-1]
    t = _threat(end_lat, end_lon, severity="HIGH", radius_m=150.0)

    route = _route()
    entry = next(a for a in route["threat_exposure"]["affected_threats"] if a["threat_id"] == t["incident_id"])
    assert entry["effect"] == "PENALIZED"
    assert entry["travel_time_multiplier"] == routing_policy.SEVERITY_MULTIPLIERS["HIGH"]
    assert route["threat_exposure"]["policy"]["calibrated"] is False


@pytestmark_graph
def test_critical_zone_containing_destination_is_reported_not_silently_blocked():
    baseline = _route()
    end_lon, end_lat = baseline["route"]["coordinates"][-1]
    t = _threat(end_lat, end_lon, severity="CRITICAL", radius_m=80.0)

    route = _route()
    assert route["status"] == "success"
    assert t["incident_id"] in route["threat_exposure"]["endpoint_zone_ids"]
    entry = next(a for a in route["threat_exposure"]["affected_threats"] if a["threat_id"] == t["incident_id"])
    assert entry["effect"] == "ENDPOINT_UNAVOIDABLE"


def _dead_end_access_edge():
    """A dead-end node whose only road is long enough to block without covering either end."""
    G = routing_service.G
    for node, data in G.nodes(data=True):
        if abs(data["y"] - 15.36) > 0.03 or abs(data["x"] - 75.12) > 0.03:
            continue
        neighbours = set(G.successors(node)) | set(G.predecessors(node))
        if len(neighbours) != 1:
            continue
        other = next(iter(neighbours))
        if not G.has_edge(other, node):
            continue
        k = min(G[other][node], key=lambda kk: G[other][node][kk].get("length", 0))
        if G[other][node][k].get("length", 0) < 200:
            continue
        line = LineString(routing_service.edge_coordinates(other, node, G[other][node][k]))
        mid = line.interpolate(0.5, normalized=True)
        return node, other, (mid.y, mid.x)
    pytest.skip("no suitable dead-end edge found in graph")


@pytestmark_graph
def test_no_safe_route_when_only_access_is_blocked():
    routing_service.load_graph()
    dead_end, _, (mid_lat, mid_lon) = _dead_end_access_edge()
    dest = (routing_service.G.nodes[dead_end]["y"], routing_service.G.nodes[dead_end]["x"])
    t = _threat(mid_lat, mid_lon, severity="CRITICAL", radius_m=10.0)

    blocked = _route(dest=dest)
    assert blocked["status"] == "no_safe_route"
    assert t["incident_id"] in blocked["blocking_threat_ids"]

    ctx = client.get(f"/api/geo/route-context?origin_lat={ORIGIN[0]}&origin_lon={ORIGIN[1]}"
                     f"&destination_lat={dest[0]}&destination_lon={dest[1]}&include_elevation=false")
    assert ctx.status_code == 409
    assert ctx.json()["detail"]["status"] == "no_safe_route"

    assert _route(dest=dest, avoid_threats=False)["status"] == "success"


@pytestmark_graph
def test_hazard_aware_route_never_contains_critical_segments():
    scenario_service.update_config({"precipitation_mm": 300.0})
    scenario_service.set_active(True)
    res = _route(origin=(15.3647, 75.1240), dest=(15.3700, 75.1300), hazard_aware=True)
    if res["status"] == "success":
        assert res["hazard_summary"]["critical_segments"] == 0
    else:
        assert res["status"] == "no_safe_route"
        assert res["blocked_hazard_edges"] > 0


# --- Monitoring, replacement, geo-context ------------------------------------

def _register(route):
    res = client.post("/api/route-monitor/register", json={
        "origin": {"lat": ORIGIN[0], "lon": ORIGIN[1]}, "destination": {"lat": DEST[0], "lon": DEST[1]},
        "route_nodes": route["route_nodes"], "distance_m": route["distance_m"],
        "estimated_time_s": route["estimated_time_s"]})
    assert res.status_code == 200, res.text
    return res.json()["route_id"]


@pytestmark_graph
def test_critical_threat_invalidates_monitored_route_and_replacement_avoids_it():
    baseline = _route()
    route_id = _register(baseline)
    t = _threat(*_mid_coordinate(baseline))

    check = client.post(f"/api/route-monitor/{route_id}/check").json()
    assert check["current_status"] == "INVALIDATED"
    assert t["incident_id"] in check["reason"]

    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    assert rec["replacement_status"] == "RECOMMENDATION_READY", rec
    candidate = {"route_nodes": rec["candidate_route"]["route_nodes"]}
    assert not _route_touches_zone(candidate, t)

    approved = client.post(f"/api/route-monitor/{route_id}/replacement/approve",
                           json={"recommendation_id": rec["recommendation_id"], "approved": True})
    assert approved.status_code == 200
    record = RouteMonitorService().get_route_record(route_id)
    assert record["monitor_status"] == "REPLACED"
    assert record["route_nodes"] == candidate["route_nodes"]


@pytestmark_graph
def test_operator_obstruction_report_creates_threat_and_drives_replacement():
    baseline = _route()
    route_id = _register(baseline)
    mid_lat, mid_lon = _mid_coordinate(baseline)

    res = client.post(f"/api/route-monitor/{route_id}/invalidate", json={
        "reason": "Tree fall blocking carriageway",
        "obstruction": {"lat": mid_lat, "lon": mid_lon, "radius_m": 30.0}}).json()
    threat = threat_service.get_threat(res["obstruction_threat_id"])
    assert threat["severity"] == "CRITICAL" and threat["source"] == "OPERATOR_REPORT"

    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    assert rec["replacement_status"] == "RECOMMENDATION_READY", rec
    assert not _route_touches_zone({"route_nodes": rec["candidate_route"]["route_nodes"]}, threat)


@pytestmark_graph
def test_manual_invalidation_is_not_cleared_by_reassessment():
    route_id = _register(_route())
    client.post(f"/api/route-monitor/{route_id}/invalidate", json={"reason": "Police closure"})
    check = client.post(f"/api/route-monitor/{route_id}/check").json()
    assert check["current_status"] == "INVALIDATED"
    assert check.get("manual_invalidation_retained") is True


@pytestmark_graph
def test_geo_context_lists_only_spatially_related_routes():
    near_route = _route()
    near_id = _register(near_route)
    far_route = _route(origin=(15.4500, 75.0100), dest=(15.4600, 75.0200), avoid_threats=False)
    far_id = client.post("/api/route-monitor/register", json={
        "origin": {"lat": 15.45, "lon": 75.01}, "destination": {"lat": 15.46, "lon": 75.02},
        "route_nodes": far_route["route_nodes"]}).json()["route_id"]

    t = _threat(*_mid_coordinate(near_route), severity="HIGH", radius_m=50.0)
    ctx = client.get(f"/api/threats/{t['incident_id']}/geo-context").json()["route_context"]
    related = {r["route_id"]: r for r in ctx["related_monitored_routes"]}
    assert near_id in related and related[near_id]["distance_m"] <= ctx["search_radius_m"]
    assert far_id not in related


# --- Policy parameters, buffer boundaries, overlapping zones -----------------

def test_policy_parameters_are_the_approved_provisional_defaults():
    assert routing_policy.SEVERITY_MULTIPLIERS == {"HIGH": 3.0, "MODERATE": 1.75, "LOW": 1.25}
    assert routing_policy.THREAT_SAFETY_BUFFER_M == 25.0
    assert routing_policy.BLOCKING_SEVERITIES == frozenset({"CRITICAL"})


def _zone(severity="HIGH", radius_m=100.0, lat=15.36, lon=75.12, threat_id=None):
    return zone_from_threat({"incident_id": threat_id or f"T-{severity}-{radius_m}", "severity": severity,
                             "status": "ACTIVE", "latitude": lat, "longitude": lon, "radius_m": radius_m})


def _east_west_line_at(distance_m, lat=15.36, lon=75.12):
    """A 2 km east-west line whose closest approach to (lat, lon) is distance_m north."""
    import math
    dlat = math.degrees(distance_m / 6371000.0)
    return [[lon - 0.01, lat + dlat], [lon + 0.01, lat + dlat]]


@pytest.mark.parametrize("distance_m,hit", [
    (90.0, True),     # inside the radius
    (110.0, True),    # outside the radius, inside the 25 m buffer
    (124.5, True),    # just inside radius + buffer
    (125.5, False),   # just outside radius + buffer
])
def test_buffer_boundary(distance_m, hit):
    zone = _zone(radius_m=100.0)
    hits = ThreatZoneIndex([zone]).intersecting(_east_west_line_at(distance_m))
    assert bool(hits) is hit
    if hit:
        assert hits[0][1] == pytest.approx(distance_m, abs=0.5)


def test_overlapping_zones_do_not_compound():
    from app.services.threat.zones import edge_multiplier
    high_a, high_b = _zone("HIGH", threat_id="A"), _zone("HIGH", threat_id="B")
    moderate, low = _zone("MODERATE", threat_id="M"), _zone("LOW", threat_id="L")
    critical = _zone("CRITICAL", threat_id="C")
    assert edge_multiplier([]) == 1.0
    assert edge_multiplier([(high_a, 0), (high_b, 0)]) == 3.0
    assert edge_multiplier([(moderate, 0), (low, 0)]) == 1.75
    assert edge_multiplier([(high_a, 0), (critical, 0)]) is None
    assert edge_multiplier([(high_a, 0), (critical, 0)], endpoint_zone_ids={"C"}) == \
        routing_policy.ENDPOINT_ZONE_MULTIPLIER


@pytestmark_graph
def test_routing_detects_segment_crossing_without_vertex_inside_and_reports_overlaps():
    routing_service.load_graph()
    dead_end, other, (mid_lat, mid_lon) = _dead_end_access_edge()
    G = routing_service.G
    # Neither end of the access edge is within the zones; only the segment crosses them.
    a = _threat(mid_lat, mid_lon, severity="HIGH", radius_m=10.0)
    b = _threat(mid_lat + 0.00005, mid_lon, severity="MODERATE", radius_m=10.0)
    for n in (dead_end, other):
        for t in (a, b):
            assert not zone_from_threat(t).contains_point(G.nodes[n]["y"], G.nodes[n]["x"])

    dest = (G.nodes[dead_end]["y"], G.nodes[dead_end]["x"])
    route = _route(dest=dest)
    assert route["status"] == "success"
    affected = {x["threat_id"]: x for x in route["threat_exposure"]["affected_threats"]}
    assert affected[a["incident_id"]]["effect"] == "PENALIZED"
    assert affected[a["incident_id"]]["travel_time_multiplier"] == 3.0
    assert affected[b["incident_id"]]["travel_time_multiplier"] == 1.75
