import sys
import unittest

import pytest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.connection import init_db, get_db_context
from app.models.threat_event import IncidentModel
from app.models.field_unit import FieldUnitModel
from app.models.monitored_route import MonitoredRouteModel
from app.services.incidents.incident_service import IncidentService
from app.services.field_operations.field_service import FieldService, FieldUnit
from app.services.route_monitor_service import RouteMonitorService
from app.repositories.threat_repository import threat_repository
from app.repositories.field_unit_repository import field_unit_repository
from app.repositories.monitored_route_repository import monitored_route_repository
from fastapi.testclient import TestClient
from app.main import app


pytestmark = pytest.mark.requires_graph

class TestPersistence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_incident_persistence(self):
        """Test 1: Create an incident and verify SQLite row."""
        inc_service = IncidentService()
        scan_res = inc_service.scan_for_incidents()
        self.assertEqual(scan_res["status"], "success")
        
        db_count = threat_repository.count()
        self.assertGreater(db_count, 0, "Incidents should be persisted in SQLite DB")
        
        incidents = threat_repository.get_all()
        first_inc = incidents[0]
        self.assertIn("incident_id", first_inc)
        self.assertIn("title", first_inc)

    def test_02_field_unit_persistence(self):
        """Test 2: Create a field unit and verify SQLite row."""
        field_svc = FieldService()
        new_unit = FieldUnit(
            name="Alpha Strike Team",
            unit_type="RESCUE_TEAM",
            status="ASSIGNED",
            state="Karnataka",
            district="Dharwad",
            city="Hubballi"
        )
        created = field_svc.create_unit(new_unit)
        self.assertEqual(created.name, "Alpha Strike Team")

        db_unit = field_unit_repository.get_by_id(created.field_unit_id)
        self.assertIsNotNone(db_unit, "Created Field Unit must exist in SQLite DB")
        self.assertEqual(db_unit["name"], "Alpha Strike Team")

    def test_03_monitored_route_persistence(self):
        """Test 3: Register a monitored route and verify SQLite row."""
        monitor_svc = RouteMonitorService()
        payload = {
            "origin": {"lat": 15.365, "lon": 75.125},
            "destination": {"lat": 15.370, "lon": 75.130},
            "route_nodes": [101, 102, 103],
            "distance_m": 1250.0,
            "estimated_time_s": 180.0
        }
        res = monitor_svc.register_route(payload)
        self.assertEqual(res["status"], "success")
        route_id = res["route_id"]

        db_route = monitored_route_repository.get_by_id(route_id)
        self.assertIsNotNone(db_route, "Monitored Route must exist in SQLite DB")
        self.assertEqual(db_route["distance_m"], 1250.0)

    def test_04_restart_persistence(self):
        """Test 4: Simulate application restart & verify records survive in fresh service instance."""
        # 1. Register a distinct route
        monitor_svc = RouteMonitorService()
        p_res = monitor_svc.register_route({
            "origin": {"lat": 15.400, "lon": 75.100},
            "destination": {"lat": 15.410, "lon": 75.110},
            "route_nodes": [9991, 9992],
            "distance_m": 850.0,
            "estimated_time_s": 120.0
        })
        route_id = p_res["route_id"]

        # 2. Simulate complete restart by instantiating FRESH service objects
        fresh_inc_svc = IncidentService()
        fresh_field_svc = FieldService()
        fresh_monitor_svc = RouteMonitorService()

        # 3. Assert data is retrieved from DB on fresh service instantiation
        retrieved_route = fresh_monitor_svc.get_route(route_id)
        self.assertEqual(retrieved_route["status"], "success", "Route record should survive backend restart")
        self.assertEqual(retrieved_route["route_id"], route_id)

        incidents = fresh_inc_svc.get_all()
        self.assertGreater(len(incidents), 0, "Incidents should survive backend restart")

        units = fresh_field_svc.get_all()
        self.assertGreater(len(units), 0, "Field Units should survive backend restart")

    def test_05_api_endpoints_regression(self):
        """Regression tests for API endpoints."""
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/system/status").status_code, 200)
        self.assertEqual(self.client.get("/api/gis/status").status_code, 200)
        self.assertEqual(self.client.get("/api/national/incidents").status_code, 200)
        self.assertEqual(self.client.get("/api/national/field-units").status_code, 200)

        route_res = self.client.get("/api/route?origin_lat=15.365&origin_lon=75.125&destination_lat=15.370&destination_lon=75.130")
        self.assertEqual(route_res.status_code, 200)

        register_res = self.client.post("/api/route-monitor/register", json={
            "origin": {"lat": 15.365, "lon": 75.125},
            "destination": {"lat": 15.370, "lon": 75.130},
            "route_nodes": [101, 102],
            "distance_m": 500.0,
            "estimated_time_s": 60.0
        })
        self.assertEqual(register_res.status_code, 200)
        r_id = register_res.json()["route_id"]

        rec_res = self.client.post(f"/api/route-monitor/{r_id}/replacement/recommend")
        self.assertEqual(rec_res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
