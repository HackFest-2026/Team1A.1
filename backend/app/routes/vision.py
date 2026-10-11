"""Video intelligence and multi-model maritime threat assessment for AEGIS-COP."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.services.evidence import EvidenceCreate, evidence_service
from app.services.vision.pipeline import RUN_DIR, vision_pipeline

router = APIRouter(prefix="/api/vision", tags=["video intelligence"])

MAX_UPLOAD_BYTES = 150 * 1024 * 1024

ALLOWED_SUFFIXES = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"
}

# Standard COCO class IDs used by yolov8n.pt.
# COCO ID 8 is boat.
NAVAL_COCO_CLASSES = [8]


@router.get("/status")
def vision_status():
    try:
        import cv2
        import ultralytics

        installed = True
        dependency_error = None
        models_info = vision_pipeline.get_models_provenance()
    except Exception as exc:
        installed = False
        dependency_error = str(exc)
        models_info = []

    return {
        "status": "ready" if installed else "dependencies_missing",
        "pipeline": "multi_model_maritime_intelligence",
        "models": models_info,
        "model": os.getenv("AEGIS_YOLO_MODEL", "yolov8n.pt"),
        "default_naval_class_filter": NAVAL_COCO_CLASSES,
        "note": (
            "Multi-model maritime surveillance pipeline. "
            "Threat scores are explainable review priorities requiring operator validation."
        ),
        "dependency_error": dependency_error,
    }


@router.post("/analyze-video")
async def analyze_video(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    description: str = Form("Video observation submitted for review"),
    confidence_threshold: float = Form(0.40),
    sample_fps: float = Form(3.0),
    detection_mode: str = Form("naval"),
    restricted_zone_entry: bool = Form(False),
    ais_status: str = Form("unknown"),
    unusual_behavior_observed: bool = Form(False),
    near_protected_asset: bool = Form(False),
):
    if not file.filename:
        raise HTTPException(status_code=415, detail="A filename is required.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: mp4, mov, avi, mkv, webm, m4v.",
        )

    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Provide both latitude and longitude, or neither.",
        )

    if latitude is not None and not -90 <= latitude <= 90:
        raise HTTPException(status_code=422, detail="Invalid latitude.")

    if longitude is not None and not -180 <= longitude <= 180:
        raise HTTPException(status_code=422, detail="Invalid longitude.")

    if not 0.05 <= confidence_threshold <= 0.95:
        raise HTTPException(
            status_code=422,
            detail="Confidence threshold must be between 0.05 and 0.95.",
        )

    if not 0.25 <= sample_fps <= 8:
        raise HTTPException(
            status_code=422,
            detail="Sampling rate must be between 0.25 and 8 FPS.",
        )

    if detection_mode not in {"naval", "general"}:
        raise HTTPException(
            status_code=422,
            detail="detection_mode must be 'naval' or 'general'.",
        )

    if ais_status not in {"unknown", "matched", "missing", "mismatch"}:
        raise HTTPException(status_code=422, detail="Invalid AIS status.")

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    temp_id = os.urandom(8).hex()
    input_path = RUN_DIR / f"{temp_id}_upload{suffix}"

    try:
        size = 0
        with input_path.open("wb") as destination:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Video exceeds the 150 MB upload limit.",
                    )
                destination.write(chunk)

        if size == 0:
            raise HTTPException(status_code=400, detail="Uploaded video is empty.")

        try:
            result = vision_pipeline.process_video(
                input_path,
                original_filename=Path(file.filename).name,
                confidence_threshold=confidence_threshold,
                sample_fps=sample_fps,
                detection_mode=detection_mode,
                latitude=latitude,
                longitude=longitude,
                restricted_zone_entry=restricted_zone_entry,
                ais_status=ais_status,
                unusual_behavior_observed=unusual_behavior_observed,
                near_protected_asset=near_protected_asset,
            )
        except ValueError as val_err:
            raise HTTPException(status_code=422, detail=str(val_err)) from val_err
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Vision pipeline processing error: {exc}"
            ) from exc

        # Create structured Evidence entry in database
        max_conf = 0.0
        for frame in result.get("frames", []):
            for d in frame.get("detections", []):
                conf = d.get("confidence", 0.0)
                if conf > max_conf:
                    max_conf = conf

        run_id = result["run_id"]
        evidence = evidence_service.create_evidence(
            EvidenceCreate(
                source_type="DRONE",
                source_id=f"VIDEO-{run_id[:8]}",
                observation_type="VIDEO_OBJECT_DETECTION",
                latitude=latitude,
                longitude=longitude,
                confidence=max_conf,
                provenance={
                    "origin": "uploaded_video",
                    "source_system": "AEGIS-COP_VIDEO_INTELLIGENCE",
                    "is_simulation": False,
                    "analysis_method": "MULTI_MODEL_MARITIME_PIPELINE",
                    "models_used": result.get("models_used", []),
                    "detection_mode": detection_mode,
                    "human_review_required": True,
                    "run_id": run_id,
                    "original_filename": Path(file.filename).name,
                    "classes_seen": result["metrics"]["unique_classes"],
                    "unique_object_counts": result["metrics"]["unique_object_counts_approx"],
                    "potential_threat_assessment": result["threat_assessment"],
                    "events": result.get("events", []),
                    "vessel_intelligence": result.get("vessel_intelligence", []),
                },
                media_reference=f"/api/vision/runs/{run_id}/video",
                description=(
                    (description.strip() or "Video observation for review")
                    + f" | {result['metrics']['frames_processed']} sampled frames; "
                    + f"{result['metrics']['detections_total']} detections. "
                    + f"Review priority: {result['threat_assessment']['level']}. "
                    + "Human review required."
                ),
            )
        )

        result["evidence_id"] = evidence["evidence_id"]
        return result

    finally:
        input_path.unlink(missing_ok=True)
        await file.close()


@router.get("/runs/{run_id}/video")
def get_annotated_video(run_id: str):
    if len(run_id) != 32 or not run_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid run ID.")

    path = RUN_DIR / f"{run_id}_annotated.mp4"

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Annotated video not found. Run analysis again.",
        )

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"aegis-{run_id[:8]}-annotated.mp4",
    )


@router.get("/runs/{run_id}/frames/{frame_filename}")
def get_evidence_frame_thumbnail(run_id: str, frame_filename: str):
    if len(run_id) != 32 or not run_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid run ID.")

    if ".." in frame_filename or "/" in frame_filename or "\\" in frame_filename:
        raise HTTPException(status_code=400, detail="Invalid frame filename.")

    path = RUN_DIR / frame_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail not found.")

    return FileResponse(path, media_type="image/jpeg")
