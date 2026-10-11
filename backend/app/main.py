from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from .services.routing_service import routing_service, NoSafeRouteError, OutsideCoverageError

from app.database.connection import init_db

# Initialize database schema automatically on startup
init_db()

app = FastAPI(
    title="AEGIS-COP API",
    description="Backend for AEGIS-COP (Tactical Edge Common Operating Picture)",
    version="0.1.0",
)

# Configure CORS to allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routes.national import router as national_router
from .routes.risk import router as risk_router
from .routes.satellite import router as satellite_router
from .routes.alerts import router as alerts_router
from .routes.vision import router as vision_router
from .routes.incidents import router as incidents_router
from .routes.resources import router as resources_router
from .routes.field_operations import router as field_operations_router
from .routes.citizens import router as citizens_router
from .routes.threats import router as threats_router
from .routes.cop import router as cop_router
from .routes.geo import router as geo_router
from .routes.evidence import router as evidence_router
from .routes.simulation import router as simulation_router
from .routes.naval import router as naval_router
from .routes.maritime import router as maritime_router

app.include_router(national_router)
app.include_router(risk_router)
app.include_router(satellite_router)
app.include_router(alerts_router)
app.include_router(incidents_router)
app.include_router(resources_router)
app.include_router(vision_router)
app.include_router(field_operations_router)
app.include_router(citizens_router)
app.include_router(threats_router)
app.include_router(cop_router)
app.include_router(geo_router)
app.include_router(evidence_router)
app.include_router(simulation_router)
app.include_router(naval_router)
app.include_router(maritime_router)

@app.get("/")
def read_root():
    return {"message": "AEGIS-COP Tactical API is running"}

class FloodSimulationRequest(BaseModel):
    rainfall_mm_hr: float
    blockage_percent: float = 0
    forecast_minutes: int = 180

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/system/status")
def system_status():
    """Component status derived from actual state (no network calls)."""
    from .services.terrain_service import terrain_service
    from .services.scenario_service import scenario_service

    terrain_reason = terrain_service.unavailable_reason()
    return {
        "backend": "ONLINE",
        "osm": "LOADED" if routing_service.load_graph() else "UNAVAILABLE",
        "terrain": "AVAILABLE" if terrain_reason is None else terrain_reason,
        "weather": "CONTROLLED_SCENARIO" if scenario_service.is_active() else "LIVE_PROVIDER (Open-Meteo, single point)",
        "flood_model": "PROTOTYPE",
        "drainage": "SYNTHETIC",
    }

@app.get("/api/gis/status")
def gis_status():
    return routing_service.get_status()

@app.get("/api/weather")
def get_weather():
    from .services.weather_adapter import weather_adapter
    return weather_adapter.get_weather_evidence()

@app.get("/api/weather/forecast")
def get_weather_forecast():
    from .services.weather_adapter import weather_adapter
    return weather_adapter.get_weather_forecast()

@app.get("/api/hazard")
def get_hazard(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude")
):
    from .services.hazard_service import hazard_service
    try:
        return hazard_service.assess_flood_hazard(lat=lat, lon=lon)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/route")
def get_route(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lon: float = Query(..., description="Origin longitude"),
    destination_lat: float = Query(..., description="Destination latitude"),
    destination_lon: float = Query(..., description="Destination longitude"),
    hazard_aware: bool = Query(False, description="Enable hazard-aware route mode"),
    avoid_threats: bool = Query(True, description="Apply the threat-zone routing policy (CRITICAL zones block, others penalize)")
):
    try:
        route_data = routing_service.calculate_route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            hazard_aware=hazard_aware,
            avoid_threats=avoid_threats,
        )
        return {
            "status": "success",
            **route_data
        }
    except NoSafeRouteError as e:
        return e.to_dict()
    except OutsideCoverageError as e:
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/route/flood-safe")
def get_flood_safe_route(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lon: float = Query(..., description="Origin longitude"),
    destination_lat: float = Query(..., description="Destination latitude"),
    destination_lon: float = Query(..., description="Destination longitude"),
    rainfall_mm_hr: float = Query(80.0, description="Simulation rainfall"),
    blockage_percent: float = Query(50.0, description="Simulation blockage"),
    forecast_minute: int = Query(60, description="Forecast minute to route on")
):
    from .services.flood_routing_service import flood_routing_service
    try:
        route_data = flood_routing_service.calculate_flood_safe_route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            rainfall_mm_hr=rainfall_mm_hr,
            blockage_percent=blockage_percent,
            forecast_minute=forecast_minute
        )
        if route_data is None:
            return {
                "status": "no_safe_route",
                "message": "No viable flood-safe route is available for the selected forecast time.",
                "recommendation": "Delay movement or use an alternative destination if possible."
            }
        return route_data
    except OutsideCoverageError as e:
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/road-hazard")
def get_road_hazard(
    u: int = Query(..., description="Origin node OSM ID"),
    v: int = Query(..., description="Destination node OSM ID"),
    key: int = Query(0, description="Edge key (for parallel edges)"),
):
    """Assess hazard for a single road segment identified by (u, v, key)."""
    from .services.road_hazard_service import road_hazard_service
    try:
        return road_hazard_service.assess_road_segment(u=u, v=v, key=key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/flood/status")
def get_flood_status():
    from .services.flood.flood_forecast_service import flood_forecast_service
    try:
        return flood_forecast_service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/flood/simulate")
def run_flood_simulation(req: FloodSimulationRequest):
    from .services.flood.flood_forecast_service import flood_forecast_service
    try:
        return flood_forecast_service.simulate(
            rainfall_mm_hr=req.rainfall_mm_hr,
            blockage_percent=req.blockage_percent,
            forecast_minutes=req.forecast_minutes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# PHASE 5C-1: SCENARIO API
# ==========================================
from .services.scenario_service import scenario_service

@app.get("/api/scenario/status")
def get_scenario_status():
    return scenario_service.get_status()

@app.post("/api/scenario/activate")
def activate_scenario():
    scenario_service.set_active(True)
    return scenario_service.get_status()

@app.post("/api/scenario/deactivate")
def deactivate_scenario():
    scenario_service.set_active(False)
    return scenario_service.get_status()

@app.get("/api/scenario/config")
def get_scenario_config():
    return scenario_service.get_config()

@app.post("/api/scenario/config")
def update_scenario_config(config: dict):
    scenario_service.update_config(config)
    return scenario_service.get_config()


# ==========================================
# PHASE 5C-2: ROUTE MONITORING API
# ==========================================
from .services.route_monitor_service import route_monitor_service

@app.post("/api/route-monitor/register")
def register_route(payload: dict):
    return route_monitor_service.register_route(payload)

@app.get("/api/route-monitor/{route_id}")
def get_monitored_route(route_id: str):
    res = route_monitor_service.get_route(route_id)
    if res.get("status") == "not_found":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Route not found")
    return res

@app.post("/api/route-monitor/{route_id}/check")
def check_monitored_route(route_id: str):
    res = route_monitor_service.reassess_route(route_id)
    if res.get("status") == "not_found":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Route not found")
    return res

class ObstructionReport(BaseModel):
    lat: float
    lon: float
    radius_m: float = 50.0
    simulated: bool = False  # True for controlled demonstrations; recorded as CONTROLLED_DEMO

class InvalidateRouteRequest(BaseModel):
    reason: str = "Manually invalidated by operator"
    actor: str = "EOC_OPERATOR"
    obstruction: Optional[ObstructionReport] = None

@app.post("/api/route-monitor/{route_id}/invalidate")
def invalidate_monitored_route(route_id: str, payload: Optional[InvalidateRouteRequest] = None):
    """Persist a manual invalidation. Optionally record the obstruction as a CRITICAL threat."""
    payload = payload or InvalidateRouteRequest()
    res = route_monitor_service.invalidate_route(
        route_id,
        reason=payload.reason,
        actor=payload.actor,
        obstruction=payload.obstruction.dict() if payload.obstruction else None,
    )
    if res is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return res


# ==========================================
# PHASE 5C-3: ROUTE REPLACEMENT API
# ==========================================
from .services.route_replacement_service import route_replacement_service

@app.post("/api/route-monitor/{route_id}/replacement/recommend")
def recommend_replacement(route_id: str):
    res = route_replacement_service.recommend_replacement(route_id)
    if res.get("status") == "error":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@app.post("/api/route-monitor/{route_id}/replacement/approve")
def approve_replacement(route_id: str, payload: dict):
    rec_id = payload.get("recommendation_id")
    if not rec_id or not payload.get("approved"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing recommendation_id or approved flag")
        
    res = route_replacement_service.approve_replacement(
        route_id, rec_id, actor=payload.get("actor"), reason=payload.get("reason"))
    if res.get("status") == "error":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@app.post("/api/route-monitor/{route_id}/replacement/reject")
def reject_replacement(route_id: str, payload: dict):
    rec_id = payload.get("recommendation_id")
    if not rec_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing recommendation_id")
        
    res = route_replacement_service.reject_replacement(
        route_id, rec_id, payload.get("reason"), actor=payload.get("actor"))
    if res.get("status") == "error":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
