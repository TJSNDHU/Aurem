/**
 * AdminCustomer360 — Iteration 208
 * =================================
 * Admin → Customer 360° view
 *
 * Route: /admin/customer/:identifier
 *   identifier = email OR business_id (either BIN format works now)
 *
 * Shows a complete 360° portrait of one customer on a single screen:
 *   • Identity (platform_users + users legacy + tenant_customers)
 *   • Workspace (aurem_workspaces)
 *   • Pricing / plan + Stripe IDs
 *   • Live Pixel status + events last 24h
 *   • Recent scan history
 *   • Referral rewards
 *   • BIN history (current + previous + sync timestamp)
 *   • Login history from audit_chain
 *   • Onboarding state
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  User, CreditCard, Radio, Shield, Gift, LogIn, Globe, Sparkles,
  RefreshCw, Loader2, Copy, CheckCircle2, XCircle,
} from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';
import Customer360ActionPanel from './Customer360ActionPanel';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  bg: '#06060C',
  panel: 'rgba(13, 13, 23, 0.58)',
  panelSolid: '#0D0D17',
  border: 'rgba(212,175,55,0.18)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

const GLASS_CARD = {
  background: C.panel,
  border: `1px solid ${C.border}`,
  borderRadius: 14,
  padding: '18px 20px',
  backdropFilter: 'blur(22px) saturate(160%)',
  WebkitBackdropFilter: 'blur(22px) saturate(160%)',
  boxShadow: '0 12px 36px rgba(0,0,0,0.45), inset 0 1px 0 rgba(212,175,55,0.12)',
};

export default function AdminCustomer360() {
  const { identifier } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const tok = getPlatformToken();
      const r = await fetch(`${API}/api/admin/customer-360/${encodeURIComponent(identifier)}`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setError(d.detail || `HTTP ${r.status}`);
      } else {
        setData(await r.json());
      }
    } catch (e) { setError(e.message); }
    setLoading(false);
  }, [identifier]);

  useEffect(() => { load(); }, [load]);

  const copy = (text, label) => {
    try { navigator.clipboard.writeText(text); setCopied(label); setTimeout(() => setCopied(''), 1600); }
    catch { /* noop */ }
  };

  if (loading && !data) {
    return <div data-testid="c360-loading" style={{minHeight:'60vh',display:'flex',alignItems:'center',justifyContent:'center',color:C.textD,fontSize:13,fontFamily:"'Jost',sans-serif"}}>
      <Loader2 size={16} style={{animation:'spin 1s linear infinite',marginRight:10}}/> Loading customer 360…
    </div>;
  }
  if (error) {
    return <div data-testid="c360-error" style={{padding:40,color:C.bad,fontFamily:"'Jost',sans-serif"}}>
      {error}<br/><Link to="/dashboard" style={{color:C.accent}}>← Back to Dashboard</Link>
    </div>;
  }
  if (!data) return null;

  const id = data.identity || {};
  const pu = id.platform_user || {};
  const tc = id.tenant_customer || {};
  const ws = data.workspace || {};
  const plan = data.pricing_plan || {};
  const pixel = data.pixel || {};
  const scans = data.scan_history || [];
  const ref = data.referrals || {};
  const binH = data.bin_history || {};
  const logins = data.login_history || [];
  const onb = data.onboarding_state || {};
  const businessName = pu.company_name || tc.company_name || ws.business_name || '—';

  return (
    <div data-testid="admin-customer-360" style={{
      minHeight:'100vh',
      background:`${C.bg} url('${process.env.REACT_APP_BACKEND_URL || ''}/api/static/customer-360-bg.jpg') center right / cover no-repeat fixed`,
      color:C.text,fontFamily:"'Jost',sans-serif",padding:'28px 36px',
      position:'relative',
    }}>
      {/* Dark vignette so the panels remain readable over the AI portrait */}
      <div aria-hidden="true" style={{
        position:'fixed', inset:0, pointerEvents:'none', zIndex:0,
        background:'linear-gradient(90deg, rgba(5,5,8,0.94) 0%, rgba(5,5,8,0.82) 45%, rgba(5,5,8,0.55) 72%, rgba(5,5,8,0.3) 100%)',
      }}/>
      <div style={{position:'relative',zIndex:1}}>
      {/* Header */}
      <div style={{marginBottom:22}}>
        <Link to="/dashboard" style={{fontSize:11,color:C.textD,letterSpacing:'0.2em',textTransform:'uppercase',textDecoration:'none'}}>← Dashboard</Link>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginTop:6,flexWrap:'wrap',gap:16}}>
          <div>
            <div style={{fontSize:11,letterSpacing:'0.24em',color:C.accent,textTransform:'uppercase',fontWeight:700}}>Customer 360°</div>
            <h1 style={{fontFamily:"'Cinzel',serif",fontSize:28,fontWeight:700,color:'#FFF',margin:'4px 0',letterSpacing:'0.02em'}}>{businessName}</h1>
            <div style={{fontSize:12,color:C.textD,fontFamily:"'JetBrains Mono',monospace",marginTop:4}}>
              {id.email} · BIN {binH.current || '—'}
            </div>
          </div>
          <button data-testid="c360-refresh" onClick={load} disabled={loading} style={btn}>
            <RefreshCw size={12} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {/* Top row: Identity + Plan + Pixel */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(320px,1fr))',gap:14}}>

        {/* Action Panel — prominent at top */}
        <Customer360ActionPanel identifier={identifier} email={id.email}/>

        {/* Identity */}
        <Card title="Identity" icon={User} testid="c360-card-identity">
          <Row label="Email"       value={id.email} copy={() => copy(id.email, 'email')} copied={copied === 'email'}/>
          <Row label="Full Name"   value={pu.full_name || tc.full_name || '—'}/>
          <Row label="Company"     value={businessName}/>
          <Row label="Role"        value={pu.role || 'user'}/>
          <Row label="platform_users" value={pu._id ? 'present' : (pu.email ? 'present' : 'missing')}/>
          <Row label="tenant_customers" value={tc.business_id ? 'present' : 'missing'}/>
          <Row label="users (legacy)"  value={id.users_legacy?.email ? 'present' : 'missing'}/>
        </Card>

        {/* BIN history */}
        <Card title="BIN History" icon={Shield} testid="c360-card-bin">
          <Row label="Current BIN"  value={binH.current || '—'} copy={() => copy(binH.current, 'bin')} copied={copied === 'bin'}/>
          <Row label="Previous BIN" value={binH.previous || '—'}/>
          <Row label="Synced At"    value={(binH.synced_at || '').slice(0, 19).replace('T', ' ') || '—'}/>
          <div style={{marginTop:10,fontSize:10.5,color:C.textD}}>
            Both 3+3+4 and 4+4 BIN formats accepted at login.
          </div>
        </Card>

        {/* Plan / Subscription */}
        <Card title="Plan &amp; Subscription" icon={CreditCard} testid="c360-card-plan">
          <Row label="Plan"           value={plan.plan || '—'}/>
          <Row label="Status"         value={plan.status || '—'}/>
          <Row label="MRR"            value={plan.mrr ? `$${plan.mrr}` : '—'}/>
          <Row label="Joined"         value={(plan.joined_date || '').slice(0, 10) || '—'}/>
          <Row label="Stripe Customer"value={plan.stripe_customer_id || '—'}/>
          <Row label="Stripe Sub ID"  value={plan.stripe_subscription_id || '—'}/>
        </Card>

        {/* Live Pixel */}
        <Card title="Live Pixel" icon={Radio} testid="c360-card-pixel">
          {!pixel.has_key ? (
            <p style={{fontSize:12,color:C.textD}}>No API key assigned.</p>
          ) : (
            <>
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10}}>
                {pixel.connected ? <CheckCircle2 size={15} color={C.good}/> : <XCircle size={15} color={C.bad}/>}
                <span style={{color: pixel.connected ? C.good : C.bad, fontWeight:700,fontSize:11,letterSpacing:'0.12em',textTransform:'uppercase'}}>
                  {pixel.connected ? 'Connected' : 'No events yet'}
                </span>
              </div>
              <Row label="Tenant ID"   value={pixel.tenant_id || '—'}/>
              <Row label="Key Preview" value={pixel.key_preview || '—'}/>
              <Row label="Active"      value={pixel.active ? 'yes' : 'no'}/>
              <Row label="Events 24h"  value={String(pixel.events_24h ?? 0)}/>
              <Row label="Total Hits"  value={String(pixel.total_hits ?? 0)}/>
              <Row label="Last Ping"   value={(pixel.last_ping || '').slice(0, 19).replace('T', ' ') || '—'}/>
            </>
          )}
        </Card>

        {/* Onboarding */}
        <Card title="Onboarding" icon={Sparkles} testid="c360-card-onboarding">
          <Row label="Smart Onboarding" value={onb.smart_complete ? 'completed' : 'pending'}/>
          <Row label="Detected Platform" value={onb.platform_detected || '—'}/>
          <Row label="First-Login Wizard" value={onb.wizard_complete ? 'completed' : `step ${onb.wizard_step}/4`}/>
          <Row label="Smart Onboarded At" value={(onb.smart_onboarded_at || '').slice(0,19).replace('T',' ') || '—'}/>
        </Card>

        {/* Referrals */}
        <Card title="Referrals &amp; Rewards" icon={Gift} testid="c360-card-referrals">
          <Row label="Referred Count"  value={String(ref.referred_count ?? 0)}/>
          <Row label="Reward Months"   value={String(ref.reward_months ?? 0)}/>
          <div style={{marginTop:10,fontSize:11,color:C.textD}}>
            Each successful referral earns the referrer one month free.
          </div>
        </Card>

        {/* Workspace */}
        <Card title="Workspace" icon={Globe} testid="c360-card-workspace">
          <Row label="Business Type"   value={ws.business_type || '—'}/>
          <Row label="Timezone"        value={ws.timezone || '—'}/>
          <Row label="Website"         value={ws.website || '—'}/>
          <Row label="Status"          value={ws.status || '—'}/>
          <Row label="Trial Override"  value={String(ws.trial_override ?? false)}/>
        </Card>

        {/* Scan history */}
        <Card title="Scan History" icon={Shield} testid="c360-card-scans" span={2}>
          {scans.length === 0 ? (
            <p style={{fontSize:12,color:C.textD}}>No scans recorded.</p>
          ) : (
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
              <thead>
                <tr>
                  <th style={th}>Scanned At</th>
                  <th style={th}>Type</th>
                  <th style={th}>Findings</th>
                  <th style={th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s, i) => (
                  <tr key={i} data-testid={`c360-scan-${i}`} style={{borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                    <td style={td}>{(s.scanned_at || s.timestamp || '').slice(0,19).replace('T',' ') || '—'}</td>
                    <td style={td}>{s.scan_type || s.type || '—'}</td>
                    <td style={td}>{s.findings_count ?? s.issues_count ?? '—'}</td>
                    <td style={td}><Badge tone={s.status === 'passed' ? 'good' : 'warn'}>{s.status || '—'}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Login history */}
        <Card title="Login History" icon={LogIn} testid="c360-card-logins" span={2}>
          {logins.length === 0 ? (
            <p style={{fontSize:12,color:C.textD}}>No login events recorded.</p>
          ) : (
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
              <thead>
                <tr>
                  <th style={th}>Timestamp</th>
                  <th style={th}>Event</th>
                  <th style={th}>IP</th>
                  <th style={th}>Success</th>
                </tr>
              </thead>
              <tbody>
                {logins.map((l, i) => (
                  <tr key={i} data-testid={`c360-login-${i}`} style={{borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                    <td style={td}>{(l.timestamp || '').slice(0,19).replace('T',' ') || '—'}</td>
                    <td style={td}>{l.event_type || '—'}</td>
                    <td style={td}>{l.ip || '—'}</td>
                    <td style={td}>{l.success === false ? <XCircle size={12} color={C.bad}/> : <CheckCircle2 size={12} color={C.good}/>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}

function Card({ title, icon: Icon, children, testid, span = 1 }) {
  return (
    <div data-testid={testid} style={{gridColumn:`span ${span}`, ...GLASS_CARD}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:12}}>
        {Icon && <Icon size={14} color={C.accent}/>}
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.accent,letterSpacing:'0.18em',textTransform:'uppercase',margin:0}}>{title}</h3>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, copy, copied }) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'6px 0',borderBottom:'1px solid rgba(255,255,255,0.04)',gap:10}}>
      <span style={{fontSize:10,letterSpacing:'0.18em',color:C.textD,textTransform:'uppercase',fontWeight:600}}>{label}</span>
      <span style={{fontSize:12,color:C.text,fontFamily:"'JetBrains Mono',monospace",textAlign:'right',maxWidth:'60%',wordBreak:'break-word'}}>
        {value}
        {copy && value && value !== '—' && (
          <button onClick={copy} style={{marginLeft:8,background:'none',border:'none',color: copied ? C.good : C.textD,cursor:'pointer'}}>
            {copied ? <CheckCircle2 size={11}/> : <Copy size={11}/>}
          </button>
        )}
      </span>
    </div>
  );
}

function Badge({ tone = 'neutral', children }) {
  const map = {
    good: { bg: 'rgba(74,222,128,0.1)', color: C.good },
    warn: { bg: 'rgba(245,158,11,0.1)', color: C.warn },
    bad:  { bg: 'rgba(239,68,68,0.1)',  color: C.bad },
    neutral: { bg: 'rgba(138,128,112,0.08)', color: C.textD },
  };
  const s = map[tone] || map.neutral;
  return <span style={{display:'inline-flex',padding:'2px 8px',borderRadius:20,fontSize:9.5,fontWeight:700,letterSpacing:'0.14em',textTransform:'uppercase',background:s.bg,color:s.color}}>{children}</span>;
}

const btn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.25)',borderRadius:8,
  color:'#D4AF37',fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};
const th = { textAlign:'left', padding:'7px 10px', fontSize:10, letterSpacing:'0.14em', color: C.textD, textTransform:'uppercase', fontWeight:700, borderBottom:'1px solid rgba(255,255,255,0.06)' };
const td = { padding:'7px 10px', fontSize:12, verticalAlign:'middle' };
