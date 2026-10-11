"""Missing or stale weather is UNKNOWN: never zero rain, never maximum hazard.

Live weather is replaced by a fake Open-Meteo response (no network calls).
"""
import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import weather_service as weather_module
from app.services.hazard_scoring import combine
from app.services.road_hazard_service import road_hazard_service
from app.services.routing_service import routing_service
from app.services.scenario_service import scenario_service
from app.services.weather_adapter import weather_adapter
from app.services.weather_service import weather_service

client = TestClient(app)
IST_OFFSET_S = 19800


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _open_meteo(precip, minutes_ago=5, include_time=True):
    observed = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    local = (observed + datetime.timedelta(seconds=IST_OFFSET_S)).replace(tzinfo=None)
    current = {"precipitation": precip, "temperature_2m": 24.0, "wind_speed_10m": 6.0, "weather_code": 61}
    if include_time:
        current["time"] = local.strftime("%Y-%m-%dT%H:%M")
    return {"utc_offset_seconds": IST_OFFSET_S, "current": current}


@pytest.fixture
def live_weather(monkeypatch):
    """Install a fake provider response: live_weather(precip, minutes_ago=..., include_time=...)."""
    def install(precip, **kwargs):
        payload = _open_meteo(precip, **kwargs)
        monkeypatch.setattr(weather_module.requests, "get", lambda *a, **k: _FakeResponse(payload))
        weather_service.clear_cache()
    return install


@pytest.fixture(autouse=True)
def _reset_weather():
    scenario_service.set_active(False)
    weather_service.clear_cache()
    yield
    scenario_service.set_active(False)
    scenario_service.update_config({"precipitation_mm": 50.0})
    weather_service.clear_cache()


# --- Weather assessment --------------------------------------------------------

def test_unreachable_provider_is_unavailable_not_zero_rain():
    a = weather_adapter.assess_weather()  # network is blocked in tests
    assert a["state"] == "UNAVAILABLE"
    assert a["precipitation_mm"] is None and a["weather_score"] is None


def test_fresh_observation_is_available(live_weather):
    live_weather(5.0, minutes_ago=10)
    a = weather_adapter.assess_weather()
    assert a["state"] == "AVAILABLE"
    assert a["precipitation_mm"] == 5.0
    assert a["weather_score"] == pytest.approx(25.0)
    assert 9 <= a["age_minutes"] <= 11


def test_old_observation_is_stale(live_weather):
    live_weather(5.0, minutes_ago=300)
    a = weather_adapter.assess_weather()
    assert a["state"] == "STALE"
    assert a["weather_score"] is None
    assert a["age_minutes"] > 290


def test_missing_observation_time_is_stale(live_weather):
    live_weather(5.0, include_time=False)
    assert weather_adapter.assess_weather()["state"] == "STALE"


def test_null_precipitation_is_unknown_not_zero(live_weather):
    live_weather(None)
    a = weather_adapter.assess_weather()
    assert a["state"] == "UNAVAILABLE"
    assert a["precipitation_mm"] is None


def test_controlled_scenario_is_available_and_flagged():
    scenario_service.update_config({"precipitation_mm": 10.0})
    scenario_service.set_active(True)
    a = weather_adapter.assess_weather()
    assert a["state"] == "AVAILABLE" and a["controlled_scenario"] is True


# --- Score combination ---------------------------------------------------------

def test_combine_keeps_component_weights_when_weather_unknown():
    r = combine(None, 80.0, ["WEATHER_UNAVAILABLE"])
    assert r["score"] == pytest.approx(32.0)        # 0.4 x 80, not 80
    assert r["score_upper_bound"] == pytest.approx(92.0)
    assert r["completeness"] == 0.4
    assert r["score_basis"] == "PARTIAL" and r["confidence"] == "LIMITED"
    assert r["level"] == "LOW" and r["level_range"] == ["LOW", "CRITICAL"]


def test_combine_keeps_component_weights_when_terrain_unknown():
    r = combine(100.0, None, ["TERRAIN_OUTSIDE_DEM_COVERAGE"])
    assert r["score"] == pytest.approx(60.0) and r["completeness"] == 0.6


def test_combine_with_nothing_known_is_unknown():
    r = combine(None, None)
    assert r["score"] is None and r["level"] == "UNKNOWN" and r["confidence"] == "UNAVAILABLE"


def test_combine_complete():
    r = combine(25.0, 50.0)
    assert r["score"] == pytest.approx(35.0) and r["score_basis"] == "COMPLETE" and r["confidence"] == "MEDIUM"


# --- Segment, point and route consumers ----------------------------------------

def _edge_near_hubballi():
    node, _ = routing_service.snap(15.3647, 75.1240)
    v, k = next((v, k) for _, v, k in routing_service.G.out_edges(node, keys=True))
    return node, v, k


@pytest.mark.requires_graph
@pytest.mark.requires_dem
@pytest.mark.parametrize("case,expected_gap", [("unavailable", "WEATHER_UNAVAILABLE"), ("stale", "WEATHER_STALE")])
def test_segment_score_with_unknown_weather(live_weather, case, expected_gap):
    if case == "stale":
        live_weather(30.0, minutes_ago=600)  # heavy but stale rain must not count
    u, v, k = _edge_near_hubballi()
    seg = road_hazard_service.assess_road_segment(u, v, k)
    terrain = seg["terrain"]
    expected = 0.4 * (0.7 * terrain["max_susceptibility"] + 0.3 * terrain["mean_susceptibility"])
    risk = seg["risk"]
    assert risk["score"] == pytest.approx(expected, abs=0.05)
    assert risk["score_basis"] == "PARTIAL" and risk["completeness"] == 0.4
    assert risk["score_upper_bound"] == pytest.approx(risk["score"] + 60.0, abs=0.05)
    assert expected_gap in risk["data_gaps"]
    assert seg["confidence"] == "LIMITED"
    assert seg["weather"]["state"] == case.upper()


@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_segment_score_with_fresh_weather(live_weather):
    live_weather(5.0)
    u, v, k = _edge_near_hubballi()
    seg = road_hazard_service.assess_road_segment(u, v, k)
    t = seg["terrain"]
    expected = 0.6 * 25.0 + 0.4 * (0.7 * t["max_susceptibility"] + 0.3 * t["mean_susceptibility"])
    assert seg["risk"]["score"] == pytest.approx(expected, abs=0.05)
    assert seg["risk"]["score_basis"] == "COMPLETE" and seg["confidence"] == "MEDIUM"


@pytest.mark.requires_dem
def test_point_hazard_does_not_reweight_terrain():
    body = client.get("/api/hazard?lat=15.3647&lon=75.1240").json()
    susc = body["indicators"]["terrain_susceptibility_score"]
    assert body["risk"]["score"] == pytest.approx(0.4 * susc, abs=0.01)
    assert body["weather"]["state"] == "UNAVAILABLE"
    assert body["confidence"] == "LIMITED"


def test_point_hazard_with_nothing_known_is_unknown():
    body = client.get("/api/hazard?lat=28.6139&lon=77.2090").json()  # outside DEM, weather offline
    assert body["risk"]["level"] == "UNKNOWN" and body["risk"]["score"] is None


@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_hazard_route_with_unknown_weather_is_not_inflated():
    res = client.get("/api/route?origin_lat=15.3647&origin_lon=75.1240"
                     "&destination_lat=15.3700&destination_lon=75.1300&hazard_aware=true").json()
    assert res["status"] == "success"
    hs = res["hazard_summary"]
    assert hs["weather"]["state"] == "UNAVAILABLE"
    assert hs["score_basis"] == "PARTIAL" and hs["confidence"] == "LIMITED"
    assert hs["highest_segment_score"] <= 40.0      # terrain at its 40% weight
    assert hs["critical_segments"] == 0
    assert hs["data_completeness"]["segments_complete"] == 0
    assert "WEATHER_UNAVAILABLE" in hs["data_completeness"]["data_gaps"]


def _register(route):
    return client.post("/api/route-monitor/register", json={
        "origin": route["origin"], "destination": route["destination"],
        "route_nodes": route["route_nodes"], "distance_m": route["distance_m"],
        "estimated_time_s": route["estimated_time_s"]}).json()


@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_monitor_does_not_invalidate_on_unknown_weather_or_clear_on_it():
    route = client.get("/api/route?origin_lat=15.3647&origin_lon=75.1240"
                       "&destination_lat=15.3700&destination_lon=75.1300").json()
    reg = _register(route)
    assert reg["monitor_status"] != "INVALIDATED"   # used to happen offline (finding F1)

    # Heavy (controlled) rain makes it worse ...
    scenario_service.update_config({"precipitation_mm": 40.0})
    scenario_service.set_active(True)
    wet = client.post(f"/api/route-monitor/{reg['route_id']}/check").json()
    assert wet["current_status"] in ("AT_RISK", "INVALIDATED")

    # ... and losing weather afterwards must not be read as "conditions improved".
    scenario_service.set_active(False)
    dry_unknown = client.post(f"/api/route-monitor/{reg['route_id']}/check").json()
    assert dry_unknown["current_status"] == wet["current_status"]
    assert dry_unknown["status_retained_incomplete_data"] is True
    assert dry_unknown["weather_state"] == "UNAVAILABLE"
    assert dry_unknown["confidence"] == "LIMITED"

    # A candidate assessed on partial data is compared on its upper bound.
    rec = client.post(f"/api/route-monitor/{reg['route_id']}/replacement/recommend").json()
    if wet["current_status"] == "INVALIDATED":
        cand = rec["candidate_route"]
        assert cand["score_basis"] == "PARTIAL"
        assert rec["data_completeness"]["candidate_confidence"] == "LIMITED"
        identical = cand["route_nodes"] == route["route_nodes"]
        if rec["replacement_status"] == "RECOMMENDATION_READY":
            assert cand["hazard_score_upper_bound"] < rec["current_route"]["hazard_score"]
        elif rec["replacement_status"] == "NO_BETTER_ROUTE" and not identical:
            assert "incomplete data" in rec["decision"]["reason"]


def test_flood_status_without_weather_runs_no_forecast():
    body = client.get("/api/flood/status").json()
    assert body["status"] == "weather_unknown"


def test_flood_status_below_model_range_is_not_raised_to_minimum(live_weather):
    live_weather(2.0)
    body = client.get("/api/flood/status").json()
    assert body["status"] == "below_model_range"
    assert body["weather"]["precipitation_mm"] == 2.0


def test_live_rainfall_unknown_is_none_not_zero():
    from app.services.flood.rainfall_service import rainfall_service
    r = rainfall_service.get_live_rainfall()
    assert r["base_intensity_mm_hr"] is None and r["mode"] == "WEATHER_UNAVAILABLE"


def test_cop_reports_weather_state():
    assert client.get("/api/cop").json()["system"]["weather_mode"] == "UNAVAILABLE"
    scenario_service.set_active(True)
    assert client.get("/api/cop").json()["system"]["weather_mode"] == "CONTROLLED_SCENARIO"


@pytest.mark.parametrize("upper_bound,expected", [(80.0, "NO_BETTER_ROUTE"), (70.0, "RECOMMENDATION_READY")])
def test_replacement_compares_partial_candidate_on_upper_bound(monkeypatch, upper_bound, expected):
    from app.repositories.monitored_route_repository import monitored_route_repository
    from app.services.route_replacement_service import route_replacement_service

    route_id = f"hazard-invalidated-{int(upper_bound)}"
    monitored_route_repository.save({
        "route_id": route_id, "origin": {"lat": 15.36, "lon": 75.12}, "destination": {"lat": 15.37, "lon": 75.13},
        "route_nodes": [1, 2, 3], "distance_m": 1000.0, "estimated_time_s": 100.0,
        "created_at": "2026-10-09T00:00:00", "last_checked_at": "2026-10-09T00:00:00",
        "initial_hazard_summary": {}, "monitor_status": "INVALIDATED",
        "current_hazard_summary": {"overall_score": 75.0, "critical_segments": 1, "score_basis": "COMPLETE"},
        "transitions": [{"previous_status": "ACTIVE", "new_status": "INVALIDATED", "reason": "hazard"}],
    })
    candidate = {
        "route_nodes": [1, 4, 3], "distance_m": 1200.0, "estimated_time_s": 130.0,
        "route": {"type": "LineString", "coordinates": []},
        "hazard_summary": {"overall_score": 20.0, "score_upper_bound": upper_bound, "score_basis": "PARTIAL",
                           "critical_segments": 0, "confidence": "LIMITED"},
    }
    monkeypatch.setattr(routing_service, "calculate_route", lambda *a, **k: candidate)

    rec = route_replacement_service.recommend_replacement(route_id)
    assert rec["replacement_status"] == expected
    if expected == "NO_BETTER_ROUTE":
        assert "incomplete data" in rec["decision"]["reason"]


def test_forecast_missing_hourly_values_stay_unknown(monkeypatch):
    now_hour = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    times = [(now_hour + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(12)]
    payload = {
        "utc_offset_seconds": IST_OFFSET_S,
        "current": {"temperature_2m": 24.0, "precipitation": 0.0},
        "hourly": {
            "time": times,
            "precipitation_probability": [40, None, 60, 10, 10, 10] + [5] * 6,
            "rain": [1.0, None, 2.0, 0.0, 0.0, 0.0] + [0.0] * 6,
            "precipitation": [1.0, None, 2.0, 0.0, 0.0, 0.0] + [0.0] * 6,
            "temperature_2m": [24.0] * 12,
            "weather_code": [61] * 12,
        },
        "daily": {},
    }
    monkeypatch.setattr(weather_module.requests, "get", lambda *a, **k: _FakeResponse(payload))
    weather_service.clear_cache()
    body = client.get("/api/weather/forecast").json()
    assert body["status"] == "success"
    assert body["hourly"][1]["rain_probability_pct"] is None      # not 0
    assert body["hourly"][1]["expected_rain_mm"] is None
    assert body["summary"]["missing_hourly_values_6h"] == 1
    assert body["summary"]["data_complete_6h"] is False
    assert body["summary"]["expected_rain_6h_mm"] == 3.0           # known hours only, reported as such
    assert "missing" in body["summary"]["preparedness_reason"]


def test_provider_failures_are_cached_briefly(monkeypatch):
    """An outage must not trigger one HTTP attempt per road segment (route hang)."""
    import requests as _requests
    attempts = {"n": 0}

    def failing_get(*a, **k):
        attempts["n"] += 1
        raise _requests.exceptions.ConnectionError("provider down")

    monkeypatch.setattr(weather_module.requests, "get", failing_get)
    weather_service.clear_cache()
    for _ in range(50):
        assert weather_adapter.assess_weather()["state"] == "UNAVAILABLE"
    assert attempts["n"] == 1

    # After the failure TTL the provider is retried.
    monkeypatch.setattr(weather_service, "_cached_time", weather_service._cached_time - weather_service.FAILURE_TTL_S - 1)
    weather_adapter.assess_weather()
    assert attempts["n"] == 2
