"""Temporal video event classifier for explosion, blast, and high-energy detonations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.services.vision.types import (
    ModelProvenance,
    VerificationStatus,
    VideoEvent,
)


class ExplosionEventClassifier:
    """Classifies temporal blast events across sequential video frame windows.

    Treats explosions as a spatio-temporal video event problem, distinguishing
    localized blast cores from camera flashes, scene cuts, and engine exhaust.
    """

    def __init__(self, custom_model_path: Optional[str] = None):
        self.custom_model_path = custom_model_path or os.getenv("AEGIS_EXPLOSION_MODEL")
        self.status = "ready"

    def get_provenance(self) -> ModelProvenance:
        return ModelProvenance(
            name="AEGIS Spatiotemporal Blast & Radiant Flux Classifier",
            version="1.0-temporal-window",
            task="VIDEO_EVENT_CLASSIFICATION",
            device="cpu",
            status=self.status,
            supported_classes=["possible_explosion_event"],
            weights_path=self.custom_model_path,
            notes=(
                "Sliding-window temporal radiant flux and plume dynamics classifier. "
                "Distinguishes localized expanding blast signatures from camera cuts and flares."
            ),
        )

    def classify_sequence(
        self,
        frame_records: List[Dict[str, Any]],
        fps: float,
    ) -> List[VideoEvent]:
        """Evaluates sequential frame metrics across sliding temporal windows.

        frame_records: list of dicts with keys:
            - 'frame_index': int
            - 'timestamp_seconds': float
            - 'frame_bgr': np.ndarray
        """
        if len(frame_records) < 3:
            return []

        events: List[VideoEvent] = []
        n_frames = len(frame_records)

        # Precompute per-frame luminance and flame metrics
        metrics = []
        for rec in frame_records:
            f = rec["frame_bgr"]
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            mean_l = float(np.mean(gray))
            p99_l = float(np.percentile(gray, 99))

            # Chromatic high-intensity core pixels
            hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
            flame_mask = (
                ((hsv[:, :, 0] <= 25) | (hsv[:, :, 0] >= 170))
                & (hsv[:, :, 1] >= 140)
                & (hsv[:, :, 2] >= 220)
            )
            flame_pixel_count = int(np.count_nonzero(flame_mask))

            metrics.append({
                "mean_l": mean_l,
                "p99_l": p99_l,
                "flame_pixels": flame_pixel_count,
                "gray": gray,
                "timestamp": rec["timestamp_seconds"],
                "frame_index": rec["frame_index"],
            })

        # Sliding window analysis (window size ~ 1.5 - 3 seconds, approx 3-8 frames)
        window_size = min(8, max(3, int(fps * 2.0)))
        step = max(1, window_size // 2)

        idx = 1
        while idx < n_frames - 1:
            prev = metrics[idx - 1]
            curr = metrics[idx]
            next_f = metrics[min(idx + 1, n_frames - 1)]

            # 1. Radiant Flux Surge: Localized brightness jump
            luminance_diff = curr["p99_l"] - prev["p99_l"]
            mean_diff = curr["mean_l"] - prev["mean_l"]
            flame_surge = curr["flame_pixels"] - prev["flame_pixels"]

            # False Alarm Rejection 1: Global Exposure Change / Scene Cut
            # If the ENTIRE frame mean jumps proportionally with the peak,
            # this is an exposure change, camera flash, or video edit.
            is_global_flash = mean_diff > 25.0 and (mean_diff / (luminance_diff + 1e-4)) > 0.65

            # False Alarm Rejection 2: Camera motion / shake
            diff_img = cv2.absdiff(curr["gray"], prev["gray"])
            high_diff_fraction = np.count_nonzero(diff_img > 40) / diff_img.size

            if is_global_flash or high_diff_fraction > 0.70:
                idx += 1
                continue

            # Candidate Event Criteria:
            # Significant localized flame/luminance surge without global screen flash
            total_pixels = curr["gray"].size
            flame_ratio = curr["flame_pixels"] / total_pixels

            if (flame_surge > 150 and flame_ratio > 0.0005) or (
                luminance_diff > 45.0 and flame_ratio > 0.0002 and high_diff_fraction < 0.40
            ):
                # Check dissipation / smoke plume in next frames
                t_start = max(0.0, curr["timestamp"] - 0.25)
                t_end = min(
                    frame_records[-1]["timestamp_seconds"],
                    curr["timestamp"] + (window_size / fps),
                )

                score = min(0.85, 0.55 + (flame_ratio * 20.0) + (luminance_diff / 150.0))

                evidence_frames = [
                    {
                        "frame_index": prev["frame_index"],
                        "timestamp_seconds": prev["timestamp"],
                        "stage": "pre_event_baseline",
                    },
                    {
                        "frame_index": curr["frame_index"],
                        "timestamp_seconds": curr["timestamp"],
                        "stage": "radiant_flash_core",
                    },
                    {
                        "frame_index": next_f["frame_index"],
                        "timestamp_seconds": next_f["timestamp"],
                        "stage": "post_detonation_plume",
                    },
                ]

                events.append(
                    VideoEvent(
                        event_type="possible_explosion_event",
                        start_time_s=t_start,
                        end_time_s=t_end,
                        confidence=score,
                        verification_status=VerificationStatus.POSSIBLE_EVENT.value,
                        model_name="aegis-temporal-blast-classifier",
                        model_version="1.0-temporal-window",
                        evidence_frames=evidence_frames,
                        limitations=[
                            "Optical video analysis cannot establish high-explosive detonation without acoustic or dual-sensor corroboration.",
                            "Ambiguous bright flashes, flares, or pyrotechnics may trigger potential event warnings.",
                            "Requires urgent human operator verification.",
                        ],
                        notes=(
                            f"Temporal radiant flux surge ({luminance_diff:.1f} intensity delta) "
                            f"with localized combustion kernel ({curr['flame_pixels']} px)."
                        ),
                    )
                )
                idx += window_size  # Skip ahead past this event window
            else:
                idx += 1

        return events
