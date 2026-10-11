"""Explainable potential-threat triage and surveillance review for AEGIS-COP.

Scores review priority and flags events requiring human validation,
NOT probabilities of hostile intent.
Context indicators are unverified unless supplied by trusted integrations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

VESSEL_LABELS = {
    "boat",
    "ship",
    "vessel",
    "motorboat",
    "sailboat",
    "small_craft",
    "large_vessel",
}


def assess_potential_threat(
    detections_by_class: dict[str, int],
    *,
    restricted_zone_entry: bool = False,
    ais_status: str = "unknown",
    unusual_behavior_observed: bool = False,
    near_protected_asset: bool = False,
    events: Optional[List[Dict[str, Any]]] = None,
    vessel_intelligence: Optional[List[Dict[str, Any]]] = None,
    suspicious_objects: Optional[List[Dict[str, Any]]] = None,
    fire_smoke_data: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return an explainable review-priority assessment separating observation from risk interpretation."""

    if ais_status not in {"unknown", "matched", "missing", "mismatch"}:
        ais_status = "unknown"

    vessel_count = sum(
        max(0, int(count))
        for label, count in detections_by_class.items()
        if str(label).strip().lower() in VESSEL_LABELS
    )

    score = 0
    indicators: list[dict[str, Any]] = []

    # 1. Visual Object Detection Observation
    if vessel_count > 0:
        indicators.append({
            "code": "VESSEL_VISUAL_DETECTION",
            "points": 0,
            "evidence": (
                f"The vision pipeline reported {vessel_count} "
                "unique or untracked vessel observations. "
                "Visual classification has not been independently verified."
            ),
            "source": "computer_vision",
            "status": "unverified",
        })

    # 2. Contextual indicators
    if restricted_zone_entry:
        score += 40
        indicators.append({
            "code": "RESTRICTED_ZONE_ENTRY",
            "points": 40,
            "evidence": (
                "Restricted-zone entry was reported. Verify the "
                "geospatial boundary, location, and timestamp."
            ),
            "source": "operator_or_geospatial_adapter",
            "status": "reported",
        })

    if ais_status == "mismatch":
        score += 25
        indicators.append({
            "code": "AIS_IDENTITY_MISMATCH",
            "points": 25,
            "evidence": (
                "An AIS identity or position mismatch was reported. "
                "Verify against a trusted AIS source and timestamps. "
                "AIS mismatch alone does not establish hostile intent."
            ),
            "source": "AIS_context",
            "status": "reported",
        })
    elif ais_status == "missing":
        score += 12
        indicators.append({
            "code": "AIS_SIGNAL_MISSING",
            "points": 12,
            "evidence": (
                "No AIS match was reported. Missing AIS alone "
                "does not establish hostile intent (may be small vessel without transponder, "
                "signal blockage, or transponder malfunction)."
            ),
            "source": "AIS_context",
            "status": "reported",
        })

    if unusual_behavior_observed:
        score += 20
        indicators.append({
            "code": "UNUSUAL_BEHAVIOR",
            "points": 20,
            "evidence": (
                "Unusual behavior was reported. Review the supporting "
                "footage; this is not an automatically verified finding."
            ),
            "source": "operator_or_behavior_model",
            "status": "reported",
        })

    if near_protected_asset:
        score += 15
        indicators.append({
            "code": "PROXIMITY_TO_PROTECTED_ASSET",
            "points": 15,
            "evidence": (
                "Proximity to a protected asset was reported. "
                "Verify coordinates and the relevant geospatial data."
            ),
            "source": "operator_or_geospatial_adapter",
            "status": "reported",
        })

    # 3. Kinetic Projectile & Missile Trajectory Analysis
    has_missile_event = False
    PROJECTILE_LABELS = {
        "missile_trajectory",
        "anti_ship_missile",
        "high_speed_projectile",
        "projectile",
    }
    projectile_count = sum(
        max(0, int(count))
        for label, count in detections_by_class.items()
        if str(label).strip().lower() in PROJECTILE_LABELS
    )

    if events:
        for ev in events:
            ev_type = ev.get("event_type", "")
            if ev_type in {"missile_inbound_alert", "missile_strike_event"}:
                has_missile_event = True
                score += 65
                indicators.append({
                    "code": "MISSILE_TRAJECTORY_DETECTED",
                    "points": 65,
                    "evidence": (
                        f"Kinetic projectile tracker identified high-speed missile trajectory "
                        f"(confidence {ev.get('confidence', 0):.2f}) at "
                        f"{ev.get('start_time_s', 0):.1f}s - {ev.get('end_time_s', 0):.1f}s. "
                        "URGENT OPERATOR REVIEW REQUIRED. Immediate combat direction system (CDS) review recommended."
                    ),
                    "source": "projectile_tracker",
                    "status": "detected",
                })

    if projectile_count > 0 and not has_missile_event:
        has_missile_event = True
        score += 60
        indicators.append({
            "code": "PROJECTILE_VISUAL_DETECTION",
            "points": 60,
            "evidence": (
                f"The vision pipeline reported {projectile_count} kinetic projectile / missile trajectory observations. "
                "Immediate operator review required."
            ),
            "source": "projectile_tracker",
            "status": "detected",
        })

    # 4. Dedicated Fire / Smoke & Explosion analysis
    has_explosion_event = False
    if events:
        for ev in events:
            if ev.get("event_type") == "possible_explosion_event":
                has_explosion_event = True
                score += 50
                indicators.append({
                    "code": "POSSIBLE_EXPLOSION_EVENT",
                    "points": 50,
                    "evidence": (
                        f"Temporal event classifier detected radiant flux burst "
                        f"(confidence {ev.get('confidence', 0):.2f}) at "
                        f"{ev.get('start_time_s', 0):.1f}s - {ev.get('end_time_s', 0):.1f}s. "
                        "URGENT OPERATOR REVIEW REQUIRED. Optical feeds cannot confirm munitions detonation."
                    ),
                    "source": "video_event_classifier",
                    "status": "possible_event",
                })

    if fire_smoke_data:
        if fire_smoke_data.get("fire_detected"):
            score += 30
            indicators.append({
                "code": "FIRE_INCIDENT_DETECTED",
                "points": 30,
                "evidence": (
                    "Active combustion core or flame spectrum detected. "
                    "Operator review recommended for maritime hazard response."
                ),
                "source": "fire_smoke_analyzer",
                "status": "detected",
            })
        elif fire_smoke_data.get("smoke_detected"):
            if fire_smoke_data.get("exhaust_smoke_only"):
                indicators.append({
                    "code": "VESSEL_EXHAUST_SMOKE",
                    "points": 0,
                    "evidence": (
                        "Engine exhaust / stack emission observed originating above vessel hull. "
                        "Not classified as active fire or hostile action."
                    ),
                    "source": "fire_smoke_analyzer",
                    "status": "requires_review",
                })
            else:
                score += 15
                indicators.append({
                    "code": "SMOKE_PLUME_DETECTED",
                    "points": 15,
                    "evidence": (
                        "Atmospheric smoke plume detected. Review footage to assess origin."
                    ),
                    "source": "fire_smoke_analyzer",
                    "status": "possible_event",
                })

    # 4. Suspicious Object Review
    if suspicious_objects:
        score += 10
        indicators.append({
            "code": "UNVERIFIED_SUSPICIOUS_OBJECT",
            "points": 10,
            "evidence": (
                f"{len(suspicious_objects)} unattended package(s) or unidentified object(s) "
                "flagged for physical inspection. Not verified as hazardous or explosive."
            ),
            "source": "safety_review_model",
            "status": "requires_review",
        })

    # Evidence-based Review Levels (Phase 5)
    if has_missile_event or (projectile_count > 0):
        review_level = "URGENT_HUMAN_REVIEW"
        level = "URGENT_HUMAN_REVIEW"
    elif has_explosion_event:
        review_level = "URGENT_HUMAN_REVIEW"
        level = "URGENT_HUMAN_REVIEW"
    elif fire_smoke_data and fire_smoke_data.get("fire_detected"):
        review_level = "ELEVATED_CONCERN"
        level = "HIGH_PRIORITY_REVIEW" if score >= 60 else "ELEVATED_REVIEW"
    elif vessel_count == 0:
        review_level = "REQUIRES_REVIEW" if score > 0 else "INSUFFICIENT_EVIDENCE"
        level = (
            "CONTEXT_REVIEW_REQUIRED"
            if score > 0
            else "INSUFFICIENT_VISUAL_EVIDENCE"
        )
    elif score >= 60:
        review_level = "ELEVATED_CONCERN"
        level = "HIGH_PRIORITY_REVIEW"
    elif score >= 30:
        review_level = "ELEVATED_CONCERN"
        level = "ELEVATED_REVIEW"
    elif score > 0:
        review_level = "REQUIRES_REVIEW"
        level = "REVIEW"
    else:
        review_level = "INFORMATIONAL"
        level = "NO_RULE_TRIGGERED"

    return {
        "assessment_type": "EXPLAINABLE_RULE_BASED_TRIAGE",
        "level": level,
        "review_level": review_level,
        "score": min(score, 100),
        "score_max": 100,
        "score_is_probability": False,
        "vessel_detections": vessel_count,
        "indicators": indicators,
        "ais_status": ais_status,
        "human_review_required": True,
        "limitations": [
            "Scores are configurable review-priority rules, not calibrated probabilities.",
            "Generic object detections can be false positives.",
            "AIS and contextual indicators are unverified unless connected to trusted sources.",
            "Visual object detection alone cannot establish hostile intent or military classification.",
            "Optical event classifiers cannot confirm high-explosive detonation without acoustic or dual-sensor corroboration.",
        ],
    }
