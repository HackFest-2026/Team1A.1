import time
from typing import Dict, Any, List, Optional
from ..config.risk_config import (
    BASE_WEIGHTS, get_risk_level, map_warning_score, map_rainfall_score,
    map_nowcast_score, map_observation_score
)
from .national_weather_service import national_weather_service

from dateutil import parser as date_parser

class NationalRiskService:
    def __init__(self):
        pass

    def _parse_timestamp(self, ts_str: Optional[str]) -> float:
        if not ts_str:
            return None
        try:
            dt = date_parser.parse(ts_str)
            return dt.timestamp()
        except:
            return None

    def _determine_freshness(self, age_seconds: int) -> str:
        if age_seconds < 1800: # 30 min
            return "FRESH"
        elif age_seconds < 7200: # 2 hours
            return "AGING"
        return "STALE"

    def _determine_confidence(self, available_signals: int, freshness: str) -> str:
        if available_signals == 0:
            return "UNKNOWN"
        if available_signals >= 3 and freshness == "FRESH":
            return "HIGH"
        if available_signals >= 2 and freshness != "STALE":
            return "MEDIUM"
        return "LOW"

    def _aggregate_region(self, district: str, state: str, weather: dict, warning: dict, nowcast: dict) -> dict:
        components = {
            "observation": {"score": None, "value": None},
            "nowcast": {"score": None, "value": None},
            "warning": {"score": None, "value": None},
            "rainfall": {"score": None, "value": None},
            "forecast": {"score": None, "value": None}
        }
        
        drivers = []
        
        # Populate components
        if weather:
            w_code = weather.get("weather", {}).get("weather_code")
            precip = weather.get("weather", {}).get("precipitation_mm")
            if precip is None:
                precip = weather.get("weather", {}).get("last_24h_rainfall_mm")
            
            obs_score = map_observation_score(w_code)
            if obs_score is not None:
                components["observation"]["score"] = obs_score
                components["observation"]["value"] = w_code
            
            rain_score = map_rainfall_score(precip)
            if rain_score is not None:
                components["rainfall"]["score"] = rain_score
                components["rainfall"]["value"] = precip
        
        official_warning = None
        if warning:
            w_level = warning.get("warning", {}).get("level")
            official_warning = warning.get("warning")
            w_score = map_warning_score(w_level)
            if w_score is not None:
                components["warning"]["score"] = w_score
                components["warning"]["value"] = w_level
                if w_score > 0:
                    drivers.append(f"Official IMD warning present ({w_level})")

        if nowcast:
            n_text = nowcast.get("warning", {}).get("text") or nowcast.get("warning", {}).get("type")
            n_score = map_nowcast_score(n_text)
            if n_score is not None:
                components["nowcast"]["score"] = n_score
                components["nowcast"]["value"] = n_text
                if n_score >= 50:
                    drivers.append(f"District nowcast indicates elevated risk ({n_text})")

        if components["rainfall"]["score"] and components["rainfall"]["score"] >= 50:
            drivers.append("Recent rainfall is elevated")
        if components["observation"]["score"] and components["observation"]["score"] >= 50:
            drivers.append("Observation indicates active weather")

        # Renormalize weights
        total_weight = 0
        available = 0
        for k, v in components.items():
            if v["score"] is not None:
                total_weight += BASE_WEIGHTS[k]
                available += 1

        effective_weights = {}
        final_score = 0
        
        if total_weight > 0:
            for k, v in components.items():
                if v["score"] is not None:
                    eff = BASE_WEIGHTS[k] / total_weight
                    effective_weights[k] = eff
                    final_score += v["score"] * eff
        else:
            final_score = None

        if not drivers and final_score is not None and final_score >= 20:
            drivers.append("Cumulative low-level indicators")
        elif not drivers:
            drivers.append("No active risk drivers")

        # Calculate freshness based on actual provider timestamps if possible
        ages = []
        current_time = time.time()
        for r in [weather, warning, nowcast]:
            if r:
                ts_str = r.get("observation_time") or r.get("issued_time")
                parsed_ts = self._parse_timestamp(ts_str)
                if parsed_ts:
                    ages.append(max(0, current_time - parsed_ts))
                elif "cache_age_seconds" in r:
                    ages.append(r["cache_age_seconds"])
        
        max_age = max(ages) if ages else 0
        freshness = self._determine_freshness(max_age)
        confidence = self._determine_confidence(available, freshness)

        # Base ID and coords on available records
        base_record = weather or warning or nowcast or {}

        # Future forecast availability
        forecast_horizon_now = final_score
        forecast_horizon_1h = components["nowcast"]["score"] if components["nowcast"]["score"] is not None else None
        
        return {
            "id": base_record.get("id", f"{state}-{district}"),
            "state": state,
            "district": district,
            "city": weather.get("city") if weather else None,
            "latitude": weather.get("latitude") if weather else None,
            "longitude": weather.get("longitude") if weather else None,
            "risk": {
                "score": round(final_score) if final_score is not None else None,
                "level": get_risk_level(round(final_score)) if final_score is not None else "UNKNOWN"
            },
            "official_warning": official_warning,
            "components": components,
            "effective_weights": effective_weights,
            "confidence": confidence,
            "freshness": freshness,
            "drivers": drivers,
            "_raw_horizons": {
                "NOW": round(forecast_horizon_now) if forecast_horizon_now is not None else None,
                "+1H": round(forecast_horizon_1h) if forecast_horizon_1h is not None else None
            }
        }

    def _get_data(self, state=None, district=None):
        weather_res = national_weather_service.get_weather(state, district)
        warning_res = national_weather_service.get_warnings(state)
        nowcast_res = national_weather_service.get_nowcast(district)
        
        if weather_res.get("mode") == "NOT_CONFIGURED":
            return {"status": "unavailable", "mode": "NOT_CONFIGURED", "regions": []}

        # Index by state/district
        regions = {}
        for w in weather_res.get("records", []):
            key = (w.get("state"), w.get("district"))
            if key not in regions: regions[key] = {"weather": None, "warning": None, "nowcast": None}
            regions[key]["weather"] = w
            
        for w in warning_res.get("records", []):
            key = (w.get("state"), w.get("district"))
            if key not in regions: regions[key] = {"weather": None, "warning": None, "nowcast": None}
            regions[key]["warning"] = w

        for n in nowcast_res.get("records", []):
            key = (n.get("state"), n.get("district"))
            if key not in regions: regions[key] = {"weather": None, "warning": None, "nowcast": None}
            regions[key]["nowcast"] = n

        return {"status": "success", "mode": weather_res.get("mode"), "regions_data": regions}

    def get_national_risk(self, state: Optional[str] = None, district: Optional[str] = None) -> Dict[str, Any]:
        data = self._get_data(state, district)
        if data.get("status") == "unavailable":
            return {
                "status": "success",
                "source": {"official_data": "IMD", "assessment": "ResilienceRoute"},
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "mode": data.get("mode"),
                "summary": {},
                "regions": []
            }

        out_regions = []
        summary = {
            "number_normal": 0, "number_watch": 0, "number_warning": 0,
            "number_high": 0, "number_critical": 0,
            "top_high_risk_regions": [], "top_critical_regions": []
        }

        for (st, dist), records in data["regions_data"].items():
            reg = self._aggregate_region(dist, st, records["weather"], records["warning"], records["nowcast"])
            out_regions.append(reg)
            lvl = reg["risk"]["level"]
            if lvl == "NORMAL": summary["number_normal"] += 1
            elif lvl == "WATCH": summary["number_watch"] += 1
            elif lvl == "WARNING": summary["number_warning"] += 1
            elif lvl == "HIGH": summary["number_high"] += 1
            elif lvl == "CRITICAL": summary["number_critical"] += 1

        # Sort for top lists
        valid_regions = [r for r in out_regions if r["risk"]["score"] is not None]
        valid_regions.sort(key=lambda x: x["risk"]["score"], reverse=True)
        
        summary["top_critical_regions"] = [r for r in valid_regions if r["risk"]["level"] == "CRITICAL"][:5]
        summary["top_high_risk_regions"] = [r for r in valid_regions if r["risk"]["level"] == "HIGH"][:5]

        # Cleanup internal keys
        for r in out_regions:
            r.pop("_raw_horizons", None)

        return {
            "status": "success",
            "source": {"official_data": "IMD", "assessment": "ResilienceRoute"},
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": data.get("mode"),
            "summary": summary,
            "regions": out_regions
        }

    def get_region_risk(self, region_id: str) -> Dict[str, Any]:
        risk_data = self.get_national_risk()
        if risk_data.get("status") == "unavailable" or not risk_data.get("regions"):
            return risk_data
        for r in risk_data["regions"]:
            if r["id"] == region_id:
                return r
        return {"error": "Region not found"}

    def get_forecast(self) -> Dict[str, Any]:
        data = self._get_data()
        if data.get("status") == "unavailable":
            return {"status": "unavailable", "mode": data.get("mode")}
        
        results = []
        for (st, dist), records in data["regions_data"].items():
            reg = self._aggregate_region(dist, st, records["weather"], records["warning"], records["nowcast"])
            horizons = {}
            raw_h = reg.pop("_raw_horizons")
            
            if raw_h["NOW"] is not None:
                horizons["NOW"] = {"forecast_available": True, "status": "AVAILABLE", "score": raw_h["NOW"], "level": get_risk_level(raw_h["NOW"])}
            else:
                horizons["NOW"] = {"forecast_available": False, "status": "UNAVAILABLE"}
                
            if raw_h["+1H"] is not None:
                horizons["+1H"] = {"forecast_available": True, "status": "AVAILABLE", "score": raw_h["+1H"], "level": get_risk_level(raw_h["+1H"])}
            else:
                horizons["+1H"] = {"forecast_available": False, "status": "UNAVAILABLE"}
                
            for h in ["+3H", "+6H", "+12H", "+24H"]:
                horizons[h] = {"forecast_available": False, "status": "UNAVAILABLE"}

            results.append({
                "region_id": reg["id"],
                "horizons": horizons
            })
            
        return {"status": "success", "results": results}

national_risk_service = NationalRiskService()
