"""End-to-end mission workflow: simulated report -> evidence + threat -> route compromised by
the threat-zone rules -> alternative -> operator reject/approve -> consistent history and COP."""
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString

from app.config import routing_policy
from app.main import app
from app.repositories.threat_repository import threat_repository
from app.services.routing_service import routing_service
from app.services.scenario_service import scenario_service
from app.services.threat.models import ThreatEventCreate
from app.services.threat.threat_service import threat_service
from app.services.threat.zones import ThreatZoneIndex, zone_from_threat

pytestmark = pytest.mark.requires_graph

client = TestClient(app)

# Demo mission corridor (same as the UI): Navanagar staging -> Hubballi city centre
ORIGIN = {"lat": 15.4030, "lon": 75.0800}
DESTINATION = {"lat": 15.3647, "lon": 75.1240}


@pytest.fixture(autouse=True)
def _clean_threats_dry_weather():
    for t in threat_repository.get_all():
        if t["status"] not in routing_policy.INACTIVE_THREAT_STATUSES:
            threat_service.close_threat(t["incident_id"])
    scenario_service.update_config({"precipitation_mm": 0.0, "intensity_multiplier": 1.0})
    scenario_service.set_active(True)
    yield
    scenario_service.set_active(False)
    scenario_service.update_config({"precipitation_mm": 50.0})


def _start_mission(origin=ORIGIN, destination=DESTINATION):
    route = client.get(f"/api/route?origin_lat={origin['lat']}&origin_lon={origin['lon']}"
                       f"&destination_lat={destination['lat']}&destination_lon={destination['lon']}").json()
    assert route["status"] == "success", route
    reg = client.post("/api/route-monitor/register", json={
        "origin": origin, "destination": destination, "route_nodes": route["route_nodes"],
        "distance_m": route["distance_m"], "estimated_time_s": route["estimated_time_s"]}).json()
    assert reg["monitor_status"] == "ACTIVE", reg
    return reg["route_id"], route


def _touches(node_ids, threat):
    edges = routing_service.route_edge_coordinates(node_ids)
    return bool(ThreatZoneIndex([zone_from_threat(threat)]).intersecting([c for e in edges for c in e]))


def test_simulated_report_creates_linked_labelled_evidence_and_threat_and_compromises_route():
    route_id, route = _start_mission()
    res = client.post("/api/simulation/field-report", json={"route_id": route_id})
    assert res.status_code == 200, res.text
    body = res.json()

    ev, threat = body["evidence"], body["threat"]
    assert body["simulated"] is True
    assert ev["provenance"]["is_simulation"] is True
    assert ev["provenance"]["confidence_basis"] == "DECLARED_BY_SIMULATION_PROFILE"
    assert ev["threat_id"] == threat["incident_id"] and ev["status"] == "ASSOCIATED"
    assert threat["evidence_references"] == [ev["evidence_id"]]
    assert threat["source"] == "SIMULATED_REPORT" and threat["severity"] == "CRITICAL"
    assert threat["confidence"] == "MEDIUM"          # documented single-source rule

    # Compromise is decided by the routing rules: the CRITICAL zone sits on the route.
    assessment = body["route_assessment"]
    assert assessment["current_status"] == "INVALIDATED"
    assert threat["incident_id"] in assessment["reason"]
    assert _touches(route["route_nodes"], threat_repository.get_by_id(threat["incident_id"]))

    history = client.get(f"/api/route-monitor/{route_id}").json()
    assert history["transitions"][-1]["new_status"] == "INVALIDATED"
    assert threat["incident_id"] in history["transitions"][-1]["reason"]

    cop = client.get("/api/cop").json()
    cop_threat = next(t for t in cop["threats"] if t["id"] == threat["incident_id"])
    cop_ev = next(e for e in cop["evidence"] if e["id"] == ev["evidence_id"])
    cop_route = next(r for r in cop["monitored_routes"] if r["id"] == route_id)
    assert cop_threat["is_demo"] is True and cop_ev["is_simulation"] is True
    assert cop_ev["threat_id"] == threat["incident_id"]
    assert cop_route["status"] == "INVALIDATED"


def test_reject_then_approve_alternative_is_recorded_consistently():
    route_id, route = _start_mission()
    report = client.post("/api/simulation/field-report", json={"route_id": route_id}).json()
    threat = threat_repository.get_by_id(report["threat"]["incident_id"])

    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    assert rec["replacement_status"] == "RECOMMENDATION_READY", rec
    assert not _touches(rec["candidate_route"]["route_nodes"], threat)
    # Comparison metrics come from the backend for both routes.
    for key in ("distance_m", "travel_time_s", "hazard_score"):
        assert key in rec["current_route"] and key in rec["candidate_route"]

    rejected = client.post(f"/api/route-monitor/{route_id}/replacement/reject",
                           json={"recommendation_id": rec["recommendation_id"], "reason": "Convoy prefers to hold"})
    assert rejected.status_code == 200
    after_reject = client.get(f"/api/route-monitor/{route_id}").json()
    assert after_reject["monitor_status"] == "INVALIDATED"
    assert after_reject["recommendations"][-1]["status"] == "REJECTED"
    assert after_reject["recommendations"][-1]["decision_reason"] == "Convoy prefers to hold"

    rec2 = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    assert rec2["replacement_status"] == "RECOMMENDATION_READY"
    approved = client.post(f"/api/route-monitor/{route_id}/replacement/approve",
                           json={"recommendation_id": rec2["recommendation_id"], "approved": True})
    assert approved.status_code == 200

    final = client.get(f"/api/route-monitor/{route_id}").json()
    assert final["monitor_status"] == "REPLACED"
    assert [r["status"] for r in final["recommendations"]] == ["REJECTED", "APPROVED"]
    assert final["transitions"][-1]["new_status"] == "REPLACED"
    cop_route = next(r for r in client.get("/api/cop").json()["monitored_routes"] if r["id"] == route_id)
    assert cop_route["status"] == "REPLACED"
    assert not _touches([n for n in rec2["candidate_route"]["route_nodes"]], threat)


def test_unknown_profile_and_route_are_rejected():
    route_id, _ = _start_mission()
    assert client.post("/api/simulation/field-report", json={"route_id": route_id, "profile": "NOPE"}).status_code == 400
    assert client.post("/api/simulation/field-report", json={"route_id": "missing"}).status_code == 404
    profiles = client.get("/api/simulation/profiles").json()
    assert set(profiles["profiles"]) == {"ROAD_FLOODING_SENSOR", "FIELD_TEAM_BLOCKAGE"}


def _dead_end():
    G = routing_service.G
    for node, data in G.nodes(data=True):
        if abs(data["y"] - 15.36) > 0.03 or abs(data["x"] - 75.12) > 0.03:
            continue
        nbrs = set(G.successors(node)) | set(G.predecessors(node))
        if len(nbrs) != 1:
            continue
        other = next(iter(nbrs))
        if not G.has_edge(other, node):
            continue
        k = min(G[other][node], key=lambda kk: G[other][node][kk].get("length", 0))
        if G[other][node][k].get("length", 0) < 200:
            continue
        mid = LineString(routing_service.edge_coordinates(other, node, G[other][node][k])).interpolate(0.5, normalized=True)
        return node, (mid.y, mid.x)
    pytest.skip("no suitable dead-end edge")


def test_no_safe_alternative_is_reported_honestly():
    routing_service.load_graph()
    dead_end, (mlat, mlon) = _dead_end()
    dest = {"lat": routing_service.G.nodes[dead_end]["y"], "lon": routing_service.G.nodes[dead_end]["x"]}
    route_id, _ = _start_mission(origin={"lat": 15.3647, "lon": 75.1240}, destination=dest)
    threat_service.create_threat(ThreatEventCreate(
        title="Access road cut", category="Road Obstruction", severity="CRITICAL",
        latitude=mlat, longitude=mlon, radius_m=10.0, source="SIMULATED_REPORT"))

    check = client.post(f"/api/route-monitor/{route_id}/check").json()
    assert check["current_status"] == "INVALIDATED"
    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    assert rec["replacement_status"] == "NO_SAFE_AVAILABLE_ROUTE"
    assert "recommendation_id" not in rec
    detail = client.get(f"/api/route-monitor/{route_id}").json()
    assert detail["recommendations"] == []
    # The honest failure is part of the mission record (survives a reload).
    attempts = detail["replacement_attempts"]
    assert [a["outcome"] for a in attempts] == ["NO_SAFE_AVAILABLE_ROUTE"]
    assert attempts[0]["message"] and attempts[0]["timestamp"]
