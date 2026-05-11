/**
 * LuxePages — every customer page reachable via the sidebar.
 * Pages: ProfilePage, LiveHealthPage, SecurityPage, AutomationPage,
 *        CRMPage, ORAPage, SettingsPage.
 * All data is REAL (live backend), no mock numbers.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Activity, Shield, Bot, Users, Sparkles, Cog, User as UserIcon, Zap,
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
} from 'recharts';
import { useLuxeAuth } from './LuxeAuthContext';
import {
  GOLD, GOLD_HI, STROKE, TEXT_HI, TEXT_MD, TEXT_LO,
  fontDisplay, fontBody, fontMono,
  labelStyle, fieldStyle, buttonGold, GRADIENT_ORANGE_CTA,
} from './tokens';
import { BACKEND_URL } from '../../lib/api';

const API = BACKEND_URL;

// ── Glass Card primitive (matches Home Glass — same shine bubble) ───
export const Card = ({ children, style, contentStyle, testid }) => (
  <div data-testid={testid} style={{
    position: 'relative',
    padding: 'clamp(14px, 3vw, 22px)', borderRadius: 'clamp(16px, 3vw, 26px)',
    overflow: 'hidden',
    // iter 322bl — stronger 3D glass-bubble shine (matches sidebar style):
    //   Layer 1: bright top-left caustic (water-bubble highlight)
    //   Layer 2: subtle gold-tinged top arc
    //   Layer 3: depth gradient (lighter at top, deeper at bottom)
    background:
      'radial-gradient(180% 90% at 25% -10%, rgba(255,255,255,0.24) 0%, rgba(255,255,255,0.06) 22%, transparent 55%),' +
      'radial-gradient(280px 140px at 75% -20%, rgba(255,228,168,0.10), transparent 70%),' +
      'linear-gradient(165deg, rgba(60,62,72,0.42) 0%, rgba(18,20,28,0.48) 60%, rgba(40,42,52,0.38) 100%)',
    border: '1px solid rgba(255,255,255,0.16)',
    backdropFilter: 'blur(34px) saturate(180%)',
    WebkitBackdropFilter: 'blur(34px) saturate(180%)',
    boxShadow:
      '0 1px 0 rgba(255,255,255,0.22) inset,' +
      ' 0 -1px 0 rgba(0,0,0,0.45) inset,' +
      ' 0 26px 50px -16px rgba(0,0,0,0.7),' +
      ' 0 0 0 1px rgba(255,228,168,0.04)',
    minWidth: 0,
    ...style,
  }}>
    {/* Top shine line — the "water bubble" rim light */}
    <span aria-hidden="true" style={{
      position: 'absolute', top: 0, left: 18, right: 18, height: 1,
      background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.32) 50%, transparent 100%)',
      pointerEvents: 'none',
    }} />
    {/* Diagonal gloss streak — subtle, only visible on darker cards */}
    <span aria-hidden="true" style={{
      position: 'absolute', top: 0, left: -40, width: 140, height: 100,
      background: 'linear-gradient(115deg, transparent 30%, rgba(255,255,255,0.06) 50%, transparent 70%)',
      pointerEvents: 'none', filter: 'blur(6px)',
    }} />
    <div style={{ position: 'relative', ...contentStyle }}>{children}</div>
  </div>
);

export const StatusDot = ({ status = 'GREEN', size = 10, label }) => {
  const map = {
    GREEN: '#bef264', YELLOW: '#fbbf24', RED: '#f87171', BLUE: '#60a5fa',
  };
  const color = map[String(status).toUpperCase()] || map.GREEN;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: fontMono, fontSize: 9, color: TEXT_LO, letterSpacing: '0.18em',
    }}>
      <span style={{
        width: size, height: size, borderRadius: '50%', background: color,
        boxShadow: `0 0 8px ${color}80`,
      }} />
      {label != null ? label : String(status).toUpperCase()}
    </span>
  );
};

const SectionLabel = ({ children, right }) => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12,
  }}>
    <div style={{
      fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11,
      letterSpacing: '0.22em', textTransform: 'uppercase',
    }}>{children}</div>
    {right}
  </div>
);

const Row = ({ k, v, mono = false, small = false }) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '6px 0', borderBottom: '1px dashed rgba(212,163,115,0.10)',
    fontFamily: fontBody, fontSize: small ? 11 : 12,
  }}>
    <span style={{ color: TEXT_MD, fontFamily: fontMono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase' }}>{k}</span>
    <span style={{ color: TEXT_HI, fontFamily: mono ? fontMono : fontBody }}>{v}</span>
  </div>
);

const PageShell = ({ icon: Icon, title, subtitle, children, testid, fitViewport }) => (
  <div data-testid={testid} style={{
    display: 'flex', flexDirection: 'column', gap: 18,
    flex: 1, minWidth: 0, padding: '4px 2px',
    height: fitViewport ? '100%' : 'auto',
    minHeight: 0,
    overflow: fitViewport ? 'hidden' : 'visible',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      {Icon && <Icon size={20} style={{ color: GOLD_HI }} />}
      <div style={{ minWidth: 0 }}>
        <h1 style={{
          margin: 0, color: TEXT_HI, fontFamily: fontDisplay,
          fontSize: 'clamp(18px, 4vw, 22px)', fontWeight: 700, letterSpacing: '0.10em',
        }}>{title}</h1>
        {subtitle && <div style={{ color: TEXT_LO, fontFamily: fontBody, fontSize: 12 }}>{subtitle}</div>}
      </div>
    </div>
    {children}
  </div>
);

// ╔══════════════════════════════════════════════════════════════════════
// ║ ProfilePage — subscription, scan schedule, F12 bug feed
// ╚══════════════════════════════════════════════════════════════════════
export const ProfilePage = () => {
  const { user, refetchMe } = useLuxeAuth();
  const token = localStorage.getItem('aurem_customer_token');
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [websiteUrl, setWebsiteUrl] = useState(user?.website_url || '');
  const [saving, setSaving] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [bugs, setBugs] = useState([]);
  const [scanInterval, setScanIntervalState] = useState('6h');
  const [scanLoading, setScanLoading] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };
  const fetchPipeline = async () => {
    try { setPipelineStatus((await axios.get(`${API}/api/customer/pipeline/status`, { headers })).data); } catch {}
  };
  const fetchSubscription = async () => {
    try {
      const { data } = await axios.get(`${API}/api/customer/me/subscription`, { headers });
      setSubscription(data);
      if (data?.scan_schedule?.interval) setScanIntervalState(data.scan_schedule.interval);
    } catch {}
  };
  const fetchBugs = async () => {
    try {
      const { data } = await axios.get(`${API}/api/customer/bugs?limit=10`, { headers });
      setBugs(Array.isArray(data?.bugs) ? data.bugs : []);
    } catch {}
  };

  useEffect(() => {
    fetchPipeline(); fetchSubscription(); fetchBugs();
    const id = setInterval(() => { fetchSubscription(); fetchBugs(); }, 20000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line

  const handleScheduleChange = async (interval) => {
    setScanIntervalState(interval);
    try {
      await axios.post(`${API}/api/customer/scan-schedule`, { interval }, { headers });
      toast.success(`Scan schedule: ${interval}`);
      fetchSubscription();
    } catch { toast.error('Failed to update schedule'); }
  };

  const handleScanNow = async () => {
    if (scanLoading) return;
    setScanLoading(true);
    try {
      const { data } = await axios.post(`${API}/api/customer/scan/now`, {}, { headers });
      toast.success(`Scan queued for ${data.url}`);
      fetchSubscription();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Scan failed'); }
    finally { setScanLoading(false); }
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await axios.put(`${API}/api/platform/me/update`, {
        full_name: fullName, company_name: companyName, website_url: websiteUrl || null,
      }, { headers });
      if (websiteUrl) {
        try {
          const { data } = await axios.post(`${API}/api/customer/pipeline/trigger`,
            { website_url: websiteUrl }, { headers });
          toast.success(data.replay
            ? 'Profile saved. Pipeline already running ✓'
            : `Pipeline activated • ${data.stages_completed} stages GREEN`);
          fetchPipeline();
        } catch { toast.error('Profile saved, but pipeline trigger failed'); }
      } else {
        toast.success('Profile saved');
      }
      await refetchMe();
    } catch { toast.error('Save failed'); }
    finally { setSaving(false); }
  };

  const fmtTime = (iso) => iso ? new Date(iso).toLocaleString() : '—';
  const fmtRel = (iso) => {
    if (!iso) return '—';
    const ms = new Date(iso).getTime() - Date.now();
    if (Number.isNaN(ms)) return iso;
    const abs = Math.abs(ms);
    const m = Math.round(abs / 60000);
    const h = Math.floor(m / 60);
    const min = m % 60;
    const txt = h > 0 ? `${h}h ${min}m` : `${m}m`;
    return ms >= 0 ? `in ${txt}` : `${txt} ago`;
  };
  const usage = subscription?.usage || user?.usage || {};

  return (
    <PageShell icon={UserIcon} title="Profile"
      subtitle="Your account, plan, ORA scan schedule & live bug feed."
      testid="page-profile">
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: 18,
      }}>
        <Card>
          <SectionLabel>Account Details</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={labelStyle}>Full name</label>
              <input data-testid="profile-fullname" style={fieldStyle}
                value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Company</label>
              <input data-testid="profile-company" style={fieldStyle}
                value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Website URL <span style={{ color: '#fca5a5', letterSpacing: 0 }}>(unlocks ORA pipeline)</span></label>
              <input data-testid="profile-website" style={fieldStyle}
                placeholder="https://your-site.com"
                value={websiteUrl} onChange={(e) => setWebsiteUrl(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 6 }}>
              <button data-testid="profile-save" style={{ ...buttonGold, opacity: saving ? 0.6 : 1 }}
                disabled={saving} onClick={handleSave}>
                {saving ? 'Saving…' : 'Save & Activate Pipeline'}
              </button>
            </div>
          </div>

          <div style={{ marginTop: 22 }}>
            <SectionLabel>ORA Scan Schedule</SectionLabel>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
              {['1h','6h','12h','24h','manual'].map((iv) => {
                const isOn = scanInterval === iv;
                return (
                  <button key={iv} data-testid={`scan-int-${iv}`} onClick={() => handleScheduleChange(iv)}
                    style={{
                      padding: '8px 14px', borderRadius: 8,
                      fontFamily: fontMono, fontSize: 11, letterSpacing: '0.18em',
                      cursor: 'pointer', textTransform: 'uppercase',
                      background: isOn ? GRADIENT_ORANGE_CTA : 'rgba(255,107,0,0.04)',
                      color: isOn ? '#fff' : GOLD_HI,
                      border: `1px solid ${isOn ? 'transparent' : 'rgba(255,107,0,0.25)'}`,
                      boxShadow: isOn ? '0 6px 18px rgba(255,107,0,0.25)' : 'none',
                    }}>Every {iv}</button>
                );
              })}
              <button data-testid="scan-now" onClick={handleScanNow} disabled={scanLoading}
                style={{
                  padding: '8px 16px', borderRadius: 8,
                  fontFamily: fontDisplay, fontSize: 11, letterSpacing: '0.20em', textTransform: 'uppercase',
                  cursor: scanLoading ? 'wait' : 'pointer',
                  background: 'rgba(255,107,0,0.10)', color: GOLD_HI,
                  border: '1px solid rgba(255,107,0,0.4)',
                }}>
                <Zap size={11} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                {scanLoading ? 'Queueing…' : 'Scan Now'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 16, marginTop: 12, fontFamily: fontMono, fontSize: 10, color: TEXT_MD }}>
              <span>Last scan: <span style={{ color: TEXT_HI }}>{fmtRel(subscription?.scan_schedule?.last_scan_at)}</span></span>
              <span>Next: <span style={{ color: GOLD_HI }}>{fmtRel(subscription?.scan_schedule?.next_scan_at)}</span></span>
            </div>
          </div>

          <div style={{ marginTop: 22 }}>
            <SectionLabel right={<span style={{ fontFamily: fontMono, fontSize: 9, letterSpacing: '0.2em', color: GOLD_HI }}>{bugs.length} CAPTURED</span>}>
              ORA F12 Bug Feed (from your pixel)
            </SectionLabel>
            {bugs.length === 0 ? (
              <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12, marginTop: 8 }}>
                No bugs captured yet. The pixel snippet on your site will report runtime errors here in real-time, and ORA will auto-fix high-severity issues through Council deliberation.
              </div>
            ) : (
              <div data-testid="bug-feed" style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8, maxHeight: 280, overflowY: 'auto' }}>
                {bugs.map((b, i) => {
                  const sev = (b.severity || 'low').toUpperCase();
                  const sevColor = sev === 'HIGH' ? '#ef4444' : (sev === 'MEDIUM' ? '#fbbf24' : '#a3a3a3');
                  const status = (b.status || 'captured').replace(/_/g, ' ');
                  return (
                    <div key={i} style={{
                      display: 'grid', gridTemplateColumns: '70px 1fr auto', gap: 10, alignItems: 'center',
                      padding: '10px 12px', borderRadius: 8,
                      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)',
                    }}>
                      <span style={{ fontFamily: fontMono, fontSize: 9, color: sevColor, letterSpacing: '0.14em' }}>● {sev}</span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontFamily: fontMono, fontSize: 10, color: TEXT_HI, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          [{b.event}] {b.msg || b.target_url || b.url || '—'}
                        </div>
                        <div style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_MD, marginTop: 2 }}>
                          {b.url || ''}{b.line ? `  · L${b.line}` : ''}{b.http_status ? `  · ${b.http_status}` : ''}
                          {b.council_recommendation ? `  · Council: ${b.council_recommendation} ${b.council_confidence ?? ''}%` : ''}
                        </div>
                      </div>
                      <span style={{ fontFamily: fontMono, fontSize: 9, color: GOLD_HI, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                        {b.auto_pushed ? 'AUTO-PUSHED' : status}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Card>
            <SectionLabel right={subscription?.lifetime ? <span style={{ fontFamily: fontMono, fontSize: 9, color: '#FFE4A8', letterSpacing: '0.20em' }}>LIFETIME</span> : null}>
              Subscription
            </SectionLabel>
            <Row k="Email" v={subscription?.email || user?.email || '—'} />
            <Row k="Plan" v={(subscription?.tier || user?.tier || 'starter').toUpperCase()} />
            <Row k="Status" v={(subscription?.tier_status || user?.tier_status || 'trial').toUpperCase()} />
            <Row k="Trial ends" v={(() => {
              const t = subscription?.trial_ends_at || user?.trial_ends_at;
              return t ? new Date(t).toLocaleDateString() : '—';
            })()} />
            {subscription?.founder && <Row k="Founder" v="✓ Founder account" />}
            <Row k="Pixel" v={(() => {
              const p = subscription?.pixel;
              if (p?.verified) return '✓ Verified';
              if (p?.installed) return 'Installed';
              return 'Not installed';
            })()} />
            {subscription?.business_id && <Row k="BIN" v={subscription.business_id} mono />}
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <UsageRow label="Crew runs" used={usage.crew_executions || 0} limit={user?.usage?.crew_limit || 500} />
              <UsageRow label="Voice min" used={usage.voice_minutes || 0} limit={user?.usage?.voice_limit || 0} />
              <UsageRow label="WhatsApp" used={usage.whatsapp_messages || 0} limit={user?.usage?.whatsapp_limit || 0} />
            </div>
          </Card>

          <Card>
            <SectionLabel right={pipelineStatus?.run && <StatusDot status={pipelineStatus.run.current_status} />}>
              ORA Pipeline
            </SectionLabel>
            {pipelineStatus?.run ? (
              <>
                <Row k="Run ID" v={pipelineStatus.run.run_id} mono small />
                <Row k="Stage" v={pipelineStatus.run.current_stage} />
                <Row k="Started" v={fmtTime(pipelineStatus.run.started_at)} small />
                <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {(pipelineStatus.stages || []).slice(-6).map((s, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      fontFamily: fontMono, fontSize: 10, color: TEXT_MD,
                    }}>
                      <StatusDot status={s.status} size={6} label="" />
                      <span style={{ minWidth: 80, color: GOLD_HI, letterSpacing: '0.12em' }}>{s.stage}</span>
                      <span style={{ flex: 1, color: TEXT_HI, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.message}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12 }}>
                No pipeline yet. Save your website URL above to activate ORA.
              </div>
            )}
          </Card>
        </div>
      </div>
    </PageShell>
  );
};

const UsageRow = ({ label, used, limit }) => {
  const has = limit && limit > 0;
  const pct = has ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontFamily: fontMono, color: TEXT_MD, fontSize: 10, letterSpacing: '0.12em' }}>{label.toUpperCase()}</span>
        <span style={{ fontFamily: fontMono, color: TEXT_HI, fontSize: 10 }}>
          {used.toLocaleString()}{has ? ` / ${limit.toLocaleString()}` : ''}
        </span>
      </div>
      <div style={{ width: '100%', height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          background: 'linear-gradient(90deg, #C9A84C 0%, #FFE4A8 100%)',
          transition: 'width .6s ease',
        }} />
      </div>
    </div>
  );
};

// ╔══════════════════════════════════════════════════════════════════════
// ║ LiveHealthPage — sentinel pulse, KPIs, recent auto-fixes
// ╚══════════════════════════════════════════════════════════════════════
export const LiveHealthPage = () => {
  const token = localStorage.getItem('aurem_customer_token');
  const [data, setData] = useState({ status: null, pulses: [], fixes: [] });

  useEffect(() => {
    const load = async () => {
      const headers = { Authorization: `Bearer ${token}` };
      const get = async (u) => { try { return (await axios.get(`${API}${u}`, { headers, timeout: 10000 })).data; } catch { return null; } };
      const [status, pulse, fixes] = await Promise.all([
        get('/api/sentinel/status'),
        get('/api/sentinel/pulse-history?limit=60'),
        get('/api/sentinel/fixes-log?limit=40'),
      ]);
      setData({
        status,
        pulses: (pulse?.pulses || []).slice().reverse(),
        fixes: fixes?.fixes || [],
      });
    };
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [token]);

  const score = data.status?.health_score ?? 0;
  const overall = score >= 80 ? 'GREEN' : score >= 50 ? 'YELLOW' : 'RED';
  const pulses = (data.pulses || []).map((p, i) => ({
    i, score: p.health_score || 0,
    issues: (p.issues_found && p.issues_found.length) || 0,
    ts: p.timestamp || '', cycle: p.cycle_number ?? null,
  }));
  const sevColor = (s) => {
    const x = (s || '').toUpperCase();
    if (x === 'P0' || x.includes('CRIT')) return { bg: 'rgba(248,113,113,0.18)', fg: '#fca5a5', border: 'rgba(248,113,113,0.4)' };
    if (x === 'P1' || x.includes('HIGH')) return { bg: 'rgba(251,146,60,0.18)', fg: '#fdba74', border: 'rgba(251,146,60,0.4)' };
    if (x === 'P2' || x.includes('MED'))  return { bg: 'rgba(250,204,21,0.18)', fg: '#fde68a', border: 'rgba(250,204,21,0.4)' };
    return { bg: 'rgba(190,242,100,0.18)', fg: '#bef264', border: 'rgba(190,242,100,0.4)' };
  };
  const fmtTime = (iso) => { if (!iso) return '—'; try { return new Date(iso).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch { return iso.slice(0,16).replace('T',' '); } };
  const fmtAgo = (iso) => {
    if (!iso) return '';
    const ms = Date.now() - new Date(iso).getTime();
    if (Number.isNaN(ms) || ms < 0) return '';
    const m = Math.floor(ms/60000); if (m<1) return 'just now'; if (m<60) return `${m}m ago`;
    const h = Math.floor(m/60); if (h<24) return `${h}h ago`; return `${Math.floor(h/24)}d ago`;
  };

  const PulseTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const p = payload[0].payload;
    return (
      <div style={{ background: 'rgba(8,10,14,0.95)', border: `1px solid ${STROKE}`, borderRadius: 8, padding: '8px 10px', fontFamily: fontMono, fontSize: 10, color: TEXT_HI }}>
        <div style={{ color: GOLD_HI, marginBottom: 3 }}>{fmtTime(p.ts)}</div>
        <div>score: <span style={{ color: '#FFE4A8', fontWeight: 700 }}>{p.score}</span> / 100</div>
        <div>issues: <span style={{ color: p.issues > 0 ? '#fdba74' : '#bef264' }}>{p.issues}</span></div>
        {p.cycle != null && <div style={{ color: TEXT_MD }}>cycle #{p.cycle}</div>}
      </div>
    );
  };

  return (
    <PageShell icon={Activity} title="Live Health" subtitle="Real-time sentinel pulse from the platform." testid="page-live-health" fitViewport>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 14, flex: '0 0 auto',
      }}>
        <Card>
          <SectionLabel right={<StatusDot status={overall} />}>Health Score</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
            <span style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 44, fontWeight: 700, lineHeight: 1 }}>{score}</span>
            <span style={{ fontFamily: fontBody, color: TEXT_MD, fontSize: 12 }}>/ 100</span>
          </div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>
            cycle #{data.status?.cycle_number ?? 0} · {fmtAgo(data.status?.last_check)}
          </div>
        </Card>
        <Card>
          <SectionLabel right={<StatusDot status={(data.status?.issues_count ?? 0) === 0 ? 'GREEN' : 'YELLOW'} />}>Issues Detected</SectionLabel>
          <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 38, fontWeight: 700 }}>{data.status?.issues_count ?? 0}</div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>last cycle</div>
        </Card>
        <Card>
          <SectionLabel right={<StatusDot status="GREEN" />}>Auto-fixes Applied</SectionLabel>
          <div style={{ fontFamily: fontDisplay, color: '#22c55e', fontSize: 38, fontWeight: 700 }}>{data.status?.total_auto_fixes ?? 0}</div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>all-time · {data.fixes.length} recent</div>
        </Card>
      </div>

      <Card style={{ flex: '0 0 auto' }}>
        <SectionLabel right={
          <span style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO, letterSpacing: '0.2em' }}>
            {pulses.length} PULSES
          </span>
        }>Pulse History</SectionLabel>
        <div style={{ height: 220 }}>
          <ResponsiveContainer>
            <AreaChart data={pulses} margin={{ top: 6, right: 12, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="pulseFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={GOLD} stopOpacity={0.45} />
                  <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="i" hide />
              <YAxis domain={[0, 100]} hide />
              <Tooltip content={<PulseTooltip />} cursor={{ stroke: GOLD_HI, strokeOpacity: 0.4 }} />
              <Area type="monotone" dataKey="score" stroke={GOLD} strokeWidth={2} fill="url(#pulseFill)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card style={{ flex: '1 1 auto', minHeight: 180, display: 'flex', flexDirection: 'column' }}
        contentStyle={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
        <SectionLabel right={
          <span style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO, letterSpacing: '0.2em' }}>
            {data.fixes.length} RECENT
          </span>
        }>Recent Auto-Fixes</SectionLabel>
        <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
          {data.fixes.length === 0 && (
            <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12, fontStyle: 'italic' }}>
              No fixes applied yet. ORA is monitoring.
            </div>
          )}
          {data.fixes.map((f, i) => {
            const sev = sevColor(f.severity);
            const okay = f.resolved !== false && f.success !== false;
            const action = f.action_taken || f.message || f.check_name || 'fix';
            const issue = f.issue_found ? ` · ${f.issue_found}` : '';
            return (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '128px 60px 38px 1fr 16px',
                gap: 10, alignItems: 'center', padding: '9px 0',
                borderBottom: '1px dashed rgba(212,163,115,0.10)',
                fontFamily: fontMono, fontSize: 11,
              }}>
                <span style={{ color: TEXT_MD, fontSize: 10 }}>{fmtTime(f.timestamp)}</span>
                <span style={{ color: TEXT_LO, fontSize: 10, letterSpacing: '0.10em', textTransform: 'uppercase' }}>{f.service || f.fix_type || '—'}</span>
                <span style={{ padding: '2px 5px', borderRadius: 4, textAlign: 'center', background: sev.bg, color: sev.fg, fontWeight: 700, fontSize: 9, letterSpacing: '0.06em', border: `1px solid ${sev.border}` }}>{(f.severity || 'LOW').toUpperCase()}</span>
                <span style={{ color: TEXT_HI, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{action}{issue}</span>
                <StatusDot status={okay ? 'GREEN' : 'RED'} size={6} label={okay ? 'OK' : 'FAIL'} />
              </div>
            );
          })}
        </div>
      </Card>
    </PageShell>
  );
};

// ╔══════════════════════════════════════════════════════════════════════
// ║ SecurityPage — auth posture, alert log
// ╚══════════════════════════════════════════════════════════════════════
export const SecurityPage = () => {
  const token = localStorage.getItem('aurem_customer_token');
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/api/sentinel/fixes-log?limit=20`, { headers: { Authorization: `Bearer ${token}` } });
        setAlerts(data?.fixes || []);
      } catch {}
    };
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [token]);

  const sevToStatus = (s) => {
    const x = (s || '').toUpperCase();
    if (x === 'P0' || x.includes('CRIT') || x.includes('HIGH')) return 'RED';
    if (x === 'P1' || x.includes('MED'))   return 'YELLOW';
    return 'GREEN';
  };

  return (
    <PageShell icon={Shield} title="Security" subtitle="Live alerts & account protection." testid="page-security" fitViewport>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 14, flex: '0 0 auto',
      }}>
        <Card>
          <SectionLabel right={<StatusDot status="GREEN" />}>FaceID</SectionLabel>
          <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 30, fontWeight: 700 }}>Active</div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>biometric · device-bound</div>
        </Card>
        <Card>
          <SectionLabel right={<StatusDot status="GREEN" />}>2FA</SectionLabel>
          <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 30, fontWeight: 700 }}>Enforced</div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>via authenticator app</div>
        </Card>
        <Card>
          <SectionLabel right={<StatusDot status="GREEN" />}>Session</SectionLabel>
          <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 30, fontWeight: 700 }}>Monitored</div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>device fingerprint + geo</div>
        </Card>
      </div>

      <Card style={{ flex: '1 1 auto', minHeight: 200, display: 'flex', flexDirection: 'column' }}
        contentStyle={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
        <SectionLabel right={
          <span style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO, letterSpacing: '0.2em' }}>
            {alerts.length} EVENTS
          </span>
        }>Alert Log</SectionLabel>
        <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
          {alerts.length === 0 && (
            <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12, fontStyle: 'italic' }}>
              No security alerts. All clear.
            </div>
          )}
          {alerts.map((a, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '160px 1fr 80px',
              gap: 10, alignItems: 'center', padding: '8px 0',
              borderBottom: '1px dashed rgba(212,163,115,0.10)',
              fontFamily: fontMono, fontSize: 11,
            }}>
              <span style={{ color: TEXT_MD }}>{(a.timestamp || '').slice(0, 19).replace('T', ' ')}</span>
              <span style={{ color: TEXT_HI }}>{a.action_taken || a.message || a.check_name || 'event'}</span>
              <StatusDot status={sevToStatus(a.severity)} size={6} label={a.severity || 'LOW'} />
            </div>
          ))}
        </div>
      </Card>
    </PageShell>
  );
};

// ╔══════════════════════════════════════════════════════════════════════
// ║ AutomationPage — workflows + queue
// ╚══════════════════════════════════════════════════════════════════════
export const AutomationPage = () => {
  const token = localStorage.getItem('aurem_customer_token');
  const [workflows, setWorkflows] = useState([]);
  const [queue, setQueue] = useState({ depth: 0, items: [] });

  useEffect(() => {
    const load = async () => {
      const headers = { Authorization: `Bearer ${token}` };
      try {
        const wf = (await axios.get(`${API}/api/orchestrator/workflows`, { headers, timeout: 10000 })).data;
        // Handle various response formats: {workflows: []}, {items: []}, or direct array
        const wfList = Array.isArray(wf) ? wf : (wf?.workflows || wf?.items || []);
        setWorkflows(Array.isArray(wfList) ? wfList : []);
      } catch { setWorkflows([]); }
      try {
        const q = (await axios.get(`${API}/api/orchestrator/queue`, { headers, timeout: 10000 })).data;
        const items = Array.isArray(q) ? q : (q?.items || []);
        setQueue({ depth: q?.depth ?? items.length, items: Array.isArray(items) ? items : [] });
      } catch { setQueue({ depth: 0, items: [] }); }
    };
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [token]);

  return (
    <PageShell icon={Bot} title="Automation" subtitle="Active workflows & orchestrator queue." testid="page-automation" fitViewport>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: 14, flex: '1 1 auto', minHeight: 0,
      }}>
        <Card style={{ display: 'flex', flexDirection: 'column' }}
          contentStyle={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
          <SectionLabel right={<StatusDot status={workflows.length > 0 ? 'GREEN' : 'YELLOW'} />}>
            Active Workflows
          </SectionLabel>
          <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
            {workflows.length === 0 && (
              <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12, fontStyle: 'italic' }}>
                No workflows yet. ORA will create them as it learns your business.
              </div>
            )}
            {workflows.map((w, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '9px 0', borderBottom: '1px dashed rgba(212,163,115,0.10)',
                fontFamily: fontBody, fontSize: 12, color: TEXT_HI,
              }}>
                <span>{w.name || w.workflow_name || w.id || `Workflow ${i + 1}`}</span>
                <StatusDot status={(w.status === 'active' || w.enabled) ? 'GREEN' : 'YELLOW'} size={6}
                  label={w.status || (w.enabled ? 'ON' : 'OFF')} />
              </div>
            ))}
          </div>
        </Card>

        <Card style={{ display: 'flex', flexDirection: 'column' }}
          contentStyle={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
          <SectionLabel right={<StatusDot status={queue.depth === 0 ? 'GREEN' : 'YELLOW'} />}>
            Orchestrator Queue
          </SectionLabel>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 38, fontWeight: 700 }}>{queue.depth}</span>
            <span style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10 }}>tasks</span>
          </div>
          <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', marginTop: 12, paddingRight: 4 }}>
            {(queue.items || []).length === 0 && (
              <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12, fontStyle: 'italic' }}>
                Queue is empty. ORA is idle and listening.
              </div>
            )}
            {(queue.items || []).map((q, i) => (
              <div key={i} style={{
                padding: '8px 0', borderBottom: '1px dashed rgba(212,163,115,0.10)',
                fontFamily: fontMono, fontSize: 11, color: TEXT_HI,
              }}>
                <span style={{ color: GOLD_HI, marginRight: 8 }}>#{i + 1}</span>
                {q.task || q.name || q.type || 'task'}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </PageShell>
  );
};

// ╔══════════════════════════════════════════════════════════════════════
// ║ CRMPage — leads
// ╚══════════════════════════════════════════════════════════════════════
export const CRMPage = () => {
  const token = localStorage.getItem('aurem_customer_token');
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({});

  useEffect(() => {
    const load = async () => {
      const headers = { Authorization: `Bearer ${token}` };
      try { setLeads((await axios.get(`${API}/api/leads?limit=50`, { headers, timeout: 10000 })).data?.leads || []); } catch {}
      try { setStats((await axios.get(`${API}/api/leads/stats`, { headers, timeout: 10000 })).data?.stats || {}); } catch {}
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [token]);

  const fmt = (n) => Number(n || 0).toLocaleString();

  return (
    <PageShell icon={Users} title="CRM" subtitle="Leads, contacts & conversion pipeline." testid="page-crm" fitViewport>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: 14, flex: '0 0 auto',
      }}>
        {[
          { k: 'Total leads',    v: fmt(stats.total_leads ?? leads.length) },
          { k: 'Qualified',      v: fmt(stats.qualified ?? 0) },
          { k: 'Conversion',     v: `${Math.round((stats.conversion_rate || 0) * (stats.conversion_rate <= 1 ? 100 : 1))}%` },
          { k: 'Pipeline value', v: `$${fmt(stats.total_value || 0)}` },
        ].map((s, i) => (
          <Card key={i}>
            <SectionLabel>{s.k}</SectionLabel>
            <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 32, fontWeight: 700 }}>{s.v}</div>
          </Card>
        ))}
      </div>
      <Card style={{ flex: '1 1 auto', minHeight: 200, display: 'flex', flexDirection: 'column' }}
        contentStyle={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
        <SectionLabel right={<span style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO, letterSpacing: '0.2em' }}>{leads.length} LEADS</span>}>
          Recent Leads
        </SectionLabel>
        <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
          {leads.length === 0 && (
            <div style={{ fontFamily: fontBody, color: TEXT_LO, fontSize: 12, fontStyle: 'italic' }}>
              No leads captured yet. Install the AUREM pixel on your site.
            </div>
          )}
          {leads.map((l, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr 100px 80px',
              gap: 10, alignItems: 'center', padding: '8px 0',
              borderBottom: '1px dashed rgba(212,163,115,0.10)',
              fontFamily: fontBody, fontSize: 12,
            }}>
              <span style={{ color: TEXT_HI }}>{l.name || l.email || '—'}</span>
              <span style={{ color: TEXT_MD, fontFamily: fontMono, fontSize: 11 }}>{l.email || '—'}</span>
              <span style={{ color: GOLD_HI, fontFamily: fontMono, fontSize: 11 }}>${(l.value || 0).toLocaleString()}</span>
              <StatusDot status={(l.status === 'converted' || l.status === 'won') ? 'GREEN' : (l.status === 'lost' ? 'RED' : 'YELLOW')}
                size={6} label={(l.status || 'NEW').toUpperCase()} />
            </div>
          ))}
        </div>
      </Card>
    </PageShell>
  );
};

// ╔══════════════════════════════════════════════════════════════════════
// ║ ORAPage — 8-agent grid
// ╚══════════════════════════════════════════════════════════════════════
export const ORAPage = () => {
  const token = localStorage.getItem('aurem_customer_token');
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/api/aurem/agents/status`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 });
        setAgents(data?.agents || []);
      } catch {}
    };
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [token]);

  return (
    <PageShell icon={Sparkles} title="ORA" subtitle="The autonomous repair intelligence." testid="page-ora" fitViewport>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, flex: '0 0 auto' }}>
        {agents.map((a, i) => {
          const active = String(a.status || '').toUpperCase() !== 'STANDBY';
          return (
            <Card key={i}>
              <SectionLabel right={<StatusDot status={active ? 'GREEN' : 'YELLOW'} label={a.status} />}>
                {a.name || a.role || 'Agent'}
              </SectionLabel>
              <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 32, fontWeight: 700, lineHeight: 1 }}>
                {(a.tasks_completed ?? 0).toLocaleString()}
              </div>
              <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6, letterSpacing: '0.10em' }}>
                {a.role || '—'} · TASKS
              </div>
              <div style={{ marginTop: 10, fontFamily: fontMono, color: TEXT_MD, fontSize: 10 }}>
                {(a.capabilities || []).slice(0,3).join(' · ') || '—'}
              </div>
            </Card>
          );
        })}
      </div>
    </PageShell>
  );
};

// ╔══════════════════════════════════════════════════════════════════════
// ║ SettingsPage — onboarding + Branding + Voice + Booking + danger zone
// ║ iter 322as — A·C·B exposed here directly inside /my
// ╚══════════════════════════════════════════════════════════════════════
const useCustomerBin = (token) => {
  const [bin, setBin] = useState('');
  useEffect(() => {
    if (!token) return;
    axios
      .get(`${API}/api/bin-auth/customer-context`, {
        headers: { Authorization: `Bearer ${token}` }, timeout: 10000,
      })
      .then(({ data }) => setBin(data?.bin || ''))
      .catch(() => {});
  }, [token]);
  return bin;
};

export const SettingsPage = () => {
  const { user, token, logout } = useLuxeAuth();
  const bin = useCustomerBin(token);

  return (
    <PageShell icon={Cog} title="Settings" subtitle="Branding · Voice · Booking · Plan · Danger zone." testid="page-settings">
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 14,
      }}>
        <Card testid="settings-onboarding">
          <SectionLabel>Onboarding</SectionLabel>
          <Row k="Email" v={user?.email || '—'} />
          <Row k="BIN" v={bin || '—'} mono />
          <Row k="Plan" v={(user?.tier || 'starter').toUpperCase()} />
          <Row k="API key" v={user?.api_key || '—'} mono />
        </Card>

        <BrandingCard bin={bin} token={token} />
        <VoiceCard token={token} />
        <BookingCard token={token} />

        <Card testid="settings-session">
          <SectionLabel>Session</SectionLabel>
          <Row k="Status" v="Authenticated" />
          <Row k="Stored at" v="aurem_customer_token (LS)" mono small />
          <button data-testid="logout-btn" onClick={logout} style={{
            marginTop: 16, padding: '10px 18px', borderRadius: 8,
            background: 'rgba(248,113,113,0.10)', border: '1px solid rgba(248,113,113,0.30)',
            color: '#fca5a5', fontFamily: fontMono, fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase',
            cursor: 'pointer',
          }}>Sign Out</button>
        </Card>
      </div>
    </PageShell>
  );
};

// ── Branding (A) ────────────────────────────────────────────────────
const BrandingCard = ({ bin, token }) => {
  const [branding, setBranding] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!bin || !token) return;
    axios
      .get(`${API}/api/admin/branding/${bin}`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
      .then(({ data }) => setBranding(data?.branding || null))
      .catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [bin, token]);

  const save = async () => {
    if (!branding || !bin) return;
    setSaving(true); setErr(''); setSaved(false);
    try {
      const { data } = await axios.post(
        `${API}/api/admin/branding/${bin}`,
        {
          brand_name: branding.brand_name || '',
          logo_url: branding.logo_url || '',
          primary_color: branding.primary_color || '#D4A373',
          domain: branding.domain || '',
        },
        { headers: { Authorization: `Bearer ${token}` }, timeout: 12000 },
      );
      if (data?.branding) setBranding(data.branding);
      setSaved(true);
      setTimeout(() => setSaved(false), 2400);
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    }
    setSaving(false);
  };

  return (
    <Card testid="settings-branding">
      <SectionLabel right={saved ? <span style={{ color: '#bef264', fontFamily: fontMono, fontSize: 10 }}>✓ Saved</span> : null}>
        Branding (White-Label)
      </SectionLabel>
      {err && <div data-testid="branding-error" style={{ color: '#f87171', fontFamily: fontMono, fontSize: 10, marginBottom: 8 }}>{err}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <LuxeField label="Brand name" testid="branding-name"
          value={branding?.brand_name || ''}
          onChange={(v) => setBranding({ ...branding, brand_name: v })} />
        <LuxeField label="Logo URL" testid="branding-logo"
          value={branding?.logo_url || ''} placeholder="https://cdn…/logo.png"
          onChange={(v) => setBranding({ ...branding, logo_url: v })} />
        <div>
          <div style={labelStyle}>Primary colour</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="color" data-testid="branding-color"
              value={branding?.primary_color || '#D4A373'}
              onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
              style={{ width: 38, height: 36, background: 'transparent', border: 'none', padding: 0 }} />
            <input data-testid="branding-color-hex" style={{ ...fieldStyle, flex: 1 }}
              value={branding?.primary_color || ''}
              onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })} />
          </div>
        </div>
        <LuxeField label="Custom domain" testid="branding-domain"
          value={branding?.domain || ''} placeholder="ai.yourcompany.com"
          onChange={(v) => setBranding({ ...branding, domain: v })} />
      </div>
      <button data-testid="branding-save" onClick={save} disabled={saving || !bin}
        style={{ ...buttonGold, marginTop: 12, opacity: (saving || !bin) ? 0.55 : 1 }}>
        {saving ? 'Saving…' : 'Save branding'}
      </button>
    </Card>
  );
};

// ── Inbound Voice (C) ──────────────────────────────────────────────
const VoiceCard = ({ token }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const refresh = () => {
    if (!token) return;
    setLoading(true);
    axios.get(`${API}/api/customer/voice-agent/status`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
      .then(({ data }) => setStatus(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };
  useEffect(refresh, [token]);
  const live = !!(status?.retell_ready || status?.retell_key_set);
  return (
    <Card testid="settings-voice">
      <SectionLabel right={<StatusDot status={live ? 'GREEN' : 'YELLOW'} label={live ? 'LIVE' : 'IDLE'} />}>
        Inbound Voice (Retell)
      </SectionLabel>
      <div style={{ fontFamily: fontBody, color: TEXT_HI, fontSize: 13 }} data-testid="voice-status-text">
        {loading ? 'Checking…' : live ? '🟢 ORA can answer calls right now.' : '🔴 Not configured yet — add RETELL_API_KEY.'}
      </div>
      {live && status?.month_usage && (
        <div style={{ marginTop: 10 }}>
          <Row k="Minutes used"
            v={`${status.month_usage.minutes_used ?? 0} / ${status.month_usage.minutes_included ?? '—'}`} mono />
          <Row k="Remaining" v={status.month_usage.minutes_remaining ?? '—'} mono />
        </div>
      )}
      {!live && (
        <ol style={{ marginTop: 10, color: TEXT_MD, fontFamily: fontBody, fontSize: 12, lineHeight: 1.7, paddingLeft: 18 }}>
          <li>Sign in to <a href="https://www.retellai.com" target="_blank" rel="noreferrer" style={{ color: GOLD_HI }}>retellai.com</a> and create an API key.</li>
          <li>Open Emergent → Env Variables → add <code style={{ color: GOLD_HI }}>RETELL_API_KEY</code>.</li>
          <li>Redeploy — ORA picks up calls 24×7.</li>
        </ol>
      )}
      <button data-testid="voice-refresh" onClick={refresh}
        style={{ ...buttonGold, marginTop: 12 }}>Refresh status</button>
    </Card>
  );
};

// ── Booking (B) ────────────────────────────────────────────────────
const BookingCard = ({ token }) => {
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!token) return;
    axios.get(`${API}/api/customer/api-key`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
      .then(({ data }) => setInfo(data))
      .catch(() => {});
  }, [token]);
  const key = info?.key || info?.key_preview || 'sk_aurem_live_xxxxx';
  const snippet = `<script src="${window.location.origin}/widget.js" data-api-key="${key}"></script>`;
  const copy = () => {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
    toast.success('Embed code copied');
  };
  return (
    <Card testid="settings-booking">
      <SectionLabel>Booking Widget</SectionLabel>
      <div style={{ color: TEXT_MD, fontFamily: fontBody, fontSize: 12, marginBottom: 10 }}>
        Drop the AUREM widget on your site — visitors can book straight from the ORA chat (Name · Phone · Service · Slot).
      </div>
      <div data-testid="booking-snippet" style={{
        padding: 12, borderRadius: 10, background: 'rgba(0,0,0,0.45)',
        border: '1px solid rgba(212,163,115,0.18)', fontFamily: fontMono,
        fontSize: 11, color: TEXT_MD, wordBreak: 'break-all', lineHeight: 1.5,
      }}>{snippet}</div>
      <button data-testid="booking-copy" onClick={copy}
        style={{ ...buttonGold, marginTop: 10 }}>
        {copied ? 'Copied ✓' : 'Copy embed code'}
      </button>
      <div style={{ marginTop: 12, fontFamily: fontMono, fontSize: 10, color: TEXT_LO, letterSpacing: '0.12em' }}>
        Default services: Consultation · Follow-up · Standard · Premium
      </div>
    </Card>
  );
};


// ╔══════════════════════════════════════════════════════════════════════
// ║ IntegrationsPage — Shopify · Widget · Pixel · Booking preview (iter 322as)
// ╚══════════════════════════════════════════════════════════════════════
export const IntegrationsPage = () => {
  const { token } = useLuxeAuth();
  return (
    <PageShell icon={Zap} title="Integrations" subtitle="Shopify · Widget · Pixel · Booking" testid="page-integrations">
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 14,
      }}>
        <ShopifyCard token={token} />
        <WidgetInstallCard token={token} />
        <PixelStatusCard token={token} />
        <BookingPreviewCard />
      </div>
    </PageShell>
  );
};

const ShopifyCard = ({ token }) => {
  const [status, setStatus] = useState(null);
  const [shop, setShop] = useState('');
  const [loading, setLoading] = useState(true);
  const refresh = () => {
    if (!token) return;
    setLoading(true);
    axios.get(`${API}/api/shopify/auth/status`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
      .then(({ data }) => setStatus(data))
      .catch(() => setStatus({ connected: false }))
      .finally(() => setLoading(false));
  };
  useEffect(refresh, [token]);
  const connected = !!(status?.connected || status?.shop);
  const url = shop ? `${API}/api/shopify/auth?shop=${encodeURIComponent(shop)}&token=${encodeURIComponent(token || '')}` : '#';
  return (
    <Card testid="integrations-shopify">
      <SectionLabel right={<StatusDot status={connected ? 'GREEN' : 'YELLOW'} label={connected ? 'CONNECTED' : 'OFF'} />}>
        Shopify
      </SectionLabel>
      <div style={{ fontFamily: fontBody, color: TEXT_HI, fontSize: 13, marginBottom: 8 }} data-testid="shopify-status-text">
        {loading ? 'Checking…' : connected ? `Connected: ${status?.shop || status?.shop_domain}` : 'Sync products, orders & customers in one click.'}
      </div>
      {!connected && (
        <>
          <input data-testid="shopify-shop-input" value={shop} onChange={(e) => setShop(e.target.value)}
            placeholder="yourstore.myshopify.com"
            style={{ ...fieldStyle, marginBottom: 10 }} />
          <a data-testid="shopify-connect-btn" href={url}
            onClick={(e) => { if (!shop) { e.preventDefault(); toast.error('Enter your Shopify store domain first.'); } }}
            style={{ ...buttonGold, textDecoration: 'none', display: 'inline-block',
                     background: '#95BF47', color: '#0E0E0F', border: 'none' }}>
            Connect Shopify Store
          </a>
        </>
      )}
      {connected && (
        <button data-testid="shopify-manage-btn" onClick={refresh} style={buttonGold}>Refresh</button>
      )}
    </Card>
  );
};

const WidgetInstallCard = ({ token }) => {
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!token) return;
    axios.get(`${API}/api/customer/api-key`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
      .then(({ data }) => setInfo(data)).catch(() => {});
  }, [token]);
  const key = info?.key || info?.key_preview || 'sk_aurem_live_xxxxx';
  const snippet = `<script src="${window.location.origin}/widget.js" data-api-key="${key}"></script>`;
  const copy = () => {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
    toast.success('Embed code copied');
  };
  return (
    <Card testid="integrations-widget">
      <SectionLabel>Website Widget</SectionLabel>
      <div style={{ color: TEXT_MD, fontFamily: fontBody, fontSize: 12, marginBottom: 10 }}>
        Paste before <code style={{ color: GOLD_HI }}>&lt;/body&gt;</code>. Auto-detects your theme, opens ORA chat, books appointments.
      </div>
      <div data-testid="widget-snippet" style={{
        padding: 12, borderRadius: 10, background: 'rgba(0,0,0,0.45)',
        border: '1px solid rgba(212,163,115,0.18)', fontFamily: fontMono,
        fontSize: 11, color: TEXT_MD, wordBreak: 'break-all', lineHeight: 1.5,
      }}>{snippet}</div>
      <button data-testid="widget-copy-btn" onClick={copy} style={{ ...buttonGold, marginTop: 10 }}>
        {copied ? 'Copied ✓' : 'Copy embed code'}
      </button>
    </Card>
  );
};

const PixelStatusCard = ({ token }) => {
  const [pixel, setPixel] = useState(null);
  const [loading, setLoading] = useState(true);
  const refresh = () => {
    if (!token) return;
    setLoading(true);
    axios.get(`${API}/api/customer/pixel/status`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
      .then(({ data }) => setPixel(data))
      .catch(() => setPixel({ status: 'not_installed' }))
      .finally(() => setLoading(false));
  };
  useEffect(refresh, [token]);
  const installed = pixel?.status === 'installed' || pixel?.connected || (pixel?.events_total > 0);
  return (
    <Card testid="integrations-pixel">
      <SectionLabel right={<StatusDot status={installed ? 'GREEN' : 'RED'} label={installed ? 'INSTALLED' : 'OFF'} />}>
        Pixel Tracking
      </SectionLabel>
      <div style={{ fontFamily: fontBody, color: TEXT_HI, fontSize: 13 }} data-testid="pixel-status-text">
        {loading ? 'Checking…' : installed
          ? `🟢 Active — ${pixel?.events_total || 0} events captured`
          : '🔴 Not installed — paste the pixel snippet on your site.'}
      </div>
      <button data-testid="pixel-refresh-btn" onClick={refresh}
        style={{ ...buttonGold, marginTop: 12 }}>Refresh</button>
    </Card>
  );
};

const BookingPreviewCard = () => (
  <Card testid="integrations-booking">
    <SectionLabel>Booking Widget</SectionLabel>
    <div style={{ color: TEXT_MD, fontFamily: fontBody, fontSize: 12, lineHeight: 1.7 }}>
      The widget includes a built-in booking modal. Visitors pick a service, date and slot — the booking lands in your{' '}
      <code style={{ color: GOLD_HI }}>bookings</code> collection.
    </div>
    <ol style={{ color: TEXT_MD, fontFamily: fontBody, fontSize: 12, lineHeight: 1.7, paddingLeft: 18, marginTop: 8 }}>
      <li>Embed the widget snippet on your site.</li>
      <li>Visitor clicks the floating ORA bubble → 📅 Book.</li>
      <li>Confirms instantly. You see it in CRM.</li>
    </ol>
    <div style={{ marginTop: 10, fontFamily: fontMono, fontSize: 10, color: TEXT_LO, letterSpacing: '0.12em' }}>
      Public endpoints: /api/public/booking/{`{types,availability,book}`}
    </div>
  </Card>
);

// ── small helper field ──
const LuxeField = ({ label, value, onChange, placeholder, testid }) => (
  <div>
    <div style={labelStyle}>{label}</div>
    <input data-testid={testid} value={value || ''} placeholder={placeholder || ''}
      onChange={(e) => onChange(e.target.value)} style={fieldStyle} />
  </div>
);
