"""Demo step: an external client posts a report through the public API (no UI click).

Shows the integration path and the automatic route re-check: the script records a
TEST evidence record and a linked CRITICAL threat on the newest monitored mission
route, using only the public endpoints a real authorised source would use
(POST /api/evidence, POST /api/threats, POST /api/evidence/{id}/associate-threat).
The backend then re-checks every monitored route by itself; nobody presses CHECK ROUTE.

Everything it creates is labelled as a simulation (provenance.is_simulation = true,
source SIMULATED_REPORT, title prefixed "SIMULATED:"). It is a test client, not a
sensor. Run it against a demo database (see docs/DEMO.md).

    .venv/bin/python scripts/demo/post_external_report.py            # point 1/3 along the route
    .venv/bin/python scripts/demo/post_external_report.py --at 0.6   # another point
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AEGIS_API", "http://127.0.0.1:8000/api").rstrip("/")


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
        sys.exit(f"post_external_report: {message}")


def main():
    parser = argparse.ArgumentParser(description="Post a SIMULATED external report on the newest mission route.")
    parser.add_argument("--at", type=float, default=1 / 3, help="fraction along the route geometry (0-1)")
    args = parser.parse_args()
    require(0.0 <= args.at <= 1.0, "--at must be between 0 and 1")

    st, cop = call("GET", "/cop")
    require(st == 200, f"COP unavailable: {cop}")
    routes = [r for r in cop.get("monitored_routes", []) if (r.get("geometry") or {}).get("coordinates")]
    require(routes, "no monitored mission route with geometry; press START MISSION first")
    route = sorted(routes, key=lambda r: r.get("created_at") or "")[-1]
    coords = route["geometry"]["coordinates"]
    lon, lat = coords[min(len(coords) - 1, int(len(coords) * args.at))]

    st, ev = call("POST", "/evidence", {
        "source_type": "HUMAN_REPORT", "source_id": "EXT-TEST-CLIENT", "observation_type": "ROAD_BLOCKAGE",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "latitude": lat, "longitude": lon, "confidence": 0.7,
        "description": "SIMULATED external report: road blocked (posted by a test client through the API).",
        "provenance": {"origin": "EXT-TEST-CLIENT", "source_system": "AEGIS-COP demo test client",
                       "is_simulation": True, "confidence_basis": "DECLARED_BY_TEST_CLIENT"}})
    require(st == 201, f"evidence creation failed: {ev}")

    st, threat = call("POST", "/threats", {
        "title": "SIMULATED: external report — road blocked", "category": "Road Obstruction",
        "severity": "CRITICAL", "confidence": "MEDIUM", "latitude": lat, "longitude": lon, "radius_m": 40,
        "source": "SIMULATED_REPORT", "evidence_references": [ev["evidence_id"]],
        "description": f"SIMULATED external report via the public API. Derived from evidence {ev['evidence_id']}."})
    require(st == 201, f"threat creation failed: {threat}")

    st, linked = call("POST", f"/evidence/{ev['evidence_id']}/associate-threat", {"threat_id": threat["incident_id"]})
    require(st == 200, f"evidence association failed: {linked}")

    st, detail = call("GET", f"/route-monitor/{route['id']}")
    require(st == 200, f"route lookup failed: {detail}")
    last = (detail.get("transitions") or [{}])[-1]
    print(json.dumps({
        "mission_route_id": route["id"],
        "evidence_id": ev["evidence_id"],
        "threat_id": threat["incident_id"],
        "route_status_now": detail.get("monitor_status"),
        "last_transition": {k: last.get(k) for k in ("previous_status", "new_status", "trigger", "reason")},
    }, indent=1))


if __name__ == "__main__":
    main()
