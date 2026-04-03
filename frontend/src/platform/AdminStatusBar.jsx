/**
 * AUREM Admin Status Bar
 * Company: Polaris Built Inc.
 * Theme: Obsidian Executive
 * 
 * Global status bar for admin pages showing:
 * - System health indicator
 * - Last sync timestamp
 * - Active missions count
 * - Circuit breaker status per channel
 * - Global SYNC button
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, RefreshCw, CheckCircle, XCircle, AlertTriangle,
  Mail, MessageSquare, Phone, Zap, Loader2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const AdminStatusBar = ({ onSyncComplete }) => {
  const [status, setStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncSuccess, setSyncSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/aurem/admin/status`);
      if (res.ok) {
        setStatus(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch status:', err);
    }
    setLoading(false);
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncSuccess(false);
    try {
      const res = await fetch(`${API_URL}/api/aurem/admin/sync`, {
        method: 'POST'
      });
      if (res.ok) {
        setSyncSuccess(true);
        await fetchStatus();
        onSyncComplete?.();
        
        // Reset success indicator after 3s
        setTimeout(() => setSyncSuccess(false), 3000);
      }
    } catch (err) {
      console.error('Sync failed:', err);
    }
    setSyncing(false);
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const circuitBreakerIcons = {
    email: Mail,
    whatsapp: MessageSquare,
    voice: Phone,
    llm: Zap,
  };

  if (loading) {
    return (
      <div className="h-12 bg-[#050505] border-b border-[#151515] flex items-center justify-center">
        <Loader2 className="w-4 h-4 text-[#333] animate-spin" />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ y: -10, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className={`h-12 border-b flex items-center justify-between px-6 transition-colors duration-300 ${
        syncSuccess
          ? 'bg-[#009874]/10 border-[#009874]/30'
          : 'bg-[#050505] border-[#151515]'
      }`}
    >
      {/* Left: System Health */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full animate-pulse ${
            status?.system_healthy ? 'bg-[#009874]' : 'bg-red-500'
          }`} />
          <span className={`text-xs tracking-wide ${
            status?.system_healthy ? 'text-[#009874]' : 'text-red-400'
          }`}>
            {status?.system_healthy ? 'SYSTEM HEALTHY' : 'SYSTEM DEGRADED'}
          </span>
        </div>

        <div className="h-4 w-px bg-[#151515]" />

        <div className="flex items-center gap-2 text-xs text-[#555]">
          <Activity className="w-3 h-3" />
          <span>{status?.active_missions || 0} Active Missions</span>
        </div>

        {status?.last_scan && (
          <>
            <div className="h-4 w-px bg-[#151515]" />
            <span className="text-xs text-[#444]">
              Last Scan: {formatTime(status.last_scan)}
            </span>
          </>
        )}
      </div>

      {/* Center: Circuit Breakers */}
      <div className="flex items-center gap-3">
        {Object.entries(status?.circuit_breakers || {}).map(([channel, cb]) => {
          const Icon = circuitBreakerIcons[channel] || Zap;
          const isOpen = cb.status === 'open';
          
          return (
            <div
              key={channel}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-[10px] tracking-wider uppercase ${
                isOpen
                  ? 'bg-[#009874]/10 text-[#009874]'
                  : 'bg-red-500/10 text-red-400'
              }`}
              title={isOpen ? `${channel} active` : `${channel} tripped - ${cb.remaining_minutes}m remaining`}
            >
              <Icon className="w-3 h-3" />
              <span>{channel}</span>
              {isOpen ? (
                <CheckCircle className="w-3 h-3" />
              ) : (
                <XCircle className="w-3 h-3" />
              )}
            </div>
          );
        })}
      </div>

      {/* Right: Sync Button */}
      <div className="flex items-center gap-4">
        {status?.last_sync && (
          <span className="text-xs text-[#444]">
            Synced: {formatTime(status.last_sync)}
          </span>
        )}
        
        <AnimatePresence mode="wait">
          {syncSuccess ? (
            <motion.div
              key="success"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              className="flex items-center gap-2 px-4 py-1.5 bg-[#009874]/20 border border-[#009874]/50 rounded"
            >
              <CheckCircle className="w-4 h-4 text-[#009874]" />
              <span className="text-xs text-[#009874] tracking-wide">Synced</span>
            </motion.div>
          ) : (
            <motion.button
              key="button"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              onClick={handleSync}
              disabled={syncing}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-[#D4AF37]/20 to-[#D4AF37]/10 border border-[#D4AF37]/50 rounded text-[#D4AF37] hover:from-[#D4AF37]/30 hover:to-[#D4AF37]/20 transition-all disabled:opacity-50"
            >
              {syncing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              <span className="text-xs tracking-wider font-medium">
                {syncing ? 'SYNCING...' : 'SYNC'}
              </span>
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

export default AdminStatusBar;
