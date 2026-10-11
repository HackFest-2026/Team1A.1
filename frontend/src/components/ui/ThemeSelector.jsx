import React from 'react';
import Icon from './Icon';
import { useTheme } from '../../hooks/useTheme';

const ITEMS = [
  { id: 'dark', label: 'Dark', icon: 'moon' },
  { id: 'light', label: 'Light', icon: 'sun' },
  { id: 'system', label: 'System', icon: 'monitor' },
];

export default function ThemeSelector() {
  const { pref, setPref } = useTheme();
  return (
    <div role="radiogroup" aria-label="Colour theme"
      className="inline-flex items-center rounded-md border border-slate-200 bg-slate-100 p-0.5">
      {ITEMS.map((it) => {
        const on = pref === it.id;
        return (
          <button key={it.id} role="radio" aria-checked={on} onClick={() => setPref(it.id)}
            title={`${it.label} theme`}
            className={`inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] font-semibold transition-colors ${
              on ? 'bg-white text-slate-900 shadow-panel' : 'text-slate-500 hover:text-slate-800'
            }`}>
            <Icon name={it.icon} size={13} />
            <span className="sr-only 2xl:not-sr-only">{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}
