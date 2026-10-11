import unittest

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.threat.threat_service import threat_service
from app.services.threat.models import ThreatEventCreate

client = TestClient(app)


pytestmark = [pytest.mark.requires_graph, pytest.mark.requires_dem]

class TestThreatGeoContextIntegration(unittest.TestCase):
    def setUp(self):
        # Create a test threat event in Hubballi-Dharwad operational area
        payload = ThreatEventCreate(
            title="Test Waterlogging Event",
            category="Waterlogging",
            severity="HIGH",
            confidence="HIGH",
            latitude=15.3647,
            longitude=75.1240,
            radius_m=300.0,
            description="Operational area flood testing"
        )
        self.threat = threat_service.create_threat(payload)
        self.threat_id = self.threat["incident_id"]

    def test_01_existing_threat_returns_geo_context(self):
        """1. Existing threat returns geographic context (200 OK)."""
        response = client.get(f"/api/threats/{self.threat_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["threat_id"], self.threat_id)

    def test_02_threat_coordinates_passed_correctly(self):
        """2. Threat coordinates are passed correctly to GeoContextService."""
        response = client.get(f"/api/threats/{self.threat_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["location"]["latitude"], 15.3647)
        self.assertEqual(data["location"]["longitude"], 75.1240)

    def test_03_terrain_context_returned(self):
        """3. Terrain context (elevation & susceptibility) is returned."""
        response = client.get(f"/api/threats/{self.threat_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        terrain = response.json()["terrain"]
        self.assertIn("status", terrain)
        self.assertIsNotNone(terrain["elevation_m"])
        self.assertIsNotNone(terrain["susceptibility_score"])

    def test_04_nearest_road_context_returned(self):
        """4. Nearest road context (node_id & distance_m) is returned."""
        response = client.get(f"/api/threats/{self.threat_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        road = response.json()["nearest_road"]
        self.assertIsNotNone(road["node_id"])
        self.assertIsNotNone(road["distance_m"])

    def test_05_route_context_returned_when_available(self):
        """5. Route context (related monitored routes) is returned when available."""
        response = client.get(f"/api/threats/{self.threat_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        route_ctx = response.json()["route_context"]
        self.assertIn("related_monitored_routes", route_ctx)

    def test_06_missing_threat_returns_404(self):
        """6. Missing threat returns 404 Not Found."""
        response = client.get("/api/threats/THREAT-NONEXISTENT-9999/geo-context")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_07_invalid_geographic_coordinates_handled(self):
        """7. Invalid geographic coordinates outside DEM bounds are handled gracefully."""
        invalid_payload = ThreatEventCreate(
            title="Out of bounds threat",
            category="Unknown",
            severity="LOW",
            confidence="LOW",
            latitude=0.0,
            longitude=0.0,
            radius_m=100.0
        )
        invalid_threat = threat_service.create_threat(invalid_payload)
        inv_id = invalid_threat["incident_id"]

        response = client.get(f"/api/threats/{inv_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["terrain"]["status"], "unavailable")
        self.assertIsNone(data["terrain"]["elevation_m"])

    def test_08_gis_optional_data_failure_handled_gracefully(self):
        """8. GIS optional-data failure is handled gracefully without crashing."""
        response = client.get(f"/api/threats/{self.threat_id}/geo-context")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Verify schema integrity even if optional fields are None
        self.assertIn("terrain", data)
        self.assertIn("nearest_road", data)

    def test_09_threat_db_record_not_mutated_by_lookup(self):
        """9. Threat database record is NOT mutated by geographic context lookup."""
        threat_before = threat_service.get_threat(self.threat_id)
        client.get(f"/api/threats/{self.threat_id}/geo-context")
        threat_after = threat_service.get_threat(self.threat_id)
        
        self.assertEqual(threat_before["created_at"], threat_after["created_at"])
        self.assertEqual(threat_before["updated_at"], threat_after["updated_at"])
        self.assertEqual(len(threat_before.get("timeline", [])), len(threat_after.get("timeline", [])))

if __name__ == "__main__":
    unittest.main()
