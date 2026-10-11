"""Data models and type definitions for AEGIS-COP Maritime Vision Pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DetectionCategory(str, Enum):
    VESSEL = "vessel"
    PERSON = "person"
    FIRE_SMOKE = "fire_smoke"
    PROJECTILE = "projectile"
    SUSPICIOUS_OBJECT = "suspicious_object"
    COASTAL_OBJECT = "coastal_object"
    UNIDENTIFIED = "unidentified"


class VerificationStatus(str, Enum):
    DETECTED = "detected"
    POSSIBLE_EVENT = "possible_event"
    REQUIRES_REVIEW = "requires_review"
    MODEL_UNAVAILABLE = "model_unavailable"


class ThreatReviewLevel(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    ELEVATED_CONCERN = "ELEVATED_CONCERN"
    URGENT_HUMAN_REVIEW = "URGENT_HUMAN_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class ModelProvenance:
    name: str
    version: str
    task: str
    device: str
    status: str  # "ready", "active", "unavailable", "experimental"
    supported_classes: List[str]
    weights_path: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "task": self.task,
            "device": self.device,
            "status": self.status,
            "supported_classes": self.supported_classes,
            "weights_path": self.weights_path,
            "notes": self.notes,
        }


@dataclass
class Detection:
    label: str
    category: str
    confidence: float
    timestamp_seconds: float
    bbox: List[float]  # [x1, y1, x2, y2]
    track_id: Optional[int] = None
    class_id: Optional[int] = None
    model_name: str = "yolov8n"
    model_version: str = "8.3"
    verification_status: str = "detected"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "timestamp_seconds": round(self.timestamp_seconds, 2),
            "bbox": [round(c, 1) for c in self.bbox],
            "track_id": self.track_id,
            "class_id": self.class_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "verification_status": self.verification_status,
            "notes": self.notes,
        }


@dataclass
class VideoEvent:
    event_type: str  # "possible_explosion_event", "fire_incident", "smoke_plume", "vessel_exhaust"
    start_time_s: float
    end_time_s: float
    confidence: float
    verification_status: str
    model_name: str
    model_version: str
    evidence_frames: List[Dict[str, Any]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "start_time_s": round(self.start_time_s, 2),
            "end_time_s": round(self.end_time_s, 2),
            "confidence": round(self.confidence, 4),
            "verification_status": self.verification_status,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "evidence_frames": self.evidence_frames,
            "limitations": self.limitations,
            "notes": self.notes,
        }


@dataclass
class TrackedVessel:
    track_id: int
    vessel_class: str
    size_category: str  # "small_craft", "large_vessel", "uncalibrated"
    confidence: float
    first_seen_s: float
    last_seen_s: float
    track_history: List[Dict[str, Any]] = field(default_factory=list)
    speed_proxy_pixels_sec: float = 0.0
    course_bearing_deg: Optional[float] = None
    people_observed_onboard: int = 0
    ais_correlation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "vessel_class": self.vessel_class,
            "size_category": self.size_category,
            "confidence": round(self.confidence, 4),
            "first_seen_s": round(self.first_seen_s, 2),
            "last_seen_s": round(self.last_seen_s, 2),
            "track_history_length": len(self.track_history),
            "speed_proxy_pixels_sec": round(self.speed_proxy_pixels_sec, 2),
            "course_bearing_deg": round(self.course_bearing_deg, 1) if self.course_bearing_deg is not None else None,
            "people_observed_onboard": self.people_observed_onboard,
            "ais_correlation": self.ais_correlation,
        }
