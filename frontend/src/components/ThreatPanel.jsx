import React, { useState } from 'react';
import Icon from './ui/Icon';

const SEV_CHIP = {
  CRITICAL: 'chip-bad',
  HIGH: 'chip-warn',
  MODERATE: 'chip-info',
  LOW: 'chip-muted',
};
const SEV_BAR = { CRITICAL: 'bg-red-500', HIGH: 'bg-amber-500', MODERATE: 'bg-blue-500', LOW: 'bg-slate-400' };

// Active threats from the COP snapshot (CLOSED/RESOLVED are excluded). Selecting one
// shows its linked evidence in SelectedThreatEvidence.
export default function ThreatPanel({ threats = [], onSelectThreat, selectedThreatId }) {
  const [filterSeverity, setFilterSeverity] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const activeThreats = threats.filter(t => t.status !== 'CLOSED' && t.status !== 'RESOLVED');
  const q = searchQuery.toLowerCase();
  const filteredThreats = activeThreats.filter(t => {
    const matchesSev = filterSeverity === 'ALL' || t.severity === filterSeverity;
    const matchesQuery = !q || t.title?.toLowerCase().includes(q) || t.category?.toLowerCase().includes(q) || t.id?.toLowerCase().includes(q);
    return matchesSev && matchesQuery;
  });

  const counts = {
    ALL: activeThreats.length,
    CRITICAL: activeThreats.filter(t => t.severity === 'CRITICAL').length,
    HIGH: activeThreats.filter(t => t.severity === 'HIGH').length,
  };

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      <div className="px-3 pt-3 pb-2 flex items-center justify-between gap-2 shrink-0">
        <h3 className="panel-title flex items-center gap-1.5">
          <Icon name="alert" size={14} className="text-red-600" /> Threat queue
        </h3>
        <span className="text-[11px] text-slate-500"><b className="text-slate-900">{activeThreats.length}</b> active</span>
      </div>

      <div className="px-3 pb-2 space-y-2 shrink-0">
        <div className="flex gap-1" role="group" aria-label="Filter by severity">
          {['ALL', 'CRITICAL', 'HIGH'].map((k) => (
            <button key={k} onClick={() => setFilterSeverity(k)} aria-pressed={filterSeverity === k}
              className={`flex-1 rounded-md border px-1.5 py-1 text-[10px] font-semibold transition-colors ${
                filterSeverity === k ? 'bg-accent-soft border-accent/40 text-accent' : 'border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}>
              {k === 'ALL' ? 'All' : k[0] + k.slice(1).toLowerCase()} <span className="font-mono">{counts[k]}</span>
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Filter by title, category or id"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          aria-label="Filter threats"
          className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-md text-slate-900 focus:border-accent outline-none"
        />
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-1.5">
        {filteredThreats.length === 0 ? (
          <div className="mx-1 mt-1 rounded-md border border-dashed border-slate-300 p-4 text-center text-[11px] text-slate-500">
            {activeThreats.length === 0
              ? <>No active threats. Threats appear here when a report is recorded — e.g. <b>SIMULATE SENSOR REPORT</b> on an active mission.</>
              : 'No threats match this filter.'}
          </div>
        ) : (
          filteredThreats.map(t => {
            const isSelected = selectedThreatId === t.id;
            return (
              <button
                key={t.id}
                onClick={() => onSelectThreat && onSelectThreat(t)}
                aria-pressed={isSelected}
                className={`relative w-full text-left rounded-md border pl-3 pr-2.5 py-2 transition-colors text-xs ${
                  isSelected ? 'bg-accent-soft border-accent/50' : 'bg-white border-slate-200 hover:bg-slate-50'
                }`}
              >
                <span className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-r ${SEV_BAR[t.severity] || 'bg-slate-400'}`} aria-hidden="true" />
                <div className="flex justify-between items-start gap-2">
                  <span className="font-semibold text-slate-900 leading-snug line-clamp-2">{t.title}</span>
                  <span className={SEV_CHIP[t.severity] || 'chip-muted'}>{t.severity}</span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-slate-500">
                  <span className="text-slate-700">{t.category}</span>
                  <span>· conf. {t.confidence}</span>
                  <span>· {t.radius_m} m</span>
                  {t.is_demo && <span className="text-amber-700 font-semibold">· DEMO/SIM</span>}
                </div>
                <div className="font-mono text-[9px] text-slate-400 mt-0.5">{t.id}</div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
