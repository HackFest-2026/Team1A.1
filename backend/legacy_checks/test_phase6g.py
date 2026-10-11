import sys
import os
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("============================================================")
    print("  PHASE 6G: FIELD OPERATIONS & EVIDENCE INTELLIGENCE")
    print("============================================================")
    
    # 1. Setup Incident
    from app.services.incidents.incident_service import incident_service
    from app.services.incidents.models import Incident
    inc = Incident(
        title="DEMO EXTREME FLOOD",
        hazard_type="Flood",
        severity="HIGH",
        state="Karnataka",
        district="Dharwad",
        latitude=15.3647,
        longitude=75.1240,
        source="SYSTEM",
        description="Demo incident for Phase 6G."
    )
    incident_service.incidents[inc.incident_id] = inc
    
    # 2. Field Unit Creation
    r = client.post("/api/national/field-units", json={
        "name": "Rescue Team Alpha (Demo)",
        "unit_type": "RESCUE_TEAM",
        "demo": True
    })
    assert r.status_code == 200, r.text
    fu_id = r.json()["record"]["field_unit_id"]
    print("PASS  Field unit creation")
    
    # 3. Coordinate validation
    r = client.post(f"/api/national/field-units/{fu_id}/location", json={
        "latitude": 999.0, # Invalid
        "longitude": 75.1240,
        "accuracy_m": 10.0
    })
    assert r.status_code == 422 # FastAPI validation
    
    r = client.post(f"/api/national/field-units/{fu_id}/location", json={
        "latitude": 15.36,
        "longitude": 75.12,
        "accuracy_m": 5.5
    })
    assert r.status_code == 200
    print("PASS  Coordinate validation & Location updates")
    
    # 4. Status transitions
    r = client.post(f"/api/national/field-units/{fu_id}/status", json={"new_status": "EN_ROUTE"})
    assert r.status_code == 200
    
    r = client.post(f"/api/national/field-units/{fu_id}/status", json={"new_status": "COMPLETED"})
    # Invalid transition (EN_ROUTE -> COMPLETED)
    assert r.status_code == 400
    print("PASS  Field status lifecycle and invalid transitions")
    
    # 5. Evidence Upload
    r = client.post(f"/api/national/incidents/{inc.incident_id}/evidence", data={
        "file_name": "flood_photo.jpg",
        "evidence_type": "PHOTO",
        "demo": True
    })
    assert r.status_code == 200
    ev_id = r.json()["record"]["evidence_id"]
    
    r = client.post(f"/api/national/incidents/{inc.incident_id}/evidence", data={
        "file_name": "virus.exe",
        "evidence_type": "PHOTO"
    })
    assert r.status_code == 400 # Unsupported type
    print("PASS  Evidence upload & file type validation")
    
    # 6. Evidence Analysis
    r = client.post(f"/api/national/evidence/{ev_id}/analyze")
    assert r.status_code == 200
    analysis = r.json()["evidence"]
    assert analysis["ai_label"] == "FLOOD_WATER_VISIBLE"
    print("PASS  Evidence CV analysis")
    
    # 7. Human Confirmation
    r = client.post(f"/api/national/evidence/{ev_id}/confirm?confirmation=CONFIRMED")
    assert r.status_code == 200
    print("PASS  Human evidence confirmation")
    
    # 8. Field Reports & Reassessment
    r = client.post(f"/api/national/incidents/{inc.incident_id}/field-reports", json={
        "incident_id": inc.incident_id,
        "summary": "Water rising, road blocked",
        "severity_observation": "CRITICAL",
        "access_condition": "BLOCKED"
    })
    assert r.status_code == 200
    
    # Check Reassessment triggers in timeline
    r = client.get(f"/api/national/incidents/{inc.incident_id}")
    inc_data = r.json()["record"]
    events = [e["event_type"] for e in inc_data["timeline"]]
    
    assert "FIELD_RISK_INCREASED" in events
    assert "FIELD_ACCESS_DETERIORATED" in events
    assert "ROUTE_REASSESSMENT_RECOMMENDED" in events
    assert "REASSESSMENT_RECOMMENDED" in events
    print("PASS  Reassessment engine")
    print("PASS  Incident timeline integration")
    print("PASS  Field reports")

    print("\n============================================================")
    print("  ALL 6G TESTS PASSED")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
