import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("============================================================")
    print("  PHASE 6H: CITIZEN SAFETY & ALERT DELIVERY")
    print("============================================================")
    
    # Setup mock incident
    from app.services.incidents.incident_service import incident_service
    from app.services.incidents.models import Incident
    inc = Incident(
        title="DEMO EXTREME FLOOD", hazard_type="Flood", severity="CRITICAL",
        state="Karnataka", district="Dharwad", latitude=15.3647, longitude=75.1240,
        source="SYSTEM", description="Demo incident for Phase 6H."
    )
    incident_service.incidents[inc.incident_id] = inc
    
    # 1. Citizen listing & filtering
    r = client.get("/api/national/citizens?state=Karnataka")
    assert r.status_code == 200
    citizens = r.json()["records"]
    assert len(citizens) > 0
    print("PASS  Citizen listing and basic filters")
    
    # 2. Alert targeting logic
    r = client.get(f"/api/national/incidents/{inc.incident_id}/target-citizens?radius_km=15.0")
    assert r.status_code == 200
    targeted = r.json()["records"]
    assert len(targeted) > 0
    c_id = targeted[0]["citizen_id"]
    print(f"PASS  Alert geographic targeting (found {len(targeted)} citizens in radius)")
    
    # 3. Create citizen alert
    r = client.post("/api/national/citizen-alerts", json={
        "incident_id": inc.incident_id,
        "citizen_id": c_id,
        "severity": "CRITICAL",
        "title": "CRITICAL FLOOD ALERT",
        "message": "Heavy rainfall and flood risk have increased.",
        "channel": "SMS",
        "demo": True
    })
    assert r.status_code == 200
    alert_id = r.json()["record"]["alert_id"]
    print("PASS  Citizen alert draft creation")
    
    # Invalid severity
    r_err = client.post("/api/national/citizen-alerts", json={
        "incident_id": inc.incident_id,
        "citizen_id": c_id,
        "severity": "UNKNOWN_SEV",
        "title": "Bad severity",
        "message": "...",
        "demo": True
    })
    assert r_err.status_code == 400
    print("PASS  Alert validation checks")
    
    # 4. Approval Workflow & invalid send
    r_err = client.post(f"/api/national/citizen-alerts/{alert_id}/send")
    assert r_err.status_code == 400 # Must be approved first
    
    r = client.post(f"/api/national/citizen-alerts/{alert_id}/approve")
    assert r.status_code == 200
    print("PASS  Alert approval workflow")
    
    # 5. Alert Sending and Mock Delivery
    r = client.post(f"/api/national/citizen-alerts/{alert_id}/send")
    assert r.status_code == 200
    print("PASS  Alert sending and provider abstraction")
    
    # 6. Acknowledgement
    r = client.post(f"/api/national/citizen-alerts/{alert_id}/acknowledge")
    assert r.status_code == 200
    assert r.json()["alert"]["status"] == "ACKNOWLEDGED"
    
    r_err = client.post(f"/api/national/citizen-alerts/{alert_id}/acknowledge")
    assert r_err.status_code == 400 # Already acknowledged
    print("PASS  Citizen acknowledgement logic")
    
    # 7. Coverage Dashboard
    r = client.get(f"/api/national/alerts/coverage/{inc.incident_id}")
    assert r.status_code == 200
    metrics = r.json()["metrics"]
    assert metrics["targeted"] > 0
    assert metrics["acknowledged"] == 1
    assert "coverage_percentage" in metrics
    print("PASS  Coverage calculations")
    
    # 8. Preparedness Engine
    r = client.get("/api/national/preparedness?hazard_type=Flood&risk_level=CRITICAL")
    assert r.status_code == 200
    guidance = r.json()["record"]
    assert len(guidance["actions"]) > 0
    assert len(guidance["avoid"]) > 0
    print("PASS  Preparedness guidance generation")
    
    # 9. Citizen Observations
    r = client.post("/api/national/citizen-observations", json={
        "incident_id": inc.incident_id,
        "description": "Water reached my doorstep.",
        "latitude": 15.365,
        "longitude": 75.125,
        "demo": True
    })
    assert r.status_code == 200
    obs_id = r.json()["record"]["observation_id"]
    
    r = client.post(f"/api/national/citizen-observations/{obs_id}/verify", json={
        "status": "VERIFIED"
    })
    assert r.status_code == 200
    print("PASS  Citizen observation integration")
    
    # 10. Incident Timeline Check
    r = client.get(f"/api/national/incidents/{inc.incident_id}")
    inc_data = r.json()["record"]
    events = [e["event_type"] for e in inc_data["timeline"]]
    
    assert "ALERT_DRAFT_CREATED" in events
    assert "ALERT_APPROVED" in events
    assert "ALERT_SENT" in events
    assert "ALERT_DELIVERED" in events
    assert "ALERT_ACKNOWLEDGED" in events
    assert "CITIZEN_OBSERVATION_RECEIVED" in events
    assert "CITIZEN_OBSERVATION_VERIFIED" in events
    assert "REASSESSMENT_RECOMMENDED" in events
    print("PASS  Full incident timeline integration for 6H")
    
    print("\n============================================================")
    print("  ALL 6H TESTS PASSED")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
