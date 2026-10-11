import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export default function AlertCenter({ onClose, selectedRegion }) {
  const [alerts, setAlerts] = useState([]);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  
  useEffect(() => {
    fetchAlerts();
  }, []);

  useEffect(() => {
    if (selectedRegion) {
      handlePreview(selectedRegion.state, selectedRegion.district);
    }
  }, [selectedRegion]);

  function showToast(msg, type = "info") {
    setToastMessage({ text: msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  }

  async function fetchAlerts() {
    try {
      const res = await fetch(`${API_BASE_URL}/national/alerts`);
      const data = await res.json();
      setAlerts(data.records || []);
    } catch (err) {
      console.error(err);
    }
  }

  async function handlePreview(state, district) {
    try {
      setError(null);
      const res = await fetch(`${API_BASE_URL}/national/alerts/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state, district })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Preview failed');
      setPreview(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSend() {
    if (!preview) return;
    try {
      setSending(true);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/national/alerts/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preview)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send alert');
      showToast(`Alert Sent! ID: ${data.alert_id}`, "success");
      setPreview(null);
      fetchAlerts();
    } catch (err) {
      setError(err.message);
      showToast("Error: " + err.message, "error");
    } finally {
      setSending(false);
    }
  }

  async function handleEscalate(alertId) {
    try {
      setEscalating(true);
      const res = await fetch(`${API_BASE_URL}/national/alerts/${alertId}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: "Recommend Command Dispatch Review" })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to escalate');
      showToast(`Authority Escalation Recommended. Incident ID: ${data.incident_id}`, "success");
      fetchAlerts();
    } catch (err) {
      showToast("Error: " + err.message, "error");
    } finally {
      setEscalating(false);
    }
  }

  const [ackLoading, setAckLoading] = useState(false);

  async function handleAcknowledgeMock(alertId) {
    if (ackLoading) return;
    try {
      setAckLoading(true);
      const citRes = await fetch(`${API_BASE_URL}/national/citizens`);
      const cData = await citRes.json();
      if (cData.records && cData.records.length > 0) {
        const cit_id = cData.records[0].citizen_id;
        const res = await fetch(`${API_BASE_URL}/national/alerts/${alertId}/acknowledge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ citizen_id: cit_id })
        });
        if (!res.ok) throw new Error('Failed to acknowledge');
        showToast("Mock Acknowledgment Received!", "success");
        fetchAlerts();
      }
    } catch (err) {
      showToast("Error: " + err.message, "error");
    } finally {
      setAckLoading(false);
    }
  }

  return (
    <div className="absolute inset-0 bg-canvas text-slate-900 z-50 flex flex-col p-4 overflow-hidden border border-slate-300">
      
      {/* Toast Banner */}
      {toastMessage && (
        <div className={`px-4 py-2 text-xs font-bold flex justify-between items-center z-50 shrink-0 ${
          toastMessage.type === 'error' ? 'bg-red-50 text-red-700 border-b border-red-200' : 'bg-emerald-50 text-emerald-700 border-b border-emerald-200'
        }`}>
          <span>ℹ {toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="font-bold">&times;</button>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-center mb-4 bg-white p-4 rounded-md border border-line shadow-sm shrink-0">
        <div>
          <h1 className="text-base font-extrabold tracking-tight text-accent uppercase flex items-center gap-2">
            <span>📢</span> TACTICAL ALERTS & BROADCAST CENTER
          </h1>
          <div className="text-xs font-bold text-slate-500 mt-0.5">● TARGETED GEOGRAPHIC ALERT DISPATCH</div>
        </div>
        <button onClick={onClose} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-bold border border-slate-300">
          CLOSE
        </button>
      </div>

      <div className="flex gap-4 flex-1 overflow-hidden">
        {/* Active Alerts */}
        <div className="w-1/2 flex flex-col bg-white p-4 rounded-md border border-line shadow-sm overflow-y-auto">
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-accent border-b border-line pb-2 mb-3">
            ACTIVE REGIONAL ALERTS ({alerts.length})
          </h2>
          {alerts.length === 0 ? <p className="text-slate-500 text-xs italic">No active alerts currently issued.</p> : (
            <div className="space-y-3 text-xs">
              {alerts.map(a => (
                <div key={a.alert_id} className="border rounded p-3 bg-slate-50 border-red-200">
                  <div className="flex justify-between border-b border-slate-200 pb-1.5 mb-2">
                    <span className="font-bold text-red-700">{a.severity} | {a.target_region.district}, {a.target_region.state}</span>
                    <span className="text-[10px] bg-red-100 text-red-800 px-2 rounded font-bold">{a.status}</span>
                  </div>
                  <div className="space-y-1 text-slate-700">
                    <p><b>Hazard:</b> {a.hazard_type}</p>
                    <p><b>Reason:</b> {a.reason}</p>
                    <p><b>Targeted:</b> {a.targeted_count} | <b>Acknowledged:</b> {a.acknowledged_count}</p>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button onClick={() => handleAcknowledgeMock(a.alert_id)} disabled={ackLoading} className="bg-slate-100 border border-slate-300 text-slate-700 px-2.5 py-1 text-xs font-bold rounded hover:bg-slate-200 disabled:opacity-50">
                      {ackLoading ? 'Processing...' : 'Acknowledge Alert'}
                    </button>
                    <button onClick={() => handleEscalate(a.alert_id)} disabled={escalating} className="bg-red-700 text-white px-2.5 py-1 text-xs font-bold rounded hover:bg-red-800">
                      AUTHORITY ESCALATION (COMMAND REVIEW)
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Alert Preview */}
        <div className="w-1/2 flex flex-col bg-white p-4 rounded-md border border-line shadow-sm overflow-y-auto">
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-accent border-b border-line pb-2 mb-3">
            ALERT PREVIEW & BROADCAST DRAFT
          </h2>
          {!preview ? (
            <p className="text-slate-500 text-xs italic">Select a region from the National EOC Map to preview geographic alerts.</p>
          ) : (
            <div className="space-y-3 text-xs">
              <div className="bg-amber-50 border border-amber-200 p-3 rounded text-amber-900 space-y-1">
                <div className="font-bold uppercase text-[10px] text-amber-800">TARGETED DISPATCH PREVIEW</div>
                <div><b>Region:</b> {preview.target_region.district}, {preview.target_region.state}</div>
                <div><b>Severity:</b> {preview.severity} | <b>Hazard:</b> {preview.hazard_type}</div>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-3 rounded text-slate-800 space-y-1">
                <div className="font-bold text-slate-900">Broadcasting Message:</div>
                <div className="italic text-slate-700 bg-white p-2 rounded border border-slate-200">"{preview.message}"</div>
              </div>

              {error && <div className="text-red-700 font-bold text-xs">{error}</div>}

              <button
                onClick={handleSend}
                disabled={sending}
                className="w-full bg-accent hover:bg-accent-strong text-white font-bold py-2 rounded text-xs transition shadow-sm"
              >
                {sending ? 'BROADCASTING...' : 'DISPATCH GEOGRAPHIC ALERT'}
              </button>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
