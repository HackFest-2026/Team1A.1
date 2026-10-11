"""Dedicated fire and smoke analysis component for maritime and coastal surveillance."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.services.vision.types import (
    Detection,
    DetectionCategory,
    ModelProvenance,
    VerificationStatus,
    VideoEvent,
)


def _merge_overlapping_boxes(boxes: List[List[float]], iou_threshold: float = 0.20, proximity: float = 15.0) -> List[List[float]]:
    """Merges overlapping or tightly adjacent bounding boxes."""
    if not boxes:
        return []

    merged: List[List[float]] = []
    candidates = [list(b) for b in boxes]

    while candidates:
        curr = candidates.pop(0)
        has_merged = True
        while has_merged:
            has_merged = False
            remaining = []
            for other in candidates:
                # Check proximity / intersection
                cx1 = max(curr[0] - proximity, other[0] - proximity)
                cy1 = max(curr[1] - proximity, other[1] - proximity)
                cx2 = min(curr[2] + proximity, other[2] + proximity)
                cy2 = min(curr[3] + proximity, other[3] + proximity)

                if cx2 >= cx1 and cy2 >= cy1:
                    # Merge into bounding envelope
                    curr[0] = min(curr[0], other[0])
                    curr[1] = min(curr[1], other[1])
                    curr[2] = max(curr[2], other[2])
                    curr[3] = max(curr[3], other[3])
                    has_merged = True
                else:
                    remaining.append(other)
            candidates = remaining
        merged.append(curr)

    return merged


class FireSmokeAnalyzer:
    """Specialist analyzer for fire, smoke, and vessel exhaust plumes.

    Distinguishes genuine fire/flame from sunsets, orange sky, and vessel engine smoke.
    Suppresses ocean water wave ripples from false smoke alerts.
    """

    def __init__(self, custom_weights_path: Optional[str] = None):
        self.custom_weights = custom_weights_path or os.getenv("AEGIS_FIRE_SMOKE_MODEL")
        self.specialist_yolo = None
        self.status = "ready"
        self._init_model()

    def _init_model(self) -> None:
        if self.custom_weights and Path(self.custom_weights).is_file():
            try:
                from ultralytics import YOLO

                self.specialist_yolo = YOLO(self.custom_weights)
                self.status = "active_custom_model"
            except Exception:
                self.specialist_yolo = None
                self.status = "ready"
        else:
            self.specialist_yolo = None
            self.status = "ready"

    def get_provenance(self) -> ModelProvenance:
        if self.specialist_yolo is not None:
            return ModelProvenance(
                name="Dedicated Fire-Smoke YOLO",
                version="1.0-custom",
                task="FIRE_AND_SMOKE_DETECTION",
                device="cpu",
                status="ready",
                supported_classes=["fire", "smoke"],
                weights_path=self.custom_weights,
                notes="Custom fine-tuned weights for fire and smoke segmentation.",
            )
        return ModelProvenance(
            name="AEGIS Spatiotemporal Fire & Smoke Analyzer",
            version="1.0-spectral",
            task="FIRE_AND_SMOKE_ANALYSIS",
            device="cpu",
            status="ready",
            supported_classes=["fire", "smoke", "vessel_exhaust_smoke"],
            weights_path=None,
            notes=(
                "Dual-spectral chromatic & incandescent plume dispersion analyzer with "
                "sunset rejection, ocean wave suppression, and vessel exhaust classification."
            ),
        )

    def analyze_frame(
        self,
        frame: np.ndarray,
        timestamp_s: float,
        vessel_bboxes: Optional[List[List[float]]] = None,
    ) -> List[Detection]:
        """Analyzes a frame for fire, smoke, or vessel exhaust plumes."""
        h, w = frame.shape[:2]
        detections: List[Detection] = []

        # If a specialist YOLO weights file is active, run it
        if self.specialist_yolo is not None:
            res = self.specialist_yolo(frame, verbose=False, conf=0.35)[0]
            if res.boxes is not None:
                for idx in range(len(res.boxes)):
                    c_id = int(res.boxes.cls[idx].item())
                    label = str(res.names.get(c_id, c_id)).lower()
                    conf = float(res.boxes.conf[idx].item())
                    xyxy = [float(v) for v in res.boxes.xyxy[idx].tolist()]
                    detections.append(
                        Detection(
                            label=label,
                            category=DetectionCategory.FIRE_SMOKE.value,
                            confidence=conf,
                            timestamp_seconds=timestamp_s,
                            bbox=xyxy,
                            model_name="fire-smoke-specialist",
                            model_version="1.0",
                            verification_status=VerificationStatus.DETECTED.value,
                            notes=f"Detected by specialist {label} model.",
                        )
                    )
            return detections

        # Built-in Spectral & Morphological Plume Analysis
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        b, g, r = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]

        # 1. Flame mask:
        # A. Chromatic flame (orange-yellow-red): H in [0, 34] or [168, 180], S >= 30, V >= 140
        flame1 = cv2.inRange(hsv, np.array([0, 30, 140]), np.array([34, 255, 255]))
        flame2 = cv2.inRange(hsv, np.array([168, 30, 140]), np.array([180, 255, 255]))
        hsv_flame = flame1 | flame2

        # B. RGB spectral dominance rule (Celik & Demirel adaptation for maritime lighting)
        # In combustion: R >= 165, G >= 75, R > B + 20
        rgb_flame = ((r >= 165) & (g >= 75) & (r > b + 20)).astype(np.uint8) * 255

        # C. Incandescent blast core / white-yellow plasma core (cameras wash out hot flames)
        blast_core = (
            (r >= 215)
            & (g >= 175)
            & (r >= b + 10)
            & (hsv[:, :, 2] >= 215)
        ).astype(np.uint8) * 255

        mask_flame = (hsv_flame & rgb_flame) | blast_core

        # Morphological operations to coalesce explosion fireballs
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        mask_flame = cv2.morphologyEx(mask_flame, cv2.MORPH_CLOSE, kernel_close)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask_flame = cv2.morphologyEx(mask_flame, cv2.MORPH_OPEN, kernel_open)

        # 2. Smoke mask: Low saturation, dark-to-medium grey or billowing plume
        # Saturation < 55, Value between 30 and 160 (dense black/grey smoke)
        lower_smoke = np.array([0, 0, 30])
        upper_smoke = np.array([180, 55, 160])
        mask_smoke = cv2.inRange(hsv, lower_smoke, upper_smoke)
        kernel_smoke_open = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        mask_smoke = cv2.morphologyEx(mask_smoke, cv2.MORPH_OPEN, kernel_smoke_open)

        # Anti-sunset filter: Only reject if the upper horizon has a wide uniform band
        is_sunset = False
        upper_third = hsv[: int(h * 0.30), :]
        avg_hue = float(np.mean(upper_third[:, :, 0]))
        avg_sat = float(np.mean(upper_third[:, :, 1]))
        if 8 <= avg_hue <= 28 and avg_sat > 75:
            is_sunset = True

        # Process Flame Contours
        flame_contours, _ = cv2.findContours(
            mask_flame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        raw_flame_boxes: List[List[float]] = []
        min_flame_area = max(16.0, (w * h) * 0.00008)  # Scalable threshold

        for cnt in flame_contours:
            area = cv2.contourArea(cnt)
            if area >= min_flame_area:
                x, y, bw, bh = cv2.boundingRect(cnt)
                # Reject hollow artificial graphic borders / hollow box outlines
                fill_ratio = area / max(1.0, float(bw * bh))
                if fill_ratio < 0.08 and min(bw, bh) > 30:
                    continue
                # Broad sunset rejection (only suppress broad horizontal bands spanning > 60% of frame)
                if is_sunset and (y + bh / 2) < h * 0.30 and bw > w * 0.60:
                    continue
                raw_flame_boxes.append([float(x), float(y), float(x + bw), float(y + bh)])

        # Merge fragmented flame boxes into cohesive fireball detections
        merged_flame_boxes = _merge_overlapping_boxes(raw_flame_boxes, proximity=20.0)

        for fx1, fy1, fx2, fy2 in merged_flame_boxes:
            box_area = (fx2 - fx1) * (fy2 - fy1)
            confidence = min(0.96, 0.65 + (box_area / (w * h)) * 10)
            detections.append(
                Detection(
                    label="fire",
                    category=DetectionCategory.FIRE_SMOKE.value,
                    confidence=confidence,
                    timestamp_seconds=timestamp_s,
                    bbox=[fx1, fy1, fx2, fy2],
                    model_name="aegis-spectral-fire",
                    model_version="1.0",
                    verification_status=VerificationStatus.DETECTED.value
                    if confidence >= 0.70
                    else VerificationStatus.POSSIBLE_EVENT.value,
                    notes="High-temperature combustion core / active flame detected.",
                )
            )

        # Process Smoke / Plume Contours
        smoke_contours, _ = cv2.findContours(
            mask_smoke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        min_smoke_area = (w * h) * 0.0025  # Substantial plume area
        raw_smoke_candidates = []

        for cnt in smoke_contours:
            area = cv2.contourArea(cnt)
            if area > min_smoke_area:
                x, y, bw, bh = cv2.boundingRect(cnt)
                aspect = float(bw) / float(max(1, bh))

                # WAVE RIPPLE FILTER:
                # Open water surface ripples form thin horizontal bands (aspect > 4.5 and bh < 30)
                # in the lower open ocean away from any vessel or combustion source.
                is_water_ripple = (aspect > 4.2 and bh < 32 and y > h * 0.50)
                if is_water_ripple:
                    continue

                raw_smoke_candidates.append([float(x), float(y), float(x + bw), float(y + bh)])

        # Merge overlapping/fragmented smoke plumes into unified plume bounds
        merged_smoke_boxes = _merge_overlapping_boxes(raw_smoke_candidates, proximity=30.0)

        for sx1, sy1, sx2, sy2 in merged_smoke_boxes:
            bw = sx2 - sx1
            bh = sy2 - sy1
            cx = sx1 + bw / 2.0
            cy = sy1 + bh / 2.0
            area = bw * bh

            # Check if this plume is directly associated with a detected vessel
            is_vessel_exhaust = False
            associated_vessel = False
            if vessel_bboxes:
                for vx1, vy1, vx2, vy2 in vessel_bboxes:
                    # Plume is in upper vicinity or directly above the vessel hull
                    if (vx1 - bw * 0.4) <= cx <= (vx2 + bw * 0.4) and (sy1 <= vy2):
                        associated_vessel = True
                        # If no flame core detected inside this vessel's bounds, classify as exhaust
                        has_flame_core = any(
                            (d.label == "fire" and not (d.bbox[2] < vx1 or d.bbox[0] > vx2))
                            for d in detections
                        )
                        if not has_flame_core:
                            is_vessel_exhaust = True
                        break

            # Check if this smoke plume billows directly from a detected fire
            near_fire = any(
                (d.label == "fire" and not (d.bbox[2] < sx1 - 40 or d.bbox[0] > sx2 + 40 or d.bbox[3] < sy1 - 40 or d.bbox[1] > sy2 + 40))
                for d in detections
            )

            if is_vessel_exhaust:
                detections.append(
                    Detection(
                        label="vessel_exhaust_smoke",
                        category=DetectionCategory.FIRE_SMOKE.value,
                        confidence=0.78,
                        timestamp_seconds=timestamp_s,
                        bbox=[sx1, sy1, sx2, sy2],
                        model_name="aegis-plume-analyzer",
                        model_version="1.0",
                        verification_status=VerificationStatus.REQUIRES_REVIEW.value,
                        notes="Engine exhaust / stack emission observed above vessel hull. Not classified as active fire.",
                    )
                )
            else:
                # Plumes near fire or billowing into the sky
                confidence = min(0.88, 0.55 + (area / (w * h)) * 5)
                note = "Dense combustion smoke plume billowing from fire source." if near_fire else "Atmospheric smoke plume detected."
                detections.append(
                    Detection(
                        label="smoke",
                        category=DetectionCategory.FIRE_SMOKE.value,
                        confidence=confidence,
                        timestamp_seconds=timestamp_s,
                        bbox=[sx1, sy1, sx2, sy2],
                        model_name="aegis-plume-analyzer",
                        model_version="1.0",
                        verification_status=VerificationStatus.DETECTED.value
                        if near_fire or confidence >= 0.70
                        else VerificationStatus.POSSIBLE_EVENT.value,
                        notes=note,
                    )
                )

        return detections
