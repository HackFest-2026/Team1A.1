from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, Any, List
from ..services.alerts.citizen_service import citizen_service
from ..services.alerts.alert_decision_service import alert_decision_service
from ..services.alerts.models import Citizen

router = APIRouter(prefix="/api/national", tags=["alerts"])

@router.get("/alerts")
def get_active_alerts():
    return {"status": "success", "records": alert_decision_service.get_all()}

@router.post("/alerts/preview")
def preview_alert(payload: Dict[str, str]):
    state = payload.get("state")
    district = payload.get("district")
    if not state or not district:
        raise HTTPException(status_code=400, detail="State and district required")
    res = alert_decision_service.preview_alert(state, district)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/alerts/send")
def send_alert(payload: Dict[str, Any]):
    # In reality this should validate against preview shape
    res = alert_decision_service.send_alert(payload)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str, payload: Dict[str, str]):
    cit_id = payload.get("citizen_id")
    if not cit_id:
        raise HTTPException(status_code=400, detail="citizen_id required")
    res = alert_decision_service.acknowledge_alert(alert_id, cit_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/alerts/{alert_id}/escalate")
def escalate(alert_id: str, payload: Dict[str, str]):
    action = payload.get("action", "General escalation")
    res = alert_decision_service.escalate_authority(alert_id, action)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/citizens")
def get_citizens():
    return {"status": "success", "records": [c.dict() for c in citizen_service.get_all()]}

@router.post("/citizens")
def register_citizen(c: Citizen):
    try:
        saved = citizen_service.register(c)
        return {"status": "success", "citizen_id": saved.citizen_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
