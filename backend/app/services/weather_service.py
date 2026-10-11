import requests
import datetime
import os

import time

class WeatherService:
    def __init__(self):
        # Default Hubballi coordinates if not provided via env
        self.lat = os.getenv("WEATHER_LAT", "15.3647")
        self.lon = os.getenv("WEATHER_LON", "75.1240")
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self._cached_weather = None
        self._cached_time = 0.0
        self._cached_forecast = None
        self._cached_forecast_time = 0.0

    # Successful observations are reused for 60 s. Failures are also remembered for
    # 30 s: hazard-aware routing asks for weather once per explored road segment, and
    # without a failure cache an outage meant tens of thousands of HTTP attempts per
    # route (each up to the 5 s timeout).
    SUCCESS_TTL_S = 60.0
    FAILURE_TTL_S = 30.0

    def get_current_weather(self):
        now = time.time()
        if self._cached_weather:
            ttl = self.SUCCESS_TTL_S if self._cached_weather.get("status") == "success" else self.FAILURE_TTL_S
            if (now - self._cached_time) < ttl:
                return self._cached_weather

        try:
            params = {
                "latitude": self.lat,
                "longitude": self.lon,
                "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
                "timezone": "auto"
            }
            # Timeout is important to avoid blocking the backend if Open-Meteo is down
            response = requests.get(self.base_url, params=params, timeout=5.0)
            response.raise_for_status()
            
            data = response.json()
            current = data.get("current", {})

            result = {
                "status": "success",
                "source": "Open-Meteo (LIVE DATA)",
                "location": {
                    "lat": float(self.lat),
                    "lon": float(self.lon),
                    "name": "Hubballi-Dharwad Region"
                },
                "timestamp": current.get("time", datetime.datetime.now().isoformat()),
                # Provider observation time in UTC (None when the provider omits it);
                # used to detect stale data. fetched_at_utc is when we received it.
                "observed_at_utc": self._observed_at_utc(current.get("time"), data.get("utc_offset_seconds")),
                "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "data": {
                    "temperature_c": current.get("temperature_2m"),
                    "precipitation_mm": current.get("precipitation"),
                    "wind_speed_kmh": current.get("wind_speed_10m"),
                    "weather_code": current.get("weather_code")
                }
            }
            self._cached_weather = result
            self._cached_time = now
            return result
        except requests.exceptions.RequestException as e:
            failure = {
                "status": "unavailable",
                "source": "Unknown",
                "location": {
                    "lat": float(self.lat),
                    "lon": float(self.lon),
                    "name": "Hubballi-Dharwad Region"
                },
                "timestamp": datetime.datetime.now().isoformat(),
                "error": str(e),
                "data": None
            }
            self._cached_weather = failure
            self._cached_time = now
            return failure

    @staticmethod
    def _observed_at_utc(local_time, utc_offset_seconds):
        """Convert Open-Meteo's local 'current.time' to an aware UTC ISO string."""
        if not local_time or utc_offset_seconds is None:
            return None
        try:
            naive = datetime.datetime.fromisoformat(local_time)
        except (TypeError, ValueError):
            return None
        utc = naive - datetime.timedelta(seconds=int(utc_offset_seconds))
        return utc.replace(tzinfo=datetime.timezone.utc).isoformat()

    def clear_cache(self):
        self._cached_weather = None
        self._cached_forecast = None
        self._cached_time = 0.0
        self._cached_forecast_time = 0.0

    def get_weather_forecast(self):
        now = time.time()
        if self._cached_forecast and (now - self._cached_forecast_time) < 120.0:
            return self._cached_forecast

        try:
            params = {
                "latitude": self.lat,
                "longitude": self.lon,
                "current": "temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m,weather_code",
                "hourly": "temperature_2m,precipitation,rain,precipitation_probability,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,precipitation_probability_max,weather_code",
                "timezone": "auto",
                "forecast_days": 3
            }
            response = requests.get(self.base_url, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()

            curr = data.get("current", {})
            hourly = data.get("hourly", {})
            daily = data.get("daily", {})

            times = hourly.get("time", [])
            probs = hourly.get("precipitation_probability", [])
            rains = hourly.get("rain", [])
            precips = hourly.get("precipitation", [])
            temps = hourly.get("temperature_2m", [])
            codes = hourly.get("weather_code", [])

            # Locate current forecast hour (single source of truth for hourly indexing)
            current_hour_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
            start_idx = 0
            for idx, t in enumerate(times):
                if t >= current_hour_str:
                    start_idx = idx
                    break

            def _point(i):
                # Missing provider values stay None (unknown); never substitute 0 mm / 0 %.
                def val(series, cast=float, ndigits=1):
                    if i < len(series) and series[i] is not None:
                        return round(cast(series[i]), ndigits) if ndigits is not None else series[i]
                    return None
                return {
                    "time": times[i],
                    "rain_probability_pct": val(probs, ndigits=None),
                    "expected_rain_mm": val(rains),
                    "precipitation_mm": val(precips),
                    "temperature_c": val(temps, ndigits=None),
                    "weather_code": val(codes, ndigits=None),
                }

            hourly_points = [_point(i) for i in range(start_idx, min(start_idx + 48, len(times)))]

            h6 = hourly_points[:6]
            h24 = hourly_points[:24]

            def _known(points, key):
                return [p[key] for p in points if p[key] is not None]

            # Aggregates use known hours only; missing hours are counted and reported.
            max_prob_6h = max(_known(h6, "rain_probability_pct"), default=0)
            expected_rain_6h = round(sum(_known(h6, "expected_rain_mm")), 1)
            max_prob_24h = max(_known(h24, "rain_probability_pct"), default=0)
            expected_rain_24h = round(sum(_known(h24, "expected_rain_mm")), 1)
            missing_6h = sum(1 for p in h6 if p["rain_probability_pct"] is None or p["expected_rain_mm"] is None)
            missing_6h += max(0, 6 - len(h6))

            # Preparedness & incident integration using existing incident_service
            from .incidents.incident_service import incident_service
            if len(incident_service.incidents) == 0:
                incident_service.scan_for_incidents()

            active_incidents = [inc for inc in incident_service.get_all() if inc.get("status") not in ["RESOLVED", "CLOSED"]]

            drainage_incidents = []
            waterlogging_incidents = []
            for inc in active_incidents:
                htype = (inc.get("hazard_type") or "").lower()
                title = (inc.get("title") or "").lower()

                if "drain" in htype or "culvert" in htype or "spillway" in htype or "drain" in title or "culvert" in title:
                    drainage_incidents.append(inc)
                elif "waterlog" in htype or "flood" in htype or "inundat" in htype or "waterlog" in title or "flood" in title:
                    waterlogging_incidents.append(inc)

            active_drainage_issues = len(drainage_incidents) + len(waterlogging_incidents)

            if max_prob_6h >= 85 and expected_rain_6h >= 25.0 and active_drainage_issues >= 2:
                prep_level = "CRITICAL PREPAREDNESS"
                prep_badge = "CRITICAL"
                prep_reason = f"Critical precipitation forecast signal ({max_prob_6h}% probability, {expected_rain_6h}mm expected in 6h) with {len(drainage_incidents)} drainage channel issues and {len(waterlogging_incidents)} active waterlogged sectors."
            elif max_prob_6h >= 75 or (expected_rain_6h >= 10.0 and active_drainage_issues > 0):
                prep_level = "HIGH PREPAREDNESS"
                prep_badge = "HIGH"
                prep_reason = f"High precipitation probability ({max_prob_6h}% in next 6h) coincides with {active_drainage_issues} active municipal drainage & road access vulnerabilities."
            elif max_prob_6h >= 50 or expected_rain_6h >= 5.0:
                prep_level = "PREPARE"
                prep_badge = "MODERATE"
                prep_reason = f"Moderate rainfall forecast ({max_prob_6h}% probability, {expected_rain_6h}mm expected in 6h). Pre-rain municipal inspection recommended for {active_drainage_issues} monitored sectors."
            elif max_prob_6h >= 25:
                prep_level = "WATCH"
                prep_badge = "WATCH"
                prep_reason = f"Low-to-moderate rain signal ({max_prob_6h}% max probability in 6h). Continuous EOC tracking active across {active_drainage_issues} monitored sectors."
            else:
                prep_level = "NORMAL"
                prep_badge = "NORMAL"
                prep_reason = f"Low rain probability ({max_prob_6h}%) over next 6 hours. Routine drainage monitoring active for {active_drainage_issues} monitored sectors."

            if missing_6h:
                prep_reason += (f" NOTE: {missing_6h} of the next 6 hourly values are missing from the provider; "
                                "6h figures cover known hours only and may understate rainfall.")

            recommendations = [
                "Inspect known drainage overflow locations (Gokul Road, Keshwapur, Dharwad Central).",
                "Clear reported open drainage blockages before rain onset.",
                "Inspect vulnerable culverts & low-lying road corridors.",
                "Pre-position field response teams in high-susceptibility sectors.",
                "Monitor low-lying road corridors & prepare alternate routes.",
                "Reassess operational stance after rainfall begins."
            ]

            result = {
                "status": "success",
                "source": "Open-Meteo (LIVE FORECAST)",
                "is_controlled_scenario": False,
                "location": {
                    "lat": float(self.lat),
                    "lon": float(self.lon),
                    "name": "Hubballi-Dharwad Municipal Region"
                },
                "timestamp": datetime.datetime.now().isoformat(),
                "current": {
                    "temperature_c": curr.get("temperature_2m"),
                    "precipitation_mm": curr.get("precipitation"),
                    "humidity_pct": curr.get("relative_humidity_2m"),
                    "wind_speed_kmh": curr.get("wind_speed_10m"),
                    "weather_code": curr.get("weather_code")
                },
                "summary": {
                    "max_prob_6h": max_prob_6h,
                    "expected_rain_6h_mm": expected_rain_6h,
                    "max_prob_24h": max_prob_24h,
                    "expected_rain_24h_mm": expected_rain_24h,
                    "preparedness_level": prep_level,
                    "preparedness_badge": prep_badge,
                    "preparedness_reason": prep_reason,
                    "active_drainage_issues": active_drainage_issues,
                    "active_drainage_incidents": len(drainage_incidents),
                    "active_waterlogging_incidents": len(waterlogging_incidents),
                    "missing_hourly_values_6h": missing_6h,
                    "data_complete_6h": missing_6h == 0,
                    "recommendations": recommendations
                },
                "hourly": hourly_points,
                "daily": daily
            }

            self._cached_forecast = result
            self._cached_forecast_time = now
            return result
        except requests.exceptions.RequestException as e:
            return {
                "status": "unavailable",
                "source": "Unknown",
                "is_controlled_scenario": False,
                "error": f"WEATHER DATA TEMPORARILY UNAVAILABLE: {str(e)}",
                "timestamp": datetime.datetime.now().isoformat()
            }

weather_service = WeatherService()

