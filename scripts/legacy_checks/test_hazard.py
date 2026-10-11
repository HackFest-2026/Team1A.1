import sys
import os
import requests

# We will run against the live local backend
BASE_URL = "http://127.0.0.1:8000"

def test():
    print("--- Phase 4 Terrain + Hazard Intelligence Test ---")
    
    # 1. Health
    print("\n1. Testing Health Endpoint...")
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"Status Code: {r.status_code}")
    assert r.status_code == 200
    
    # 2. GIS
    print("\n2. Testing GIS Status...")
    r = requests.get(f"{BASE_URL}/api/gis/status")
    print(f"GIS: {r.json().get('status')}")
    assert r.json().get('graph_available') is True

    # 3. Routing
    print("\n3. Testing Existing Routing...")
    route_url = f"{BASE_URL}/api/route?origin_lat=15.3647&origin_lon=75.1240&destination_lat=15.4589&destination_lon=75.0078"
    r = requests.get(route_url)
    print(f"Routing Status Code: {r.status_code}")
    assert r.status_code == 200
    assert r.json().get("status") == "success"

    # 4. Weather
    print("\n4. Testing Weather...")
    r = requests.get(f"{BASE_URL}/api/weather")
    print(f"Weather Status Code: {r.status_code}")
    assert r.status_code == 200
    
    # 5. Hazard (Valid Terrain)
    print("\n5. Testing Hazard Intelligence (Inside Hubballi-Dharwad DEM bounds)...")
    r = requests.get(f"{BASE_URL}/api/hazard?lat=15.41&lon=75.06")
    print(f"Hazard Status Code: {r.status_code}")
    assert r.status_code == 200
    data = r.json()
    print(f"Risk Level: {data['risk']['level']}")
    print(f"Risk Score: {data['risk']['score']}")
    print(f"Confidence: {data['confidence']}")
    print(f"Reasons: {data['reasons']}")
    print(f"Provenance Terrain: {data['source']['terrain']}")
    print(f"Sampled Elevation: {data['indicators'].get('elevation_m')}m")
    
    assert "score" in data["risk"]
    assert "level" in data["risk"]
    assert data["source"]["terrain"] != "UNAVAILABLE"
    assert data["indicators"]["elevation_m"] is not None

    # 6. Hazard (Outside Terrain)
    print("\n6. Testing Hazard Intelligence (Outside DEM bounds e.g. London)...")
    r = requests.get(f"{BASE_URL}/api/hazard?lat=51.5&lon=-0.1")
    print(f"Invalid Params Status Code: {r.status_code}")
    assert r.status_code == 200
    out_data = r.json()
    print(f"Terrain Status (Expected UNAVAILABLE): {out_data['source']['terrain']}")
    assert out_data["source"]["terrain"] == "UNAVAILABLE"
    assert out_data["confidence"] == "LIMITED" # Only weather fallback

    # 7. Invalid Coordinates
    print("\n7. Testing Missing Coordinates...")
    r = requests.get(f"{BASE_URL}/api/hazard")
    print(f"Missing Params Status Code: {r.status_code}")
    assert r.status_code == 422 # FastAPI validation error

    print("\n--- All tests passed successfully! ---")

if __name__ == "__main__":
    test()
