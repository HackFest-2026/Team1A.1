import { useCallback, useEffect, useState } from 'react';

// Theme preference: 'dark' (default), 'light' or 'system'. The resolved theme is written
// to <html data-theme>, which src/theme/palette.css keys every colour token on.
const KEY = 'aegis-theme';
const OPTIONS = ['dark', 'light', 'system'];

function readPref() {
  try {
    const v = localStorage.getItem(KEY);
    return OPTIONS.includes(v) ? v : 'dark';
  } catch {
    return 'dark';
  }
}

function resolve(pref) {
  if (pref !== 'system') return pref;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function useTheme() {
  const [pref, setPrefState] = useState(readPref);
  const [resolved, setResolved] = useState(() => resolve(readPref()));

  useEffect(() => {
    const apply = () => {
      const r = resolve(pref);
      document.documentElement.setAttribute('data-theme', r);
      setResolved(r);
    };
    apply();
    if (pref !== 'system' || !window.matchMedia) return undefined;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, [pref]);

  const setPref = useCallback((next) => {
    setPrefState(next);
    try { localStorage.setItem(KEY, next); } catch { /* preference not persisted */ }
  }, []);

  return { pref, resolved, setPref, options: OPTIONS };
}
