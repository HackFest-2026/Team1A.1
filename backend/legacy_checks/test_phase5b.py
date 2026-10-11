"""Phase 5B comprehensive test suite."""
import requests
import sys

BASE = "http://127.0.0.1:8000"
passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        failed += 1

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ==============================================================
section("1. REGRESSION TESTS")
# ==============================================================
def test_route():
    r = requests.get(f"{BASE}/api/route?origin_lat=15.36&origin_lon=75.12&destination_lat=15.42&destination_lon=75.10", timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    d = r.json()
    assert d["status"] == "success"
test("GET /api/route", test_route)

def test_hazard():
    r = requests.get(f"{BASE}/api/hazard?lat=15.36&lon=75.12", timeout=15)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
test("GET /api/hazard", test_hazard)

def test_road_hazard():
    r = requests.get(f"{BASE}/api/road-hazard?u=7872006581&v=7872007929&key=0", timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
test("GET /api/road-hazard", test_road_hazard)

# ==============================================================
section("2. API FLOOD STATUS")
# ==============================================================
def test_flood_status():
    r = requests.get(f"{BASE}/api/flood/status", timeout=60)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    d = r.json()
    assert "status" in d
    assert "scenario" in d
    assert "forecast" in d
    assert "summary" in d["forecast"][0]
    print(f"         Summary: {d['forecast'][0]['summary']}")
test("GET /api/flood/status", test_flood_status)

# ==============================================================
section("3. WHAT-IF SIMULATION (Rainfall=80, Blockage=50)")
# ==============================================================
def test_flood_simulate():
    req = {
        "rainfall_mm_hr": 80,
        "blockage_percent": 50,
        "forecast_minutes": 180
    }
    r = requests.post(f"{BASE}/api/flood/simulate", json=req, timeout=120)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    d = r.json()
    assert d["status"] == "success"
    
    # 3.1 Rainfall conversion & Runoff
    assert d["scenario"]["rainfall_mm_hr"] == 80
    assert d["scenario"]["runoff_coefficient"] > 0
    assert d["scenario"]["blockage_percent"] == 50
    
    # 3.9 Forecast generation (0 to 180 min by 30 min = 7 steps)
    assert len(d["forecast"]) == 7
    
    # Check each step
    for step in d["forecast"]:
        # 3.2 Runoff Calculation (roughly 80 * coeff)
        assert step["runoff_mm_hr"] > 0
        
        # Check roads in this step
        for road_id, road_data in step["roads"].items():
            # 3.7 Flood score bounds
            assert 0 <= road_data["flood_score"] <= 100
            # 3.8 Depth never negative
            assert road_data["estimated_depth_cm"] >= 0
            
    print(f"         Scenario: {d['scenario']}")
    print(f"         Timesteps generated: {len(d['forecast'])}")
    print(f"         Total roads geometries: {len(d['road_geometries'])}")
    print(f"         Max depth at t=180: {d['forecast'][-1]['summary']['max_depth_cm']}cm")
test("POST /api/flood/simulate (80mm/hr, 50%)", test_flood_simulate)

# ==============================================================
section("4. INVALID SIMULATION PARAMETERS")
# ==============================================================
def test_flood_simulate_invalid():
    req = {
        "rainfall_mm_hr": 999, # invalid
        "blockage_percent": 0,
        "forecast_minutes": 180
    }
    r = requests.post(f"{BASE}/api/flood/simulate", json=req, timeout=10)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
test("POST /api/flood/simulate (invalid param)", test_flood_simulate_invalid)

# ==============================================================
section("5. INTERNAL LOGIC TESTS via service imports")
# ==============================================================
def test_internal_logic():
    import os, sys
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # backend/
    from app.services.flood.drainage_service import drainage_service
    from app.services.flood.runoff_service import runoff_service
    from app.services.flood.inundation_service import inundation_service
    
    # 5.1 Runoff calc
    r = runoff_service.calculate_runoff(100.0)
    assert r == 100.0 * runoff_service.DEFAULT_URBAN_COEFFICIENT
    
    # 5.2 Blockage & Effective capacity / Overflow / Utilization
    drain_state = drainage_service.simulate(runoff_mm_hr=50, blockage_percent=50)
    # Check one node
    if drain_state["nodes"]:
        n_id = list(drain_state["nodes"].keys())[0]
        node = drain_state["nodes"][n_id]
        
        # effective capacity check (needs base capacity but we don't have it in output)
        # we can check utilization
        expected_util = node["total_inflow_lps"] / max(node["effective_capacity_lps"], 1.0)
        assert abs(node["utilization"] - expected_util) < 1e-5
        
        # overflow check
        if node["total_inflow_lps"] > node["effective_capacity_lps"]:
            assert node["overflow_lps"] > 0
        else:
            assert node["overflow_lps"] == 0
test("Internal logic: runoff, capacity, blockage, overflow, util", test_internal_logic)

section("SUMMARY")
print(f"\n  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Total:  {passed + failed}")
if failed > 0:
    sys.exit(1)
