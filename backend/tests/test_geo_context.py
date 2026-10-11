import unittest

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.geo import geo_context_service

client = TestClient(app)


pytestmark = [pytest.mark.requires_graph, pytest.mark.requires_dem]

class TestGeoContextLayer(unittest.TestCase):
    def setUp(self):
        # Coordinates in Hubballi-Dharwad operational area
        self.orig_lat = 15.3647
        self.orig_lon = 75.1240
        self.dest_lat = 15.3700
        self.dest_lon = 75.1300

    def test_01_geo_gis_status_endpoint(self):
        response = client.get("/api/geo/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("graph_available", data)
        self.assertIn("dem_available", data)
        self.assertIn("dem_source", data)
        self.assertIn("region", data)
        self.assertTrue(data["graph_available"])
        self.assertTrue(data["dem_available"])

    def test_02_geo_point_context_endpoint(self):
        response = client.get(f"/api/geo/point?lat={self.orig_lat}&lon={self.orig_lon}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["latitude"], self.orig_lat)
        self.assertEqual(data["longitude"], self.orig_lon)
        self.assertIsNotNone(data["elevation_m"])
        self.assertIsNotNone(data["susceptibility_score"])
        self.assertIsNotNone(data["nearest_node_id"])
        self.assertIsNotNone(data["nearest_node_lat"])
        self.assertIsNotNone(data["nearest_node_lon"])
        self.assertIsNotNone(data["distance_to_nearest_node_m"])

    def test_03_geo_snap_endpoint(self):
        response = client.get(f"/api/geo/snap?lat={self.orig_lat}&lon={self.orig_lon}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["input_lat"], self.orig_lat)
        self.assertEqual(data["input_lon"], self.orig_lon)
        self.assertIsInstance(data["snapped_node_id"], int)
        self.assertIsInstance(data["snapped_lat"], float)
        self.assertIsInstance(data["snapped_lon"], float)
        self.assertGreaterEqual(data["distance_m"], 0.0)

    def test_04_geo_route_context_standard_endpoint(self):
        url = (
            f"/api/geo/route-context?"
            f"origin_lat={self.orig_lat}&origin_lon={self.orig_lon}&"
            f"destination_lat={self.dest_lat}&destination_lon={self.dest_lon}&"
            f"hazard_aware=false&include_elevation=true"
        )
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("origin", data)
        self.assertIn("destination", data)
        self.assertGreater(data["distance_m"], 0.0)
        self.assertGreater(data["estimated_time_s"], 0.0)
        self.assertEqual(data["route_geometry"]["type"], "LineString")
        self.assertIsInstance(data["route_geometry"]["coordinates"], list)
        self.assertIsNotNone(data["elevation_profile"])
        self.assertIsNotNone(data["min_elevation_m"])
        self.assertIsNotNone(data["max_elevation_m"])
        self.assertLessEqual(data["min_elevation_m"], data["max_elevation_m"])

    def test_05_geo_route_context_hazard_aware_endpoint(self):
        url = (
            f"/api/geo/route-context?"
            f"origin_lat={self.orig_lat}&origin_lon={self.orig_lon}&"
            f"destination_lat={self.dest_lat}&destination_lon={self.dest_lon}&"
            f"hazard_aware=true&include_elevation=false"
        )
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["route_mode"], "HAZARD_AWARE")
        self.assertIsNotNone(data["hazard_summary"])
        self.assertIn("overall_level", data["hazard_summary"])
        self.assertIsNone(data["elevation_profile"])

    def test_06_direct_service_haversine(self):
        from app.services.geo.geo_context_service import haversine_distance_m
        dist = haversine_distance_m(15.3647, 75.1240, 15.3647, 75.1240)
        self.assertEqual(dist, 0.0)
        dist_moved = haversine_distance_m(15.3647, 75.1240, 15.3700, 75.1300)
        self.assertGreater(dist_moved, 500.0)

if __name__ == "__main__":
    unittest.main()
