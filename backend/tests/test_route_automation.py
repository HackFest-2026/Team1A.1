"""Automatic route reassessment on threat changes, operator-attributed decisions, and
labelling of incidents created from the built-in demo region list."""
import pytest
from fastapi.testclient import TestClient

from app.config import routing_policy
from app.main import app
from app.repositories.threat_repository import threat_repository
from app.services.incidents.incident_service import incident_service
from app.services.route_replacement_service import ACTOR_BASIS
from app.services.scenario_service import scenario_service
from app.services.threat.threat_service import threat_service

client = TestClient(app)
requires_graph = pytest.mark.requires_graph

# Demo mission corridor (same as the UI): Navanagar staging -> Hubballi city centre
ORIGIN = {"lat": 15.4030, "lon": 75.0800}
DESTINATION = {"lat": 15.3647, "lon": 75.1240}


@pytest.fixture(autouse=True)
def _clean_threats_dry_weather():
    for t in threat_repository.get_all():
        if t["status"] not in routing_policy.INACTIVE_THREAT_STATUSES:
            threat_service.close_threat(t["incident_id"], reassess_routes=False)
    scenario_service.update_config({"precipitation_mm": 0.0, "intensity_multiplier": 1.0})
    scenario_service.set_active(True)
    yield
    scenario_service.set_active(False)
    scenario_service.update_config({"precipitation_mm": 50.0})


def _start_mission():
    route = client.get(f"/api/route?origin_lat={ORIGIN['lat']}&origin_lon={ORIGIN['lon']}"
                       f"&destination_lat={DESTINATION['lat']}&destination_lon={DESTINATION['lon']}").json()
    assert route["status"] == "success", route
    reg = client.post("/api/route-monitor/register", json={
        "origin": ORIGIN, "destination": DESTINATION, "route_nodes": route["route_nodes"],
        "distance_m": route["distance_m"], "estimated_time_s": route["estimated_time_s"]}).json()
    assert reg["monitor_status"] == "ACTIVE", reg
    return reg["route_id"], route


def _midpoint(route):
    coords = route["route"]["coordinates"]
    lon, lat = coords[len(coords) // 2]
    return lat, lon


def _post_threat(lat, lon, severity="CRITICAL", radius_m=60.0):
    res = client.post("/api/threats", json={
        "title": "TEST: external report", "category": "Road Flooding", "severity": severity,
        "latitude": lat, "longitude": lon, "radius_m": radius_m, "source": "SIMULATED_REPORT"})
    assert res.status_code == 201, res.text
    return res.json()


def _detail(route_id):
    return client.get(f"/api/route-monitor/{route_id}").json()


@requires_graph
def test_threat_created_through_api_invalidates_route_without_a_check():
    route_id, route = _start_mission()
    threat = _post_threat(*_midpoint(route))

    detail = _detail(route_id)  # no /check call anywhere
    assert detail["monitor_status"] == "INVALIDATED"
    last = detail["transitions"][-1]
    assert last["new_status"] == "INVALIDATED"
    assert last["trigger"] == "THREAT_CHANGE"
    assert threat["incident_id"] in last["reason"]

    # A later manual check reports the stored reason instead of an empty one.
    check = client.post(f"/api/route-monitor/{route_id}/check").json()
    assert check["changed"] is False
    assert threat["incident_id"] in check["reason"]
    assert check["reason_recorded_at"] == last["timestamp"]


@requires_graph
def test_closing_a_threat_triggers_reassessment():
    route_id, route = _start_mission()
    threat = _post_threat(*_midpoint(route))
    before = _detail(route_id)
    assert before["monitor_status"] == "INVALIDATED"

    res = client.post(f"/api/threats/{threat['incident_id']}/close", params={"reason": "cleared"})
    assert res.status_code == 200, res.text

    after = _detail(route_id)
    assert after["last_checked_at"] > before["last_checked_at"]
    # Downgrading is only allowed on complete data (no DEM -> terrain unknown -> kept).
    if after["monitor_status"] == "ACTIVE":
        assert after["transitions"][-1]["trigger"] == "THREAT_CHANGE"
    else:
        assert after["monitor_status"] == "INVALIDATED"


@requires_graph
def test_replaced_route_stays_replaced_when_an_unrelated_threat_is_recorded():
    route_id, _ = _start_mission()
    client.post("/api/simulation/field-report", json={"route_id": route_id})
    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    assert rec["replacement_status"] == "RECOMMENDATION_READY", rec
    client.post(f"/api/route-monitor/{route_id}/replacement/approve",
                json={"recommendation_id": rec["recommendation_id"], "approved": True})
    replaced = _detail(route_id)
    assert replaced["monitor_status"] == "REPLACED"

    _post_threat(15.4589, 75.0078, severity="HIGH")  # Dharwad, far from the corridor

    after = _detail(route_id)
    assert after["monitor_status"] == "REPLACED"
    assert len(after["transitions"]) == len(replaced["transitions"])


@requires_graph
def test_decisions_record_a_self_declared_operator_and_reason():
    route_id, _ = _start_mission()
    client.post("/api/simulation/field-report", json={"route_id": route_id})

    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    rejected = client.post(f"/api/route-monitor/{route_id}/replacement/reject", json={
        "recommendation_id": rec["recommendation_id"], "actor": "  Lt. A. Rao \n",
        "reason": "Convoy holds\tfor recce"}).json()
    assert rejected["audit_event"]["actor"] == "Lt. A. Rao"
    assert rejected["audit_event"]["actor_basis"] == ACTOR_BASIS

    rec2 = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    approved = client.post(f"/api/route-monitor/{route_id}/replacement/approve", json={
        "recommendation_id": rec2["recommendation_id"], "approved": True,
        "actor": "Lt. A. Rao", "reason": "x" * 600}).json()
    assert approved["audit_event"]["actor_basis"] == ACTOR_BASIS

    detail = _detail(route_id)
    first, second = detail["recommendations"]
    assert (first["status"], first["decided_by"], first["decision_reason"]) == ("REJECTED", "Lt. A. Rao", "Convoy holds for recce")
    assert (second["status"], second["decided_by"]) == ("APPROVED", "Lt. A. Rao")
    assert len(second["decision_reason"]) == 500
    assert "Lt. A. Rao" in detail["transitions"][-1]["reason"]


@requires_graph
def test_decision_without_a_name_uses_the_default_label():
    route_id, _ = _start_mission()
    client.post("/api/simulation/field-report", json={"route_id": route_id})
    rec = client.post(f"/api/route-monitor/{route_id}/replacement/recommend").json()
    client.post(f"/api/route-monitor/{route_id}/replacement/approve",
                json={"recommendation_id": rec["recommendation_id"], "approved": True, "actor": "   "})
    assert _detail(route_id)["recommendations"][-1]["decided_by"] == "EOC operator"


def test_scan_without_a_risk_feed_creates_clearly_labelled_demo_incidents():
    result = incident_service.scan_for_incidents()
    assert result["source"] == "BUILT_IN_DEMO_REGIONS"
    assert result["new_incidents"]
    for incident_id in result["new_incidents"]:
        inc = incident_service.get_by_id(incident_id)
        assert inc["title"].startswith("DEMO")
        assert inc["official_warning"] == "NONE"      # no fabricated official warning
        assert inc["confidence"] == "MEDIUM"          # never HIGH without a real feed
        assert inc["source"] == "CONTROLLED_DEMO"
        created = inc["timeline"][0]
        assert created["source"] == "DEMO_FIXTURE"
        assert "not a detection" in created["description"]
