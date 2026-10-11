import { useState, useEffect, useRef } from 'react';
import Icon from './ui/Icon';
import ChakraEmblem from './ui/ChakraEmblem';
import { API_BASE_URL, BACKEND_HOST } from '../config';

export default function VideoIntelligence() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState(null);

  // Form parameters
  const [latitude, setLatitude] = useState('15.4210');
  const [longitude, setLongitude] = useState('73.7820');
  const [description, setDescription] = useState('Coastal surveillance patrol sector — Western Seaboard monitoring');
  const [restrictedZone, setRestrictedZone] = useState(false);
  const [unusualBehavior, setUnusualBehavior] = useState(false);
  const [nearAsset, setNearAsset] = useState(false);
  const [aisStatus, setAisStatus] = useState('matched');
  const [detectionMode, setDetectionMode] = useState('naval');
  const [confidenceThreshold, setConfidenceThreshold] = useState('0.40');
  const [sampleFps, setSampleFps] = useState('3.0');

  // Filter and interactive states
  const [activeCategoryFilter, setActiveCategoryFilter] = useState('ALL');
  const [operatorReviewDecision, setOperatorReviewDecision] = useState(null);
  const [activeTab, setActiveTab] = useState('video'); // 'video' | 'detections' | 'evidence'

  const videoRef = useRef(null);

  useEffect(() => {
    fetchPipelineStatus();
  }, []);

  async function fetchPipelineStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/vision/status`);
      if (res.ok) {
        const data = await res.json();
        setPipelineStatus(data);
      }
    } catch {
      // Offline fallback
    }
  }

  async function analyzeVideo(event) {
    if (event) event.preventDefault();
    if (!file) return;

    setLoading(true);
    setError('');
    setResult(null);
    setOperatorReviewDecision(null);

    const body = new FormData();
    body.append('file', file);
    body.append('description', description);
    body.append('confidence_threshold', confidenceThreshold);
    body.append('sample_fps', sampleFps);
    body.append('detection_mode', detectionMode);
    body.append('restricted_zone_entry', String(restrictedZone));
    body.append('unusual_behavior_observed', String(unusualBehavior));
    body.append('near_protected_asset', String(nearAsset));
    body.append('ais_status', aisStatus);

    if (latitude.trim()) body.append('latitude', latitude);
    if (longitude.trim()) body.append('longitude', longitude);

    try {
      const response = await fetch(`${API_BASE_URL}/vision/analyze-video`, {
        method: 'POST',
        body,
      });

      if (!response.ok) {
        let errorMsg = `Analysis request rejected (${response.status})`;
        try {
          const errData = await response.json();
          if (errData.detail) errorMsg = errData.detail;
        } catch {
          const text = await response.text().catch(() => '');
          if (text) errorMsg = text;
        }
        throw new Error(errorMsg);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Video analysis pipeline encountered an error');
    } finally {
      setLoading(false);
    }
  }

  function handleSeekTo(seconds) {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, seconds);
      videoRef.current.play().catch(() => {});
    }
  }

  // Precompute filtered detections
  const allDetections = result
    ? result.frames.flatMap(f =>
        f.detections.map(d => ({
          ...d,
          frameIndex: f.frame,
          timestamp: f.timestamp_seconds,
        }))
      )
    : [];

  const filteredDetections = allDetections.filter(d => {
    if (activeCategoryFilter === 'ALL') return true;
    if (activeCategoryFilter === 'VESSEL') return d.category === 'vessel';
    if (activeCategoryFilter === 'PERSON') return d.category === 'person';
    if (activeCategoryFilter === 'PROJECTILE') return d.category === 'projectile' || d.label.includes('missile');
    if (activeCategoryFilter === 'FIRE') return d.label === 'fire';
    if (activeCategoryFilter === 'FIRE_SMOKE') return d.category === 'fire_smoke' && d.label !== 'fire';
    if (activeCategoryFilter === 'SUSPICIOUS') return d.category === 'suspicious_object';
    return true;
  });

  const vesselCount = allDetections.filter(d => d.category === 'vessel').length;
  const personCount = allDetections.filter(d => d.category === 'person').length;
  const projectileCount = allDetections.filter(d => d.category === 'projectile' || d.label.includes('missile')).length;
  const fireCount = allDetections.filter(d => d.label === 'fire').length;
  const fireSmokeCount = allDetections.filter(d => d.category === 'fire_smoke' && d.label !== 'fire').length;
  const suspiciousCount = allDetections.filter(d => d.category === 'suspicious_object').length;

  return (
    <div className="flex-1 flex flex-col h-full bg-[#071522] text-[#F4F6F8] overflow-hidden select-none">
      {/* Top Tactical Status Bar */}
      <div className="bg-[#101F2D] border-b border-[#1C2E3D] px-4 py-2 shrink-0 flex flex-wrap items-center justify-between gap-3 relative">
        <div className="tricolour-bar absolute top-0 left-0 right-0" />

        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-[#071522] border border-[#FF9933]/40 flex items-center justify-center text-[#FF9933] shadow-inner">
            <ChakraEmblem size={20} color="#7891A5" accentColor="#FF9933" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-black tracking-wider text-white">MARITIME SURVEILLANCE WORKSTATION</span>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-extrabold bg-[#FF9933]/15 text-[#FF9933] border border-[#FF9933]/30">
                INDIA WATCH
              </span>
            </div>
            <p className="text-[10px] text-[#7891A5] font-mono flex items-center gap-2 mt-0.5">
              <span>SECTOR: 15.42° N, 73.78° E (WESTERN SEABOARD)</span>
              <span>·</span>
              <span className="text-[#138808] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#138808] animate-pulse"></span>
                ACTIVE C2 LINK
              </span>
            </p>
          </div>
        </div>

        {/* Model Pipeline Readiness Badges */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono">
          <span className="px-2 py-0.5 rounded bg-[#071522] border border-[#1C2E3D] text-[#7891A5] flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#138808]"></span>
            YOLOv8 Boat/Crew: <b className="text-slate-200">ACTIVE</b>
          </span>
          <span className="px-2 py-0.5 rounded bg-[#071522] border border-[#1C2E3D] text-[#7891A5] flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#138808]"></span>
            Plume/Exhaust: <b className="text-slate-200">ACTIVE</b>
          </span>
          <span className="px-2 py-0.5 rounded bg-[#071522] border border-[#1C2E3D] text-[#7891A5] flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF9933]"></span>
            Blast Classifier: <b className="text-slate-200">SLIDING-WINDOW</b>
          </span>
          <span className="px-2 py-0.5 rounded bg-[#071522] border border-[#1C2E3D] text-slate-400 hidden xl:flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
            YOLO-World: <b className="text-slate-400">OFFLINE</b>
          </span>
        </div>
      </div>

      {/* 3-Column Operational Workspace Layout */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        
        {/* ======================================================== */}
        {/* COLUMN 1: Ingest, Feeds & Technical Configuration (3 cols) */}
        {/* ======================================================== */}
        <div className="lg:col-span-3 border-r border-[#1C2E3D] bg-[#0A1826] p-3 flex flex-col justify-between overflow-y-auto space-y-3">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-[#1C2E3D] pb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#7891A5] flex items-center gap-1.5">
                <Icon name="file" size={13} className="text-[#FF9933]" />
                Footage Ingest &amp; Parameters
              </span>
              <span className="text-[9px] font-mono text-[#7891A5]">QUEUE: READY</span>
            </div>

            <form onSubmit={analyzeVideo} className="space-y-3">
              {/* File Upload Box */}
              <div className="p-2.5 rounded border border-dashed border-[#263D52] bg-[#101F2D]/60 hover:border-[#FF9933]/60 transition-colors">
                <span className="block text-[10px] font-bold uppercase text-[#7891A5] tracking-wider mb-1">
                  Surveillance Feed File
                </span>
                <input
                  type="file"
                  accept="video/*"
                  onChange={e => setFile(e.target.files?.[0] || null)}
                  className="block w-full text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[10px] file:font-bold file:bg-[#FF9933] file:text-slate-950 hover:file:bg-[#e68a2e] cursor-pointer"
                />
                {file && (
                  <p className="mt-1.5 text-[10px] text-[#FF9933] font-mono truncate">
                    ✓ {file.name} ({(file.size / 1048576).toFixed(1)} MB)
                  </p>
                )}
              </div>

              {/* Observation Narrative */}
              <div>
                <label className="block text-[10px] font-bold uppercase text-[#7891A5] tracking-wider mb-1">
                  Tactical Log / Narrative
                </label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  className="w-full rounded bg-[#101F2D] border border-[#1C2E3D] p-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-[#FF9933]"
                  placeholder="Observation remarks..."
                />
              </div>

              {/* Coordinates Grid */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <label className="block text-[9px] uppercase font-bold text-[#7891A5]">Sector Lat (°N)</label>
                  <input
                    type="number"
                    step="any"
                    value={latitude}
                    onChange={e => setLatitude(e.target.value)}
                    className="w-full mt-0.5 rounded bg-[#101F2D] border border-[#1C2E3D] p-1.5 text-xs font-mono text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[9px] uppercase font-bold text-[#7891A5]">Sector Lon (°E)</label>
                  <input
                    type="number"
                    step="any"
                    value={longitude}
                    onChange={e => setLongitude(e.target.value)}
                    className="w-full mt-0.5 rounded bg-[#101F2D] border border-[#1C2E3D] p-1.5 text-xs font-mono text-slate-200"
                  />
                </div>
              </div>

              {/* Mode & Sampling */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <label className="block text-[9px] uppercase font-bold text-[#7891A5]">Target Class Mode</label>
                  <select
                    value={detectionMode}
                    onChange={e => setDetectionMode(e.target.value)}
                    className="w-full mt-0.5 rounded bg-[#101F2D] border border-[#1C2E3D] p-1.5 text-[11px] text-slate-200"
                  >
                    <option value="naval">Naval / Maritime</option>
                    <option value="general">General Coastal</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[9px] uppercase font-bold text-[#7891A5]">Sample Rate</label>
                  <select
                    value={sampleFps}
                    onChange={e => setSampleFps(e.target.value)}
                    className="w-full mt-0.5 rounded bg-[#101F2D] border border-[#1C2E3D] p-1.5 text-[11px] text-slate-200"
                  >
                    <option value="1.0">1.0 FPS</option>
                    <option value="2.0">2.0 FPS</option>
                    <option value="3.0">3.0 FPS</option>
                    <option value="5.0">5.0 FPS</option>
                  </select>
                </div>
              </div>

              {/* Confidence Threshold */}
              <div className="p-2 rounded bg-[#101F2D] border border-[#1C2E3D]">
                <div className="flex justify-between items-center text-[10px]">
                  <span className="font-bold text-[#7891A5] uppercase">Confidence Filter</span>
                  <span className="font-mono text-[#FF9933] font-bold">{Math.round(confidenceThreshold * 100)}%</span>
                </div>
                <input
                  type="range"
                  min="0.20"
                  max="0.80"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={e => setConfidenceThreshold(e.target.value)}
                  className="w-full mt-1.5 accent-[#FF9933] cursor-pointer"
                />
              </div>

              {/* Context Flags */}
              <div className="p-2.5 rounded bg-[#101F2D] border border-[#1C2E3D] space-y-1.5">
                <span className="block text-[9px] font-bold uppercase tracking-wider text-[#7891A5]">
                  Coastal Surveillance Context
                </span>

                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={restrictedZone}
                    onChange={e => setRestrictedZone(e.target.checked)}
                    className="accent-[#FF9933]"
                  />
                  <span>Restricted Zone Encroachment</span>
                </label>

                <div className="pt-1">
                  <span className="block text-[9px] text-[#7891A5]">AIS Correlation Broadcast:</span>
                  <select
                    value={aisStatus}
                    onChange={e => setAisStatus(e.target.value)}
                    className="w-full mt-0.5 rounded bg-[#071522] border border-[#1C2E3D] p-1 text-[11px] text-slate-200"
                  >
                    <option value="matched">Matched Shore Station</option>
                    <option value="missing">Zero AIS Broadcast (Dark)</option>
                    <option value="mismatch">Identity/Position Mismatch</option>
                    <option value="unknown">Unknown / Unchecked</option>
                  </select>
                </div>

                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={unusualBehavior}
                    onChange={e => setUnusualBehavior(e.target.checked)}
                    className="accent-[#FF9933]"
                  />
                  <span>Unusual Tactical Maneuvering</span>
                </label>
              </div>

              {/* Submit Trigger */}
              <button
                type="submit"
                disabled={!file || loading}
                className="w-full py-2.5 px-4 rounded font-bold text-xs uppercase tracking-wider text-slate-950 bg-[#FF9933] hover:bg-[#e68a2e] transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-[#FF9933]/10 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <ChakraEmblem size={16} spin={true} color="#071522" accentColor="#071522" />
                    Executing Intelligence Pipeline…
                  </>
                ) : (
                  <>
                    <Icon name="radar" size={16} />
                    Process Surveillance Video
                  </>
                )}
              </button>

              {error && (
                <div className="p-2 rounded bg-red-950/40 border border-[#D64545] text-[#D64545] text-xs">
                  {error}
                </div>
              )}
            </form>
          </div>

          <div className="pt-2 border-t border-[#1C2E3D] text-[9px] text-[#7891A5] font-mono text-center">
            AEGIS-COP MARITIME C2 · SECURE EDGE WORKSTATION
          </div>
        </div>

        {/* ======================================================== */}
        {/* COLUMN 2: Surveillance Centerpiece Video & Scrubber (6 cols) */}
        {/* ======================================================== */}
        <div className="lg:col-span-6 flex flex-col min-h-0 bg-[#071522] border-r border-[#1C2E3D]">
          {result ? (
            <div className="flex-1 flex flex-col min-h-0 p-3 space-y-3 overflow-y-auto">
              
              {/* Main Video Screen with HUD */}
              <div className="relative rounded-lg overflow-hidden bg-black border border-[#1C2E3D] shadow-2xl">
                <video
                  ref={videoRef}
                  controls
                  className="w-full max-h-[460px] object-contain bg-black"
                  src={`${BACKEND_HOST}${result.annotated_video_url}`}
                />
                
                {/* Visual HUD Overlay Bar */}
                <div className="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none px-2.5 py-1.5 rounded bg-[#071522]/85 backdrop-blur-sm border border-[#1C2E3D]/80 text-[10px] font-mono">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#138808] animate-pulse"></span>
                    <span className="text-[#FF9933] font-bold">TACTICAL FEED OVERLAY</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[#7891A5]">
                      RUN: {result.run_id.slice(0, 8).toUpperCase()} · FPS: {result.metrics.analysis_fps}
                    </span>
                    <a
                      href={`${BACKEND_HOST}${result.annotated_video_url}`}
                      download={`aegis-${result.run_id.slice(0, 8)}-annotated.mp4`}
                      className="pointer-events-auto px-2 py-0.5 rounded bg-[#FF9933] hover:bg-[#e68a2e] text-slate-950 font-bold flex items-center gap-1 text-[9px] shadow"
                      title="Quick download"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      DOWNLOAD
                    </a>
                  </div>
                </div>
              </div>

              {/* Dedicated Download & Feed Export Action Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-[#101F2D] border border-[#1C2E3D] shadow-sm">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#138808] animate-pulse"></span>
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    Annotated Surveillance Video
                  </span>
                  <span className="text-[10px] font-mono text-[#7891A5]">
                    (MP4 / H.264 Overlays)
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {/* Primary Download Button */}
                  <a
                    href={`${BACKEND_HOST}${result.annotated_video_url}`}
                    download={`aegis-${result.run_id.slice(0, 8)}-annotated.mp4`}
                    className="px-3.5 py-1.5 rounded bg-[#FF9933] hover:bg-[#e68a2e] text-slate-950 text-xs font-black transition-all flex items-center gap-1.5 shadow-md shadow-[#FF9933]/20"
                    title="Download the full annotated MP4 video with tactical bounding boxes and track IDs"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Download Annotated Video (.mp4)
                  </a>

                  {/* Open in Separate Tab */}
                  <a
                    href={`${BACKEND_HOST}${result.annotated_video_url}`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-2.5 py-1.5 rounded bg-[#071522] hover:bg-[#1C2E3D] text-[#7891A5] hover:text-white border border-[#1C2E3D] text-xs font-semibold transition-all flex items-center gap-1"
                    title="Open annotated video in a new browser tab"
                  >
                    <Icon name="link" size={13} />
                    Open Tab
                  </a>
                </div>
              </div>

              {/* Category Filter Buttons Bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-[#101F2D] border border-[#1C2E3D]">
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('ALL')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'ALL'
                        ? 'bg-[#FF9933] text-slate-950'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    All Contacts ({allDetections.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('VESSEL')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'VESSEL'
                        ? 'bg-[#138808] text-white'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    Vessels ({vesselCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('PERSON')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'PERSON'
                        ? 'bg-[#7891A5] text-slate-950'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    Personnel ({personCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('PROJECTILE')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'PROJECTILE'
                        ? 'bg-[#FF9933] text-slate-950 font-black shadow-md'
                        : projectileCount > 0
                        ? 'bg-[#FF9933]/15 text-[#FF9933] hover:text-white border border-[#FF9933]/40'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    Missiles / Projectiles ({projectileCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('FIRE')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'FIRE'
                        ? 'bg-[#D64545] text-white font-black shadow-md'
                        : fireCount > 0
                        ? 'bg-[#D64545]/15 text-[#D64545] hover:text-white border border-[#D64545]/40'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    Active Fire ({fireCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('FIRE_SMOKE')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'FIRE_SMOKE'
                        ? 'bg-[#7891A5] text-slate-950 font-bold'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    Smoke Plumes ({fireSmokeCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveCategoryFilter('SUSPICIOUS')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                      activeCategoryFilter === 'SUSPICIOUS'
                        ? 'bg-[#D64545] text-white'
                        : 'bg-[#071522] text-[#7891A5] hover:text-white border border-[#1C2E3D]'
                    }`}
                  >
                    Suspicious Objects ({suspiciousCount})
                  </button>
                </div>

                <span className="text-[10px] font-mono text-[#7891A5]">
                  {result.metrics.frames_processed} frames sampled
                </span>
              </div>

              {/* Evidence Frame Thumbnails Scrubber */}
              {result.evidence_thumbnails && result.evidence_thumbnails.length > 0 && (
                <div className="p-2.5 rounded bg-[#101F2D] border border-[#1C2E3D] space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-[#7891A5]">
                    <span className="flex items-center gap-1 text-[#FF9933]">
                      <Icon name="eye" size={13} />
                      Evidence Frame Captures (Click to jump timestamp)
                    </span>
                    <span>{result.evidence_thumbnails.length} captures</span>
                  </div>

                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {result.evidence_thumbnails.map((thumb, idx) => (
                      <div
                        key={idx}
                        onClick={() => handleSeekTo(thumb.timestamp_seconds)}
                        className="p-1 rounded bg-[#071522] hover:bg-[#1C2E3D] border border-[#1C2E3D] hover:border-[#FF9933] cursor-pointer shrink-0 transition-all text-center group"
                      >
                        <img
                          src={`${BACKEND_HOST}${thumb.url}`}
                          alt={`Thumbnail at ${thumb.timestamp_seconds}s`}
                          className="w-24 h-16 object-cover rounded bg-black border border-black"
                          loading="lazy"
                        />
                        <div className="mt-1 font-mono text-[10px] text-[#FF9933] font-bold group-hover:text-white">
                          T+{thumb.timestamp_seconds}s
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Detection Log Table */}
              <div className="p-2.5 rounded bg-[#101F2D] border border-[#1C2E3D] space-y-2 flex-1 min-h-[160px] flex flex-col">
                <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-[#7891A5]">
                  <span>Telemetry Detection Stream</span>
                  <span className="font-mono text-[#7891A5]">{filteredDetections.length} recorded</span>
                </div>

                <div className="overflow-x-auto flex-1 max-h-56 overflow-y-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[#071522] text-[#7891A5] text-[10px] sticky top-0">
                      <tr>
                        <th className="p-1.5">Time</th>
                        <th className="p-1.5">Contact / Label</th>
                        <th className="p-1.5">Track ID</th>
                        <th className="p-1.5">Confidence</th>
                        <th className="p-1.5">Model Source</th>
                        <th className="p-1.5">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1C2E3D] text-[11px]">
                      {filteredDetections.slice(0, 100).map((d, i) => (
                        <tr key={i} className="hover:bg-[#071522]/60">
                          <td className="p-1.5 font-bold text-[#FF9933]">
                            <button
                              type="button"
                              onClick={() => handleSeekTo(d.timestamp)}
                              className="hover:underline"
                            >
                              T+{d.timestamp}s
                            </button>
                          </td>
                          <td className="p-1.5 font-sans font-semibold text-white capitalize">
                            {d.label.replace('_', ' ')}
                          </td>
                          <td className="p-1.5 text-slate-400">
                            {d.track_id !== null ? `#${d.track_id}` : '—'}
                          </td>
                          <td className="p-1.5 text-[#138808] font-bold">
                            {Math.round(d.confidence * 100)}%
                          </td>
                          <td className="p-1.5 text-[#7891A5] text-[10px]">{d.model_name}</td>
                          <td className="p-1.5">
                            <span
                              className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                                d.verification_status === 'detected'
                                  ? 'bg-[#138808]/20 text-[#138808]'
                                  : d.verification_status === 'possible_event'
                                  ? 'bg-[#FF9933]/20 text-[#FF9933]'
                                  : 'bg-[#7891A5]/20 text-[#7891A5]'
                              }`}
                            >
                              {d.verification_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            /* Empty State: Indian Coastline Technical Nautical Graphic */
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center nautical-grid">
              <div className="w-24 h-24 rounded-full bg-[#101F2D] border border-[#263D52] flex items-center justify-center shadow-xl shadow-black/40 mb-4 text-[#7891A5] relative">
                <ChakraEmblem size={56} color="#7891A5" accentColor="#FF9933" />
                <div className="absolute inset-0 rounded-full border border-[#FF9933]/20 animate-ping pointer-events-none" />
              </div>

              <h3 className="text-base font-bold text-white tracking-wide">
                INDIAN MARITIME WATCH · READY FOR INGEST
              </h3>
              <p className="text-xs text-[#7891A5] max-w-md mt-1.5 leading-relaxed">
                Select coastal surveillance footage from the left panel to execute multi-model vessel detection,
                plume classification, and kinematic tracking across the Western Seaboard.
              </p>

              {/* Technical Coordinates Grid Ticks */}
              <div className="mt-6 grid grid-cols-3 gap-4 text-[10px] font-mono text-[#7891A5] border-t border-[#1C2E3D] pt-4">
                <div>
                  <span className="block text-slate-500">COVERAGE</span>
                  <span className="font-bold text-slate-300">ARABIAN SEA</span>
                </div>
                <div>
                  <span className="block text-slate-500">RADAR HORIZON</span>
                  <span className="font-bold text-[#FF9933]">35 KM OPTICAL</span>
                </div>
                <div>
                  <span className="block text-slate-500">LINK PROTOCOL</span>
                  <span className="font-bold text-[#138808]">AISSTREAM / COP</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ======================================================== */}
        {/* COLUMN 3: Vessel Intel, AIS & Threat Review (3 cols)      */}
        {/* ======================================================== */}
        <div className="lg:col-span-3 bg-[#0A1826] p-3 flex flex-col justify-between overflow-y-auto space-y-3">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-[#1C2E3D] pb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#7891A5] flex items-center gap-1.5">
                <Icon name="shield" size={13} className="text-[#138808]" />
                Maritime Intelligence &amp; AIS
              </span>
              <span className="text-[9px] font-mono text-[#138808]">SECURE</span>
            </div>

            {result ? (
              <>
                {/* Vessel Intelligence Card */}
                {result.vessel_intelligence && result.vessel_intelligence.length > 0 ? (
                  result.vessel_intelligence.map(v => (
                    <div
                      key={v.track_id}
                      className="p-3 rounded bg-[#101F2D] border border-[#1C2E3D] space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white flex items-center gap-1.5">
                          <Icon name="anchor" size={14} className="text-[#FF9933]" />
                          Vessel Contact #{v.track_id}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#138808]/20 text-[#138808] border border-[#138808]/30">
                          {v.size_category === 'large_vessel' ? 'Large Vessel' : 'Small Craft'}
                        </span>
                      </div>

                      <div className="text-[11px] text-[#7891A5] space-y-1">
                        <p>Class: <span className="font-mono text-white capitalize">{v.vessel_class}</span></p>
                        <p>
                          Personnel on Board:{' '}
                          <span className="font-semibold text-slate-200">
                            {v.people_observed_onboard > 0
                              ? `${v.people_observed_onboard} crew observed`
                              : 'None observed'}
                          </span>
                        </p>
                        {v.course_bearing_deg !== null && (
                          <p>
                            Estimated Bearing:{' '}
                            <span className="font-mono text-[#FF9933]">{v.course_bearing_deg}°</span>
                          </p>
                        )}
                        <p className="text-[9px] text-slate-500 italic">
                          Size classification is an uncalibrated optical heuristic.
                        </p>
                      </div>

                      {/* AIS Broadcast Correlation */}
                      <div className="pt-2 border-t border-[#1C2E3D] text-[10px]">
                        <div className="flex justify-between items-center font-bold">
                          <span className="text-[#7891A5]">AIS Correlation:</span>
                          <span
                            className={
                              v.ais_correlation?.status === 'matched'
                                ? 'text-[#138808]'
                                : v.ais_correlation?.status === 'missing'
                                ? 'text-[#FF9933]'
                                : 'text-[#7891A5]'
                            }
                          >
                            {v.ais_correlation?.status?.toUpperCase() || 'UNKNOWN'}
                          </span>
                        </div>
                        <p className="text-[#7891A5] text-[10px] mt-1 leading-relaxed">
                          {v.ais_correlation?.notes}
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-3 rounded bg-[#101F2D] border border-[#1C2E3D] text-xs text-[#7891A5] italic">
                    No vessel tracks correlated in this run.
                  </div>
                )}
                {/* Critical Kinetic & Combat Events Alert Card */}
                {result.events && result.events.length > 0 && (
                  <div className="p-3 rounded bg-[#101F2D] border border-[#D64545]/40 space-y-2 text-xs shadow-lg shadow-red-950/20">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white flex items-center gap-1.5 uppercase text-[10px] tracking-wider text-[#FF9933]">
                        <Icon name="alert-triangle" size={14} className="text-[#D64545]" />
                        Critical Operational Events ({result.events.length})
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-black bg-[#D64545]/20 text-[#D64545] border border-[#D64545]/40 animate-pulse">
                        HIGH PRIORITY
                      </span>
                    </div>

                    <div className="space-y-1.5">
                      {result.events.map((ev, idx) => (
                        <div
                          key={idx}
                          className="p-2 rounded bg-[#071522] border border-[#1C2E3D] hover:border-[#FF9933] text-[10px] space-y-1 cursor-pointer transition-all"
                          onClick={() => handleSeekTo(ev.start_time_s)}
                        >
                          <div className="flex items-center justify-between font-bold">
                            <span className="text-[#FF9933] uppercase">
                              {ev.event_type.replaceAll('_', ' ')}
                            </span>
                            <span className="font-mono text-white text-[11px] hover:underline">
                              T+{ev.start_time_s}s - T+{ev.end_time_s}s ▶
                            </span>
                          </div>
                          <p className="text-[9px] text-[#7891A5] leading-tight">
                            {ev.notes || 'Temporal optical anomaly flagged for command review.'}
                          </p>
                          <div className="flex items-center justify-between text-[9px] text-slate-400 font-mono pt-0.5">
                            <span>Conf: {Math.round(ev.confidence * 100)}%</span>
                            <span className="text-[#138808] font-bold capitalize">{ev.verification_status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Threat & Review Assessment */}
                <div className="p-3 rounded bg-[#101F2D] border border-[#1C2E3D] space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#7891A5] uppercase text-[10px]">Review Priority</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        result.threat_assessment.level.includes('URGENT')
                          ? 'bg-[#D64545]/20 text-[#D64545] border border-[#D64545]/40 animate-pulse'
                          : result.threat_assessment.level.includes('HIGH') || result.threat_assessment.level.includes('ELEVATED')
                          ? 'bg-[#FF9933]/20 text-[#FF9933] border border-[#FF9933]/40'
                          : 'bg-[#138808]/20 text-[#138808] border border-[#138808]/40'
                      }`}
                    >
                      {result.threat_assessment.level.replaceAll('_', ' ')}
                    </span>
                  </div>

                  <p className="text-[11px] text-[#7891A5]">
                    Review Score: <b className="text-white font-mono">{result.threat_assessment.score}/100</b>
                    {' (Rule priority · Not probability)'}
                  </p>

                  <div className="space-y-1.5 pt-1">
                    {result.threat_assessment.indicators.map((it, idx) => (
                      <div key={idx} className="p-2 rounded bg-[#071522] border border-[#1C2E3D] text-[10px] text-slate-300">
                        <div className="font-bold text-white flex justify-between">
                          <span>{it.code.replaceAll('_', ' ')}</span>
                          {it.points > 0 && <span className="text-[#FF9933]">+{it.points}</span>}
                        </div>
                        <p className="text-[9px] text-[#7891A5] mt-0.5 leading-tight">{it.evidence}</p>
                      </div>
                    ))}
                  </div>

                  {/* Uncertainty & Caveats */}
                  <div className="p-2 rounded bg-[#071522]/80 border border-[#263D52] text-[9px] text-[#7891A5] space-y-0.5">
                    <p className="font-bold text-[#FF9933]">OPERATIONAL CAUTION</p>
                    <p>• Automated detections cannot confirm military ship nationality or weapons.</p>
                    <p>• AIS absence does not prove hostile intent.</p>
                    <p>• Exhaust smoke is distinguished from active fire.</p>
                  </div>

                  {/* Operator Decisions */}
                  <div className="pt-2 border-t border-[#1C2E3D] space-y-1.5">
                    <span className="block text-[9px] text-[#7891A5] font-bold uppercase">Operator Action</span>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        type="button"
                        onClick={() => setOperatorReviewDecision('VERIFIED_MARITIME_WATCH')}
                        className="py-1.5 px-2 rounded bg-[#138808] hover:bg-[#0f6b06] text-white text-[10px] font-bold transition-all text-center"
                      >
                        ✓ Log to Watch
                      </button>
                      <button
                        type="button"
                        onClick={() => setOperatorReviewDecision('FLAGGED_FALSE_ALARM')}
                        className="py-1.5 px-2 rounded bg-[#1C2E3D] hover:bg-[#263D52] text-slate-300 text-[10px] font-semibold transition-all text-center"
                      >
                        Dismiss Alarm
                      </button>
                    </div>
                    {operatorReviewDecision && (
                      <p className="text-[9px] text-[#FF9933] font-mono text-center pt-1">
                        Recorded: {operatorReviewDecision}
                      </p>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="p-4 rounded bg-[#101F2D] border border-[#1C2E3D] text-xs text-[#7891A5] space-y-2">
                <p className="font-semibold text-slate-300">Awaiting Footage Analysis</p>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Vessel kinematic profiles, size estimates, and explainable threat scoring will appear here
                  once footage is processed.
                </p>
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-[#1C2E3D] text-[9px] text-[#7891A5] font-mono">
            EVIDENCE ID: {result?.evidence_id || 'STANDBY'}
          </div>
        </div>
      </div>
    </div>
  );
}
