from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from ..services.resources.resource_service import resource_service
from ..services.resources.resource_matching_service import resource_matching_service
from ..services.incidents.incident_service import incident_service
from datetime import datetime

router = APIRouter(prefix="/api/national", tags=["resources"])

@router.get("/resources")
def get_resources(state: Optional[str] = None, district: Optional[str] = None, resource_type: Optional[str] = None):
    res = resource_service.get_all_resources(state, district, resource_type)
    return {"status": "success", "records": res}

@router.get("/incidents/{incident_id}/requirements")
def get_requirements(incident_id: str):
    reqs = resource_service.get_requirements_for_incident(incident_id)
    return {"status": "success", "records": reqs}

@router.post("/incidents/{incident_id}/requirements")
def generate_requirements(incident_id: str):
    reqs = resource_matching_service.generate_requirements(incident_id)
    return {"status": "success", "records": reqs}

@router.get("/incidents/{incident_id}/response-plan")
def get_response_plan(incident_id: str):
    plans = resource_service.get_plans_for_incident(incident_id)
    return {"status": "success", "records": plans}

@router.post("/incidents/{incident_id}/response-plan")
def generate_response_plan(incident_id: str):
    res = resource_matching_service.create_response_plan(incident_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/response-plans/{plan_id}/approve")
def approve_response_plan(plan_id: str):
    # Search by plan_id or response_plan_id
    plan = resource_service.plans.get(plan_id)
    if not plan:
        for p in resource_service.plans.values():
            if p.response_plan_id == plan_id:
                plan = p
                break

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    pd = plan.dict()
    pd["plan_id"] = plan.response_plan_id
        
    if plan.status == "APPROVED":
        return {"status": "success", "message": "Plan is already approved", "plan": pd}
        
    if plan.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail="Plan not in pending state")
        
    plan.status = "APPROVED"
    plan.approved_by = "EOC_OPERATOR"
    plan.updated_at = datetime.utcnow().isoformat() + "Z"
    
    # Reserve resources
    for action in plan.actions:
        success = resource_service.reserve_resource(action.resource_id, action.quantity)
        if success:
            action.status = "APPROVED"
            action.approved_at = datetime.utcnow().isoformat() + "Z"
            action.approved_by = "EOC_OPERATOR"
        else:
            action.status = "CANCELLED"
            action.notes = "Resource unavailable or over-allocated"

    inc = incident_service.incidents.get(plan.incident_id)
    if inc:
        incident_service._add_timeline(inc, "RESPONSE_PLAN_APPROVED", "Response plan approved by operator. Resources reserved.", "OPERATOR", "EOC_OPERATOR")
        incident_service._log_audit("EOC_OPERATOR", "EOC_OPERATOR", "RESPONSE_PLAN_APPROVED", inc.incident_id, "SUCCESS")

    pd = plan.dict()
    pd["plan_id"] = plan.response_plan_id
    return {"status": "success", "plan": pd}

@router.post("/response-actions/{action_id}/dispatch")
def dispatch_action(action_id: str):
    # Find action
    target_action = None
    target_plan = None
    for plan in resource_service.plans.values():
        for action in plan.actions:
            if action.action_id == action_id:
                target_action = action
                target_plan = plan
                break
        if target_action: break
        
    if not target_action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    if target_action.status != "APPROVED":
        raise HTTPException(status_code=400, detail="Action must be APPROVED before dispatch")
        
    # Simulate dispatch
    success = resource_service.dispatch_resource(target_action.resource_id, target_action.quantity)
    if not success:
        raise HTTPException(status_code=400, detail="Resource dispatch failed (unavailable)")
        
    target_action.status = "DISPATCHED"
    target_action.dispatched_at = datetime.utcnow().isoformat() + "Z"
    
    inc = incident_service.incidents.get(target_plan.incident_id)
    if inc:
        incident_service._add_timeline(inc, "SIMULATED_DISPATCH", f"DEMO RESPONSE: Simulated dispatch for {target_action.resource_type}", "OPERATOR", "EOC_OPERATOR")
        incident_service._log_audit("EOC_OPERATOR", "EOC_OPERATOR", "SIMULATED_DISPATCH", inc.incident_id, "SUCCESS")

    return {"status": "success", "action": target_action.dict(), "message": "SIMULATED RESPONSE. NO REAL RESOURCE HAS BEEN DISPATCHED."}
