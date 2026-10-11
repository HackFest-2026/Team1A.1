import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_naval_status_and_vessels():
    # Test naval status
    res = client.get("/api/naval/status")
    assert res.status_code == 200
    data = res.json()
    assert "INDIAN_NAVY" in data["service"]
    assert "active_contacts" in data

    # Test list vessels
    res = client.get("/api/naval/vessels")
    assert res.status_code == 200
    vessels = res.json()["vessels"]
    assert len(vessels) >= 3

    # Test ingest vessel
    ingest_payload = {
        "mmsi": "999888777",
        "name": "TEST CORVETTE",
        "vessel_type": "CORVETTE",
        "latitude": 15.40,
        "longitude": 73.70,
        "sog": 24.5,
        "cog": 180.0,
        "ais_status": "matched",
        "is_dark_vessel": False,
        "notes": "Test vessel track"
    }
    post_res = client.post("/api/naval/vessels", json=ingest_payload)
    assert post_res.status_code == 200
    assert post_res.json()["contact"]["mmsi"] == "999888777"
