/**
 * AUREM Bug History Dashboard
 * Company: Polaris Built Inc.
 * Theme: Obsidian Executive
 * 
 * Shows timeline of bug scans with auto-fix results
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bug, CheckCircle, XCircle, AlertTriangle, Clock,
  Activity, Zap, ChevronDown, ChevronUp, Download,
  RefreshCw, Shield, Terminal, Loader2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const AuremBugHistory = () => {
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [historyRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/aurem/bug-engine/history?limit=50`),
        fetch(`${API_URL}/api/aurem/bug-engine/stats`)
      ]);

      if (historyRes.ok) {
        const data = await historyRes.json();
        setHistory(data.history || []);
      }
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch (err) {
      console.error('Failed to fetch bug data:', err);
    }
    setLoading(false);
  };

  const triggerScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API_URL}/api/aurem/bug-engine/scan`, {
        method: 'POST'
      });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error('Scan failed:', err);
    }
    setScanning(false);
  };

  const exportHistory = () => {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aurem-bug-history-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
  };

  const filteredHistory = history.filter(entry => {
    if (filter === 'all') return true;
    if (filter === 'auto-fixed') return (entry.auto_fixed?.length || 0) > 0;
    if (filter === 'ai-fixed') return (entry.ai_suggested_fixes?.length || 0) > 0;
    if (filter === 'failing') return !entry.system_healthy_after;
    if (filter === 'healthy') return entry.system_healthy_after;
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-[#D4AF37] animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="Total Scans (7d)"
          value={stats?.total_scans || 0}
          icon={Activity}
        />
        <StatCard
          title="Auto-Fix Rate"
          value={`${stats?.auto_fix_rate || 0}%`}
          icon={Zap}
          highlight
        />
        <StatCard
          title="Healthy Scans"
          value={stats?.healthy_scans || 0}
          icon={CheckCircle}
          color="#009874"
        />
        <StatCard
          title="Total Errors"
          value={stats?.total_errors || 0}
          icon={Bug}
          color="#ef4444"
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {['all', 'auto-fixed', 'ai-fixed', 'failing', 'healthy'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded text-xs tracking-wide transition-all ${
                filter === f
                  ? 'bg-[#D4AF37]/20 text-[#D4AF37] border border-[#D4AF37]/50'
                  : 'bg-[#0A0A0A] text-[#555] border border-[#151515] hover:border-[#333]'
              }`}
            >
              {f.replace('-', ' ').toUpperCase()}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={exportHistory}
            className="flex items-center gap-2 px-4 py-2 bg-[#0A0A0A] border border-[#151515] rounded text-sm text-[#888] hover:border-[#D4AF37]/50 transition-all"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={triggerScan}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 bg-[#D4AF37]/10 border border-[#D4AF37]/50 rounded text-sm text-[#D4AF37] hover:bg-[#D4AF37]/20 transition-all disabled:opacity-50"
          >
            {scanning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {scanning ? 'Scanning...' : 'Manual Scan'}
          </button>
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-3">
        <AnimatePresence>
          {filteredHistory.length === 0 ? (
            <div className="text-center py-12 text-[#444]">
              <Shield className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p>No scan history found</p>
            </div>
          ) : (
            filteredHistory.map((entry, idx) => (
              <HistoryEntry
                key={idx}
                entry={entry}
                expanded={expandedId === idx}
                onToggle={() => setExpandedId(expandedId === idx ? null : idx)}
              />
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

const StatCard = ({ title, value, icon: Icon, highlight, color }) => (
  <motion.div
    whileHover={{ y: -2 }}
    className={`p-5 rounded-lg border transition-all ${
      highlight
        ? 'bg-gradient-to-br from-[#D4AF37]/10 to-[#0A0A0A] border-[#D4AF37]/30'
        : 'bg-[#0A0A0A] border-[#151515]'
    }`}
  >
    <div className="flex items-center justify-between mb-2">
      <span className="text-[10px] text-[#444] tracking-[0.15em] uppercase">{title}</span>
      <Icon className="w-4 h-4" style={{ color: color || (highlight ? '#D4AF37' : '#333') }} />
    </div>
    <span className="text-2xl font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
      {value}
    </span>
  </motion.div>
);

const HistoryEntry = ({ entry, expanded, onToggle }) => {
  const errorsCount = entry.errors_found?.length || 0;
  const autoFixedCount = entry.auto_fixed?.length || 0;
  const aiFixedCount = entry.ai_suggested_fixes?.length || 0;
  const isHealthy = entry.system_healthy_after;

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="bg-[#0A0A0A] border border-[#151515] rounded-lg overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-[#0F0F0F] transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            isHealthy ? 'bg-[#009874]/10' : 'bg-red-500/10'
          }`}>
            {isHealthy ? (
              <CheckCircle className="w-5 h-5 text-[#009874]" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )}
          </div>
          <div className="text-left">
            <p className="text-sm">{formatTime(entry.timestamp)}</p>
            <p className="text-xs text-[#444]">
              Duration: {entry.scan_duration_ms || 0}ms
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {errorsCount > 0 && (
            <div className="flex items-center gap-2">
              <Bug className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-400">{errorsCount} errors</span>
            </div>
          )}
          {autoFixedCount > 0 && (
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#D4AF37]" />
              <span className="text-sm text-[#D4AF37]">{autoFixedCount} auto-fixed</span>
            </div>
          )}
          {aiFixedCount > 0 && (
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-400" />
              <span className="text-sm text-blue-400">{aiFixedCount} AI fixes</span>
            </div>
          )}
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-[#333]" />
          ) : (
            <ChevronDown className="w-5 h-5 text-[#333]" />
          )}
        </div>
      </button>

      {/* Expanded Details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-[#151515]"
          >
            <div className="p-6 space-y-4">
              {/* Health Checks */}
              <div>
                <p className="text-xs text-[#444] mb-2 tracking-wider uppercase">Health Checks</p>
                <div className="grid grid-cols-2 gap-2">
                  {entry.health_checks?.map((check, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-2 bg-[#050505] rounded border border-[#151515]"
                    >
                      <span className="text-xs text-[#888]">{check.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[#444]">{check.response_time_ms}ms</span>
                        {check.healthy ? (
                          <CheckCircle className="w-3 h-3 text-[#009874]" />
                        ) : (
                          <XCircle className="w-3 h-3 text-red-400" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Errors Found */}
              {entry.errors_found?.length > 0 && (
                <div>
                  <p className="text-xs text-[#444] mb-2 tracking-wider uppercase">Errors Found</p>
                  <div className="space-y-2">
                    {entry.errors_found.map((error, i) => (
                      <div
                        key={i}
                        className="p-3 bg-red-500/5 border border-red-500/20 rounded"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <AlertTriangle className="w-3 h-3 text-red-400" />
                          <span className="text-xs text-red-400 uppercase">{error.level}</span>
                        </div>
                        <p className="text-sm text-[#888] font-mono">{error.message}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Auto Fixes */}
              {entry.auto_fixed?.length > 0 && (
                <div>
                  <p className="text-xs text-[#444] mb-2 tracking-wider uppercase">Auto-Fixed</p>
                  <div className="space-y-2">
                    {entry.auto_fixed.map((fix, i) => (
                      <div
                        key={i}
                        className="p-3 bg-[#D4AF37]/5 border border-[#D4AF37]/20 rounded"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Zap className="w-3 h-3 text-[#D4AF37]" />
                          <span className="text-xs text-[#D4AF37]">{fix.action}</span>
                          {fix.success && <CheckCircle className="w-3 h-3 text-[#009874]" />}
                        </div>
                        <p className="text-sm text-[#888]">{fix.description}</p>
                        {fix.note && (
                          <p className="text-xs text-[#444] mt-1">{fix.note}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Suggestions */}
              {entry.ai_suggested_fixes?.length > 0 && (
                <div>
                  <p className="text-xs text-[#444] mb-2 tracking-wider uppercase">AI Suggestions</p>
                  <div className="space-y-2">
                    {entry.ai_suggested_fixes.map((fix, i) => (
                      <div
                        key={i}
                        className="p-3 bg-blue-500/5 border border-blue-500/20 rounded"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Terminal className="w-3 h-3 text-blue-400" />
                          <span className="text-xs text-blue-400">AI Suggestion</span>
                        </div>
                        <p className="text-xs text-[#666] mb-2">{fix.error}</p>
                        <pre className="text-xs text-[#888] bg-[#050505] p-2 rounded overflow-x-auto">
                          {fix.ai_suggestion}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default AuremBugHistory;
