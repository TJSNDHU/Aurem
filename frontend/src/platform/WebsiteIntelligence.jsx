import React, { useState, useEffect, useCallback } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import { motion } from 'framer-motion';
import { Globe, RefreshCw, AlertTriangle, CheckCircle, Shield, Zap, Eye, Search, ChevronRight, Clock, TrendingDown, Wrench } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const ScoreBar = ({ score, label, size = 'md' }) => {
  const color = score >= 90 ? '#4ade80' : score >= 70 ? '#facc15' : '#ef4444';
  const width = size === 'sm' ? 'w-20' : 'w-32';
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-[#9ca3af] w-24 truncate">{label}</span>
      <div className={`${width} h-1.5 rounded-full bg-[#1a1a2e] overflow-hidden`}>
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-xs font-bold" style={{ color }}>{score}</span>
    </div>
  );
};

const SeverityBadge = ({ severity }) => {
  const colors = {
    critical: 'bg-red-500/10 text-red-400 border-red-500/20',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    medium: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    low: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  };
  return (
    <span className={`text-[9px] px-1.5 py-0.5 rounded border ${colors[severity] || colors.medium}`}>
      {severity}
    </span>
  );
};

const ClientScanCard = ({ client, onSelect }) => {
  const score = client.overall_score || 0;
  const color = score >= 90 ? '#4ade80' : score >= 70 ? '#facc15' : '#ef4444';
  return (
    <motion.div
      whileHover={{ y: -2, borderColor: 'rgba(212,175,55,0.3)' }}
      onClick={() => onSelect(client)}
      className="p-4 rounded-xl cursor-pointer transition-all border border-[#1a1a2e] hover:border-[#D4AF37]/30"
      style={{ background: 'rgba(10,10,20,0.6)' }}
      data-testid={`client-scan-card-${client.tenant_id}`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-[#D4AF37]" />
          <span className="text-sm font-medium text-white truncate max-w-[180px]">{client.business_name || client.tenant_id}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="text-lg font-bold" style={{ color }}>{score}</div>
          <span className="text-[9px] text-[#9ca3af]">/100</span>
        </div>
      </div>
      <div className="space-y-1">
        {client.scores && Object.entries(client.scores).filter(([, v]) => typeof v === 'number' && v > 0).slice(0, 4).map(([k, v]) => (
          <ScoreBar key={k} label={k.replace('_', ' ')} score={v} size="sm" />
        ))}
      </div>
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#1a1a2e]">
        <div className="flex items-center gap-3 text-[9px] text-[#9ca3af]">
          {client.issues_count > 0 && <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-yellow-400" /> {client.issues_count} issues</span>}
          {client.auto_fix_count > 0 && <span className="flex items-center gap-1"><Wrench className="w-3 h-3 text-green-400" /> {client.auto_fix_count} fixed</span>}
        </div>
        <ChevronRight className="w-3 h-3 text-[#9ca3af]" />
      </div>
    </motion.div>
  );
};

const ScanDetailPanel = ({ scan, onClose, onRescan, scanning, scanError }) => {
  if (!scan) return null;
  const score = scan.overall_score || 0;
  const color = score >= 90 ? '#4ade80' : score >= 70 ? '#facc15' : '#ef4444';

  return (
    <div className="space-y-4" data-testid="scan-detail-panel">
      <div className="flex items-center justify-between">
        <button onClick={onClose} className="text-xs text-[#9ca3af] hover:text-[#D4AF37] transition-colors" aria-label="Back to overview">&larr; All Clients</button>
        <button
          onClick={onRescan}
          disabled={scanning}
          aria-label="Rescan website"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold tracking-wider text-[#050507] disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #D4AF37, #B8860B)' }}
          data-testid="rescan-btn"
        >
          <RefreshCw className={`w-3 h-3 ${scanning ? 'animate-spin' : ''}`} />
          {scanning ? 'Scanning...' : 'Rescan Now'}
        </button>
      </div>

      {scanError && (
        <div className="p-3 rounded-lg flex items-start gap-2 bg-red-500/10 border border-red-500/30" data-testid="scan-error-banner">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-xs font-bold text-red-400">Rescan failed</div>
            <p className="text-[11px] text-red-300/80 mt-0.5">{scanError}</p>
          </div>
        </div>
      )}

      <div className="p-5 rounded-xl border border-[#1a1a2e]" style={{ background: 'rgba(10,10,20,0.6)' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white">{scan.business_name || scan.tenant_id}</h3>
            <a href={scan.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#D4AF37] hover:underline">{scan.url}</a>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold" style={{ color }}>{score}</div>
            <div className="text-[9px] text-[#9ca3af]">Overall Score</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-4">
          {scan.scores && Object.entries(scan.scores).filter(([, v]) => typeof v === 'number' && v > 0).map(([k, v]) => (
            <ScoreBar key={k} label={k.replace('_', ' ')} score={v} />
          ))}
        </div>

        {scan.pagespeed_raw && (
          <div className="flex items-center gap-4 text-[10px] text-[#9ca3af] border-t border-[#1a1a2e] pt-3 mb-3">
            <span>LCP: <strong className="text-white">{scan.pagespeed_raw.lcp}</strong></span>
            <span>FCP: <strong className="text-white">{scan.pagespeed_raw.fcp}</strong></span>
            <span>CLS: <strong className="text-white">{scan.pagespeed_raw.cls}</strong></span>
            <span>TBT: <strong className="text-white">{scan.pagespeed_raw.tbt}</strong></span>
          </div>
        )}

        <div className="flex items-center gap-3 text-[9px] text-[#9ca3af]">
          <Clock className="w-3 h-3" />
          <span>Last scan: {scan.scanned_at ? new Date(scan.scanned_at).toLocaleString() : 'N/A'}</span>
          {scan.scan_duration_seconds && <span>({scan.scan_duration_seconds}s)</span>}
        </div>
      </div>

      {scan.issues && scan.issues.length > 0 && (
        <div className="p-4 rounded-xl border border-[#1a1a2e]" style={{ background: 'rgba(10,10,20,0.6)' }}>
          <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />
            Issues Found ({scan.issues.length})
          </h4>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {scan.issues.map((issue, i) => (
              <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-[#0a0a14] border border-[#1a1a2e]" data-testid={`issue-${i}`}>
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={issue.severity} />
                  <span className="text-xs text-white">{issue.title}</span>
                  {issue.detail && <span className="text-[9px] text-[#9ca3af]">({issue.detail})</span>}
                </div>
                {issue.fixable ? (
                  <span className="text-[9px] text-green-400 flex items-center gap-1"><Wrench className="w-3 h-3" /> Auto-fixable</span>
                ) : (
                  <span className="text-[9px] text-[#9ca3af]">Manual fix</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {scan.auto_fixed && scan.auto_fixed.length > 0 && (
        <div className="p-4 rounded-xl border border-green-500/20" style={{ background: 'rgba(74,222,128,0.03)' }}>
          <h4 className="text-xs font-bold text-green-400 mb-3 flex items-center gap-2">
            <CheckCircle className="w-3.5 h-3.5" />
            Auto-Fixed ({scan.auto_fixed.length})
          </h4>
          <div className="space-y-2">
            {scan.auto_fixed.map((fix, i) => (
              <div key={i} className="p-2.5 rounded-lg bg-[#0a0a14] border border-[#1a1a2e]">
                <div className="text-xs text-white mb-1">{fix.title || fix.fix_type}</div>
                {fix.instruction && <pre className="text-[9px] text-[#9ca3af] whitespace-pre-wrap font-mono bg-[#050510] p-2 rounded mt-1">{fix.instruction}</pre>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};


const WebsiteIntelligence = ({ token }) => {
  const [clients, setClients] = useState([]);
  const [selectedClient, setSelectedClient] = useState(null);
  const [detailScan, setDetailScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const [scanError, setScanError] = useState(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchClients = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/intelligence/all-clients`, { headers });
      const data = await r.json();
      setClients(data.clients || []);
    } catch (e) {
      console.error('Failed to fetch clients:', e);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  // iter 271 — smart polling every 15s (pauses in background tab)
  useLivePolling(fetchClients, 15000);

  useEffect(() => {
    const interval = setInterval(fetchClients, 30000);
    return () => clearInterval(interval);
  }, [fetchClients]);

  const selectClient = async (client) => {
    setSelectedClient(client);
    setScanError(null);
    try {
      const r = await fetch(`${API}/api/intelligence/latest/${client.tenant_id}`, { headers });
      const data = await r.json();
      if (data.found) {
        setDetailScan({ ...data, business_name: client.business_name });
      } else {
        setDetailScan({ ...client, issues: [], auto_fixed: [] });
      }
    } catch (e) {
      setDetailScan({ ...client, issues: [], auto_fixed: [] });
    }
  };

  const triggerRescan = async () => {
    if (!selectedClient) return;
    setScanning(true);
    setScanError(null);
    try {
      // Always pass the URL we already know for the selected client to avoid
      // the backend's "No website URL" error when the tenant row is missing.
      const body = selectedClient.url || selectedClient.website_url
        ? { website_url: selectedClient.url || selectedClient.website_url }
        : {};
      const r = await fetch(`${API}/api/intelligence/scan/${selectedClient.tenant_id}`, {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok || data.detail) {
        // Keep the previous scan visible and surface an error banner instead of wiping to zeros.
        setScanError(data.detail || `Rescan failed (HTTP ${r.status})`);
      } else {
        setDetailScan({ ...data, business_name: selectedClient.business_name });
        fetchClients();
      }
    } catch (e) {
      setScanError(`Network error: ${e.message}`);
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="intelligence-loading">
        <RefreshCw className="w-6 h-6 text-[#D4AF37] animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="website-intelligence">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-[#D4AF37]" />
          <h2 className="text-lg font-bold text-white tracking-wide">Website Intelligence</h2>
        </div>
        <div className="flex items-center gap-2 text-[9px] text-[#9ca3af]">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          Auto-scanning daily at 3:15 AM UTC
        </div>
      </div>

      {selectedClient && detailScan ? (
        <ScanDetailPanel
          scan={detailScan}
          onClose={() => { setSelectedClient(null); setDetailScan(null); setScanError(null); }}
          onRescan={triggerRescan}
          scanning={scanning}
          scanError={scanError}
        />
      ) : (
        <>
          {clients.length === 0 ? (
            <div className="text-center py-12 text-[#9ca3af]">
              <Search className="w-8 h-8 mx-auto mb-3 opacity-40" />
              <p className="text-sm">No client websites scanned yet.</p>
              <p className="text-xs mt-1">Add a website_url to a client profile to start scanning.</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
              {clients.map((c, i) => (
                <ClientScanCard key={c.tenant_id || i} client={c} onSelect={selectClient} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default WebsiteIntelligence;
