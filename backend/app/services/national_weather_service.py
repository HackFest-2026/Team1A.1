import os
import time
import requests
from typing import Dict, Any, List

class IMDService:
    def __init__(self):
        self.base_url = os.environ.get("IMD_API_BASE_URL", "https://mausam.imd.gov.in/api")
        # IMD mausam PHP endpoints are typically public/IP-whitelisted rather than bearer-token based.
        # We use a local configuration gate to authorize upstream access.
        self.access_configured = os.environ.get("IMD_ACCESS_AUTHORIZED", "false").lower() == "true" or bool(os.environ.get("IMD_API_KEY"))
        self.cache_ttl = int(os.environ.get("NATIONAL_WEATHER_CACHE_TTL_SECONDS", 300))
        self.cache: Dict[str, Dict[str, Any]] = {}

    def _not_configured(self) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "provider": "IMD",
            "mode": "NOT_CONFIGURED",
            "message": "IMD access not configured/authorized",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "records": []
        }

    def get_status(self) -> Dict[str, Any]:
        if not self.access_configured:
            return {
                "status": "unavailable",
                "provider": "IMD",
                "mode": "NOT_CONFIGURED",
                "message": "IMD access not configured/authorized"
            }
        return {
            "status": "success",
            "provider": "IMD",
            "mode": "LIVE",
            "configured": True,
            "cache": {
                "enabled": True,
                "ttl_seconds": self.cache_ttl,
                "age_seconds": 0
            }
        }

    def _normalize_record(self, raw: dict, product: str) -> dict:
        return {
            "id": raw.get("id"),
            "station_id": raw.get("station_id"),
            "station_name": raw.get("station_name") if "station_name" in raw else raw.get("station"),
            "country": "India",
            "state": raw.get("state"),
            "district": raw.get("district"),
            "city": raw.get("city"),
            "latitude": raw.get("latitude"),
            "longitude": raw.get("longitude"),
            
            "product": product,
            "observation_time": raw.get("observation_time"),
            "issued_time": raw.get("issued_time"),
            "valid_from": raw.get("valid_from"),
            "valid_until": raw.get("valid_until"),
            
            "weather": {
                "temperature_c": raw.get("temperature") if "temperature" in raw else raw.get("temperature_c"),
                "precipitation_mm": raw.get("rainfall") if "rainfall" in raw else raw.get("precipitation_mm"),
                "last_24h_rainfall_mm": raw.get("last_24h_rainfall") if "last_24h_rainfall" in raw else raw.get("last_24h_rainfall_mm"),
                "humidity": raw.get("humidity"),
                "wind_speed_kmh": raw.get("wind_speed_kmh"),
                "weather_code": raw.get("weather_condition") if "weather_condition" in raw else raw.get("weather_code")
            },
            
            "warning": {
                "level": raw.get("warning_level"),
                "type": raw.get("warning_type"),
                "text": raw.get("warning_text")
            },
            
            "source": "IMD",
            "mode": "LIVE - IMD",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cache_age_seconds": 0
        }

    def _fetch_imd(self, endpoint: str, params: dict, product: str) -> Dict[str, Any]:
        if not self.access_configured:
            return self._not_configured()

        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        cache_key = f"{endpoint}?{param_str}"

        now = time.time()
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if now < entry["expires_at"]:
                # Return cached data
                import copy
                result = copy.deepcopy(entry["data"])
                result["mode"] = "CACHED - IMD"
                result["cache_age_seconds"] = int(now - entry["fetched_at"])
                for r in result["records"]:
                    r["mode"] = "CACHED - IMD"
                    r["cache_age_seconds"] = int(now - entry["fetched_at"])
                return result

        try:
            # The official mausam.imd.gov.in/api PHP endpoints do not universally support
            # Bearer tokens or state/district query string filters.
            # We fetch the bulk dataset and filter locally.
            response = requests.get(f"{self.base_url}/{endpoint}", timeout=10)
            response.raise_for_status()
            raw_data = response.json()

            records = [self._normalize_record(r, product) for r in raw_data.get("records", [])]
            
            # Apply filters locally since the upstream API does not support them in the query string
            state = params.get("state")
            district = params.get("district")
            if state:
                records = [r for r in records if r.get("state", "").lower() == state.lower()]
            if district:
                records = [r for r in records if r.get("district", "").lower() == district.lower()]

            fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            result = {
                "status": "success",
                "provider": "IMD",
                "mode": "LIVE - IMD",
                "fetched_at": fetched_at,
                "records": records
            }

            self.cache[cache_key] = {
                "data": result,
                "fetched_at": now,
                "expires_at": now + self.cache_ttl
            }

            return result

        except requests.exceptions.RequestException as e:
            return {
                "status": "unavailable",
                "provider": "IMD",
                "mode": "ERROR",
                "error": str(e),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "records": []
            }

    def get_weather(self, state: str = None, district: str = None) -> Dict[str, Any]:
        params = {}
        if state: params["state"] = state
        if district: params["district"] = district
        return self._fetch_imd("current_wx_api.php", params, product="Current Observations")

    def get_warnings(self, state: str = None) -> Dict[str, Any]:
        params = {}
        if state: params["state"] = state
        return self._fetch_imd("warnings_district_api.php", params, product="District Warnings")

    def get_nowcast(self, district: str = None) -> Dict[str, Any]:
        params = {}
        if district: params["district"] = district
        return self._fetch_imd("nowcast_district_api.php", params, product="District Nowcast")

national_weather_service = IMDService()
