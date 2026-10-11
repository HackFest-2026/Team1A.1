import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.services.evidence.evidence_service import evidence_service
from app.services.evidence.models import EvidenceCreate, EvidenceUpdate, EvidenceResponse
from app.services.threat.threat_service import threat_service
from app.services.threat.models import ThreatEventCreate
from app.repositories.evidence_repository import evidence_repository
from app.repositories.threat_repository import threat_repository

client = TestClient(app)

class TestEvidenceDomain(unittest.TestCase):
    def setUp(self):
        # Create a sample threat for association tests
        payload = ThreatEventCreate(
            title="Test Baseline Threat for Evidence",
            category="Flood",
            severity="HIGH",
            confidence="HIGH",
            latitude=15.3647,
            longitude=75.1240,
            radius_m=400.0,
            description="Baseline threat event"
        )
        self.threat = threat_service.create_threat(payload)
        self.threat_id = self.threat["incident_id"]

    def test_01_create_evidence(self):
        """1. Create evidence."""
        payload = {
            "source_type": "DRONE",
            "source_id": "DRONE-01",
            "observation_type": "WATERLOGGING_PHOTO",
            "latitude": 15.3650,
            "longitude": 75.1250,
            "confidence": 0.95,
            "description": "Drone footage showing road inundation"
        }
        response = client.post("/api/evidence", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["evidence_id"].startswith("EVD-"))
        self.assertEqual(data["source_type"], "DRONE")
        self.assertEqual(data["status"], "NEW")

    def test_02_retrieve_evidence(self):
        """2. Retrieve evidence by ID."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="SENSOR",
            observation_type="WATER_LEVEL",
            confidence=0.8
        ))
        ev_id = ev["evidence_id"]
        response = client.get(f"/api/evidence/{ev_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["evidence_id"], ev_id)

    def test_03_list_evidence(self):
        """3. List evidence with filters."""
        evidence_service.create_evidence(EvidenceCreate(
            source_type="SATELLITE",
            observation_type="RADAR_IMAGERY",
            confidence=0.9
        ))
        response = client.get("/api/evidence?source_type=SATELLITE")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertTrue(len(items) >= 1)
        for item in items:
            self.assertEqual(item["source_type"], "SATELLITE")

    def test_04_persist_evidence(self):
        """4. Persist evidence across repository lookup."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="HUMAN_REPORT",
            observation_type="CITIZEN_CALL",
            description="Flooding reported near market",
            confidence=0.7
        ))
        ev_id = ev["evidence_id"]
        fetched = evidence_repository.get_by_id(ev_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["source_type"], "HUMAN_REPORT")

    def test_05_validate_confidence_range(self):
        """5. Validate confidence range (0.0 to 1.0)."""
        # Invalid confidence > 1.0
        payload_high = {
            "source_type": "SENSOR",
            "observation_type": "TEST",
            "confidence": 1.5
        }
        response_high = client.post("/api/evidence", json=payload_high)
        self.assertEqual(response_high.status_code, 422)

        # Invalid confidence < 0.0
        payload_low = {
            "source_type": "SENSOR",
            "observation_type": "TEST",
            "confidence": -0.1
        }
        response_low = client.post("/api/evidence", json=payload_low)
        self.assertEqual(response_low.status_code, 422)

    def test_06_validate_latitude_longitude(self):
        """6. Validate latitude (-90..90) and longitude (-180..180)."""
        # Invalid latitude
        response_lat = client.post("/api/evidence", json={
            "source_type": "DRONE",
            "observation_type": "TEST",
            "latitude": 95.0,
            "longitude": 75.0
        })
        self.assertEqual(response_lat.status_code, 422)

        # Invalid longitude
        response_lon = client.post("/api/evidence", json={
            "source_type": "DRONE",
            "observation_type": "TEST",
            "latitude": 15.0,
            "longitude": 200.0
        })
        self.assertEqual(response_lon.status_code, 422)

    def test_07_reject_invalid_source_type(self):
        """7. Reject invalid source type."""
        response = client.post("/api/evidence", json={
            "source_type": "INVALID_TYPE",
            "observation_type": "TEST"
        })
        self.assertEqual(response.status_code, 422)

    def test_08_associate_evidence_with_existing_threat(self):
        """8. Associate evidence with existing threat."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="DRONE",
            observation_type="OVERVIEW"
        ))
        ev_id = ev["evidence_id"]

        response = client.post(f"/api/evidence/{ev_id}/associate-threat", json={
            "threat_id": self.threat_id
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["threat_id"], self.threat_id)
        self.assertEqual(data["status"], "ASSOCIATED")

    def test_09_reject_association_with_missing_threat(self):
        """9. Reject association with missing threat (returns 404)."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="SENSOR",
            observation_type="WATER_LEVEL"
        ))
        ev_id = ev["evidence_id"]

        response = client.post(f"/api/evidence/{ev_id}/associate-threat", json={
            "threat_id": "THREAT-NONEXISTENT-9999"
        })
        self.assertEqual(response.status_code, 404)

    def test_10_prevent_unsafe_duplicate_association(self):
        """10. Prevent unsafe duplicate association (idempotent operation)."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="SIMULATION",
            observation_type="SIM_FLOOD"
        ))
        ev_id = ev["evidence_id"]

        # First association
        r1 = client.post(f"/api/evidence/{ev_id}/associate-threat", json={"threat_id": self.threat_id})
        self.assertEqual(r1.status_code, 200)

        # Second association with same threat ID
        r2 = client.post(f"/api/evidence/{ev_id}/associate-threat", json={"threat_id": self.threat_id})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["threat_id"], self.threat_id)

    def test_11_archive_evidence(self):
        """11. Archive evidence."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="HUMAN_REPORT",
            observation_type="OLD_REPORT"
        ))
        ev_id = ev["evidence_id"]

        response = client.post(f"/api/evidence/{ev_id}/archive")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ARCHIVED")

    def test_12_evidence_creation_does_not_create_threat(self):
        """12. Evidence creation does NOT create a threat."""
        threat_count_before = len(threat_repository.get_all())
        evidence_service.create_evidence(EvidenceCreate(
            source_type="SENSOR",
            observation_type="RAIN_GAUGE"
        ))
        threat_count_after = len(threat_repository.get_all())
        self.assertEqual(threat_count_before, threat_count_after)

    def test_13_evidence_association_does_not_change_threat_severity(self):
        """13. Evidence association does NOT automatically change threat severity."""
        threat_before = threat_service.get_threat(self.threat_id)
        sev_before = threat_before["severity"]

        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="DRONE",
            observation_type="EXTREME_FLOOD_IMAGE"
        ))
        evidence_service.associate_evidence_with_threat(ev["evidence_id"], self.threat_id)

        threat_after = threat_service.get_threat(self.threat_id)
        self.assertEqual(threat_after["severity"], sev_before)

    def test_14_evidence_creation_does_not_mutate_unrelated_threat_fields(self):
        """14. Evidence creation does NOT mutate unrelated threat fields."""
        threat_before = threat_service.get_threat(self.threat_id)
        
        evidence_service.create_evidence(EvidenceCreate(
            source_type="SIMULATION",
            observation_type="WATER_SURGE"
        ))

        threat_after = threat_service.get_threat(self.threat_id)
        self.assertEqual(threat_before["title"], threat_after["title"])
        self.assertEqual(threat_before["updated_at"], threat_after["updated_at"])

    def test_15_evidence_response_conforms_to_pydantic_schema(self):
        """15. Evidence response conforms to Pydantic schema."""
        ev = evidence_service.create_evidence(EvidenceCreate(
            source_type="SATELLITE",
            source_id="SENTINEL-2B",
            observation_type="OPTICAL_IMAGERY",
            latitude=15.3647,
            longitude=75.1240,
            confidence=0.88,
            description="Satellite optical pass"
        ))
        parsed = EvidenceResponse(**ev)
        self.assertEqual(parsed.evidence_id, ev["evidence_id"])
        self.assertEqual(parsed.confidence, 0.88)

if __name__ == "__main__":
    unittest.main()
