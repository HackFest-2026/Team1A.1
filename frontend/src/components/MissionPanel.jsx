import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { API_BASE_URL } from '../config';
import Icon from './ui/Icon';
import { registrationImpactReason } from './DecisionChain';

// Demo mission corridor. The route itself is computed by the backend road graph.
const MISSION = {
  name: 'Supply convoy',
  origin: { lat: 15.4030, lon: 75.0800, label: 'Navanagar staging area' },
  destination: { lat: 15.3647, lon: 75.1240, label: 'Hubballi city centre' },
};

const STATUS_CHIP = { ACTIVE: 'chip-info', AT_RISK: 'chip-warn', INVALIDATED: 'chip-bad', REPLACED: 'chip-ok' };

// Label the mission from the backend record; only the built-in demo corridor has names.
function missionLabel(detail) {
  const o = detail?.origin; const d = detail?.destination;
  const near = (a, b) => a && Math.abs(a.lat - b.lat) < 1e-4 && Math.abs(a.lon - b.lon) < 1e-4;
  if (!o || !d || (near(o, MISSION.origin) && near(d, MISSION.destination))) {
    return `${MISSION.name}: ${MISSION.origin.label} → ${MISSION.destination.label}`;
  }
  const fmt = (p) => `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`;
  return `Mission: (${fmt(o)}) → (${fmt(d)})`;
}

const score = (v) => (typeof v === 'number' ? v.toFixed(1) : '—');
const km = (m) => (typeof m === 'number' ? `${(m / 1000).toFixed(1)} km` : '—');
const mins = (s) => (typeof s === 'number' ? `${Math.round(s / 60)} min` : '—');
const time = (t) => (t ? new Date(t).toLocaleTimeString() : '—');

async function api(path, options) {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.message || `HTTP ${res.status}`);
  }
  return body;
}

const post = (path, payload) => api(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: payload === undefined ? undefined : JSON.stringify(payload),
});

function describeOutcome(rec) {
  switch (rec?.replacement_status) {
    case 'NO_SAFE_AVAILABLE_ROUTE': return 'No safe alternative exists: every path to the destination crosses a CRITICAL zone.';
    case 'NO_BETTER_ROUTE': return `No better alternative found. ${rec.decision?.reason || ''}`;
    case 'NO_ROUTE': return 'No alternative path exists in the road network.';
    case 'NOT_REQUIRED': return 'Replacement not required: the route is not compromised.';
    default: return rec?.message || 'No recommendation available.';
  }
}

const OUTCOME_LABEL = {
  NO_SAFE_AVAILABLE_ROUTE: 'no safe route exists',
  NO_ROUTE: 'no alternative path in the road network',
  NO_BETTER_ROUTE: 'no better route found',
};

function Metric({ label, current, proposed, change }) {
  return (
    <tr className="border-t border-slate-100">
      <td className="py-1 pr-2 font-sans text-slate-500">{label}</td>
      <td className="py-1 pl-2 text-right text-slate-800">{current}</td>
      <td className="py-1 pl-2 text-right font-semibold text-emerald-800">{proposed}</td>
      <td className="py-1 pl-2 text-right text-slate-500">{change}</td>
    </tr>
  );
}

export default function MissionPanel({ copData, refreshCop, showToast, onProposedRoute, onMissionChange, onStateChange }) {
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [busy, setBusy] = useState(null);
  // Self-declared operator name (no login in this prototype); remembered in this browser only.
  const [operator, setOperatorState] = useState(() => {
    try { return localStorage.getItem('aegis-operator') || ''; } catch { return ''; }
  });
  const setOperator = (v) => {
    setOperatorState(v);
    try { localStorage.setItem('aegis-operator', v); } catch { /* not persisted */ }
  };
  const [decisionReason, setDecisionReason] = useState('');
  const [lastOutcome, setLastOutcome] = useState(null);

  // The mission is the most recently created monitored route (backend state).
  const route = useMemo(() => {
    const routes = copData?.monitored_routes || [];
    return [...routes].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))[0] || null;
  }, [copData]);

  const routeId = route?.id;
  const loadDetail = useCallback(async () => {
    if (!routeId) { setDetail(null); return; }
    try {
      setDetail(await api(`/route-monitor/${routeId}`));
      setDetailError(null);
    } catch (e) {
      setDetailError(e.message || 'request failed'); // keep last detail, but say it is not current
    }
  }, [routeId]);

  useEffect(() => { loadDetail(); }, [loadDetail, copData?.generated_at]);
  useEffect(() => { onMissionChange?.(route); }, [route, onMissionChange]);
  useEffect(() => {
    onStateChange?.({ route, detail, detailError, lastOutcome, busy });
  }, [route, detail, detailError, lastOutcome, busy, onStateChange]);

  const pending = useMemo(
    () => (detail?.recommendations || []).filter((r) => r.status === 'PENDING').slice(-1)[0] || null,
    [detail],
  );

  useEffect(() => {
    const coords = pending?.candidate_route?.route?.coordinates;
    onProposedRoute(coords ? coords.map((c) => [c[1], c[0]]) : null);
  }, [pending, onProposedRoute]);

  const run = async (label, fn) => {
    setBusy(label);
    try {
      await fn();
    } catch (e) {
      showToast(`${label} failed: ${e.message}`, 'error');
    } finally {
      setBusy(null);
      await refreshCop?.();
      await loadDetail();
    }
  };

  const startMission = () => run('Mission setup', async () => {
    const { origin, destination } = MISSION;
    const r = await api(`/route?origin_lat=${origin.lat}&origin_lon=${origin.lon}&destination_lat=${destination.lat}&destination_lon=${destination.lon}`);
    if (r.status !== 'success') throw new Error(r.message || 'route planning failed');
    const reg = await post('/route-monitor/register', {
      origin: { lat: origin.lat, lon: origin.lon }, destination: { lat: destination.lat, lon: destination.lon },
      route_nodes: r.route_nodes, distance_m: r.distance_m, estimated_time_s: r.estimated_time_s,
    });
    setLastOutcome(null);
    showToast(`Mission route planned: ${km(r.distance_m)}, ${mins(r.estimated_time_s)} — status ${reg.monitor_status}`, 'success');
  });

  const computeAlternative = () => run('Alternative route', async () => {
    const rec = await post(`/route-monitor/${route.id}/replacement/recommend`);
    setLastOutcome(rec);
    showToast(rec.replacement_status === 'RECOMMENDATION_READY'
      ? 'Alternative route proposed — awaiting operator decision' : describeOutcome(rec),
    rec.replacement_status === 'RECOMMENDATION_READY' ? 'info' : 'error');
  });

  const simulateReport = (profile) => run('Simulated report', async () => {
    const res = await post('/simulation/field-report', { route_id: route.id, profile });
    const status = res.route_assessment?.current_status;
    showToast(`SIMULATED report → threat ${res.threat.incident_id} (${res.threat.severity}); mission route ${status}`,
      status === 'INVALIDATED' ? 'error' : 'info');
    if (status === 'INVALIDATED') {
      const rec = await post(`/route-monitor/${route.id}/replacement/recommend`);
      setLastOutcome(rec);
    }
  });

  const checkRoute = () => run('Route check', async () => {
    const res = await post(`/route-monitor/${route.id}/check`);
    showToast(`Route check: ${res.current_status}${res.reason ? ' — ' + res.reason : ''}`,
      res.current_status === 'ACTIVE' ? 'success' : 'error');
  });

  const decide = (approve) => run(approve ? 'Approval' : 'Rejection', async () => {
    const who = operator.trim() || undefined;          // backend default: "EOC operator"
    const why = decisionReason.trim() || undefined;
    if (approve) {
      await post(`/route-monitor/${route.id}/replacement/approve`,
        { recommendation_id: pending.recommendation_id, approved: true, actor: who, reason: why });
      showToast(`Replacement route approved by ${who || 'EOC operator'} — now the active mission route`, 'success');
    } else {
      await post(`/route-monitor/${route.id}/replacement/reject`,
        { recommendation_id: pending.recommendation_id, actor: who, reason: why });
      showToast(`Replacement route rejected by ${who || 'EOC operator'} — route remains compromised`, 'info');
    }
    setDecisionReason('');
    setLastOutcome(null);
  });

  // Threats currently on the mission route, with their linked evidence (COP state).
  const exposure = route?.hazard_summary?.threat_exposure || {};
  const threatIds = [...(exposure.critical_threat_ids || []), ...(exposure.high_threat_ids || [])];
  const threats = (copData?.threats || []).filter((t) => threatIds.includes(t.id));
  const evidenceFor = (id) => (copData?.evidence || []).filter((e) => e.threat_id === id);

  const events = useMemo(() => {
    if (!detail) return [];
    const ev = [{ t: detail.created_at, text: 'Mission route planned and monitoring started' }];
    (detail.transitions || []).forEach((tr) => ev.push({
      t: tr.timestamp,
      text: `${tr.previous_status} → ${tr.new_status}${tr.reason ? `: ${tr.reason}` : ''}${tr.trigger === 'THREAT_CHANGE' ? ' (automatic re-check)' : ''}`,
      tone: tr.new_status === 'INVALIDATED' ? 'red' : tr.new_status === 'REPLACED' ? 'green' : undefined,
    }));
    (detail.recommendations || []).forEach((r) => {
      ev.push({ t: r.created_at, text: `Alternative proposed (${km(r.candidate_route?.distance_m)}, ${mins(r.candidate_route?.estimated_time_s)})` });
      if (r.decided_at) {
        ev.push({
          t: r.decided_at,
          text: `${r.decided_by || 'Operator'} ${r.status === 'APPROVED' ? 'APPROVED' : 'REJECTED'} the alternative${r.decision_reason ? ` (${r.decision_reason})` : ''}`,
          tone: r.status === 'APPROVED' ? 'green' : 'amber',
        });
      }
    });
    (detail.replacement_attempts || []).forEach((a) => ev.push({
      t: a.timestamp,
      text: `Alternative search: ${OUTCOME_LABEL[a.outcome] || a.outcome}${a.blocking_threat_ids?.length ? ` (blocked by ${a.blocking_threat_ids.join(', ')})` : ''}`,
      tone: 'red',
    }));
    return ev.filter((e) => e.t).sort((a, b) => new Date(a.t) - new Date(b.t));
  }, [detail]);

  const status = route?.status;
  const hs = route?.hazard_summary || {};
  const lastTransition = (detail?.transitions || []).slice(-1)[0];
  const decided = (detail?.recommendations || []).filter((r) => r.decided_at).slice(-1)[0];
  // Latest persisted replacement search that produced no recommendation, if it is newer
  // than the route's last transition (i.e. it concerns the current compromise).
  const latestAttempt = (detail?.replacement_attempts || []).slice(-1)[0];
  const attemptOutcome = latestAttempt && (!lastTransition || latestAttempt.timestamp >= lastTransition.timestamp)
    ? { replacement_status: latestAttempt.outcome, message: latestAttempt.message, at: latestAttempt.timestamp } : null;
  const shownOutcome = lastOutcome || attemptOutcome;
  const cand = pending?.candidate_route;
  const candExposure = cand?.threat_exposure?.affected_threats || [];

  const signed = (v, digits, unit) => (typeof v === 'number' ? `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)} ${unit}` : '—');
  const dKm = typeof cand?.distance_m === 'number' && typeof route?.distance_m === 'number' ? (cand.distance_m - route.distance_m) / 1000 : null;
  const dMin = typeof cand?.estimated_time_s === 'number' && typeof route?.estimated_time_s === 'number' ? (cand.estimated_time_s - route.estimated_time_s) / 60 : null;

  return (
    <section className="panel text-[12px]" aria-label="Active mission">
      <header className="px-3 pt-3 pb-2 flex items-center justify-between gap-2 border-b border-slate-200">
        <h3 className="panel-title flex items-center gap-1.5"><Icon name="route" size={14} className="text-accent" /> Active mission</h3>
        <span className={busy ? 'chip-info' : STATUS_CHIP[status] || 'chip-muted'} aria-live="polite">
          {busy ? `${busy.toUpperCase()}…` : status || 'NO MISSION'}
        </span>
      </header>

      <div className="p-3 space-y-3">
        {!route ? (
          <div className="space-y-3">
            <div className="rounded-md border border-dashed border-slate-300 p-3 text-slate-600">
              <div className="font-semibold text-slate-900">{MISSION.name}</div>
              <div className="flex items-center gap-1 mt-0.5"><Icon name="pin" size={12} /> {MISSION.origin.label} → {MISSION.destination.label}</div>
              <p className="mt-2 text-[11px] text-slate-500">
                Starting plans a threat-aware route on the road graph and registers it for monitoring.
              </p>
            </div>
            <button onClick={startMission} disabled={!!busy} className="btn-primary w-full py-2">
              <Icon name="route" size={14} /> START MISSION
            </button>
          </div>
        ) : (
          <>
            <div>
              <div className="font-semibold text-slate-900 leading-snug">{missionLabel(detail)}</div>
              <dl className="mt-2 grid grid-cols-3 gap-1.5">
                <div className="rounded-md bg-slate-50 border border-slate-200 px-2 py-1.5">
                  <dt className="text-[10px] text-slate-500">Distance</dt>
                  <dd className="font-mono font-semibold text-slate-900">{km(route.distance_m)}</dd>
                </div>
                <div className="rounded-md bg-slate-50 border border-slate-200 px-2 py-1.5" title="Road-graph travel time">
                  <dt className="text-[10px] text-slate-500">Travel time</dt>
                  <dd className="font-mono font-semibold text-slate-900">{mins(route.estimated_time_s)}</dd>
                </div>
                <div className="rounded-md bg-slate-50 border border-slate-200 px-2 py-1.5" title="Heuristic hazard score (uncalibrated)">
                  <dt className="text-[10px] text-slate-500">Hazard (heuristic)</dt>
                  <dd className="font-mono font-semibold text-slate-900">{hs.overall_level ?? '—'} {score(hs.overall_score)}</dd>
                </div>
              </dl>
              {(hs.score_basis && hs.score_basis !== 'COMPLETE') || hs.confidence ? (
                <p className="mt-1 text-[11px] text-slate-500">
                  {hs.score_basis && hs.score_basis !== 'COMPLETE' && <span className="text-amber-700">Partial data — could be up to {score(hs.score_upper_bound)}. </span>}
                  {hs.confidence && <>Confidence {hs.confidence}.</>}
                </p>
              ) : null}
            </div>

            {status === 'REPLACED' && decided?.status === 'APPROVED' && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 p-2.5">
                <div className="flex items-center gap-1.5 font-semibold text-emerald-800"><Icon name="check" size={14} /> Operator decision recorded</div>
                <div className="mt-0.5 text-slate-800">
                  Approved alternative ({km(decided.candidate_route?.distance_m)} · {mins(decided.candidate_route?.estimated_time_s)}) at {time(decided.decided_at)}{decided.decided_by ? ` by ${decided.decided_by} (self-declared name)` : ''}.
                </div>
                {decided.decision_reason && <div className="text-slate-700"><b>Reason:</b> {decided.decision_reason}</div>}
                <div className="text-slate-600">The mission now follows the replacement route (green on the map) and is still monitored.</div>
              </div>
            )}

            {pending ? (
              <div className="rounded-lg border border-emerald-300 bg-white shadow-panel overflow-hidden" aria-label="Proposed alternative">
                <div className="px-2.5 py-2 bg-emerald-50 border-b border-emerald-200 flex items-center justify-between gap-2">
                  <span className="font-semibold text-emerald-800">Proposed alternative</span>
                  <span className="chip-warn">AWAITING YOUR DECISION</span>
                </div>
                <div className="p-2.5 space-y-2">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wide text-slate-500">
                        <th className="text-left font-medium pb-1"></th>
                        <th className="text-right font-medium pb-1">Current</th>
                        <th className="text-right font-medium pb-1">Proposed</th>
                        <th className="text-right font-medium pb-1">Change</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      <Metric label="Distance" current={km(route.distance_m)} proposed={km(cand?.distance_m)} change={signed(dKm, 1, 'km')} />
                      <Metric label="Travel time" current={mins(route.estimated_time_s)} proposed={mins(cand?.estimated_time_s)} change={signed(dMin, 0, 'min')} />
                      <Metric label="Hazard score" current={score(hs.overall_score)} proposed={score(cand?.hazard_summary?.overall_score)}
                        change={typeof hs.overall_score === 'number' && typeof cand?.hazard_summary?.overall_score === 'number' ? signed(cand.hazard_summary.overall_score - hs.overall_score, 1, '') : '—'} />
                      <Metric label="Threat zones crossed" current={threatIds.length} proposed={candExposure.length} change={signed(candExposure.length - threatIds.length, 0, '')} />
                    </tbody>
                  </table>
                  {dKm !== null && dMin !== null && (
                    <p className="text-slate-800"><b>Trade-off:</b> {signed(dKm, 1, 'km')}, {signed(dMin, 0, 'min')} to cross {candExposure.length} instead of {threatIds.length} known threat zone(s).</p>
                  )}
                  <p className="text-slate-600"><b className="text-slate-800">Engine rationale:</b> {pending.reason}</p>
                  <p className="text-[11px] text-slate-500 flex gap-1">
                    <Icon name="info" size={13} className="mt-px" />
                    <span>Avoids only the threat zones currently known to the backend; it is not a guarantee that the road is safe. Hazard scores are uncalibrated heuristics.</span>
                  </p>
                  <div className="grid grid-cols-1 gap-1.5 pt-0.5">
                    <label className="text-[11px] text-slate-600">
                      Decision by
                      <input data-field="operator" value={operator} onChange={(e) => setOperator(e.target.value)} maxLength={80}
                        placeholder="Your name or callsign"
                        className="mt-0.5 w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-900 focus:border-accent outline-none" />
                    </label>
                    <label className="text-[11px] text-slate-600">
                      Reason (recorded with the decision)
                      <input data-field="reason" value={decisionReason} onChange={(e) => setDecisionReason(e.target.value)} maxLength={500}
                        placeholder="Optional — e.g. tactical deviation to avoid compromised corridor"
                        className="mt-0.5 w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-900 focus:border-accent outline-none" />
                    </label>
                    <p className="text-[10px] text-slate-500">The name is self-declared and recorded as given — this prototype has no login.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 pt-0.5">
                    <button onClick={() => decide(true)} disabled={!!busy} className="btn-success py-2">
                      <Icon name="check" size={14} /> APPROVE
                    </button>
                    <button onClick={() => decide(false)} disabled={!!busy} className="btn-secondary py-2">
                      <Icon name="x" size={14} /> REJECT
                    </button>
                  </div>
                </div>
              </div>
            ) : status === 'INVALIDATED' && (
              <div className="rounded-md border border-red-200 bg-red-50 p-2.5 space-y-2">
                <div className="font-semibold text-red-800">Route compromised</div>
                {shownOutcome && (
                  <div className="text-red-900">
                    {describeOutcome(shownOutcome)}
                    {shownOutcome.at && <span className="block font-mono text-[10px] text-slate-500">recorded {time(shownOutcome.at)}</span>}
                  </div>
                )}
                <button onClick={computeAlternative} disabled={!!busy} className="btn-danger w-full">
                  <Icon name="route" size={13} /> {shownOutcome ? 'RECOMPUTE ALTERNATIVE' : 'COMPUTE ALTERNATIVE ROUTE'}
                </button>
              </div>
            )}

            {(status === 'INVALIDATED' || status === 'AT_RISK') && detail && (
              <div className="rounded-md border border-red-200 bg-red-50 p-2.5">
                <div className="flex items-center gap-1.5 font-semibold text-red-800"><Icon name="alert" size={14} /> Why the route is {status}</div>
                <div className="mt-0.5 text-red-900">{lastTransition ? lastTransition.reason : registrationImpactReason(route)}</div>
                <div className="font-mono text-[10px] text-slate-500 mt-0.5">recorded {time(lastTransition ? lastTransition.timestamp : detail.created_at)}</div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-1.5">
              <button onClick={checkRoute} disabled={!!busy} className="btn-secondary">
                <Icon name="refresh" size={13} /> CHECK ROUTE
              </button>
              <button onClick={() => simulateReport('FIELD_TEAM_BLOCKAGE')} disabled={!!busy}
                title="Creates a SIMULATED field report (evidence + CRITICAL threat) at the route midpoint"
                className="btn bg-amber-50 text-amber-900 border border-amber-300 hover:bg-amber-100">
                <Icon name="flask" size={13} /> SIMULATE THREAT REPORT
              </button>
            </div>

            {threats.map((t) => (
              <details key={t.id} open className="group rounded-md border border-slate-200">
                <summary className="cursor-pointer list-none px-2.5 py-2 flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900 flex items-center gap-1.5"><Icon name="alert" size={14} className="text-red-600" /> Threat assessment</span>
                  <span className="flex items-center gap-1.5">
                    {t.is_demo && <span className="chip-warn">SIMULATED</span>}
                    <Icon name="chevronDown" size={14} className="text-slate-500 transition-transform group-open:rotate-180" />
                  </span>
                </summary>
                <div className="px-2.5 pb-2.5 space-y-1.5">
                  <div className="font-semibold text-slate-900">{t.title}</div>
                  <div className="text-slate-700">Severity <b>{t.severity}</b> · {t.category} · radius {t.radius_m} m</div>
                  <div className="text-slate-700">Threat confidence <b>{t.confidence}</b> · source {t.source || 'unknown'} · reported {time(t.first_seen)}</div>
                  {evidenceFor(t.id).map((e) => (
                    <div key={e.id} className="rounded-md bg-slate-50 border border-slate-200 p-2 text-[11px]">
                      <div className="flex justify-between gap-1"><b className="font-mono">Evidence {e.id}</b>{e.is_simulation && <span className="text-amber-700 font-semibold">(SIMULATED)</span>}</div>
                      <div className="text-slate-700">{e.source_type} {e.source_id} · {e.observation_type} · {time(e.timestamp)}</div>
                      <div className="text-slate-600">Source-declared confidence {(e.confidence * 100).toFixed(0)}%
                        {e.provenance?.confidence_basis === 'DECLARED_BY_SIMULATION_PROFILE' && ' (fixed by the simulation profile, not measured)'}
                      </div>
                    </div>
                  ))}
                  {evidenceFor(t.id).length === 0 && <div className="text-slate-500">No evidence linked to this threat.</div>}
                  <div className="text-[11px] text-slate-500">Rule: an active {routePolicyText(t.severity)}</div>
                </div>
              </details>
            ))}

            <div>
              <div className="panel-title flex items-center gap-1.5 mb-1.5"><Icon name="clock" size={13} /> Mission log · backend record</div>
              {detailError && (
                <div className="mb-1 text-[11px] text-red-800">Mission record could not be refreshed ({detailError}){detail ? '; showing last loaded copy' : ''}.</div>
              )}
              <ol className="relative border-l border-slate-200 ml-1 space-y-1.5">
                {events.slice(-8).map((e, i) => (
                  <li key={i} className="pl-3 relative text-[11px] leading-snug">
                    <span aria-hidden="true" className={`absolute -left-[4.5px] top-1.5 w-2 h-2 rounded-full ${
                      e.tone === 'red' ? 'bg-red-500' : e.tone === 'green' ? 'bg-emerald-500' : e.tone === 'amber' ? 'bg-amber-500' : 'bg-slate-400'}`} />
                    <span className="font-mono text-[10px] text-slate-500">{time(e.t)}</span>{' '}
                    <span className={e.tone === 'red' ? 'text-red-800' : e.tone === 'green' ? 'text-emerald-800' : e.tone === 'amber' ? 'text-amber-800' : 'text-slate-700'}>{e.text}</span>
                  </li>
                ))}
              </ol>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function routePolicyText(severity) {
  if (severity === 'CRITICAL') {
    return 'CRITICAL zone is a hard exclusion: any route segment within its radius + 25 m buffer is compromised (INVALIDATED), and alternatives may not enter it.';
  }
  return `${severity} zone on the route marks it AT_RISK and adds a travel-time penalty to alternatives (uncalibrated).`;
}
