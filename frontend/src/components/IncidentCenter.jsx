import { useState, useEffect } from 'react';
import Icon from './ui/Icon';
import { API_BASE_URL } from '../config';

export default function IncidentCenter({ onClose, sharedSelectedIncident, onSelectIncident }) {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(sharedSelectedIncident || null);
  const [activePlan, setActivePlan] = useState(null);
  const [linkedEvidence, setLinkedEvidence] = useState(null);
  const [dispatching, setDispatching] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanStep, setScanStep] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);

  useEffect(() => {
    fetchIncidents();
  }, []);

  useEffect(() => {
    if (sharedSelectedIncident) {
      setSelectedIncident(sharedSelectedIncident);
    }
  }, [sharedSelectedIncident]);

  useEffect(() => {
    if (selectedIncident?.incident_id) {
      fetchResponsePlan(selectedIncident.incident_id);
      fetchLinkedEvidence(selectedIncident.incident_id);
    } else {
      setActivePlan(null);
      setLinkedEvidence(null);
    }
  }, [selectedIncident]);

  async function fetchIncidents() {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE_URL}/national/incidents`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to fetch incidents');
      setIncidents(data.records || []);
      if (data.records && data.records.length > 0 && !selectedIncident) {
        const first = data.records[0];
        setSelectedIncident(first);
        if (onSelectIncident) onSelectIncident(first);
      }
    } catch (err) {
      showToast("Error: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function fetchLinkedEvidence(incId) {
    try {
      const res = await fetch(`${API_BASE_URL}/evidence?threat_id=${encodeURIComponent(incId)}`);
      setLinkedEvidence(res.ok ? await res.json() : null);
    } catch {
      setLinkedEvidence(null);
    }
  }

  async function fetchResponsePlan(incId) {
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
    } catch (err) {
      console.error(err);
      setActivePlan(null);
    }
  }

  function showToast(msg, type = "info") {
    setToastMessage({ text: msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  }

  async function handleScanForIncidents() {
    try {
      setScanStep('SCANNING...');
      const res = await fetch(`${API_BASE_URL}/national/incidents/recommend`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      setScanStep('SCAN COMPLETE');
      await fetchIncidents();

      const created = (data.new_incidents || []).length;
      showToast(data.source === 'BUILT_IN_DEMO_REGIONS'
        ? `No regional risk feed is configured: ${created} DEMO incident(s) created from the built-in region list (fixtures, not detections).`
        : `Regional risk feed scanned: ${created} new incident(s).`, "success");
      setTimeout(() => setScanStep(null), 2000);
    } catch (err) {
      showToast("Error scanning incidents: " + err.message, "error");
      setScanStep(null);
    }
  }

  async function handleGeneratePlan() {
    if (!selectedIncident?.incident_id || planLoading) return;
    try {
      setPlanLoading(true);
      const res = await fetch(`${API_BASE_URL}/national/incidents/${selectedIncident.incident_id}/response-plan`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.plan) {
        setActivePlan(data.plan);
        showToast(`✓ Response plan generated for ${selectedIncident.title} (PENDING_APPROVAL)`, "success");
      } else {
        throw new Error(data.detail || "Failed to generate plan");
      }
    } catch (err) {
      showToast("Generate plan error: " + err.message, "error");
    } finally {
      setPlanLoading(false);
    }
  }

  async function handleApprovePlan() {
    if (!activePlan || planLoading) return;
    const pId = activePlan.response_plan_id || activePlan.plan_id;
    if (!pId) return;
    try {
      setPlanLoading(true);
      const res = await fetch(`${API_BASE_URL}/national/response-plans/${pId}/approve`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.plan) {
        setActivePlan(data.plan);
        showToast(`✓ Response plan approved for ${selectedIncident.title}`, "success");
        fetchIncidents();
      } else {
        throw new Error(data.detail || "Approval failed");
      }
    } catch (err) {
      showToast("Approve plan error: " + err.message, "error");
    } finally {
      setPlanLoading(false);
    }
  }

  async function handleSimulatedDispatch(action) {
    if (dispatching) return;
    try {
      setDispatching(action.action_id);
      const res = await fetch(`${API_BASE_URL}/national/response-actions/${action.action_id}/dispatch`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      showToast(data.message || 'SIMULATED dispatch recorded.', "success");
      await fetchResponsePlan(selectedIncident.incident_id);
    } catch (err) {
      showToast("Simulated dispatch rejected: " + err.message, "error");
    } finally {
      setDispatching(null);
    }
  }

  async function handleAction(id, actionPath) {
    try {
      const res = await fetch(`${API_BASE_URL}/national/incidents/${id}/${actionPath}`, { method: 'POST' });
      if (!res.ok) throw new Error(`Failed to ${actionPath}`);
      showToast(`Incident status updated to ${actionPath.toUpperCase()}`, "success");
      fetchIncidents();
      
      const detailRes = await fetch(`${API_BASE_URL}/national/incidents/${id}`);
      const d = await detailRes.json();
      if (detailRes.ok) {
        setSelectedIncident(d.record);
        if (onSelectIncident) onSelectIncident(d.record);
      }
    } catch (err) {
      showToast("Error: " + err.message, "error");
    }
  }

  function selectInc(inc) {
    setSelectedIncident(inc);
    if (onSelectIncident) onSelectIncident(inc);
  }

  return (
    <div className="h-full flex flex-col bg-canvas text-slate-900 p-4 space-y-4 overflow-hidden">
      
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className={`px-4 py-2.5 text-xs font-bold rounded shadow flex justify-between items-center z-50 shrink-0 ${
          toastMessage.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
        }`}>
          <span>ℹ {toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="font-bold">&times;</button>
        </div>
      )}

      {/* Header */}
      <div className="panel px-4 py-3 flex flex-wrap gap-3 justify-between items-center shrink-0">
        <div>
          <h1 className="text-[15px] font-semibold tracking-tight text-slate-900 flex items-center gap-2"><Icon name="alert" size={18} className="text-red-600" /> Incidents</h1>
          <div className="text-[11px] text-slate-500 mt-0.5">Incident queue, linked evidence, response plans and status actions (dispatch is simulated)</div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleScanForIncidents}
            disabled={!!scanStep}
            className="px-4 py-2 bg-accent hover:bg-accent-strong text-white rounded text-xs font-bold shadow-sm transition disabled:opacity-50"
          >
            {scanStep || 'SCAN FOR INCIDENTS'}
          </button>
          {onClose && (
            <button onClick={onClose} className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-bold border border-slate-300">
              Back to EOC
            </button>
          )}
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="flex gap-4 flex-1 overflow-hidden">
        
        {/* Left Queue */}
        <div className="w-1/3 flex flex-col bg-white p-4 rounded-md border border-line shadow-sm">
          <div className="flex justify-between items-center border-b border-line pb-2 mb-3">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-800">
              INCIDENT QUEUE ({incidents.length})
            </h2>
            <span className="text-[10px] text-slate-500 font-mono">ACTIVE TRIAGE</span>
          </div>

          {loading ? (
            <p className="text-xs text-slate-500 italic">Scanning records...</p>
          ) : incidents.length === 0 ? (
            <div className="text-xs text-slate-500 italic p-6 text-center border border-dashed border-slate-300 rounded">
              No active incidents detected.
              <br/>
              <span className="text-[10px] text-accent font-bold mt-1 block">Click 'SCAN FOR INCIDENTS' to assess feeds.</span>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {incidents.map(inc => {
                const isSel = selectedIncident?.incident_id === inc.incident_id;
                return (
                  <div
                    key={inc.incident_id}
                    onClick={() => selectInc(inc)}
                    className={`border rounded p-3 cursor-pointer transition ${
                      isSel ? 'border-accent bg-blue-50/80 ring-1 ring-accent' : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className={`text-[10px] px-2 py-0.5 rounded font-black uppercase text-white ${
                        inc.severity === 'CRITICAL' ? 'bg-red-700' : 'bg-amber-600'
                      }`}>
                        {inc.severity}
                      </span>
                      <span className="text-[10px] font-bold text-accent uppercase tracking-wider bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                        {inc.status}
                      </span>
                    </div>
                    <p className="font-bold text-sm text-slate-900">{inc.title}</p>
                    <p className="text-xs text-slate-600"><Icon name="pin" size={11} className="inline-block align-[-1px] mr-0.5" />{inc.district}, {inc.state}</p>
                    <div className="mt-2 text-[10px] text-slate-500 flex justify-between border-t border-slate-200 pt-1">
                      <span>Severity score: <strong className="text-red-700">{inc.risk_score}/100</strong></span>
                      <span>{inc.source}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Details & Evidence Panel */}
        <div className="w-2/3 flex flex-col bg-white p-4 rounded-md border border-line shadow-sm overflow-y-auto">
          {!selectedIncident ? (
            <div className="text-slate-500 text-xs italic p-6 text-center border border-dashed border-slate-300 rounded">
              Select an incident from the queue to inspect details, evidence, and response actions.
            </div>
          ) : (
            <div className="space-y-4 text-xs">
              
              {/* Header */}
              <div className="border-b border-line pb-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-black uppercase text-white ${
                      selectedIncident.severity === 'CRITICAL' ? 'bg-red-700' : 'bg-amber-600'
                    }`}>
                      {selectedIncident.severity}
                    </span>
                    <h2 className="text-xl font-extrabold text-slate-900 mt-1">{selectedIncident.title}</h2>
                    <p className="text-slate-600 font-medium"><Icon name="pin" size={11} className="inline-block align-[-1px] mr-0.5" />Location: {selectedIncident.district}, {selectedIncident.state}</p>
                  </div>
                  <span className="text-xs font-bold text-accent bg-blue-50 px-2.5 py-1 rounded border border-blue-200">
                    STATUS: {selectedIncident.status}
                  </span>
                </div>
              </div>

              {/* Evidence & Risk Breakdown */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 p-3 rounded border border-slate-200 space-y-1">
                  <p className="font-extrabold text-[10px] text-accent uppercase tracking-wider mb-1">EVIDENCE & INTELLIGENCE</p>
                  <p><b>Official Warning:</b> <span className="text-slate-800">{['NONE', 'NORMAL', null, undefined, ''].includes(selectedIncident.official_warning) ? 'None linked' : selectedIncident.official_warning}</span></p>
                  <p><b>Severity score:</b> <span className="text-red-700 font-mono font-bold">{selectedIncident.risk_score}/100</span> <span className="text-slate-500 text-[10px]">(fixed per severity level, not a calibrated risk)</span></p>
                  <p><b>Confidence:</b> <span className="text-slate-800">{selectedIncident.confidence}</span></p>
                  <p><b>Data Source:</b> <span className="text-slate-800">{selectedIncident.source}</span></p>
                </div>
                <div className="bg-slate-50 p-3 rounded border border-slate-200 space-y-1">
                  <p className="font-extrabold text-[10px] text-accent uppercase tracking-wider mb-1">SITUATION DESCRIPTION</p>
                  <p className="text-slate-700">{selectedIncident.description}</p>
                  {selectedIncident.title.includes("DEMO") && (
                    <p className="mt-2 text-amber-900 font-bold text-[10px] bg-amber-50 p-1 rounded border border-amber-200">
                      CONTROLLED TACTICAL EXERCISE INCIDENT
                    </p>
                  )}
                </div>
              </div>

              {/* Linked evidence records (backend) */}
              <div className="bg-slate-50 p-3 rounded border border-slate-200 space-y-2">
                <div className="flex justify-between items-center border-b border-slate-200 pb-1.5">
                  <p className="font-extrabold text-[10px] text-slate-700 uppercase tracking-wider">LINKED EVIDENCE RECORDS</p>
                  <span className="text-[9px] text-slate-500 font-mono">GET /api/evidence?threat_id=</span>
                </div>
                {linkedEvidence === null ? (
                  <p className="text-[11px] text-slate-500 italic">Evidence records unavailable.</p>
                ) : linkedEvidence.length === 0 ? (
                  <p className="text-[11px] text-slate-500 italic">No evidence records are linked to this incident. Its source is {selectedIncident.source || 'unknown'}.</p>
                ) : linkedEvidence.map(ev => (
                  <div key={ev.evidence_id} className="bg-white p-2 rounded border border-slate-200 text-[11px] space-y-0.5">
                    <div className="flex justify-between">
                      <b>{ev.evidence_id}</b>
                      {ev.provenance?.is_simulation
                        ? <span className="text-[9px] font-bold text-amber-800 bg-amber-50 border border-amber-200 px-1 rounded">SIMULATED</span>
                        : <span className="text-[9px] font-bold text-slate-600 border border-slate-200 px-1 rounded">{ev.status}</span>}
                    </div>
                    <div>{ev.source_type} · {ev.source_id} · {ev.observation_type}</div>
                    <div className="text-slate-600">{ev.description}</div>
                    <div className="text-slate-500 font-mono text-[10px]">
                      {ev.timestamp} · ({ev.latitude?.toFixed(4)}, {ev.longitude?.toFixed(4)}) · source-declared confidence {ev.confidence ?? 'n/a'}
                    </div>
                  </div>
                ))}
              </div>

              {/* Incident Response Plan & Resource Assignment Section */}
              <div className="bg-slate-50 p-3 rounded border border-slate-200 space-y-3">
                <div className="flex justify-between items-center border-b border-slate-200 pb-1.5">
                  <p className="font-extrabold text-[10px] text-accent uppercase tracking-wider">RESPONSE PLAN & RESOURCE COMMAND</p>
                  <span className="text-[10px] font-bold text-slate-600">PLAN INCIDENT ID: {selectedIncident.incident_id}</span>
                </div>

                <div className="bg-white p-3 rounded border border-slate-200 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-slate-900 text-xs">SPECIFIC OPERATIONAL PLAN:</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                      activePlan?.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                      activePlan?.status === 'PENDING_APPROVAL' ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-slate-100 text-slate-700'
                    }`}>
                      STATUS: {activePlan?.status || 'NO PLAN GENERATED'}
                    </span>
                  </div>

                  {/* Hazard Specific Recommended Steps */}
                  <div className="text-[11px] text-slate-700 space-y-1.5">
                    {activePlan?.situation_summary && (
                      <p className="font-bold text-slate-800 bg-blue-50/50 p-2 rounded border border-blue-100">
                        {activePlan.situation_summary}
                      </p>
                    )}
                    
                    <p className="font-bold text-slate-900 mt-1">RECOMMENDED ACTIONS:</p>
                    <ul className="list-disc pl-4 text-slate-700 text-[11px] space-y-1">
                      {activePlan?.recommended_steps && activePlan.recommended_steps.length > 0 ? (
                        activePlan.recommended_steps.map((step, idx) => (
                          <li key={idx}>{step}</li>
                        ))
                      ) : (
                        <li className="italic text-slate-500">{activePlan ? 'This plan lists resource actions only (below).' : 'No plan generated yet.'}</li>
                      )}
                    </ul>
                  </div>

                  <div className="pt-2 border-t border-slate-200 flex gap-2">
                    {!activePlan && ['RESOLVED', 'CLOSED'].includes(selectedIncident.status) ? (
                      <div className="text-[10px] text-slate-500 italic">Incident is {selectedIncident.status}; no new plan can be generated.</div>
                    ) : !activePlan ? (
                      <button
                        onClick={handleGeneratePlan}
                        disabled={planLoading}
                        className="bg-accent hover:bg-accent-strong text-white font-bold py-1.5 px-4 rounded text-xs shadow-sm disabled:opacity-50"
                      >
                        {planLoading ? 'GENERATING...' : 'GENERATE RESPONSE PLAN'}
                      </button>
                    ) : activePlan.status === 'PENDING_APPROVAL' ? (
                      <button
                        onClick={handleApprovePlan}
                        disabled={planLoading}
                        className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold py-1.5 px-4 rounded text-xs shadow-sm disabled:opacity-50"
                      >
                        {planLoading ? 'APPROVING...' : 'APPROVE RESPONSE PLAN'}
                      </button>
                    ) : (
                      <div className="text-xs font-extrabold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded border border-emerald-200 flex items-center gap-1.5">
                        <span>✓ RESPONSE PLAN APPROVED</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Plan resource actions (backend). Dispatch is SIMULATED. */}
                <div className="bg-white p-3 rounded border border-slate-200 space-y-2">
                  <div className="font-bold text-slate-900 text-xs flex justify-between">
                    <span>PLAN RESOURCE ACTIONS</span>
                    <span className="text-[9px] font-bold text-amber-800 bg-amber-50 border border-amber-200 px-1 rounded">DISPATCH IS SIMULATED</span>
                  </div>
                  {!activePlan?.actions?.length ? (
                    <div className="text-[10px] text-slate-500 italic bg-slate-50 p-2 rounded">
                      {activePlan ? 'The plan matched no available resources.' : 'Generate a response plan to see matched resources.'}
                    </div>
                  ) : activePlan.actions.map(a => (
                    <div key={a.action_id} className="text-[11px] text-slate-700 border border-slate-200 rounded p-2 space-y-1">
                      <div className="flex justify-between">
                        <span><b>{a.resource_type}</b> ×{a.quantity} ({a.resource_id})</span>
                        <span className="font-bold text-[10px]">{a.status}</span>
                      </div>
                      <div className="text-slate-500">{a.recommendation_reason} · match score {a.match_score}</div>
                      {a.status === 'APPROVED' && (
                        <button
                          onClick={() => handleSimulatedDispatch(a)}
                          disabled={!!dispatching}
                          className="w-full bg-accent hover:bg-accent-strong text-white font-bold py-1 rounded text-[11px] disabled:opacity-50"
                        >
                          {dispatching === a.action_id ? 'RECORDING...' : 'RECORD SIMULATED DISPATCH'}
                        </button>
                      )}
                    </div>
                  ))}
                  {activePlan && activePlan.status !== 'APPROVED' && activePlan.actions?.length > 0 && (
                    <div className="text-[10px] text-slate-500 italic">Approve the plan before recording a dispatch.</div>
                  )}
                </div>
              </div>

              {/* Operator Command Actions */}
              <div className="bg-slate-50 p-3 rounded border border-slate-200 space-y-2">
                <p className="font-extrabold text-[10px] text-slate-700 uppercase tracking-wider mb-2">OPERATOR STATUS ACTIONS</p>
                <div className="flex gap-2">
                  {selectedIncident.status === 'DETECTED' && (
                    <button onClick={() => handleAction(selectedIncident.incident_id, 'acknowledge')} className="bg-accent hover:bg-accent-strong text-white font-bold py-1.5 px-3 rounded text-xs">
                      ACKNOWLEDGE
                    </button>
                  )}
                  {selectedIncident.status !== 'RESOLVED' && (
                    <button onClick={() => handleAction(selectedIncident.incident_id, 'escalate')} className="bg-amber-700 hover:bg-amber-800 text-white font-bold py-1.5 px-3 rounded text-xs">
                      ESCALATE
                    </button>
                  )}
                  {selectedIncident.status !== 'RESOLVED' ? (
                    <button onClick={() => handleAction(selectedIncident.incident_id, 'resolve')} className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold py-1.5 px-3 rounded text-xs">
                      MARK RESOLVED
                    </button>
                  ) : <span className="text-[11px] text-slate-500 italic">Incident resolved.</span>}
                </div>
              </div>

            </div>
          )}
        </div>

      </div>

    </div>
  );
}
