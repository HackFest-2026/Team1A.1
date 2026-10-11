import math
from typing import Dict, List, Any, Optional
from datetime import datetime
from .models import Citizen
from ..incidents.incident_service import incident_service

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

DEMO_CITIZENS = [
    Citizen(name="Demo User 1", phone="+919999999901", email="demo1@example.com", state="Karnataka", district="Dharwad", city="Hubballi", latitude=15.3600, longitude=75.1200, consent_sms=True, consent_email=True, demo=True),
    Citizen(name="Demo User 2", phone="+919999999902", email="demo2@example.com", state="Karnataka", district="Dharwad", city="Hubballi", latitude=15.3700, longitude=75.1300, consent_sms=True, consent_email=False, demo=True),
    Citizen(name="Demo User 3", phone="+919999999903", email="demo3@example.com", state="Karnataka", district="Dharwad", city="Dharwad", latitude=15.4500, longitude=75.0000, consent_sms=False, consent_email=True, demo=True),
    Citizen(name="Demo User 4", phone="+919999999904", email="demo4@example.com", state="Karnataka", district="Belagavi", city="Belagavi", latitude=15.8400, longitude=74.5000, consent_sms=True, consent_email=True, demo=True)
]

class CitizenService:
    def __init__(self):
        self.citizens: Dict[str, Citizen] = {c.citizen_id: c for c in DEMO_CITIZENS}

    def get_all(self, state: str = None, district: str = None, status: str = None) -> List[Dict[str, Any]]:
        res = []
        for c in self.citizens.values():
            if state and c.state != state: continue
            if district and c.district != district: continue
            if status and c.status != status: continue
            
            # Masking for EOC
            c_dict = c.dict()
            c_dict["phone"] = c.phone[:4] + "****" + c.phone[-2:] if c.phone else ""
            c_dict["email"] = c.email[:2] + "****@" + c.email.split("@")[-1] if c.email and "@" in c.email else ""
            res.append(c_dict)
        return res

    def get_citizen(self, citizen_id: str) -> Optional[Citizen]:
        return self.citizens.get(citizen_id)

    def create_citizen(self, citizen: Citizen) -> Citizen:
        self.citizens[citizen.citizen_id] = citizen
        incident_service._log_audit("SYSTEM", "SYSTEM", "CITIZEN_CREATED", citizen.citizen_id, "SUCCESS")
        return citizen

    def get_targeted_citizens(self, lat: float, lon: float, radius_km: float) -> List[Dict[str, Any]]:
        targeted = []
        for c in self.citizens.values():
            dist = haversine(lat, lon, c.latitude, c.longitude)
            if dist <= radius_km:
                c_dict = c.dict()
                c_dict["targeting_distance"] = dist
                c_dict["targeting_reason"] = f"Citizen is within configured {radius_km} km alert radius."
                targeted.append(c_dict)
        return targeted

citizen_service = CitizenService()
