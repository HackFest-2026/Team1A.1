"""General and maritime object detector using YOLO and ByteTrack."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from app.services.vision.types import (
    Detection,
    DetectionCategory,
    ModelProvenance,
    VerificationStatus,
)

# Standard COCO classes
# 0: person, 8: boat, 24: backpack, 26: handbag, 28: suitcase
NAVAL_VESSEL_CLASSES = [8]
MARITIME_EXPANDED_CLASSES = [0, 8, 24, 26, 28]

CONTAINER_CLASSES = {24: "backpack", 26: "handbag", 28: "suitcase"}


class MaritimeObjectDetector:
    """Manages object detection and multi-object tracking for coastal surveillance."""

    def __init__(self, weights_path: Optional[str] = None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.weights_path = self._resolve_weights(weights_path)
        self.model = None
        self.yolo_world_model = None
        self.yolo_world_status = "unavailable"
        self._load_models()

    def _resolve_weights(self, custom_path: Optional[str]) -> str:
        if custom_path and Path(custom_path).is_file():
            return str(Path(custom_path).resolve())

        env_model = os.getenv("AEGIS_YOLO_MODEL")
        if env_model and Path(env_model).is_file():
            return str(Path(env_model).resolve())

        root_dir = Path(__file__).resolve().parents[4]
        candidate_root = root_dir / "yolov8n.pt"
        if candidate_root.is_file():
            return str(candidate_root)

        backend_dir = root_dir / "backend" / "yolov8n.pt"
        if backend_dir.is_file():
            return str(backend_dir)

        return "yolov8n.pt"

    def _load_models(self) -> None:
        from ultralytics import YOLO

        try:
            self.model = YOLO(self.weights_path)
            # Move to device if necessary
            if self.device == "cuda":
                self.model.to("cuda")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load primary YOLO detector from {self.weights_path}: {exc}"
            ) from exc

        # Check for open-vocabulary YOLO-World
        world_env = os.getenv("AEGIS_YOLOWORLD_MODEL", "yolov8s-world.pt")
        world_path = Path(world_env)
        root_dir = Path(__file__).resolve().parents[4]
        if not world_path.is_file():
            world_path = root_dir / world_env
        if not world_path.is_file():
            world_path = root_dir / "backend" / world_env

        if world_path.is_file():
            try:
                from ultralytics import YOLOWorld
                self.yolo_world_model = YOLOWorld(str(world_path))
                self.yolo_world_status = "ready"
            except Exception:
                self.yolo_world_model = None
                self.yolo_world_status = "unavailable"
        else:
            self.yolo_world_status = "unavailable"

    def get_provenance(self) -> List[ModelProvenance]:
        supported_primary = ["boat", "person", "backpack", "suitcase", "handbag"]
        models = [
            ModelProvenance(
                name="Ultralytics YOLOv8 Nano",
                version="8.3.107",
                task="OBJECT_DETECTION_AND_TRACKING",
                device=self.device,
                status="ready" if self.model is not None else "unavailable",
                supported_classes=supported_primary,
                weights_path=self.weights_path,
                notes="Standard COCO-trained checkpoint. Provides boat, personnel, and package detection with ByteTrack.",
            ),
            ModelProvenance(
                name="YOLO-World Open-Vocabulary",
                version="v8-world",
                task="OPEN_VOCABULARY_DETECTION",
                device=self.device,
                status=self.yolo_world_status,
                supported_classes=["life_raft", "lifeboat", "floating_debris", "buoy"],
                weights_path=os.getenv("AEGIS_YOLOWORLD_MODEL", "yolov8s-world.pt")
                if self.yolo_world_status == "ready" else None,
                notes=(
                    "Open-vocabulary text-guided detector. "
                    + ("Active for candidate maritime classes."
                       if self.yolo_world_status == "ready"
                       else "Weights not installed locally. Candidate classes require offline weights.")
                ),
            ),
        ]
        return models

    def track_frame(
        self,
        frame: Any,
        *,
        confidence_threshold: float = 0.40,
        detection_mode: str = "naval",
        classes_filter: Optional[List[int]] = None,
    ) -> Tuple[List[Detection], Any]:
        """Runs tracking on a single frame and returns structured detections and plot."""
        if self.model is None:
            return [], frame

        track_options: Dict[str, Any] = {
            "persist": True,
            "conf": confidence_threshold,
            "tracker": "bytetrack.yaml",
            "verbose": False,
        }

        if classes_filter is not None:
            track_options["classes"] = classes_filter
        elif detection_mode == "naval":
            track_options["classes"] = MARITIME_EXPANDED_CLASSES

        results = self.model.track(frame, **track_options)[0]
        annotated_frame = results.plot()
        detections: List[Detection] = []

        boxes = results.boxes
        if boxes is not None:
            names = results.names
            for idx in range(len(boxes)):
                class_id = int(boxes.cls[idx].item())
                label = str(names.get(class_id, class_id)).lower()
                confidence = float(boxes.conf[idx].item())
                xyxy = [float(v) for v in boxes.xyxy[idx].tolist()]

                track_id = None
                if boxes.id is not None and idx < len(boxes.id):
                    raw_id = boxes.id[idx]
                    if raw_id is not None:
                        track_id = int(raw_id.item())

                category = DetectionCategory.UNIDENTIFIED.value
                if class_id == 8 or label in {"boat", "ship", "vessel"}:
                    category = DetectionCategory.VESSEL.value
                elif class_id == 0 or label == "person":
                    category = DetectionCategory.PERSON.value
                elif class_id in CONTAINER_CLASSES:
                    category = DetectionCategory.SUSPICIOUS_OBJECT.value
                else:
                    category = DetectionCategory.COASTAL_OBJECT.value

                detections.append(
                    Detection(
                        label=label,
                        category=category,
                        confidence=confidence,
                        timestamp_seconds=0.0,  # Caller stamps this
                        bbox=xyxy,
                        track_id=track_id,
                        class_id=class_id,
                        model_name="yolov8n",
                        model_version="8.3.107",
                        verification_status=VerificationStatus.DETECTED.value,
                    )
                )

        return detections, annotated_frame
