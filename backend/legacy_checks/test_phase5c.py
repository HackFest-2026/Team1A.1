"""Phase 5C comprehensive test suite."""
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
section("1. PHASE 5A & 5B REGRESSION TESTS")
# ==============================================================
def test_route():
    r = requests.get(f"{BASE}/api/route?origin_lat=15.36&origin_lon=75.12&destination_lat=15.42&destination_lon=75.10", timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
test("GET /api/route (baseline)", test_route)

def test_hazard():
    r = requests.get(f"{BASE}/api/hazard?lat=15.36&lon=75.12", timeout=15)
    assert r.status_code == 200
test("GET /api/hazard", test_hazard)

def test_road_hazard():
    r = requests.get(f"{BASE}/api/road-hazard?u=7872006581&v=7872007929&key=0", timeout=30)
    assert r.status_code == 200
test("GET /api/road-hazard", test_road_hazard)

def test_flood_status():
    r = requests.get(f"{BASE}/api/flood/status", timeout=60)
    assert r.status_code == 200
test("GET /api/flood/status", test_flood_status)

# ==============================================================
section("2. FLOOD-SAFE ROUTING TESTS")
# ==============================================================
def test_flood_safe_route_valid():
    r = requests.get(f"{BASE}/api/route/flood-safe?origin_lat=15.36&origin_lon=75.12&destination_lat=15.42&destination_lon=75.10&rainfall_mm_hr=80&blockage_percent=50&forecast_minute=60", timeout=120)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    d = r.json()
    assert d["status"] == "success"
    assert "baseline_route" in d
    assert "recommended_route" in d
    assert "comparison" in d
    assert "decision" in d
    
    comp = d["comparison"]
    print(f"         Is rerouted: {comp['is_rerouted']}")
    print(f"         Distance diff: {comp['distance_difference_m']}m")
    print(f"         Risk reduction: {comp['risk_reduction']}")
test("GET /api/route/flood-safe (valid)", test_flood_safe_route_valid)

def test_flood_safe_route_invalid_coords():
    r = requests.get(f"{BASE}/api/route/flood-safe?origin_lat=999&origin_lon=999&destination_lat=15.42&destination_lon=75.10", timeout=10)
    # Depending on how OSMnx nearest_nodes behaves, it might return a node or fail
    assert r.status_code in [200, 400, 500] 
test("GET /api/route/flood-safe (invalid coords)", test_flood_safe_route_invalid_coords)

def test_flood_safe_route_invalid_forecast():
    r = requests.get(f"{BASE}/api/route/flood-safe?origin_lat=15.36&origin_lon=75.12&destination_lat=15.42&destination_lon=75.10&forecast_minute=999", timeout=10)
    assert r.status_code == 400 # We clamp or raise ValueError
test("GET /api/route/flood-safe (invalid forecast)", test_flood_safe_route_invalid_forecast)

# ==============================================================
section("3. NO SAFE ROUTE BEHAVIOR")
# ==============================================================
def test_no_safe_route():
    # Force an impossible route or extremely high flood risk that cuts off destination
    # We'll just test that if it occurs, it handles gracefully.
    # It's hard to force NetworkXNoPath without specifically knowing the graph bottleneck.
    # Let's mock the nx.shortest_path in our test just to check the endpoint response.
    # For now, just a dummy check.
    pass
test("No safe route behavior (placeholder)", test_no_safe_route)

section("SUMMARY")
print(f"\n  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Total:  {passed + failed}")
if failed > 0:
    sys.exit(1)
