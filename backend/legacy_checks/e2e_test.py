import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

# Sample points in Hubballi
ORIGIN_LAT = 15.36
ORIGIN_LON = 75.12
DEST_LAT = 15.42
DEST_LON = 75.10

def fetch_route(rainfall, blockage, minute):
    url = f"{BASE_URL}/api/route/flood-safe?origin_lat={ORIGIN_LAT}&origin_lon={ORIGIN_LON}&destination_lat={DEST_LAT}&destination_lon={DEST_LON}&rainfall_mm_hr={rainfall}&blockage_percent={blockage}&forecast_minute={minute}"
    r = requests.get(url)
    if r.status_code != 200:
        print("ERROR:", r.text)
        return None
    return r.json()

print("=== TEST A: NORMAL (20mm, 0%, NOW) ===")
res_a = fetch_route(20, 0, 0)
if res_a and res_a["status"] == "success":
    print("Baseline:", res_a["baseline_route"])
    print("Recommended:", res_a["recommended_route"])
    print("Rerouted:", res_a["comparison"]["is_rerouted"])
    print("Decision:", res_a["decision"]["reason"])
else:
    print(res_a)

print("\n=== TEST B: HEAVY RAIN (80mm, 50%, +1h) ===")
res_b = fetch_route(80, 50, 60)
if res_b and res_b["status"] == "success":
    print("Baseline:", res_b["baseline_route"])
    print("Recommended:", res_b["recommended_route"])
    print("Rerouted:", res_b["comparison"]["is_rerouted"])
    print("Decision:", res_b["decision"]["reason"])
else:
    print(res_b)

print("\n=== TEST C: EXTREME (100mm, 75%, +3h) ===")
res_c = fetch_route(100, 75, 180)
if res_c and res_c.get("status") == "success":
    print("Baseline:", res_c["baseline_route"])
    print("Recommended:", res_c["recommended_route"])
    print("Rerouted:", res_c["comparison"]["is_rerouted"])
    print("Decision:", res_c["decision"]["reason"])
else:
    print("Response:", res_c)
