"""
Road Segment Hazard Intelligence Service — Phase 5A

Assesses flood hazard for individual OSM road edges by combining:
  - Real terrain evidence (ISRO/NRSC CartoDEM V3 R1 via terrain_service)
  - Live weather evidence (Open-Meteo via weather_service)

Sampling Strategy:
  - For each road edge, the actual OSM geometry is used when available.
  - When no geometry attribute exists, a straight line between the endpoint
    nodes is constructed from their (x, y) coordinates.
  - Adaptive sampling: minimum 3 points per segment (start, middle, end).
    For segments longer than 100m, one additional sample per 100m.
    Capped at 20 samples per segment.
  - Both endpoints are always included.
  - Points are interpolated at equal fractional distances along the
    LineString using ``line.interpolate(fraction, normalized=True)``.

Terrain Aggregation:
  segment_terrain_score = 0.70 × max_susceptibility + 0.30 × mean_susceptibility
  This captures potentially hazardous local portions (via max) while the mean
  represents broader segment conditions.
  NOTE: This is NOT a physically calibrated flood propagation model.

Final Hazard Score (see app/services/hazard_scoring.py):
  final_score = 0.60 × weather_score + 0.40 × segment_terrain_score
  Weather weight = 0.60, Terrain weight = 0.40
  A missing or stale component is UNKNOWN: it contributes nothing to the score
  (no re-weighting), the result is marked PARTIAL with reduced completeness and
  confidence, and score_upper_bound shows how high the full score could be.

Classification Thresholds:
   0–24  = SAFE
  25–49  = LOW
  50–74  = HIGH
  75–100 = CRITICAL
"""

import datetime
from shapely.geometry import LineString

from .terrain_service import terrain_service
from .weather_adapter import weather_adapter, WEATHER_AVAILABLE
from .routing_service import routing_service
from .hazard_scoring import combine


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TERRAIN_MAX_WEIGHT = 0.70
TERRAIN_MEAN_WEIGHT = 0.30

MIN_SAMPLES = 3
MAX_SAMPLES = 20
SAMPLE_INTERVAL_M = 100.0  # one extra sample per this many metres

PROVENANCE_TERRAIN = "ISRO/NRSC CartoDEM V3 R1 — D43D (LOCAL/CACHED DATA)"
PROVENANCE_ROAD = "OpenStreetMap (LOCAL/CACHED GRAPH)"


class RoadHazardService:
    """On-demand road-segment hazard assessment."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess_road_segment(self, u: int, v: int, key: int = 0) -> dict:
        """Assess hazard for a single OSM edge identified by (u, v, key).

        Returns a dict with road info, risk score/level, terrain evidence,
        weather evidence, reasons, confidence, and provenance.
        """
        # 1. Ensure graph is loaded
        graph = self._get_graph()

        # 2. Validate edge exists
        if not graph.has_edge(u, v, key=key):
            raise ValueError(
                f"Edge ({u}, {v}, key={key}) does not exist in the graph."
            )

        edge_data = graph.edges[u, v, key]

        # 3. Build line geometry
        line = self._edge_geometry(graph, u, v, edge_data)

        # 4. Sample points along the road
        sample_coords = self._sample_along_edge(line, edge_data.get("length", 0))

        # 5. Terrain evidence (one rasterio open per sample point)
        terrain_results = self._sample_terrain(sample_coords)
        terrain_agg = self._aggregate_terrain(terrain_results)

        # 6. Weather evidence (single API call)
        # sample_coords are (lon, lat) tuples per Shapely convention
        mid_lon, mid_lat = sample_coords[len(sample_coords)//2] if sample_coords else (None, None)
        weather_evidence = self._get_weather_evidence(lat=mid_lat, lon=mid_lon)

        # 7. Combine known components; unknown ones are reported, not re-weighted
        data_gaps = []
        if not weather_evidence["available"]:
            data_gaps.append(f"WEATHER_{weather_evidence['summary']['state']}")
        if not terrain_agg["available"]:
            data_gaps.append(f"TERRAIN_{terrain_agg.get('reason') or 'UNAVAILABLE'}")
        risk = combine(weather_evidence["weather_score"], terrain_agg["segment_score"], data_gaps)

        # 8. Explainability
        reasons = self._generate_reasons(terrain_agg, weather_evidence, risk)

        # 9. Build response
        return {
            "status": "success",
            "road": {
                "u": u,
                "v": v,
                "key": key,
                "length_m": round(edge_data.get("length", 0), 2),
                "name": edge_data.get("name", None),
                "highway": edge_data.get("highway", None),
            },
            "risk": risk,
            "terrain": terrain_agg["summary"],
            "weather": weather_evidence["summary"],
            "reasons": reasons,
            "confidence": risk["confidence"],
            "source": {
                "road": PROVENANCE_ROAD,
                "terrain": PROVENANCE_TERRAIN,
                "weather": (
                    weather_evidence["summary"]["source"]
                    if weather_evidence["available"]
                    else weather_evidence["summary"]["state"]
                ),
            },
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def assess_route(self, node_ids: list[int]) -> dict:
        """Assess an existing route's edge sequence segment-by-segment.
        
        This provides an internal capability to view hazard information
        along a path, without altering the route selection itself.
        """
        if not node_ids or len(node_ids) < 2:
            return {
                "route_nodes": node_ids,
                "segment_count": 0,
                "max_risk_score": 0.0,
                "max_risk_level": "SAFE",
                "segments": []
            }

        segments = []
        route_max_score = 0.0
        route_max_level = "SAFE"

        # Ensure the graph is loaded before iterating
        graph = self._get_graph()

        for i in range(len(node_ids) - 1):
            u = node_ids[i]
            v = node_ids[i+1]
            
            # Use the shortest travel time edge if multiple exist
            best_key = 0
            if graph.has_edge(u, v):
                edge_keys = graph[u][v].keys()
                # find the one with min travel_time
                best_key = min(edge_keys, key=lambda k: graph[u][v][k].get("travel_time", float('inf')))

            try:
                segment_info = self.assess_road_segment(u, v, key=best_key)
                segments.append({
                    "u": u,
                    "v": v,
                    "hazard": segment_info
                })
                score = segment_info.get("risk", {}).get("score") or 0.0
                if score > route_max_score:
                    route_max_score = score
                    route_max_level = segment_info.get("risk", {}).get("level", "SAFE")
            except ValueError:
                # If edge doesn't exist, we skip
                continue

        return {
            "route_nodes": node_ids,
            "segment_count": len(segments),
            "max_risk_score": route_max_score,
            "max_risk_level": route_max_level,
            "segments": segments
        }

    # ------------------------------------------------------------------
    # Graph access
    # ------------------------------------------------------------------

    def _get_graph(self):
        """Return the loaded graph, triggering load if necessary."""
        if not routing_service.load_graph():
            raise RuntimeError("Road graph is not available.")
        return routing_service.G

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _edge_geometry(graph, u: int, v: int, edge_data: dict) -> LineString:
        """Return the Shapely LineString for an edge.

        Uses the stored ``geometry`` attribute when present.  Otherwise
        constructs a straight segment from the endpoint node coordinates.
        """
        if "geometry" in edge_data:
            return edge_data["geometry"]

        # Fallback: straight line between node coordinates
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        return LineString([(u_data["x"], u_data["y"]), (v_data["x"], v_data["y"])])

    # ------------------------------------------------------------------
    # Adaptive sampling
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_along_edge(line: LineString, length_m: float) -> list[tuple[float, float]]:
        """Return evenly-spaced (lon, lat) sample points along *line*.

        Sampling strategy
        -----------------
        * Minimum 3 points per segment (start, middle, end).
        * For segments longer than 100 m: one additional sample per 100 m.
        * Capped at 20 samples per segment.
        * Both endpoints are always included.
        * Points are interpolated at equal fractional distances along the
          LineString using ``line.interpolate(fraction, normalized=True)``.
        """
        # Determine number of samples
        n_samples = MIN_SAMPLES
        if length_m > SAMPLE_INTERVAL_M:
            n_samples = max(MIN_SAMPLES, int(length_m / SAMPLE_INTERVAL_M) + 2)
        n_samples = min(n_samples, MAX_SAMPLES)

        # Generate evenly-spaced fractions [0.0 … 1.0]
        if n_samples <= 1:
            fractions = [0.0]
        else:
            fractions = [i / (n_samples - 1) for i in range(n_samples)]

        coords = []
        for frac in fractions:
            pt = line.interpolate(frac, normalized=True)
            coords.append((pt.x, pt.y))  # (lon, lat)

        return coords

    # ------------------------------------------------------------------
    # Terrain sampling & aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_terrain(
        sample_coords: list[tuple[float, float]],
    ) -> list[dict]:
        """Query terrain_service for every sample point.

        Returns a list of result dicts — one per sample coordinate.
        """
        results = []
        for lon, lat in sample_coords:
            result = terrain_service.get_terrain_susceptibility(lat=lat, lon=lon)
            result["sample_lon"] = lon
            result["sample_lat"] = lat
            results.append(result)
        return results

    @staticmethod
    def _aggregate_terrain(terrain_results: list[dict]) -> dict:
        """Aggregate per-point terrain evidence into a segment-level summary.

        Segment terrain score formula:
            segment_terrain_score = 0.70 * max_susceptibility
                                  + 0.30 * mean_susceptibility
        Capped to [0, 100].

        The *max* captures a potentially hazardous local portion of the road,
        while the *mean* represents broader segment conditions.
        """
        valid = [r for r in terrain_results if r.get("status") == "success"]

        if not valid:
            return {
                "available": False,
                "reason": next((r.get("reason") for r in terrain_results if r.get("reason")), None),
                "sample_count": len(terrain_results),
                "valid_count": 0,
                "segment_score": None,
                "summary": {
                    "sample_count": len(terrain_results),
                    "valid_count": 0,
                    "mean_susceptibility": None,
                    "max_susceptibility": None,
                    "mean_relative_elevation_m": None,
                    "min_relative_elevation_m": None,
                },
            }

        susceptibilities = [r["susceptibility_score"] for r in valid]
        relative_elevations = [r["local_relative_elevation_m"] for r in valid]

        mean_susc = sum(susceptibilities) / len(susceptibilities)
        max_susc = max(susceptibilities)
        mean_rel_el = sum(relative_elevations) / len(relative_elevations)
        min_rel_el = min(relative_elevations)

        # Segment terrain score (capped 0–100)
        segment_score = TERRAIN_MAX_WEIGHT * max_susc + TERRAIN_MEAN_WEIGHT * mean_susc
        segment_score = max(0.0, min(100.0, segment_score))

        return {
            "available": True,
            "sample_count": len(terrain_results),
            "valid_count": len(valid),
            "segment_score": segment_score,
            "summary": {
                "sample_count": len(terrain_results),
                "valid_count": len(valid),
                "mean_susceptibility": round(mean_susc, 2),
                "max_susceptibility": round(max_susc, 2),
                "mean_relative_elevation_m": round(mean_rel_el, 2),
                "min_relative_elevation_m": round(min_rel_el, 2),
            },
        }

    # ------------------------------------------------------------------
    # Weather evidence
    # ------------------------------------------------------------------

    @staticmethod
    def _get_weather_evidence(lat: float = None, lon: float = None) -> dict:
        """Weather evidence via weather_adapter.assess_weather().

        Only AVAILABLE weather yields a score (precipitation_mm / 20 * 100, capped).
        STALE or UNAVAILABLE weather yields weather_score=None (unknown).
        """
        a = weather_adapter.assess_weather(lat=lat, lon=lon)
        available = a["state"] == WEATHER_AVAILABLE
        return {
            "available": available,
            "weather_score": a["weather_score"],
            "summary": {
                "state": a["state"],
                "precipitation_mm": a["precipitation_mm"],
                "score": round(a["weather_score"], 2) if available else None,
                "source": a["source"] if available else a["state"],
                "controlled_scenario": a["controlled_scenario"],
                "observed_at_utc": a["observed_at_utc"],
                "age_minutes": a["age_minutes"],
                "reason": a["reason"],
            },
        }

    # ------------------------------------------------------------------
    # Explainability
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_reasons(terrain_agg: dict, weather_evidence: dict, risk: dict) -> list[str]:
        """Build human-readable reason strings from measured evidence."""
        reasons: list[str] = []

        # --- Weather reasons ---
        if weather_evidence["available"]:
            precip = weather_evidence["summary"]["precipitation_mm"]
            if precip > 15:
                reasons.append("Heavy precipitation is actively occurring.")
            elif precip > 5:
                reasons.append("Moderate precipitation is currently detected.")
            elif precip > 0:
                reasons.append("Light precipitation is currently detected.")
            else:
                reasons.append("No active precipitation is currently reported.")
        else:
            state = weather_evidence["summary"]["state"].lower()
            reasons.append(
                f"Weather data is {state}; its 60% contribution is unknown, not assumed "
                f"safe or severe. The score covers known components only and could be "
                f"as high as {risk['score_upper_bound']:.0f}."
            )

        # --- Terrain reasons ---
        if terrain_agg["available"]:
            summary = terrain_agg["summary"]
            max_susc = summary["max_susceptibility"]
            min_rel = summary["min_relative_elevation_m"]

            if max_susc >= 75:
                reasons.append(
                    "Segment contains a locally low terrain portion relative "
                    "to its neighborhood."
                )
            elif max_susc >= 50:
                reasons.append(
                    "Terrain susceptibility is elevated on part of this segment."
                )
            elif max_susc >= 25:
                reasons.append(
                    "Terrain susceptibility is moderate along this segment."
                )
            else:
                reasons.append(
                    "Terrain along this segment is relatively elevated compared "
                    "to its local neighborhood."
                )

            if min_rel is not None and min_rel <= -2.0:
                reasons.append(
                    f"The lowest sampled point is {abs(min_rel):.1f} m below "
                    "the local neighborhood mean elevation."
                )

            valid_count = summary["valid_count"]
            total_count = summary["sample_count"]
            if valid_count < total_count:
                reasons.append(
                    f"Terrain data was available for {valid_count} of "
                    f"{total_count} sampled points."
                )
        else:
            reasons.append(
                "Terrain evidence unavailable for this segment "
                f"({terrain_agg.get('reason') or 'UNAVAILABLE'}); its 40% contribution is unknown."
            )

        return reasons



# Module-level singleton
road_hazard_service = RoadHazardService()
