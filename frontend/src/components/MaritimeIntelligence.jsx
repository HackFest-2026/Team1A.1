import React, { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Icon from './ui/Icon';
import ChakraEmblem from './ui/ChakraEmblem';
import MapAutoResize from './ui/MapAutoResize';
import { API_BASE_URL } from '../config';

// Helper component to auto-pan/fit map to bounds
function MapBoundsFitter({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length === 2) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
    }
  }, [bounds, map]);
  return null;
}

// Icon generator for vessels based on ship type and course
function createVesselMarkerIcon(shipType, name, cog, isSelected = false) {
  const typeLower = (shipType || '').toLowerCase();
  let bg = '#3B82F6'; // Cargo / Default blue
  let symbol = '🚢';

  if (typeLower.includes('military') || typeLower.includes('patrol')) {
    bg = '#FF9933'; // Saffron for naval/patrol
    symbol = '⚓';
  } else if (typeLower.includes('tanker')) {
    bg = '#EF4444'; // Red
    symbol = '🛢️';
  } else if (typeLower.includes('fishing')) {
    bg = '#10B981'; // Green
    symbol = '🐟';
  } else if (typeLower.includes('research')) {
    bg = '#8B5CF6'; // Purple
    symbol = '🔬';
  }

  const rotation = typeof cog === 'number' ? cog : 0;
  const border = isSelected ? '3px solid #F59E0B' : '2px solid rgba(255,255,255,0.9)';
  const shadow = isSelected ? '0 0 12px #F59E0B' : '0 2px 6px rgba(0,0,0,0.5)';

  return L.divIcon({
    html: `
      <div style="display:flex; flex-direction:column; align-items:center; cursor:pointer;">
        <div style="
          width: 28px; height: 28px; border-radius: 50%; background: ${bg};
          border: ${border}; box-shadow: ${shadow}; display: flex; align-items: center;
          justify-content: center; font-size: 13px; transform: rotate(${rotation}deg);
          transition: transform 0.2s ease;
        ">
          ${symbol}
        </div>
        <div style="
          margin-top: 2px; font-size: 9px; font-weight: 700; color: #E2E8F0;
          background: rgba(15, 23, 42, 0.85); padding: 1px 4px; border-radius: 4px;
          border: 1px solid rgba(255,255,255,0.2); white-space: nowrap; max-width: 90px;
          overflow: hidden; text-overflow: ellipsis; text-align: center;
        ">
          ${name || 'VESSEL'}
        </div>
      </div>
    `,
    className: 'custom-ais-marker',
    iconSize: [32, 44],
    iconAnchor: [16, 14]
  });
}

// Icon for active playback vessel marker
const activePlaybackIcon = L.divIcon({
  html: `
    <div style="position:relative; display:flex; align-items:center; justify-content:center;">
      <div style="position:absolute; width: 36px; height: 36px; border-radius: 50%; background: rgba(255,153,51,0.35); animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
      <div style="width: 26px; height: 26px; border-radius: 50%; background: #FF9933; border: 3px solid white; box-shadow: 0 0 14px #FF9933; display: flex; align-items: center; justify-content: center; font-size: 13px; z-index: 2;">
        🧭
      </div>
    </div>
  `,
  className: 'custom-playback-marker',
  iconSize: [36, 36],
  iconAnchor: [18, 18]
});

export default function MaritimeIntelligence() {
  // Navigation & Sub-tabs
  const [activePanel, setActivePanel] = useState('vessels'); // 'vessels', 'playback', 'route', 'import'

  // AIS Dataset State
  const [summary, setSummary] = useState(null);
  const [vessels, setVessels] = useState([]);
  const [selectedMmsi, setSelectedMmsi] = useState(null);
  const [loadingVessels, setLoadingVessels] = useState(false);

  // Filters
  const [searchFilter, setSearchFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [showVesselOverlay, setShowVesselOverlay] = useState(true);
  const [showSeaRouteOverlay, setShowSeaRouteOverlay] = useState(true);

  // Historical Track Playback State
  const [trackData, setTrackData] = useState(null);
  const [trackLoading, setTrackLoading] = useState(false);
  const [playbackIndex, setPlaybackIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(2); // 1x, 2x, 5x, 10x
  const playbackTimerRef = useRef(null);

  // Sea-Route Planner State
  const [ports, setPorts] = useState([]);
  const [originPort, setOriginPort] = useState('mumbai');
  const [destPort, setDestPort] = useState('colombo');
  const [speedKnots, setSpeedKnots] = useState(14);
  const [plannedRoute, setPlannedRoute] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState(null);

  // File Upload State
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState(null);
  const fileInputRef = useRef(null);

  // Map Bounds State
  const [mapBounds, setMapBounds] = useState(null);

  // Initial Data Load
  useEffect(() => {
    fetchSummary();
    fetchVessels();
    fetchPorts();
  }, []);

  // Fetch AIS Summary
  async function fetchSummary() {
    try {
      const res = await fetch(`${API_BASE_URL}/maritime/ais/summary`);
      if (res.ok) {
        const data = await res.json();
        setSummary(data.dataset);
        // If bounding box available, center map
        if (data.dataset?.bounding_box) {
          const bb = data.dataset.bounding_box;
          setMapBounds([[bb.min_lat, bb.min_lon], [bb.max_lat, bb.max_lon]]);
        }
      }
    } catch (e) {
      console.error('Failed to fetch AIS summary:', e);
    }
  }

  // Fetch Vessels
  async function fetchVessels(search = searchFilter, type = typeFilter) {
    setLoadingVessels(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (type && type !== 'ALL') params.append('ship_type', type);

      const res = await fetch(`${API_BASE_URL}/maritime/ais/vessels?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setVessels(data.vessels || []);
        // Auto-select first vessel if none selected
        if (!selectedMmsi && data.vessels?.length > 0) {
          selectVessel(data.vessels[0].mmsi);
        }
      }
    } catch (e) {
      console.error('Failed to fetch vessels:', e);
    } finally {
      setLoadingVessels(false);
    }
  }

  // Fetch Ports for Sea Route Planner
  async function fetchPorts() {
    try {
      const res = await fetch(`${API_BASE_URL}/maritime/ports`);
      if (res.ok) {
        const data = await res.json();
        setPorts(data.ports || []);
      }
    } catch (e) {
      console.error('Failed to fetch ports:', e);
    }
  }

  // Select Vessel and load its historical track
  async function selectVessel(mmsi) {
    setSelectedMmsi(mmsi);
    setIsPlaying(false);
    setTrackLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/maritime/ais/tracks/${mmsi}`);
      if (res.ok) {
        const data = await res.json();
        setTrackData(data.track);
        setPlaybackIndex(0);

        // Zoom map to track points
        if (data.track?.points?.length > 0) {
          const lats = data.track.points.map(p => p.lat);
          const lons = data.track.points.map(p => p.lon);
          setMapBounds([
            [Math.min(...lats), Math.min(...lons)],
            [Math.max(...lats), Math.max(...lons)]
          ]);
        }
      }
    } catch (e) {
      console.error('Failed to fetch vessel track:', e);
    } finally {
      setTrackLoading(false);
    }
  }

  // Handle Playback Loop
  useEffect(() => {
    if (isPlaying && trackData?.points?.length > 0) {
      const intervalMs = Math.max(80, Math.floor(600 / playbackSpeed));
      playbackTimerRef.current = setInterval(() => {
        setPlaybackIndex(prev => {
          if (prev >= trackData.points.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, intervalMs);
    } else {
      if (playbackTimerRef.current) clearInterval(playbackTimerRef.current);
    }
    return () => {
      if (playbackTimerRef.current) clearInterval(playbackTimerRef.current);
    };
  }, [isPlaying, trackData, playbackSpeed]);

  // Handle CSV file upload
  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadLoading(true);
    setUploadMessage({ type: 'info', text: `Validating & importing ${file.name}...` });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE_URL}/maritime/ais/import`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setUploadMessage({
          type: 'success',
          text: `Successfully imported ${data.summary.valid_rows} rows (${data.summary.vessel_count} vessels). Rejected: ${data.summary.rejected_rows}.`
        });
        fetchSummary();
        fetchVessels();
      } else {
        setUploadMessage({
          type: 'error',
          text: data.detail || 'Import failed. Verify CSV headers and data types.'
        });
      }
    } catch (err) {
      setUploadMessage({ type: 'error', text: `Upload failed: ${err.message}` });
    } finally {
      setUploadLoading(false);
    }
  }

  // Reload Bundled Demo Dataset
  async function handleLoadDemoDataset() {
    setUploadLoading(true);
    setUploadMessage({ type: 'info', text: 'Loading bundled Arabian Sea & Indian Ocean demonstration dataset...' });
    try {
      const res = await fetch(`${API_BASE_URL}/maritime/ais/demo-load`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setUploadMessage({
          type: 'success',
          text: `Demo dataset active: ${data.summary.valid_rows} observations across ${data.summary.vessel_count} vessels.`
        });
        fetchSummary();
        fetchVessels();
      } else {
        setUploadMessage({ type: 'error', text: data.detail || 'Failed to load demo dataset.' });
      }
    } catch (err) {
      setUploadMessage({ type: 'error', text: `Error: ${err.message}` });
    } finally {
      setUploadLoading(false);
    }
  }

  // Calculate Sea Route
  async function handleCalculateSeaRoute(e) {
    e?.preventDefault();
    if (originPort === destPort) {
      setRouteError('Origin and destination must be distinct ports.');
      return;
    }
    setRouteLoading(true);
    setRouteError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/maritime/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin: originPort,
          destination: destPort,
          speed_knots: parseFloat(speedKnots) || 14
        })
      });
      const data = await res.json();
      if (res.ok) {
        setPlannedRoute(data.route);
        // Fit map bounds to sea route coordinates
        if (data.route?.coordinates?.length > 1) {
          const lats = data.route.coordinates.map(c => c[0]);
          const lons = data.route.coordinates.map(c => c[1]);
          setMapBounds([
            [Math.min(...lats), Math.min(...lons)],
            [Math.max(...lats), Math.max(...lons)]
          ]);
        }
      } else {
        setRouteError(data.detail || 'Failed to compute sea route.');
      }
    } catch (err) {
      setRouteError(`Routing request failed: ${err.message}`);
    } finally {
      setRouteLoading(false);
    }
  }

  // Active playback point
  const currentPlaybackPoint = useMemo(() => {
    if (!trackData?.points || trackData.points.length === 0) return null;
    return trackData.points[playbackIndex] || trackData.points[0];
  }, [trackData, playbackIndex]);

  // Track coordinates up to active playback index
  const playedSegments = useMemo(() => {
    if (!trackData?.points || trackData.points.length === 0) return [];
    const activePoints = trackData.points.slice(0, playbackIndex + 1);
    const segs = [];
    let currentSeg = [];
    for (const p of activePoints) {
      if (p.gap_break && currentSeg.length > 0) {
        segs.push(currentSeg);
        currentSeg = [];
      }
      currentSeg.push([p.lat, p.lon]);
    }
    if (currentSeg.length > 0) segs.push(currentSeg);
    return segs;
  }, [trackData, playbackIndex]);

  return (
    <div className="flex-1 min-h-0 flex flex-col bg-[#071522] text-slate-100 font-sans overflow-hidden">
      
      {/* ============================================================ */}
      {/* 1. TOP HEADER & OPERATIONAL STATUS STRIP                     */}
      {/* ============================================================ */}
      <header className="bg-[#101F2D] border-b border-[#1B2E42] px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-[#071522] border border-[#FF9933]/50 flex items-center justify-center text-[#FF9933] shadow-md">
            <ChakraEmblem size={20} color="#7891A5" accentColor="#FF9933" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-black tracking-wide text-white uppercase flex items-center gap-1.5">
                <span>MARITIME INTELLIGENCE &amp; AIS TRACKING</span>
              </h1>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-blue-900/60 text-blue-300 border border-blue-500/40 tracking-wider">
                HISTORICAL AIS ARCHIVE
              </span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-emerald-900/60 text-emerald-300 border border-emerald-500/40 tracking-wider">
                UTC NORMALIZED
              </span>
            </div>
            <p className="text-[10px] text-[#7891A5] flex items-center gap-2 mt-0.5 font-mono">
              <span>Coverage: {summary?.bounding_box ? `[${summary.bounding_box.min_lat}°N, ${summary.bounding_box.min_lon}°E] to [${summary.bounding_box.max_lat}°N, ${summary.bounding_box.max_lon}°E]` : 'Detecting...'}</span>
              <span>·</span>
              <span>Total Vessels: {summary?.vessel_count || 0}</span>
              <span>·</span>
              <span>Observations: {summary?.valid_rows || 0}</span>
            </p>
          </div>
        </div>

        {/* Quick Actions in Header */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadLoading}
            className="px-2.5 py-1.5 rounded bg-blue-600/80 hover:bg-blue-600 text-white font-bold text-xs flex items-center gap-1.5 transition border border-blue-400/40 shadow-sm disabled:opacity-50"
          >
            <Icon name="file" size={13} />
            <span>Import AIS CSV</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileUpload}
            className="hidden"
          />

          <button
            onClick={handleLoadDemoDataset}
            disabled={uploadLoading}
            className="px-2.5 py-1.5 rounded bg-[#FF9933]/20 hover:bg-[#FF9933]/30 text-[#FF9933] font-bold text-xs flex items-center gap-1.5 transition border border-[#FF9933]/50 shadow-sm disabled:opacity-50"
          >
            <Icon name="refresh" size={13} />
            <span>Load Demo Dataset</span>
          </button>

          <div className="h-5 w-px bg-slate-700 mx-1 hidden sm:block" />

          {/* Layer toggles */}
          <button
            onClick={() => setShowVesselOverlay(!showVesselOverlay)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition ${
              showVesselOverlay
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/50'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
            title="Toggle AIS Vessel markers overlay on map"
          >
            Vessels: {showVesselOverlay ? 'ON' : 'OFF'}
          </button>

          <button
            onClick={() => setShowSeaRouteOverlay(!showSeaRouteOverlay)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition ${
              showSeaRouteOverlay
                ? 'bg-amber-950/60 text-amber-300 border-amber-500/50'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
            title="Toggle Sea Route overlay on map"
          >
            Sea Lanes: {showSeaRouteOverlay ? 'ON' : 'OFF'}
          </button>
        </div>
      </header>

      {/* Upload Toast Banner */}
      {uploadMessage && (
        <div className={`px-4 py-2 text-xs font-semibold flex items-center justify-between border-b ${
          uploadMessage.type === 'error' ? 'bg-red-950/80 text-red-200 border-red-700' :
          uploadMessage.type === 'success' ? 'bg-emerald-950/80 text-emerald-200 border-emerald-700' :
          'bg-blue-950/80 text-blue-200 border-blue-700'
        }`}>
          <span>ℹ {uploadMessage.text}</span>
          <button onClick={() => setUploadMessage(null)} className="text-slate-300 hover:text-white font-bold ml-4">✕</button>
        </div>
      )}

      {/* ============================================================ */}
      {/* 2. MAIN WORKSTATION: WORKSPACE PANELS & LEAFLET MAP           */}
      {/* ============================================================ */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[440px_minmax(0,1fr)] overflow-hidden">
        
        {/* LEFT CONTROL SIDEBAR */}
        <div className="bg-[#101F2D] border-r border-[#1B2E42] flex flex-col min-h-0 overflow-hidden">
          
          {/* Sub-panel Navigation Tabs */}
          <div className="flex border-b border-[#1B2E42] bg-[#0A1724] px-2 pt-2 gap-1 shrink-0 overflow-x-auto">
            {[
              { id: 'vessels', label: 'AIS Vessels', icon: 'anchor', count: vessels.length },
              { id: 'playback', label: 'Track Playback', icon: 'clock', badge: trackData ? `${trackData.total_points} pts` : null },
              { id: 'route', label: 'Sea-Route Planner', icon: 'compass' },
              { id: 'import', label: 'Dataset Diagnostics', icon: 'database' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActivePanel(tab.id)}
                className={`px-3 py-2 text-xs font-bold rounded-t-md flex items-center gap-1.5 border-t border-x transition whitespace-nowrap ${
                  activePanel === tab.id
                    ? 'bg-[#101F2D] text-[#FF9933] border-[#1B2E42] border-b-[#101F2D] border-b-2'
                    : 'bg-transparent text-slate-400 border-transparent hover:text-slate-200'
                }`}
              >
                <Icon name={tab.icon} size={13} />
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
                    {tab.count}
                  </span>
                )}
                {tab.badge && (
                  <span className="ml-1 text-[9px] px-1 py-0.2 rounded bg-amber-900/60 text-amber-300 font-mono">
                    {tab.badge}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* PANEL 1: AIS VESSEL TRACKING & FILTERING */}
          {activePanel === 'vessels' && (
            <div className="flex-1 flex flex-col min-h-0 p-3 overflow-hidden">
              {/* Search & Filter Bar */}
              <div className="space-y-2 pb-3 border-b border-[#1B2E42] shrink-0">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      placeholder="Search MMSI or Vessel Name..."
                      value={searchFilter}
                      onChange={e => {
                        setSearchFilter(e.target.value);
                        fetchVessels(e.target.value, typeFilter);
                      }}
                      className="w-full bg-[#071522] border border-[#1B2E42] rounded px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#FF9933]"
                    />
                    {searchFilter && (
                      <button
                        onClick={() => {
                          setSearchFilter('');
                          fetchVessels('', typeFilter);
                        }}
                        className="absolute right-2 top-1.5 text-slate-400 hover:text-white text-xs"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  <select
                    value={typeFilter}
                    onChange={e => {
                      setTypeFilter(e.target.value);
                      fetchVessels(searchFilter, e.target.value);
                    }}
                    className="bg-[#071522] border border-[#1B2E42] rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-[#FF9933]"
                  >
                    <option value="ALL">All Vessel Types</option>
                    {(summary?.vessel_types || ['Cargo', 'Tanker', 'Fishing', 'Military Ops', 'Research']).map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center justify-between text-[11px] text-[#7891A5]">
                  <span>Showing <b>{vessels.length}</b> vessels</span>
                  <span className="font-mono text-[10px]">Select vessel to load track</span>
                </div>
              </div>

              {/* Vessel List */}
              <div className="flex-1 overflow-y-auto space-y-2 pt-2 pr-1">
                {loadingVessels ? (
                  <div className="py-8 text-center text-xs text-slate-400">Loading vessel telemetry...</div>
                ) : vessels.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-400 bg-[#071522] rounded border border-[#1B2E42] p-4">
                    <Icon name="anchor" size={24} className="mx-auto mb-2 text-slate-500" />
                    <p className="font-bold text-slate-300">No vessels match current filters.</p>
                    <p className="text-[11px] text-slate-500 mt-1">Try clearing search or load the demo dataset.</p>
                    <button
                      onClick={handleLoadDemoDataset}
                      className="mt-3 px-3 py-1.5 rounded bg-[#FF9933]/20 hover:bg-[#FF9933]/30 text-[#FF9933] text-xs font-bold border border-[#FF9933]/40"
                    >
                      Load Demo Dataset
                    </button>
                  </div>
                ) : (
                  vessels.map(v => {
                    const isSelected = selectedMmsi === v.mmsi;
                    const pos = v.latest_position || {};
                    return (
                      <div
                        key={v.mmsi}
                        onClick={() => {
                          selectVessel(v.mmsi);
                        }}
                        className={`p-2.5 rounded border transition cursor-pointer ${
                          isSelected
                            ? 'bg-[#182C3F] border-[#FF9933] shadow-md'
                            : 'bg-[#0A1724] border-[#1B2E42] hover:bg-[#0D1E30] hover:border-slate-600'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-bold text-xs text-white truncate flex items-center gap-1.5">
                            <span className="text-[12px]">
                              {v.ship_type?.toLowerCase().includes('tanker') ? '🛢️' :
                               v.ship_type?.toLowerCase().includes('military') ? '⚓' :
                               v.ship_type?.toLowerCase().includes('fishing') ? '🐟' :
                               v.ship_type?.toLowerCase().includes('research') ? '🔬' : '🚢'}
                            </span>
                            <span>{v.ship_name || `MMSI ${v.mmsi}`}</span>
                          </span>
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                            {v.ship_type || 'Unknown'}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-[#7891A5] mt-2 font-mono">
                          <div>MMSI: <span className="text-slate-200">{v.mmsi}</span></div>
                          <div>SOG: <span className="text-amber-300 font-bold">{pos.sog !== null ? `${pos.sog} kts` : 'N/A'}</span></div>
                          <div>COG: <span className="text-slate-200">{pos.cog !== null ? `${pos.cog}°` : 'N/A'}</span></div>
                          <div>Observations: <span className="text-slate-200">{v.observation_count}</span></div>
                        </div>

                        <div className="mt-1.5 pt-1.5 border-t border-[#1B2E42]/60 flex items-center justify-between text-[10px] text-slate-400">
                          <span className="truncate">Lat: {pos.lat}° | Lon: {pos.lon}°</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              selectVessel(v.mmsi);
                              setActivePanel('playback');
                            }}
                            className="text-[#FF9933] hover:underline font-bold text-[10px] flex items-center gap-1 shrink-0 ml-2"
                          >
                            <span>Inspect Track</span>
                            <span>→</span>
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* PANEL 2: HISTORICAL TRACK PLAYBACK */}
          {activePanel === 'playback' && (
            <div className="flex-1 flex flex-col min-h-0 p-3 overflow-y-auto space-y-3">
              {trackLoading ? (
                <div className="py-12 text-center text-xs text-slate-400">Loading chronological vessel observations...</div>
              ) : !trackData ? (
                <div className="py-12 text-center text-xs text-slate-400 bg-[#071522] rounded border border-[#1B2E42] p-4">
                  <p className="font-bold text-slate-300">No vessel selected.</p>
                  <p className="mt-1 text-[11px] text-slate-500">Pick a vessel from the AIS Vessels tab to inspect historical playback.</p>
                </div>
              ) : (
                <>
                  {/* Selected Vessel Summary Card */}
                  <div className="p-3 bg-[#0A1724] border border-[#1B2E42] rounded-lg space-y-2">
                    <div className="flex justify-between items-start gap-2">
                      <div>
                        <h3 className="font-black text-sm text-white flex items-center gap-1.5">
                          <span>{trackData.ship_name}</span>
                        </h3>
                        <p className="text-[10px] text-[#7891A5] font-mono mt-0.5">
                          MMSI: {trackData.mmsi} · Type: {trackData.ship_type}
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FF9933]/20 text-[#FF9933] border border-[#FF9933]/40">
                        {trackData.total_points} PTS
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] bg-[#071522] p-2 rounded border border-[#1B2E42] font-mono">
                      <div>Track Distance: <b className="text-emerald-400">{trackData.total_distance_nm} NM</b></div>
                      <div>Segments: <b className="text-slate-200">{trackData.segment_count}</b></div>
                      <div className="col-span-2 text-[10px] text-slate-400 truncate">
                        Start: {trackData.first_observed ? new Date(trackData.first_observed).toLocaleString() : 'N/A'}
                      </div>
                      <div className="col-span-2 text-[10px] text-slate-400 truncate">
                        End: {trackData.last_observed ? new Date(trackData.last_observed).toLocaleString() : 'N/A'}
                      </div>
                    </div>
                  </div>

                  {/* Playback Controls Box */}
                  <div className="p-3 bg-[#0A1724] border border-[#1B2E42] rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-[#7891A5] flex items-center gap-1">
                        <Icon name="clock" size={13} /> Playback Controls
                      </span>
                      <div className="flex items-center gap-1 text-[10px]">
                        <span className="text-slate-400">Speed:</span>
                        {[1, 2, 5, 10].map(s => (
                          <button
                            key={s}
                            onClick={() => setPlaybackSpeed(s)}
                            className={`px-1.5 py-0.5 rounded font-bold ${
                              playbackSpeed === s
                                ? 'bg-[#FF9933] text-slate-950 font-black'
                                : 'bg-[#071522] text-slate-300 hover:bg-slate-800'
                            }`}
                          >
                            {s}x
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Timeline Slider */}
                    <div className="space-y-1">
                      <input
                        type="range"
                        min="0"
                        max={Math.max(0, (trackData.points?.length || 1) - 1)}
                        value={playbackIndex}
                        onChange={e => {
                          setPlaybackIndex(parseInt(e.target.value, 10));
                          setIsPlaying(false);
                        }}
                        className="w-full accent-[#FF9933] cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] font-mono text-slate-400">
                        <span>Pt {playbackIndex + 1} / {trackData.points.length}</span>
                        <span>Covered: {currentPlaybackPoint?.cumulative_dist_nm || 0} NM</span>
                      </div>
                    </div>

                    {/* Buttons: Play, Pause, Reset */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setIsPlaying(!isPlaying)}
                        className={`flex-1 py-1.5 rounded font-bold text-xs flex items-center justify-center gap-1.5 transition ${
                          isPlaying
                            ? 'bg-amber-600 hover:bg-amber-700 text-white'
                            : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                        }`}
                      >
                        <span>{isPlaying ? '⏸ PAUSE' : '▶ PLAY TRACK'}</span>
                      </button>
                      <button
                        onClick={() => {
                          setIsPlaying(false);
                          setPlaybackIndex(0);
                        }}
                        className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs border border-slate-700"
                        title="Reset playback to beginning"
                      >
                        ⏮ Reset
                      </button>
                    </div>

                    {/* Active Observation Telemetry Box */}
                    {currentPlaybackPoint && (
                      <div className="bg-[#071522] border border-[#1B2E42] rounded p-2.5 space-y-1 text-xs">
                        <div className="text-[10px] uppercase font-bold text-[#FF9933] flex justify-between">
                          <span>HISTORICAL OBSERVATION AT T+{playbackIndex}</span>
                          <span className="font-mono text-slate-400">
                            {new Date(currentPlaybackPoint.timestamp).toLocaleTimeString()} IST
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] font-mono text-slate-300 pt-1">
                          <div>Lat: <span className="text-white">{currentPlaybackPoint.lat}°</span></div>
                          <div>Lon: <span className="text-white">{currentPlaybackPoint.lon}°</span></div>
                          <div>Speed: <span className="text-amber-300 font-bold">{currentPlaybackPoint.sog !== null ? `${currentPlaybackPoint.sog} kts` : 'N/A'}</span></div>
                          <div>Course: <span className="text-slate-200">{currentPlaybackPoint.cog !== null ? `${currentPlaybackPoint.cog}°` : 'N/A'}</span></div>
                          <div>Heading: <span className="text-slate-200">{currentPlaybackPoint.heading !== null ? `${currentPlaybackPoint.heading}°` : 'N/A'}</span></div>
                          <div>Gap Break: <span className={currentPlaybackPoint.gap_break ? 'text-red-400 font-bold' : 'text-slate-400'}>{currentPlaybackPoint.gap_break ? 'YES' : 'NO'}</span></div>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="p-2.5 rounded bg-blue-950/30 border border-blue-900/50 text-[11px] text-blue-200 space-y-1">
                    <p className="font-bold flex items-center gap-1 text-blue-300">
                      <Icon name="info" size={13} /> Historical Movement vs Predicted
                    </p>
                    <p className="text-[10px] text-slate-400">
                      Playback displays actual historical AIS telemetry recorded by coastal transponders. Track segments separate when large time gaps exist to avoid misleading straight lines across data outages.
                    </p>
                  </div>
                </>
              )}
            </div>
          )}

          {/* PANEL 3: MARITIME SEA-ROUTE PLANNER */}
          {activePanel === 'route' && (
            <div className="flex-1 flex flex-col min-h-0 p-3 overflow-y-auto space-y-3">
              <div className="p-3 bg-[#0A1724] border border-[#1B2E42] rounded-lg space-y-3">
                <div className="flex items-center justify-between border-b border-[#1B2E42] pb-2">
                  <h3 className="font-black text-xs uppercase tracking-wide text-white flex items-center gap-1.5">
                    <Icon name="compass" size={14} className="text-[#FF9933]" />
                    <span>Topological Sea-Route Planner</span>
                  </h3>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-300 border border-amber-600/40">
                    DIJKSTRA GRAPH
                  </span>
                </div>

                <form onSubmit={handleCalculateSeaRoute} className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-bold text-[#7891A5] uppercase mb-1">
                      Origin Port / Waypoint
                    </label>
                    <select
                      value={originPort}
                      onChange={e => setOriginPort(e.target.value)}
                      className="w-full bg-[#071522] border border-[#1B2E42] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#FF9933]"
                    >
                      {ports.map(p => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.country})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-[#7891A5] uppercase mb-1">
                      Destination Port / Waypoint
                    </label>
                    <select
                      value={destPort}
                      onChange={e => setDestPort(e.target.value)}
                      className="w-full bg-[#071522] border border-[#1B2E42] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#FF9933]"
                    >
                      {ports.map(p => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.country})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-[11px] font-bold text-[#7891A5] uppercase">
                        Vessel Cruising Speed
                      </label>
                      <span className="text-xs font-mono font-bold text-amber-300">{speedKnots} knots</span>
                    </div>
                    <input
                      type="range"
                      min="5"
                      max="30"
                      step="1"
                      value={speedKnots}
                      onChange={e => setSpeedKnots(parseFloat(e.target.value))}
                      className="w-full accent-[#FF9933] cursor-pointer"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={routeLoading}
                    className="w-full py-2 rounded bg-[#FF9933] hover:bg-[#FF9933]/90 text-slate-950 font-black text-xs flex items-center justify-center gap-1.5 transition shadow-md disabled:opacity-50"
                  >
                    <Icon name="navigation" size={13} />
                    <span>{routeLoading ? 'CALCULATING ROUTE...' : 'CALCULATE SEA ROUTE'}</span>
                  </button>
                </form>

                {routeError && (
                  <div className="p-2 rounded bg-red-950/80 border border-red-700 text-red-200 text-xs font-medium">
                    ⚠️ {routeError}
                  </div>
                )}
              </div>

              {/* Calculated Route Results */}
              {plannedRoute && (
                <div className="p-3 bg-[#0A1724] border border-[#1B2E42] rounded-lg space-y-3">
                  <div className="flex justify-between items-center border-b border-[#1B2E42] pb-2">
                    <span className="text-xs font-bold text-white uppercase flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span>{plannedRoute.origin.name} → {plannedRoute.destination.name}</span>
                    </span>
                    <span className="text-xs font-bold font-mono text-emerald-300 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-700">
                      {plannedRoute.total_distance_nm} NM
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-[#071522] p-2.5 rounded border border-[#1B2E42]">
                    <div>Transit ETA: <b className="text-amber-300">{plannedRoute.estimated_days} days</b></div>
                    <div>Hours: <b className="text-slate-200">{plannedRoute.estimated_hours} hrs</b></div>
                    <div>Cruising Speed: <b className="text-slate-200">{plannedRoute.vessel_speed_knots} kts</b></div>
                    <div>Waypoints: <b className="text-slate-200">{plannedRoute.waypoint_count}</b></div>
                  </div>

                  {/* Navigable Waypoints Step-by-Step */}
                  <div className="space-y-1.5">
                    <div className="text-[10px] uppercase font-bold text-slate-400">Navigable Sea Corridor Sequence:</div>
                    <ol className="space-y-1 text-[11px] font-mono border-l-2 border-slate-700 pl-3">
                      {plannedRoute.waypoints.map((wp, idx) => (
                        <li key={idx} className="text-slate-300">
                          <span className="text-[#FF9933] font-bold">[{idx + 1}]</span>{' '}
                          <span className="text-white font-semibold">{wp.name}</span>{' '}
                          <span className="text-slate-500 text-[10px]">({wp.lat}°, {wp.lon}°)</span>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Prototype Safety Caveat */}
                  <div className="p-2.5 rounded bg-amber-950/30 border border-amber-900/60 text-[10px] text-amber-200 space-y-1">
                    <p className="font-bold flex items-center gap-1 text-amber-300">
                      <Icon name="alert" size={12} /> PROTOTYPE ROUTING CAVEAT
                    </p>
                    <p className="text-slate-400 leading-relaxed">
                      {plannedRoute.disclaimer}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* PANEL 4: DATASET IMPORT & DIAGNOSTICS */}
          {activePanel === 'import' && (
            <div className="flex-1 flex flex-col min-h-0 p-3 overflow-y-auto space-y-3">
              <div className="p-3 bg-[#0A1724] border border-[#1B2E42] rounded-lg space-y-3">
                <h3 className="font-black text-xs uppercase tracking-wide text-white flex items-center gap-1.5">
                  <Icon name="database" size={13} />
                  <span>Imported Dataset Statistics</span>
                </h3>

                <div className="space-y-2 text-xs font-mono bg-[#071522] p-3 rounded border border-[#1B2E42]">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Data Source:</span>
                    <span className="text-white font-bold truncate max-w-[200px]" title={summary?.source}>
                      {summary?.source || 'None'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Total Rows Processed:</span>
                    <span className="text-white">{summary?.total_rows || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Valid Records Accepted:</span>
                    <span className="text-emerald-400 font-bold">{summary?.valid_rows || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Rejected Rows:</span>
                    <span className={summary?.rejected_rows > 0 ? 'text-red-400 font-bold' : 'text-slate-400'}>
                      {summary?.rejected_rows || 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Unique Vessels Tracked:</span>
                    <span className="text-amber-300 font-bold">{summary?.vessel_count || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Time Range (UTC):</span>
                    <span className="text-slate-300 text-[10px]">
                      {summary?.time_range?.min_time ? `${new Date(summary.time_range.min_time).toLocaleDateString()} to ${new Date(summary.time_range.max_time).toLocaleDateString()}` : 'N/A'}
                    </span>
                  </div>
                </div>

                {/* Bounding Box Information */}
                {summary?.bounding_box && (
                  <div className="p-2.5 rounded bg-[#071522] border border-[#1B2E42] space-y-1 text-xs">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">Geographic Coverage Bounding Box</div>
                    <div className="grid grid-cols-2 gap-1 text-[11px] font-mono text-slate-300">
                      <div>Min Lat: <span className="text-white">{summary.bounding_box.min_lat}°</span></div>
                      <div>Max Lat: <span className="text-white">{summary.bounding_box.max_lat}°</span></div>
                      <div>Min Lon: <span className="text-white">{summary.bounding_box.min_lon}°</span></div>
                      <div>Max Lon: <span className="text-white">{summary.bounding_box.max_lon}°</span></div>
                    </div>
                  </div>
                )}

                {/* Sample Rejection Logs if any */}
                {summary?.rejections_sample?.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-red-400 uppercase">Rejected Rows Log (Sample):</div>
                    <div className="bg-[#071522] p-2 rounded border border-red-900/60 max-h-36 overflow-y-auto space-y-1 text-[10px] font-mono text-red-300">
                      {summary.rejections_sample.map((err, i) => (
                        <div key={i}>• {err}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Supported Columns Cheatsheet */}
              <div className="p-3 bg-[#0A1724] border border-[#1B2E42] rounded-lg space-y-2 text-xs">
                <div className="font-bold text-slate-300 uppercase text-[11px]">Supported CSV Field Names:</div>
                <ul className="text-[10px] text-slate-400 space-y-1 list-disc pl-4 font-mono">
                  <li><b>MMSI:</b> mmsi, MMSI, vessel_mmsi, vessel_id</li>
                  <li><b>Timestamp:</b> timestamp, BaseDateTime, datetime, date_time</li>
                  <li><b>Coordinates:</b> lat / LAT / latitude, lon / LON / longitude</li>
                  <li><b>Telemetry:</b> sog / SOG / speed (kts), cog / COG / course (deg), heading</li>
                  <li><b>Ship Info:</b> ship_name / VesselName, ship_type / VesselType</li>
                </ul>
              </div>
            </div>
          )}

        </div>

        {/* RIGHT AREA: INTERACTIVE LEAFLET MARITIME MAP */}
        <div className="relative h-full w-full bg-[#030B14] overflow-hidden">
          
          <MapContainer
            center={[15.0, 75.0]}
            zoom={5}
            className="h-full w-full z-10"
            zoomControl={true}
          >
            <MapAutoResize />
            {mapBounds && <MapBoundsFitter bounds={mapBounds} />}

            {/* Standard OpenStreetMap basemap tile layer (no API key required) */}
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              className="basemap-tiles"
            />

            {/* 1. AIS VESSEL MARKERS OVERLAY */}
            {showVesselOverlay && vessels.map(v => {
              const pos = v.latest_position;
              if (!pos || pos.lat === undefined || pos.lon === undefined) return null;
              const isSelected = v.mmsi === selectedMmsi;

              return (
                <Marker
                  key={v.mmsi}
                  position={[pos.lat, pos.lon]}
                  icon={createVesselMarkerIcon(v.ship_type, v.ship_name, pos.cog, isSelected)}
                  eventHandlers={{
                    click: () => selectVessel(v.mmsi)
                  }}
                >
                  <Popup>
                    <div className="p-1 space-y-1 text-slate-900 text-xs">
                      <div className="font-bold text-sm text-slate-950 flex items-center justify-between gap-2 border-b pb-1">
                        <span>{v.ship_name}</span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">
                          {v.ship_type}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[11px] font-mono text-slate-700">
                        <div>MMSI: <b>{v.mmsi}</b></div>
                        <div>SOG: <b>{pos.sog !== null ? `${pos.sog} kts` : 'N/A'}</b></div>
                        <div>COG: <b>{pos.cog !== null ? `${pos.cog}°` : 'N/A'}</b></div>
                        <div>Heading: <b>{pos.heading !== null ? `${pos.heading}°` : 'N/A'}</b></div>
                      </div>
                      <div className="text-[10px] text-slate-500 pt-1">
                        Last seen: {new Date(pos.timestamp).toLocaleString()}
                      </div>
                      <button
                        onClick={() => {
                          selectVessel(v.mmsi);
                          setActivePanel('playback');
                        }}
                        className="w-full mt-2 py-1 rounded bg-[#FF9933] hover:bg-amber-600 text-slate-950 font-bold text-xs shadow-sm"
                      >
                        Inspect Historical Track
                      </button>
                    </div>
                  </Popup>
                </Marker>
              );
            })}

            {/* 2. HISTORICAL TRACK POLYLINES */}
            {trackData?.segment_coordinates?.map((seg, idx) => (
              <Polyline
                key={`full-track-seg-${idx}`}
                positions={seg}
                pathOptions={{
                  color: '#0284C7',
                  weight: 3,
                  opacity: 0.6,
                  dashArray: '4, 4'
                }}
              />
            ))}

            {/* 3. PLAYED TRACK POLYLINES (ACCUMULATED UP TO CURRENT PLAYBACK POSITION) */}
            {playedSegments.map((seg, idx) => (
              <Polyline
                key={`played-track-seg-${idx}`}
                positions={seg}
                pathOptions={{
                  color: '#FF9933',
                  weight: 4,
                  opacity: 0.95
                }}
              />
            ))}

            {/* 4. ACTIVE PLAYBACK VESSEL MARKER */}
            {currentPlaybackPoint && (
              <Marker
                position={[currentPlaybackPoint.lat, currentPlaybackPoint.lon]}
                icon={activePlaybackIcon}
              >
                <Popup>
                  <div className="p-1 space-y-1 text-slate-900 text-xs font-mono">
                    <div className="font-bold text-slate-950">{trackData?.ship_name}</div>
                    <div>Playback Step: {playbackIndex + 1} / {trackData?.points?.length}</div>
                    <div>Timestamp: {new Date(currentPlaybackPoint.timestamp).toLocaleString()}</div>
                    <div>Speed: {currentPlaybackPoint.sog} kts | Course: {currentPlaybackPoint.cog}°</div>
                  </div>
                </Popup>
              </Marker>
            )}

            {/* 5. SEA ROUTE OVERLAY */}
            {showSeaRouteOverlay && plannedRoute?.coordinates?.length > 1 && (
              <>
                <Polyline
                  positions={plannedRoute.coordinates}
                  pathOptions={{
                    color: '#10B981',
                    weight: 4,
                    dashArray: '8, 6',
                    opacity: 0.9
                  }}
                />
                {plannedRoute.waypoints.map((wp, idx) => (
                  <CircleMarker
                    key={`wp-${idx}`}
                    center={[wp.lat, wp.lon]}
                    radius={wp.type === 'PORT' ? 7 : 4}
                    pathOptions={{
                      color: wp.type === 'PORT' ? '#10B981' : '#FF9933',
                      fillColor: wp.type === 'PORT' ? '#047857' : '#D97706',
                      fillOpacity: 0.9,
                      weight: 2
                    }}
                  >
                    <Popup>
                      <div className="p-1 text-xs text-slate-900 font-mono">
                        <div className="font-bold text-slate-950">{wp.name}</div>
                        <div>Type: <b>{wp.type}</b> ({wp.country})</div>
                        <div>Lat: {wp.lat}° | Lon: {wp.lon}°</div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </>
            )}

          </MapContainer>

          {/* FLOATING MAP LEGEND & DISCLAIMER OVERLAY */}
          <div className="absolute bottom-4 right-4 z-[500] bg-[#101F2D]/90 backdrop-blur-md border border-[#1B2E42] rounded-lg p-3 text-xs text-slate-200 shadow-2xl max-w-xs space-y-2 pointer-events-auto">
            <div className="flex items-center justify-between border-b border-[#1B2E42] pb-1.5">
              <span className="font-bold text-[11px] uppercase tracking-wider text-[#FF9933] flex items-center gap-1.5">
                <ChakraEmblem size={13} color="#7891A5" accentColor="#FF9933" />
                <span>Maritime Map Legend</span>
              </span>
              <span className="text-[9px] font-mono text-slate-400">HISTORICAL</span>
            </div>

            <div className="space-y-1 text-[11px]">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#FF9933] border border-white shrink-0" />
                <span>Naval / Coast Guard / Patrol</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#EF4444] border border-white shrink-0" />
                <span>Crude Tanker / Liquid Cargo</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#3B82F6] border border-white shrink-0" />
                <span>Commercial Cargo / Container</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#10B981] border border-white shrink-0" />
                <span>Deep Sea Fishing Craft</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-1 bg-[#FF9933] shrink-0" />
                <span>Track Movement Polyline</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-1 bg-[#10B981] border-b border-dashed border-[#10B981] shrink-0" />
                <span>Navigable Sea Corridor Route</span>
              </div>
            </div>

            <div className="pt-1.5 border-t border-[#1B2E42] text-[9px] text-[#7891A5] font-mono">
              Notice: Records are historical observations. This demonstration prototype does not claim live radar broadcast correlation.
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
