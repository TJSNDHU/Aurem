/**
 * useTheme — auto-detect system theme + manual override.
 *
 * Persists to `localStorage('aurem_theme')` (values: 'dark' | 'light' | 'auto').
 * When 'auto', tracks the OS preference via `prefers-color-scheme` and updates
 * on the fly. Applies `data-theme` attribute on the supplied element (default:
 * <html>) so CSS variables in `dashboard-theme.css` take effect.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'aurem_theme';

const readStored = () => {
  if (typeof window === 'undefined') return 'auto';
  return window.localStorage.getItem(STORAGE_KEY) || 'auto';
};

const systemPrefersDark = () =>
  typeof window !== 'undefined'
  && window.matchMedia
  && window.matchMedia('(prefers-color-scheme: dark)').matches;

const resolveEffective = (mode) => {
  if (mode === 'dark' || mode === 'light') return mode;
  return systemPrefersDark() ? 'dark' : 'light';
};

export const useTheme = (target = (typeof document !== 'undefined' ? document.documentElement : null)) => {
  const [mode, setMode] = useState(readStored);
  const [effective, setEffective] = useState(() => resolveEffective(readStored()));

  // Apply attribute on every change.
  useEffect(() => {
    if (!target) return;
    target.setAttribute('data-theme', effective);
  }, [effective, target]);

  // Persist mode + recompute effective when mode flips.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, mode);
    setEffective(resolveEffective(mode));
  }, [mode]);

  // Track OS preference while in 'auto'.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e) => {
      if (mode === 'auto') setEffective(e.matches ? 'dark' : 'light');
    };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else mq.removeListener(onChange);
    };
  }, [mode]);

  const toggle = useCallback(() => {
    setMode((prev) => {
      const eff = resolveEffective(prev);
      return eff === 'dark' ? 'light' : 'dark';
    });
  }, []);

  return useMemo(() => ({ mode, effective, setMode, toggle }), [mode, effective, toggle]);
};
