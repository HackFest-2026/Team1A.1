import Icon from './ui/Icon';
import React, { useState, useEffect } from 'react';
import { Circle, CircleMarker, Polyline, Polygon, Popup, Rectangle, Tooltip } from 'react-leaflet';
import { API_BASE_URL } from '../config';

// Canonical COP layers rendered from backend. Authoritative defence visualization.

const THREAT_COLORS = { CRITICAL: '#991B1B', HIGH: '#DC2626', MODERATE: '#D97706', LOW: '#2563EB' };
const ROUTE_COLORS = { ACTIVE: '#1D4ED8', AT_RISK: '#D97706', INVALIDATED: '#DC2626', REPLACED: '#059669' };
const UNIT_COLORS = { EN_ROUTE: '#0B4F8A', AT_SCENE: '#7C3AED', OPERATING: '#7C3AED', RETURNING: '#0891B2', COMPLETED: '#64748B', UNAVAILABLE: '#94A3B8', ASSIGNED: '#059669' };
const EVIDENCE_COLOR = '#7C3AED';
const NAVAL_COLOR = '#0284C7';
const ARMY_COLOR = '#059669';
const FIRMS_COLOR = '#EA580C';
const ZONE_COLOR = '#4F46E5';

const INACTIVE_THREAT = new Set(['CLOSED', 'RESOLVED']);

const hasCoords = (o) => o && typeof o.latitude === 'number' && typeof o.longitude === 'number'
  && !isNaN(o.latitude) && !isNaN(o.longitude);

function Badge({ children, className }) {
  return <span className={`text-[9px] px-1.5 py-0.5 rounded font-black ${className}`}>{children}</span>;
}

export function COPLayers({ copData, visible, missionArea }) {
  const [navalVessels, setNavalVessels] = useState([]);
  const [armyUnits, setArmyUnits] = useState([]);
  const [thermalHotspots, setThermalHotspots] = useState([]);
  const [tacticalZones, setTacticalZones] = useState([]);

  useEffect(() => {
    let mounted = true;
    async function loadTacticalFeeds() {
      try {
        const [navRes, armyRes, firmsRes, zonesRes] = await Promise.all([
          fetch(`${API_BASE_URL}/naval/vessels`).then(r => r.json()).catch(() => null),
          fetch(`${API_BASE_URL}/army/units`).then(r => r.json()).catch(() => null),
          fetch(`${API_BASE_URL}/army/thermal-hotspots`).then(r => r.json()).catch(() => null),
          fetch(`${API_BASE_URL}/army/tactical-zones`).then(r => r.json()).catch(() => null),
        ]);
        if (!mounted) return;
        if (navRes?.vessels) setNavalVessels(navRes.vessels);
        if (armyRes?.units) setArmyUnits(armyRes.units);
        if (firmsRes?.records) setThermalHotspots(firmsRes.records);
        if (zonesRes?.zones) setTacticalZones(zonesRes.zones);
      } catch (err) {
        // silent fallback
      }
    }
    loadTacticalFeeds();
    const timer = setInterval(loadTacticalFeeds, 6000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  if (!copData) return null;
  const { threats = [], field_units = [], monitored_routes = [], evidence = [] } = copData;
  const activeMissionId = [...monitored_routes].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))[0]?.id;

  return (
    <>
      {missionArea && (
        <Rectangle
          bounds={[[missionArea.min_lat, missionArea.min_lon], [missionArea.max_lat, missionArea.max_lon]]}
          pathOptions={{ color: '#475569', weight: 1, dashArray: '6, 6', fill: false, interactive: false }}
        />
      )}

      {/* Tactical Military Grid Zones (Polygons) */}
      {visible.zones && tacticalZones.map(z => {
        if (!z.coordinates || z.coordinates.length < 3) return null;
        return (
          <Polygon
            key={`zone-${z.zone_id}`}
            positions={z.coordinates}
            pathOptions={{
              color: ZONE_COLOR,
              fillColor: ZONE_COLOR,
              fillOpacity: 0.15,
              weight: 2,
              dashArray: '5, 5'
            }}
          >
            <Tooltip direction="center" permanent={false}>
              <span className="font-bold text-xs">{z.name}</span>
            </Tooltip>
            <Popup>
              <div className="text-xs space-y-1 font-sans">
                <div className="font-bold text-indigo-900">{z.name}</div>
                <div><b>Type:</b> {z.zone_type}</div>
                <div><b>Security:</b> <span className="font-bold text-red-700">{z.security_level}</span></div>
                <div><b>Commander:</b> {z.commander}</div>
                <div className="text-slate-600 text-[11px] pt-1">{z.description}</div>
              </div>
            </Popup>
          </Polygon>
        );
      })}

      {/* Monitored Routes */}
      {visible.routes && monitored_routes.flatMap(r => [['origin', r.origin], ['destination', r.destination]]
        .map(([kind, p]) => [kind, p, r.id === activeMissionId])
        .filter(([, p]) => p && typeof p.lat === 'number' && typeof p.lon === 'number')
        .map(([kind, p, isActive]) => (
          <CircleMarker
            key={`mission-${kind}-${r.id}-${isActive ? "active" : "earlier"}`}
            center={[p.lat, p.lon]}
            radius={8}
            pathOptions={{ color: '#0F172A', fillColor: kind === 'origin' ? '#FFFFFF' : '#0F172A', fillOpacity: 1, weight: 3 }}
          >
            <Tooltip direction="top" offset={[0, -8]} permanent={isActive}>
              {isActive ? 'Mission ' : 'Earlier mission '}{kind === 'origin' ? 'origin' : 'destination'}
            </Tooltip>
          </CircleMarker>
        )))}
      {visible.routes && monitored_routes.filter(r => r.geometry?.coordinates?.length > 1).map(r => {
        const color = ROUTE_COLORS[r.status] || '#334155';
        return (
          <Polyline
            key={`cop-route-${r.id}`}
            positions={r.geometry.coordinates.map(c => [c[1], c[0]])}
            pathOptions={{ color, weight: r.status === 'INVALIDATED' ? 6 : 5, opacity: 0.85 }}
          >
            <Popup>
              <div className="text-xs space-y-1 font-sans">
                <div className="font-extrabold text-slate-900">Monitored route</div>
                <div><b>Status:</b> <span className="font-bold" style={{ color }}>{r.status}</span></div>
                <div><b>Distance:</b> {(r.distance_m / 1000).toFixed(2)} km · <b>ETA:</b> {Math.round(r.estimated_time_s / 60)} min</div>
                {r.hazard_summary?.overall_level && (
                  <div><b>Hazard:</b> {r.hazard_summary.overall_level} ({r.hazard_summary.overall_score})</div>
                )}
                {r.hazard_summary?.threat_exposure?.critical_threat_ids?.length > 0 && (
                  <div className="text-red-700"><b>Critical threats:</b> {r.hazard_summary.threat_exposure.critical_threat_ids.join(', ')}</div>
                )}
                <div className="text-[9px] text-slate-500 font-mono">{r.id}</div>
              </div>
            </Popup>
          </Polyline>
        );
      })}

      {/* Threats */}
      {visible.threats && threats.filter(t => hasCoords(t) && !INACTIVE_THREAT.has(t.status)).map(t => {
        const color = THREAT_COLORS[t.severity] || '#334155';
        return (
          <React.Fragment key={`cop-threat-${t.id}`}>
            <Circle
              center={[t.latitude, t.longitude]}
              radius={t.radius_m}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.15, weight: 1.5, dashArray: '4, 4' }}
            />
            <CircleMarker
              center={[t.latitude, t.longitude]}
              radius={9}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 2 }}
            >
              <Popup>
                <div className="text-xs space-y-1 font-sans max-w-xs">
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-extrabold text-slate-900">{t.category}</span>
                    <Badge className={t.severity === 'CRITICAL' ? 'bg-red-700 text-white' : 'bg-amber-600 text-white'}>
                      {t.severity}
                    </Badge>
                  </div>
                  <div><b>Status:</b> {t.status} · <b>Confidence:</b> {t.confidence}</div>
                  <div><b>Radius:</b> {t.radius_m}m · <b>Source:</b> {t.source}</div>
                  {t.description && <div className="text-slate-600 text-[11px] pt-1 border-t border-slate-200">{t.description}</div>}
                  <div className="text-[9px] text-slate-500 font-mono">{t.id}</div>
                </div>
              </Popup>
            </CircleMarker>
          </React.Fragment>
        );
      })}

      {/* Live AIS Naval Vessels Layer */}
      {visible.naval && navalVessels.filter(hasCoords).map(v => {
        const isDark = v.is_dark_vessel;
        const color = isDark ? '#DC2626' : v.ais_status === 'mismatch' ? '#D97706' : NAVAL_COLOR;
        return (
          <React.Fragment key={`naval-${v.mmsi}`}>
            {isDark && (
              <Circle
                center={[v.latitude, v.longitude]}
                radius={600}
                pathOptions={{ color: '#DC2626', fillColor: '#DC2626', fillOpacity: 0.2, weight: 2, dashArray: '3, 3' }}
              />
            )}
            <CircleMarker
              center={[v.latitude, v.longitude]}
              radius={isDark ? 9 : 7}
              pathOptions={{ color: '#FFFFFF', fillColor: color, fillOpacity: 1, weight: 2 }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <span className="font-bold text-xs">{v.name}</span>
                {isDark && <span className="text-[10px] text-red-600 font-bold block">DARK VESSEL (NO AIS)</span>}
              </Tooltip>
              <Popup>
                <div className="text-xs space-y-1 font-sans">
                  <div className="font-extrabold text-slate-900 flex items-center justify-between">
                    <span>{v.name}</span>
                    <Badge className={isDark ? 'bg-red-700 text-white' : 'bg-sky-700 text-white'}>
                      {v.vessel_type}
                    </Badge>
                  </div>
                  <div><b>MMSI:</b> <span className="font-mono">{v.mmsi}</span></div>
                  <div><b>Speed / Course:</b> {v.sog} kts @ {v.cog}°</div>
                  <div><b>AIS Status:</b> <span className={`font-bold ${isDark ? 'text-red-700' : 'text-emerald-700'}`}>{v.ais_status?.toUpperCase()}</span></div>
                  <div><b>Coordinates:</b> {v.latitude?.toFixed(4)}, {v.longitude?.toFixed(4)}</div>
                  <div className="text-[11px] text-slate-600 pt-1 border-t border-slate-200">{v.notes}</div>
                </div>
              </Popup>
            </CircleMarker>
          </React.Fragment>
        );
      })}

      {/* Army Blue Force Tracking (BFT) Ground Units Layer */}
      {visible.army && armyUnits.filter(hasCoords).map(u => (
        <CircleMarker
          key={`army-${u.unit_id}`}
          center={[u.latitude, u.longitude]}
          radius={8}
          pathOptions={{ color: '#FFFFFF', fillColor: ARMY_COLOR, fillOpacity: 1, weight: 2 }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            <span className="font-bold text-xs">{u.callsign} ({u.unit_type})</span>
          </Tooltip>
          <Popup>
            <div className="text-xs space-y-1 font-sans">
              <div className="font-extrabold text-emerald-950 flex items-center justify-between">
                <span>{u.callsign}</span>
                <Badge className="bg-emerald-800 text-white">{u.status}</Badge>
              </div>
              <div><b>Unit ID:</b> <span className="font-mono">{u.unit_id}</span></div>
              <div><b>Type &amp; Echelon:</b> {u.unit_type} ({u.echelon})</div>
              <div><b>Heading / Speed:</b> {u.heading}° · {u.speed_kmh} km/h</div>
              <div><b>Combat Logistics:</b> Ammo {u.ammo_pct}% · Fuel {u.fuel_pct}%</div>
              <div><b>Sector:</b> {u.sector}</div>
            </div>
          </Popup>
        </CircleMarker>
      ))}

      {/* ISRO Bhuvan Satellite Thermal Hotspots Layer */}
      {visible.thermal && thermalHotspots.filter(hasCoords).map((h, idx) => (
        <CircleMarker
          key={`firms-${idx}`}
          center={[h.latitude, h.longitude]}
          radius={6}
          pathOptions={{ color: '#FFFFFF', fillColor: FIRMS_COLOR, fillOpacity: 0.9, weight: 2 }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <span className="font-bold text-xs text-red-700">ISRO Bhuvan ({h.satellite})</span>
          </Tooltip>
          <Popup>
            <div className="text-xs space-y-1 font-sans">
              <div className="font-bold text-red-900">{h.tactical_classification || 'ISRO SATELLITE THERMAL ANOMALY'}</div>
              <div><b>Satellite Sensor:</b> {h.satellite} ({h.confidence} confidence)</div>
              <div><b>Brightness:</b> {h.brightness} K · <b>Radiative Power:</b> {h.frp} MW</div>
              <div><b>Coordinates:</b> {h.latitude?.toFixed(4)}, {h.longitude?.toFixed(4)}</div>
            </div>
          </Popup>
        </CircleMarker>
      ))}

      {/* Field units */}
      {visible.units && field_units.filter(hasCoords).map(u => {
        const color = UNIT_COLORS[u.status] || '#334155';
        return (
          <CircleMarker
            key={`cop-unit-${u.id}`}
            center={[u.latitude, u.longitude]}
            radius={7}
            pathOptions={{ color: '#ffffff', fillColor: color, fillOpacity: 1, weight: 2 }}
          >
            <Popup>
              <div className="text-xs space-y-1 font-sans">
                <div className="font-extrabold text-slate-900">{u.name}</div>
                {u.is_demo && <Badge className="bg-amber-100 text-amber-800">DEMO UNIT</Badge>}
                <div><b>Type:</b> {u.type}</div>
                <div><b>Status:</b> <span className="font-bold" style={{ color }}>{u.status}</span></div>
                <div><b>Last seen:</b> {u.last_seen || 'unknown'}</div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}

      {/* Evidence */}
      {visible.evidence && evidence.filter(hasCoords).map(e => (
        <CircleMarker
          key={`cop-evidence-${e.id}`}
          center={[e.latitude, e.longitude]}
          radius={6}
          pathOptions={{ color: EVIDENCE_COLOR, fillColor: '#ffffff', fillOpacity: 1, weight: 3, dashArray: e.is_simulation ? '3, 3' : null }}
        >
          <Popup>
            <div className="text-xs space-y-1 font-sans max-w-xs">
              <div className="font-extrabold text-slate-900">{e.observation_type}</div>
              {e.is_simulation && <Badge className="bg-amber-100 text-amber-800">SIMULATED</Badge>}
              <div><b>Source:</b> {e.source_type}{e.source_id ? ` (${e.source_id})` : ''}</div>
              <div><b>Observed:</b> {e.timestamp}</div>
              <div><b>Source confidence:</b> {(e.confidence * 100).toFixed(0)}%</div>
              <div><b>Status:</b> {e.status}{e.threat_id ? ` → ${e.threat_id}` : ''}</div>
              {e.description && <div className="text-slate-600 text-[11px] pt-1 border-t border-slate-200">{e.description}</div>}
              <div className="text-[9px] text-slate-500 font-mono">{e.id}</div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

const LAYER_ROWS = [
  { key: 'threats', label: 'Threats', count: s => s.active_threat_count, swatch: THREAT_COLORS.CRITICAL },
  { key: 'naval', label: 'Indian Navy & ICG (AIS)', count: () => 'Live', swatch: NAVAL_COLOR },
  { key: 'army', label: 'Indian Army (BFT)', count: () => 'Active', swatch: ARMY_COLOR },
  { key: 'thermal', label: 'ISRO Bhuvan Sat', count: () => 'NRT', swatch: FIRMS_COLOR },
  { key: 'zones', label: 'Military Grid / Bases', count: () => 'Vector', swatch: ZONE_COLOR },
  { key: 'units', label: 'Field units', count: s => s.active_unit_count, swatch: UNIT_COLORS.ASSIGNED },
  { key: 'routes', label: 'Monitored routes', count: s => s.monitored_route_count, swatch: ROUTE_COLORS.ACTIVE },
  { key: 'evidence', label: 'Evidence', count: s => s.active_evidence_count, swatch: EVIDENCE_COLOR },
];

export function COPLayerPanel({ copData, copError, visible, onToggle }) {
  const [open, setOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 1700);
  const summary = copData?.summary;
  const updatedAt = copData ? new Date(copData.generated_at).toLocaleTimeString() : null;

  return (
    <div className="absolute bottom-6 right-3 z-[1000] w-64 font-sans text-[11px] rounded-lg border border-line bg-white/95 shadow-raised backdrop-blur-sm">
      <button onClick={() => setOpen(o => !o)} aria-expanded={open}
        className="w-full flex items-center justify-between gap-2 px-2.5 py-2 text-left">
        <span className="panel-title flex items-center gap-1.5"><Icon name="layers" size={13} /> Tactical COP layers</span>
        <span className="flex items-center gap-1.5 text-slate-500">
          {updatedAt && <span className="font-mono text-[10px]" title="Snapshot generated_at">{updatedAt}</span>}
          <Icon name={open ? 'chevronDown' : 'chevronUp'} size={14} />
        </span>
      </button>
      {!open && (
        <div className="px-2.5 pb-2 -mt-1 text-[10px] text-slate-600 space-y-0.5">
          <div className="font-mono">
            Threats {summary ? summary.active_threat_count : '–'} · Indian Navy &amp; Army BFT
          </div>
        </div>
      )}
      {open && (
        <div className="px-2.5 pb-2.5 space-y-1.5">
          <div className="space-y-0.5">
            {LAYER_ROWS.map(row => (
              <label key={row.key} className="flex items-center gap-1.5 py-0.5 cursor-pointer hover:bg-slate-50 rounded px-1">
                <input type="checkbox" className="accent-blue-600" checked={visible[row.key] !== false} onChange={() => onToggle(row.key)} />
                <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: row.swatch }} />
                <span className="flex-1 font-medium text-slate-800">{row.label}</span>
                <span className="font-mono text-slate-600 text-[10px]">{row.count(summary || {})}</span>
              </label>
            ))}
          </div>
          <div className="pt-1.5 border-t border-slate-200 text-[10px] text-slate-600 grid grid-cols-1 gap-0.5">
            <div><span className="inline-block w-3 h-3 rounded-full mr-1.5 align-middle" style={{ background: NAVAL_COLOR }} />Indian Navy / ICG vessel track (blue)</div>
            <div><span className="inline-block w-3 h-3 rounded-full mr-1.5 align-middle bg-red-600" />Dark vessel contact (red)</div>
            <div><span className="inline-block w-3 h-3 rounded-full mr-1.5 align-middle" style={{ background: ARMY_COLOR }} />Indian Army BFT unit (green)</div>
            <div><span className="inline-block w-3 h-3 rounded-full mr-1.5 align-middle" style={{ background: FIRMS_COLOR }} />ISRO Bhuvan satellite hotspot (orange)</div>
            <div><span className="inline-block w-3 h-3 border border-indigo-600 mr-1.5 align-middle" style={{ background: 'rgba(79, 70, 229, 0.2)' }} />Military base / cantonment sector</div>
          </div>
        </div>
      )}
    </div>
  );
}
