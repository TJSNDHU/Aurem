/**
 * Customer360ActionPanel — Iteration 209
 * =======================================
 * Admin-only dangerous-action panel embedded inside the /admin/customer/:id view.
 *
 * All 6 actions hit /api/admin/customer-360/{identifier}/actions/*
 * Every action shows a confirmation prompt (text prompts for message/plan).
 */
import React, { useState } from 'react';
import {
  Key, MessageCircle, ArrowUpCircle, RefreshCw, Zap, UserCheck,
  Copy, CheckCircle2, AlertTriangle, Loader2,
} from 'lucide-react';
import { getPlatformToken, setPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  panel: 'rgba(13, 13, 23, 0.58)', border: 'rgba(212,175,55,0.18)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

const PLANS = ['trial', 'starter', 'growth', 'enterprise'];

export default function Customer360ActionPanel({ identifier, email }) {
  const [loading, setLoading] = useState('');           // which action is running
  const [result, setResult] = useState(null);           // last result blob
  const [error, setError] = useState('');

  const call = async (path, body) => {
    setLoading(path); setError(''); setResult(null);
    try {
      const tok = getPlatformToken();
      const r = await fetch(`${API}/api/admin/customer-360/${encodeURIComponent(identifier)}/actions/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` },
        body: body ? JSON.stringify(body) : null,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setResult({ action: path, ...d });
      return d;
    } catch (e) {
      setError(e.message || 'Action failed');
      return null;
    } finally {
      setLoading('');
    }
  };

  const onResetPassword = async () => {
    if (!window.confirm(`Reset password for ${email}? A temp password will be generated and (if phone on file) sent via WhatsApp.`)) return;
    await call('reset-password', { notify: true });
  };

  const onSendWhatsApp = async () => {
    const msg = window.prompt(`WhatsApp message to ${email}:`);
    if (!msg || !msg.trim()) return;
    await call('send-whatsapp', { message: msg });
  };

  const onChangePlan = async () => {
    const plan = window.prompt(`New plan for ${email}? (${PLANS.join(' / ')})`);
    if (!plan) return;
    const p = plan.trim().toLowerCase();
    if (!PLANS.includes(p)) { alert(`Invalid plan — must be one of ${PLANS.join(', ')}`); return; }
    if (!window.confirm(`Confirm plan change to "${p}"?`)) return;
    await call('change-plan', { plan: p });
  };

  const onRotateKey = async () => {
    if (!window.confirm(`Rotate API key for ${email}?\n\nThis will DEACTIVATE the current key immediately. The new key will be shown ONCE.`)) return;
    await call('rotate-api-key', null);
  };

  const onTriggerScan = async () => {
    if (!window.confirm(`Queue an immediate website scan for ${email}?`)) return;
    await call('trigger-scan', null);
  };

  const onImpersonate = async () => {
    if (!window.confirm(`Impersonate ${email}?\n\n• 30-minute token\n• All actions audit-logged as impersonation\n• Your admin session will be replaced — log out and back in to return to admin.`)) return;
    const d = await call('impersonate', null);
    if (d && d.impersonation_token) {
      // Replace admin token with impersonation token; open customer portal in new tab
      setPlatformToken(d.impersonation_token);
      window.open('/my', '_blank', 'noopener');
    }
  };

  const copy = (text) => {
    try { navigator.clipboard.writeText(text); } catch { /* noop */ }
  };

  return (
    <div data-testid="c360-action-panel" style={{gridColumn:'span 2',background:C.panel,border:`1px solid rgba(239,68,68,0.28)`,borderRadius:14,padding:'18px 20px',backdropFilter:'blur(22px) saturate(160%)',WebkitBackdropFilter:'blur(22px) saturate(160%)',boxShadow:'0 12px 36px rgba(0,0,0,0.45), inset 0 1px 0 rgba(239,68,68,0.15)'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
        <AlertTriangle size={14} color={C.bad}/>
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.bad,letterSpacing:'0.2em',textTransform:'uppercase',margin:0}}>Action Panel · Admin Only</h3>
      </div>
      <p style={{fontSize:11,color:C.textD,marginBottom:14}}>Every action is audit-logged. Confirm prompts before execution. All against: <strong style={{color:C.text}}>{email}</strong></p>

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:10,marginBottom:14}}>
        <ActionBtn testid="c360-action-reset"   icon={Key}           label="Reset Password"     onClick={onResetPassword}  loading={loading === 'reset-password'}/>
        <ActionBtn testid="c360-action-wa"      icon={MessageCircle} label="Send WhatsApp"       onClick={onSendWhatsApp}   loading={loading === 'send-whatsapp'}/>
        <ActionBtn testid="c360-action-plan"    icon={ArrowUpCircle} label="Change Plan"         onClick={onChangePlan}     loading={loading === 'change-plan'}/>
        <ActionBtn testid="c360-action-rotate"  icon={RefreshCw}     label="Rotate API Key"      onClick={onRotateKey}      loading={loading === 'rotate-api-key'}/>
        <ActionBtn testid="c360-action-scan"    icon={Zap}           label="Trigger Scan"        onClick={onTriggerScan}    loading={loading === 'trigger-scan'}/>
        <ActionBtn testid="c360-action-impersonate" icon={UserCheck} label="Impersonate (30m)"  onClick={onImpersonate}    loading={loading === 'impersonate'} danger/>
      </div>

      {error && (
        <div data-testid="c360-action-error" style={{marginTop:10,padding:'8px 12px',background:'rgba(239,68,68,0.08)',border:`1px solid rgba(239,68,68,0.3)`,borderRadius:8,color:C.bad,fontSize:12}}>
          {error}
        </div>
      )}

      {result && (
        <div data-testid="c360-action-result" style={{marginTop:10,padding:'12px 14px',background:'rgba(74,222,128,0.05)',border:`1px solid rgba(74,222,128,0.25)`,borderRadius:8,fontSize:12,color:C.text}}>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
            <CheckCircle2 size={14} color={C.good}/>
            <strong style={{color:C.good,textTransform:'uppercase',letterSpacing:'0.1em',fontSize:10.5}}>{result.action} · success</strong>
          </div>
          {result.temp_password && (
            <CopyRow label="Temp Password" value={result.temp_password} onCopy={() => copy(result.temp_password)}/>
          )}
          {result.new_key && (
            <CopyRow label="New API Key (save now!)" value={result.new_key} onCopy={() => copy(result.new_key)} highlight/>
          )}
          {result.impersonation_token && (
            <CopyRow label="Impersonation Token" value={`${result.impersonation_token.slice(0,40)}…`} onCopy={() => copy(result.impersonation_token)}/>
          )}
          {result.scan_id && (
            <div style={{fontSize:11.5}}>Scan queued: <code style={{color:C.accent,fontFamily:"'JetBrains Mono',monospace"}}>{result.scan_id}</code></div>
          )}
          {result.from !== undefined && result.to !== undefined && (
            <div style={{fontSize:11.5}}>Plan: <strong>{result.from || 'unset'}</strong> → <strong style={{color:C.accent}}>{result.to}</strong></div>
          )}
          {result.warning && (
            <div style={{marginTop:6,fontSize:11,color:C.warn,display:'flex',gap:6,alignItems:'center'}}>
              <AlertTriangle size={11}/> {result.warning}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ActionBtn({ icon: Icon, label, onClick, loading, danger, testid }) {
  return (
    <button
      data-testid={testid}
      onClick={onClick}
      disabled={loading}
      style={{
        display:'flex',alignItems:'center',gap:8,padding:'10px 14px',
        background: danger ? 'rgba(239,68,68,0.08)' : 'transparent',
        border: `1px solid ${danger ? 'rgba(239,68,68,0.3)' : 'rgba(212,175,55,0.2)'}`,
        borderRadius:8,
        color: danger ? C.bad : C.accent,
        fontSize:11.5,fontWeight:700,letterSpacing:'0.06em',textTransform:'uppercase',
        cursor: loading ? 'wait' : 'pointer',
        fontFamily:"'Jost',sans-serif",
        opacity: loading ? 0.6 : 1,
      }}
    >
      {loading ? <Loader2 size={13} style={{animation:'spin 1s linear infinite'}}/> : <Icon size={13}/>}
      {label}
    </button>
  );
}

function CopyRow({ label, value, onCopy, highlight }) {
  return (
    <div style={{display:'flex',alignItems:'center',gap:10,padding:'6px 8px',background:highlight?'rgba(212,175,55,0.06)':'transparent',borderRadius:6,marginBottom:6}}>
      <span style={{fontSize:10,letterSpacing:'0.14em',color:C.textD,textTransform:'uppercase',fontWeight:700,minWidth:120}}>{label}</span>
      <code style={{flex:1,color:C.text,fontFamily:"'JetBrains Mono',monospace",fontSize:11,wordBreak:'break-all'}}>{value}</code>
      <button onClick={onCopy} style={{background:'transparent',border:'none',color:C.accent,cursor:'pointer'}} aria-label="Copy">
        <Copy size={12}/>
      </button>
    </div>
  );
}
