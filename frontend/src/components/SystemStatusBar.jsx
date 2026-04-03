/**
 * AUREM System Status Bar
 * Shows real-time system health at top of dashboard
 * Based on Reroots production pattern
 */

import React, { useState, useEffect } from 'react';
import { Activity, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SystemStatusBar = ({ token }) => {
  const [status, setStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadStatus();
    // Refresh every 60 seconds
    const interval = setInterval(loadStatus, 60000);
    return () => clearInterval(interval);
  }, [token]);

  const loadStatus = async () => {
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
      console.error('Status load error:', err);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/api/system/sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      const data = await response.json();
      
      if (data.success) {
        setLastSync(new Date().toLocaleTimeString());
        // Reload status after sync
        setTimeout(loadStatus, 1000);
      } else {
        setError(`Sync completed with ${data.errors?.length || 0} errors`);
      }
    } catch (err) {
      setError('Sync failed');
      console.error('Sync error:', err);
    } finally {
      setSyncing(false);
    }
  };

  if (!status) {
    return (
      <div style={{
        background: '#0A0A0A',
        borderBottom: '1px solid #1A1A1A',
        padding: '8px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontSize: 12
      }}>
        <Activity className="w-3 h-3 text-[#666] animate-pulse" />
        <span style={{color: '#666'}}>Loading system status...</span>
      </div>
    );
  }

  const isHealthy = status.overall_status === 'healthy';
  const openBreakers = status.services?.circuit_breakers?.open || 0;
  const pendingWork = 
    (status.pending_work?.followups || 0) +
    (status.pending_work?.handoffs || 0) +
    (status.pending_work?.approvals || 0);

  return (
    <div style={{
      background: isHealthy ? '#0A1A0A' : '#1A0A0A',
      borderBottom: `1px solid ${isHealthy ? '#1A3A1A' : '#3A1A1A'}`,
      padding: '8px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      fontSize: 12
    }}>
      {/* Left - Status */}
      <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
        {/* Overall Status */}
        <div style={{display: 'flex', alignItems: 'center', gap: 8}}>
          {isHealthy ? (
            <CheckCircle className="w-4 h-4 text-[#4A4]" />
          ) : (
            <AlertCircle className="w-4 h-4 text-[#F44]" />
          )}
          <span style={{
            color: isHealthy ? '#4A4' : '#F44',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            {isHealthy ? 'All Systems Healthy' : 'Issues Detected'}
          </span>
        </div>

        {/* Circuit Breakers */}
        {openBreakers > 0 && (
          <div style={{
            padding: '2px 8px',
            background: '#3A1A1A',
            border: '1px solid #5A2A2A',
            borderRadius: 4,
            color: '#F88'
          }}>
            {openBreakers} Circuit{openBreakers > 1 ? 's' : ''} Open
          </div>
        )}

        {/* Pending Work */}
        {pendingWork > 0 && (
          <div style={{
            padding: '2px 8px',
            background: '#1A1A2A',
            border: '1px solid #2A2A5A',
            borderRadius: 4,
            color: '#88F'
          }}>
            {pendingWork} Pending Item{pendingWork > 1 ? 's' : ''}
          </div>
        )}

        {/* Database Status */}
        <div style={{
          color: status.services?.database?.healthy ? '#888' : '#F44',
          display: 'flex',
          alignItems: 'center',
          gap: 4
        }}>
          <span>●</span>
          <span>Database: {status.services?.database?.healthy ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {/* Right - Actions */}
      <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
        {/* Last Sync */}
        {lastSync && (
          <span style={{color: '#666', fontSize: 11}}>
            Last sync: {lastSync}
          </span>
        )}

        {/* Error Message */}
        {error && (
          <span style={{color: '#F44', fontSize: 11}}>
            {error}
          </span>
        )}

        {/* Sync Button */}
        <button
          onClick={handleSync}
          disabled={syncing}
          style={{
            background: syncing ? '#333' : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 6,
            padding: '6px 14px',
            cursor: syncing ? 'not-allowed' : 'pointer',
            color: syncing ? '#888' : '#050505',
            fontWeight: 600,
            fontSize: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            transition: 'all 0.2s',
            opacity: syncing ? 0.6 : 1
          }}
          onMouseEnter={(e) => {
            if (!syncing) e.currentTarget.style.opacity = '0.9';
          }}
          onMouseLeave={(e) => {
            if (!syncing) e.currentTarget.style.opacity = '1';
          }}
        >
          <RefreshCw className={`w-3 h-3 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Syncing...' : 'Sync'}
        </button>
      </div>
    </div>
  );
};

export default SystemStatusBar;
