"""Suspicious object and coastal safety review component."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.vision.types import (
    Detection,
    DetectionCategory,
    ModelProvenance,
    VerificationStatus,
)


class SuspiciousObjectReviewer:
    """Triage for visible objects warranting human inspection.

    Strict safety invariant: NEVER claims an object is a bomb, IED, or explosive device.
    Labels objects as unverified_suspicious_object for human review.
    """

    def get_provenance(self) -> ModelProvenance:
        return ModelProvenance(
            name="AEGIS Coastal Safety & Suspicious Object Reviewer",
            version="1.0-safety-triage",
            task="SAFETY_REVIEW_TRIAGE",
            device="cpu",
            status="ready",
            supported_classes=[
                "unverified_suspicious_object",
                "unattended_container",
                "unidentified_floating_object",
            ],
            notes=(
                "Flags visible unattended containers, packages, or unusual floating objects "
                "for operator inspection. Explicitly does not classify explosive content."
            ),
        )

    def review_detections(
        self,
        raw_detections: List[Detection],
        vessel_bboxes: Optional[List[List[float]]] = None,
    ) -> List[Detection]:
        """Filters and formats candidate suspicious objects for human inspection."""
        flagged: List[Detection] = []

        container_labels = {"backpack", "handbag", "suitcase"}

        for det in raw_detections:
            # Check containers / packages
            if det.label in container_labels:
                notes = (
                    "Visible container/package observed in surveillance frame. "
                    "Unverified suspicious object — human review required. "
                    "Cannot establish hazard or explosive content."
                )
                flagged.append(
                    Detection(
                        label="unverified_suspicious_object",
                        category=DetectionCategory.SUSPICIOUS_OBJECT.value,
                        confidence=det.confidence,
                        timestamp_seconds=det.timestamp_seconds,
                        bbox=det.bbox,
                        track_id=det.track_id,
                        class_id=det.class_id,
                        model_name="aegis-safety-review",
                        model_version="1.0",
                        verification_status=VerificationStatus.REQUIRES_REVIEW.value,
                        notes=notes,
                    )
                )

        return flagged
