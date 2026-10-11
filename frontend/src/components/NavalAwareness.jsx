import { useState, useEffect } from 'react';
import Icon from './ui/Icon';
import ChakraEmblem from './ui/ChakraEmblem';
import { API_BASE_URL } from '../config';

export default function NavalAwareness({ onSelectTab }) {
  const [evidenceList, setEvidenceList] = useState([]);
  const [threats, setThreats] = useState([]);
  const [liveVessels, setLiveVessels] = useState([]);
  const [aisStatus, setAisStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterMode, setFilterMode] = useState('ALL');
  const [showIngestModal, setShowIngestModal] = useState(false);

  // Ingest form state
  const [ingestForm, setIngestForm] = useState({
    name: 'TACTICAL CONTACT 01',
    mmsi: '419009988',
    vessel_type: 'CORVETTE',
    latitude: '15.4120',
    longitude: '73.7250',
    sog: '22.0',
    cog: '190.0',
    ais_status: 'matched',
    is_dark_vessel: false
  });
  const [ingestBusy, setIngestBusy] = useState(false);

  useEffect(() => {
    fetchNavalData();
    const interval = setInterval(fetchNavalData, 5000);
    return () => clearInterval(interval);
  }, []);

  async function fetchNavalData() {
    try {
      const [evRes, thRes, vesRes, statRes] = await Promise.all([
        fetch(`${API_BASE_URL}/evidence`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE_URL}/threats`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE_URL}/naval/vessels`).then(r => r.json()).catch(() => ({ vessels: [] })),
        fetch(`${API_BASE_URL}/naval/status`).then(r => r.json()).catch(() => null)
      ]);

      setEvidenceList(Array.isArray(evRes) ? evRes : []);
      setThreats(Array.isArray(thRes) ? thRes : []);
      setLiveVessels(vesRes?.vessels || []);
      setAisStatus(statRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleIngestSubmit(e) {
    e.preventDefault();
    try {
      setIngestBusy(true);
      const res = await fetch(`${API_BASE_URL}/naval/vessels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: ingestForm.name,
          mmsi: ingestForm.mmsi,
          vessel_type: ingestForm.vessel_type,
          latitude: parseFloat(ingestForm.latitude),
          longitude: parseFloat(ingestForm.longitude),
          sog: parseFloat(ingestForm.sog),
          cog: parseFloat(ingestForm.cog),
          ais_status: ingestForm.ais_status,
          is_dark_vessel: ingestForm.is_dark_vessel || ingestForm.ais_status === 'missing'
        })
      });
      if (res.ok) {
        setShowIngestModal(false);
        fetchNavalData();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIngestBusy(false);
    }
  }

  // Filter evidence that contains maritime detections (boat, ship, vessel, or naval detection mode)
  const navalEvidence = evidenceList.filter(ev => {
    const prov = ev.provenance || {};
    const classes = prov.classes_seen || [];
    const isMaritimeClass = classes.some(c => ['boat', 'ship', 'vessel'].includes(c.toLowerCase()));
    const isNavalMode = prov.detection_mode === 'naval';
    const isMaritimeObs = ['MARITIME_OBSERVATION', 'VESSEL_CONTACT'].includes(ev.observation_type);
    return isMaritimeClass || isNavalMode || isMaritimeObs;
  });

  const vesselContactCount = navalEvidence.reduce((acc, ev) => {
    const counts = ev.provenance?.unique_object_counts || {};
    return acc + (counts.boat || counts.ship || counts.vessel || 0);
  }, 0);

  const filteredVessels = liveVessels.filter(v => {
    if (filterMode === 'ALL') return true;
    if (filterMode === 'DARK') return v.is_dark_vessel;
    if (filterMode === 'MISMATCH') return v.ais_status === 'mismatch';
    return true;
  });

  return (
    <div className="flex-1 overflow-y-auto bg-canvas p-4 space-y-4">
      {/* Header with Tricolour Accent */}
      <section className="panel p-4 flex flex-wrap items-center justify-between gap-4 relative overflow-hidden">
        <div className="tricolour-bar absolute top-0 left-0 right-0" />
        <div>
          <div className="flex items-center gap-3 pt-1">
            <span className="p-2 rounded bg-slate-900 text-[#FF9933] border border-[#FF9933]/30 shadow-panel">
              <ChakraEmblem size={22} color="#7891A5" accentColor="#FF9933" />
            </span>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-bold text-slate-100 tracking-tight">
                  Indian Maritime &amp; Coastal Awareness
                </h2>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold bg-[#FF9933]/15 text-[#FF9933] border border-[#FF9933]/40 tracking-wider">
                  INDIA · EEZ WATCH
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#138808]/20 text-[#138808] border border-[#138808]/30 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#138808] animate-pulse"></span>
                  {aisStatus?.mode || 'LIVE AIS ENGINE'}
                </span>
              </div>
              <p className="text-xs text-[#7891A5] mt-0.5">
                Arabian Sea &amp; Western Seaboard tactical maritime contacts, dark-vessel identification, and coastal video intelligence.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowIngestModal(true)}
            className="btn bg-sky-700 hover:bg-sky-800 text-white text-xs font-bold"
          >
            <Icon name="plus" size={14} /> Ingest Radar / AIS Track
          </button>
          <button
            onClick={() => onSelectTab && onSelectTab('video')}
            className="btn-primary text-xs"
          >
            <Icon name="video" size={14} /> Analyze Coastal Footage
          </button>
          <button
            onClick={fetchNavalData}
            className="btn-secondary text-xs"
            title="Refresh maritime data"
          >
            <Icon name="refresh" size={14} />
          </button>
        </div>
      </section>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Live AIS Contacts</span>
          <span className="text-2xl font-bold font-mono text-sky-700">{liveVessels.length}</span>
          <span className="text-[10px] text-slate-400 block mt-0.5">Actively tracked vessels</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Dark Vessels</span>
          <span className="text-2xl font-bold font-mono text-red-700">
            {liveVessels.filter(v => v.is_dark_vessel).length}
          </span>
          <span className="text-[10px] text-red-500 font-bold block mt-0.5">Missing AIS transponder</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">AIS Identity Mismatches</span>
          <span className="text-2xl font-bold font-mono text-amber-700">
            {liveVessels.filter(v => v.ais_status === 'mismatch').length}
          </span>
          <span className="text-[10px] text-amber-600 block mt-0.5">Radar/AIS drift detected</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Vision Detections</span>
          <span className="text-2xl font-bold font-mono text-slate-900">{vesselContactCount}</span>
          <span className="text-[10px] text-slate-400 block mt-0.5">Identified via AI vision</span>
        </div>

        <div className="panel p-3">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Stream Ingestion</span>
          <span className="text-sm font-bold font-mono text-emerald-700 block mt-1">ONLINE</span>
          <span className="text-[10px] text-slate-400 block mt-0.5">{aisStatus?.active_contacts || 0} telemetry buffers</span>
        </div>
      </div>

      {/* Live AIS Vessels Table */}
      <section className="panel p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-line">
          <div>
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
              <Icon name="navigation" size={16} className="text-sky-700" />
              Live AIS Vessel Tracks &amp; Tactical Contacts
            </h3>
            <p className="text-xs text-slate-500">Real-time SOG, COG, position kinematics, and transponder verification</p>
          </div>

          <div className="flex gap-1">
            {[
              { id: 'ALL', label: 'All Contacts' },
              { id: 'DARK', label: 'Dark Vessels Only' },
              { id: 'MISMATCH', label: 'AIS Mismatches' }
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setFilterMode(item.id)}
                className={`px-2.5 py-1 text-xs rounded font-bold border transition ${
                  filterMode === item.id
                    ? 'bg-sky-900 border-sky-800 text-white'
                    : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-100 text-slate-600 font-bold uppercase tracking-wider text-[10px] border-b border-slate-200">
                <th className="p-2.5">Vessel Name / Callsign</th>
                <th className="p-2.5">MMSI</th>
                <th className="p-2.5">Type</th>
                <th className="p-2.5">Coordinates</th>
                <th className="p-2.5">Speed (SOG)</th>
                <th className="p-2.5">Course (COG)</th>
                <th className="p-2.5">AIS Status</th>
                <th className="p-2.5">Operational Assessment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 font-mono">
              {filteredVessels.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-4 text-center text-slate-400 italic">No vessel contacts matching the active filter.</td>
                </tr>
              ) : (
                filteredVessels.map(v => (
                  <tr key={v.mmsi} className={`hover:bg-slate-50 ${v.is_dark_vessel ? 'bg-red-50/50' : ''}`}>
                    <td className="p-2.5 font-bold text-slate-900 font-sans">
                      {v.name}
                      {v.is_dark_vessel && (
                        <span className="ml-1.5 px-1.5 py-0.2 rounded text-[9px] font-bold bg-red-700 text-white uppercase font-mono">
                          DARK
                        </span>
                      )}
                    </td>
                    <td className="p-2.5 text-slate-600">{v.mmsi}</td>
                    <td className="p-2.5 font-sans font-semibold text-slate-700">{v.vessel_type}</td>
                    <td className="p-2.5 text-slate-800">{v.latitude.toFixed(4)}, {v.longitude.toFixed(4)}</td>
                    <td className="p-2.5 text-sky-800 font-bold">{v.sog.toFixed(1)} kts</td>
                    <td className="p-2.5 text-slate-700">{v.cog.toFixed(0)}°</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        v.ais_status === 'matched' ? 'bg-emerald-100 text-emerald-800' :
                        v.ais_status === 'missing' ? 'bg-red-100 text-red-800' :
                        'bg-amber-100 text-amber-800'
                      }`}>
                        {v.ais_status.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-2.5 font-sans text-[11px] text-slate-600 max-w-xs truncate" title={v.notes}>
                      {v.notes}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Manual Ingest Modal */}
      {showIngestModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5 space-y-4 border border-slate-300">
            <div className="flex justify-between items-center border-b border-slate-200 pb-2">
              <h3 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                <Icon name="navigation" size={16} className="text-sky-700" />
                Ingest Radar / Sonar / AIS Contact
              </h3>
              <button onClick={() => setShowIngestModal(false)} className="text-slate-400 hover:text-slate-700 font-bold">
                ✕
              </button>
            </div>

            <form onSubmit={handleIngestSubmit} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">Vessel Name</label>
                  <input
                    type="text"
                    value={ingestForm.name}
                    onChange={e => setIngestForm({ ...ingestForm, name: e.target.value })}
                    required
                    className="w-full p-2 border border-slate-300 rounded focus:border-accent outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">MMSI (or 000000000)</label>
                  <input
                    type="text"
                    value={ingestForm.mmsi}
                    onChange={e => setIngestForm({ ...ingestForm, mmsi: e.target.value })}
                    required
                    className="w-full p-2 border border-slate-300 rounded font-mono focus:border-accent outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={ingestForm.latitude}
                    onChange={e => setIngestForm({ ...ingestForm, latitude: e.target.value })}
                    required
                    className="w-full p-2 border border-slate-300 rounded font-mono focus:border-accent outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={ingestForm.longitude}
                    onChange={e => setIngestForm({ ...ingestForm, longitude: e.target.value })}
                    required
                    className="w-full p-2 border border-slate-300 rounded font-mono focus:border-accent outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">Speed (Knots)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={ingestForm.sog}
                    onChange={e => setIngestForm({ ...ingestForm, sog: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-mono focus:border-accent outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">Heading (COG)</label>
                  <input
                    type="number"
                    value={ingestForm.cog}
                    onChange={e => setIngestForm({ ...ingestForm, cog: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-mono focus:border-accent outline-none"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-600 block mb-0.5">AIS Status</label>
                  <select
                    value={ingestForm.ais_status}
                    onChange={e => setIngestForm({ ...ingestForm, ais_status: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-bold focus:border-accent outline-none"
                  >
                    <option value="matched">Matched</option>
                    <option value="missing">Missing (Dark)</option>
                    <option value="mismatch">Mismatch</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-2 pt-2 border-t border-slate-200">
                <button
                  type="submit"
                  disabled={ingestBusy}
                  className="flex-1 bg-sky-700 hover:bg-sky-800 text-white font-bold py-2 rounded text-xs transition"
                >
                  {ingestBusy ? 'INGESTING...' : 'INGEST CONTACT'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowIngestModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700 font-bold hover:bg-slate-100"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
