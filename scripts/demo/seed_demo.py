"""Seed deterministic, clearly labelled demo data into an EMPTY AEGIS-COP backend.

Usage (backend already running against a fresh DATABASE_PATH):
    python scripts/demo/seed_demo.py            # default API http://127.0.0.1:8000/api
    AEGIS_API=http://host:port/api python scripts/demo/seed_demo.py

Everything created here is demo data: threats use source CONTROLLED_DEMO (shown as
DEMO in the COP) and evidence carries provenance.is_simulation = true (shown as
SIMULATED). The script writes only through the public API and refuses to run if
the backend already has threats, so it cannot pollute a real database.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AEGIS_API", "http://127.0.0.1:8000/api").rstrip("/")
DEMO_PROVENANCE = {"origin": "DEMO_SEED", "source_system": "AEGIS-COP demo seed", "is_simulation": True}


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
        sys.exit(f"seed_demo: {message}")


def threat(title, severity, lat, lon, radius_m, category="Waterlogging"):
    st, t = call("POST", "/threats", {
        "title": title, "category": category, "severity": severity, "confidence": "MEDIUM",
        "latitude": lat, "longitude": lon, "radius_m": radius_m, "source": "CONTROLLED_DEMO",
        "description": "Demo fixture for the AEGIS-COP walkthrough (not a real observation)."})
    require(st == 201, f"threat creation failed: {t}")
    return t


def evidence(**fields):
    body = {"observation_type": "WATERLOGGING_OBSERVATION", "confidence": 0.8,
            "provenance": dict(DEMO_PROVENANCE), **fields}
    st, e = call("POST", "/evidence", body)
    require(st == 201, f"evidence creation failed: {e}")
    return e


def main():
    try:
        st, health = call("GET", "/health")
    except urllib.error.URLError as e:
        sys.exit(f"seed_demo: backend not reachable at {API} ({e.reason})")
    require(st == 200, f"backend unhealthy: {health}")

    st, existing = call("GET", "/threats")
    require(st == 200 and existing == [],
            f"refusing to seed: backend already has {len(existing)} threat(s); start it with a fresh DATABASE_PATH")

    gokul = threat("DEMO: Gokul Road underpass flooding", "CRITICAL", 15.3600, 75.1300, 150)
    threat("DEMO: Keshwapur drain overflow", "HIGH", 15.3700, 75.1150, 200, category="Drainage Overflow")
    threat("DEMO: Vidyanagar ponding", "MODERATE", 15.3760, 75.1300, 120)
    cleared = threat("DEMO: Cleared culvert (closed)", "HIGH", 15.3550, 75.1200, 100)
    call("POST", f"/threats/{cleared['incident_id']}/close?reason=demo-cleared")

    st, units = call("GET", "/national/field-units")
    require(st == 200 and units.get("records"), "no field units available")
    for unit, (lat, lon) in zip(units["records"][:2], [(15.3640, 75.1180), (15.3720, 75.1250)]):
        st, _ = call("POST", f"/national/field-units/{unit['field_unit_id']}/location",
                     {"latitude": lat, "longitude": lon, "accuracy_m": 10})
        require(st == 200, "field unit location update failed")

    evidence(source_type="DRONE", source_id="DEMO-DRONE-07", latitude=15.3605, longitude=75.1295,
             threat_id=gokul["incident_id"], description="Demo drone frame: water across underpass")
    evidence(source_type="SENSOR", source_id="DEMO-GAUGE-3", latitude=15.3720, longitude=75.1160,
             description="Demo water-level gauge reading")
    evidence(source_type="HUMAN_REPORT", description="Demo phone report without location")
    archived = evidence(source_type="DRONE", source_id="DEMO-DRONE-02", latitude=15.3660, longitude=75.1220,
                        description="Demo superseded frame")
    call("POST", f"/evidence/{archived['evidence_id']}/archive")

    st, cop = call("GET", "/cop")
    require(st == 200, "COP snapshot failed")
    print(json.dumps({"seeded": True, "summary": cop["summary"],
                      "weather_mode": cop["system"]["weather_mode"]}, indent=1))


if __name__ == "__main__":
    main()
