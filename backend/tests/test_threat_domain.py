import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.connection import init_db
from app.services.threat.threat_service import ThreatService, threat_service
from app.services.threat.models import ThreatEventCreate, ThreatEventUpdate, RouteExposureRequest
from app.repositories.threat_repository import threat_repository
from fastapi.testclient import TestClient
from app.main import app

class TestThreatDomain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_create_threat_event(self):
        """Test 1 & 2: Create threat event and verify persistence."""
        payload = ThreatEventCreate(
            title="Gokul Road Deep Waterlogging",
            category="Road Waterlogging",
            severity="HIGH",
            confidence="HIGH",
            latitude=15.3647,
            longitude=75.1240,
            radius_m=600.0,
            description="Severe inundation near Gokul Road corridor",
            evidence_references=["EVD-TEST-001"]
        )
        result = threat_service.create_threat(payload)
        self.assertIn("incident_id", result)
        self.assertEqual(result["title"], "Gokul Road Deep Waterlogging")
        self.assertEqual(result["radius_m"], 600.0)

        # Verify SQLite row
        db_threat = threat_repository.get_by_id(result["incident_id"])
        self.assertIsNotNone(db_threat, "Created threat event must exist in SQLite DB")
        self.assertEqual(db_threat["title"], "Gokul Road Deep Waterlogging")
        self.assertEqual(db_threat["evidence_references"], ["EVD-TEST-001"])

    def test_02_retrieve_threat_event(self):
        """Test 3: Retrieve threat event by ID."""
        payload = ThreatEventCreate(
            title="Dharwad Central Drainage Blockage",
            category="Drainage Overflow",
            severity="MODERATE",
            latitude=15.4589,
            longitude=75.0078,
            radius_m=400.0
        )
        created = threat_service.create_threat(payload)
        t_id = created["incident_id"]

        retrieved = threat_service.get_threat(t_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["incident_id"], t_id)
        self.assertEqual(retrieved["category"], "Drainage Overflow")

    def test_03_update_threat_event(self):
        """Test 4: Update severity, confidence, status, and radius."""
        payload = ThreatEventCreate(
            title="Unkal Lake Overflow",
            category="Culvert Overflow",
            severity="HIGH",
            confidence="MEDIUM",
            latitude=15.3850,
            longitude=75.1050,
            radius_m=500.0
        )
        created = threat_service.create_threat(payload)
        t_id = created["incident_id"]

        update_payload = ThreatEventUpdate(
            severity="CRITICAL",
            confidence="HIGH",
            status="ACTIVE",
            radius_m=850.0
        )
        updated = threat_service.update_threat(t_id, update_payload)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["severity"], "CRITICAL")
        self.assertEqual(updated["confidence"], "HIGH")
        self.assertEqual(updated["status"], "ACTIVE")
        self.assertEqual(updated["radius_m"], 850.0)

    def test_04_close_threat_event(self):
        """Test 5: Close threat event."""
        payload = ThreatEventCreate(
            title="Temporary Water Accumulation",
            category="Road Waterlogging",
            severity="LOW",
            latitude=15.3550,
            longitude=75.1320
        )
        created = threat_service.create_threat(payload)
        t_id = created["incident_id"]

        closed = threat_service.close_threat(t_id, reason="Runoff cleared by maintenance team")
        self.assertIsNotNone(closed)
        self.assertEqual(closed["status"], "CLOSED")
        self.assertIsNotNone(closed["resolved_at"])

    def test_05_restart_persistence(self):
        """Test 6: Threat event survives fresh service/repository instance restart."""
        payload = ThreatEventCreate(
            title="Vidyanagar Junction Inundation",
            category="Flooded Junction",
            severity="HIGH",
            latitude=15.3720,
            longitude=75.1180,
            radius_m=750.0
        )
        created = threat_service.create_threat(payload)
        t_id = created["incident_id"]

        # Simulate backend restart with fresh service instance
        fresh_svc = ThreatService()
        reopened = fresh_svc.get_threat(t_id)
        self.assertIsNotNone(reopened, "Threat event must survive backend restart")
        self.assertEqual(reopened["incident_id"], t_id)
        self.assertEqual(reopened["radius_m"], 750.0)

    def test_06_threat_zone_generation(self):
        """Test 7: Threat Zone generation from location + radius."""
        payload = ThreatEventCreate(
            title="Keshwapur Drain Overflow",
            category="Open Drain Blockage",
            severity="HIGH",
            latitude=15.3600,
            longitude=75.1450,
            radius_m=500.0
        )
        created = threat_service.create_threat(payload)
        t_id = created["incident_id"]

        zone = threat_service.get_threat_zone(t_id)
        self.assertIsNotNone(zone)
        self.assertEqual(zone["threat_id"], t_id)
        self.assertEqual(zone["radius_m"], 500.0)
        self.assertEqual(zone["center"]["lat"], 15.3600)
        self.assertEqual(zone["center"]["lon"], 75.1450)
        self.assertIn("bounding_box", zone)

    def test_07_route_exposure_contract(self):
        """Test 8: Route exposure contract evaluation."""
        payload = ThreatEventCreate(
            title="Gokul Road Critical Inundation",
            category="Road Waterlogging",
            severity="CRITICAL",
            latitude=15.3647,
            longitude=75.1240,
            radius_m=500.0
        )
        created = threat_service.create_threat(payload)
        t_id = created["incident_id"]

        # Route passing right through (15.3647, 75.1240)
        intersecting_coords = [
            [75.1200, 15.3640],
            [75.1240, 15.3647], # Exact center hit
            [75.1280, 15.3655]
        ]
        exposure = threat_service.assess_route_exposure(intersecting_coords, threat_ids=[t_id])
        self.assertTrue(exposure["exposed"])
        self.assertGreater(exposure["exposure_score"], 50.0)
        self.assertIn(t_id, exposure["affected_threat_ids"])

        # Route far away
        safe_coords = [
            [75.0000, 15.0000],
            [75.0010, 15.0010]
        ]
        safe_exposure = threat_service.assess_route_exposure(safe_coords, threat_ids=[t_id])
        self.assertFalse(safe_exposure["exposed"])
        self.assertEqual(safe_exposure["exposure_score"], 0.0)

    def test_08_threat_api_endpoints(self):
        """Test 9: REST API endpoints for threats router."""
        # List threats
        res = self.client.get("/api/threats")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

        # Create threat via POST
        create_res = self.client.post("/api/threats", json={
            "title": "API Created Threat",
            "category": "Flood",
            "severity": "HIGH",
            "confidence": "HIGH",
            "latitude": 15.36,
            "longitude": 75.12,
            "radius_m": 450.0,
            "state": "Karnataka",
            "district": "Dharwad",
            "description": "Created via REST API"
        })
        self.assertEqual(create_res.status_code, 201)
        threat_data = create_res.json()
        t_id = threat_data["incident_id"]

        # Get threat by ID
        get_res = self.client.get(f"/api/threats/{t_id}")
        self.assertEqual(get_res.status_code, 200)

        # Get threat zone
        zone_res = self.client.get(f"/api/threats/{t_id}/zone")
        self.assertEqual(zone_res.status_code, 200)

        # Update threat
        patch_res = self.client.patch(f"/api/threats/{t_id}", json={"severity": "CRITICAL", "radius_m": 800.0})
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["severity"], "CRITICAL")

        # Assess route exposure
        exp_res = self.client.post("/api/threats/assess-exposure", json={
            "route_coordinates": [[75.12, 15.36]],
            "threat_ids": [t_id]
        })
        self.assertEqual(exp_res.status_code, 200)
        self.assertTrue(exp_res.json()["exposed"])

        # Close threat
        close_res = self.client.post(f"/api/threats/{t_id}/close?reason=API_TEST_COMPLETE")
        self.assertEqual(close_res.status_code, 200)
        self.assertEqual(close_res.json()["status"], "CLOSED")

if __name__ == "__main__":
    unittest.main()
