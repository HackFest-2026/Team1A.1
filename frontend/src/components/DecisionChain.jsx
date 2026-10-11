import React from 'react';
import Icon from './ui/Icon';

// Observation -> Evidence -> Threat -> Route impact -> Recommendation -> Human decision,
// derived only from backend state: the monitored-route record (transitions and
// recommendations from GET /route-monitor/{id}) and the COP snapshot. Nothing here is
// stored separately, so the chain cannot disagree with the mission log or the map.

// Threat ids as written in transition reasons (THREAT-… from the threat API, RR-… from the risk engine).
const THREAT_ID_RE = /\b[A-Z]{2,8}-\d{4}-[A-F0-9]{8}\b/g;

const STAGES = [
  ['observation', 'Observation received'],
  ['evidence', 'Evidence linked'],
  ['threat', 'Threat identified'],
  ['impact', 'Route impact assessed'],
  ['alternative', 'Alternative generated'],
  ['decision', 'Operator decision'],
  ['outcome', 'Outcome recorded'],
];

const km = (m) => (typeof m === 'number' ? `${(m / 1000).toFixed(1)} km` : '—');
const mins = (s) => (typeof s === 'number' ? `${Math.round(s / 60)} min` : '—');
const time = (t) => (t ? new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');

// Reason text for a route that was already compromised when it was registered.
export function registrationImpactReason(route) {
  const ex = route?.hazard_summary?.threat_exposure || {};
  const ids = [...(ex.critical_threat_ids || []), ...(ex.high_threat_ids || [])];
  return ids.length
    ? `${route.status} since registration (no status change recorded). Currently crosses active threat zone(s): ${ids.join(', ')}`
    : `${route.status} since registration (hazard level; no status change recorded)`;
}

export function deriveChain(mission, copData) {
  const { route, detail, detailError, lastOutcome } = mission || {};
  const make = (overrides = {}) => STAGES.map(([key, label]) => ({
    key, label, state: 'pending', detail: '', at: null, ...(overrides[key] || {}),
  }));

  if (!route) {
    return { mission: null, steps: make(), next: 'Start the mission: Active Mission → START MISSION.' };
  }
  const missionInfo = { status: route.status, text: `${km(route.distance_m)} · ${mins(route.estimated_time_s)}` };

  if (!detail) {
    // Without the persisted mission record the chain cannot be derived; do not guess.
    const all = Object.fromEntries(STAGES.map(([k]) => [k, { state: detailError ? 'unknown' : 'pending', detail: detailError ? 'unknown' : '' }]));
    return {
      mission: { ...missionInfo, status: `last known ${route.status}` },
      steps: make(all),
      next: detailError ? `Mission record unavailable (${detailError}). Steps are unknown until the backend responds.` : 'Loading mission record…',
    };
  }

  const transitions = detail.transitions || [];
  const recs = detail.recommendations || [];
  let impact = [...transitions].reverse().find((t) => ['INVALIDATED', 'AT_RISK'].includes(t.new_status));
  if (!impact && transitions.length === 0 && ['INVALIDATED', 'AT_RISK'].includes(route.status)) {
    // Compromised from the start: registration records the initial status without a
    // transition, so use the persisted registration-time threat exposure instead.
    impact = { new_status: route.status, timestamp: detail.created_at, reason: registrationImpactReason(route), atRegistration: true };
  }
  // Backend timestamps for transitions and recommendations share one ISO format, so
  // string comparison orders them correctly.
  const after = (ts) => impact && ts && ts >= impact.timestamp;

  const threatIds = impact ? [...new Set(impact.reason?.match(THREAT_ID_RE) || [])] : [];
  const threats = threatIds.map((id) => (copData?.threats || []).find((t) => t.id === id) || { id, inactive: true });
  const evidence = (copData?.evidence || []).filter((e) => threatIds.includes(e.threat_id));
  const recsAfter = recs.filter((r) => after(r.created_at));
  const latestRec = recsAfter[recsAfter.length - 1];
  const replaced = transitions.find((t) => t.new_status === 'REPLACED' && after(t.timestamp));
  // A replacement search that produced no recommendation: persisted attempts first
  // (they survive a reload), else the outcome this browser just received.
  const attemptsAfter = (detail.replacement_attempts || []).filter((a) => after(a.timestamp));
  const latestAttempt = attemptsAfter[attemptsAfter.length - 1];
  const attemptIsLatest = latestAttempt && (!latestRec || latestAttempt.timestamp > latestRec.created_at);
  const failedOutcome = attemptIsLatest
    ? { replacement_status: latestAttempt.outcome, at: latestAttempt.timestamp }
    : (lastOutcome && lastOutcome.replacement_status !== 'RECOMMENDATION_READY' ? lastOutcome : null);

  const o = {};
  if (impact) {
    const e = evidence[evidence.length - 1];
    if (e) {
      o.observation = { state: 'done', detail: `${e.source_type} ${e.source_id || ''}${e.is_simulation ? ' · SIMULATED' : ''}`, at: e.timestamp };
      o.evidence = { state: 'done', detail: `${e.id} → ${e.threat_id}`, at: e.timestamp };
    } else if (threatIds.length) {
      o.observation = { state: 'warn', detail: 'No evidence record found' };
      o.evidence = { state: 'warn', detail: 'No evidence linked to the threat' };
    } else {
      o.observation = { state: 'na', detail: 'Not observation-driven' };
      o.evidence = { state: 'na', detail: 'Manual invalidation' };
    }
    // Prefer the threat that has linked evidence (the observation-driven one).
    const t = threats.find((x) => evidence.some((ev) => ev.threat_id === x.id)) || threats[0];
    o.threat = t
      ? { state: 'done', detail: t.inactive ? `${t.id} (no longer active)` : `${t.severity} · conf. ${t.confidence}${t.is_demo ? ' · SIMULATED' : ''}`, at: t.first_seen }
      : { state: 'na', detail: 'No threat referenced' };
    o.impact = replaced
      ? { state: 'done', detail: `${impact.new_status} (resolved)`, at: impact.timestamp }
      : { state: impact.new_status === 'INVALIDATED' ? 'alert' : 'warn', detail: `${impact.new_status}${impact.atRegistration ? ' (since registration)' : ''}`, at: impact.timestamp };

    if (failedOutcome && (!latestRec || latestRec.status !== 'PENDING')) {
      o.alternative = { state: 'alert', detail: failedOutcome.replacement_status === 'NO_SAFE_AVAILABLE_ROUTE' ? 'No safe route exists' : failedOutcome.replacement_status, at: failedOutcome.at };
    } else if (latestRec) {
      o.alternative = { state: 'done', detail: `${km(latestRec.candidate_route?.distance_m)} · ${mins(latestRec.candidate_route?.estimated_time_s)}`, at: latestRec.created_at };
    } else {
      o.alternative = { state: 'current', detail: 'No proposal on record' };
    }

    if (latestRec?.status === 'PENDING') o.decision = { state: 'current', detail: 'Awaiting approve / reject' };
    else if (latestRec) o.decision = { state: latestRec.status === 'APPROVED' ? 'done' : 'warn', detail: `${latestRec.status}${latestRec.decided_by ? ` by ${latestRec.decided_by}` : ''}`, at: latestRec.decided_at };

    if (replaced) o.outcome = { state: 'done', detail: 'Route REPLACED', at: replaced.timestamp };
  }

  let next;
  if (!impact) next = 'Route is monitored: it is re-checked automatically whenever a threat is recorded, changed or closed. Next: SIMULATE SENSOR REPORT (labelled simulation).';
  else if (replaced) next = 'Operator approved the alternative; the mission now follows the replacement route.';
  else if (latestRec?.status === 'PENDING') next = 'Review the comparison in Active Mission, then APPROVE or REJECT.';
  else if (failedOutcome) next = 'No acceptable alternative was found. The route stays compromised; recompute after conditions change.';
  else if (latestRec?.status === 'REJECTED') next = 'Alternative rejected; the route stays compromised. Recompute or hold.';
  else next = 'Route compromised. Next: COMPUTE ALTERNATIVE ROUTE in Active Mission.';
  return { mission: missionInfo, steps: make(o), next };
}

const NODE = {
  done: { cls: 'bg-emerald-600 text-white border-emerald-600', icon: 'check', label: 'complete' },
  current: { cls: 'bg-accent text-white border-accent ring-4 ring-accent/20', icon: 'clock', label: 'awaiting action' },
  alert: { cls: 'bg-red-600 text-white border-red-600', icon: 'alert', label: 'adverse result' },
  warn: { cls: 'bg-amber-500 text-white border-amber-500', icon: 'alert', label: 'needs attention' },
  unknown: { cls: 'bg-slate-200 text-slate-600 border-slate-300', icon: 'wifiOff', label: 'unknown' },
  na: { cls: 'bg-slate-100 text-slate-500 border-slate-300', icon: 'info', label: 'not applicable' },
  pending: { cls: 'bg-white text-slate-400 border-slate-300 border-dashed', icon: null, label: 'pending' },
};
const LABEL_TONE = {
  done: 'text-slate-900', current: 'text-accent', alert: 'text-red-700', warn: 'text-amber-800',
  unknown: 'text-slate-500', na: 'text-slate-500', pending: 'text-slate-400',
};
const STATUS_CHIP = { ACTIVE: 'chip-info', AT_RISK: 'chip-warn', INVALIDATED: 'chip-bad', REPLACED: 'chip-ok' };

export default function DecisionChain({ mission, copData }) {
  const { mission: m, steps, next } = deriveChain(mission, copData);
  return (
    <section className="panel px-3 py-2.5 shrink-0" aria-label="Mission decision chain">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2.5">
        <h3 className="panel-title flex items-center gap-1.5"><Icon name="activity" size={14} className="text-accent" /> Decision chain</h3>
        <span className="text-[11px] text-slate-500 flex items-center gap-1.5">
          Mission:
          {m ? <><span className={STATUS_CHIP[m.status] || 'chip-muted'}>{m.status}</span><span className="text-slate-700">{m.text}</span></>
            : <span className="chip-muted">NOT STARTED</span>}
        </span>
        <span className="ml-auto text-[11px] text-slate-700 flex items-center gap-1.5 min-w-0">
          <Icon name="info" size={13} className="text-accent" />
          <span>{next}</span>
        </span>
      </div>
      <ol className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-x-2 gap-y-3">
        {steps.map((s, i) => {
          const node = NODE[s.state] || NODE.pending;
          return (
            <li key={s.key} data-step={s.key} data-state={s.state} className="relative min-w-0">
              {i < steps.length - 1 && (
                <span aria-hidden="true"
                  className={`hidden xl:block absolute top-[11px] left-7 right-[-6px] h-0.5 ${s.state === 'done' ? 'bg-emerald-500/60' : 'bg-slate-200'}`} />
              )}
              <div className="relative flex items-start gap-2">
                <span className={`relative z-10 mt-0.5 w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 ${node.cls}`}
                  title={node.label}>
                  {node.icon ? <Icon name={node.icon} size={13} strokeWidth={2.4} /> : <span className="text-[10px] font-bold">{i + 1}</span>}
                </span>
                <div className="min-w-0 pt-0.5">
                  <div className={`text-[11px] font-semibold leading-tight ${LABEL_TONE[s.state]}`}>{s.label}</div>
                  <div className="text-[11px] text-slate-600 leading-snug break-words line-clamp-2" title={s.detail}>
                    {s.detail || <span className="text-slate-400">{s.state === 'pending' ? 'Pending' : ''}</span>}
                  </div>
                  {s.at && <div className="font-mono text-[10px] text-slate-400">{time(s.at)}</div>}
                  <span className="sr-only">Status: {node.label}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

const SOURCE_DOT = { ok: 'bg-emerald-500', sim: 'bg-amber-500', off: 'bg-slate-400', bad: 'bg-red-500' };

// Compact data-source availability (values from /api/system/status, the COP snapshot
// and fixed facts about what this prototype does not ingest).
export function DataSourceStrip({ copData, copError, systemStatus }) {
  const weather = copData?.system?.weather_mode;
  const terrain = systemStatus?.terrain;
  const lastKnown = (v) => (copError ? `${v} (last known)` : v);
  const sources = [
    ['Backend', copError ? 'UNREACHABLE' : copData ? 'CONNECTED' : 'CONNECTING', copError ? 'bad' : copData ? 'ok' : 'off'],
    ['Road graph (OSM)', lastKnown(systemStatus?.osm || 'UNKNOWN'), systemStatus?.osm === 'LOADED' && !copError ? 'ok' : 'off'],
    ['Terrain (CartoDEM)', lastKnown(!terrain ? 'UNKNOWN' : terrain === 'AVAILABLE' ? 'AVAILABLE' : `UNAVAILABLE (${terrain})`), terrain === 'AVAILABLE' && !copError ? 'ok' : 'off'],
    ['Weather', lastKnown(weather === 'CONTROLLED_SCENARIO' ? 'CONTROLLED SCENARIO' : weather || 'UNKNOWN'),
      copError ? 'off' : weather === 'AVAILABLE' ? 'ok' : weather === 'CONTROLLED_SCENARIO' ? 'sim' : 'off'],
    ['Sensor / field feeds', 'NONE CONNECTED — simulated reports only', 'sim'],
    ['Unit positions', 'MANUAL / SEEDED — no live GPS', 'sim'],
  ];
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]" aria-label="Data source availability">
      {sources.map(([name, value, tone]) => (
        <li key={name} className="flex items-center gap-1.5 whitespace-nowrap" title={`${name}: ${value}`}>
          <span className={`dot ${SOURCE_DOT[tone]}`} aria-hidden="true" />
          <span className="text-slate-500">{name}:</span>
          <span className={`font-semibold ${tone === 'bad' ? 'text-red-700' : tone === 'ok' ? 'text-slate-800' : tone === 'sim' ? 'text-amber-800' : 'text-slate-600'}`}>{value}</span>
        </li>
      ))}
    </ul>
  );
}
