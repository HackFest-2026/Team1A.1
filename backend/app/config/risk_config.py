from typing import Dict, Any, List, Tuple

# Base weights for National Risk Assessment
BASE_WEIGHTS = {
    "observation": 20,
    "nowcast": 25,
    "warning": 25,
    "rainfall": 20,
    "forecast": 10
}

# ResilienceRoute Risk Thresholds
RISK_THRESHOLDS = [
    (19, "NORMAL"),
    (39, "WATCH"),
    (59, "WARNING"),
    (79, "HIGH"),
    (100, "CRITICAL")
]

def get_risk_level(score: float) -> str:
    for upper_bound, level in RISK_THRESHOLDS:
        if score <= upper_bound:
            return level
    return "CRITICAL"

# Official IMD Warning Mappings
WARNING_MAPPING = {
    "no warning": 0,
    "watch": 25,
    "alert": 50,
    "warning": 75,
    "yellow": 25,
    "orange": 50,
    "red": 75,
    "green": 0
}

def map_warning_score(level_str: str) -> float:
    if not level_str:
        return None
    val = level_str.lower().strip()
    return WARNING_MAPPING.get(val, None)

# Rainfall Scoring Heuristic
# Semantic: This explicitly represents 24-hour cumulative rainfall (last_24h_rainfall_mm).
# It does NOT represent instantaneous precipitation rate.
# 0mm = 0 Risk. >0 to <10mm = 20 Risk. >=60mm = 100 Risk.
def map_rainfall_score(precip_24h_mm: float) -> float:
    if precip_24h_mm is None:
        return None
    if precip_24h_mm <= 0:
        return 0
    elif precip_24h_mm < 10:
        return 20
    elif precip_24h_mm < 30:
        return 50
    elif precip_24h_mm < 60:
        return 75
    else:
        return 100

# Nowcast Scoring Heuristic
NOWCAST_MAPPING = {
    "light rain": 20,
    "moderate rain": 50,
    "heavy rain": 75,
    "thunderstorm": 60,
    "severe thunderstorm": 90,
    "no warning": 0,
    "cloudy": 10,
    "clear": 0
}

def map_nowcast_score(text: str) -> float:
    if not text:
        return None
    val = text.lower().strip()
    for k, v in NOWCAST_MAPPING.items():
        if k in val:
            return v
    return None

def map_observation_score(weather_code: str) -> float:
    if not weather_code:
        return None
    val = weather_code.lower().strip()
    if "rain" in val or "storm" in val:
        return 50
    if "clear" in val or "sunny" in val:
        return 0
    if "cloud" in val:
        return 10
    return None
