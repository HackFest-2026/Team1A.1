"""Demo step: report a CRITICAL road closure on the "Unkal - Vidyanagar" planner route.

Places a clearly labelled demo threat (source CONTROLLED_DEMO) at the midpoint of the
route the planner currently computes for that preset, so re-planning shows the
threat-avoidance detour. Writes only through the API.

    python scripts/demo/add_road_closure.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AEGIS_API", "http://127.0.0.1:8000/api").rstrip("/")
ORIGIN = (15.3750, 75.1300)        # planner preset "Unkal - Vidyanagar"
DESTINATION = (15.3850, 75.1350)


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def route():
    q = (f"/route?origin_lat={ORIGIN[0]}&origin_lon={ORIGIN[1]}"
         f"&destination_lat={DESTINATION[0]}&destination_lon={DESTINATION[1]}")
    st, r = call("GET", q)
    if st != 200 or r.get("status") != "success":
        sys.exit(f"add_road_closure: route not available: {r}")
    return r


def main():
    before = route()
    coords = before["route"]["coordinates"]
    lon, lat = coords[len(coords) // 2]
    st, threat = call("POST", "/threats", {
        "title": "DEMO: Road collapse (critical)", "category": "Road Obstruction", "severity": "CRITICAL",
        "confidence": "MEDIUM", "latitude": lat, "longitude": lon, "radius_m": 40,
        "source": "CONTROLLED_DEMO", "description": "Demo road closure for the threat-avoidance walkthrough."})
    if st != 201:
        sys.exit(f"add_road_closure: threat creation failed: {threat}")
    after = route()
    print(json.dumps({
        "threat_id": threat["incident_id"], "at": [round(lat, 5), round(lon, 5)],
        "before": {"nodes": len(before["route_nodes"]), "distance_m": before["distance_m"]},
        "after": {"nodes": len(after["route_nodes"]), "distance_m": after["distance_m"],
                  "rerouted": after["route_nodes"] != before["route_nodes"]},
    }, indent=1))


if __name__ == "__main__":
    main()
