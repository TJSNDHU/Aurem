/**
 * AUREM Auto Theme System
 * Smart day/night mode with:
 * - Time-based auto-switch (Light 6AM-6PM, Dark 6PM-6AM)
 * - OS preference detection as fallback
 * - Manual toggle with localStorage persistence
 * - Smooth transition between modes
 */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const ThemeContext = createContext({ theme: 'dark', toggleTheme: () => {}, isAuto: true, setAutoMode: () => {} });

export const useTheme = () => useContext(ThemeContext);

function getTimeBasedTheme() {
  const hour = new Date().getHours();
  return (hour >= 6 && hour < 18) ? 'light' : 'dark';
}

function getOSPreference() {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
  return 'dark';
}

function resolveAutoTheme() {
  const timeBased = getTimeBasedTheme();
  const osPref = getOSPreference();
  // Time-based takes priority, OS pref is tiebreaker during transition hours
  const hour = new Date().getHours();
  if (hour === 6 || hour === 18) return osPref; // transition hours — defer to OS
  return timeBased;
}

export function ThemeProvider({ children }) {
  const [isAuto, setIsAutoState] = useState(() => {
    const saved = localStorage.getItem('aurem-theme-mode');
    return saved !== 'manual';
  });

  const [theme, setTheme] = useState(() => {
    const savedMode = localStorage.getItem('aurem-theme-mode');
    if (savedMode === 'manual') {
      return localStorage.getItem('aurem-theme') || 'dark';
    }
    return resolveAutoTheme();
  });

  const applyTheme = useCallback((t) => {
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(t);
    document.documentElement.setAttribute('data-theme', t);
    // Force browser reflow to ensure CSS rules apply immediately
    void document.documentElement.offsetHeight;
  }, []);

  // Apply theme on change
  useEffect(() => { applyTheme(theme); }, [theme, applyTheme]);

  // Auto-update every minute when in auto mode
  useEffect(() => {
    if (!isAuto) return;
    const interval = setInterval(() => {
      const newTheme = resolveAutoTheme();
      if (newTheme !== theme) setTheme(newTheme);
    }, 60000);
    return () => clearInterval(interval);
  }, [isAuto, theme]);

  // Listen for OS preference changes
  useEffect(() => {
    if (!isAuto) return;
    const mq = window.matchMedia('(prefers-color-scheme: light)');
    const handler = () => setTheme(resolveAutoTheme());
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [isAuto]);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    setIsAutoState(false);
    localStorage.setItem('aurem-theme-mode', 'manual');
    localStorage.setItem('aurem-theme', newTheme);
  };

  const setManualTheme = (t) => {
    setTheme(t);
    setIsAutoState(false);
    localStorage.setItem('aurem-theme-mode', 'manual');
    localStorage.setItem('aurem-theme', t);
  };

  const setAutoMode = () => {
    setIsAutoState(true);
    localStorage.setItem('aurem-theme-mode', 'auto');
    localStorage.removeItem('aurem-theme');
    setTheme(resolveAutoTheme());
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setManualTheme, isAuto, setAutoMode }}>
      {children}
    </ThemeContext.Provider>
  );
}
