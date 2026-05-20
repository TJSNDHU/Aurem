/**
 * AUREM System Status Bar
 * Shows real-time system health — clean, non-overlapping layout
 * Sync button does GLOBAL sync of all sidebar data in one press
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Activity, AlertCircle, CheckCircle, RefreshCw, Trash2, Database } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SystemStatusBar = ({ token }) => {
  const [status, setStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [syncSuccess, setSyncSuccess] = useState(false);
  const [clearSuccess, setClearSuccess] = useState(false);
  const [clearResult, setClearResult] = useState(null);
  const [error, setError] = useState(null);

  const loadStatus = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch(`${API_URL}/api/system/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError('Failed to load system status');
    }
  }, [token]);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 60000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  // GLOBAL SYNC — hits all major data endpoints in parallel
  const handleGlobalSync = async () => {
    setSyncing(true);
    setError(null);
    setSyncSuccess(false);
    try {
      const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
      const syncEndpoints = [
        fetch(`${API_URL}/api/system/sync`, { method: 'POST', headers }),
        fetch(`${API_URL}/api/admin/customers`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/campaign/overview`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/agent/status`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/churn/analytics`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/fraud/dashboard`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/dark-scout/status`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/intelligence/all-clients`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/brief/today`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/empire/pulse`, { headers }).catch(() => null),
      ];
      await Promise.allSettled(syncEndpoints);
      setLastSync(new Date().toLocaleTimeString());
      setSyncSuccess(true);
      setTimeout(() => setSyncSuccess(false), 3000);
      setTimeout(loadStatus, 500);
    } catch (err) {
      setError('Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleCacheClear = async () => {
    setClearing(true);
    setError(null);
    setClearSuccess(false);
    setClearResult(null);
    try {
      const response = await fetch(`${API_URL}/api/cache/clear`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success) {
        setClearSuccess(true);
        setClearResult(data.cleared_items);
        setTimeout(() => { setClearSuccess(false); setClearResult(null); }, 4000);
        setTimeout(loadStatus, 1000);
      } else {
        setError('Cache clear failed');
      }
    } catch (err) {
      setError('Cache clear failed');
    } finally {
      setClearing(false);
    }
  };

  if (!status) {
    return (
      <div data-testid="system-status-bar" style={{
        background: 'rgba(255,255,255,0.5)',
        borderBottom: '1px solid rgba(45,122,74,0.1)',
        padding: '6px 20px',
        display: 'flex', alignItems: 'center', gap: 12, fontSize: 12,
        backdropFilter: 'blur(8px)',
      }}>
        <Activity className="size-3 text-[#888] animate-pulse" />
        <span style={{color: '#888'}}>Loading system status…</span>
      </div>
    );
  }

  const isHealthy = status.overall_status === 'healthy';
  const openBreakers = status.services?.circuit_breakers?.open || 0;
  const pendingWork =
    (status.pending_work?.followups || 0) +
    (status.pending_work?.handoffs || 0) +
    (status.pending_work?.approvals || 0);
  const dbCollections = status.services?.database?.collections || 0;

  return (
    <div data-testid="system-status-bar" style={{
      background: 'rgba(255,255,255,0.5)',
      borderBottom: `1px solid rgba(45,122,74,${isHealthy ? '0.12' : '0.05'})`,
      padding: '5px 20px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11,
      backdropFilter: 'blur(8px)',
      gap: 8,
      flexWrap: 'nowrap',
      minHeight: 36,
    }}>
      {/* Left - Status indicators */}
      <div style={{display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, overflow: 'hidden'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 5}}>
          {isHealthy ? <CheckCircle className="size-3.5 text-[#4A4]" /> : <AlertCircle className="size-3.5 text-[#F44]" />}
          <span style={{ color: isHealthy ? '#4A4' : '#F44', fontWeight: 600, fontSize: 10, letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>
            {isHealthy ? 'HEALTHY' : 'ISSUES'}
          </span>
        </div>

        {openBreakers > 0 && (
          <div style={{ padding: '1px 6px', background: '#3A1A1A', border: '1px solid #5A2A2A', borderRadius: 4, color: '#F88', fontSize: 9, whiteSpace: 'nowrap' }}>
            {openBreakers} Breaker{openBreakers > 1 ? 's' : ''}
          </div>
        )}

        {pendingWork > 0 && (
          <div style={{ padding: '1px 6px', background: '#1A1A2A', border: '1px solid #2A2A5A', borderRadius: 4, color: '#88F', fontSize: 9, whiteSpace: 'nowrap' }}>
            {pendingWork} Pending
          </div>
        )}

        <div style={{ color: '#888', display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, whiteSpace: 'nowrap' }}>
          <Database className="size-3" />
          <span>DB: {dbCollections}</span>
        </div>

        {status.services?.voice_tts?.elevenlabs !== 'active' && (
          <div style={{ padding: '1px 6px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 4, color: '#f59e0b', fontSize: 9, whiteSpace: 'nowrap' }}>
            TTS: fallback
          </div>
        )}
      </div>

      {/* Right - Actions (properly spaced, no overlap) */}
      <div style={{display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0}}>
        {/* Feedback messages */}
        {lastSync && !syncSuccess && <span style={{color: '#888', fontSize: 9, whiteSpace: 'nowrap'}}>Synced {lastSync}</span>}
        {error && <span style={{color: '#F44', fontSize: 9, whiteSpace: 'nowrap'}}>{error}</span>}
        {syncSuccess && <span style={{color: '#4ade80', fontSize: 9, fontWeight: 600, whiteSpace: 'nowrap'}}>All synced!</span>}
        {clearSuccess && <span style={{color: '#A855F7', fontSize: 9, fontWeight: 600, whiteSpace: 'nowrap'}}>{clearResult || 0} cleared</span>}

        {/* Cache Reset */}
        <button onClick={handleCacheClear} disabled={clearing} data-testid="cache-reset-btn"
          style={{
            background: 'rgba(168,85,247,0.06)', border: '1px solid rgba(168,85,247,0.15)',
            borderRadius: 6, padding: '4px 10px', cursor: clearing ? 'not-allowed' : 'pointer',
            color: '#8B5CF6', fontWeight: 600, fontSize: 10, display: 'flex', alignItems: 'center', gap: 4,
            opacity: clearing ? 0.6 : 1, whiteSpace: 'nowrap',
          }}>
          <Trash2 className={`size-3 ${clearing ? 'animate-spin' : ''}`} />
          {clearing ? 'Clearing' : 'Cache'}
        </button>

        {/* Global Sync */}
        <button onClick={handleGlobalSync} disabled={syncing} data-testid="sync-system-btn"
          style={{
            background: syncSuccess ? 'rgba(74,222,128,0.15)' : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: syncSuccess ? '1px solid rgba(74,222,128,0.3)' : 'none',
            borderRadius: 6, padding: '4px 12px', cursor: syncing ? 'not-allowed' : 'pointer',
            color: syncing ? '#888' : syncSuccess ? '#2D7A4A' : '#050505',
            fontWeight: 700, fontSize: 10, display: 'flex', alignItems: 'center', gap: 4,
            opacity: syncing ? 0.6 : 1, whiteSpace: 'nowrap',
          }}>
          <RefreshCw className={`size-3 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Syncing All...' : syncSuccess ? 'Done!' : 'Sync All'}
        </button>
      </div>
    </div>
  );
};

export default SystemStatusBar;
