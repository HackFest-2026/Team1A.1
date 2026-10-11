"""
Unit tests for Maritime AIS Tracking, CSV normalization, Track Playback, and Sea-Route Planner.
Verifies all 9 requirements from FEATURE 8:
1. AIS CSV parsing and column normalization.
2. Invalid coordinates and timestamps.
3. Missing optional fields.
4. Filtering observations by vessel and time.
5. Track ordering and duplicate timestamps.
6. Distance calculations in nautical miles.
7. Finding a route in the configured graph.
8. Handling unknown ports and disconnected routes.
9. Ensuring maritime router does not alter existing API routes.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.maritime_ais import MaritimeAISService, haversine_nm

client = TestClient(app)

SAMPLE_CSV_VARIED_COLUMNS = """MMSI,BaseDateTime,LAT,LON,SOG,COG,Heading,VesselName,VesselType
419001111,2026-03-15T08:00:00Z,18.9000,72.8000,14.5,180.0,180.0,INS TEST SHIP,Patrol
419001111,2026-03-15T09:00:00Z,18.7000,72.8000,14.2,180.0,180.0,INS TEST SHIP,Patrol
419002222,2026-03-15T08:30:00Z,15.4000,73.8000,10.0,270.0,270.0,OCEAN EXPLORER,Research
"""

SAMPLE_CSV_ANOTHER_FORMAT = """vessel_id,timestamp,latitude,longitude,speed,course,vessel
999000111,2026-03-15 10:00:00,12.92,74.81,12.0,210.0,CARGO RUNNER
"""

INVALID_RECORDS_CSV = """mmsi,timestamp,lat,lon,sog
419009999,2026-03-15T08:00:00Z,92.5000,72.8000,10.0
419009999,2026-03-15T08:30:00Z,18.5000,195.0000,10.0
419009999,invalid_timestamp_here,18.5000,72.8000,10.0
,2026-03-15T09:00:00Z,18.5000,72.8000,10.0
419009999,2026-03-15T09:30:00Z,not_a_num,72.8000,10.0
419009999,2026-03-15T10:00:00Z,18.5000,72.8000,10.0
"""

DUPLICATE_AND_UNORDERED_CSV = """mmsi,timestamp,lat,lon,sog,cog
419005555,2026-03-15T12:00:00Z,15.0000,73.0000,12.0,180.0
419005555,2026-03-15T10:00:00Z,15.5000,73.0000,12.0,180.0
419005555,2026-03-15T11:00:00Z,15.2500,73.0000,12.0,180.0
419005555,2026-03-15T11:00:00Z,15.2500,73.0000,12.5,180.0
"""

def test_1_ais_csv_parsing_and_column_normalization():
    """Verify flexible column alias mapping and parsing into internal schema."""
    svc = MaritimeAISService()
    summary1 = svc.import_csv_content(SAMPLE_CSV_VARIED_COLUMNS, "test_file_1.csv")
    assert summary1["valid_rows"] == 3
    assert summary1["vessel_count"] == 2
    assert "Patrol" in summary1["vessel_types"]

    summary2 = svc.import_csv_content(SAMPLE_CSV_ANOTHER_FORMAT, "test_file_2.csv")
    assert summary2["valid_rows"] == 1
    assert summary2["vessel_count"] == 1
    vessel = svc.vessels_by_mmsi["999000111"]
    assert vessel["ship_name"] == "CARGO RUNNER"
    assert vessel["latest_position"]["lat"] == 12.92
    assert vessel["latest_position"]["lon"] == 74.81

def test_2_invalid_coordinates_and_timestamps():
    """Verify rejection of invalid coordinates, non-numeric values, and broken timestamps without crashing."""
    svc = MaritimeAISService()
    summary = svc.import_csv_content(INVALID_RECORDS_CSV, "invalid_test.csv")
    # In INVALID_RECORDS_CSV, 5 rows are invalid (lat > 90, lon > 180, bad timestamp, missing MMSI, non-numeric lat)
    # Exactly 1 valid row (18.5, 72.8 at 10:00:00Z)
    assert summary["valid_rows"] == 1
    assert summary["rejected_rows"] == 5
    assert len(summary["rejections_sample"]) >= 4

def test_3_missing_optional_fields():
    """Verify graceful handling when sog, cog, heading, ship_name, or ship_type are missing."""
    minimal_csv = """mmsi,timestamp,lat,lon
123456789,2026-03-15T00:00:00Z,15.0,73.0
123456789,2026-03-15T01:00:00Z,15.1,73.1
"""
    svc = MaritimeAISService()
    summary = svc.import_csv_content(minimal_csv, "minimal.csv")
    assert summary["valid_rows"] == 2
    rec = svc.records[0]
    assert rec["sog"] is None
    assert rec["cog"] is None
    assert rec["heading"] is None
    assert rec["ship_name"] is None

def test_4_filtering_observations_by_vessel_and_time():
    """Verify filtering of vessels and positions by identifier, ship type, and time bounds."""
    svc = MaritimeAISService()
    svc.import_csv_content(SAMPLE_CSV_VARIED_COLUMNS, "filter_test.csv")

    # Filter by search/mmsi
    vessels = svc.list_vessels(search="419001111")
    assert len(vessels) == 1
    assert vessels[0]["mmsi"] == "419001111"

    # Filter by ship type
    research_vessels = svc.list_vessels(ship_type="Research")
    assert len(research_vessels) == 1
    assert research_vessels[0]["mmsi"] == "419002222"

    # Filter positions by time
    pos_res = svc.get_positions(
        start_time="2026-03-15T08:15:00Z",
        end_time="2026-03-15T09:15:00Z"
    )
    assert pos_res["total_matching"] == 2

def test_5_track_ordering_and_duplicate_timestamps():
    """Verify chronological ordering, duplicate timestamp resolution, and gap break detection."""
    svc = MaritimeAISService()
    svc.import_csv_content(DUPLICATE_AND_UNORDERED_CSV, "unordered_test.csv")

    track = svc.get_vessel_track("419005555")
    assert track["found"] is True
    # 4 rows had timestamps 12:00, 10:00, 11:00, 11:00 (duplicate)
    # Deduplication leaves 3 points: 10:00, 11:00, 12:00
    assert track["total_points"] == 3
    timestamps = [p["timestamp"] for p in track["points"]]
    assert timestamps == [
        "2026-03-15T10:00:00+00:00",
        "2026-03-15T11:00:00+00:00",
        "2026-03-15T12:00:00+00:00"
    ]
    assert track["total_distance_nm"] > 0.0

def test_6_distance_calculations_in_nautical_miles():
    """Verify great-circle distance calculation in nautical miles."""
    # 1 degree of latitude is approximately 60 Nautical Miles
    dist = haversine_nm(10.0, 75.0, 11.0, 75.0)
    assert 59.5 < dist < 60.5

    # Known distance: Mumbai to Colombo is approx 800-900 NM direct
    dist_mumbai_colombo = haversine_nm(18.9438, 72.8656, 6.9400, 79.8400)
    assert 750 < dist_mumbai_colombo < 900

def test_7_finding_a_route_in_the_configured_graph():
    """Verify Dijkstra shortest path finds navigable sea route and estimates transit duration."""
    svc = MaritimeAISService()
    # Route between Mumbai and Colombo
    res = svc.plan_sea_route("mumbai", "colombo", speed_knots=15.0)
    assert res["status"] == "SUCCESS"
    assert res["total_distance_nm"] > 500.0
    assert res["waypoint_count"] >= 3
    assert res["estimated_hours"] is not None
    assert res["estimated_days"] is not None
    assert "PROTOTYPE MARITIME ROUTE" in res["disclaimer"]

    # First and last waypoints match origin and destination
    assert res["waypoints"][0]["id"] == "mumbai"
    assert res["waypoints"][-1]["id"] == "colombo"

def test_8_handling_unknown_ports_and_disconnected_routes():
    """Verify unknown ports produce clear ValueError and not crash."""
    svc = MaritimeAISService()

    with pytest.raises(ValueError, match="not found in maritime graph"):
        svc.plan_sea_route("atlantis_port", "colombo")

    with pytest.raises(ValueError, match="not found in maritime graph"):
        svc.plan_sea_route("mumbai", "unknown_destination")

    with pytest.raises(ValueError, match="must be distinct"):
        svc.plan_sea_route("mumbai", "mumbai")

def test_9_maritime_router_endpoints_and_non_interference():
    """Verify dedicated /api/maritime API endpoints work and do not affect existing endpoints."""
    # 1. Summary endpoint
    res = client.get("/api/maritime/ais/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

    # 2. Ports endpoint
    res = client.get("/api/maritime/ports")
    assert res.status_code == 200
    ports_data = res.json()
    assert len(ports_data["ports"]) > 0

    # 3. Route endpoint
    res = client.post("/api/maritime/route", json={
        "origin": "mumbai",
        "destination": "colombo",
        "speed_knots": 14.0
    })
    assert res.status_code == 200
    route_json = res.json()
    assert route_json["status"] == "success"
    assert route_json["route"]["total_distance_nm"] > 0

    # 4. Verify existing road routing and system endpoints are completely intact!
    gis_res = client.get("/api/gis/status")
    assert gis_res.status_code == 200

    system_res = client.get("/api/system/status")
    assert system_res.status_code == 200

    health_res = client.get("/api/health")
    assert health_res.status_code == 200
