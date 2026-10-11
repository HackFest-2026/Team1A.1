from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from ..services.incidents.incident_service import incident_service
from ..services.national_weather_service import national_weather_service
from ..services.satellite_gibs_service import satellite_gibs_service
from ..services.national_risk_service import national_risk_service
from ..services.alerts.sms_service import sms_service

router = APIRouter(prefix="/api/national", tags=["incidents"])

@router.get("/eoc/status")
def get_eoc_status():
    imd_status = "ONLINE" if national_weather_service.access_configured else "NOT_CONFIGURED"
    
    sat_res = satellite_gibs_service.get_status()
    sat_status = sat_res if isinstance(sat_res, str) else sat_res.get("mode", "UNKNOWN")
    
    # Check risk engine
    risk_status = "ONLINE"
    try:
        national_risk_service.get_national_risk()
    except Exception:
        risk_status = "UNAVAILABLE"

    # Alert engine status
    alert_status = sms_service.get_status() # SIMULATED, AVAILABLE, NOT_CONFIGURED
    
    return {
        "status": "success",
        "imd": imd_status,
        "satellite": sat_status,
        "risk_engine": risk_status,
        "alert_engine": alert_status,
        "incident_engine": "ONLINE"
    }

@router.get("/incidents")
def get_incidents(state: Optional[str] = None, status: Optional[str] = None):
    records = incident_service.get_all(state=state, status=status)
    return {"status": "success", "records": records}

@router.post("/incidents/recommend")
def recommend_incidents():
    res = incident_service.scan_for_incidents()
    if res.get("status") == "unavailable":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    inc = incident_service.get_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "success", "record": inc}

@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(incident_id: str):
    res = incident_service.update_status(incident_id, "ASSESSING")
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/incidents/{incident_id}/escalate")
def escalate_incident(incident_id: str):
    res = incident_service.update_status(incident_id, "ESCALATED")
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str):
    res = incident_service.update_status(incident_id, "RESOLVED")
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
