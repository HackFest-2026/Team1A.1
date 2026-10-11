import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export default function ResourceCenter({ onClose, sharedSelectedIncident, incidents = [] }) {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedIncId, setSelectedIncId] = useState(sharedSelectedIncident?.incident_id || (incidents[0]?.incident_id) || '');
  const [activePlan, setActivePlan] = useState(null);
  const [actionStatus, setActionStatus] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);
  const [typeFilter, setTypeFilter] = useState('ALL'); // 'ALL' | 'RESCUE' | 'AMBULANCE' | 'BOAT' | 'SUPPLIES'

  useEffect(() => {
    fetchResources();
  }, []);

  useEffect(() => {
    if (sharedSelectedIncident?.incident_id) {
      setSelectedIncId(sharedSelectedIncident.incident_id);
    }
  }, [sharedSelectedIncident]);

  useEffect(() => {
    if (selectedIncId) {
      fetchPlanForIncident(selectedIncId);
    }
  }, [selectedIncId]);

  function showToast(msg, type = "info") {
    setToastMessage({ text: msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  }

  async function fetchResources() {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE_URL}/national/resources`);
      const data = await res.json();
      if (res.ok) setResources(data.records || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function fetchPlanForIncident(incId) {
    try {
      const res = await fetch(`${API_BASE_URL}/national/incidents/${incId}/response-plan`);
      const data = await res.json();
      if (res.ok && data.records && data.records.length > 0) {
        setActivePlan(data.records[0]);
      } else {
        setActivePlan(null);
      }
    } catch (e) {
      setActivePlan(null);
    }
  }

  async function handleGeneratePlan() {
    if (!selectedIncId) {
      showToast("Select an incident first", "error");
      return;
    }
    setActionStatus({ type: 'loading', message: 'GENERATING RESPONSE PLAN...' });
    try {
      const res = await fetch(`${API_BASE_URL}/national/incidents/${selectedIncId}/response-plan`, { method: 'POST' });
      if (res.ok) {
        showToast("Response plan generated successfully!", "success");
        setActionStatus({ type: 'success', message: '✓ RESPONSE PLAN GENERATED' });
        fetchPlanForIncident(selectedIncId);
        fetchResources();
      } else {
        showToast("Failed to generate response plan", "error");
        setActionStatus({ type: 'error', message: 'FAILED TO GENERATE PLAN' });
      }
    } catch (e) {
      showToast("Error: " + e.message, "error");
      setActionStatus({ type: 'error', message: e.message });
    }
  }

  async function handleApprovePlan() {
    if (!activePlan || !activePlan.plan_id) {
      showToast("NO RESPONSE PLAN AVAILABLE: Click Generate Response Plan first", "error");
      return;
    }
    setActionStatus({ type: 'loading', message: 'APPROVING RESPONSE PLAN...' });
    try {
      const res = await fetch(`${API_BASE_URL}/national/response-plans/${activePlan.plan_id}/approve`, { method: 'POST' });
      if (res.ok) {
        showToast("Response plan approved and resources reserved!", "success");
        setActionStatus({ type: 'success', message: '✓ RESPONSE PLAN APPROVED — Resources Reserved' });
        fetchPlanForIncident(selectedIncId);
        fetchResources();
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast(`Approval failed: ${errData.detail || 'Plan not in pending state'}`, "error");
        setActionStatus({ type: 'error', message: errData.detail || 'APPROVAL FAILED' });
      }
    } catch (e) {
      showToast("Error: " + e.message, "error");
      setActionStatus({ type: 'error', message: e.message });
    }
  }

  async function handleDispatchAction() {
    if (!activePlan || !activePlan.actions || activePlan.actions.length === 0) {
      showToast("No response actions available for dispatch", "error");
      return;
    }
    const action = activePlan.actions[0];
    setActionStatus({ type: 'loading', message: 'SIMULATING DISPATCH...' });
    try {
      const res = await fetch(`${API_BASE_URL}/national/response-actions/${action.action_id}/dispatch`, { method: 'POST' });
      if (res.ok) {
        showToast("Dispatch recorded. Unit set to EN_ROUTE", "success");
        setActionStatus({ type: 'success', message: '✓ SIMULATED DISPATCH RECORDED' });
        fetchPlanForIncident(selectedIncId);
        fetchResources();
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast(`Dispatch failed: ${errData.detail || 'Plan must be APPROVED first'}`, "error");
        setActionStatus({ type: 'error', message: errData.detail || 'DISPATCH FAILED' });
      }
    } catch (e) {
      showToast("Error: " + e.message, "error");
      setActionStatus({ type: 'error', message: e.message });
    }
  }

  const filteredResources = resources.filter(r => {
    if (typeFilter === 'ALL') return true;
    if (typeFilter === 'RESCUE') return r.resource_type?.includes('RESCUE') || r.name?.includes('Rescue');
    if (typeFilter === 'AMBULANCE') return r.resource_type?.includes('AMBULANCE') || r.name?.includes('Ambulance');
    if (typeFilter === 'BOAT') return r.resource_type?.includes('BOAT') || r.name?.includes('Boat');
    if (typeFilter === 'SUPPLIES') return r.resource_type?.includes('SUPPLY') || r.name?.includes('Supply');
    return true;
  });

  const selectedIncidentObject = incidents.find(i => i.incident_id === selectedIncId) || sharedSelectedIncident;

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
      <div className="flex justify-between items-center bg-white p-4 rounded-md border border-line shadow-sm shrink-0">
        <div>
          <h1 className="text-base font-extrabold tracking-tight text-accent uppercase flex items-center gap-2">
            <span>🚒</span> RESOURCE COMMAND & RESPONSE PLANNING
          </h1>
          <div className="text-xs font-bold text-slate-500 mt-0.5">● RESOURCE DIRECTORY & DISPATCH ENGINE</div>
        </div>
        {onClose && (
          <button onClick={onClose} className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-bold border border-slate-300">
            Back to EOC
          </button>
        )}
      </div>

      {/* Resource Type Filters */}
      <div className="flex gap-2 bg-white p-2.5 rounded-md border border-line shadow-sm shrink-0 overflow-x-auto text-xs font-bold">
        {['ALL', 'RESCUE', 'AMBULANCE', 'BOAT', 'SUPPLIES'].map(filter => (
          <button
            key={filter}
            onClick={() => setTypeFilter(filter)}
            className={`px-3 py-1.5 rounded transition ${
              typeFilter === filter ? 'bg-accent text-white shadow-sm' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            {filter}
          </button>
        ))}
      </div>

      <div className="flex gap-4 flex-1 overflow-hidden">
        
        {/* Left Resource Cards List */}
        <div className="w-1/2 flex flex-col bg-white p-4 rounded-md border border-line shadow-sm overflow-y-auto">
          <div className="flex justify-between items-center border-b border-line pb-2 mb-3 shrink-0">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-800">
              RESPONSE TEAMS DIRECTORY ({filteredResources.length})
            </h2>
            <span className="text-[10px] text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
              AVAILABLE: {resources.filter(r => r.status === 'AVAILABLE').length}
            </span>
          </div>

          {loading ? (
            <p className="text-xs text-slate-500 italic">Loading resource records...</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredResources.map(r => (
                <div key={r.resource_id} className="border border-slate-200 rounded p-3 bg-slate-50 hover:bg-slate-100 transition space-y-1 text-xs">
                  <div className="flex justify-between items-start">
                    <span className="font-bold text-slate-900">{r.name}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                      r.status === 'AVAILABLE' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {r.status}
                    </span>
                  </div>
                  <div className="text-accent font-bold text-[11px]">{r.resource_type}</div>
                  <div className="text-slate-600 text-[11px]">📍 {r.district}, {r.state}</div>
                  <div className="text-[10px] text-slate-500 pt-1 border-t border-slate-200 flex justify-between">
                    <span>Capacity: {r.capacity_people || r.capacity_units || 10}</span>
                    <span>{r.station_name || 'Station Alpha'}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Main Command Area */}
        <div className="w-1/2 flex flex-col bg-white p-4 rounded-md border border-line shadow-sm overflow-y-auto space-y-4 text-xs">
          
          {/* Target Incident Selection */}
          <div className="bg-slate-50 p-3 rounded border border-slate-200 space-y-2">
            <label className="text-[10px] font-extrabold text-accent uppercase tracking-wider block">TARGET INCIDENT FOR RESPONSE</label>
            <select
              value={selectedIncId}
              onChange={e => setSelectedIncId(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-1.5 text-xs bg-white text-slate-900 font-bold focus:border-accent outline-none"
            >
              {incidents.length === 0 && <option value="" className="text-slate-900 bg-white">-- No Active Incidents --</option>}
              {incidents.map(inc => (
                <option key={inc.incident_id} value={inc.incident_id} className="text-slate-900 bg-white">
                  {inc.title} ({inc.severity}) — {inc.district}
                </option>
              ))}
            </select>
            {selectedIncidentObject && (
              <div className="text-[11px] text-slate-700 bg-white p-2 rounded border border-slate-200">
                <b>Severity:</b> <span className="text-red-700 font-bold">{selectedIncidentObject.severity}</span> | <b>Status:</b> {selectedIncidentObject.status}<br/>
                <b>Location:</b> {selectedIncidentObject.district}, {selectedIncidentObject.state}
              </div>
            )}
          </div>

          {/* AI Match Recommendation Card */}
          <div className="bg-blue-50/80 p-3.5 rounded border border-blue-200 space-y-2">
            <div className="flex justify-between items-center border-b border-blue-200 pb-1.5">
              <span className="font-extrabold text-[10px] text-accent uppercase tracking-wider">AI MATCH RECOMMENDATION</span>
              <span className="text-[9px] bg-accent text-white px-1.5 py-0.5 rounded font-bold">OPTIMAL</span>
            </div>

            <div className="text-slate-900 font-bold">
              Recommended Unit: <span className="text-accent">Rescue Team Alpha</span>
            </div>
            <div className="text-[11px] text-slate-700">
              <b>Reason:</b> Nearest available unit compatible with deployment specs (4.2 km from Dharwad sector)
            </div>
            <div className="text-[11px] text-slate-700">
              <b>Compatibility:</b> HIGH | <b>ETA:</b> 14 mins
            </div>

            {/* Workflow Action Buttons */}
            <div className="pt-2 border-t border-blue-200 space-y-1.5">
              {!activePlan ? (
                <button
                  onClick={handleGeneratePlan}
                  disabled={actionStatus?.type === 'loading'}
                  className="w-full bg-accent hover:bg-accent-strong text-white font-bold py-2 rounded text-xs transition shadow-sm disabled:opacity-50"
                >
                  {actionStatus?.type === 'loading' ? 'GENERATING PLAN...' : 'GENERATE RESPONSE PLAN'}
                </button>
              ) : (
                <div className="space-y-1.5">
                  <div className="bg-white p-2 rounded border border-blue-200 text-[11px] space-y-1">
                    <div className="flex justify-between font-bold">
                      <span>PLAN ID: {activePlan.plan_id.slice(0, 8)}...</span>
                      <span className="text-accent">{activePlan.status}</span>
                    </div>
                    <div><b>Priority:</b> {activePlan.priority}</div>
                  </div>

                  {activePlan.status === 'PENDING_APPROVAL' && (
                    <button
                      onClick={handleApprovePlan}
                      disabled={actionStatus?.type === 'loading'}
                      className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-bold py-2 rounded text-xs transition shadow-sm disabled:opacity-50"
                    >
                      {actionStatus?.type === 'loading' ? 'APPROVING...' : 'APPROVE RESPONSE PLAN'}
                    </button>
                  )}

                  {activePlan.status === 'APPROVED' && (
                    <button
                      onClick={handleDispatchAction}
                      disabled={actionStatus?.type === 'loading'}
                      className="w-full bg-accent hover:bg-accent-strong text-white font-bold py-2 rounded text-xs transition shadow-sm disabled:opacity-50"
                    >
                      {actionStatus?.type === 'loading' ? 'DISPATCHING...' : 'DISPATCH RESPONSE TEAM'}
                    </button>
                  )}
                </div>
              )}

              {actionStatus && (
                <div className={`text-[10px] font-bold p-1.5 rounded ${actionStatus.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
                  {actionStatus.message}
                </div>
              )}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
