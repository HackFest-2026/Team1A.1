"""Combining hazard components without inflating partial evidence.

A hazard score is a weighted sum of components (weather 0.6, terrain 0.4). When a
component is unknown (missing or stale data) its contribution is UNKNOWN, not zero
and not maximal:

- ``score`` is the sum of the *known* weighted components (a lower bound);
- ``score_upper_bound`` adds the largest value the unknown components could add;
- ``completeness`` is the weight share of components that were known (0-1);
- ``level`` classifies the known score; ``level_range`` shows how far it could move;
- ``confidence`` falls to LIMITED (partial) or UNAVAILABLE (nothing known).

Weights and thresholds are uncalibrated prototype heuristics.
"""
from typing import Dict, Iterable, List, Optional

WEATHER_WEIGHT = 0.60
TERRAIN_WEIGHT = 0.40

# (exclusive upper bound, label): 0-24 SAFE, 25-49 LOW, 50-74 HIGH, 75-100 CRITICAL
CLASSIFICATION_THRESHOLDS = [(25, "SAFE"), (50, "LOW"), (75, "HIGH"), (101, "CRITICAL")]
UNKNOWN_LEVEL = "UNKNOWN"


def classify(score: float) -> str:
    for threshold, label in CLASSIFICATION_THRESHOLDS:
        if score < threshold:
            return label
    return "CRITICAL"


def combine(weather_score: Optional[float], terrain_score: Optional[float],
            data_gaps: Iterable[str] = ()) -> Dict:
    known_weight = 0.0
    score = 0.0
    if weather_score is not None:
        score += WEATHER_WEIGHT * max(0.0, min(100.0, weather_score))
        known_weight += WEATHER_WEIGHT
    if terrain_score is not None:
        score += TERRAIN_WEIGHT * max(0.0, min(100.0, terrain_score))
        known_weight += TERRAIN_WEIGHT

    gaps = list(data_gaps)
    if known_weight == 0.0:
        return {
            "score": None,
            "level": UNKNOWN_LEVEL,
            "score_upper_bound": 100.0,
            "level_range": ["SAFE", "CRITICAL"],
            "completeness": 0.0,
            "score_basis": "NONE",
            "confidence": "UNAVAILABLE",
            "data_gaps": gaps,
        }

    upper = score + 100.0 * (1.0 - known_weight)
    complete = known_weight >= 0.999
    return {
        "score": round(score, 2),
        "level": classify(score),
        "score_upper_bound": round(upper, 2),
        "level_range": [classify(score), classify(upper)],
        "completeness": round(known_weight, 2),
        "score_basis": "COMPLETE" if complete else "PARTIAL",
        "confidence": "MEDIUM" if complete else "LIMITED",
        "data_gaps": gaps,
    }


def summarize_risks(risks: List[Dict]) -> Dict:
    """Route-level completeness from per-segment ``risk`` dicts produced by combine()."""
    total = len(risks)
    complete = sum(1 for r in risks if r.get("score_basis") == "COMPLETE")
    unknown = sum(1 for r in risks if r.get("score_basis") == "NONE")
    partial = total - complete - unknown
    gaps = sorted({g for r in risks for g in r.get("data_gaps", [])})
    if total and complete == total:
        confidence, basis = "MEDIUM", "COMPLETE"
    elif total and unknown == total:
        confidence, basis = "UNAVAILABLE", "NONE"
    else:
        confidence, basis = ("LIMITED", "PARTIAL") if total else ("UNAVAILABLE", "NONE")
    return {
        "score_basis": basis,
        "confidence": confidence,
        "score_upper_bound": max((r.get("score_upper_bound", 0.0) for r in risks), default=0.0),
        "data_completeness": {
            "segments_total": total,
            "segments_complete": complete,
            "segments_partial": partial,
            "segments_unknown": unknown,
            "data_gaps": gaps,
        },
    }
