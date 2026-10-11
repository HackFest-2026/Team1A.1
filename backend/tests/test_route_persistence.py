"""Monitored-route state transitions and replacement decisions survive reloads/restarts."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.route_recommendation_repository import route_recommendation_repository
from app.services.cop.cop_service import cop_service
from app.services.route_monitor_service import RouteMonitorService
from app.services.route_replacement_service import RouteReplacementService
from app.services.routing_service import routing_service

pytestmark = pytest.mark.requires_graph

client = TestClient(app)

ORIGIN = {"lat": 15.365, "lon": 75.125}
DEST = {"lat": 15.370, "lon": 75.130}


def _register_route():
    route = routing_service.calculate_route(ORIGIN["lat"], ORIGIN["lon"], DEST["lat"], DEST["lon"])
    res = client.post("/api/route-monitor/register", json={
        "origin": ORIGIN, "destination": DEST, "route_nodes": route["route_nodes"],
        "distance_m": route["distance_m"], "estimated_time_s": route["estimated_time_s"]})
    assert res.status_code == 200, res.text
    return res.json()["route_id"], route


def test_manual_invalidation_survives_cop_reload_and_restart():
    route_id, _ = _register_route()
    before = RouteMonitorService().get_route_record(route_id)

    res = client.post(f"/api/route-monitor/{route_id}/invalidate",
                      json={"reason": "Bridge closed by police", "actor": "operator-1"})
    assert res.status_code == 200, res.text

    # The COP poll reloads route state from the database; this used to discard the change.
    cop_service.get_cop_snapshot()
    assert client.get(f"/api/route-monitor/{route_id}").json()["monitor_status"] == "INVALIDATED"

    # Fresh service instance == backend restart against the same database.
    record = RouteMonitorService().get_route_record(route_id)
    assert record["monitor_status"] == "INVALIDATED"
    last = record["transitions"][-1]
    assert last["trigger"] == "MANUAL"
    assert last["actor"] == "operator-1"
    assert last["reason"] == "Bridge closed by police"
    assert last["previous_status"] == before["monitor_status"]
    # A manual report must not fabricate hazard measurements.
    assert record["current_hazard_summary"] == before["current_hazard_summary"]


def test_invalidation_without_body_and_unknown_route():
    route_id, _ = _register_route()
    assert client.post(f"/api/route-monitor/{route_id}/invalidate").status_code == 200
    assert client.post("/api/route-monitor/does-not-exist/invalidate").status_code == 404


def test_cop_reports_invalidated_route():
    route_id, _ = _register_route()
    client.post(f"/api/route-monitor/{route_id}/invalidate")
    summary = client.get("/api/cop/summary").json()
    routes = {r["id"]: r for r in client.get("/api/cop").json()["monitored_routes"]}
    assert routes[route_id]["status"] == "INVALIDATED"
    assert summary["invalidated_route_count"] >= 1


def _pending_recommendation(route_id, route):
    rec_id = f"rec-{route_id[:8]}"
    route_recommendation_repository.save({
        "recommendation_id": rec_id, "route_id": route_id, "status": "PENDING",
        "candidate_route": {**route, "hazard_summary": {"overall_score": 10.0, "critical_segments": 0}},
        "reason": "test", "created_at": "2026-10-09T00:00:00"})
    return rec_id


def test_approval_decision_persists_across_restart():
    route_id, route = _register_route()
    rec_id = _pending_recommendation(route_id, route)

    # A fresh service instance (restart) can still find and approve the recommendation.
    res = RouteReplacementService().approve_replacement(route_id, rec_id, actor="operator-2")
    assert res["status"] == "success"

    stored = route_recommendation_repository.get_by_id(rec_id)
    assert stored["status"] == "APPROVED"
    assert stored["decided_by"] == "operator-2"
    assert stored["decided_at"]
    record = RouteMonitorService().get_route_record(route_id)
    assert record["monitor_status"] == "REPLACED"
    assert record["previous_route_nodes"] == route["route_nodes"]

    again = client.post(f"/api/route-monitor/{route_id}/replacement/approve",
                        json={"recommendation_id": rec_id, "approved": True})
    assert again.status_code == 400
    assert "already APPROVED" in again.json()["detail"]


def test_rejection_decision_persists():
    route_id, route = _register_route()
    rec_id = _pending_recommendation(route_id, route)
    res = client.post(f"/api/route-monitor/{route_id}/replacement/reject",
                      json={"recommendation_id": rec_id, "reason": "Convoy already en route"})
    assert res.status_code == 200, res.text
    stored = route_recommendation_repository.get_by_id(rec_id)
    assert stored["status"] == "REJECTED"
    assert stored["decision_reason"] == "Convoy already en route"
