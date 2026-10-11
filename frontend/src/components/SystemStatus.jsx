import { useState, useEffect } from 'react';
import Icon from './ui/Icon';
import { API_BASE_URL, BACKEND_HOST } from '../config';

export default function SystemStatus() {
  const [backendHealth, setBackendHealth] = useState(null);
  const [visionStatus, setVisionStatus] = useState(null);
  const [systemData, setSystemData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastCheck, setLastCheck] = useState(null);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  async function fetchStatus() {
    try {
      setLoading(true);
      const [hRes, vRes, sRes] = await Promise.all([
        fetch(`${API_BASE_URL}/health`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API_BASE_URL}/vision/status`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API_BASE_URL}/system/status`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);

      setBackendHealth(hRes);
      setVisionStatus(vRes);
      setSystemData(sRes);
      setLastCheck(new Date().toLocaleTimeString());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const isBackendUp = backendHealth?.status === 'ok';
  const isVisionReady = visionStatus?.status === 'ready';

  return (
    <div className="flex-1 overflow-y-auto bg-canvas p-4 space-y-4">
      {/* Header */}
      <section className="panel p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="p-2 rounded bg-slate-900 text-sky-400 border border-slate-700">
            <Icon name="shield" size={20} />
          </span>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              AEGIS-COP System Health &amp; Model Status
            </h2>
            <p className="text-xs text-slate-500">
              Operational readiness of the tactical-edge API, computer vision pipeline, and storage subsystems.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {lastCheck && (
            <span className="text-[11px] font-mono text-slate-400">
              Checked: {lastCheck}
            </span>
          )}
          <button
            onClick={fetchStatus}
            className="btn-secondary text-xs"
            title="Refresh status"
          >
            <Icon name="refresh" size={14} /> Refresh
          </button>
        </div>
      </section>

      {/* Top Health Indicators */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Backend Core</span>
          <div className="flex items-center gap-2 mt-1">
            <span className={`w-2.5 h-2.5 rounded-full ${isBackendUp ? 'bg-emerald-500' : 'bg-red-500'}`} />
            <span className="text-lg font-bold font-mono text-slate-900">
              {isBackendUp ? 'ONLINE' : 'UNREACHABLE'}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono block mt-1">{BACKEND_HOST}</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Vision Pipeline</span>
          <div className="flex items-center gap-2 mt-1">
            <span className={`w-2.5 h-2.5 rounded-full ${isVisionReady ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-lg font-bold font-mono text-slate-900">
              {isVisionReady ? 'READY' : 'DEGRADED'}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 block mt-1">OpenCV &amp; Ultralytics YOLO</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Active Weights</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-lg font-bold font-mono text-slate-900 truncate">
              {visionStatus?.model || 'yolov8n.pt'}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 block mt-1">Edge inference on CPU/CUDA</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Data Engine</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-lg font-bold font-mono text-slate-900">
              SQLITE + OSM
            </span>
          </div>
          <span className="text-[10px] text-slate-400 block mt-1">Canonical evidence store</span>
        </div>
      </div>

      {/* Subsystem Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Video Intelligence Engine */}
        <div className="panel p-4 space-y-3">
          <h3 className="font-bold text-sm text-slate-900 pb-2 border-b border-line flex items-center gap-2">
            <Icon name="video" size={16} /> Computer Vision Service Details
          </h3>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Service Status</span>
              <span className={`font-mono font-bold ${isVisionReady ? 'text-emerald-700' : 'text-amber-700'}`}>
                {visionStatus?.status || (loading ? 'Checking…' : 'Unavailable')}
              </span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Model File</span>
              <span className="font-mono text-slate-800">{visionStatus?.model || 'yolov8n.pt'}</span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Linear Assignment Tracker</span>
              <span className="font-mono text-emerald-700 font-bold">ByteTrack (lap/lapx)</span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Default Naval Class Filter</span>
              <span className="font-mono text-slate-800">
                COCO ID 8 (boat/vessel)
              </span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Supported Video Formats</span>
              <span className="font-mono text-slate-800">MP4, MOV, AVI, MKV, WEBM</span>
            </div>

            <div className="flex justify-between py-1">
              <span className="text-slate-500">Max Upload Limit</span>
              <span className="font-mono text-slate-800">150 MB</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200 text-xs text-slate-600 space-y-1">
            <div className="font-bold text-slate-800">Model Scope Notice:</div>
            <p className="text-[11px] leading-relaxed">
              {visionStatus?.note || 'Generic object detection only. Detections provide review priorities and require human operator confirmation.'}
            </p>
          </div>
        </div>

        {/* Right: Operational Infrastructure */}
        <div className="panel p-4 space-y-3">
          <h3 className="font-bold text-sm text-slate-900 pb-2 border-b border-line flex items-center gap-2">
            <Icon name="grid" size={16} /> Backend Architecture &amp; Data Feeds
          </h3>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">FastAPI Server</span>
              <span className="font-mono text-emerald-700 font-bold">{isBackendUp ? 'HEALTHY (200 OK)' : 'DOWN'}</span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Database Engine</span>
              <span className="font-mono text-slate-800">SQLite (data/aegis.db)</span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Road Network Graph</span>
              <span className="font-mono text-slate-800">{systemData?.osm || 'OSM Drive Graph (Hubballi-Dharwad)'}</span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Storage Runs Directory</span>
              <span className="font-mono text-slate-800">data/vision_runs/</span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Sensor &amp; AIS Feeds</span>
              <span className="font-mono text-slate-800">Direct Video Upload &amp; API Ingestion</span>
            </div>

            <div className="flex justify-between py-1">
              <span className="text-slate-500">Authentication</span>
              <span className="font-mono text-slate-600">Localhost edge isolation (127.0.0.1)</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200 text-xs text-slate-600 space-y-1">
            <div className="font-bold text-slate-800">Tactical Edge Integrity:</div>
            <p className="text-[11px] leading-relaxed">
              AEGIS-COP runs fully offline without requiring cloud dependencies. Video frames are processed locally and evidence records are stamped with source provenance.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
