"""
AEGIS-COP Geo Context Layer Package
Exposes core ResilienceRoute GIS/routing engine (OSM, CartoDEM, NetworkX)
via clean domain contracts.
"""
from .models import GeoPointContext, GeoSnapResult, GeoRouteContext, GeoGISStatus
from .geo_context_service import geo_context_service

__all__ = [
    "GeoPointContext",
    "GeoSnapResult",
    "GeoRouteContext",
    "GeoGISStatus",
    "geo_context_service",
]
