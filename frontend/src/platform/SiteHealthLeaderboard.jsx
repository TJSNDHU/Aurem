/**
 * Site Health Leaderboard — Customer health ranking
 * Shows Phase 1 (Pixel) and Phase 2 (Origin-Write) status per site.
 * Sites missing Phase 2 anchoring are flagged for attention.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, Shield, CheckCircle, XCircle, Clock, AlertTriangle,
  Globe, TrendingUp, RefreshCw, Loader2, ChevronDown, ChevronRight,
  Zap, Lock, ExternalLink, Eye, Link2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ─── Health Score Ring ─── */
const HealthRing = ({ score, size = 52 }) => {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const color = score >= 80 ? '#4ade80' : score >= 50 ? '#D4B977' : '#FF6B6B';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} data-testid="health-ring">
      <circle cx={size/2} cy={size/2} r={r} stroke="rgba(61,58,57,0.15)" strokeWidth="4" fill="none" />
      <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth="4" fill="none"
        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`} style={{ transition: 'stroke-dashoffset 1s ease-out' }} />
      <text x={size/2} y={size/2 + 4} textAnchor="middle" fontSize="13" fontWeight="bold" fill="#1A1A2E">{score}</text>
    </svg>
  );
};

/* ─── Phase Badge ─── */
const PhaseBadge = ({ active, verified, label }) => {
  if (verified) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider bg-[#4ade80]/15 text-[#FF6B00]" data-testid={`badge-${label}`}>
        <CheckCircle className="size-3" /> {label}
      </span>
    );
  }
  if (active) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider bg-[#D4B977]/15 text-[#B8942A]" data-testid={`badge-${label}`}>
        <Clock className="size-3" /> {label}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider bg-[#FF6B6B]/10 text-[#FF6B6B]" data-testid={`badge-${label}`}>
      <AlertTriangle className="size-3" /> {label}
    </span>
  );
};

/* ─── PSI Score Bar ─── */
const PSIBar = ({ label, score }) => {
  const color = score >= 90 ? '#4ade80' : score >= 50 ? '#D4B977' : '#FF6B6B';
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] text-[#888] w-10 truncate">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-[#f0f0ee] overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-[10px] font-bold w-6 text-right" style={{ color }}>{score}</span>
    </div>
  );
};

/* ─── Site Row ─── */
const SiteRow = ({ site, expanded, onToggle, onDeployPixel, deployingUrl }) => {
  const psi = site.pagespeed_scores || {};
  const hasPSI = Object.keys(psi).length > 0;
  const isDeploying = deployingUrl === site.url;

  return (
    <div className="mb-2" data-testid={`site-row-${site.url}`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-3.5 rounded-xl bg-white/50 backdrop-blur-sm border border-white/30 hover:bg-white/70 transition-all text-left"
        data-testid={`toggle-${site.url}`}
      >
        {/* Health Score */}
        <HealthRing score={site.health_score} />

        {/* Site Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Globe className="size-3.5 text-[#D4AF37] flex-shrink-0" />
            <span className="text-xs font-bold text-[#1A1A2E] truncate">{site.url}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <PhaseBadge active={site.phase1_pixel} verified={site.phase1_pixel} label="PIXEL" />
            <PhaseBadge active={site.phase2_origin} verified={site.phase2_verified} label="ORIGIN" />
            {site.double_lock_status === 'verified' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider bg-[#FF6B00]/15 text-[#FF6B00]">
                <Lock className="size-3" /> DOUBLE-LOCKED
              </span>
            )}
          </div>
        </div>

        {/* Fix Stats */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right">
            <div className="text-xs font-bold text-[#1A1A2E]">{site.deployed}/{site.total_fixes}</div>
            <div className="text-[9px] text-[#888]">deployed</div>
          </div>
          {expanded ? <ChevronDown className="size-3.5 text-[#888]" /> : <ChevronRight className="size-3.5 text-[#888]" />}
        </div>
      </button>

      {/* Deploy Pixel button — visible when pixel isn't deployed yet.
          Clicking runs a LIVE fetch of the URL, scans for the AUREM pixel snippet,
          and auto-marks if detected — no manual trust needed. */}
      {!site.phase1_pixel && site.total_fixes > 0 && (
        <button
          onClick={(e) => { e.stopPropagation(); onDeployPixel(site.url); }}
          disabled={isDeploying}
          data-testid={`deploy-pixel-btn-${site.url}`}
          className="mt-1 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-[10px] font-bold tracking-wider transition-all disabled:opacity-50"
          style={{
            background: 'linear-gradient(135deg, #FF6B00, #D4AF37)',
            color: '#0B0E11',
            boxShadow: '0 0 18px rgba(255,107,0,0.25)',
          }}
        >
          {isDeploying ? (
            <><Loader2 className="size-3.5 animate-spin" /> Detecting pixel on live site…</>
          ) : (
            <><Zap className="size-3.5" /> Detect &amp; Deploy Pixel ({site.total_fixes - site.deployed} fixes)</>
          )}
        </button>
      )}

      {/* Expanded Detail */}
      {expanded && (
        <div className="mt-1 sm:ml-14 p-3 sm:p-4 rounded-xl bg-white/40 border border-white/30 space-y-3" style={{ animation: 'auremFadeSlideIn 0.2s ease both' }}>
          {/* Fix breakdown */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="p-2 rounded-lg text-center" style={{ background: 'rgba(74,222,128,0.06)' }}>
              <div className="text-sm font-bold text-[#FF6B00]">{site.seo_fixes}</div>
              <div className="text-[8px] text-[#888] uppercase tracking-wider font-bold">SEO</div>
            </div>
            <div className="p-2 rounded-lg text-center" style={{ background: 'rgba(168,85,247,0.06)' }}>
              <div className="text-sm font-bold text-[#A855F7]">{site.geo_fixes}</div>
              <div className="text-[8px] text-[#888] uppercase tracking-wider font-bold">GEO</div>
            </div>
            <div className="p-2 rounded-lg text-center" style={{ background: 'rgba(100,200,255,0.06)' }}>
              <div className="text-sm font-bold text-[#64C8FF]">{site.a11y_fixes}</div>
              <div className="text-[8px] text-[#888] uppercase tracking-wider font-bold">A11Y</div>
            </div>
            <div className="p-2 rounded-lg text-center" style={{ background: 'rgba(255,107,107,0.06)' }}>
              <div className="text-sm font-bold text-[#FF6B6B]">{site.pending}</div>
              <div className="text-[8px] text-[#888] uppercase tracking-wider font-bold">PENDING</div>
            </div>
          </div>

          {/* Origin-Write Status */}
          <div className="p-3 rounded-lg" style={{ background: 'linear-gradient(135deg, #1C1712, #211D17)', border: '1px solid rgba(184,135,89,0.15)' }}>
            <div className="flex items-center gap-2 mb-2">
              <Lock className="size-3.5 text-[#D4A574]" />
              <span className="text-[10px] font-bold tracking-[1.5px] text-[#D4A574] uppercase">Double-Lock Status</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div>
                <span className="text-[#6B5744]">Phase 1 (Pixel):</span>
                <span className={`ml-1 font-bold ${site.phase1_pixel ? 'text-[#4ade80]' : 'text-[#FF6B6B]'}`}>
                  {site.phase1_pixel ? 'DEPLOYED' : 'NOT DEPLOYED'}
                </span>
              </div>
              <div>
                <span className="text-[#6B5744]">Phase 2 (Origin):</span>
                <span className={`ml-1 font-bold ${site.phase2_verified ? 'text-[#4ade80]' : site.phase2_origin ? 'text-[#D4B977]' : 'text-[#FF6B6B]'}`}>
                  {site.phase2_verified ? 'VERIFIED' : site.phase2_origin ? 'COMMITTED' : 'NOT COMMITTED'}
                </span>
              </div>
              {site.origin_committed_at && (
                <div>
                  <span className="text-[#6B5744]">Committed:</span>
                  <span className="ml-1 text-[#9B8B7A]">{new Date(site.origin_committed_at).toLocaleDateString()}</span>
                </div>
              )}
              {site.origin_verified_at && (
                <div>
                  <span className="text-[#6B5744]">Verified:</span>
                  <span className="ml-1 text-[#9B8B7A]">{new Date(site.origin_verified_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>
            {site.url_slug && (
              <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(184,135,89,0.1)' }}>
                <div className="flex items-center gap-1.5">
                  <Link2 className="size-3 text-[#6B5744]" />
                  <span className="text-[9px] text-[#6B5744] font-mono truncate">
                    /api/repair/origin/serve/{site.url_slug}/fixes.css
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* PageSpeed Scores */}
          {hasPSI && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 mb-1">
                <Eye className="size-3 text-[#888]" />
                <span className="text-[9px] font-bold tracking-[1px] text-[#888] uppercase">PageSpeed Insights</span>
              </div>
              {Object.entries(psi).map(([key, score]) => (
                <PSIBar key={key} label={key.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} score={score} />
              ))}
            </div>
          )}

          {/* Last activity */}
          {site.last_activity && (
            <div className="text-[9px] text-[#aaa] flex items-center gap-1">
              <Clock className="size-2.5" />
              Last activity: {new Date(site.last_activity).toLocaleString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/* ═══ MAIN COMPONENT ═══ */
const SiteHealthLeaderboard = ({ token }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedSite, setExpandedSite] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [deployingUrl, setDeployingUrl] = useState(null);
  const [deployToast, setDeployToast] = useState(null);
  const [heartbeat, setHeartbeat] = useState(null);
  const [heartbeatRunning, setHeartbeatRunning] = useState(false);

  const fetchLeaderboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/repair/health/leaderboard`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (e) {
      console.error('Leaderboard fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchLeaderboard();
  }, [token, fetchLeaderboard]);

  const fetchHeartbeat = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${API_URL}/api/repair/health/heartbeat/last`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const d = await r.json();
        setHeartbeat(d);
      }
    } catch { /* silent */ }
  }, [token]);

  useEffect(() => { fetchHeartbeat(); }, [fetchHeartbeat]);

  const handleRunHeartbeat = async () => {
    if (!window.confirm('Run Pixel Heartbeat now?\n\nThis live-fetches every tracked URL and auto-flips Phase-1 badges based on whether the AUREM pixel is currently present.')) return;
    setHeartbeatRunning(true);
    setDeployToast(null);
    try {
      const r = await fetch(`${API_URL}/api/repair/health/heartbeat/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      const d = await r.json();
      if (r.ok && d.ok) {
        setDeployToast({
          kind: 'success',
          msg: `🫀 Heartbeat complete — ${d.scanned} site${d.scanned === 1 ? '' : 's'} scanned · ${d.auto_marked} auto-marked · ${d.auto_reverted} reverted`,
        });
        await fetchLeaderboard();
        await fetchHeartbeat();
      } else {
        setDeployToast({ kind: 'error', msg: d.detail || `HTTP ${r.status}` });
      }
    } catch (e) {
      setDeployToast({ kind: 'error', msg: `Network: ${e.message}` });
    }
    setHeartbeatRunning(false);
    setTimeout(() => setDeployToast(null), 8000);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchLeaderboard();
  };

  const handleDeployPixel = async (url) => {
    setDeployingUrl(url);
    setDeployToast(null);

    // Step 1: auto-detect the AUREM pixel on the live site.
    let detected = false;
    let marked = 0;
    try {
      const res = await fetch(`${API_URL}/api/repair/health/verify-pixel`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const d = await res.json();
      if (res.ok && d.ok) {
        detected = !!d.detected;
        marked = d.auto_marked || 0;
        if (detected) {
          setDeployToast({
            kind: 'success',
            msg: `✓ Pixel detected on ${url} (${(d.matched_signatures || []).join(', ')}). Auto-marked ${marked} fix${marked === 1 ? '' : 'es'} as deployed.`,
          });
          await fetchLeaderboard();
          setDeployingUrl(null);
          setTimeout(() => setDeployToast(null), 8000);
          return;
        }
      }
    } catch (e) {
      // fall through to manual path
      console.warn('verify-pixel failed:', e);
    }

    // Step 2: pixel not detected — offer manual override.
    const msg = `The AUREM pixel wasn't detected on ${url}.\n\n` +
      `This can happen if:\n` +
      `• The pixel is injected server-side or via an edge function (not visible in raw HTML)\n` +
      `• The site is behind auth / Cloudflare challenge\n` +
      `• You haven't actually installed the snippet yet\n\n` +
      `Click OK to override and mark all pending fixes as deployed anyway.\n` +
      `Click Cancel to install the pixel first.`;
    if (!window.confirm(msg)) {
      setDeployingUrl(null);
      setDeployToast({ kind: 'error', msg: `Pixel not detected on ${url} — install it, then retry.` });
      setTimeout(() => setDeployToast(null), 8000);
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/repair/health/mark-pixel-deployed`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const d = await res.json();
      if (res.ok && d.ok) {
        setDeployToast({ kind: 'success', msg: `⚠ Manual override — ${d.marked_deployed} fix${d.marked_deployed === 1 ? '' : 'es'} marked deployed for ${url}` });
        await fetchLeaderboard();
      } else {
        setDeployToast({ kind: 'error', msg: d.detail || `HTTP ${res.status}` });
      }
    } catch (e) {
      setDeployToast({ kind: 'error', msg: `Network: ${e.message}` });
    }
    setDeployingUrl(null);
    setTimeout(() => setDeployToast(null), 8000);
  };

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 text-[#D4AF37] animate-spin" />
          <span className="ml-3 text-sm text-[#888]">Loading site health data…</span>
        </div>
      </div>
    );
  }

  const summary = data?.summary || {};
  const sites = data?.sites || [];

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6" style={{ background: 'transparent' }} data-testid="site-health-leaderboard">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div>
            <h1 className="text-lg sm:text-xl font-bold text-[#1A1A2E] tracking-wider mb-1">Site Health Leaderboard</h1>
            <p className="text-[11px] sm:text-xs text-[#888]">Phase 1 (Pixel) + Phase 2 (Origin-Write) status per customer site</p>
            {heartbeat && heartbeat.finished_at && (
              <p className="text-[10px] text-[#999] mt-1" data-testid="heartbeat-status">
                🫀 Last heartbeat: {new Date(heartbeat.finished_at).toLocaleString()} · {heartbeat.scanned || 0} scanned · {heartbeat.auto_marked || 0} marked · {heartbeat.auto_reverted || 0} reverted
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={handleRunHeartbeat}
              disabled={heartbeatRunning}
              data-testid="run-heartbeat"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
              style={{ background: 'rgba(255,107,0,0.12)', border: '1px solid rgba(255,107,0,0.3)', color: '#FF6B00' }}
              title="Live-verify pixel on every tracked site now"
            >
              {heartbeatRunning ? <Loader2 className="size-3.5 animate-spin" /> : <span className="text-sm">🫀</span>}
              Heartbeat
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              data-testid="refresh-leaderboard"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
              style={{ background: 'rgba(61,58,57,0.15)', border: '1px solid rgba(255,107,0,0.1)', color: '#FF6B00' }}
            >
              <RefreshCw className={`size-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Deploy toast */}
        {deployToast && (
          <div
            data-testid="deploy-toast"
            className={`mb-4 p-3 rounded-xl text-xs font-semibold border ${
              deployToast.kind === 'success'
                ? 'bg-green-500/10 border-green-500/30 text-green-700'
                : 'bg-red-500/10 border-red-500/30 text-red-700'
            }`}
          >
            {deployToast.msg}
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3 mb-6" data-testid="leaderboard-summary">
          <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
            <div className="text-xl font-bold text-[#1A1A2E]">{summary.total_sites || 0}</div>
            <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Total Sites</div>
          </div>
          <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
            <div className="text-xl font-bold text-[#4ade80]">{summary.phase1_deployed || 0}</div>
            <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Phase 1</div>
          </div>
          <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
            <div className="text-xl font-bold text-[#D4B977]">{summary.phase2_committed || 0}</div>
            <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Phase 2</div>
          </div>
          <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
            <div className="text-xl font-bold text-[#FF6B00]">{summary.phase2_verified || 0}</div>
            <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Verified</div>
          </div>
          <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
            <div className="text-xl font-bold" style={{ color: (summary.average_health || 0) >= 70 ? '#4ade80' : '#D4B977' }}>
              {summary.average_health || 0}%
            </div>
            <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Avg Health</div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 mb-4 px-1">
          <div className="flex items-center gap-1.5">
            <div className="size-2 rounded-full bg-[#4ade80]" />
            <span className="text-[9px] text-[#888]">Double-Locked</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="size-2 rounded-full bg-[#D4B977]" />
            <span className="text-[9px] text-[#888]">Origin Committed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="size-2 rounded-full bg-[#FF6B6B]" />
            <span className="text-[9px] text-[#888]">Needs Attention</span>
          </div>
        </div>

        {/* Site List */}
        {sites.length === 0 ? (
          <div className="text-center py-16">
            <Activity className="size-12 text-[#D4AF37]/30 mx-auto mb-3" />
            <h3 className="text-sm font-bold text-[#1A1A2E] mb-1">No Sites Tracked Yet</h3>
            <p className="text-xs text-[#888]">Scan a URL in the ORA Repair Engine to start tracking site health</p>
          </div>
        ) : (
          <div data-testid="site-list">
            {sites.map((site) => (
              <SiteRow
                key={site.url}
                site={site}
                expanded={expandedSite === site.url}
                onToggle={() => setExpandedSite(expandedSite === site.url ? null : site.url)}
                onDeployPixel={handleDeployPixel}
                deployingUrl={deployingUrl}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SiteHealthLeaderboard;
