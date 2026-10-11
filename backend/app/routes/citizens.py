from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from ..services.citizens.models import Citizen, CitizenAlert, CitizenObservationVerification, PreparednessGuidance
from ..services.field_operations.models import CitizenObservation
from ..services.citizens.citizen_service import citizen_service
from ..services.citizens.alert_delivery_service import alert_delivery_service
from ..services.citizens.preparedness_service import preparedness_service
from ..services.citizens.coverage_service import coverage_service
from ..services.incidents.incident_service import incident_service
from datetime import datetime

router = APIRouter(prefix="/api/national", tags=["citizens"])

@router.get("/citizens")
def get_citizens(state: Optional[str] = None, district: Optional[str] = None, status: Optional[str] = None):
    return {"status": "success", "records": citizen_service.get_all(state, district, status)}

@router.post("/citizens")
def create_citizen(citizen: Citizen):
    c = citizen_service.create_citizen(citizen)
    return {"status": "success", "record": c.dict()}

@router.get("/incidents/{incident_id}/target-citizens")
def target_citizens(incident_id: str, radius_km: float = 5.0):
    inc = incident_service.get_by_id(incident_id)
    if not inc: raise HTTPException(status_code=404, detail="Incident not found")
    
    lat = inc.get("latitude")
    lon = inc.get("longitude")
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Incident lacks coordinates")
        
    targeted = citizen_service.get_targeted_citizens(lat, lon, radius_km)
    return {"status": "success", "records": targeted}

@router.get("/citizen-alerts")
def get_citizen_alerts(incident_id: Optional[str] = None):
    return {"status": "success", "records": alert_delivery_service.get_all(incident_id)}

@router.post("/citizen-alerts")
def create_citizen_alert(alert: CitizenAlert):
    if alert.severity not in ["INFO", "WATCH", "WARNING", "HIGH", "CRITICAL"]:
        raise HTTPException(status_code=400, detail="Invalid severity")
        
    a = alert_delivery_service.create_alert(alert)
    return {"status": "success", "record": a.dict()}

@router.post("/citizen-alerts/{alert_id}/approve")
def approve_citizen_alert(alert_id: str):
    res = alert_delivery_service.approve_alert(alert_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/citizen-alerts/{alert_id}/send")
def send_citizen_alert(alert_id: str):
    res = alert_delivery_service.send_alert(alert_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/citizen-alerts/{alert_id}/acknowledge")
def acknowledge_citizen_alert(alert_id: str):
    res = alert_delivery_service.acknowledge_alert(alert_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/preparedness")
def get_preparedness(hazard_type: str, risk_level: str):
    return preparedness_service.get_guidance(hazard_type, risk_level)

@router.get("/alerts/coverage/{incident_id}")
def get_alert_coverage(incident_id: str):
    return coverage_service.get_coverage_metrics(incident_id)

# Observation Routes
observations: Dict[str, CitizenObservation] = {}

@router.post("/citizen-observations")
def create_observation(obs: CitizenObservation):
    observations[obs.observation_id] = obs
    incident_service._log_audit("CITIZEN", "CITIZEN", "CITIZEN_OBSERVATION_RECEIVED", obs.observation_id, "SUCCESS")
    
    inc = incident_service.incidents.get(obs.incident_id)
    if inc:
        incident_service._add_timeline(inc, "CITIZEN_OBSERVATION_RECEIVED", f"Citizen submitted an observation: {obs.description}", "CITIZEN", "CITIZEN")
        
    return {"status": "success", "record": obs.dict()}

@router.post("/citizen-observations/{observation_id}/verify")
def verify_observation(observation_id: str, payload: CitizenObservationVerification):
    obs = observations.get(observation_id)
    if not obs: raise HTTPException(status_code=404, detail="Observation not found")
    
    obs.verification_status = payload.status
    
    inc = incident_service.incidents.get(obs.incident_id)
    if inc:
        if payload.status == "VERIFIED":
            incident_service._add_timeline(inc, "CITIZEN_OBSERVATION_VERIFIED", "Citizen observation verified by operator.", payload.actor, "EOC_OPERATOR")
            # Possibly trigger reassessment...
            incident_service._add_timeline(inc, "REASSESSMENT_RECOMMENDED", "Verified citizen observation may alter risk.", "SYSTEM", "SYSTEM")
        else:
            incident_service._add_timeline(inc, "CITIZEN_OBSERVATION_REJECTED", "Citizen observation rejected by operator.", payload.actor, "EOC_OPERATOR")
            
    incident_service._log_audit(payload.actor, "EOC_OPERATOR", "CITIZEN_OBSERVATION_VERIFIED", observation_id, payload.status)
    return {"status": "success", "record": obs.dict()}
