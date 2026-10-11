import unittest
import datetime
from unittest.mock import patch
import requests
from fastapi.testclient import TestClient
from app.main import app
from app.services.scenario_service import scenario_service
from app.services.weather_service import weather_service

class TestWeatherForecastAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        scenario_service.set_active(False)
        weather_service.clear_cache()

    def tearDown(self):
        scenario_service.set_active(False)
        weather_service.clear_cache()

    def test_01_get_weather_current(self):
        res = self.client.get("/api/weather")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("data", data)
        if data["status"] == "success":
            curr = data["data"]
            self.assertIn("temperature_c", curr)
            self.assertIn("precipitation_mm", curr)
            self.assertIn("wind_speed_kmh", curr)

    def test_02_get_weather_forecast_live(self):
        res = self.client.get("/api/weather/forecast")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertFalse(data.get("is_controlled_scenario"))
        self.assertIn("location", data)
        self.assertIn("current", data)
        self.assertIn("summary", data)
        self.assertIn("hourly", data)
        self.assertIn("daily", data)

        # Check hourly fields & current hour alignment
        hourly = data["hourly"]
        self.assertGreaterEqual(len(hourly), 24)
        first = hourly[0]
        self.assertIn("time", first)
        self.assertIn("rain_probability_pct", first)
        self.assertIn("expected_rain_mm", first)
        self.assertIn("precipitation_mm", first)
        self.assertIn("temperature_c", first)
        self.assertIn("weather_code", first)

        # Verify hourly points start at or near current hour
        current_hour_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
        self.assertGreaterEqual(first["time"], current_hour_str[:13])

        # Check summary metrics
        summary = data["summary"]
        self.assertIn("max_prob_6h", summary)
        self.assertIn("expected_rain_6h_mm", summary)
        self.assertIn("preparedness_level", summary)
        self.assertIn("preparedness_badge", summary)
        self.assertIn("recommendations", summary)
        self.assertIn("active_drainage_issues", summary)

    def test_03_controlled_scenario_forecast_toggle_and_cache_purging(self):
        # Activate scenario
        res_act = self.client.post("/api/scenario/activate")
        self.assertEqual(res_act.status_code, 200)

        # Fetch forecast in scenario mode
        res_scen = self.client.get("/api/weather/forecast")
        self.assertEqual(res_scen.status_code, 200)
        scen_data = res_scen.json()
        self.assertTrue(scen_data.get("is_controlled_scenario"))
        self.assertEqual(scen_data.get("source"), "CONTROLLED SCENARIO")
        self.assertEqual(scen_data["summary"]["preparedness_level"], "CRITICAL PREPAREDNESS")
        self.assertEqual(len(scen_data["hourly"]), 48)

        # Deactivate scenario
        res_deact = self.client.post("/api/scenario/deactivate")
        self.assertEqual(res_deact.status_code, 200)

        # Fetch forecast after deactivation (cache must be purged, returning live data)
        res_live = self.client.get("/api/weather/forecast")
        self.assertEqual(res_live.status_code, 200)
        live_data = res_live.json()
        self.assertFalse(live_data.get("is_controlled_scenario"))
        self.assertIn("Open-Meteo", live_data.get("source", ""))

    @patch("requests.get")
    def test_04_api_failure_returns_unavailable_state_without_fabrication(self, mock_get):
        weather_service.clear_cache()
        mock_get.side_effect = requests.exceptions.RequestException("Connection timed out")

        res = self.client.get("/api/weather/forecast")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "unavailable")
        self.assertIn("WEATHER DATA TEMPORARILY UNAVAILABLE", data.get("error", ""))
        self.assertNotIn("hourly", data)

if __name__ == "__main__":
    unittest.main()

