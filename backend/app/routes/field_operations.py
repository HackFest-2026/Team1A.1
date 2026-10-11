from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Dict, Any, Optional
from ..services.field_operations.models import FieldUnit, LocationUpdate, StatusUpdate, Evidence, FieldReport
from ..services.field_operations.field_service import field_service
from ..services.field_operations.evidence_service import evidence_service
from datetime import datetime

router = APIRouter(prefix="/api/national", tags=["field_operations"])

@router.get("/field-units")
def get_field_units(incident_id: Optional[str] = None):
    return {"status": "success", "records": field_service.get_all(incident_id)}

@router.get("/field-units/{field_unit_id}")
def get_field_unit(field_unit_id: str):
    u = field_service.get_unit(field_unit_id)
    if not u: raise HTTPException(status_code=404, detail="Unit not found")
    return {"status": "success", "record": u.dict()}

@router.post("/field-units")
def create_field_unit(unit: FieldUnit):
    u = field_service.create_unit(unit)
    return {"status": "success", "record": u.dict()}

@router.post("/field-units/{field_unit_id}/location")
def update_location(field_unit_id: str, loc: LocationUpdate):
    res = field_service.update_location(field_unit_id, loc)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.post("/field-units/{field_unit_id}/status")
def update_status(field_unit_id: str, status: StatusUpdate):
    res = field_service.update_status(field_unit_id, status)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/incidents/{incident_id}/evidence")
def upload_evidence(
    incident_id: str,
    file_name: str = Form(...),
    evidence_type: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    description: str = Form(""),
    field_unit_id: Optional[str] = Form(None),
    demo: bool = Form(False)
):
    # Dummy file validation for MVP, ignoring actual file stream
    # Supported: JPG, JPEG, PNG, WEBP
    ext = file_name.split(".")[-1].lower()
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        raise HTTPException(status_code=400, detail="Unsupported file format")

    ev = Evidence(
        incident_id=incident_id,
        evidence_type=evidence_type,
        file_name=file_name,
        file_path=f"/fake/storage/{file_name}",
        latitude=latitude,
        longitude=longitude,
        description=description,
        field_unit_id=field_unit_id,
        demo=demo
    )
    saved = evidence_service.add_evidence(ev)
    return {"status": "success", "record": saved.dict()}

@router.get("/incidents/{incident_id}/evidence")
def get_evidence(incident_id: str):
    return {"status": "success", "records": evidence_service.get_evidence_for_incident(incident_id)}

@router.post("/evidence/{evidence_id}/analyze")
def analyze_evidence(evidence_id: str):
    res = evidence_service.analyze_evidence(evidence_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.post("/evidence/{evidence_id}/confirm")
def confirm_evidence(evidence_id: str, confirmation: str):
    res = evidence_service.confirm_evidence(evidence_id, confirmation)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/incidents/{incident_id}/field-reports")
def create_field_report(incident_id: str, report: FieldReport):
    report.incident_id = incident_id
    saved = evidence_service.add_report(report)
    return {"status": "success", "record": saved.dict()}

@router.get("/incidents/{incident_id}/field-reports")
def get_field_reports(incident_id: str):
    return {"status": "success", "records": evidence_service.get_reports_for_incident(incident_id)}
