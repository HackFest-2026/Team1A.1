import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Indian Navy (IN) & Indian Coast Guard (ICG) Vessels and Commercial Traffic in Indian Ocean / Arabian Sea
DEFAULT_INDIAN_MARITIME_VESSELS = [
    {
        "mmsi": "419001122",
        "name": "INS VIKRAMADITYA (R33)",
        "vessel_type": "AIRCRAFT_CARRIER",
        "latitude": 15.4210,
        "longitude": 73.7820,
        "sog": 24.2,
        "cog": 245.0,
        "ais_status": "matched",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "WESTERN_NAVAL_COMMAND_C2",
        "flag": "IN",
        "is_dark_vessel": False,
        "notes": "Indian Navy Western Fleet flag group operating in Arabian Sea patrol sector"
    },
    {
        "mmsi": "419004455",
        "name": "ICGS SAMARTH",
        "vessel_type": "OFFSHORE_PATROL_VESSEL",
        "latitude": 15.3520,
        "longitude": 73.6540,
        "sog": 16.5,
        "cog": 180.0,
        "ais_status": "matched",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "INDIAN_COAST_GUARD_NAIS",
        "flag": "IN",
        "is_dark_vessel": False,
        "notes": "Indian Coast Guard offshore patrol vessel enforcing EEZ security"
    },
    {
        "mmsi": "000000000",
        "name": "UNIDENTIFIED FAST INTRUDER CONTACT",
        "vessel_type": "HIGH_SPEED_WATERCRAFT",
        "latitude": 15.4830,
        "longitude": 73.6920,
        "sog": 29.8,
        "cog": 92.0,
        "ais_status": "missing",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "COASTAL_RADAR_CHAIN (IMAC GURGAON)",
        "flag": "UNKNOWN",
        "is_dark_vessel": True,
        "notes": "Coastal radar / EO track with zero AIS broadcast. Suspected dark vessel approaching coastal line."
    },
    {
        "mmsi": "419007788",
        "name": "FV JALATHARANG-12",
        "vessel_type": "DEEP_SEA_TRAWLER",
        "latitude": 15.2910,
        "longitude": 73.8100,
        "sog": 5.1,
        "cog": 305.0,
        "ais_status": "mismatch",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "NATIONAL_AIS_NETWORK (DGLL)",
        "flag": "IN",
        "is_dark_vessel": False,
        "notes": "Reported coastal transponder position mismatch with radar track. Under verification."
    }
]

class AISStreamService:
    def __init__(self):
        self.api_key = os.environ.get("AISSTREAM_API_KEY", "")
        self.vessels: Dict[str, Dict[str, Any]] = {
            v["mmsi"] if v["mmsi"] != "000000000" else f"DARK_{idx}": dict(v)
            for idx, v in enumerate(DEFAULT_INDIAN_MARITIME_VESSELS)
        }
        self.last_fetch = time.time()

    def get_status(self) -> Dict[str, Any]:
        return {
            "service": "INDIAN_NAVY_MARITIME_INTELLIGENCE (IMAC/IFC-IOR)",
            "api_key_configured": bool(self.api_key),
            "mode": "LIVE_NAIS_STREAM" if self.api_key else "INDIAN_MARITIME_TACTICAL_ENGINE",
            "active_contacts": len(self.vessels),
            "dark_vessels_detected": sum(1 for v in self.vessels.values() if v.get("is_dark_vessel")),
            "ais_mismatches": sum(1 for v in self.vessels.values() if v.get("ais_status") == "mismatch"),
            "theatre": "ARABIAN_SEA_WESTERN_SEABOARD",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def list_vessels(self, filter_status: Optional[str] = None) -> List[Dict[str, Any]]:
        self._simulate_step()
        results = list(self.vessels.values())
        if filter_status and filter_status != "ALL":
            if filter_status == "DARK":
                results = [v for v in results if v.get("is_dark_vessel")]
            elif filter_status == "MISMATCH":
                results = [v for v in results if v.get("ais_status") == "mismatch"]
            else:
                results = [v for v in results if v.get("ais_status") == filter_status.lower()]
        return results

    def ingest_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        mmsi = str(contact.get("mmsi") or f"CONTACT_{int(time.time() * 1000) % 100000}")
        is_dark = contact.get("is_dark_vessel", False) or contact.get("ais_status") == "missing"
        
        record = {
            "mmsi": mmsi,
            "name": contact.get("name", f"CONTACT-{mmsi}"),
            "vessel_type": contact.get("vessel_type", "SURFACE_VESSEL"),
            "latitude": float(contact["latitude"]),
            "longitude": float(contact["longitude"]),
            "sog": float(contact.get("sog", 0.0)),
            "cog": float(contact.get("cog", 0.0)),
            "ais_status": contact.get("ais_status", "matched"),
            "last_update": datetime.now(timezone.utc).isoformat(),
            "source": contact.get("source", "COASTAL_SURVEILLANCE_RADAR"),
            "flag": contact.get("flag", "IN"),
            "is_dark_vessel": is_dark,
            "notes": contact.get("notes", "Maritime track verified by Indian Coast Guard")
        }
        self.vessels[mmsi] = record
        return record

    def _simulate_step(self):
        now = time.time()
        dt = min(30.0, max(0.5, now - self.last_fetch))
        self.last_fetch = now

        for v in self.vessels.values():
            sog = v.get("sog", 0.0)
            cog = v.get("cog", 0.0)
            if sog > 0:
                import math
                rad = math.radians(cog)
                d_deg = (sog * (dt / 3600.0)) / 60.0
                v["latitude"] = round(v["latitude"] + d_deg * math.cos(rad), 5)
                v["longitude"] = round(v["longitude"] + d_deg * math.sin(rad), 5)
                v["last_update"] = datetime.now(timezone.utc).isoformat()

ais_service = AISStreamService()
