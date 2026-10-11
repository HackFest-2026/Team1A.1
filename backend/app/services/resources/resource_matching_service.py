import math
from typing import List, Dict, Any, Tuple, Optional
from .models import Resource, ResourceRequirement, ResponsePlan, ResponseAction
from .resource_service import resource_service
from ..incidents.incident_service import incident_service

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _build_hazard_steps(hazard_type: str, title: str, description: str) -> Tuple[str, List[str]]:
    ht = (hazard_type or "").lower()
    t = (title or "").lower()
    
    if "drainage overflow" in ht or "drainage overflow" in t or "overflow" in ht:
        summary = f"Stormwater drainage overflow is affecting access near {title}."
        steps = [
            "1. Deploy field assessment team.",
            "2. Inspect drainage outlet/culvert.",
            "3. Assess roadway water accumulation.",
            "4. Determine road accessibility.",
            "5. Establish temporary access control if required.",
            "6. Identify a lower-risk route.",
            "7. Position suitable response resources.",
            "8. Collect field evidence.",
            "9. Reassess after field feedback."
        ]
    elif "drain" in ht or "blockage" in ht or "blockage" in t:
        summary = f"Open drain blockage causing localized overflow near {title}."
        steps = [
            "1. Inspect blockage at drainage culvert.",
            "2. Assess overflow rate and localized flooding.",
            "3. Determine affected road segments.",
            "4. Inspect nearby alternative access points.",
            "5. Collect visual field evidence.",
            "6. Reassess risk after field feedback."
        ]
    elif "waterlogging" in ht or "waterlogging" in t or "flood" in ht:
        summary = f"Road waterlogging impeding traffic near {title}."
        steps = [
            "1. Assess water accumulation depth on roadway.",
            "2. Assess road access and vehicle passability.",
            "3. Inspect municipal drainage capacity.",
            "4. Determine route condition and detour options.",
            "5. Collect visual field evidence.",
            "6. Reassess after field team deployment."
        ]
    else:
        summary = f"Hazard incident detected near {title}: {description}."
        steps = [
            "1. Deploy field assessment team.",
            "2. Evaluate localized hazard and safety risks.",
            "3. Inspect access routes and road conditions.",
            "4. Position appropriate emergency response units.",
            "5. Collect field evidence and monitor developments."
        ]
    return summary, steps

class ResourceMatchingService:

    def generate_requirements(self, incident_id: str) -> List[Dict[str, Any]]:
        inc_dict = incident_service.get_by_id(incident_id)
        if not inc_dict: return []
        
        severity = inc_dict.get("severity", "NORMAL")
        hazard = inc_dict.get("hazard_type", "").lower()
        
        # Rule-based requirements
        reqs = []
        if any(k in hazard for k in ["flood", "waterlogging", "drainage", "water", "blocked", "weather", "severe"]):
            if severity == "CRITICAL":
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="RESCUE_TEAM", required_quantity=2, priority="HIGH", reason="Critical flood/waterlogging requires personnel"))
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="AMBULANCE", required_quantity=2, priority="HIGH", reason="Medical standby"))
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="BOAT", required_quantity=3, priority="CRITICAL", reason="Water rescue essential"))
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="MEDICAL_KIT", required_quantity=20, priority="HIGH", reason="Emergency care coverage"))
            else:
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="RESCUE_TEAM", required_quantity=1, priority="MEDIUM", reason="Response team dispatch"))
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="AMBULANCE", required_quantity=1, priority="MEDIUM", reason="Medical standby"))
                reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="BOAT", required_quantity=1, priority="HIGH", reason="Water access"))
        elif "fire" in hazard:
            reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="FIRE_TRUCK", required_quantity=2, priority="CRITICAL", reason="Active fire suppression"))
            reqs.append(ResourceRequirement(incident_id=incident_id, resource_type="AMBULANCE", required_quantity=1, priority="HIGH", reason="Medical standby"))
        
        saved = []
        for r in reqs:
            resource_service.add_requirement(r)
            saved.append(r.dict())
            
        # Also generate Pre-Positioning Recommendations
        if severity in ["HIGH", "CRITICAL"]:
            incident_service._add_timeline(
                incident_service.incidents[incident_id], 
                "PRE_POSITIONING_RECOMMENDED", 
                "Pre-positioning of resources recommended for high-risk zones.", 
                "SYSTEM", "SYSTEM"
            )

        return saved

    def create_response_plan(self, incident_id: str) -> Dict[str, Any]:
        inc_dict = incident_service.get_by_id(incident_id)
        if not inc_dict: return {"error": "Incident not found"}
        
        # If plan already exists for this incident, return existing plan
        existing_plans = resource_service.get_plans_for_incident(incident_id)
        if existing_plans:
            return {"status": "success", "plan": existing_plans[-1]}

        reqs = resource_service.get_requirements_for_incident(incident_id)
        if not reqs:
            reqs = self.generate_requirements(incident_id)
            
        plan = ResponsePlan(incident_id=incident_id, status="PENDING_APPROVAL")
        
        summary, steps = _build_hazard_steps(
            inc_dict.get("hazard_type", ""),
            inc_dict.get("title", ""),
            inc_dict.get("description", "")
        )
        plan.notes = f"{summary} Steps: " + " ".join(steps)
        
        lat = inc_dict.get("latitude", 0)
        lon = inc_dict.get("longitude", 0)
        
        for req in reqs:
            best_match = self._find_best_match(req["resource_type"], req["required_quantity"], lat, lon, req["priority"])
            if best_match:
                resource, qty, score, reason = best_match
                action = ResponseAction(
                    response_plan_id=plan.response_plan_id,
                    incident_id=incident_id,
                    resource_id=resource.resource_id,
                    resource_type=resource.resource_type,
                    quantity=qty,
                    priority=req["priority"],
                    recommendation_reason=reason,
                    match_score=score,
                    status="PENDING_APPROVAL"
                )
                plan.actions.append(action)
                
        resource_service.save_plan(plan)
        
        # Link to incident
        inc_obj = incident_service.incidents[incident_id]
        if plan.response_plan_id not in inc_obj.response_plans:
            inc_obj.response_plans.append(plan.response_plan_id)
        
        incident_service._add_timeline(inc_obj, "RESPONSE_PLAN_CREATED", f"Response plan {plan.response_plan_id} recommended", "SYSTEM", "SYSTEM")
        incident_service._log_audit("SYSTEM", "SYSTEM", "RESPONSE_PLAN_CREATED", incident_id, "SUCCESS")

        pd = plan.dict()
        pd["plan_id"] = plan.response_plan_id
        pd["situation_summary"] = summary
        pd["recommended_steps"] = steps
        return {"status": "success", "plan": pd}

    def _find_best_match(self, resource_type: str, required_qty: int, lat: float, lon: float, priority: str) -> Optional[Tuple[Resource, int, int, str]]:
        candidates = []
        for r in resource_service.resources.values():
            if r.resource_type == resource_type and r.available_quantity > 0:
                dist = haversine(lat, lon, r.latitude, r.longitude)
                # Score Logic
                dist_score = max(0, 50 - int(dist / 2)) # Closer is better, max 50
                qty_score = 30 if r.available_quantity >= required_qty else int((r.available_quantity / required_qty) * 30)
                pri_score = 20 if priority in ["HIGH", "CRITICAL"] else 10
                
                total_score = dist_score + qty_score + pri_score
                candidates.append((r, total_score, dist))
                
        if not candidates:
            return None
            
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_resource, score, dist = candidates[0]
        
        qty_to_assign = min(best_resource.available_quantity, required_qty)
        reason = f"Available {best_resource.resource_type} located {dist:.1f} km from incident. Score: {score}/100."
        
        return (best_resource, qty_to_assign, score, reason)

resource_matching_service = ResourceMatchingService()

