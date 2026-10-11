"""Maritime vessel intelligence, tracking, size estimation, and AIS correlation."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from app.services.vision.types import (
    Detection,
    ModelProvenance,
    TrackedVessel,
)


class MaritimeVesselIntelligence:
    """Consolidates vessel tracking, kinematic trajectory, and AIS correlation."""

    def get_provenance(self) -> ModelProvenance:
        return ModelProvenance(
            name="AEGIS Maritime Kinematics & Vessel Intelligence Engine",
            version="1.0-correlator",
            task="VESSEL_INTELLIGENCE",
            device="cpu",
            status="ready",
            supported_classes=["boat", "small_craft", "large_vessel"],
            notes=(
                "ByteTrack kinematic trajectory aggregator with uncalibrated visual "
                "size categorizer and AISStream integration."
            ),
        )

    def process_tracks(
        self,
        frame_detections: List[Dict[str, Any]],
        video_width: int,
        video_height: int,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        operator_ais_status: str = "unknown",
    ) -> List[TrackedVessel]:
        """Aggregates per-frame vessel and person detections into vessel profiles."""
        vessel_tracks: Dict[int, Dict[str, Any]] = {}
        frame_area = max(1, video_width * video_height)

        for f_data in frame_detections:
            t_sec = f_data["timestamp_seconds"]
            dets = f_data["detections"]

            vessel_dets = [
                d for d in dets
                if (d.get("category") if isinstance(d, dict) else d.category) == "vessel"
                and (d.get("track_id") if isinstance(d, dict) else d.track_id) is not None
            ]
            person_dets = [
                d for d in dets
                if (d.get("category") if isinstance(d, dict) else d.category) == "person"
            ]

            for v in vessel_dets:
                tr_id = v.get("track_id") if isinstance(v, dict) else v.track_id
                v_label = v.get("label") if isinstance(v, dict) else v.label
                v_conf = v.get("confidence") if isinstance(v, dict) else v.confidence
                v_bbox = v.get("bbox") if isinstance(v, dict) else v.bbox

                if tr_id not in vessel_tracks:
                    vessel_tracks[tr_id] = {
                        "track_id": tr_id,
                        "vessel_class": v_label,
                        "confidences": [v_conf],
                        "first_seen_s": t_sec,
                        "last_seen_s": t_sec,
                        "history": [],
                        "max_people_onboard": 0,
                        "areas": [],
                    }

                vt = vessel_tracks[tr_id]
                vt["confidences"].append(v_conf)
                vt["last_seen_s"] = t_sec

                x1, y1, x2, y2 = v_bbox
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                bbox_area = max(1.0, (x2 - x1) * (y2 - y1))
                norm_area = bbox_area / frame_area
                vt["areas"].append(norm_area)

                vt["history"].append({
                    "timestamp_seconds": t_sec,
                    "bbox": v_bbox,
                    "center_xy": [round(cx, 1), round(cy, 1)],
                })

                # Check person-on-vessel geometric overlap
                people_on_this_vessel = 0
                for p in person_dets:
                    px1, py1, px2, py2 = p.get("bbox") if isinstance(p, dict) else p.bbox
                    pcx = (px1 + px2) / 2.0
                    pcy = (py1 + py2) / 2.0
                    if (x1 - 10) <= pcx <= (x2 + 10) and (y1 - 25) <= pcy <= (y2 + 5):
                        people_on_this_vessel += 1

                if people_on_this_vessel > vt["max_people_onboard"]:
                    vt["max_people_onboard"] = people_on_this_vessel

        # Correlate with AIS if coordinates available
        ais_match_info = self._correlate_ais(latitude, longitude, operator_ais_status)

        results: List[TrackedVessel] = []
        for tr_id, vt in sorted(vessel_tracks.items(), key=lambda kv: kv[0]):
            avg_conf = sum(vt["confidences"]) / len(vt["confidences"])
            avg_area = sum(vt["areas"]) / len(vt["areas"])

            # Size categorization (uncalibrated visual heuristic)
            if avg_area >= 0.08:
                size_cat = "large_vessel"
            else:
                size_cat = "small_craft"

            # Compute velocity proxy and bearing
            speed_proxy = 0.0
            bearing_deg = None
            if len(vt["history"]) >= 2:
                p0 = vt["history"][0]
                p_last = vt["history"][-1]
                dt = p_last["timestamp_seconds"] - p0["timestamp_seconds"]
                if dt > 0.1:
                    dx = p_last["center_xy"][0] - p0["center_xy"][0]
                    dy = p_last["center_xy"][1] - p0["center_xy"][1]
                    dist_px = math.hypot(dx, dy)
                    speed_proxy = dist_px / dt
                    rad = math.atan2(dx, -dy)
                    bearing_deg = (math.degrees(rad) + 360.0) % 360.0

            results.append(
                TrackedVessel(
                    track_id=tr_id,
                    vessel_class=vt["vessel_class"],
                    size_category=size_cat,
                    confidence=avg_conf,
                    first_seen_s=vt["first_seen_s"],
                    last_seen_s=vt["last_seen_s"],
                    track_history=vt["history"],
                    speed_proxy_pixels_sec=speed_proxy,
                    course_bearing_deg=bearing_deg,
                    people_observed_onboard=vt["max_people_onboard"],
                    ais_correlation=ais_match_info,
                )
            )

        return results

    def _correlate_ais(
        self,
        lat: Optional[float],
        lon: Optional[float],
        operator_ais_status: str,
    ) -> Dict[str, Any]:
        """Correlates video location and operator status with AIS contacts."""
        try:
            from app.services.ais_service import ais_service
            live_vessels = ais_service.list_vessels()
        except Exception:
            live_vessels = []

        if lat is not None and lon is not None and live_vessels:
            # Find nearest AIS contact
            nearest = None
            min_dist_km = 99999.0
            for v in live_vessels:
                v_lat = v.get("latitude")
                v_lon = v.get("longitude")
                if v_lat is not None and v_lon is not None:
                    # Approx equirectangular distance
                    d_km = math.hypot((v_lat - lat) * 111.0, (v_lon - lon) * 111.0 * math.cos(math.radians(lat)))
                    if d_km < min_dist_km:
                        min_dist_km = d_km
                        nearest = v

            if nearest and min_dist_km < 35.0:  # Within 35 km maritime radar horizon
                return {
                    "status": "matched" if not nearest.get("is_dark_vessel") else "dark_vessel_candidate",
                    "matched_mmsi": nearest.get("mmsi"),
                    "matched_name": nearest.get("name"),
                    "vessel_type": nearest.get("vessel_type"),
                    "distance_km": round(min_dist_km, 1),
                    "notes": f"Correlated with nearby AIS contact {nearest.get('name')} ({nearest.get('mmsi')}).",
                }

        # Fallback to operator supplied AIS status
        notes_map = {
            "matched": "Operator indicated AIS identity was confirmed with shore station.",
            "missing": "No matching AIS signal reported. Missing AIS alone does not imply hostile intent (may be small craft without transponder, signal obstruction, or malfunction).",
            "mismatch": "Reported AIS data does not match visual vessel type or position. Requires inspection.",
            "unknown": "AIS correlation not verified for this observation.",
        }

        return {
            "status": operator_ais_status,
            "matched_mmsi": None,
            "matched_name": None,
            "distance_km": None,
            "notes": notes_map.get(operator_ais_status, "AIS correlation unverified."),
        }
