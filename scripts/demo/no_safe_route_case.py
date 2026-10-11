"""Demo step: show the honest "no safe route" outcome in the UI.

Registers a second monitored mission (Hubballi city centre -> a dead-end street whose
only access road is 224 m long) and reports a SIMULATED CRITICAL washout on that access
road, with a linked SIMULATED evidence record. The UI's Active Mission panel follows
the newest mission, so after running this:

    CHECK ROUTE                -> INVALIDATED (route crosses the CRITICAL zone)
    COMPUTE ALTERNATIVE ROUTE  -> "No safe alternative exists ..." (NO_SAFE_AVAILABLE_ROUTE)

Coordinates were derived from the tracked OSM graph (data/osm/hubballi_dharwad_drive.graphml)
with the same rule as backend/tests/test_mission_workflow.py::_dead_end. Writes only
through the public API; run it against a demo database (see docs/DEMO.md).
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AEGIS_API", "http://127.0.0.1:8000/api").rstrip("/")
ORIGIN = {"lat": 15.3647, "lon": 75.1240}          # Hubballi city centre
DEAD_END = {"lat": 15.3531358, "lon": 75.0931855}  # graph node with a single access road
ACCESS_ROAD_MIDPOINT = (15.35278125, 75.09416185)


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def require(ok, message):
    if not ok:
        sys.exit(f"no_safe_route_case: {message}")


def main():
    st, route = call("GET", f"/route?origin_lat={ORIGIN['lat']}&origin_lon={ORIGIN['lon']}"
                            f"&destination_lat={DEAD_END['lat']}&destination_lon={DEAD_END['lon']}")
    require(st == 200 and route.get("status") == "success", f"route planning failed: {route}")
    st, reg = call("POST", "/route-monitor/register", {
        "origin": ORIGIN, "destination": DEAD_END, "route_nodes": route["route_nodes"],
        "distance_m": route["distance_m"], "estimated_time_s": route["estimated_time_s"]})
    require(st == 200, f"register failed: {reg}")

    lat, lon = ACCESS_ROAD_MIDPOINT
    st, threat = call("POST", "/threats", {
        "title": "SIMULATED: access road washed out", "category": "Road Flooding", "severity": "CRITICAL",
        "confidence": "MEDIUM", "latitude": lat, "longitude": lon, "radius_m": 10,
        "source": "SIMULATED_REPORT",
        "description": "Demo fixture for the no-safe-route case (not a real observation)."})
    require(st == 201, f"threat creation failed: {threat}")
    st, ev = call("POST", "/evidence", {
        "source_type": "HUMAN_REPORT", "source_id": "SIM-FIELD-TEAM-4", "observation_type": "ROAD_FLOODING",
        "latitude": lat, "longitude": lon, "confidence": 0.7, "threat_id": threat["incident_id"],
        "description": "SIMULATED field-team report: only access road washed out.",
        "provenance": {"origin": "DEMO_SCRIPT", "source_system": "AEGIS-COP demo", "is_simulation": True,
                       "confidence_basis": "DECLARED_BY_SIMULATION_PROFILE"}})
    require(st == 201, f"evidence creation failed: {ev}")

    print(json.dumps({"mission_route_id": reg["route_id"], "distance_m": route["distance_m"],
                      "threat_id": threat["incident_id"], "evidence_id": ev["evidence_id"],
                      "next": "UI: CHECK ROUTE, then COMPUTE ALTERNATIVE ROUTE"}, indent=1))


if __name__ == "__main__":
    main()
