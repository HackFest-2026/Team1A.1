from typing import List, Optional, Dict
from .models import Citizen
import os

class CitizenService:
    def __init__(self):
        self.citizens: Dict[str, Citizen] = {}
        self._seed_demo_data()

    def _seed_demo_data(self):
        # Only seed demo users if in DEMO_ALERT_MODE
        if os.environ.get("DEMO_ALERT_MODE", "true").lower() == "true":
            # Seed 18 demo users in Dharwad
            for i in range(1, 19):
                c = Citizen(
                    name=f"Demo Team Member {i}",
                    phone=f"+9199999999{i:02d}",
                    email=f"demo{i}@resilienceroute.local",
                    state="Karnataka",
                    district="Dharwad",
                    city="Hubballi",
                    consent_status=True,
                    preferred_language="en"
                )
                self.citizens[c.citizen_id] = c
                
            # Seed a few in Belagavi
            for i in range(1, 6):
                c = Citizen(
                    name=f"Demo Team Member Belagavi {i}",
                    phone=f"+9188888888{i:02d}",
                    email=f"belagavi{i}@resilienceroute.local",
                    state="Karnataka",
                    district="Belagavi",
                    consent_status=True
                )
                self.citizens[c.citizen_id] = c

    def get_all(self) -> List[Citizen]:
        return list(self.citizens.values())

    def get_by_region(self, state: str, district: Optional[str] = None) -> List[Citizen]:
        result = []
        for c in self.citizens.values():
            if c.consent_status and c.state == state:
                if district is None or c.district == district:
                    result.append(c)
        return result

    def register(self, citizen: Citizen) -> Citizen:
        if not citizen.consent_status:
            raise ValueError("Consent is required to register for alerts.")
        self.citizens[citizen.citizen_id] = citizen
        return citizen

    def update(self, citizen_id: str, updates: dict) -> Optional[Citizen]:
        if citizen_id not in self.citizens:
            return None
        c = self.citizens[citizen_id]
        for k, v in updates.items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c

citizen_service = CitizenService()
