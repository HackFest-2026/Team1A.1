import { useState, useEffect } from 'react';
import MapComponent from './Map';
import IncidentCenter from './IncidentCenter';
import ThreatPanel from './ThreatPanel';
import MissionPanel from './MissionPanel';
import VideoIntelligence from './VideoIntelligence';
import MaritimeIntelligence from './MaritimeIntelligence';
import NavalAwareness from './NavalAwareness';
import SystemStatus from './SystemStatus';
import DecisionChain, { DataSourceStrip } from './DecisionChain';
import Icon from './ui/Icon';
import ChakraEmblem from './ui/ChakraEmblem';
import ThemeSelector from './ui/ThemeSelector';
import { useCOP } from '../hooks/useCOP';
import { API_BASE_URL } from '../config';


export default function EocDashboard({ systemStatus }) {
  // Common Operating Picture (COP) Data Hook (10s polling refresh)
  const { data: copData, loading: copLoading, error: copError, refresh: refreshCop } = useCOP(10000);

  // Navigation active tab (Naval Video Detection is the primary landing page)
  const [activeTab, setActiveTab] = useState('video');

  // Shared Global Selected Incident State
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [selectedIncidentDetail, setSelectedIncidentDetail] = useState(null);
  const [activePlan, setActivePlan] = useState(null);

  // Backend Data States
  const [incidents, setIncidents] = useState([]);
  const [resources, setResources] = useState([]);
  const [fieldUnits, setFieldUnits] = useState([]);

  // Mission (route monitoring) state lives in the backend; MissionPanel reads it from the COP.
  const [proposedRoute, setProposedRoute] = useState(null);
  const [missionRoute, setMissionRoute] = useState(null);
  const [missionState, setMissionState] = useState(null);

  // Field Operations State Machine
  const [fieldUnitStates, setFieldUnitStates] = useState({});

  // Drawer & Toast State
  const [toastMessage, setToastMessage] = useState(null);

  // Map layer controls
  const [layers, setLayers] = useState({
    incidents: true,
    risk: true,
    resources: true,
    fieldUnits: true,
    satellite: false,
    routing: true,
  });

  const [planActionStatus, setPlanActionStatus] = useState(null);
  const [dispatchStatus, setDispatchStatus] = useState(null);
  const [lastUpdatedTime, setLastUpdatedTime] = useState(new Date().toLocaleTimeString() + ' IST');

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(() => {
      fetchAllData();
      setLastUpdatedTime(new Date().toLocaleTimeString() + ' IST');
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedIncident?.incident_id) {
      fetchIncidentResponsePlan(selectedIncident.incident_id);
    } else {
      setActivePlan(null);
    }
  }, [selectedIncident]);

  async function fetchIncidentResponsePlan(incId) {
    try {
      const res = await fetch(`${API_BASE_URL}/national/incidents/${incId}/response-plan`);
      if (res.ok) {
        const data = await res.json();
        if (data.records && data.records.length > 0) {
          setActivePlan(data.records[data.records.length - 1]);
        } else {
          setActivePlan(null);
        }
      } else {
        setActivePlan(null);
      }
    } catch (e) {
      setActivePlan(null);
    }
  }

  function showToast(msg, type = "info") {
    setToastMessage({ text: msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  }

  async function fetchAllData() {
    try {
      const [incRes, resRes, fuRes] = await Promise.all([
        fetch(`${API_BASE_URL}/national/incidents`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE_URL}/national/resources`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE_URL}/national/field-units`).then(r => r.json()).catch(() => null),
      ]);

      if (incRes?.records) {
        setIncidents(incRes.records);
        if (!selectedIncident && incRes.records.length > 0) {
          setSelectedIncident(incRes.records[0]);
          fetchIncidentDetail(incRes.records[0].incident_id);
        }
      }
      if (resRes?.records) setResources(resRes.records);
      if (fuRes?.records) setFieldUnits(fuRes.records);

    } catch (err) {
      console.error("Failed to fetch data:", err);
    }
  }

  async function fetchIncidentDetail(incidentId) {
    try {
      const res = await fetch(`${API_BASE_URL}/national/incidents/${incidentId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedIncidentDetail(data.record);
      }
    } catch (e) {
      console.error(e);
    }
  }

  function handleSelectIncident(inc) {
    setSelectedIncident(inc);
    fetchIncidentDetail(inc.incident_id);
  }

  const handleUpdateUnitState = async (unitId, nextState) => {
    try {
      const res = await fetch(`${API_BASE_URL}/national/field-units/${unitId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_status: nextState, actor: 'EOC Operator', role: 'EOC_OPERATOR' })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      setFieldUnitStates(prev => ({ ...prev, [unitId]: nextState }));
      setFieldUnits(prev => prev.map(u => u.field_unit_id === unitId ? { ...u, status: nextState } : u));
      showToast(`✓ Field unit status recorded by backend: ${nextState}`, "success");
      return true;
    } catch (e) {
      showToast(`Status change rejected: ${e.message}`, "error");
      return false;
    }
  };

  const activeIncidents = incidents.filter(i => !['RESOLVED', 'CLOSED'].includes(i.status));

  // State for Start Operation Modal
  const [activeOperationModal, setActiveOperationModal] = useState(null);

  return (
    <div className="flex h-screen bg-canvas text-slate-900 font-sans overflow-hidden">
      
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className={`fixed top-3 right-3 z-[2000] px-4 py-2.5 rounded-md font-bold text-xs shadow-lg flex items-center gap-2 border transition ${
          toastMessage.type === 'error' ? 'bg-red-50 text-red-700 border-red-200' :
          toastMessage.type === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-900 text-white border-slate-700'
        }`}>
          <span>ℹ {toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 font-black hover:opacity-75">&times;</button>
        </div>
      )}

      {/* Start Operation Modal */}
      {activeOperationModal && (
        <div className="fixed inset-0 z-[3000] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-slate-300 shadow-2xl max-w-lg w-full p-5 space-y-4 text-xs">
            <div className="flex justify-between items-center border-b border-slate-200 pb-2">
              <h3 className="font-black text-sm uppercase text-accent flex items-center gap-2">
                <Icon name="radio" size={16} /> FIELD OPERATION IN PROGRESS: {activeOperationModal.name}
              </h3>
              <button onClick={() => setActiveOperationModal(null)} className="text-slate-400 hover:text-slate-700 font-bold text-sm">✕</button>
            </div>

            <div className="bg-blue-50/70 border border-blue-200 p-3 rounded space-y-1.5 text-slate-800">
              <div><b>SELECTED INCIDENT:</b> <span className="font-bold text-accent">{selectedIncident?.title || 'none selected'}</span></div>
              <div><b>STATUS:</b> <span className="font-bold text-purple-700 bg-purple-100 px-2 py-0.5 rounded border border-purple-200">OPERATING</span></div>
              <div><b>ASSIGNED TEAM:</b> {activeOperationModal.name} ({activeOperationModal.unit_type})</div>
            </div>

            <div className="space-y-1.5">
              <div className="font-bold uppercase text-[10px] text-slate-500">CURRENT OPERATIONAL TASK</div>
              <p className="bg-slate-50 p-2.5 rounded border border-slate-200 text-slate-700 font-medium">
                Status OPERATING recorded by the backend. Task details are not tracked in this prototype.
              </p>
            </div>

            <div className="pt-2 flex justify-end gap-2 border-t border-slate-200">
              <button
                onClick={() => {
                  handleUpdateUnitState(activeOperationModal.field_unit_id, 'COMPLETED');
                  setActiveOperationModal(null);
                }}
                className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold px-4 py-2 rounded text-xs shadow-sm"
              >
                COMPLETE OPERATION
              </button>
              <button
                onClick={() => setActiveOperationModal(null)}
                className="bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold px-3 py-2 rounded text-xs"
              >
                Close Modal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* APP SHELL: navigation rail */}
      {/* ============================================================ */}
      <aside className="w-16 xl:w-60 bg-white border-r border-line flex flex-col justify-between shrink-0 z-30">
        <div>
          {/* Header Brand Area with Ashoka Chakra-inspired Technical Emblem & Tricolour */}
          <div className="h-16 px-3 xl:px-4 flex items-center gap-2.5 border-b border-line bg-slate-900/40 relative">
            <span className="w-9 h-9 rounded-lg bg-slate-800 text-[#FF9933] border border-[#FF9933]/30 flex items-center justify-center shadow-panel shrink-0">
              <ChakraEmblem size={22} color="#7891A5" accentColor="#FF9933" />
            </span>
            <span className="sr-only xl:not-sr-only overflow-hidden">
              <div className="flex items-center gap-1.5">
                <span className="block text-[13px] font-black tracking-tight text-slate-100 leading-none">AEGIS-COP</span>
                <span className="px-1.5 py-0.5 rounded text-[8px] font-extrabold bg-[#FF9933]/20 text-[#FF9933] border border-[#FF9933]/40 leading-none tracking-widest">
                  INDIA
                </span>
              </div>
              <span className="block text-[9px] uppercase tracking-wider text-[#7891A5] font-semibold mt-1 leading-tight truncate">
                Coastal Surveillance &amp; Intel
              </span>
            </span>
          </div>

          <nav className="p-2 xl:p-2.5 space-y-1 text-[13px]" aria-label="Command panels">
            <div className="sr-only xl:not-sr-only px-2 pt-1.5 pb-1 panel-title flex items-center justify-between text-[10px]">
              <span>Command Panels</span>
              <span className="text-[#138808] font-bold">LIVE</span>
            </div>
            {[
              { id: 'video', label: 'Naval Video Detection', icon: 'video' },
              { id: 'maritime', label: 'Maritime Intelligence', icon: 'compass' },
              { id: 'naval', label: 'Naval Awareness', icon: 'navigation' },
              { id: 'overview', label: 'Tactical Route Command', icon: 'route' },
              { id: 'incidents', label: 'Incident Review', icon: 'alert',
                badge: activeIncidents.length > 0 ? <span className="chip-bad">{activeIncidents.length}</span> : null },
              { id: 'system', label: 'System Status', icon: 'shield' },
            ].map((item) => {
              const active = activeTab === item.id;
              return (
                <button key={item.id} onClick={() => setActiveTab(item.id)} title={item.label}
                  aria-current={active ? 'page' : undefined}
                  className={`relative w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition-all justify-center xl:justify-start ${
                    active
                      ? 'bg-slate-800/80 text-[#FF9933] font-bold shadow-sm'
                      : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                  }`}>
                  {active && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-[#FF9933]" aria-hidden="true" />
                  )}
                  <Icon name={item.icon} size={17} className={active ? 'text-[#FF9933]' : 'text-[#7891A5]'} />
                  <span className="sr-only xl:not-sr-only xl:flex-1 text-left text-xs">{item.label}</span>
                  {item.badge && <span className="hidden xl:inline-flex">{item.badge}</span>}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Footer with India Maritime Watch Identity */}
        <div className="p-2 xl:p-3 border-t border-line text-[11px] text-slate-500 space-y-1.5 bg-slate-900/30">
          <div className="hidden xl:flex items-center gap-1.5 font-bold text-slate-300 uppercase text-[9px] tracking-wider">
            <span className="w-2 h-2 rounded-full bg-[#138808] animate-pulse"></span>
            <span>INDIA / MARITIME WATCH</span>
          </div>
          <div className="flex items-center gap-1.5 justify-center xl:justify-start" title="Backend connection (COP refresh every 10 s)">
            <span className={`dot ${copError ? 'bg-red-500' : copData ? 'bg-[#138808]' : 'bg-slate-400'}`} />
            <span className="sr-only xl:not-sr-only text-[#7891A5] text-[10px] font-mono">
              {copError ? 'BACKEND UNREACHABLE' : copData ? 'IFC-IOR SECURE LINK' : 'CONNECTING…'}
            </span>
          </div>
          <div className="hidden xl:block font-mono text-[9px] text-slate-500">LAST SYNC {lastUpdatedTime}</div>
        </div>
      </aside>

      {/* ============================================================ */}
      {/* MAIN CONTENT AREA                                            */}
      {/* ============================================================ */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden relative">

        {/* Tactical Header with Slim Saffron-White-Green Tricolour Accent Line */}
        <header className="relative min-h-16 bg-white border-b border-line px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-2 z-20 shrink-0">
          {/* Saffron-White-Green Tricolour Accent Line */}
          <div className="tricolour-bar absolute top-0 left-0 right-0 z-30" />

          <div className="min-w-0 mr-auto pt-1">
            <h2 className="text-[14px] sm:text-[15px] font-bold tracking-tight text-slate-100 leading-tight flex items-center gap-2 flex-wrap">
              <span className="text-[#FF9933] font-black tracking-wide">AEGIS-COP</span>
              <span className="font-normal text-slate-600">/</span>
              <span className="font-bold text-slate-200 uppercase tracking-wider text-xs">
                Coastal Surveillance &amp; Maritime Intelligence
              </span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold bg-[#FF9933]/15 text-[#FF9933] border border-[#FF9933]/40 tracking-widest">
                INDIA
              </span>
            </h2>
            <p className="text-[10px] sm:text-[11px] text-[#7891A5] flex items-center gap-2 mt-0.5 flex-wrap">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#138808] animate-pulse" />
              <span>Western Seaboard Watch · Tactical Common Operating Picture</span>
              <span className="hidden md:inline text-slate-600">·</span>
              <span className="hidden md:inline text-slate-400 font-mono text-[10px]">
                Independent Maritime Security Prototype (Not Official Naval Insignia)
              </span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900/60 border border-slate-700/60 text-[10px] text-[#7891A5]">
              <ChakraEmblem size={13} color="#7891A5" accentColor="#138808" />
              <span className="font-mono text-slate-300">ARABIAN SEA SECTOR</span>
            </div>

            <span className={copError ? 'chip-bad' : copData ? 'chip-ok' : 'chip-muted'} title="Based on the last COP refresh (every 10 s)">
              <span className={`dot ${copError ? 'bg-red-500' : copData ? 'bg-emerald-500' : 'bg-slate-400'}`} />
              {copError ? 'BACKEND UNREACHABLE' : copData ? 'BACKEND CONNECTED' : 'CONNECTING'}
            </span>

            <ThemeSelector />
          </div>
        </header>

        {/* ============================================================ */}
        {/* TAB: TACTICAL ROUTE COMMAND & COMMON OPERATING PICTURE       */}
        {/* ============================================================ */}
        {activeTab === 'overview' && (
          <div className="flex-1 min-h-0 overflow-y-auto xl:overflow-hidden bg-canvas p-3 flex flex-col gap-3">

            {/* Operational summary */}
            <section className="panel px-3 py-2 flex flex-wrap items-center gap-x-6 gap-y-2 shrink-0" aria-label="Operational summary">
              {copError && copData && (
                <span className="chip-bad" title={`Last refresh failed: ${copError}`}>STALE SNAPSHOT · {new Date(copData.generated_at).toLocaleTimeString()}</span>
              )}
              <dl className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
                {[
                  ['Active threats', copData?.summary?.active_threat_count, 'bad'],
                  ['Monitored routes', copData?.summary?.monitored_route_count, null],
                  ['Compromised routes', copData?.summary?.invalidated_route_count, 'bad'],
                  ['Awaiting operator', missionState?.detail ? (missionState.detail.recommendations || []).filter(r => r.status === 'PENDING').length : undefined, 'warn'],
                  ['Active evidence', copData?.summary?.active_evidence_count, null],
                ].map(([label, value, tone]) => (
                  <div key={label} className="flex items-baseline gap-1.5" title={label === 'Awaiting operator' ? 'Pending recommendations on the active mission' : 'From the COP summary'}>
                    <dd className={`text-lg font-semibold font-mono leading-none ${
                      typeof value !== 'number' ? 'text-slate-400' : value > 0 && tone === 'bad' ? 'text-red-700' : value > 0 && tone === 'warn' ? 'text-amber-700' : 'text-slate-900'
                    }`}>{typeof value === 'number' ? value : '–'}</dd>
                    <dt className="text-[11px] text-slate-500">{label}</dt>
                  </div>
                ))}
              </dl>
              <div className="xl:ml-auto min-w-0">
                <DataSourceStrip copData={copData} copError={copError} systemStatus={systemStatus} />
              </div>
            </section>

            <DecisionChain mission={missionState} copData={copData} />

            {/* Map + panels layout */}
            <div className="grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-[17rem_minmax(0,1fr)_24rem] xl:[grid-template-rows:minmax(0,1fr)] xl:flex-1 xl:min-h-0">

              <div className="panel overflow-hidden relative md:col-span-2 xl:col-span-1 xl:col-start-2 xl:row-start-1 h-[58vh] min-h-[420px] xl:h-auto xl:min-h-0">
                <MapComponent
                  showIncidents={layers.incidents}
                  showRisk={layers.risk}
                  showResources={layers.resources}
                  showFieldUnits={layers.fieldUnits}
                  showSatellite={layers.satellite}
                  incidents={incidents}
                  resources={resources}
                  fieldUnits={fieldUnits}
                  copData={copData}
                  copError={copError}
                  copEnabled={true}
                  replacementRoute={proposedRoute}
                />
              </div>

              {/* Threat queue and evidence */}
              <div className="xl:col-start-1 xl:row-start-1 flex flex-col gap-3 min-h-0 h-[560px] xl:h-auto">
                {copLoading ? (
                  <div className="panel p-4 text-xs text-slate-500">Loading COP…</div>
                ) : copError && !copData ? (
                  <div className="panel p-3 text-xs text-red-800 bg-red-50 border-red-200">
                    <div className="font-semibold mb-0.5">COP unavailable</div>
                    The backend could not be reached ({copError}). Nothing is shown until it responds.
                  </div>
                ) : (
                  <>
                    {copError && (
                      <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] font-semibold text-red-800">
                        STALE — last refresh failed ({copError}). Showing snapshot from {new Date(copData.generated_at).toLocaleTimeString()}.
                      </div>
                    )}
                    <div className="flex-1 min-h-0">
                      <ThreatPanel
                        threats={copData?.threats || []}
                        onSelectThreat={(t) => handleSelectIncident({
                          incident_id: t.id,
                          title: t.title,
                          severity: t.severity,
                          status: t.status,
                          latitude: t.latitude,
                          longitude: t.longitude,
                          hazard_type: t.category,
                          description: t.description
                        })}
                        selectedThreatId={selectedIncident?.incident_id}
                      />
                    </div>
                    <SelectedThreatEvidence copData={copData} threatId={selectedIncident?.incident_id}
                      timeline={selectedIncidentDetail?.incident_id === selectedIncident?.incident_id ? selectedIncidentDetail?.timeline : null} />
                  </>
                )}
              </div>

              {/* Active mission and field units */}
              <div className="xl:col-start-3 xl:row-start-1 min-h-0 h-[560px] xl:h-auto overflow-y-auto flex flex-col gap-3">
                <MissionPanel
                  copData={copData}
                  refreshCop={refreshCop}
                  showToast={showToast}
                  onProposedRoute={setProposedRoute}
                  onMissionChange={setMissionRoute}
                  onStateChange={setMissionState}
                />

                <details className="panel group shrink-0">
                  <summary className="cursor-pointer list-none px-3 py-2.5 flex items-center justify-between gap-2">
                    <span className="panel-title flex items-center gap-1.5">
                      <Icon name="users" size={14} /> Field units
                    </span>
                    <span className="flex items-center gap-2 text-[11px] text-slate-500">
                      {fieldUnits.filter(u => ['EN_ROUTE', 'AT_SCENE', 'OPERATING'].includes(fieldUnitStates[u.field_unit_id] || u.status)).length} en route / on scene
                      <Icon name="chevronDown" size={14} className="transition-transform group-open:rotate-180" />
                    </span>
                  </summary>
                  <div className="px-3 pb-3 space-y-1.5 text-xs">
                    <p className="text-[10px] text-slate-500">Positions are manual or seeded updates — there is no live GPS feed.</p>
                    {fieldUnits.length === 0 ? (
                      <div className="text-slate-500 text-[11px]">No field units registered.</div>
                    ) : fieldUnits.map(fu => {
                      const st = fieldUnitStates[fu.field_unit_id] || fu.status || 'UNKNOWN';
                      return (
                        <div key={fu.field_unit_id} className="flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5">
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-900 truncate">{fu.name}</div>
                            <div className="text-[10px] text-slate-500 truncate">
                              {fu.unit_type} · {fu.city || fu.district || 'location unknown'} · incident: {incidents.find(i => i.incident_id === fu.incident_id)?.title || 'none'}
                            </div>
                          </div>
                          <span className={st === 'EN_ROUTE' ? 'chip-info' : st === 'AT_SCENE' || st === 'OPERATING' ? 'chip-warn' : st === 'COMPLETED' ? 'chip-ok' : 'chip-muted'}>{st}</span>
                        </div>
                      );
                    })}
                  </div>
                </details>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB: VIDEO INTELLIGENCE                                      */}
        {/* ============================================================ */}
        {activeTab === 'video' && <VideoIntelligence />}

        {/* ============================================================ */}
        {/* TAB: MARITIME INTELLIGENCE                                   */}
        {/* ============================================================ */}
        {activeTab === 'maritime' && <MaritimeIntelligence />}

        {/* ============================================================ */}
        {/* TAB: NAVAL / MARITIME AWARENESS                              */}
        {/* ============================================================ */}
        {activeTab === 'naval' && <NavalAwareness onSelectTab={setActiveTab} />}

        {/* ============================================================ */}
        {/* TAB: INCIDENT REVIEW                                         */}
        {/* ============================================================ */}
        {activeTab === 'incidents' && (
          <div className="flex-1 p-4 overflow-hidden bg-canvas">
            <IncidentCenter
              onClose={() => setActiveTab('overview')}
              sharedSelectedIncident={selectedIncident}
              onSelectIncident={inc => {
                setSelectedIncident(inc);
                fetchIncidentDetail(inc.incident_id);
              }}
            />
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB: SYSTEM STATUS                                           */}
        {/* ============================================================ */}
        {activeTab === 'system' && <SystemStatus />}

      </div>

    </div>
  );
}

// Evidence linked to the threat selected in the left panel
function SelectedThreatEvidence({ copData, threatId, timeline }) {
  const threat = (copData?.threats || []).find((t) => t.id === threatId);
  if (!threat) {
    return (
      <div className="panel px-3 py-2.5 text-[11px] text-slate-500 shrink-0">
        Select a threat to inspect its linked evidence and record timeline.
      </div>
    );
  }
  const evidence = (copData?.evidence || []).filter((e) => e.threat_id === threat.id);
  return (
    <div className="panel px-3 py-2.5 text-[11px] space-y-2 shrink-0 max-h-[45%] overflow-y-auto">
      <div>
        <div className="panel-title flex items-center gap-1.5"><Icon name="link" size={13} /> Linked evidence</div>
        <div className="mt-0.5 text-slate-600">
          <span className="font-mono text-slate-800">{threat.id}</span> · {threat.status} · source {threat.source || 'unknown'}
          {threat.is_demo && <span className="text-amber-700 font-semibold"> · DEMO/SIMULATED</span>}
        </div>
      </div>
      {evidence.length === 0 ? (
        <div className="text-slate-500">No evidence records are linked to this threat.</div>
      ) : evidence.map((e) => (
        <div key={e.id} className="rounded-md border border-slate-200 bg-slate-50 p-2 space-y-0.5">
          <div className="flex justify-between gap-1">
            <b className="font-mono text-slate-900 truncate">{e.id}</b>
            {e.is_simulation && <span className="chip-warn">SIMULATED</span>}
          </div>
          <div className="text-slate-700">{e.source_type} {e.source_id || ''} · {e.observation_type}</div>
          {e.description && <div className="text-slate-600">{e.description}</div>}
          <div className="text-slate-500">Source-declared confidence {Math.round(e.confidence * 100)}% · {new Date(e.timestamp).toLocaleTimeString()}</div>
        </div>
      ))}
      {timeline?.length > 0 && (
        <div>
          <div className="panel-title flex items-center gap-1.5 mb-1"><Icon name="clock" size={13} /> Threat record timeline</div>
          <ol className="space-y-1 border-l border-slate-200 pl-2.5">
            {timeline.map((evt, idx) => (
              <li key={idx} className="text-slate-700">
                <span className="font-mono text-[10px] text-slate-500">{new Date(evt.timestamp).toLocaleTimeString()}</span>{' '}
                <span className="font-semibold text-accent">{evt.event_type}</span>{evt.description ? ` — ${evt.description}` : ''}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
