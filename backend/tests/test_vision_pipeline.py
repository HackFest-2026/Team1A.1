"""Tests for AEGIS-COP Maritime Vision Intelligence Pipeline."""

import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.vision.explosion_classifier import ExplosionEventClassifier
from app.services.vision.fire_smoke import FireSmokeAnalyzer
from app.services.vision.object_detector import MaritimeObjectDetector
from app.services.vision.projectile_detector import MaritimeProjectileDetector
from app.services.vision.suspicious_objects import SuspiciousObjectReviewer
from app.services.vision.types import Detection, DetectionCategory
from app.services.vision.vessel_intelligence import MaritimeVesselIntelligence

client = TestClient(app)


def test_vision_status_endpoint():
    """Verify vision status reports all integrated pipeline models and provenance."""
    res = client.get("/api/vision/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["pipeline"] == "multi_model_maritime_intelligence"
    assert "models" in data
    assert len(data["models"]) >= 5

    model_names = [m["name"] for m in data["models"]]
    assert any("YOLO" in n for n in model_names)
    assert any("Fire" in n for n in model_names)
    assert any("Blast" in n or "Explosion" in n for n in model_names)
    assert any("Projectile" in n or "Missile" in n for n in model_names)


def test_fire_smoke_analyzer_flame_and_exhaust_distinction():
    """Verify fire is detected for flame color, but vessel exhaust is distinguished from fire."""
    analyzer = FireSmokeAnalyzer()

    # 1. Flame synthetic patch (High saturation orange-red combustion core)
    flame_frame = np.zeros((200, 200, 3), dtype=np.uint8)
    # BGR for high flame: Yellow-Orange (B=20, G=150, R=255)
    flame_frame[80:120, 80:120] = [20, 160, 255]

    flame_dets = analyzer.analyze_frame(flame_frame, timestamp_s=2.5)
    fire_labels = [d.label for d in flame_dets]
    assert "fire" in fire_labels

    # 2. Vessel exhaust synthetic patch: dark grey smoke directly above vessel hull
    exhaust_frame = np.zeros((400, 400, 3), dtype=np.uint8)
    # Water background (blue-green)
    exhaust_frame[:, :] = [180, 120, 50]
    # Dark grey smoke patch at (150, 100) to (250, 180)
    exhaust_frame[100:180, 150:250] = [70, 70, 70]

    # Vessel hull located at [120, 170, 280, 300]
    vessel_bboxes = [[120.0, 170.0, 280.0, 300.0]]
    exhaust_dets = analyzer.analyze_frame(exhaust_frame, timestamp_s=4.0, vessel_bboxes=vessel_bboxes)

    labels = [d.label for d in exhaust_dets]
    assert "vessel_exhaust_smoke" in labels
    assert "fire" not in labels  # Must NOT label engine smoke as fire!


def test_fire_smoke_analyzer_incandescent_fire_and_wave_rejection():
    """Verify white-yellow incandescent explosion fireballs are detected and water ripples are rejected."""
    analyzer = FireSmokeAnalyzer()

    # 1. White-yellow incandescent blast core (camera desaturation typical of naval explosions)
    blast_frame = np.zeros((300, 300, 3), dtype=np.uint8)
    # Bright incandescent plasma: R=240, G=225, B=185
    blast_frame[100:150, 100:160] = [185, 225, 240]
    blast_dets = analyzer.analyze_frame(blast_frame, timestamp_s=10.0)
    blast_labels = [d.label for d in blast_dets]
    assert "fire" in blast_labels

    # 2. Open water surface ripples (thin horizontal wave crests in lower ocean)
    wave_frame = np.zeros((400, 400, 3), dtype=np.uint8)
    # Open water background: H~100, S~40, V~100 (in BGR: ~[110, 95, 70])
    wave_frame[:, :] = [110, 95, 70]
    # Surface wave ripples (aspect ratio > 6, thin horizontal strip, lower ocean)
    wave_frame[280:292, 120:260] = [60, 60, 60]  # thin horizontal strip (bw=140, bh=12)
    wave_dets = analyzer.analyze_frame(wave_frame, timestamp_s=12.0)
    # Wave ripples must be rejected, NOT detected as smoke!
    smoke_dets = [d for d in wave_dets if d.label == "smoke"]
    assert len(smoke_dets) == 0


def test_projectile_detector_kinetic_tracking():
    """Verify kinetic projectile detector tracks fast directional motion and flags anti-ship missile."""
    detector = MaritimeProjectileDetector()

    # Create sequence of 3 frames with a fast-moving projectile with radiant flare head
    # Frame 1: Projectile at x=60, y=100
    f1 = np.zeros((400, 500, 3), dtype=np.uint8)
    # Radiant flare head: R=230, G=210, B=210
    f1[95:105, 50:70] = [210, 210, 230]

    d1 = detector.analyze_frame(f1, timestamp_s=1.0, frame_index=0)

    # Frame 2: Projectile moved to x=150, y=102 (fast horizontal displacement: dx=90, dt=0.5s -> 180 px/s)
    f2 = np.zeros((400, 500, 3), dtype=np.uint8)
    # Horizontal vapor trail behind radiant head
    f2[97:103, 90:140] = [180, 180, 180]
    f2[95:105, 140:160] = [210, 210, 230]

    d2 = detector.analyze_frame(f2, timestamp_s=1.5, frame_index=1)
    assert len(d2) >= 1
    assert any(d.label in {"missile_trajectory", "anti_ship_missile"} for d in d2)
    assert any(d.category == DetectionCategory.PROJECTILE.value for d in d2)

    # Frame 3: Converging on a vessel located at [220, 70, 350, 180]
    f3 = np.zeros((400, 500, 3), dtype=np.uint8)
    f3[97:103, 170:220] = [180, 180, 180]
    f3[95:105, 220:240] = [210, 210, 230]

    vessel_boxes = [[220.0, 70.0, 350.0, 180.0]]
    d3 = detector.analyze_frame(f3, timestamp_s=2.0, frame_index=2, vessel_bboxes=vessel_boxes)
    assert len(d3) >= 1
    # Near vessel hull, must escalate to anti_ship_missile!
    assert any(d.label == "anti_ship_missile" for d in d3)
    events = detector.get_events()
    assert len(events) >= 1
    assert events[0].event_type in {"missile_inbound_alert", "missile_strike_event"}


def test_explosion_classifier_temporal_event_and_false_alarm_rejection():
    """Verify temporal radiant surge detects explosion, but global camera flash is rejected."""
    classifier = ExplosionEventClassifier()

    # Scenario A: Localized radiant blast core expansion
    frame_a0 = np.zeros((200, 200, 3), dtype=np.uint8)
    frame_a0[:, :] = [100, 100, 100]

    frame_a1 = frame_a0.copy()
    # Localized bright flame flash
    frame_a1[80:120, 80:120] = [30, 200, 255]

    frame_a2 = frame_a0.copy()
    # Lingering dark smoke plume
    frame_a2[70:130, 70:130] = [50, 50, 50]

    records_blast = [
        {"frame_index": 0, "timestamp_seconds": 0.0, "frame_bgr": frame_a0},
        {"frame_index": 1, "timestamp_seconds": 0.5, "frame_bgr": frame_a1},
        {"frame_index": 2, "timestamp_seconds": 1.0, "frame_bgr": frame_a2},
    ]

    events = classifier.classify_sequence(records_blast, fps=2.0)
    assert len(events) >= 1
    assert events[0].event_type == "possible_explosion_event"
    assert events[0].verification_status == "possible_event"
    assert len(events[0].limitations) >= 2

    # Scenario B: Global camera exposure jump / scene cut (entire frame flashes white)
    frame_flash = np.ones((200, 200, 3), dtype=np.uint8) * 240
    records_global_flash = [
        {"frame_index": 0, "timestamp_seconds": 0.0, "frame_bgr": frame_a0},
        {"frame_index": 1, "timestamp_seconds": 0.5, "frame_bgr": frame_flash},
        {"frame_index": 2, "timestamp_seconds": 1.0, "frame_bgr": frame_a0},
    ]

    flash_events = classifier.classify_sequence(records_global_flash, fps=2.0)
    # Must reject global flash as camera exposure change, NOT an explosion
    assert len(flash_events) == 0


def test_suspicious_object_safety_rule():
    """Verify suspicious object triage never invents bombs or weapon classifications."""
    reviewer = SuspiciousObjectReviewer()

    sample_dets = [
        Detection(
            label="backpack",
            category="suspicious_object",
            confidence=0.82,
            timestamp_seconds=1.0,
            bbox=[10.0, 20.0, 40.0, 60.0],
            track_id=1,
        ),
        Detection(
            label="boat",
            category="vessel",
            confidence=0.91,
            timestamp_seconds=1.0,
            bbox=[50.0, 50.0, 200.0, 150.0],
            track_id=2,
        ),
    ]

    reviewed = reviewer.review_detections(sample_dets)
    assert len(reviewed) == 1
    assert reviewed[0].label == "unverified_suspicious_object"
    assert reviewed[0].verification_status == "requires_review"
    assert "Cannot establish hazard or explosive content" in reviewed[0].notes


def test_vessel_intelligence_size_and_person_correlation():
    """Verify vessel size categorization, crew count on board, and AIS correlation."""
    intel = MaritimeVesselIntelligence()

    # Frame with vessel and person on board
    frames_data = [
        {
            "frame": 0,
            "timestamp_seconds": 0.0,
            "detections": [
                Detection(
                    label="boat",
                    category="vessel",
                    confidence=0.85,
                    timestamp_seconds=0.0,
                    bbox=[50.0, 50.0, 350.0, 250.0],
                    track_id=5,
                ),
                Detection(
                    label="person",
                    category="person",
                    confidence=0.78,
                    timestamp_seconds=0.0,
                    bbox=[120.0, 80.0, 150.0, 160.0],
                    track_id=10,
                ),
            ],
        },
        {
            "frame": 1,
            "timestamp_seconds": 1.0,
            "detections": [
                Detection(
                    label="boat",
                    category="vessel",
                    confidence=0.87,
                    timestamp_seconds=1.0,
                    bbox=[60.0, 50.0, 360.0, 250.0],
                    track_id=5,
                ),
            ],
        },
    ]

    vessels = intel.process_tracks(
        frames_data,
        video_width=640,
        video_height=480,
        latitude=15.421,
        longitude=73.782,
        operator_ais_status="matched",
    )

    assert len(vessels) == 1
    v = vessels[0]
    assert v.track_id == 5
    assert v.size_category == "large_vessel"
    assert v.people_observed_onboard == 1
    assert v.ais_correlation["status"] == "matched"


def test_api_validation_errors():
    """Verify input validation rejecting bad extensions, empty files, and bad coords."""
    # Bad suffix
    res = client.post(
        "/api/vision/analyze-video",
        files={"file": ("test.txt", io.BytesIO(b"dummy"), "text/plain")},
    )
    assert res.status_code == 415

    # Bad coordinate range
    res = client.post(
        "/api/vision/analyze-video",
        files={"file": ("test.mp4", io.BytesIO(b"test"), "video/mp4")},
        data={"latitude": 120.0, "longitude": 75.0},
    )
    assert res.status_code == 422


def test_full_video_pipeline_synthetic_run():
    """Verify full end-to-end execution on a synthetic MP4 file."""
    # Create small synthetic 6-frame video
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        temp_path = tf.name

    try:
        vw = cv2.VideoWriter(temp_path, cv2.VideoWriter_fourcc(*"mp4v"), 2.0, (160, 120))
        for _ in range(6):
            f = np.zeros((120, 160, 3), dtype=np.uint8)
            f[:, :] = [120, 80, 40]
            vw.write(f)
        vw.release()

        with open(temp_path, "rb") as vf:
            res = client.post(
                "/api/vision/analyze-video",
                files={"file": ("synthetic_patrol.mp4", vf, "video/mp4")},
                data={
                    "confidence_threshold": "0.30",
                    "sample_fps": "2.0",
                    "detection_mode": "naval",
                    "ais_status": "unknown",
                },
            )

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert "evidence_id" in data
        assert "run_id" in data
        assert "threat_assessment" in data
        assert "models_used" in data
        assert "vessel_intelligence" in data
        assert "evidence_thumbnails" in data
        assert data["metrics"]["frames_processed"] >= 3

        # Check annotated video retrieval endpoint
        run_id = data["run_id"]
        v_res = client.get(f"/api/vision/runs/{run_id}/video")
        assert v_res.status_code == 200
        assert v_res.headers["content-type"] == "video/mp4"

    finally:
        Path(temp_path).unlink(missing_ok=True)
