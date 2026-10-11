"""COP integration with the canonical evidence store and documented summary rules."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.field_operations.evidence_service import evidence_service as legacy_evidence_service
from app.services.field_operations.models import Evidence as LegacyEvidence
from app.services.field_operations.field_service import field_service
from app.services.field_operations.models import StatusUpdate
from app.services.threat.models import ThreatEventCreate
from app.services.threat.threat_service import threat_service

client = TestClient(app)


def _create_evidence(**overrides):
    payload = {
        "source_type": "DRONE",
        "source_id": "DRONE-07",
        "observation_type": "WATERLOGGING_OBSERVATION",
        "latitude": 15.3650,
        "longitude": 75.1245,
        "confidence": 0.85,
        "description": "Standing water across carriageway",
    }
    payload.update(overrides)
    res = client.post("/api/evidence", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _cop():
    res = client.get("/api/cop")
    assert res.status_code == 200, res.text
    return res.json()


def test_canonical_evidence_appears_in_cop_with_canonical_fields():
    threat = threat_service.create_threat(ThreatEventCreate(
        title="Underpass flooding", category="Waterlogging", latitude=15.365, longitude=75.124))
    ev = _create_evidence(threat_id=threat["incident_id"])

    match = [e for e in _cop()["evidence"] if e["id"] == ev["evidence_id"]]
    assert len(match) == 1
    item = match[0]
    assert item["threat_id"] == threat["incident_id"]
    assert item["source_type"] == "DRONE"
    assert item["observation_type"] == "WATERLOGGING_OBSERVATION"
    assert item["confidence"] == pytest.approx(0.85)
    assert item["status"] == "ASSOCIATED"
    assert item["is_simulation"] is False
    assert item["provenance"]["origin"] == "DRONE-07"


def test_simulated_evidence_is_flagged():
    ev = _create_evidence(source_type="SIMULATION", source_id="SIM-1")
    item = next(e for e in _cop()["evidence"] if e["id"] == ev["evidence_id"])
    assert item["is_simulation"] is True


def test_archived_evidence_is_excluded_from_active_cop():
    ev = _create_evidence()
    assert client.post(f"/api/evidence/{ev['evidence_id']}/archive").status_code == 200

    snapshot = _cop()
    assert ev["evidence_id"] not in {e["id"] for e in snapshot["evidence"]}
    # The record itself is preserved.
    assert client.get(f"/api/evidence/{ev['evidence_id']}").json()["status"] == "ARCHIVED"


def test_legacy_field_evidence_is_not_counted_in_cop():
    legacy = LegacyEvidence(incident_id="INC-LEGACY", evidence_type="PHOTO",
                            file_name="flood.jpg", file_path="/dev/null")
    legacy_evidence_service.add_evidence(legacy)

    ids = {e["id"] for e in _cop()["evidence"]}
    assert legacy.evidence_id not in ids


def test_summary_counts_match_snapshot_and_documented_filters():
    _create_evidence()
    archived = _create_evidence()
    client.post(f"/api/evidence/{archived['evidence_id']}/archive")
    closed = threat_service.create_threat(ThreatEventCreate(
        title="Cleared drain", category="Drainage Overflow", latitude=15.36, longitude=75.12))
    threat_service.close_threat(closed["incident_id"])
    unit_id = field_service.get_all()[0]["field_unit_id"]
    field_service.update_status(unit_id, StatusUpdate(new_status="UNAVAILABLE"))

    snapshot = _cop()
    summary = client.get("/api/cop/summary").json()

    assert summary["active_evidence_count"] == len(snapshot["evidence"])
    assert summary["active_threat_count"] == len(
        [t for t in snapshot["threats"] if t["status"] not in ("CLOSED", "RESOLVED")])
    assert summary["active_unit_count"] == len(
        [u for u in snapshot["field_units"] if u["status"] not in ("COMPLETED", "UNAVAILABLE")])
    assert summary["active_unit_count"] < len(snapshot["field_units"])
    assert summary["monitored_route_count"] == len(snapshot["monitored_routes"])
    assert summary["invalidated_route_count"] == len(
        [r for r in snapshot["monitored_routes"] if r["status"] == "INVALIDATED"])
    # The snapshot embeds the same counts, so a client needs only one request.
    embedded = {k: v for k, v in snapshot["summary"].items() if k != "generated_at"}
    assert embedded == {k: v for k, v in summary.items() if k != "generated_at"}


def test_demo_records_are_labelled():
    demo = threat_service.create_threat(ThreatEventCreate(
        title="Demo flood", category="Flood", latitude=15.36, longitude=75.12, source="CONTROLLED_DEMO"))
    threats = {t["id"]: t for t in _cop()["threats"]}
    assert threats[demo["incident_id"]]["is_demo"] is True
    # Seeded field units are demo units.
    assert all(u["is_demo"] for u in _cop()["field_units"])


@pytest.mark.requires_graph
def test_monitored_route_geometry_comes_from_road_graph():
    route = client.get("/api/route?origin_lat=15.365&origin_lon=75.125"
                       "&destination_lat=15.370&destination_lon=75.130").json()
    reg = client.post("/api/route-monitor/register", json={
        "origin": route["origin"], "destination": route["destination"],
        "route_nodes": route["route_nodes"], "distance_m": route["distance_m"],
        "estimated_time_s": route["estimated_time_s"]}).json()

    item = next(r for r in _cop()["monitored_routes"] if r["id"] == reg["route_id"])
    assert item["geometry"]["type"] == "LineString"
    assert item["geometry"]["coordinates"] == route["route"]["coordinates"]
