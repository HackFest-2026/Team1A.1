import React, { useEffect, useRef, useState, useCallback } from 'react';
import MapAutoResize from './ui/MapAutoResize';
import Icon from './ui/Icon';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, Circle, GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE_URL } from '../config';
import { COPLayers, COPLayerPanel } from './COPLayers';

function ClickHandler({ onPointSelect }) {
  useMapEvents({
    click(e) {
      if (onPointSelect) onPointSelect(e.latlng);
    }
  });
  return null;
}

const PRESET_ROUTES = [
  {
    name: 'Gokul Road Corridor',
    origin: { lat: 15.3647, lng: 75.1240 },
    destination: { lat: 15.3700, lng: 75.1200 },
    originName: 'Gokul Road Sector',
    destName: 'Keshwapur Safe Zone'
  },
  {
    name: 'Dharwad Central',
    origin: { lat: 15.4589, lng: 75.0078 },
    destination: { lat: 15.4500, lng: 75.0150 },
    originName: 'Dharwad Central',
    destName: 'Jubilee Circle Base'
  },
  {
    name: 'Unkal - Vidyanagar',
    origin: { lat: 15.3750, lng: 75.1300 },
    destination: { lat: 15.3850, lng: 75.1350 },
    originName: 'Vidyanagar Hubballi',
    destName: 'Unkal Staging'
  }
];

const createVehicleIcon = (unitType, name, status) => L.divIcon({
  html: `<div style="background-color: ${status === 'EN_ROUTE' ? '#0B4F8A' : status === 'OPERATING' ? '#7C3AED' : '#059669'}; color: white; padding: 4px 8px; border-radius: 14px; font-weight: bold; font-size: 11px; border: 2px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.35); display: inline-flex; align-items: center; gap: 4px; white-space: nowrap;">
    <span>${unitType?.includes('BOAT') ? '🛥️' : unitType?.includes('AMBULANCE') ? '🚑' : '🚒'}</span>
    <span>${name || 'Response Unit'}</span>
    <span style="font-size: 9px; opacity: 0.9; background: rgba(255,255,255,0.25); padding: 1px 4px; border-radius: 6px;">${status || 'ACTIVE'}</span>
  </div>`,
  className: 'custom-vehicle-marker',
  iconSize: [140, 28],
  iconAnchor: [70, 14]
});

// Short, truthful summary of a route response for the collapsed planner bar.
function routeBadge(data) {
  if (!data) return null;
  if (data.recommended_route) {
    const r = data.recommended_route;
    const score = r.threat_score ?? r.risk_score ?? 0;
    return { text: `${r.route_safety} (${score}/100, tactical assessment)`, tone: r.route_safety === 'SAFE' ? 'ok' : 'warn' };
  }
  const exposure = data.threat_exposure;
  if (exposure?.exposed) {
    return { text: `THREAT EXPOSURE (${exposure.affected_threats.length})`, tone: 'warn' };
  }
  if (exposure && exposure.active_zone_count > 0) return { text: 'AVOIDS ACTIVE THREAT ZONES', tone: 'ok' };
  return { text: 'NO ACTIVE THREAT ZONES', tone: 'neutral' };
}

function errorText(data, fallback) {
  const detail = data?.detail;
  if (!detail) return fallback;
  return typeof detail === 'string' ? detail : (detail.message || fallback);
}

export default function MapComponent({
  onRouteCalculated,
  onMapClick,
  showIncidents = true,
  showRisk = true,
  showResources = true,
  showFieldUnits = true,
  showSatellite = false,
  incidents = [],
  resources = [],
  fieldUnits = [],
  activeDispatch = null,
  replacementRoute = null,
  monitorStatus = null,
  copData = null,
  copError = null,
  copEnabled = false
}) {
  const center = [15.3647, 75.1240];
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [originLabel, setOriginLabel] = useState('');
  const [destLabel, setDestLabel] = useState('');
  
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [collapsed, setCollapsed] = useState(true);
  
  const [routeMode, setRouteMode] = useState('FASTEST');
  const [forecastMinute, setForecastMinute] = useState(0);
  const [routeInfoDisplay, setRouteInfoDisplay] = useState(null);
  const [copVisible, setCopVisible] = useState({
    threats: true,
    units: true,
    routes: true,
    evidence: true,
    naval: true,
    army: true,
    thermal: true,
    zones: true
  });
  const [missionArea, setMissionArea] = useState(null);
  useEffect(() => {
    if (!copEnabled) return;
    fetch(`${API_BASE_URL}/geo/coverage`).then(r => r.ok ? r.json() : null)
      .then(m => setMissionArea(m?.road_graph?.bounds || null)).catch(() => setMissionArea(null));
  }, [copEnabled]);
  const toggleCopLayer = (key) => setCopVisible(v => ({ ...v, [key]: !v[key] }));

  // Search state (Submit-driven low-frequency caching)
  const [originInput, setOriginInput] = useState('');
  const [destInput, setDestInput] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchTarget, setSearchTarget] = useState(null); // 'A' or 'B'
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchCache, setSearchCache] = useState({});

  const handlePointSelect = useCallback((latlng) => {
    if (onMapClick) onMapClick(latlng);
    if (!origin) {
      setOrigin(latlng);
      setOriginLabel(`Selected Point (${latlng.lat.toFixed(3)}, ${latlng.lng.toFixed(3)})`);
    } else if (!destination) {
      setDestination(latlng);
      setDestLabel(`Selected Point (${latlng.lat.toFixed(3)}, ${latlng.lng.toFixed(3)})`);
    } else {
      setOrigin(latlng);
      setOriginLabel(`Selected Point (${latlng.lat.toFixed(3)}, ${latlng.lng.toFixed(3)})`);
      setDestination(null);
      setDestLabel('');
    }
  }, [origin, destination, onMapClick]);

  const handleSearchSubmit = async (e, target) => {
    e.preventDefault();
    const query = target === 'A' ? originInput : destInput;
    if (!query || query.trim().length < 2) return;
    
    const cleanQuery = query.trim().toLowerCase();
    if (searchCache[cleanQuery]) {
      setSearchResults(searchCache[cleanQuery]);
      setSearchTarget(target);
      return;
    }

    setSearchLoading(true);
    setSearchTarget(target);
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(cleanQuery + ' Hubballi Dharwad Karnataka')}&limit=4`);
      const data = await res.json();
      const formatted = data.map(item => ({
        name: item.display_name.split(',')[0],
        fullName: item.display_name,
        lat: parseFloat(item.lat),
        lng: parseFloat(item.lon)
      }));
      setSearchResults(formatted);
      setSearchCache(prev => ({ ...prev, [cleanQuery]: formatted }));
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setSearchLoading(false);
    }
  };

  const selectSearchResult = (item) => {
    if (searchTarget === 'A') {
      setOrigin({ lat: item.lat, lng: item.lng });
      setOriginLabel(item.name);
      setOriginInput(item.name);
    } else {
      setDestination({ lat: item.lat, lng: item.lng });
      setDestLabel(item.name);
      setDestInput(item.name);
    }
    setSearchResults([]);
    setSearchTarget(null);
  };

  const handleCalculateRoute = async () => {
    if (!origin || !destination) return;
    setLoading(true);
    setError(null);
    setRoute(null);
    setRouteInfoDisplay(null);
    try {
      const url = `${API_BASE_URL}/route?origin_lat=${origin.lat}&origin_lon=${origin.lng}&destination_lat=${destination.lat}&destination_lon=${destination.lng}`;
      
      const response = await fetch(url);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(errorText(data, 'Failed to calculate route'));
      }
      
      if (data.status === 'success') {
        const latLngs = data.route.coordinates.map(coord => [coord[1], coord[0]]);
        setRoute(latLngs);
        setRouteInfoDisplay(data);
        setCollapsed(true); // Auto-collapse to maximize map view
        if (onRouteCalculated) {
          onRouteCalculated({
            distance: data.distance_m || (data.recommended_route?.distance_m),
            time: data.estimated_time_s || (data.recommended_route?.estimated_time_s),
            source: data.source || 'Tactical Routing Engine',
            rawDetails: data
          });
        }
      } else if (data.status === 'no_safe_route') {
        const blockers = data.blocking_threat_ids?.length ? ` Blocking threats: ${data.blocking_threat_ids.join(', ')}.` : '';
        setError(`${data.message}${data.recommendation ? ' ' + data.recommendation : ''}${blockers}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setOrigin(null);
    setDestination(null);
    setOriginLabel('');
    setDestLabel('');
    setOriginInput('');
    setDestInput('');
    setRoute(null);
    setError(null);
    setRouteInfoDisplay(null);
    setCollapsed(false);
    if (onRouteCalculated) {
      onRouteCalculated(null);
    }
  };

  return (
    <div className="relative h-full w-full bg-slate-100">
      
      {/* FLOATING COMPACT ROUTE SEARCH PANEL (TOP LEFT OF MAP) */}
      {!showSatellite && (
        <div className="absolute top-3 left-14 z-[1000] transition-all duration-200 max-w-sm">
          {collapsed ? (
            <div className="bg-white border border-slate-300 shadow-md rounded-lg p-2 flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2 truncate">
                <span className="w-2 h-2 rounded-full bg-accent"></span>
                <span className="font-bold text-slate-800 truncate">
                  {originLabel || destLabel ? `${originLabel || 'Origin'} ➔ ${destLabel || 'Destination'}` : 'Ad-hoc route planner'}
                </span>
                {routeInfoDisplay && (() => {
                  const badge = routeBadge(routeInfoDisplay);
                  const tone = badge.tone === 'ok' ? 'bg-emerald-100 text-emerald-800'
                    : badge.tone === 'warn' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700';
                  const terrainPct = routeInfoDisplay.coverage?.terrain_coverage_pct;
                  return (
                    <>
                      <span className={`${tone} font-bold px-1.5 py-0.5 rounded text-[10px] shrink-0`}>{badge.text}</span>
                      {typeof terrainPct === 'number' && terrainPct < 100 && (
                        <span className="bg-slate-100 text-slate-700 font-bold px-1.5 py-0.5 rounded text-[10px] shrink-0" title="Share of route edges inside the DEM">
                          TERRAIN {terrainPct}%
                        </span>
                      )}
                    </>
                  );
                })()}
              </div>
              <button
                onClick={() => setCollapsed(false)}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-[10px] border border-slate-300"
              >
                {route ? 'Modify' : 'Open'}
              </button>
            </div>
          ) : (
            <div className="bg-white/95 border border-slate-300 backdrop-blur-md p-3.5 rounded-lg shadow-lg text-slate-900 w-80 space-y-3">
              <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                <h3 className="font-bold text-xs uppercase tracking-wider text-accent flex items-center gap-1.5">
                  <Icon name="route" size={14} /> THREAT-AWARE ROUTE PLANNER
                </h3>
                <button onClick={() => setCollapsed(true)} className="text-slate-400 hover:text-slate-700 font-bold text-xs">
                  ✕
                </button>
              </div>

              {/* Presets */}
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Quick Locations
                </label>
                <div className="space-y-1">
                  {PRESET_ROUTES.map((p, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setOrigin(p.origin);
                        setDestination(p.destination);
                        setOriginLabel(p.originName);
                        setDestLabel(p.destName);
                        setOriginInput(p.originName);
                        setDestInput(p.destName);
                        setRoute(null);
                        setError(null);
                        if (onMapClick) onMapClick(p.origin);
                      }}
                      className="w-full text-[11px] text-left px-2.5 py-1 bg-slate-50 hover:bg-slate-100 text-slate-800 rounded border border-slate-200 transition font-medium truncate flex justify-between"
                    >
                      <span className="truncate flex items-center gap-1"><Icon name="pin" size={12} />{p.name}</span>
                      <span className="text-[9px] text-accent font-bold">Select</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Inputs */}
              <div className="space-y-2">
                <div>
                  <label className="text-[10px] font-bold text-slate-600 uppercase tracking-wider block mb-1">ORIGIN</label>
                  <form onSubmit={e => handleSearchSubmit(e, 'A')} className="flex gap-1">
                    <input
                      type="text"
                      placeholder="Search starting location..."
                      value={originInput}
                      onChange={e => setOriginInput(e.target.value)}
                      className="flex-1 px-2.5 py-1 text-xs bg-white border border-slate-300 text-slate-900 rounded focus:border-accent outline-none"
                    />
                    <button type="submit" className="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-xs border border-slate-300">
                      Search
                    </button>
                  </form>
                  {originLabel && <div className="text-[10px] text-emerald-700 font-bold mt-1">✓ Set: {originLabel}</div>}
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-600 uppercase tracking-wider block mb-1">DESTINATION</label>
                  <form onSubmit={e => handleSearchSubmit(e, 'B')} className="flex gap-1">
                    <input
                      type="text"
                      placeholder="Search destination..."
                      value={destInput}
                      onChange={e => setDestInput(e.target.value)}
                      className="flex-1 px-2.5 py-1 text-xs bg-white border border-slate-300 text-slate-900 rounded focus:border-accent outline-none"
                    />
                    <button type="submit" className="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-2 py-1 rounded text-xs border border-slate-300">
                      Search
                    </button>
                  </form>
                  {destLabel && <div className="text-[10px] text-emerald-700 font-bold mt-1">✓ Set: {destLabel}</div>}
                </div>
              </div>

              {/* Search Dropdown */}
              {searchLoading && <div className="text-[10px] text-slate-500 italic">Searching locations...</div>}
              {searchResults.length > 0 && (
                <div className="bg-slate-50 border border-slate-300 rounded p-1 text-xs space-y-1 max-h-36 overflow-y-auto">
                  {searchResults.map((item, idx) => (
                    <button
                      key={idx}
                      onClick={() => selectSearchResult(item)}
                      className="w-full text-left p-1.5 rounded hover:bg-slate-200 text-[11px] text-slate-800 truncate block border-b border-slate-200"
                    >
                      {item.fullName}
                    </button>
                  ))}
                </div>
              )}

              {error && (
                <div className="bg-red-50 text-red-700 p-2 text-xs rounded border border-red-200 font-bold">
                  {error}
                </div>
              )}

              <div className="flex gap-2 pt-1">
                <button 
                  onClick={handleCalculateRoute}
                  disabled={!origin || !destination || loading}
                  className="flex-1 bg-accent hover:bg-accent-strong text-white py-1.5 rounded text-xs font-bold shadow-sm transition disabled:opacity-50"
                >
                  {loading ? 'CALCULATING...' : 'PLAN THREAT-AWARE ROUTE'}
                </button>
                <button 
                  onClick={handleReset}
                  className="bg-slate-100 hover:bg-slate-200 text-slate-700 py-1.5 px-3 rounded text-xs font-bold border border-slate-300"
                >
                  Reset
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Map Container */}
      <MapContainer center={center} zoom={showSatellite ? 13 : 12} className="h-full w-full z-0">
        <MapAutoResize />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="basemap-tiles"
        />

        {/* ISRO Bhuvan / National Earth Observation Satellite Layer */}
        {showSatellite && (
          <TileLayer
            attribution="ISRO Bhuvan / National Earth Observation Satellite Services"
            url="https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/default/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg"
            maxNativeZoom={9}
            opacity={0.8}
          />
        )}

        <ClickHandler onPointSelect={handlePointSelect} />

        {/* Origin / Destination Markers */}
        {origin && typeof origin.lat === 'number' && typeof origin.lng === 'number' && !isNaN(origin.lat) && !isNaN(origin.lng) && (
          <Marker position={[origin.lat, origin.lng]}>
            <Popup>
              <div className="font-bold text-xs text-emerald-700">ORIGIN: {originLabel}</div>
            </Popup>
          </Marker>
        )}

        {destination && typeof destination.lat === 'number' && typeof destination.lng === 'number' && !isNaN(destination.lat) && !isNaN(destination.lng) && (
          <Marker position={[destination.lat, destination.lng]}>
            <Popup>
              <div className="font-bold text-xs text-blue-700">DESTINATION: {destLabel}</div>
            </Popup>
          </Marker>
        )}

        {/* Canonical COP layers (threats, field units, monitored routes, evidence) */}
        {copEnabled && <COPLayers copData={copData} visible={copVisible} missionArea={missionArea} />}

        {/* Operational Incidents Layer */}
        {showIncidents && !copEnabled && incidents.filter(inc => inc && typeof inc.latitude === 'number' && typeof inc.longitude === 'number' && !isNaN(inc.latitude) && !isNaN(inc.longitude)).map(inc => (
          <CircleMarker
            key={inc.incident_id}
            center={[inc.latitude, inc.longitude]}
            radius={11}
            pathOptions={{
              color: inc.severity === 'CRITICAL' ? '#991B1B' : inc.severity === 'HIGH' ? '#C62828' : '#D97706',
              fillColor: inc.severity === 'CRITICAL' ? '#991B1B' : inc.severity === 'HIGH' ? '#C62828' : '#D97706',
              fillOpacity: 0.75,
              weight: 2
            }}
          >
            <Popup>
              <div className="text-xs space-y-1.5 p-0.5 max-w-xs">
                <div className="flex justify-between items-center border-b border-slate-200 pb-1">
                  <span className="font-extrabold text-slate-900 text-sm">{inc.title}</span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded font-black text-white ${
                    inc.severity === 'CRITICAL' ? 'bg-red-700' : 'bg-amber-600'
                  }`}>
                    {inc.severity}
                  </span>
                </div>
                <div><b>Location:</b> {inc.district}, {inc.city || 'Hubballi'}</div>
                <div><b>Problem Type:</b> <span className="font-bold text-accent">{inc.hazard_type}</span></div>
                <div><b>Risk Score:</b> <strong className="text-red-700">{inc.risk_score}/100</strong></div>
                <div><b>Operational Status:</b> <span className="font-bold text-emerald-800">{inc.status}</span></div>
                <div className="text-slate-600 text-[11px] pt-1 border-t border-slate-200">{inc.description}</div>
                {showSatellite && (
                  <div className="bg-blue-50 text-[10px] text-blue-900 p-1.5 rounded border border-blue-200 mt-1 font-mono">
                    ℹ Operational Incident Overlay on top of ISRO Bhuvan Earth Observation Imagery.
                  </div>
                )}
                {!showSatellite && (
                  <div className="bg-slate-100 text-[9px] text-slate-600 p-1 rounded mt-1 font-mono">
                    PROVENANCE: EOC Operational Incident Feed
                  </div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Response Resources Layer */}
        {showResources && resources.filter(res => res && typeof res.latitude === 'number' && typeof res.longitude === 'number' && !isNaN(res.latitude) && !isNaN(res.longitude)).map(res => (
          <CircleMarker
            key={res.resource_id}
            center={[res.latitude, res.longitude]}
            radius={8}
            pathOptions={{ color: '#0B4F8A', fillColor: '#0B4F8A', fillOpacity: 0.8 }}
          >
            <Popup>
              <div className="text-xs">
                <div className="font-bold text-slate-900">{res.name}</div>
                <div className="text-blue-700 font-bold">{res.resource_type}</div>
                <div className="text-slate-600">Status: {res.status}</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Dispatched Field Units & Response Vehicles Layer */}
        {showFieldUnits && !copEnabled && fieldUnits.filter(fu => fu && typeof fu.latitude === 'number' && typeof fu.longitude === 'number' && !isNaN(fu.latitude) && !isNaN(fu.longitude)).map(fu => (
          <Marker
            key={fu.field_unit_id}
            position={[fu.latitude, fu.longitude]}
            icon={createVehicleIcon(fu.unit_type, fu.name, fu.status)}
          >
            <Popup>
              <div className="text-xs space-y-1 p-1">
                <div className="font-extrabold text-sm text-accent">{fu.name}</div>
                <div><b>Type:</b> {fu.unit_type}</div>
                <div><b>Status:</b> <span className="font-bold text-emerald-700">{fu.status}</span></div>
                {fu.target_incident_title && (
                  <div><b>Target Destination:</b> {fu.target_incident_title}</div>
                )}
                <div><b>Location:</b> {fu.city || fu.district}</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Live Connecting Route Polyline between Dispatched Unit and Incident */}
        {activeDispatch && activeDispatch.unitLat && activeDispatch.incLat && (
          <Polyline
            positions={[
              [activeDispatch.unitLat, activeDispatch.unitLng],
              [activeDispatch.incLat, activeDispatch.incLng]
            ]}
            pathOptions={{
              color: monitorStatus === 'INVALIDATED' ? '#DC2626' : monitorStatus === 'REPLACED' ? '#059669' : '#0B4F8A',
              weight: 5,
              dashArray: monitorStatus === 'INVALIDATED' ? '6, 6' : '8, 8',
              opacity: 0.9
            }}
          />
        )}

        {/* Proposed Replacement Route Polyline when Obstruction / Invalidation occurs */}
        {replacementRoute && Array.isArray(replacementRoute) && replacementRoute.length > 0 && (
          <Polyline
            positions={replacementRoute}
            pathOptions={{ color: '#059669', weight: 5, opacity: 0.9, dashArray: '10 8' }}
          />
        )}

        {/* Calculated Route Polyline */}
        {route && Array.isArray(route) && route.filter(pt => Array.isArray(pt) && pt.length >= 2 && typeof pt[0] === 'number' && typeof pt[1] === 'number' && !isNaN(pt[0]) && !isNaN(pt[1])).length > 0 && (
          <Polyline
            positions={route.filter(pt => Array.isArray(pt) && pt.length >= 2 && typeof pt[0] === 'number' && typeof pt[1] === 'number' && !isNaN(pt[0]) && !isNaN(pt[1]))}
            pathOptions={{
              // The planner route is independent of the monitored corridor (shown by the COP layer),
              // so its styling must not follow the monitor status.
              color: '#0B4F8A',
              weight: 6,
              opacity: 0.9
            }}
          />
        )}
      </MapContainer>
      {copEnabled && (
        <COPLayerPanel copData={copData} copError={copError} visible={copVisible} onToggle={toggleCopLayer} />
      )}
    </div>
  );
}
