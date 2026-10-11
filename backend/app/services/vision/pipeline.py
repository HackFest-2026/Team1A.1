"""Unified Maritime Vision Pipeline for AEGIS-COP Coastal Surveillance."""

from __future__ import annotations

import os
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.services.threat_assessment import assess_potential_threat
from app.services.vision.explosion_classifier import ExplosionEventClassifier
from app.services.vision.fire_smoke import FireSmokeAnalyzer
from app.services.vision.object_detector import (
    NAVAL_VESSEL_CLASSES,
    MaritimeObjectDetector,
)
from app.services.vision.projectile_detector import MaritimeProjectileDetector
from app.services.vision.suspicious_objects import SuspiciousObjectReviewer
from app.services.vision.types import (
    Detection,
    DetectionCategory,
    ModelProvenance,
    VerificationStatus,
    VideoEvent,
)
from app.services.vision.vessel_intelligence import MaritimeVesselIntelligence

ROOT_DIR = Path(__file__).resolve().parents[4]
RUN_DIR = ROOT_DIR / "data" / "vision_runs"


class MaritimeVisionPipeline:
    """Modular multi-model vision pipeline for maritime surveillance."""

    def __init__(self):
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        self.detector = MaritimeObjectDetector()
        self.fire_smoke_analyzer = FireSmokeAnalyzer()
        self.projectile_detector = MaritimeProjectileDetector()
        self.explosion_classifier = ExplosionEventClassifier()
        self.suspicious_reviewer = SuspiciousObjectReviewer()
        self.vessel_intel = MaritimeVesselIntelligence()

    def get_models_provenance(self) -> List[Dict[str, Any]]:
        models: List[ModelProvenance] = []
        models.extend(self.detector.get_provenance())
        models.append(self.fire_smoke_analyzer.get_provenance())
        models.append(self.projectile_detector.get_provenance())
        models.append(self.explosion_classifier.get_provenance())
        models.append(self.suspicious_reviewer.get_provenance())
        models.append(self.vessel_intel.get_provenance())
        return [m.to_dict() for m in models]

    def process_video(
        self,
        input_video_path: Path,
        original_filename: str,
        *,
        confidence_threshold: float = 0.40,
        sample_fps: float = 3.0,
        detection_mode: str = "naval",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        restricted_zone_entry: bool = False,
        ais_status: str = "unknown",
        unusual_behavior_observed: bool = False,
        near_protected_asset: bool = False,
    ) -> Dict[str, Any]:
        """Executes full multi-model surveillance pipeline on the provided video."""
        run_id = uuid.uuid4().hex
        output_video_path = RUN_DIR / f"{run_id}_annotated.mp4"

        capture = cv2.VideoCapture(str(input_video_path))
        if not capture.isOpened():
            capture.release()
            raise ValueError("Could not decode video file.")

        source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration_seconds = frame_count / source_fps if source_fps > 0 else 0

        stride = max(1, round(source_fps / sample_fps))
        effective_fps = source_fps / stride

        writer = None
        frame_records = []
        processed_frames_data = []
        frames_processed = 0
        frame_index = 0

        frame_detection_counts = Counter()
        unique_tracks = set()
        untracked_counts = Counter()
        all_detections_flat: List[Detection] = []
        evidence_thumbnails: List[Dict[str, Any]] = []

        started = time.perf_counter()
        self.projectile_detector.reset()

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if frame_index % stride == 0:
                    t_sec = frame_index / source_fps
                    frame_copy = frame.copy()

                    # 1. Primary YOLO Object Tracking
                    raw_dets, _ = self.detector.track_frame(
                        frame,
                        confidence_threshold=confidence_threshold,
                        detection_mode=detection_mode,
                    )

                    # Update timestamps
                    for d in raw_dets:
                        d.timestamp_seconds = t_sec

                    # Extract vessel bboxes for smoke/exhaust and missile intercept association
                    vessel_boxes = [
                        d.bbox for d in raw_dets if d.category == DetectionCategory.VESSEL.value
                    ]

                    # 2. Fire and Smoke Analysis
                    fs_dets = self.fire_smoke_analyzer.analyze_frame(
                        frame, t_sec, vessel_bboxes=vessel_boxes
                    )

                    # 3. Kinetic Projectile & Missile Trajectory Tracking
                    fire_boxes = [d.bbox for d in fs_dets if d.label == "fire"]
                    proj_dets = self.projectile_detector.analyze_frame(
                        frame,
                        t_sec,
                        frame_index,
                        vessel_bboxes=vessel_boxes,
                        fire_bboxes=fire_boxes,
                    )

                    # 4. Suspicious Object Review
                    suspicious_dets = self.suspicious_reviewer.review_detections(
                        raw_dets, vessel_bboxes=vessel_boxes
                    )

                    # Combine all detections for this frame
                    # Filter out raw containers that were converted to suspicious objects
                    non_container_raw = [
                        d for d in raw_dets if d.category != DetectionCategory.SUSPICIOUS_OBJECT.value
                    ]
                    current_frame_dets = non_container_raw + fs_dets + proj_dets + suspicious_dets

                    # Update counters
                    for d in current_frame_dets:
                        label = d.label
                        frame_detection_counts[label] += 1
                        if d.track_id is not None:
                            unique_tracks.add((label, d.track_id))
                        else:
                            untracked_counts[label] += 1
                        all_detections_flat.append(d)

                    # Draw Tactical Annotations
                    annotated = self._render_annotations(
                        frame_copy, current_frame_dets, t_sec, run_id
                    )

                    if writer is None:
                        out_h, out_w = annotated.shape[:2]
                        writer = cv2.VideoWriter(
                            str(output_video_path),
                            cv2.VideoWriter_fourcc(*"mp4v"),
                            max(0.25, effective_fps),
                            (out_w, out_h),
                        )
                        if not writer.isOpened():
                            raise RuntimeError("Could not initialize video writer.")

                    writer.write(annotated)

                    # Save evidence thumbnail for significant frames (up to 8)
                    has_significant = any(
                        d.category in {"fire_smoke", "projectile", "suspicious_object"}
                        or d.label in {"fire", "missile_trajectory", "anti_ship_missile"}
                        or (d.category == "vessel" and frames_processed % 15 == 0)
                        for d in current_frame_dets
                    )
                    if (has_significant or frames_processed == 0) and len(evidence_thumbnails) < 8:
                        thumb_name = f"{run_id}_thumb_{frames_processed}.jpg"
                        thumb_path = RUN_DIR / thumb_name
                        cv2.imwrite(str(thumb_path), annotated)
                        evidence_thumbnails.append({
                            "thumbnail_name": thumb_name,
                            "url": f"/api/vision/runs/{run_id}/frames/{thumb_name}",
                            "timestamp_seconds": round(t_sec, 2),
                            "frame_index": frame_index,
                            "labels": [d.label for d in current_frame_dets],
                        })

                    processed_frames_data.append({
                        "frame": frame_index,
                        "timestamp_seconds": round(t_sec, 2),
                        "detections": [d.to_dict() for d in current_frame_dets],
                    })

                    frame_records.append({
                        "frame_index": frame_index,
                        "timestamp_seconds": t_sec,
                        "frame_bgr": frame,
                    })

                    frames_processed += 1

                frame_index += 1

        finally:
            capture.release()
            if writer is not None:
                writer.release()

        if frames_processed == 0 or not output_video_path.exists():
            raise ValueError("No decodable frames were found in video.")

        elapsed = time.perf_counter() - started

        # 4. Temporal Explosion / Blast & Missile Event Aggregation
        explosion_events = self.explosion_classifier.classify_sequence(
            frame_records, fps=effective_fps
        )
        projectile_events = self.projectile_detector.get_events()
        all_events = explosion_events + projectile_events

        # 5. Vessel Intelligence Aggregation & AIS Correlation
        vessel_intelligence = self.vessel_intel.process_tracks(
            processed_frames_data,
            video_width=width,
            video_height=height,
            latitude=latitude,
            longitude=longitude,
            operator_ais_status=ais_status,
        )

        # Count unique objects
        unique_object_counts = Counter(label for label, _ in unique_tracks)
        unique_object_counts.update(untracked_counts)
        classes_seen = sorted(frame_detection_counts.keys())
        detection_total = sum(frame_detection_counts.values())

        # Compile suspicious objects list
        suspicious_objects = [
            d.to_dict()
            for d in all_detections_flat
            if d.category == DetectionCategory.SUSPICIOUS_OBJECT.value
        ]

        # Compile fire & smoke data
        fire_smoke_events = [
            ev.to_dict()
            for ev in explosion_events
        ]
        fire_detected = any(d.label == "fire" for d in all_detections_flat)
        smoke_detected = any("smoke" in d.label for d in all_detections_flat)
        projectiles_detected = any(d.category == DetectionCategory.PROJECTILE.value for d in all_detections_flat)

        # 6. Comprehensive Threat & Review Assessment (Phase 5)
        threat_assessment = assess_potential_threat(
            dict(unique_object_counts),
            restricted_zone_entry=restricted_zone_entry,
            ais_status=ais_status,
            unusual_behavior_observed=unusual_behavior_observed,
            near_protected_asset=near_protected_asset,
            events=[ev.to_dict() for ev in all_events],
            vessel_intelligence=[v.to_dict() for v in vessel_intelligence],
            suspicious_objects=suspicious_objects,
            fire_smoke_data={
                "fire_detected": fire_detected,
                "smoke_detected": smoke_detected,
                "exhaust_smoke_only": not fire_detected and smoke_detected,
            },
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "review_status": "UNVERIFIED_REQUIRES_HUMAN_REVIEW",
            "model": self.detector.weights_path,
            "detection_mode": detection_mode,
            "source_video": original_filename,
            "models_used": self.get_models_provenance(),
            "video": {
                "width": width,
                "height": height,
                "source_fps": round(source_fps, 2),
                "duration_seconds": round(duration_seconds, 2),
                "file_size_bytes": os.path.getsize(str(input_video_path))
                if input_video_path.exists() else 0,
            },
            "metrics": {
                "frames_processed": frames_processed,
                "detections_total": detection_total,
                "detections_by_class_per_frame": dict(frame_detection_counts),
                "unique_object_counts_approx": dict(unique_object_counts),
                "unique_classes": classes_seen,
                "processing_seconds": round(elapsed, 3),
                "analysis_fps": round(frames_processed / elapsed, 2)
                if elapsed > 0 else 0,
                "sampled_fps": round(effective_fps, 2),
            },
            "frames": processed_frames_data[:500],
            "events": [ev.to_dict() for ev in all_events],
            "projectile_events": [ev.to_dict() for ev in projectile_events],
            "projectiles_detected": projectiles_detected,
            "vessel_intelligence": [v.to_dict() for v in vessel_intelligence],
            "suspicious_objects": suspicious_objects[:50],
            "fire_smoke_analysis": {
                "fire_detected": fire_detected,
                "smoke_detected": smoke_detected,
                "plume_events": fire_smoke_events,
            },
            "evidence_thumbnails": evidence_thumbnails,
            "threat_assessment": threat_assessment,
            "annotated_video_url": f"/api/vision/runs/{run_id}/video",
            "note": (
                "Multi-model maritime vision pipeline. Visual detections require "
                "human operator verification. AIS absence does not prove hostile intent."
            ),
        }

    def _render_annotations(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        t_sec: float,
        run_id: str,
    ) -> np.ndarray:
        """Renders color-coded tactical overlays on video frame."""
        # Color mapping: BGR
        palette = {
            DetectionCategory.VESSEL.value: (0, 220, 110),        # Vibrant Emerald Green
            DetectionCategory.PERSON.value: (255, 180, 0),        # Cyan / Blue
            DetectionCategory.FIRE_SMOKE.value: (0, 140, 255),    # Orange for smoke
            DetectionCategory.PROJECTILE.value: (0, 90, 255),     # Saffron-Red for kinetic projectiles
            DetectionCategory.SUSPICIOUS_OBJECT.value: (0, 215, 255), # Amber
            DetectionCategory.COASTAL_OBJECT.value: (200, 200, 200),
            "fire": (0, 0, 245),                                  # Crimson Red for fire
            "vessel_exhaust_smoke": (0, 165, 255),                # Dark Orange for exhaust
            "missile_trajectory": (0, 90, 255),                   # Saffron-Red
            "anti_ship_missile": (0, 25, 255),                    # High-Alert Red
        }

        h, w = frame.shape[:2]

        for d in detections:
            x1, y1, x2, y2 = [int(v) for v in d.bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)

            color = palette.get(d.label, palette.get(d.category, (0, 255, 0)))

            # Draw bounding box (thicker for missile/anti-ship missile)
            thickness = 3 if d.category == DetectionCategory.PROJECTILE.value or d.label == "fire" else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Draw tactical corner accents for missiles
            if d.category == DetectionCategory.PROJECTILE.value or d.label in {"missile_trajectory", "anti_ship_missile"}:
                corner_len = min(15, (x2 - x1) // 3)
                cv2.line(frame, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), 2)
                cv2.line(frame, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), 2)
                cv2.line(frame, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)
                cv2.line(frame, (x2, y2), (x2, y2 - corner_len), (255, 255, 255), 2)

            # Build label text
            text_parts = []
            if d.track_id is not None:
                text_parts.append(f"id:{d.track_id}")
            text_parts.append(d.label.upper())
            text_parts.append(f"{d.confidence:.2f}")
            label_text = " ".join(text_parts)

            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
            cv2.rectangle(
                frame,
                (x1, max(0, y1 - th - 6)),
                (x1 + tw + 6, max(th + 6, y1)),
                color,
                -1,
            )
            cv2.putText(
                frame,
                label_text,
                (x1 + 3, max(th + 2, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (0, 0, 0) if color != (0, 0, 245) else (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Tactical HUD header
        has_missile = any(d.category == DetectionCategory.PROJECTILE.value or d.label in {"missile_trajectory", "anti_ship_missile"} for d in detections)
        has_fire = any(d.label == "fire" for d in detections)

        alert_tag = ""
        if has_missile:
            alert_tag = " | [CRITICAL: MISSILE TRAJECTORY DETECTED]"
        elif has_fire:
            alert_tag = " | [COMBAT: ACTIVE COMBUSTION / FIRE DETECTED]"

        hud_text = f"AEGIS-COP VISION | T+{t_sec:.1f}s | DETECTIONS: {len(detections)}{alert_tag}"
        hud_bg = (10, 15, 20)
        hud_fg = (0, 40, 255) if has_missile else ((0, 140, 255) if has_fire else (0, 230, 150))

        cv2.rectangle(frame, (10, 10), (w - 10, 36), hud_bg, -1)
        cv2.putText(
            frame,
            hud_text,
            (20, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            hud_fg,
            1,
            cv2.LINE_AA,
        )

        return frame


vision_pipeline = MaritimeVisionPipeline()
