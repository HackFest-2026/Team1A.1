from typing import List, Dict, Any, Optional
from datetime import datetime
from .models import Resource, ResourceRequirement, ResponsePlan, ResponseAction

# Pre-seeded demo resources
DEMO_RESOURCES = [
    Resource(name="Rescue Team Alpha", resource_type="RESCUE_TEAM", category="PERSONNEL", quantity=2, available_quantity=2, latitude=15.3647, longitude=75.1240, state="Karnataka", district="Dharwad", city="Hubballi", location_name="Hubballi Fire Station", demo=True),
    Resource(name="Rescue Team Beta", resource_type="RESCUE_TEAM", category="PERSONNEL", quantity=1, available_quantity=1, latitude=15.4589, longitude=75.0078, state="Karnataka", district="Dharwad", city="Dharwad", location_name="Dharwad Central", demo=True),
    Resource(name="Ambulance Unit A", resource_type="AMBULANCE", category="VEHICLE", quantity=5, available_quantity=5, latitude=15.3500, longitude=75.1500, state="Karnataka", district="Dharwad", city="Hubballi", location_name="KIMS Hospital", demo=True),
    Resource(name="Boat Unit A", resource_type="BOAT", category="VEHICLE", quantity=3, available_quantity=3, latitude=15.3700, longitude=75.1300, state="Karnataka", district="Dharwad", city="Hubballi", location_name="Unkal Lake Depot", demo=True),
    Resource(name="Medical Supply Depot", resource_type="MEDICAL_KIT", category="SUPPLY", quantity=100, available_quantity=100, latitude=15.3600, longitude=75.1400, state="Karnataka", district="Dharwad", city="Hubballi", location_name="District Health Center", demo=True),
    Resource(name="Emergency Supply Depot", resource_type="EMERGENCY_KIT", category="SUPPLY", quantity=50, available_quantity=50, latitude=15.3800, longitude=75.1100, state="Karnataka", district="Dharwad", city="Hubballi", location_name="Civil Defense Base", demo=True)
]

class ResourceService:
    def __init__(self):
        self.resources: Dict[str, Resource] = {r.resource_id: r for r in DEMO_RESOURCES}
        self.requirements: Dict[str, ResourceRequirement] = {}
        self.plans: Dict[str, ResponsePlan] = {}

    def get_all_resources(self, state: str = None, district: str = None, resource_type: str = None) -> List[Dict[str, Any]]:
        res = []
        for r in self.resources.values():
            if state and r.state != state: continue
            if district and r.district != district: continue
            if resource_type and r.resource_type != resource_type: continue
            res.append(r.dict())
        return res

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        return self.resources.get(resource_id)

    def reserve_resource(self, resource_id: str, quantity: int) -> bool:
        r = self.resources.get(resource_id)
        if not r: return False
        if quantity <= 0: return False
        if r.available_quantity < quantity: return False
        
        r.available_quantity -= quantity
        if r.available_quantity == 0:
            r.status = "RESERVED"
        elif r.available_quantity < r.quantity:
            r.status = "PARTIALLY_AVAILABLE"
        r.last_updated = datetime.utcnow().isoformat() + "Z"
        return True

    def dispatch_resource(self, resource_id: str, quantity: int) -> bool:
        r = self.resources.get(resource_id)
        if not r: return False
        # In a real system, we'd track exactly how many are dispatched vs reserved.
        # For this MVP, if it's dispatched, we ensure it's marked as DISPATCHED or IN_TRANSIT.
        r.status = "IN_TRANSIT"
        r.last_updated = datetime.utcnow().isoformat() + "Z"
        return True

    def add_requirement(self, req: ResourceRequirement):
        self.requirements[req.requirement_id] = req

    def get_requirements_for_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        return [r.dict() for r in self.requirements.values() if r.incident_id == incident_id]

    def save_plan(self, plan: ResponsePlan):
        self.plans[plan.response_plan_id] = plan

    def get_plans_for_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        res = []
        for p in self.plans.values():
            if p.incident_id == incident_id:
                pd = p.dict()
                pd["plan_id"] = p.response_plan_id
                res.append(pd)
        return res

resource_service = ResourceService()
