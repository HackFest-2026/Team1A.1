from typing import Dict, Any, List
from datetime import datetime, timezone

# Indian Armed Forces (Army, Navy, Air Force) Military Grid Sectors
DEFAULT_INDIAN_TACTICAL_ZONES = [
    {
        "zone_id": "MS-DHARWAD-01",
        "name": "MILITARY STATION DHARWAD (HQ SUB-AREA)",
        "zone_type": "MILITARY_STATION_FOB",
        "security_level": "LEVEL_4_RESTRICTED",
        "center": [15.3610, 75.1200],
        "radius_m": 800,
        "coordinates": [
            [15.3660, 75.1150],
            [15.3660, 75.1250],
            [15.3560, 75.1250],
            [15.3560, 75.1150]
        ],
        "description": "Primary Indian Army tactical logistics, cantonment perimeter, and mission command hub",
        "commander": "BRIGADIER A. S. CHAUHAN, SOUTHERN COMMAND",
        "active": True
    },
    {
        "zone_id": "AIR-DEFENCE-AKASH-03",
        "name": "AKASH SAM AIR DEFENCE UMBRELLA SECTOR",
        "zone_type": "AIR_DEFENCE_UMBRELLA",
        "security_level": "RED_ZONE_INTERCEPT_READY",
        "center": [15.3900, 75.1350],
        "radius_m": 1500,
        "coordinates": [
            [15.4000, 75.1250],
            [15.4000, 75.1450],
            [15.3800, 75.1450],
            [15.3800, 75.1250]
        ],
        "description": "Army Air Defence (AAD) Akash surface-to-air missile engagement perimeter",
        "commander": "47 ARMY AIR DEFENCE REGIMENT",
        "active": True
    },
    {
        "zone_id": "DEFENCE-AXIS-ALPHA",
        "name": "NH48 MILITARY SUPPLY CORRIDOR",
        "zone_type": "TACTICAL_LOGISTICS_CORRIDOR",
        "security_level": "ESCORTED_MILITARY_TRANSIT",
        "center": [15.3550, 75.1450],
        "radius_m": 500,
        "coordinates": [
            [15.3400, 75.1300],
            [15.3700, 75.1600]
        ],
        "description": "Hardened defence route designated for armored column and ammunition replenishment",
        "commander": "CORPS OF MILITARY POLICE (CMP)",
        "active": True
    }
]

class TacticalZonesService:
    def __init__(self):
        self.zones: Dict[str, Dict[str, Any]] = {
            z["zone_id"]: dict(z) for z in DEFAULT_INDIAN_TACTICAL_ZONES
        }

    def list_zones(self) -> List[Dict[str, Any]]:
        return list(self.zones.values())

    def add_zone(self, data: Dict[str, Any]) -> Dict[str, Any]:
        zone_id = data.get("zone_id") or f"TACTICAL_ZONE_{len(self.zones) + 1}"
        record = {
            "zone_id": zone_id,
            "name": data.get("name", f"ZONE {zone_id}"),
            "zone_type": data.get("zone_type", "RESTRICTED_MILITARY_ZONE"),
            "security_level": data.get("security_level", "RESTRICTED"),
            "center": data.get("center", [15.3647, 75.1240]),
            "radius_m": data.get("radius_m", 500),
            "coordinates": data.get("coordinates", []),
            "description": data.get("description", "Indian Armed Forces tactical sector boundary"),
            "commander": data.get("commander", "SOUTHERN THEATRE COMMAND"),
            "active": data.get("active", True),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.zones[zone_id] = record
        return record

tactical_zones_service = TacticalZonesService()
