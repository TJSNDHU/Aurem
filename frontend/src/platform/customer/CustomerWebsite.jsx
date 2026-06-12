/**
 * CustomerWebsite — Complete Customer Dashboard (Phase 3 rewrite)
 * =================================================================
 * Replaces manual "Rescan" with subscription-driven architecture:
 *   1. Trial Meter / Subscription Status (top)
 *   2. Golden Demo Repair Dashboard (existing logic — preserved)
 *   3. "Boost Your Site" service catalog grid (NEW)
 *   4. "Scan a Friend's Site" viral growth section (NEW)
 *   5. Pixel Installer wizard (4 methods) (NEW)
 */
import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  Activity, AlertTriangle, CheckCircle2, Loader2, ShieldCheck, Sparkles,
  Zap, Target, TrendingUp, Lock, Users as UsersIcon, Gift, Share2,
  Phone, Wrench, Shield, BarChart3, Mail, Megaphone, DollarSign,
  Copy, Download, Code,
} from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';
import CouncilRepairPanel from './CouncilRepairPanel';

const API = process.env.REACT_APP_BACKEND_URL || '';

const COLORS = {
  bg: 'rgba(15,18,28,0.55)',
  border: 'rgba(212,175,55,0.18)',
  gold: '#D4AF37',
  orange: '#FF8A3D',
  red: '#EF4444',
  yellow: '#EAB308',
  green: '#22C55E',
  textHi: '#F4F4F4',
  textLo: '#8A8070',
};

const CLUSTER_ICONS = {
  repair: Wrench,
  security: Shield,
  crm: UsersIcon,
  marketing: Megaphone,
  power: Zap,
  monitor: Activity,
  growth: TrendingUp,
  compliance: Lock,
};

const CLUSTER_COLORS = {
  repair: '#3b82f6',
  security: '#ef4444',
  crm: '#22c55e',
  marketing: '#a855f7',
  power: '#fb923c',
  monitor: '#06b6d4',
  growth: '#eab308',
  compliance: '#ec4899',
};

const card = {
  borderRadius: 18, padding: 24,
  background: COLORS.bg,
  backdropFilter: 'blur(22px) saturate(150%)',
  WebkitBackdropFilter: 'blur(22px) saturate(150%)',
  border: `1px solid ${COLORS.border}`,
  boxShadow: '0 16px 44px rgba(0,0,0,0.35), inset 0 1px 0 rgba(212,175,55,0.08)',
  position: 'relative',
  marginBottom: 18,
};

function scoreColor(s) {
  if (s >= 80) return COLORS.green;
  if (s >= 60) return COLORS.yellow;
  if (s >= 40) return COLORS.orange;
  return COLORS.red;
}

function ScoreGauge({ score, label, size = 170 }) {
  const color = scoreColor(score || 0);
  const radius = size / 2 - 14;
  const circ = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, score || 0));
  const dash = (pct / 100) * circ;
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="rgba(255,255,255,0.06)" strokeWidth={10} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={radius} stroke={color} strokeWidth={10} fill="none"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 1s ease, stroke 1s ease', filter: `drop-shadow(0 0 12px ${color}66)` }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontSize: size * 0.32, fontWeight: 800, color, lineHeight: 1, fontFamily: "'Cinzel',serif" }}>{score ?? '—'}</div>
        <div style={{ fontSize: 10, color: COLORS.textLo, letterSpacing: '0.2em', textTransform: 'uppercase', marginTop: 4, fontWeight: 600 }}>{label || 'Score'}</div>
      </div>
    </div>
  );
}

function SeverityDot({ sev }) {
  const c = sev === 'critical' ? COLORS.red : sev === 'high' ? COLORS.orange : sev === 'medium' ? COLORS.yellow : COLORS.green;
  return <span style={{ width: 8, height: 8, borderRadius: 999, background: c, display: 'inline-block', marginRight: 10, marginTop: 6, flexShrink: 0, boxShadow: `0 0 6px ${c}99` }} />;
}

function HeatmapBar({ pct, color }) {
  return (
    <div style={{ position: 'relative', height: 18, background: 'rgba(10,10,18,0.7)', borderRadius: 6, overflow: 'hidden' }}>
      <div style={{
        width: `${pct}%`, height: '100%',
        background: `linear-gradient(90deg, ${COLORS.red} 0%, ${COLORS.orange} 35%, ${COLORS.yellow} 60%, ${color || COLORS.green} 100%)`,
        transition: 'width 0.8s ease-out',
        boxShadow: `0 0 14px ${color || COLORS.gold}66`,
      }} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#FFF', fontWeight: 700 }}>
        {Math.floor(pct)}%
      </div>
    </div>
  );
}

export default function CustomerWebsite() {
  const token = getPlatformToken();
  const H = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  // Repair state
  const [scan, setScan] = useState(null);
  const [loadingScan, setLoadingScan] = useState(true);
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  // Trial + subscriptions
  const [trial, setTrial] = useState(null);
  const [mySubs, setMySubs] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [loadingCatalog, setLoadingCatalog] = useState(true);

  // Load initial scan + trial + catalog
  useEffect(() => {
    (async () => {
      try {
        // Ensure trial exists
        await fetch(`${API}/api/trial/activate`, { method: 'POST', headers: H }).catch(() => {});
        const [scanR, trialR, subR, catR] = await Promise.all([
          fetch(`${API}/api/customer/website/scan`, { method: 'POST', headers: H }),
          fetch(`${API}/api/trial/status`, { headers: H }),
          fetch(`${API}/api/customer/subscriptions`, { headers: H }),
          fetch(`${API}/api/catalog/services`),
        ]);
        if (scanR.ok) setScan(await scanR.json());
        if (trialR.ok) setTrial((await trialR.json()).trial);
        if (subR.ok) setMySubs(await subR.json());
        if (catR.ok) setCatalog(await catR.json());
      } catch (e) {
        // graceful degrade
      } finally {
        setLoadingScan(false);
        setLoadingCatalog(false);
      }
    })();
  }, [H]);

  // Repair job polling
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const handleStart = async () => {
    if (!scan) return;
    setStarting(true);
    try {
      const res = await fetch(`${API}/api/customer/website/repair/start`, { method: 'POST', headers: H });
      if (!res.ok) throw new Error('Start failed');
      const d = await res.json();
      setJob({ ...d, events: d.events || [], status: 'running', progress_pct: 0 });
      pollRef.current = setInterval(async () => {
        const r = await fetch(`${API}/api/customer/website/repair/status`, { headers: H });
        if (r.ok) {
          const s = await r.json();
          setJob(s);
          if (s.status === 'completed' || s.status === 'error') clearInterval(pollRef.current);
        }
      }, 2200);
    } catch (e) { alert(e.message); } finally { setStarting(false); }
  };

  const refreshSubs = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/customer/subscriptions`, { headers: H });
      if (r.ok) setMySubs(await r.json());
    } catch (e) {}
  }, [H]);

  const isIdle = !job || job.status === 'idle';
  const isRunning = job?.status === 'running';
  const isDone = job?.status === 'completed';

  const activeServiceIds = new Set((mySubs?.subscriptions || []).map(s => s.service_id));

  // Group catalog services by cluster
  const clusteredServices = useMemo(() => {
    if (!catalog?.services) return {};
    const g = {};
    for (const s of catalog.services) {
      (g[s.cluster] = g[s.cluster] || []).push(s);
    }
    return g;
  }, [catalog]);

  return (
    <div data-testid="customer-website" style={{ padding: '16px 0', fontFamily: "'Jost',sans-serif" }}>
      {/* iter D-84 §4 — Council-gated repair entry point */}
      <CouncilRepairPanel />

      {/* ═════════ 1. TRIAL + SUBSCRIPTION METER ═════════ */}
      <TrialMeterCard trial={trial} subs={mySubs} />

      {/* ═════════ 2. GOLDEN DEMO REPAIR DASHBOARD ═════════ */}
      {isIdle && !loadingScan && (
        <div data-testid="website-idle" style={{ ...card }}>
          <div style={{ display: 'grid', gridTemplateColumns: '220px auto', gap: 32, alignItems: 'center' }}>
            <ScoreGauge score={scan?.score || 0} label="Current Score" size={200} />
            <div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                padding: '6px 12px', borderRadius: 999,
                background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)',
                color: COLORS.red, fontSize: 11, letterSpacing: '0.15em', textTransform: 'uppercase', fontWeight: 700,
                marginBottom: 12,
              }}>
                <AlertTriangle size={12} /> Critical Vulnerabilities Found
              </div>
              <h2 style={{ fontSize: 22, color: '#FFF', fontFamily: "'Cinzel',serif", marginBottom: 8 }}>
                {scan?.issues?.length || 0} issues detected
              </h2>
              {scan?.metrics && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginBottom: 16, fontSize: 12, color: COLORS.textLo }}>
                  <span><b style={{ color: '#FFF' }}>{scan.metrics.lcp_s}s</b> LCP</span>
                  <span><b style={{ color: '#FFF' }}>{scan.metrics.cls}</b> CLS</span>
                  <span><b style={{ color: '#FFF' }}>{scan.metrics.unused_js_kb}KB</b> unused JS</span>
                  <span><b style={{ color: '#FFF' }}>{scan.metrics.schema_errors}</b> schema errors</span>
                </div>
              )}
              <button
                onClick={handleStart}
                disabled={starting || loadingScan}
                data-testid="initiate-repair-btn"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 10,
                  padding: '14px 28px', borderRadius: 12,
                  background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)',
                  color: '#0A0A0F', border: 'none', cursor: 'pointer',
                  fontSize: 14, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                  boxShadow: '0 14px 36px rgba(212,175,55,0.35), 0 0 60px rgba(255,138,61,0.2)',
                  opacity: (starting || loadingScan) ? 0.6 : 1,
                }}>
                {starting ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
                {starting ? 'Starting…' : 'Initiate AUREM Repair'}
              </button>
              <p style={{ fontSize: 11, color: COLORS.textLo, marginTop: 10 }}>
                Takes ~90 seconds · Sentinel-verified · Zero downtime
              </p>
            </div>
          </div>
          {scan?.issues?.length > 0 && (
            <div style={{ marginTop: 26, borderTop: `1px solid ${COLORS.border}`, paddingTop: 20 }}>
              <div style={{ fontSize: 11, color: COLORS.gold, letterSpacing: '0.15em', textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                Issues Detected
              </div>
              {scan.issues.map((it, i) => (
                <div key={i} data-testid={`issue-${i}`} style={{ display: 'flex', alignItems: 'flex-start', padding: '12px 0', borderBottom: i < scan.issues.length - 1 ? '1px solid rgba(212,175,55,0.08)' : 'none' }}>
                  <SeverityDot sev={it.severity} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, color: '#E8E0D0', marginBottom: 2, fontWeight: 500 }}>{it.diagnosis}</div>
                    <div style={{ fontSize: 11, color: COLORS.textLo }}>{it.service} · {it.severity} · fix: {it.proposed_fix}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {isRunning && (
        <div style={{ ...card }} data-testid="repair-running">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <Loader2 className="animate-spin" size={16} style={{ color: job?.current_phase_color || COLORS.orange }} />
            <span style={{ fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', color: job?.current_phase_color || COLORS.orange, fontWeight: 700 }}>{job?.current_phase || 'diagnosing'}</span>
          </div>
          <div style={{ fontSize: 15, color: '#FFF', marginBottom: 16 }}>{job?.current_phase_label || 'Working…'}</div>
          <HeatmapBar pct={job?.progress_pct || 0} color={job?.current_phase_color || COLORS.orange} />
          <div style={{ marginTop: 22, padding: 16, borderRadius: 12, background: 'rgba(5,5,10,0.72)', border: `1px solid ${COLORS.border}`, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, maxHeight: 240, overflowY: 'auto' }}>
            {(job?.events || []).slice().reverse().map((ev, i) => {
              const c = ev.phase === 'diagnosing' ? COLORS.red : ev.phase === 'patching' ? COLORS.orange : ev.phase === 'validating' ? COLORS.yellow : COLORS.green;
              return (
                <div key={i} style={{ color: '#C9C9D1', marginBottom: 4, display: 'flex', gap: 10 }}>
                  <span style={{ color: COLORS.textLo }}>{(ev.at || '').slice(11, 19)}</span>
                  <span style={{ color: c, width: 72 }}>[{(ev.phase || '').toUpperCase()}]</span>
                  <span>{ev.message}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {isDone && (
        <div data-testid="repair-completed">
          <div style={{ ...card }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderRadius: 999, marginBottom: 18, background: 'rgba(34,197,94,0.14)', border: '1px solid rgba(34,197,94,0.35)', color: COLORS.green, fontSize: 11, letterSpacing: '0.15em', textTransform: 'uppercase', fontWeight: 700 }}>
              <CheckCircle2 size={12} /> Repair Complete
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '180px auto 180px', gap: 32, alignItems: 'center' }}>
              <div style={{ textAlign: 'center' }}><ScoreGauge score={job?.score_before} label="Before" size={160} /></div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: "'Cinzel',serif", fontSize: 42, fontWeight: 800, color: COLORS.green }}>+{job?.delta}</div>
                <div style={{ fontSize: 11, color: COLORS.textLo, letterSpacing: '0.18em', textTransform: 'uppercase' }}>Points Gained</div>
                <div style={{ marginTop: 14, display: 'flex', justifyContent: 'center', gap: 6 }}>
                  <TrendingUp size={14} style={{ color: COLORS.green }} />
                  <span style={{ fontSize: 12, color: COLORS.green }}>Sentinel verified</span>
                </div>
              </div>
              <div style={{ textAlign: 'center' }}><ScoreGauge score={job?.score_after} label="After" size={160} /></div>
            </div>
          </div>
        </div>
      )}

      {/* ═════════ 3. SERVICE CATALOG GRID ═════════ */}
      <ServiceCatalogGrid
        catalog={catalog}
        activeServiceIds={activeServiceIds}
        mySubs={mySubs}
        loading={loadingCatalog}
        H={H}
        onRefresh={refreshSubs}
      />

      {/* ═════════ 4. FRIEND SCANNER ═════════ */}
      <FriendScannerCard token={token} H={H} trial={trial} subs={mySubs} />

      {/* ═════════ 5. PIXEL INSTALLER ═════════ */}
      <PixelInstallerCard H={H} />
    </div>
  );
}

// ═════════════════ TRIAL METER CARD ═════════════════

function TrialMeterCard({ trial, subs }) {
  if (!trial) return null;
  const isTrial = trial.state === 'active';
  const hasPaid = (subs?.active_count || 0) > 0;
  const bundleLabel = subs?.bundle?.rule_label;

  return (
    <div data-testid="trial-meter-card" style={{
      ...card,
      background: isTrial
        ? 'linear-gradient(135deg, rgba(34,197,94,0.06) 0%, rgba(212,175,55,0.04) 100%)'
        : (hasPaid ? 'linear-gradient(135deg, rgba(212,175,55,0.1) 0%, rgba(255,138,61,0.04) 100%)' : 'rgba(15,18,28,0.55)'),
      borderColor: isTrial ? 'rgba(34,197,94,0.25)' : (hasPaid ? 'rgba(212,175,55,0.3)' : COLORS.border),
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px', borderRadius: 999,
            background: isTrial ? 'rgba(34,197,94,0.15)' : hasPaid ? 'rgba(212,175,55,0.15)' : 'rgba(107,114,128,0.15)',
            color: isTrial ? COLORS.green : hasPaid ? COLORS.gold : '#6b7280',
            fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', marginBottom: 10,
          }}>
            <Sparkles size={12} />
            {isTrial ? `Power Trial · Day ${7 - trial.days_remaining}/7` : hasPaid ? 'Active Subscription' : 'Forever Free'}
          </div>
          <h2 style={{ fontSize: 20, color: '#FFF', margin: '0 0 8px 0', fontFamily: "'Cinzel',serif" }}>
            {isTrial
              ? `${trial.days_remaining} ${trial.days_remaining === 1 ? 'day' : 'days'} left in your trial`
              : hasPaid
              ? `${subs.active_count} service${subs.active_count !== 1 ? 's' : ''} active · $${(subs.bundle?.final_total ?? subs.base_total ?? 0).toFixed(2)}/mo`
              : 'Upgrade to unlock full AUREM'}
          </h2>
          {isTrial && (
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 11, color: COLORS.textLo, marginBottom: 10 }}>
              <span data-testid="meter-scanner">Scanner: <b style={{ color: '#FFF' }}>{trial.scanner_used}/{trial.scanner_quota}</b></span>
              <span data-testid="meter-friend">Friend scans: <b style={{ color: '#FFF' }}>{trial.friend_scans_used}/{trial.friend_scans_quota}</b></span>
              <span data-testid="meter-ora">ORA messages: <b style={{ color: '#FFF' }}>{trial.ora_msgs_used}/{trial.ora_msgs_quota}</b></span>
            </div>
          )}
          {bundleLabel && (
            <div style={{ display: 'inline-block', padding: '6px 12px', background: 'rgba(34,197,94,0.14)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 8, color: COLORS.green, fontSize: 11, fontWeight: 700 }}>
              🎉 {bundleLabel} — saving ${(subs.bundle.discount_amount || 0).toFixed(2)}/mo
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═════════════════ SERVICE CATALOG GRID ═════════════════

function ServiceCatalogGrid({ catalog, activeServiceIds, mySubs, loading, H, onRefresh }) {
  const [subscribing, setSubscribing] = useState(null);

  if (loading) return <div style={card}><Loader2 className="animate-spin" size={24} style={{ color: COLORS.gold, margin: '10px auto', display: 'block' }} /></div>;
  if (!catalog?.services?.length) return null;

  const bySlot = {};
  for (const s of catalog.services) (bySlot[s.cluster] = bySlot[s.cluster] || []).push(s);

  const subscribe = async (svc) => {
    setSubscribing(svc.service_id);
    try {
      const res = await fetch(`${API}/api/customer/subscriptions/subscribe`, {
        method: 'POST', headers: H,
        body: JSON.stringify({ service_id: svc.service_id, origin_url: window.location.origin }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Subscribe failed'); }
      const { url } = await res.json();
      if (url) window.location.href = url;
    } catch (e) { alert(e.message); setSubscribing(null); }
  };

  const cancel = async (svc) => {
    if (!window.confirm(`Cancel ${svc.name}?`)) return;
    try {
      await fetch(`${API}/api/customer/subscriptions/cancel`, {
        method: 'POST', headers: H,
        body: JSON.stringify({ service_id: svc.service_id }),
      });
      await onRefresh();
    } catch (e) { alert(e.message); }
  };

  return (
    <div data-testid="service-catalog-grid" style={{ ...card }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <h2 style={{ fontSize: 16, color: COLORS.gold, fontFamily: "'Cinzel',serif", margin: 0, letterSpacing: '0.04em' }}>
          ⚡ Boost Your Site
        </h2>
        <span style={{ fontSize: 11, color: COLORS.textLo }}>
          Subscribe à la carte · Pick 3+ save 15%
        </span>
      </div>

      {Object.keys(bySlot).sort((a, b) => {
        const order = { repair: 1, security: 2, crm: 3, marketing: 4, power: 5 };
        return (order[a] || 9) - (order[b] || 9);
      }).map(cluster => {
        const Icon = CLUSTER_ICONS[cluster] || Wrench;
        const color = CLUSTER_COLORS[cluster] || COLORS.gold;
        return (
          <div key={cluster} style={{ marginBottom: 18 }} data-testid={`cluster-section-${cluster}`}>
            <div style={{ fontSize: 10, color, letterSpacing: '0.2em', textTransform: 'uppercase', fontWeight: 700, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon size={12} /> {cluster.replace('_', ' ')}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
              {bySlot[cluster].map(svc => {
                const isActive = activeServiceIds.has(svc.service_id);
                const isSubscribing = subscribing === svc.service_id;
                return (
                  <div key={svc.service_id} data-testid={`svc-card-${svc.service_id}`} style={{
                    position: 'relative', padding: 14, borderRadius: 12,
                    background: isActive ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${isActive ? 'rgba(34,197,94,0.3)' : 'rgba(212,175,55,0.1)'}`,
                    opacity: svc.status === 'disabled' ? 0.4 : 1,
                  }}>
                    {isActive && (
                      <div style={{ position: 'absolute', top: 10, right: 10, padding: '3px 7px', borderRadius: 6, background: 'rgba(34,197,94,0.2)', color: COLORS.green, fontSize: 9, fontWeight: 800, letterSpacing: '0.1em' }}>
                        ACTIVE ✓
                      </div>
                    )}
                    {!isActive && svc.service_id && svc.service_id.startsWith('site_monitor') && (
                      <div style={{ position: 'absolute', top: 10, right: 10, padding: '3px 7px', borderRadius: 6, background: 'linear-gradient(90deg,#06b6d4,#0891b2)', color: '#fff', fontSize: 9, fontWeight: 800, letterSpacing: '0.12em', boxShadow: '0 4px 12px rgba(6,182,212,0.35)' }}>
                        ✨ NEW
                      </div>
                    )}
                    {/* Iter 320.4 — Beta badge for partial-rollout services. Tooltip on hover. */}
                    {!isActive && svc.maturity === 'beta' && !svc.service_id.startsWith('site_monitor') && (
                      <div
                        title={svc.badge_tooltip || 'Full feature rollout in progress — core functionality active.'}
                        data-testid={`svc-badge-beta-${svc.service_id}`}
                        style={{ position: 'absolute', top: 10, right: 10, padding: '3px 7px', borderRadius: 6, background: 'rgba(212,175,55,0.18)', color: COLORS.gold, fontSize: 9, fontWeight: 800, letterSpacing: '0.12em', border: '1px solid rgba(212,175,55,0.4)', cursor: 'help' }}>
                        {svc.badge || 'BETA'}
                      </div>
                    )}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      {!isActive && <Lock size={11} style={{ color: COLORS.textLo }} />}
                      <span style={{ fontSize: 13, color: '#FFF', fontWeight: 700 }}>{svc.name}</span>
                    </div>
                    <p style={{ fontSize: 11, color: COLORS.textLo, margin: '0 0 10px 0', lineHeight: 1.5 }}>
                      {svc.description}
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <span style={{ fontSize: 15, color: COLORS.gold, fontWeight: 800, fontFamily: "'Cinzel',serif" }}>
                          ${(svc.price_monthly || 0).toFixed(0)}
                        </span>
                        <span style={{ fontSize: 10, color: COLORS.textLo, marginLeft: 4 }}>{svc.unit_label || '/mo'}</span>
                      </div>
                      <button
                        onClick={() => isActive ? cancel(svc) : subscribe(svc)}
                        disabled={isSubscribing || svc.status === 'disabled'}
                        data-testid={`svc-btn-${svc.service_id}`}
                        style={{
                          padding: '6px 12px', borderRadius: 8, fontSize: 10, fontWeight: 700,
                          letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer',
                          background: isActive
                            ? 'rgba(239,68,68,0.1)'
                            : 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)',
                          color: isActive ? COLORS.red : '#0A0A0F',
                          border: isActive ? '1px solid rgba(239,68,68,0.3)' : 'none',
                          opacity: (isSubscribing || svc.status === 'disabled') ? 0.5 : 1,
                        }}>
                        {isSubscribing ? <Loader2 className="animate-spin" size={10} /> : isActive ? 'Cancel' : 'Unlock'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ═════════════════ FRIEND SCANNER ═════════════════

function FriendScannerCard({ token, H, trial, subs }) {
  const [url, setUrl] = useState('');
  const [friendName, setFriendName] = useState('');
  const [friendEmail, setFriendEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [savedToast, setSavedToast] = useState(null); // iter 279 — UX feedback

  const hasPaid = (subs?.active_count || 0) > 0;
  const quotaLeft = hasPaid ? Infinity : Math.max(0, (trial?.friend_scans_quota || 0) - (trial?.friend_scans_used || 0));

  const doScan = async () => {
    if (!url) return;
    setSubmitting(true);
    setResult(null);
    try {
      const res = await fetch(`${API}/api/customer/friend-scan`, {
        method: 'POST', headers: H,
        body: JSON.stringify({
          friend_website: url,
          friend_name: friendName || null,
          friend_email: friendEmail || null,
        }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Scan failed'); }
      const data = await res.json();
      setResult(data);
      // iter 279 — green "Saved" toast so client knows DB wrote successfully
      setSavedToast({
        kind: 'success',
        msg: `Saved · scan ${data?.scan?.scan_id || ''} · share link ready`,
      });
      setTimeout(() => setSavedToast(null), 3500);
    } catch (e) {
      setSavedToast({ kind: 'error', msg: e.message || 'Save failed' });
      setTimeout(() => setSavedToast(null), 4000);
    } finally { setSubmitting(false); }
  };

  const shareUrl = result ? `${window.location.origin}/report/${result.referral_slug}` : '';

  const copyShare = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div data-testid="friend-scanner-card" style={{ ...card, position: 'relative' }}>
      {/* iter 279 — "Saved" toast for UX trust feedback */}
      {savedToast ? (
        <div
          data-testid="friend-scan-saved-toast"
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            padding: '8px 14px',
            borderRadius: 10,
            background: savedToast.kind === 'success'
              ? 'rgba(34,197,94,0.15)'
              : 'rgba(239,68,68,0.15)',
            border: `1px solid ${savedToast.kind === 'success' ? '#22C55E' : '#EF4444'}`,
            color: savedToast.kind === 'success' ? '#86EFAC' : '#FCA5A5',
            fontSize: 12,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            boxShadow: '0 6px 18px rgba(0,0,0,0.35)',
            zIndex: 5,
            animation: 'fadeInSlideDown 0.3s ease-out',
          }}
        >
          <span>{savedToast.kind === 'success' ? '✅' : '⚠️'}</span>
          {savedToast.msg}
        </div>
      ) : null}
      <style>{`
        @keyframes fadeInSlideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Gift size={18} style={{ color: COLORS.gold }} />
        <h2 style={{ fontSize: 16, color: '#FFF', margin: 0, fontFamily: "'Cinzel',serif" }}>
          Scan a Friend's Website
        </h2>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: COLORS.textLo, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          {hasPaid ? 'UNLIMITED' : `${quotaLeft} scans left this week`}
        </span>
      </div>
      <p style={{ fontSize: 12, color: COLORS.textLo, marginTop: 0, marginBottom: 14 }}>
        Scan any website. Share the report via WhatsApp/email. When your friend signs up + subscribes, you earn <b style={{ color: COLORS.gold }}>$20 credit</b>.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: 8, marginBottom: 10 }}>
        <input
          data-testid="friend-url-input"
          placeholder="https://friendsite.com"
          value={url}
          onChange={e => setUrl(e.target.value)}
          style={{ padding: 10, borderRadius: 8, background: 'rgba(0,0,0,0.3)', border: `1px solid ${COLORS.border}`, color: '#FFF', fontSize: 12 }}
        />
        <input
          data-testid="friend-name-input"
          placeholder="Friend's name (optional)"
          value={friendName}
          onChange={e => setFriendName(e.target.value)}
          style={{ padding: 10, borderRadius: 8, background: 'rgba(0,0,0,0.3)', border: `1px solid ${COLORS.border}`, color: '#FFF', fontSize: 12 }}
        />
        <input
          data-testid="friend-email-input"
          placeholder="Email (optional)"
          value={friendEmail}
          onChange={e => setFriendEmail(e.target.value)}
          style={{ padding: 10, borderRadius: 8, background: 'rgba(0,0,0,0.3)', border: `1px solid ${COLORS.border}`, color: '#FFF', fontSize: 12 }}
        />
        <button
          onClick={doScan}
          disabled={submitting || !url || quotaLeft === 0}
          data-testid="friend-scan-btn"
          style={{
            padding: '10px 18px', borderRadius: 8,
            background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)',
            color: '#0A0A0F', border: 'none', cursor: 'pointer',
            fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
            opacity: (submitting || !url || quotaLeft === 0) ? 0.5 : 1,
          }}>
          {submitting ? <Loader2 className="animate-spin" size={12} /> : 'Scan'}
        </button>
      </div>
      {result && (
        <div data-testid="friend-scan-result" style={{ marginTop: 14, padding: 14, borderRadius: 10, background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.25)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: '#FFF', fontWeight: 700, marginBottom: 4 }}>
                Scan ready! {result.scan.friend_website}
              </div>
              <div style={{ fontSize: 11, color: COLORS.textLo }}>
                Score: <b style={{ color: scoreColor(result.scan.score) }}>{result.scan.score}/100</b> · {result.scan.issues_count} issues found
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={copyShare} data-testid="copy-share-btn" style={{ padding: '7px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.06)', color: COLORS.gold, border: '1px solid rgba(212,175,55,0.3)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}>
                <Copy size={10} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                {copied ? 'Copied' : 'Copy link'}
              </button>
              <a href={`https://wa.me/?text=${encodeURIComponent(`Check your site score: ${shareUrl}`)}`} target="_blank" rel="noreferrer" data-testid="share-whatsapp-btn" style={{ padding: '7px 12px', borderRadius: 8, background: 'rgba(34,197,94,0.14)', color: COLORS.green, border: '1px solid rgba(34,197,94,0.3)', fontSize: 10, fontWeight: 700, textDecoration: 'none' }}>
                <Share2 size={10} style={{ verticalAlign: '-1px', marginRight: 4 }} /> WhatsApp
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═════════════════ PIXEL INSTALLER ═════════════════

function PixelInstallerCard({ H }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/customer/pixel/install`, { headers: H });
        if (r.ok) setData(await r.json());
      } catch (e) {} finally { setLoading(false); }
    })();
  }, [H]);

  if (loading) return <div style={card}><Loader2 className="animate-spin" size={20} style={{ color: COLORS.gold, margin: '10px auto', display: 'block' }} /></div>;
  if (!data) return null;

  const step = data.progress?.step ?? 0;
  const copySnippet = () => { navigator.clipboard.writeText(data.snippet || ''); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div data-testid="pixel-installer-card" style={{ ...card, marginBottom: 40 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Activity size={18} style={{ color: COLORS.gold }} />
        <h2 style={{ fontSize: 16, color: '#FFF', margin: 0, fontFamily: "'Cinzel',serif" }}>Install AUREM Pixel</h2>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: step === 4 ? COLORS.green : COLORS.orange, letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 700 }}>
          Step {step}/4 · {data.progress?.label}
        </span>
      </div>
      {/* Progress bar */}
      <div style={{ height: 6, background: 'rgba(0,0,0,0.3)', borderRadius: 3, marginBottom: 16, overflow: 'hidden' }}>
        <div style={{
          width: `${(step / 4) * 100}%`, height: '100%',
          background: 'linear-gradient(90deg, #FF8A3D 0%, #D4AF37 50%, #22C55E 100%)',
          transition: 'width 0.6s',
        }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
        {(data.methods || []).map(m => (
          <div key={m.id} data-testid={`install-method-${m.id}`} style={{
            padding: 14, borderRadius: 12, cursor: m.ready ? 'pointer' : 'default',
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(212,175,55,0.1)',
            opacity: m.ready ? 1 : 0.5,
          }}
          onClick={() => m.ready && setExpanded(expanded === m.id ? null : m.id)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: '#FFF', fontWeight: 700 }}>{m.name}</span>
              {!m.ready && <span style={{ fontSize: 9, color: COLORS.textLo, letterSpacing: '0.12em' }}>SOON</span>}
            </div>
            <p style={{ fontSize: 10, color: COLORS.textLo, margin: 0, lineHeight: 1.5 }}>{m.description}</p>
            {expanded === m.id && m.id === 'manual' && (
              <div style={{ marginTop: 10 }}>
                <code style={{ display: 'block', padding: 8, background: 'rgba(0,0,0,0.5)', borderRadius: 6, fontSize: 10, color: '#C9C9D1', fontFamily: "'JetBrains Mono',monospace", whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {data.snippet}
                </code>
                <button onClick={(e) => { e.stopPropagation(); copySnippet(); }} data-testid="copy-snippet-btn" style={{ marginTop: 8, padding: '5px 10px', borderRadius: 6, background: 'rgba(212,175,55,0.1)', color: COLORS.gold, border: '1px solid rgba(212,175,55,0.3)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}>
                  <Copy size={9} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                  {copied ? 'Copied' : 'Copy snippet'}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
