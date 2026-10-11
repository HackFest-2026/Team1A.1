import sys
import unittest

import pytest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.connection import init_db
from app.services.cop.cop_service import cop_service
from app.services.cop.models import COPSnapshotResponse, COPSummaryResponse
from app.services.threat.threat_service import threat_service
from app.services.threat.models import ThreatEventCreate
from app.services.field_operations.field_service import field_service, FieldUnit
from app.services.route_monitor_service import route_monitor_service
from fastapi.testclient import TestClient
from app.main import app


pytestmark = pytest.mark.requires_graph

class TestCopContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_cop_snapshot_endpoint(self):
        """Test 1 & 2: GET /api/cop returns 200 and validates against COPSnapshotResponse schema."""
        res = self.client.get("/api/cop")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        # Schema validation via Pydantic model
        snapshot = COPSnapshotResponse(**data)
        self.assertIsNotNone(snapshot.generated_at)
        self.assertEqual(snapshot.system.status, "ONLINE")
        self.assertEqual(snapshot.map.region, "Hubballi-Dharwad")

    def test_02_threats_in_cop_snapshot(self):
        """Test 3: Threat data appears in COP snapshot."""
        # Create a threat event
        t_payload = ThreatEventCreate(
            title="COP Test Threat Event",
            category="Road Waterlogging",
            severity="HIGH",
            latitude=15.3647,
            longitude=75.1240,
            radius_m=600.0
        )
        created = threat_service.create_threat(t_payload)
        t_id = created["incident_id"]

        snapshot = cop_service.get_cop_snapshot()
        matching_threats = [t for t in snapshot.threats if t.id == t_id]
        self.assertEqual(len(matching_threats), 1, "Created threat must appear in COP snapshot")
        self.assertEqual(matching_threats[0].title, "COP Test Threat Event")
        self.assertEqual(matching_threats[0].radius_m, 600.0)

    def test_03_field_units_in_cop_snapshot(self):
        """Test 4: Field unit data appears in COP snapshot."""
        unit = FieldUnit(
            name="COP Special Rescue Team",
            unit_type="RESCUE_TEAM",
            status="ASSIGNED",
            state="Karnataka",
            district="Dharwad",
            city="Hubballi"
        )
        created_unit = field_service.create_unit(unit)
        u_id = created_unit.field_unit_id

        snapshot = cop_service.get_cop_snapshot()
        matching_units = [u for u in snapshot.field_units if u.id == u_id]
        self.assertEqual(len(matching_units), 1, "Created field unit must appear in COP snapshot")
        self.assertEqual(matching_units[0].name, "COP Special Rescue Team")

    def test_04_monitored_routes_in_cop_snapshot(self):
        """Test 5: Monitored route data appears in COP snapshot."""
        r_payload = {
            "origin": {"lat": 15.365, "lon": 75.125},
            "destination": {"lat": 15.370, "lon": 75.130},
            "route_nodes": [501, 502],
            "distance_m": 1500.0,
            "estimated_time_s": 200.0
        }
        res = route_monitor_service.register_route(r_payload)
        r_id = res["route_id"]

        snapshot = cop_service.get_cop_snapshot()
        matching_routes = [r for r in snapshot.monitored_routes if r.id == r_id]
        self.assertEqual(len(matching_routes), 1, "Monitored route must appear in COP snapshot")
        self.assertEqual(matching_routes[0].distance_m, 1500.0)

    def test_05_cop_summary_endpoint(self):
        """Test 6: GET /api/cop/summary returns 200 and valid statistics."""
        res = self.client.get("/api/cop/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        summary = COPSummaryResponse(**data)
        self.assertEqual(summary.system_status, "ONLINE")
        self.assertGreater(summary.active_threat_count, 0)
        self.assertGreater(summary.active_unit_count, 0)

if __name__ == "__main__":
    unittest.main()
