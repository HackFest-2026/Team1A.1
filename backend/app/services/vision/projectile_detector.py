"""Dedicated kinetic projectile and missile trajectory tracker for AEGIS-COP maritime surveillance."""

from __future__ import annotations

import math
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


class MaritimeProjectileDetector:
    """Detects and tracks high-velocity kinetic projectiles, rocket motor plumes,
    and anti-ship missile trajectories across maritime airspace and sea surface.
    """

    def __init__(self):
        self.status = "ready"
        self.active_tracks: List[Dict[str, Any]] = []
        self.next_track_id = 1
        self.events: List[VideoEvent] = []
        self.prev_frame_gray: Optional[np.ndarray] = None
        self.prev_timestamp: float = 0.0

    def reset(self) -> None:
        """Resets tracking state between video runs."""
        self.active_tracks = []
        self.next_track_id = 1
        self.events = []
        self.prev_frame_gray = None
        self.prev_timestamp = 0.0

    def get_provenance(self) -> ModelProvenance:
        return ModelProvenance(
            name="AEGIS Kinetic Projectile & Missile Trajectory Tracker",
            version="1.0-kinetic",
            task="KINETIC_PROJECTILE_AND_MISSILE_TRACKING",
            device="cpu",
            status="ready",
            supported_classes=["missile_trajectory", "anti_ship_missile", "high_speed_projectile"],
            weights_path=None,
            notes=(
                "Multi-frame optical kinetic velocity tracker, radiant rocket motor flare "
                "detection, and directional sea-skimming/ballistic trajectory analyzer."
            ),
        )

    def analyze_frame(
        self,
        frame: np.ndarray,
        timestamp_s: float,
        frame_index: int,
        vessel_bboxes: Optional[List[List[float]]] = None,
        fire_bboxes: Optional[List[List[float]]] = None,
    ) -> List[Detection]:
        """Analyzes a frame for inbound or traversing missiles and high-speed projectiles."""
        h, w = frame.shape[:2]
        detections: List[Detection] = []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        b, g, r = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]

        # Exclude immediate synthetic top and bottom margins (e.g. status bar / tickers)
        # and deep foreground water where waves break right at the camera
        y_min = int(h * 0.025)
        y_max = int(h * 0.78)
        if y_max <= y_min:
            return detections

        sub_gray = gray[y_min:y_max, :]
        sub_r = r[y_min:y_max, :]
        sub_g = g[y_min:y_max, :]
        sub_hsv = hsv[y_min:y_max, :]
        sub_val = sub_hsv[:, :, 2]
        sub_sat = sub_hsv[:, :, 1]

        # 1. Radiant rocket motor flare & incandescent projectile tip
        # High intensity grayscale, bright red/green, high value
        flare_mask = (
            (sub_gray > 195)
            & (sub_r >= 180)
            & (sub_g >= 160)
            & (sub_val > 195)
        ).astype(np.uint8) * 255

        # 2. Linear streak / vapor trail directional morphology (horizontal / shallow angle)
        k_streak = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
        dilated_flare = cv2.morphologyEx(flare_mask, cv2.MORPH_DILATE, k_streak)

        # Vapor condensation trail in horizon / air (light gray or white with low saturation)
        vapor_mask = ((sub_val > 165) & (sub_sat < 50)).astype(np.uint8) * 255
        vapor_streak = cv2.morphologyEx(vapor_mask, cv2.MORPH_OPEN, k_streak)

        combined_candidate = flare_mask | (dilated_flare & vapor_streak)
        k_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        combined_candidate = cv2.morphologyEx(combined_candidate, cv2.MORPH_CLOSE, k_connect)

        cnts, _ = cv2.findContours(combined_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in cnts:
            a = cv2.contourArea(c)
            cx_box, cy_box, bw, bh = cv2.boundingRect(c)
            # Map back to full frame coordinates
            full_y = cy_box + y_min
            aspect = max(bw, bh) / max(1, min(bw, bh))

            # Reject hollow borders / synthetic box outlines
            fill_ratio = a / max(1.0, float(bw * bh))
            if fill_ratio < 0.08 and min(bw, bh) > 30:
                continue

            # Must have elongation or radiant flare presence
            if (aspect >= 2.0 and bw >= 22 and a >= 25) or (a >= 45 and aspect >= 1.5):
                sub_flare_crop = flare_mask[cy_box : cy_box + bh, cx_box : cx_box + bw]
                has_flare = bool(np.any(sub_flare_crop > 0))

                candidates.append({
                    "bbox": [float(cx_box), float(full_y), float(cx_box + bw), float(full_y + bh)],
                    "cx": float(cx_box + bw / 2),
                    "cy": float(full_y + bh / 2),
                    "bw": float(bw),
                    "bh": float(bh),
                    "aspect": float(aspect),
                    "has_flare": has_flare,
                    "area": float(a),
                })

        # Rank candidates prioritising flare presence, aspect ratio, and width
        candidates.sort(
            key=lambda k: (1 if k["has_flare"] else 0, k["aspect"], k["bw"]),
            reverse=True,
        )
        candidates = candidates[:6]

        confirmed_this_frame = []
        updated_tracks = []
        dt = max(0.01, timestamp_s - self.prev_timestamp) if self.prev_timestamp > 0 else 0.33

        for cand in candidates:
            # Check A: Single-frame high-confidence streak (long horizontal trail with radiant flare)
            if cand["aspect"] >= 3.2 and cand["bw"] >= 35 and cand["has_flare"]:
                confirmed_this_frame.append({
                    "track_id": None,
                    "bbox": cand["bbox"],
                    "confidence": 0.88,
                    "speed": 85.0,
                    "bearing": 90.0,
                    "has_flare": True,
                    "notes": "High-aspect kinetic rocket motor trail and radiant flare.",
                })
                continue

            # Check B: Inter-frame velocity matching with previous active tracks
            matched = False
            for trk in self.active_tracks:
                dist = math.hypot(cand["cx"] - trk["cx"], cand["cy"] - trk["cy"])
                speed = dist / dt

                # Valid missile displacement (displaces between 12 and 450 pixels per frame step)
                if 12.0 <= dist <= 450.0 and speed >= 32.0:
                    bearing = float(math.degrees(math.atan2(cand["cy"] - trk["cy"], cand["cx"] - trk["cx"]))) % 360
                    prev_bearing = trk.get("bearing")
                    is_linear = True
                    if prev_bearing is not None:
                        angle_diff = abs((bearing - prev_bearing + 180) % 360 - 180)
                        if angle_diff > 45:
                            is_linear = False

                    if is_linear:
                        matched = True
                        conf = min(0.95, 0.74 + (0.10 if cand["has_flare"] else 0.0) + (0.08 if cand["aspect"] > 2.0 else 0.0))
                        tid = trk["id"]
                        confirmed_this_frame.append({
                            "track_id": tid,
                            "bbox": cand["bbox"],
                            "confidence": conf,
                            "speed": speed,
                            "bearing": bearing,
                            "has_flare": cand["has_flare"],
                            "notes": f"Kinetic projectile track #{tid} (speed: {speed:.1f} px/s, bearing: {bearing:.0f}\u00b0).",
                        })
                        updated_tracks.append({
                            "id": tid,
                            "cx": cand["cx"],
                            "cy": cand["cy"],
                            "t": timestamp_s,
                            "bearing": bearing,
                        })
                        break

            if not matched:
                tid = self.next_track_id
                self.next_track_id += 1
                updated_tracks.append({
                    "id": tid,
                    "cx": cand["cx"],
                    "cy": cand["cy"],
                    "t": timestamp_s,
                    "bearing": None,
                })

        # Update tracking memory (keep most recent tracks)
        self.active_tracks = updated_tracks[:10]
        self.prev_timestamp = timestamp_s
        self.prev_frame_gray = gray

        # Check vessel intercept correlation for confirmed detections
        for det_data in confirmed_this_frame:
            bbox = det_data["bbox"]
            label = "missile_trajectory"
            notes = det_data["notes"]
            confidence = det_data["confidence"]

            if vessel_bboxes:
                for vx1, vy1, vx2, vy2 in vessel_bboxes:
                    # Missile is converging on, in close proximity to, or intersecting vessel corridor
                    bx1, by1, bx2, by2 = bbox
                    x_overlap = not (bx2 < vx1 - 100 or bx1 > vx2 + 100)
                    y_overlap = not (by2 < vy1 - 80 or by1 > vy2 + 80)
                    if x_overlap and y_overlap:
                        label = "anti_ship_missile"
                        confidence = min(0.96, confidence + 0.08)
                        notes = (
                            f"URGENT: Inbound anti-ship missile trajectory converging on vessel hull. "
                            f"{det_data['notes']}"
                        )
                        break

            detections.append(
                Detection(
                    label=label,
                    category=DetectionCategory.PROJECTILE.value,
                    confidence=confidence,
                    timestamp_seconds=timestamp_s,
                    bbox=bbox,
                    track_id=det_data.get("track_id"),
                    model_name="aegis-kinetic-projectile-tracker",
                    model_version="1.0",
                    verification_status=VerificationStatus.DETECTED.value
                    if confidence >= 0.85
                    else VerificationStatus.POSSIBLE_EVENT.value,
                    notes=notes,
                )
            )

        # If high-confidence detections found, record VideoEvent
        if detections:
            max_conf = max(d.confidence for d in detections)
            has_antiship = any(d.label == "anti_ship_missile" for d in detections)
            event_type = "missile_strike_event" if has_antiship else "missile_inbound_alert"

            # Check if this frame is already part of an ongoing event
            if self.events and abs(timestamp_s - self.events[-1].end_time_s) < 2.0:
                self.events[-1].end_time_s = timestamp_s
                self.events[-1].confidence = max(self.events[-1].confidence, max_conf)
            else:
                self.events.append(
                    VideoEvent(
                        event_type=event_type,
                        start_time_s=timestamp_s,
                        end_time_s=timestamp_s,
                        confidence=max_conf,
                        verification_status=VerificationStatus.DETECTED.value,
                        model_name="aegis-kinetic-projectile-tracker",
                        model_version="1.0",
                        limitations=[
                            "Visual kinetic trajectory analysis requires naval CDS / radar correlation.",
                            "Sensor frame rate may limit exact supersonic velocity measurement.",
                        ],
                        notes="Fast kinetic projectile / missile trajectory identified across surveillance horizon.",
                    )
                )

        return detections

    def get_events(self) -> List[VideoEvent]:
        """Returns aggregated missile/projectile video events."""
        return self.events
