/**
 * ORA Repair Engine — AI-Powered SEO + Accessibility Auto-Fix
 * + Master Patch Deploy + Stripe Scan-to-Pay + GitHub PR
 *
 * Copper Wireframe Code Diff Theme
 * Tiered: Basic ($29 download) / Pro ($99 GitHub auto-push)
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Eye, CheckCircle, XCircle, Clock,
  ChevronDown, ChevronRight, Copy, Check, Sparkles,
  Image, Code, Type, Globe, FileText, Accessibility,
  ArrowRight, Loader2, AlertTriangle, Wrench,
  Download, Github, CreditCard, Lock, Unlock, Zap, ExternalLink,
  History, RefreshCw, TrendingUp, Calendar, Settings, Save, Users, Star, Link2,
  Upload, Trash2, Music, BookOpen, Link, Languages, BrainCircuit, Quote, LayoutList
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ═══ Score Gauge ═══ */
const ScoreRing = ({ score, label, size = 90 }) => {
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const color = score >= 80 ? '#4ade80' : score >= 60 ? '#D4B977' : '#FF6B6B';
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(61,58,57,0.15)" strokeWidth="6" fill="none" />
        <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth="6" fill="none"
          strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`} style={{ transition: 'stroke-dashoffset 1.2s ease-out' }} />
        <text x={size/2} y={size/2 - 4} textAnchor="middle" fontSize="18" fontWeight="bold" fill="#1A1A2E">{score}</text>
        <text x={size/2} y={size/2 + 12} textAnchor="middle" fontSize="8" fill="#888" letterSpacing="1">{score >= 80 ? 'GOOD' : score >= 60 ? 'FAIR' : 'POOR'}</text>
      </svg>
      <span className="text-[9px] tracking-[1.5px] text-[#888] mt-1 uppercase font-bold">{label}</span>
    </div>
  );
};

/* ═══ Before/After Score Card ═══ */
const BeforeAfterCard = ({ title, icon: Icon, before, after, fixCount, color }) => (
  <div className="p-5 rounded-2xl border border-white/30 bg-white/50 backdrop-blur-sm" data-testid={`score-card-${title.toLowerCase()}`}>
    <div className="flex items-center gap-2 mb-4">
      <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${color}15` }}>
        <Icon className="size-4" style={{ color }} />
      </div>
      <div>
        <h3 className="text-xs font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">{title}</h3>
        <span className="text-[10px] text-[#888]">{fixCount} fixes generated</span>
      </div>
    </div>
    <div className="flex items-center justify-center gap-4">
      <ScoreRing score={before} label="Before" />
      <ArrowRight className="size-5 text-[#D4B977] flex-shrink-0" />
      <ScoreRing score={after} label="After" />
    </div>
    <div className="mt-3 text-center">
      <span className="text-sm font-bold" style={{ color: after > before ? '#4ade80' : '#888' }}>
        {after > before ? `+${after - before} points` : 'No change'}
      </span>
    </div>
  </div>
);

/* ═══ Fix Type Icons ═══ */
const fixTypeIcon = (type) => {
  const map = {
    title: Type, meta_description: FileText, h1: Type,
    og_title: Globe, og_description: Globe,
    alt_text: Image, aria_main: Code, aria_nav: Code,
    aria_banner: Code, aria_footer: Code,
    lang_attr: Globe, skip_nav: Accessibility, form_labels: FileText,
    json_ld_base: Code, json_ld_faq: LayoutList, json_ld_article: FileText,
    ai_summary: Quote, citation_block: Link2, semantic_html: Code,
  };
  return map[type] || Wrench;
};

/* ═══ Single Fix Item ═══ */
const FixItem = ({ fix, onApprove, onReject, loading }) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const Icon = fixTypeIcon(fix.fix_type);

  const statusConfig = {
    pending_approval: { color: '#D4B977', bg: 'rgba(212,175,55,0.1)', label: 'PENDING', icon: Clock },
    approved: { color: '#4ade80', bg: 'rgba(74,222,128,0.1)', label: 'APPROVED', icon: CheckCircle },
    rejected: { color: '#FF6B6B', bg: 'rgba(255,107,107,0.1)', label: 'REJECTED', icon: XCircle },
    deployed: { color: '#FF6B00', bg: 'rgba(61,58,57,0.25)', label: 'DEPLOYED', icon: CheckCircle },
  };
  const st = statusConfig[fix.status] || statusConfig.pending_approval;
  const StIcon = st.icon;

  const handleCopy = () => {
    navigator.clipboard.writeText(fix.fix_code || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mb-2" data-testid={`fix-item-${fix.fix_id}`}>
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/50 backdrop-blur-sm border border-white/30 hover:bg-white/70 transition-all text-left">
        <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: st.bg }}>
          <Icon className="size-4" style={{ color: st.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-xs font-bold text-[#1A1A2E] truncate pr-2">{fix.label}</span>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[8px] px-1.5 py-0.5 rounded font-bold tracking-wider flex items-center gap-1" style={{ background: st.bg, color: st.color }}>
                <StIcon className="size-2.5" />{st.label}
              </span>
              {expanded ? <ChevronDown className="size-3 text-[#888]" /> : <ChevronRight className="size-3 text-[#888]" />}
            </div>
          </div>
          {fix.suggested_value && <p className="text-[10px] text-[#666] truncate">{fix.suggested_value}</p>}
        </div>
      </button>

      {expanded && (
        <div className="mt-1 ml-11 p-4 rounded-xl bg-white/40 border border-white/30 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="text-[9px] font-bold tracking-[1px] text-[#FF6B6B] uppercase block mb-1">Original</span>
              <div className="p-2 rounded-lg bg-[#FF6B6B]/5 border border-[#FF6B6B]/10 text-[11px] text-[#666] font-mono break-all">
                {fix.original_value || '(empty)'}
              </div>
            </div>
            <div>
              <span className="text-[9px] font-bold tracking-[1px] text-[#4ade80] uppercase block mb-1">Suggested</span>
              <div className="p-2 rounded-lg bg-[#4ade80]/5 border border-[#4ade80]/10 text-[11px] text-[#1A1A2E] font-mono break-all">
                {fix.suggested_value}
              </div>
            </div>
          </div>
          {fix.fix_code && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] font-bold tracking-[1px] text-[#888] uppercase">Fix Code</span>
                <button onClick={handleCopy} className="text-[10px] text-[#888] hover:text-[#1A1A2E] flex items-center gap-1">
                  {copied ? <><Check className="size-3 text-[#4ade80]" />Copied</> : <><Copy className="size-3" />Copy</>}
                </button>
              </div>
              <pre className="p-3 rounded-lg bg-[#1a1a2e] text-[11px] text-green-300 font-mono overflow-x-auto whitespace-pre-wrap">{fix.fix_code}</pre>
            </div>
          )}
          <div className="flex items-center gap-2">
            <Sparkles className="size-3 text-[#D4B977]" />
            <span className="text-[9px] text-[#888]">
              Generated by <span className="font-bold text-[#D4B977]">{fix.ai_model === 'nano-banana-2' ? 'Nano Banana 2' : fix.ai_model === 'gemini-3.1-pro-preview' ? 'Gemini 3.1 Pro' : fix.ai_model}</span>
            </span>
          </div>
          {fix.status === 'pending_approval' && (
            <div className="flex gap-2 pt-1">
              <button onClick={() => onApprove(fix.fix_id)} disabled={loading} data-testid={`approve-${fix.fix_id}`}
                className="flex-1 py-2 rounded-lg bg-[#4ade80]/15 text-[#FF6B00] text-xs font-bold hover:bg-[#4ade80]/25 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50">
                <CheckCircle className="size-3.5" /> Approve Fix
              </button>
              <button onClick={() => onReject(fix.fix_id)} disabled={loading} data-testid={`reject-${fix.fix_id}`}
                className="flex-1 py-2 rounded-lg bg-[#FF6B6B]/10 text-[#FF6B6B] text-xs font-bold hover:bg-[#FF6B6B]/20 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50">
                <XCircle className="size-3.5" /> Reject
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};


/* ═══════════════════════════════════════════════════════════════ */
/* ═══ COPPER WIREFRAME CODE DIFF VIEWER ═══ */
/* ═══════════════════════════════════════════════════════════════ */

const CopperDiffViewer = ({ diffs }) => {
  if (!diffs || diffs.length === 0) return null;

  return (
    <div className="space-y-3" data-testid="copper-diff-viewer">
      {diffs.map((diff, i) => (
        <div key={diff.fix_id || i}
          className="rounded-xl overflow-hidden"
          style={{ border: '1px solid rgba(184,135,89,0.25)', background: 'linear-gradient(135deg, #1C1712 0%, #211D17 100%)' }}>
          {/* Diff Header */}
          <div className="px-4 py-2.5 flex items-center justify-between"
            style={{ borderBottom: '1px solid rgba(184,135,89,0.15)', background: 'rgba(184,135,89,0.06)' }}>
            <div className="flex items-center gap-2">
              <div className="size-2 rounded-full" style={{ background: '#B88759' }} />
              <span className="text-[11px] font-bold tracking-wider" style={{ color: '#D4A574' }}>
                {diff.label}
              </span>
              <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(184,135,89,0.15)', color: '#B88759' }}>
                {diff.category?.toUpperCase()}
              </span>
            </div>
            <Code className="size-3.5" style={{ color: '#6B5744' }} />
          </div>
          {/* Side-by-Side Diff */}
          <div className="grid grid-cols-2 divide-x" style={{ borderColor: 'rgba(184,135,89,0.1)' }}>
            {/* OLD (Left) */}
            <div className="p-0">
              <div className="px-3 py-1.5" style={{ background: 'rgba(255,107,107,0.06)', borderBottom: '1px solid rgba(255,107,107,0.08)' }}>
                <span className="text-[8px] font-bold tracking-[2px] uppercase" style={{ color: '#FF6B6B' }}>Before</span>
              </div>
              <pre className="p-3 text-[11px] font-mono whitespace-pre-wrap break-all leading-relaxed" style={{ color: '#9B8B7A' }}>
                <span style={{ background: 'rgba(255,107,107,0.08)', borderLeft: '2px solid rgba(255,107,107,0.3)', paddingLeft: '8px', display: 'block' }}>
                  {diff.old_code || '(empty — element missing)'}
                </span>
              </pre>
            </div>
            {/* NEW (Right) */}
            <div className="p-0" style={{ borderColor: 'rgba(184,135,89,0.1)' }}>
              <div className="px-3 py-1.5" style={{ background: 'rgba(74,222,128,0.04)', borderBottom: '1px solid rgba(74,222,128,0.08)' }}>
                <span className="text-[8px] font-bold tracking-[2px] uppercase" style={{ color: '#4ade80' }}>ORA-Optimized</span>
              </div>
              <pre className="p-3 text-[11px] font-mono whitespace-pre-wrap break-all leading-relaxed" style={{ color: '#D4C5B5' }}>
                <span style={{ background: 'rgba(74,222,128,0.06)', borderLeft: '2px solid rgba(74,222,128,0.3)', paddingLeft: '8px', display: 'block' }}>
                  {diff.new_code}
                </span>
              </pre>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};


/* ═══════════════════════════════════════════════════════════════ */
/* ═══ DEPLOY TIER SELECTOR + STRIPE CHECKOUT ═══ */
/* ═══════════════════════════════════════════════════════════════ */

const DeployTierCard = ({ tier, name, price, description, selected, onSelect, icon: Icon, locked, lockMessage }) => (
  <button
    onClick={() => onSelect(tier)}
    disabled={locked && tier !== 'free'}
    data-testid={`tier-${tier}`}
    className={`relative p-5 rounded-2xl border-2 text-left transition-all w-full ${
      locked && tier !== 'free' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:scale-[1.01]'
    } ${selected ? (tier === 'free' ? 'border-[#FF6B00] bg-[#FF6B00]/5 shadow-lg shadow-[#FF6B00]/10' : 'border-[#D4AF37] bg-[#D4AF37]/5 shadow-lg shadow-[#D4AF37]/10') : 'border-white/30 bg-white/40'}`}
  >
    {tier === 'free' && (
      <div className="absolute -top-2.5 right-4 text-[8px] font-bold tracking-[2px] px-3 py-0.5 rounded-full"
        style={{ background: 'linear-gradient(135deg, #FF6B00, #1a5c33)', color: '#fff' }}>
        TESTING
      </div>
    )}
    {tier === 'pro' && (
      <div className="absolute -top-2.5 right-4 text-[8px] font-bold tracking-[2px] px-3 py-0.5 rounded-full"
        style={{ background: 'linear-gradient(135deg, #D4AF37, #B88759)', color: '#fff' }}>
        RECOMMENDED
      </div>
    )}
    <div className="flex items-start gap-3">
      <div className="size-10 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: tier === 'free' ? 'rgba(255,107,0,0.1)' : tier === 'pro' ? 'linear-gradient(135deg, #D4AF37, #B88759)' : 'rgba(61,58,57,0.25)' }}>
        <Icon className="size-5" style={{ color: tier === 'free' ? '#FF6B00' : tier === 'pro' ? '#fff' : '#FF6B00' }} />
      </div>
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-bold text-[#1A1A2E]">{name}</h3>
          <span className="text-lg font-bold" style={{color: tier === 'free' ? '#FF6B00' : '#1A1A2E'}}>{price === 0 ? 'FREE' : `$${price}`}</span>
        </div>
        <p className="text-[11px] text-[#888]">{description}</p>
        {locked && (
          <div className="mt-2 flex items-center gap-1.5 text-[10px] font-bold" style={{color: tier === 'free' ? '#FF6B00' : '#D4AF37'}}>
            <Lock className="size-3" />{lockMessage}
          </div>
        )}
      </div>
    </div>
    {selected && (
      <div className="absolute top-3 left-3">
        <CheckCircle className="size-4" style={{color: tier === 'free' ? '#FF6B00' : '#D4AF37'}} />
      </div>
    )}
  </button>
);

/* PIN Modal for Free Tier */
const FreePinModal = ({ open, onClose, onUnlock }) => {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  if (!open) return null;
  const handleUnlock = () => {
    if (pin === '7668') { onUnlock(); onClose(); }
    else { setError('Invalid PIN. Please try again.'); setPin(''); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm mx-4" data-testid="pin-modal">
        <div className="flex items-center gap-3 mb-4">
          <div className="size-10 rounded-xl bg-[#FF6B00]/10 flex items-center justify-center">
            <Unlock className="size-5 text-[#FF6B00]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#1A1A2E]">Unlock Free Tier</h3>
            <p className="text-[11px] text-[#888]">Enter your testing PIN to access free deployment</p>
          </div>
        </div>
        <input data-testid="pin-input" type="password" maxLength={4} placeholder="Enter 4-digit PIN" value={pin}
          onChange={e => { setPin(e.target.value.replace(/\D/g,'')); setError(''); }}
          onKeyDown={e => { if (e.key === 'Enter') handleUnlock(); }}
          className="w-full p-3 rounded-xl border-2 border-[#FF6B00]/20 text-center text-2xl font-mono tracking-[0.5em] outline-none focus:border-[#FF6B00] transition-all bg-[#f8f8f6]"
          style={{letterSpacing:'0.5em'}} autoFocus />
        {error && <p className="text-red-500 text-xs mt-2 text-center">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-3 rounded-xl text-sm font-medium text-[#888] bg-[#f0f0ee] transition-all hover:bg-[#e5e5e2]">Cancel</button>
          <button data-testid="pin-submit" onClick={handleUnlock} disabled={pin.length < 4}
            className="flex-2 py-3 px-6 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-40"
            style={{background:'linear-gradient(135deg, #FF6B00, #1a5c33)'}}>Unlock</button>
        </div>
      </div>
    </div>
  );
};


/* ═══════════════════════════════════════════════════════════════ */
/* ═══ MINI SPARKLINE (SVG) ═══ */
/* ═══════════════════════════════════════════════════════════════ */

const MiniSparkline = ({ data, width = 100, height = 28, color, scoreKey = 'score' }) => {
  if (!data || data.length < 2) return <span className="text-[9px] text-[#888]">--</span>;
  const scores = data.map(d => d[scoreKey]).filter(s => s != null);
  if (scores.length < 2) return <span className="text-[9px] text-[#888]">--</span>;
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1;
  const points = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * width;
    const y = height - ((s - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');
  const lastScore = scores[scores.length - 1];
  const firstScore = scores[0];
  const improving = lastScore >= firstScore;
  const lineColor = color || (improving ? '#4ade80' : '#FF6B6B');

  return (
    <div className="flex items-center gap-2">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="flex-shrink-0">
        <polyline fill="none" stroke={lineColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={points} />
        <circle cx={(scores.length - 1) / (scores.length - 1) * width} cy={height - ((lastScore - min) / range) * (height - 4) - 2}
          r="3" fill={lineColor} />
      </svg>
      <span className="text-[10px] font-bold" style={{ color: lineColor }}>
        {improving ? '+' : ''}{lastScore - firstScore}
      </span>
    </div>
  );
};


/* ═══════════════════════════════════════════════════════════════ */
/* ═══ PULSE HISTORY TAB ═══ */
/* ═══════════════════════════════════════════════════════════════ */

const PulseHistory = ({ token, onRescan }) => {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rescanningUrl, setRescanningUrl] = useState(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API_URL}/api/repair/history`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.history)) {
            setHistory(data);
          }
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    fetchHistory();
  }, [token]);

  const handleRescan = (url) => {
    setRescanningUrl(url);
    onRescan(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-6 text-[#D4AF37] animate-spin" />
        <span className="ml-3 text-sm text-[#888]">Loading scan history…</span>
      </div>
    );
  }

  if (!history || !Array.isArray(history.history) || history.total_scans === 0) {
    return (
      <div className="text-center py-16">
        <History className="size-12 text-[#D4AF37]/30 mx-auto mb-3" />
        <h3 className="text-sm font-bold text-[#1A1A2E] mb-1">No Scan History Yet</h3>
        <p className="text-xs text-[#888]">Analyze a URL to start building your improvement trajectory</p>
      </div>
    );
  }

  const statusBadge = (status) => {
    const map = {
      paid: { bg: '#4ade80', label: 'PAID' },
      deployed: { bg: '#FF6B00', label: 'DEPLOYED' },
      preview: { bg: '#D4B977', label: 'PREVIEW' },
      payment_pending: { bg: '#D4B977', label: 'AWAITING PAY' },
    };
    const s = map[status] || { bg: '#888', label: status?.toUpperCase() || 'SCAN' };
    return (
      <span className="text-[7px] px-1.5 py-0.5 rounded font-bold tracking-wider text-white" style={{ background: s.bg }}>
        {s.label}
      </span>
    );
  };

  return (
    <div data-testid="pulse-history">
      {/* Stats Bar */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
          <div className="text-xl font-bold text-[#1A1A2E]">{history.total_scans}</div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">URLs Scanned</div>
        </div>
        <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
          <div className="text-xl font-bold text-[#D4B977]">{history.total_fixes_all_time}</div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Total Fixes</div>
        </div>
        <div className="p-4 bg-white/50 rounded-xl border border-white/30 text-center">
          <div className="text-xl font-bold text-[#4ade80]">{history.total_deployed}</div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Deployed</div>
        </div>
      </div>

      {/* Overall Health Sparkline + Per-Category Trends */}
      {history.sparkline && history.sparkline.length > 1 && (
        <div className="mb-5 p-4 rounded-xl bg-gradient-to-r from-[#1C1712] to-[#211D17] border border-[#B88759]/20" data-testid="health-sparkline">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4 text-[#D4A574]" />
              <span className="text-[10px] font-bold tracking-[1.5px] text-[#D4A574] uppercase">Overall Health Trend</span>
            </div>
            <span className="text-xs font-bold text-white">{history.sparkline[history.sparkline.length - 1]?.score || 0}%</span>
          </div>
          <MiniSparkline data={history.sparkline} width={400} height={40} />

          {/* Per-Category Sparklines */}
          {(history.sparkline.some(d => d.seo != null) || history.sparkline.some(d => d.geo != null) || history.sparkline.some(d => d.a11y != null)) && (
            <div className="grid grid-cols-3 gap-4 mt-3 pt-3" style={{ borderTop: '1px solid rgba(184,135,89,0.12)' }}>
              {history.sparkline.some(d => d.seo != null) && (
                <div data-testid="sparkline-seo">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-bold tracking-[1px] text-[#4ade80] uppercase">SEO</span>
                    <span className="text-[10px] font-bold text-[#4ade80]">{history.sparkline.filter(d => d.seo != null).slice(-1)[0]?.seo ?? '--'}%</span>
                  </div>
                  <MiniSparkline data={history.sparkline.filter(d => d.seo != null)} width={120} height={24} color="#4ade80" scoreKey="seo" />
                </div>
              )}
              {history.sparkline.some(d => d.geo != null) && (
                <div data-testid="sparkline-geo">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-bold tracking-[1px] text-[#A855F7] uppercase">GEO</span>
                    <span className="text-[10px] font-bold text-[#A855F7]">{history.sparkline.filter(d => d.geo != null).slice(-1)[0]?.geo ?? '--'}%</span>
                  </div>
                  <MiniSparkline data={history.sparkline.filter(d => d.geo != null)} width={120} height={24} color="#A855F7" scoreKey="geo" />
                </div>
              )}
              {history.sparkline.some(d => d.a11y != null) && (
                <div data-testid="sparkline-a11y">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-bold tracking-[1px] text-[#64C8FF] uppercase">A11y</span>
                    <span className="text-[10px] font-bold text-[#64C8FF]">{history.sparkline.filter(d => d.a11y != null).slice(-1)[0]?.a11y ?? '--'}%</span>
                  </div>
                  <MiniSparkline data={history.sparkline.filter(d => d.a11y != null)} width={120} height={24} color="#64C8FF" scoreKey="a11y" />
                </div>
              )}
            </div>
          )}
          <p className="text-[9px] text-[#6B5744] mt-2">ORA tracks SEO, GEO, and Accessibility improvement over time</p>
        </div>
      )}

      {/* Scan Entries */}
      <div className="space-y-2">
        {history.history.map((entry, i) => (
          <div key={entry.url + i}
            className="p-4 rounded-xl bg-white/50 border border-white/30 hover:bg-white/70 transition-all"
            data-testid={`history-entry-${i}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Globe className="size-3.5 text-[#D4AF37] flex-shrink-0" />
                  <span className="text-xs font-bold text-[#1A1A2E] truncate">{entry.url}</span>
                  {entry.deploy_status && statusBadge(entry.deploy_status)}
                  {entry.deploy_tier && (
                    <span className="text-[7px] px-1.5 py-0.5 rounded font-bold tracking-wider"
                      style={{ background: entry.deploy_tier === 'pro' ? 'rgba(212,175,55,0.15)' : 'rgba(61,58,57,0.25)', color: entry.deploy_tier === 'pro' ? '#D4AF37' : '#FF6B00' }}>
                      {entry.deploy_tier.toUpperCase()}
                    </span>
                  )}
                </div>

                {/* Fix Counts */}
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-[9px] text-[#888]">
                    <span className="font-bold text-[#1A1A2E]">{entry.total_fixes}</span> fixes
                  </span>
                  <span className="text-[9px] text-[#4ade80]">{entry.deployed} deployed</span>
                  <span className="text-[9px] text-[#D4B977]">{entry.pending} pending</span>
                  {entry.seo_fixes > 0 && <span className="text-[9px] text-[#888]">{entry.seo_fixes} SEO</span>}
                  {entry.geo_fixes > 0 && <span className="text-[9px] text-[#A855F7]">{entry.geo_fixes} GEO</span>}
                  {entry.a11y_fixes > 0 && <span className="text-[9px] text-[#888]">{entry.a11y_fixes} A11y</span>}
                </div>

                {/* Score Comparison */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-[#888]">Score:</span>
                    <span className="text-xs font-bold" style={{ color: entry.overall_score_before >= 70 ? '#4ade80' : entry.overall_score_before >= 50 ? '#D4B977' : '#FF6B6B' }}>
                      {entry.overall_score_before}
                    </span>
                    <ArrowRight className="size-3 text-[#888]" />
                    <span className="text-xs font-bold" style={{ color: entry.overall_score_after >= 70 ? '#4ade80' : entry.overall_score_after >= 50 ? '#D4B977' : '#FF6B6B' }}>
                      {entry.overall_score_after}
                    </span>
                    {entry.score_improvement > 0 && (
                      <span className="text-[9px] font-bold text-[#4ade80]">+{entry.score_improvement}</span>
                    )}
                  </div>
                  <span className="text-[8px] text-[#aaa]">
                    <Calendar className="size-2.5 inline mr-0.5" />
                    {entry.last_scan?.slice(0, 10)}
                  </span>
                </div>
              </div>

              {/* Re-Scan Button */}
              <button
                onClick={() => handleRescan(entry.url)}
                disabled={rescanningUrl === entry.url}
                data-testid={`rescan-${i}`}
                className="flex-shrink-0 px-3 py-2 rounded-lg text-[10px] font-bold flex items-center gap-1.5 transition-all disabled:opacity-50"
                style={{ background: rescanningUrl === entry.url ? 'rgba(212,175,55,0.15)' : 'rgba(61,58,57,0.15)', border: '1px solid rgba(255,107,0,0.1)', color: '#FF6B00' }}>
                {rescanningUrl === entry.url ? (
                  <><Loader2 className="size-3 animate-spin" /> Comparing with Previous Pulse…</>
                ) : (
                  <><RefreshCw className="size-3" /> Re-Scan</>
                )}
              </button>
            </div>

            {/* GitHub PR Link */}
            {entry.github_pr_url && (
              <a href={entry.github_pr_url} target="_blank" rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1.5 text-[10px] text-[#D4AF37] hover:underline">
                <Github className="size-3" /> View GitHub PR
                <ExternalLink className="size-2.5" />
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};


/* ═══════════════════════════════════════════════════════════════ */
/* ═══ MAIN COMPONENT ═══ */
/* ═══════════════════════════════════════════════════════════════ */

const ORARepairEngine = ({ token }) => {
  const [url, setUrl] = useState('');
  const [seoLoading, setSeoLoading] = useState(false);
  const [a11yLoading, setA11yLoading] = useState(false);
  const [geoLoading, setGeoLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');

  // Results
  const [seoResult, setSeoResult] = useState(null);
  const [a11yResult, setA11yResult] = useState(null);
  const [geoResult, setGeoResult] = useState(null);
  const [fixes, setFixes] = useState([]);

  // Deploy state
  const [deployPreview, setDeployPreview] = useState(null);
  const [deployLoading, setDeployLoading] = useState(false);
  const [selectedTier, setSelectedTier] = useState('basic');
  const [githubConnected, setGithubConnected] = useState(false);
  const [githubRepo, setGithubRepo] = useState('');
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [deployStatus, setDeployStatus] = useState(null); // 'paid', 'deployed'
  const [paymentPolling, setPaymentPolling] = useState(false);

  // Free tier state
  const [freeUnlocked, setFreeUnlocked] = useState(false);
  const [showPinModal, setShowPinModal] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState('');

  // Origin-Write state (Phase 2: The Anchor)
  const [originStatus, setOriginStatus] = useState(null);
  const [originLoading, setOriginLoading] = useState(false);
  const [originResult, setOriginResult] = useState(null);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  // Tab state
  const [activeTab, setActiveTab] = useState('engine'); // 'engine' | 'history' | 'ora-settings' | 'training'
  const [rescanComparison, setRescanComparison] = useState(null);

  // ORA Settings state
  const [oraReviewUrl, setOraReviewUrl] = useState('');
  const [oraSettingsLoading, setOraSettingsLoading] = useState(false);
  const [oraSettingsSaved, setOraSettingsSaved] = useState(false);
  const [oraLeads, setOraLeads] = useState([]);

  // Training tab state
  const [trainingFiles, setTrainingFiles] = useState([]);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [trainLang, setTrainLang] = useState('English');
  const [trainPurpose, setTrainPurpose] = useState('knowledge_base');
  const [trainNotes, setTrainNotes] = useState('');
  const [trainUrl, setTrainUrl] = useState('');
  const [trainUrlLoading, setTrainUrlLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const LANG_OPTIONS = ['English','French','Spanish','Arabic','Hindi','Punjabi','Mandarin','Cantonese','Japanese','Korean','Portuguese','German','Italian','Russian','Turkish','Vietnamese','Thai','Indonesian','Urdu','Bengali','Dutch','Swedish','Polish','Greek','Hebrew','Persian','Other'];
  const PURPOSE_LABELS = { voice_clone: 'Voice Clone', stt_training: 'STT Training', language_pack: 'Language Pack', knowledge_base: 'Knowledge Base' };

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  // Check for payment return from Stripe
  const pollPaymentStatus = useCallback(async (sessionId, deployId, attempt) => {
    if (attempt >= 8) {
      setPaymentPolling(false);
      setError('Payment status check timed out. Please check your email for confirmation.');
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/repair/deploy/status/${sessionId}`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (data.payment_status === 'paid') {
        setPaymentPolling(false);
        setDeployStatus('deployed');
        setFixes(prev => prev.map(f => f.status === 'approved' ? { ...f, status: 'deployed' } : f));
        return;
      }
      setTimeout(() => pollPaymentStatus(sessionId, deployId, attempt + 1), 2500);
    } catch (e) {
      setTimeout(() => pollPaymentStatus(sessionId, deployId, attempt + 1), 3000);
    }
  }, [token]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get('session_id');
    const deployId = params.get('deploy_id');
    const paymentStatus = params.get('payment');

    if (sessionId && paymentStatus === 'success') {
      setPaymentPolling(true);
      pollPaymentStatus(sessionId, deployId, 0);
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [pollPaymentStatus]);

  // Check GitHub connection on mount
  useEffect(() => {
    const checkGithub = async () => {
      try {
        const res = await fetch(`${API_URL}/api/repair/deploy/github-check`, { headers: { Authorization: `Bearer ${token}` } });
        const data = await res.json();
        setGithubConnected(data.github_connected);
      } catch (e) { /* silent */ }
    };
    if (token) checkGithub();
  }, [token]);

  /* ─── Fetch training files ─── */
  const fetchTrainingFiles = useCallback(async () => {
    setTrainingLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/ora/training/files`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (res.ok) setTrainingFiles(data.files || []);
    } catch {}
    setTrainingLoading(false);
  }, [token]);

  useEffect(() => { if (activeTab === 'training' && token) fetchTrainingFiles(); }, [activeTab, token, fetchTrainingFiles]);

  /* ─── Upload training file ─── */
  const handleTrainingUpload = useCallback(async (files) => {
    if (!files || files.length === 0) return;
    setUploadProgress('uploading');
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('language', trainLang);
      formData.append('purpose', trainPurpose);
      formData.append('notes', trainNotes);
      try {
        const res = await fetch(`${API_URL}/api/ora/training/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          setError(d.detail || 'Upload failed');
        }
      } catch { setError('Upload failed'); }
    }
    setUploadProgress(null);
    setTrainNotes('');
    fetchTrainingFiles();
  }, [token, trainLang, trainPurpose, trainNotes, fetchTrainingFiles]);

  /* ─── Add web link ─── */
  const handleAddLink = useCallback(async () => {
    if (!trainUrl.trim()) return;
    setTrainUrlLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/ora/training/link`, {
        method: 'POST', headers,
        body: JSON.stringify({ url: trainUrl.trim(), language: trainLang, purpose: trainPurpose, notes: trainNotes }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Failed to add link');
      } else {
        setTrainUrl('');
        setTrainNotes('');
      }
    } catch { setError('Failed to add link'); }
    setTrainUrlLoading(false);
    fetchTrainingFiles();
  }, [trainUrl, trainLang, trainPurpose, trainNotes, fetchTrainingFiles, headers]);

  /* ─── Delete training file ─── */
  const handleDeleteTraining = useCallback(async (fileId) => {
    try {
      await fetch(`${API_URL}/api/ora/training/${fileId}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      });
      fetchTrainingFiles();
    } catch {}
  }, [token, fetchTrainingFiles]);

  /* ─── Poll payment status ─── */

  /* ─── Generate SEO ─── */
  const handleSEO = useCallback(async () => {
    if (!url.trim()) { setError('Enter a URL to analyze'); return; }
    setSeoLoading(true); setError(''); setDeployPreview(null); setDeployStatus(null);
    try {
      const res = await fetch(`${API_URL}/api/repair/seo/generate`, {
        method: 'POST', headers, body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'SEO analysis failed');
      setSeoResult(data);
      setFixes(prev => {
        const ids = new Set(prev.map(f => f.fix_id));
        return [...prev, ...(data.fixes || []).filter(f => !ids.has(f.fix_id))];
      });
    } catch (e) { setError(e.message); }
    finally { setSeoLoading(false); }
  }, [url, headers]);

  /* ─── Generate Accessibility ─── */
  const handleA11y = useCallback(async () => {
    if (!url.trim()) { setError('Enter a URL to analyze'); return; }
    setA11yLoading(true); setError(''); setDeployPreview(null); setDeployStatus(null);
    try {
      const res = await fetch(`${API_URL}/api/repair/accessibility/generate`, {
        method: 'POST', headers, body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Accessibility analysis failed');
      setA11yResult(data);
      setFixes(prev => {
        const ids = new Set(prev.map(f => f.fix_id));
        return [...prev, ...(data.fixes || []).filter(f => !ids.has(f.fix_id))];
      });
    } catch (e) { setError(e.message); }
    finally { setA11yLoading(false); }
  }, [url, headers]);

  /* ─── Generate GEO ─── */
  const handleGEO = useCallback(async () => {
    if (!url.trim()) { setError('Enter a URL to analyze'); return; }
    setGeoLoading(true); setError(''); setDeployPreview(null); setDeployStatus(null);
    try {
      const res = await fetch(`${API_URL}/api/repair/geo/generate`, {
        method: 'POST', headers, body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'GEO analysis failed');
      setGeoResult(data);
      setFixes(prev => {
        const ids = new Set(prev.map(f => f.fix_id));
        return [...prev, ...(data.fixes || []).filter(f => !ids.has(f.fix_id))];
      });
    } catch (e) { setError(e.message); }
    finally { setGeoLoading(false); }
  }, [url, headers]);

  /* ─── Analyze All ─── */
  const handleAnalyzeBoth = useCallback(async () => {
    if (!url.trim()) { setError('Enter a URL to analyze'); return; }
    setError(''); setDeployPreview(null); setDeployStatus(null);
    // Clear previous results to force fresh display
    setSeoResult(null); setA11yResult(null); setGeoResult(null); setFixes([]);
    setSeoLoading(true); setA11yLoading(true); setGeoLoading(true);

    const [seoFixes, a11yFixes, geoFixes] = await Promise.all([
      (async () => {
        try {
          const res = await fetch(`${API_URL}/api/repair/seo/generate`, { method: 'POST', headers, body: JSON.stringify({ url: url.trim() }) });
          const data = await res.json();
          if (res.ok) { setSeoResult(data); return data.fixes || []; }
        } catch (e) { console.error(e); }
        return [];
      })(),
      (async () => {
        try {
          const res = await fetch(`${API_URL}/api/repair/accessibility/generate`, { method: 'POST', headers, body: JSON.stringify({ url: url.trim() }) });
          const data = await res.json();
          if (res.ok) { setA11yResult(data); return data.fixes || []; }
        } catch (e) { console.error(e); }
        return [];
      })(),
      (async () => {
        try {
          const res = await fetch(`${API_URL}/api/repair/geo/generate`, { method: 'POST', headers, body: JSON.stringify({ url: url.trim() }) });
          const data = await res.json();
          if (res.ok) { setGeoResult(data); return data.fixes || []; }
        } catch (e) { console.error(e); }
        return [];
      })()
    ]);
    setFixes([...seoFixes, ...a11yFixes, ...geoFixes]);
    setSeoLoading(false); setA11yLoading(false); setGeoLoading(false);
  }, [url, headers]);

  /* ─── Approve / Reject ─── */
  const handleApprove = useCallback(async (fixId) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/repair/${fixId}/approve`, { method: 'POST', headers });
      if (res.ok) setFixes(prev => prev.map(f => f.fix_id === fixId ? { ...f, status: 'approved' } : f));
    } catch (e) { console.error(e); }
    finally { setActionLoading(false); }
  }, [headers]);

  const handleReject = useCallback(async (fixId) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/repair/${fixId}/reject`, { method: 'POST', headers });
      if (res.ok) setFixes(prev => prev.map(f => f.fix_id === fixId ? { ...f, status: 'rejected' } : f));
    } catch (e) { console.error(e); }
    finally { setActionLoading(false); }
  }, [headers]);

  /* ─── Deploy Preview (Master Patch) ─── */
  const handleDeployPreview = useCallback(async () => {
    setDeployLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/repair/deploy/preview`, {
        method: 'POST', headers, body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Deploy preview failed');
      setDeployPreview(data);
    } catch (e) { setError(e.message); }
    finally { setDeployLoading(false); }
  }, [url, headers]);

  /* ─── Stripe Checkout ─── */
  const handleCheckout = useCallback(async () => {
    if (!deployPreview) return;
    setCheckoutLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/repair/deploy/checkout`, {
        method: 'POST', headers,
        body: JSON.stringify({
          deploy_id: deployPreview.deploy_id,
          tier: selectedTier,
          origin_url: window.location.origin,
          github_repo: selectedTier === 'pro' ? githubRepo : null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Checkout failed');
      // Redirect to Stripe
      window.location.href = data.checkout_url;
    } catch (e) { setError(e.message); setCheckoutLoading(false); }
  }, [deployPreview, selectedTier, githubRepo, headers]);

  /* ─── Free Tier Deploy ─── */
  const handleFreeDeploy = useCallback(async () => {
    if (!deployPreview) return;
    setActionLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/repair/deploy/free/${deployPreview.deploy_id}`, {
        method: 'POST', headers,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Free deploy failed');
      setDeployStatus('deployed');
      setFixes(prev => prev.map(f => f.status === 'approved' ? { ...f, status: 'deployed' } : f));
    } catch (e) { setError(e.message); }
    finally { setActionLoading(false); }
  }, [deployPreview, headers]);

  /* ─── Download Patch ─── */
  const handleDownload = useCallback(async () => {
    if (!deployPreview) return;
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/repair/deploy/download/${deployPreview.deploy_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Download failed');
      }
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `ora-patch-${deployPreview.deploy_id}.html`;
      a.click();
    } catch (e) { setError(e.message); }
  }, [deployPreview, token]);

  /* ─── Trigger GitHub PR ─── */
  const handleGithubPR = useCallback(async () => {
    if (!deployPreview) return;
    setActionLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/repair/deploy/github-pr/${deployPreview.deploy_id}`, {
        method: 'POST', headers,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'GitHub PR failed');
      setDeployStatus('deployed');
      if (data.github_pr_url) window.open(data.github_pr_url, '_blank');
    } catch (e) { setError(e.message); }
    finally { setActionLoading(false); }
  }, [deployPreview, headers]);

  /* ─── Re-Scan from History ─── */
  const handleRescan = useCallback((rescanUrl) => {
    setUrl(rescanUrl);
    setActiveTab('engine');
    setRescanComparison(rescanUrl);
    setError('');
    setDeployPreview(null);
    setDeployStatus(null);
    setSeoResult(null);
    setA11yResult(null);
    setGeoResult(null);
    setFixes([]);

    // Auto-trigger analysis
    setTimeout(async () => {
      setSeoLoading(true); setA11yLoading(true); setGeoLoading(true);
      const [seoFx, a11yFx, geoFx] = await Promise.all([
        (async () => {
          try {
            const res = await fetch(`${API_URL}/api/repair/seo/generate`, { method: 'POST', headers, body: JSON.stringify({ url: rescanUrl }) });
            const data = await res.json();
            if (res.ok) { setSeoResult(data); return data.fixes || []; }
          } catch (e) { console.error(e); }
          return [];
        })(),
        (async () => {
          try {
            const res = await fetch(`${API_URL}/api/repair/accessibility/generate`, { method: 'POST', headers, body: JSON.stringify({ url: rescanUrl }) });
            const data = await res.json();
            if (res.ok) { setA11yResult(data); return data.fixes || []; }
          } catch (e) { console.error(e); }
          return [];
        })(),
        (async () => {
          try {
            const res = await fetch(`${API_URL}/api/repair/geo/generate`, { method: 'POST', headers, body: JSON.stringify({ url: rescanUrl }) });
            const data = await res.json();
            if (res.ok) { setGeoResult(data); return data.fixes || []; }
          } catch (e) { console.error(e); }
          return [];
        })()
      ]);
      setFixes([...seoFx, ...a11yFx, ...geoFx]);
      setSeoLoading(false); setA11yLoading(false); setGeoLoading(false);
      setRescanComparison(null);
    }, 100);
  }, [headers]);

  /* ─── Origin-Write: Commit to Origin (Phase 2: The Anchor) ─── */
  const handleOriginCommit = useCallback(async () => {
    if (!url) return;
    setOriginLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/repair/origin/commit`, {
        method: 'POST', headers, body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Origin commit failed');
      setOriginResult(data);
      setOriginStatus(data);
    } catch (e) { setError(e.message); }
    finally { setOriginLoading(false); }
  }, [url, headers]);

  const handleOriginVerify = useCallback(async () => {
    if (!url) return;
    setVerifyLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/repair/origin/verify`, {
        method: 'POST', headers, body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Verification failed');
      setVerifyResult(data);
    } catch (e) { setError(e.message); }
    finally { setVerifyLoading(false); }
  }, [url, headers]);

  const handleCheckOriginStatus = useCallback(async () => {
    if (!url) return;
    try {
      const res = await fetch(`${API_URL}/api/repair/origin/status?url=${encodeURIComponent(url)}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setOriginStatus(data);
      }
    } catch (e) { /* silent */ }
  }, [url, headers]);

  const seoFixes = fixes.filter(f => ['title', 'meta_description', 'h1', 'og_title', 'og_description'].includes(f.fix_type));
  const geoFixes = fixes.filter(f => ['json_ld_base', 'json_ld_faq', 'json_ld_article', 'ai_summary', 'citation_block', 'semantic_html'].includes(f.fix_type));
  const a11yFixes = fixes.filter(f => f.fix_type && !['title', 'meta_description', 'h1', 'og_title', 'og_description', 'json_ld_base', 'json_ld_faq', 'json_ld_article', 'ai_summary', 'citation_block', 'semantic_html'].includes(f.fix_type));
  const approvedCount = fixes.filter(f => f.status === 'approved').length;
  const pendingCount = fixes.filter(f => f.status === 'pending_approval').length;
  const deployedCount = fixes.filter(f => f.status === 'deployed').length;
  const isAnalyzing = seoLoading || a11yLoading || geoLoading;
  const hasApprovedFixes = approvedCount > 0;

  // Check origin status when URL changes and fixes are deployed
  useEffect(() => { if (url && deployedCount > 0) handleCheckOriginStatus(); }, [url, deployedCount]);

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">

        {/* ── Header + Tabs ── */}
        <div className="mb-6" data-testid="repair-engine-header">
          <h1 className="text-xl font-bold text-[#1A1A2E] tracking-wider mb-1">ORA Repair Engine</h1>
          <p className="text-xs text-[#888] mb-4">AI-powered SEO + GEO + Accessibility via Gemini 3.1 Pro &amp; Nano Banana 2</p>
          <div className="flex gap-1 p-0.5 bg-white/30 rounded-lg w-fit" data-testid="repair-tabs">
            <button onClick={() => setActiveTab('engine')} data-testid="tab-engine"
              className={`px-4 py-2 rounded-md text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 ${
                activeTab === 'engine' ? 'bg-white shadow-sm text-[#1A1A2E]' : 'text-[#888] hover:text-[#1A1A2E]'
              }`}>
              <Wrench className="size-3.5" /> Repair Engine
            </button>
            <button onClick={() => setActiveTab('history')} data-testid="tab-history"
              className={`px-4 py-2 rounded-md text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 ${
                activeTab === 'history' ? 'bg-white shadow-sm text-[#1A1A2E]' : 'text-[#888] hover:text-[#1A1A2E]'
              }`}>
              <History className="size-3.5" /> Pulse History
            </button>
            <button onClick={() => {
              setActiveTab('ora-settings');
              fetch(`${API_URL}/api/ora/settings`).then(r=>r.json()).then(d=>{setOraReviewUrl(d.google_review_url||'');}).catch(()=>{});
              fetch(`${API_URL}/api/ora/leads`).then(r=>r.json()).then(d=>{setOraLeads(d.leads||[]);}).catch(()=>{});
            }} data-testid="tab-ora-settings"
              className={`px-4 py-2 rounded-md text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 ${
                activeTab === 'ora-settings' ? 'bg-white shadow-sm text-[#1A1A2E]' : 'text-[#888] hover:text-[#1A1A2E]'
              }`}>
              <Settings className="size-3.5" /> ORA Settings
            </button>
            <button onClick={() => setActiveTab('training')} data-testid="tab-training"
              className={`px-4 py-2 rounded-md text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 ${
                activeTab === 'training' ? 'bg-white shadow-sm text-[#1A1A2E]' : 'text-[#888] hover:text-[#1A1A2E]'
              }`}>
              <Languages className="size-3.5" /> Training
            </button>
          </div>
        </div>

        {/* ── Re-Scan Comparison Banner ── */}
        {rescanComparison && (
          <div className="mb-4 p-4 rounded-xl bg-[#D4AF37]/10 border border-[#D4AF37]/30 flex items-center gap-3" data-testid="rescan-comparison">
            <Loader2 className="size-5 text-[#D4AF37] animate-spin" />
            <div>
              <span className="text-sm font-bold text-[#1A1A2E]">Comparing with Previous Pulse…</span>
              <p className="text-[10px] text-[#888]">ORA is re-analyzing {rescanComparison} and comparing against historical data</p>
            </div>
          </div>
        )}

        {/* ── PULSE HISTORY TAB ── */}
        {activeTab === 'history' && (
          <PulseHistory token={token} onRescan={handleRescan} />
        )}

        {/* ── ORA SETTINGS TAB ── */}
        {activeTab === 'ora-settings' && (
          <div className="space-y-6" data-testid="ora-settings-panel">
            {/* Google Review URL */}
            <div className="p-5 rounded-2xl border border-white/30 bg-white/50 backdrop-blur-sm">
              <div className="flex items-center gap-2 mb-4">
                <div className="size-8 rounded-lg flex items-center justify-center bg-[#D4AF37]/10">
                  <Star className="size-4 text-[#D4AF37]" />
                </div>
                <div>
                  <h3 className="text-xs font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Google Review URL</h3>
                  <p className="text-[10px] text-[#888]">Destination link for the PWA gamified 5-star review unlock</p>
                </div>
              </div>
              <div className="flex gap-2">
                <input
                  data-testid="ora-google-review-url"
                  type="url"
                  value={oraReviewUrl}
                  onChange={e => { setOraReviewUrl(e.target.value); setOraSettingsSaved(false); }}
                  placeholder="https://g.page/r/YOUR_BUSINESS/review"
                  className="flex-1 px-3 py-2 rounded-lg border border-[#FF6B00]/15 bg-white text-sm text-[#1A1A2E] placeholder:text-[#bbb] focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/30"
                />
                <button
                  data-testid="ora-save-review-url"
                  disabled={oraSettingsLoading}
                  onClick={async () => {
                    setOraSettingsLoading(true);
                    try {
                      await fetch(`${API_URL}/api/ora/settings`, {
                        method: 'PUT',
                        headers,
                        body: JSON.stringify({ google_review_url: oraReviewUrl })
                      });
                      setOraSettingsSaved(true);
                    } catch {}
                    setOraSettingsLoading(false);
                  }}
                  className="px-4 py-2 rounded-lg bg-[#D4AF37] text-white text-xs font-bold hover:bg-[#C9A22E] transition-all flex items-center gap-1.5 disabled:opacity-50"
                >
                  {oraSettingsLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                  {oraSettingsSaved ? 'Saved' : 'Save'}
                </button>
              </div>
            </div>

            {/* Captured Leads */}
            <div className="p-5 rounded-2xl border border-white/30 bg-white/50 backdrop-blur-sm">
              <div className="flex items-center gap-2 mb-4">
                <div className="size-8 rounded-lg flex items-center justify-center bg-[#4ade80]/10">
                  <Users className="size-4 text-[#4ade80]" />
                </div>
                <div>
                  <h3 className="text-xs font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">PWA Captured Leads</h3>
                  <p className="text-[10px] text-[#888]">{oraLeads.length} lead{oraLeads.length !== 1 ? 's' : ''} captured from ORA PWA</p>
                </div>
              </div>
              {oraLeads.length === 0 ? (
                <p className="text-xs text-[#888] text-center py-6">No leads captured yet. Share your PWA link to start collecting.</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-white/40">
                  <table className="w-full text-xs" data-testid="ora-leads-table">
                    <thead>
                      <tr className="bg-[#1A1A2E]/5">
                        <th className="text-left px-3 py-2 font-bold text-[#888] uppercase tracking-wider">Name</th>
                        <th className="text-left px-3 py-2 font-bold text-[#888] uppercase tracking-wider">Email</th>
                        <th className="text-left px-3 py-2 font-bold text-[#888] uppercase tracking-wider">Referrals</th>
                        <th className="text-left px-3 py-2 font-bold text-[#888] uppercase tracking-wider">Captured</th>
                      </tr>
                    </thead>
                    <tbody>
                      {oraLeads.map((lead, i) => (
                        <tr key={i} className="border-t border-white/30 hover:bg-white/40 transition-colors">
                          <td className="px-3 py-2 text-[#1A1A2E] font-medium">{lead.full_name || '—'}</td>
                          <td className="px-3 py-2 text-[#888]">{lead.email || '—'}</td>
                          <td className="px-3 py-2">
                            <span className="px-2 py-0.5 rounded-full bg-[#4ade80]/15 text-[#FF6B00] font-bold text-[10px]">
                              {(lead.referrals || []).length}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-[#888]">{lead.captured_at ? new Date(lead.captured_at).toLocaleDateString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TRAINING TAB ── */}
        {activeTab === 'training' && (
          <div className="space-y-5" data-testid="training-panel">

            {/* Upload & Link Controls */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

              {/* File Upload */}
              <div className="p-5 rounded-2xl border border-white/30 bg-white/50 backdrop-blur-sm">
                <div className="flex items-center gap-2 mb-3">
                  <div className="size-8 rounded-lg flex items-center justify-center bg-[#FF6B00]/10">
                    <Upload className="size-4 text-[#FF6B00]" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Upload Training Data</h3>
                    <p className="text-[10px] text-[#888]">Audio (MP3, WAV), Documents (PDF, TXT, DOCX), Data (JSON, CSV)</p>
                  </div>
                </div>

                {/* Drag & Drop Zone */}
                <div
                  data-testid="training-dropzone"
                  onDragOver={e => { e.preventDefault(); setDragActive(true); }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={e => { e.preventDefault(); setDragActive(false); handleTrainingUpload(e.dataTransfer.files); }}
                  onClick={() => document.getElementById('training-file-input').click()}
                  className={`relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                    dragActive ? 'border-[#FF6B00] bg-[#FF6B00]/5' : 'border-[#FF6B00]/20 hover:border-[#FF6B00]/40 bg-white/30'
                  }`}
                >
                  <input id="training-file-input" type="file" multiple className="hidden"
                    accept=".mp3,.wav,.m4a,.ogg,.flac,.aac,.pdf,.docx,.doc,.txt,.md,.csv,.xlsx,.json,.xml,.yaml,.pptx,.webm"
                    onChange={e => handleTrainingUpload(e.target.files)} />
                  {uploadProgress ? (
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="size-5 text-[#FF6B00] animate-spin" />
                      <span className="text-sm text-[#FF6B00] font-medium">Uploading…</span>
                    </div>
                  ) : (
                    <>
                      <Upload className="size-8 text-[#888] mx-auto mb-2" />
                      <p className="text-xs text-[#1A1A2E] font-medium">Drop files here or click to browse</p>
                      <p className="text-[10px] text-[#888] mt-1">Max 50MB per file</p>
                    </>
                  )}
                </div>
              </div>

              {/* Web Link */}
              <div className="p-5 rounded-2xl border border-white/30 bg-white/50 backdrop-blur-sm">
                <div className="flex items-center gap-2 mb-3">
                  <div className="size-8 rounded-lg flex items-center justify-center bg-[#64C8FF]/10">
                    <Globe className="size-4 text-[#64C8FF]" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Add Web Link</h3>
                    <p className="text-[10px] text-[#888]">Paste any URL, ORA crawls and learns from the content</p>
                  </div>
                </div>
                <div className="flex gap-2 mb-3">
                  <input
                    data-testid="training-url-input"
                    type="url"
                    value={trainUrl}
                    onChange={e => setTrainUrl(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleAddLink()}
                    placeholder="https://example.com/page-to-learn-from"
                    className="flex-1 px-3 py-2 rounded-lg border border-[#FF6B00]/15 bg-white text-sm text-[#1A1A2E] placeholder:text-[#bbb] focus:outline-none focus:ring-2 focus:ring-[#64C8FF]/30"
                  />
                  <button
                    data-testid="training-add-link-btn"
                    disabled={trainUrlLoading || !trainUrl.trim()}
                    onClick={handleAddLink}
                    className="px-4 py-2 rounded-lg bg-[#64C8FF] text-white text-xs font-bold hover:bg-[#4ab8f0] transition-all flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {trainUrlLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Link className="size-3.5" />}
                    Crawl
                  </button>
                </div>
                <div className="flex gap-2">
                  <input
                    data-testid="training-notes-input"
                    type="text"
                    value={trainNotes}
                    onChange={e => setTrainNotes(e.target.value)}
                    placeholder="Notes (optional) — e.g. 'French product catalog'"
                    className="flex-1 px-3 py-2 rounded-lg border border-[#FF6B00]/15 bg-white text-xs text-[#1A1A2E] placeholder:text-[#bbb] focus:outline-none focus:ring-2 focus:ring-[#64C8FF]/30"
                  />
                </div>
              </div>
            </div>

            {/* Language & Purpose Selectors */}
            <div className="flex gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <label className="text-[10px] font-bold text-[#888] uppercase tracking-wider">Language</label>
                <select data-testid="training-lang-select" value={trainLang} onChange={e => setTrainLang(e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-[#FF6B00]/15 bg-white text-xs text-[#1A1A2E] focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/30">
                  {LANG_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-[10px] font-bold text-[#888] uppercase tracking-wider">Purpose</label>
                <select data-testid="training-purpose-select" value={trainPurpose} onChange={e => setTrainPurpose(e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-[#FF6B00]/15 bg-white text-xs text-[#1A1A2E] focus:outline-none focus:ring-2 focus:ring-[#D4AF37]/30">
                  {Object.entries(PURPOSE_LABELS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            </div>

            {/* Training Files List */}
            <div className="p-5 rounded-2xl border border-white/30 bg-white/50 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="size-8 rounded-lg flex items-center justify-center bg-[#D4AF37]/10">
                    <BookOpen className="size-4 text-[#D4AF37]" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Training Library</h3>
                    <p className="text-[10px] text-[#888]">{trainingFiles.length} item{trainingFiles.length !== 1 ? 's' : ''} in ORA's knowledge base</p>
                  </div>
                </div>
                <button onClick={fetchTrainingFiles} disabled={trainingLoading}
                  className="p-2 rounded-lg hover:bg-white/60 transition-all">
                  <RefreshCw className={`size-3.5 text-[#888] ${trainingLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {trainingFiles.length === 0 ? (
                <p className="text-xs text-[#888] text-center py-8">No training data yet. Upload files or paste links above to teach ORA.</p>
              ) : (
                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                  {trainingFiles.map(f => (
                    <div key={f.file_id} data-testid={`training-item-${f.file_id}`}
                      className="flex items-center gap-3 p-3 rounded-xl bg-white/40 border border-white/30 hover:bg-white/60 transition-all group">
                      {/* Icon */}
                      <div className={`size-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        f.file_category === 'audio' ? 'bg-[#FF6B00]/10' :
                        f.file_category === 'web' ? 'bg-[#64C8FF]/10' : 'bg-[#4ade80]/10'
                      }`}>
                        {f.file_category === 'audio' ? <Music className="size-4 text-[#FF6B00]" /> :
                         f.file_category === 'web' ? <Globe className="size-4 text-[#64C8FF]" /> :
                         <FileText className="size-4 text-[#4ade80]" />}
                      </div>
                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-[#1A1A2E] truncate">{f.filename || f.url || 'Unknown'}</span>
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#D4AF37]/10 text-[#D4AF37] flex-shrink-0">{f.language}</span>
                        </div>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-[10px] text-[#888]">{PURPOSE_LABELS[f.purpose] || f.purpose}</span>
                          <span className="text-[10px] text-[#888]">{f.file_size > 1024 * 1024 ? `${(f.file_size / (1024*1024)).toFixed(1)}MB` : f.file_size > 1024 ? `${(f.file_size / 1024).toFixed(0)}KB` : `${f.file_size}B`}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                            f.status === 'crawled' ? 'bg-[#4ade80]/15 text-[#FF6B00]' :
                            f.status === 'uploaded' ? 'bg-[#64C8FF]/15 text-[#3a9fd4]' :
                            f.status === 'crawl_failed' ? 'bg-red-100 text-red-600' : 'bg-[#888]/10 text-[#888]'
                          }`}>{f.status}</span>
                          {f.notes && <span className="text-[10px] text-[#aaa] italic truncate max-w-[120px]">{f.notes}</span>}
                        </div>
                      </div>
                      {/* Delete */}
                      <button onClick={() => handleDeleteTraining(f.file_id)} data-testid={`delete-training-${f.file_id}`}
                        className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-50 transition-all">
                        <Trash2 className="size-3.5 text-red-400" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── ENGINE TAB ── */}
        {activeTab === 'engine' && (<>

        {/* ── Payment Success Banner ── */}
        {paymentPolling && (
          <div className="mb-4 p-4 rounded-xl bg-[#D4AF37]/10 border border-[#D4AF37]/30 flex items-center gap-3" data-testid="payment-polling">
            <Loader2 className="size-5 text-[#D4AF37] animate-spin" />
            <span className="text-sm font-bold text-[#1A1A2E]">Verifying payment…</span>
          </div>
        )}
        {deployStatus === 'paid' && (
          <div className="mb-4 p-4 rounded-xl bg-[#4ade80]/10 border border-[#4ade80]/30 flex items-center justify-between" data-testid="payment-success">
            <div className="flex items-center gap-3">
              <CheckCircle className="size-5 text-[#4ade80]" />
              <span className="text-sm font-bold text-[#1A1A2E]">Payment confirmed, your fixes are ready!</span>
            </div>
            <div className="flex gap-2">
              <button onClick={handleDownload} data-testid="download-patch-btn"
                className="px-4 py-2 rounded-lg bg-white border border-[#FF6B00]/20 text-[#FF6B00] text-xs font-bold hover:bg-[#4ade80]/10 transition-all flex items-center gap-1.5">
                <Download className="size-3.5" /> Download Patch
              </button>
              {selectedTier === 'pro' && githubConnected && (
                <button onClick={handleGithubPR} disabled={actionLoading} data-testid="github-pr-btn"
                  className="px-4 py-2 rounded-lg text-white text-xs font-bold hover:opacity-90 transition-all flex items-center gap-1.5 disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #D4AF37, #B88759)' }}>
                  <Github className="size-3.5" /> Push to GitHub
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── URL Input ── */}
        <div className="mb-6 p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-2xl" data-testid="repair-url-input">
          <label className="block text-[10px] text-[#888] mb-2 uppercase tracking-[1.5px] font-bold">Target URL</label>
          <div className="flex gap-3">
            <input type="url" value={url} onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyzeBoth()}
              placeholder="https://example.com"
              className="flex-1 px-4 py-3 bg-white/60 border border-[#FF6B00]/20 rounded-lg text-[#1A1A2E] placeholder-[#aaa] text-sm focus:outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/20"
              disabled={isAnalyzing} data-testid="repair-url-field" />
            <button onClick={handleAnalyzeBoth} disabled={isAnalyzing} data-testid="analyze-all-btn"
              className="px-6 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-white rounded-lg font-bold text-sm hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-[#D4AF37]/20">
              {isAnalyzing ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {isAnalyzing ? 'Analyzing...' : 'Analyze & Generate Fixes'}
            </button>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={handleSEO} disabled={isAnalyzing} data-testid="analyze-seo-btn"
              className="flex-1 py-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              style={{ background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)', color: '#FF6B00' }}>
              {seoLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Eye className="size-3.5" />}
              {seoLoading ? 'SEO...' : 'SEO Only'}
            </button>
            <button onClick={handleGEO} disabled={isAnalyzing} data-testid="analyze-geo-btn"
              className="flex-1 py-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              style={{ background: 'rgba(168,85,247,0.08)', border: '1px solid rgba(168,85,247,0.2)', color: '#7C3AED' }}>
              {geoLoading ? <Loader2 className="size-3.5 animate-spin" /> : <BrainCircuit className="size-3.5" />}
              {geoLoading ? 'GEO...' : 'GEO Optimize'}
            </button>
            <button onClick={handleA11y} disabled={isAnalyzing} data-testid="analyze-a11y-btn"
              className="flex-1 py-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              style={{ background: 'rgba(100,200,255,0.08)', border: '1px solid rgba(100,200,255,0.2)', color: '#3B82F6' }}>
              {a11yLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Accessibility className="size-3.5" />}
              {a11yLoading ? 'A11y...' : 'A11y Only'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50/80 border border-red-200/50 rounded-lg text-red-600 text-sm flex items-center gap-2" data-testid="repair-error">
            <AlertTriangle className="size-4 flex-shrink-0" />{error}
          </div>
        )}

        {/* ── Before / After Score Cards ── */}
        {(seoResult || a11yResult || geoResult) && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4" data-testid="score-comparison">
            {seoResult && <BeforeAfterCard title="SEO" icon={Eye} before={seoResult.seo_score_before} after={seoResult.seo_score_after} fixCount={seoResult.total_fixes} color="#4ade80" />}
            {geoResult && <BeforeAfterCard title="GEO" icon={BrainCircuit} before={geoResult.geo_score_before} after={geoResult.geo_score_after} fixCount={geoResult.total_fixes} color="#A855F7" />}
            {a11yResult && <BeforeAfterCard title="Accessibility" icon={Accessibility} before={a11yResult.accessibility_score_before} after={a11yResult.accessibility_score_after} fixCount={a11yResult.total_fixes} color="#64C8FF" />}
          </div>
        )}

        {/* ── Previously Fixed Banner ── */}
        {((seoResult?.previously_fixed > 0) || (a11yResult?.previously_fixed > 0) || (geoResult?.previously_fixed > 0)) && (
          <div className="mb-4 p-3 rounded-xl bg-[#4ade80]/10 border border-[#4ade80]/30 flex items-center gap-3" data-testid="previously-fixed-banner">
            <CheckCircle className="size-5 text-[#4ade80]" />
            <div>
              <span className="text-sm font-bold text-[#1A1A2E]">
                {(seoResult?.previously_fixed || 0) + (a11yResult?.previously_fixed || 0) + (geoResult?.previously_fixed || 0)} issues previously fixed
              </span>
              <p className="text-[10px] text-[#888]">These fixes were approved/deployed in earlier scans and are excluded from new results</p>
            </div>
          </div>
        )}

        {/* ── No New Issues Banner ── */}
        {(seoResult || a11yResult || geoResult) && fixes.length === 0 && !isAnalyzing && (
          <div className="text-center py-12" data-testid="all-clear-banner">
            <CheckCircle className="size-12 text-[#4ade80] mx-auto mb-3" />
            <h3 className="text-lg font-bold text-[#1A1A2E] mb-1">All Clear!</h3>
            <p className="text-sm text-[#888]">No new issues detected. {((seoResult?.previously_fixed || 0) + (a11yResult?.previously_fixed || 0) + (geoResult?.previously_fixed || 0)) > 0 ? 'Previous repairs are holding strong.' : 'This page is well optimized.'}</p>
          </div>
        )}

        {/* ── Stats Bar ── */}
        {fixes.length > 0 && (
          <div className="flex items-center gap-4 mb-4 px-2" data-testid="fix-stats">
            <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">{fixes.length} Total</span>
            <span className="text-[10px] font-bold text-[#D4B977]">{pendingCount} Pending</span>
            <span className="text-[10px] font-bold text-[#4ade80]">{approvedCount} Approved</span>
            {deployedCount > 0 && <span className="text-[10px] font-bold text-[#FF6B00]">{deployedCount} Deployed</span>}
          </div>
        )}

        {/* ── SEO Fixes ── */}
        {seoFixes.length > 0 && (
          <div className="mb-6" data-testid="seo-fixes-section">
            <div className="flex items-center gap-2 mb-3">
              <Eye className="size-4 text-[#4ade80]" />
              <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">SEO FIXES</h2>
              <span className="text-[9px] px-2 py-0.5 rounded-full bg-[#4ade80]/10 text-[#FF6B00] font-bold">Gemini 3.1 Pro</span>
            </div>
            {seoFixes.map(fix => <FixItem key={fix.fix_id} fix={fix} onApprove={handleApprove} onReject={handleReject} loading={actionLoading} />)}
          </div>
        )}

        {/* ── GEO Fixes ── */}
        {geoFixes.length > 0 && (
          <div className="mb-6" data-testid="geo-fixes-section">
            <div className="flex items-center gap-2 mb-3">
              <BrainCircuit className="size-4 text-[#A855F7]" />
              <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">GEO FIXES</h2>
              <span className="text-[9px] px-2 py-0.5 rounded-full bg-[#A855F7]/10 text-[#7C3AED] font-bold">Generative Engine Optimization</span>
            </div>
            {geoFixes.map(fix => <FixItem key={fix.fix_id} fix={fix} onApprove={handleApprove} onReject={handleReject} loading={actionLoading} />)}
          </div>
        )}

        {/* ── Accessibility Fixes ── */}
        {a11yFixes.length > 0 && (
          <div className="mb-6" data-testid="a11y-fixes-section">
            <div className="flex items-center gap-2 mb-3">
              <Accessibility className="size-4 text-[#64C8FF]" />
              <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">ACCESSIBILITY FIXES</h2>
              <span className="text-[9px] px-2 py-0.5 rounded-full bg-[#64C8FF]/10 text-[#3B82F6] font-bold">Nano Banana 2</span>
            </div>
            {a11yFixes.map(fix => <FixItem key={fix.fix_id} fix={fix} onApprove={handleApprove} onReject={handleReject} loading={actionLoading} />)}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════ */}
        {/* ═══ DEPLOY SUCCESS STATE ═══ */}
        {/* ═══════════════════════════════════════════════════════ */}
        {deployStatus && (
          <div className="mb-6 p-6 rounded-2xl border-2 border-[#4ade80]/30 bg-gradient-to-br from-[#4ade80]/5 to-white/50" data-testid="deploy-success">
            <div className="flex items-center gap-3 mb-4">
              <div className="size-10 rounded-xl flex items-center justify-center bg-[#4ade80]/20">
                <CheckCircle className="size-5 text-[#4ade80]" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">FIXES DEPLOYED SUCCESSFULLY</h2>
                <p className="text-[10px] text-[#888]">{deployPreview?.fix_count || approvedCount} fixes have been applied</p>
              </div>
            </div>
            <div className="flex gap-3">
              {deployPreview && (
                <button onClick={handleDownload} data-testid="download-patch-btn"
                  className="px-5 py-2.5 rounded-lg font-bold text-sm text-white hover:opacity-90 transition-all flex items-center gap-2"
                  style={{ background: 'linear-gradient(135deg, #FF6B00, #1a5c33)' }}>
                  <Download className="size-4" /> Download Patch File
                </button>
              )}
              <button onClick={() => { setDeployStatus(null); setDeployPreview(null); setSeoResult(null); setA11yResult(null); setGeoResult(null); setFixes([]); }} data-testid="new-scan-btn"
                className="px-5 py-2.5 rounded-lg font-bold text-sm text-[#1A1A2E] hover:bg-white/60 transition-all flex items-center gap-2 border border-[#D4AF37]/30">
                <RefreshCw className="size-4" /> New Scan
              </button>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════ */}
        {/* ═══ DOUBLE-LOCK: ORIGIN-WRITE (Phase 2: The Anchor) ═══ */}
        {/* ═══════════════════════════════════════════════════════ */}
        {deployedCount > 0 && (
          <div className="mb-6 p-6 rounded-2xl border-2 border-[#FF6B00]/30 bg-gradient-to-br from-[#FF6B00]/5 to-white/50" data-testid="origin-write-section">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #FF6B00, #1a5c33)' }}>
                  <Lock className="size-5 text-white" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">DOUBLE-LOCK: COMMIT TO ORIGIN</h2>
                  <p className="text-[10px] text-[#888]">
                    Phase 2 — Write {deployedCount} fixes into source code so Google sees them
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Phase indicators */}
                <span className="px-2 py-1 rounded text-[8px] font-bold" style={{ background: 'rgba(74,222,128,0.15)', color: '#4ade80' }}>
                  Phase 1: PIXEL ACTIVE
                </span>
                <span className={`px-2 py-1 rounded text-[8px] font-bold ${
                  originStatus?.status === 'committed'
                    ? 'bg-[rgba(74,222,128,0.15)] text-[#4ade80]'
                    : 'bg-[rgba(212,175,55,0.15)] text-[#D4AF37]'
                }`}>
                  Phase 2: {originStatus?.status === 'committed' ? 'ANCHORED' : 'PENDING'}
                </span>
              </div>
            </div>

            {/* Origin commit result */}
            {originResult && (
              <div className="mb-4 p-4 rounded-xl border border-[#4ade80]/20 bg-white/60">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle className="size-4 text-[#4ade80]" />
                  <span className="text-xs font-bold text-[#1A1A2E]">
                    {originResult.fix_count} fixes compiled to origin-ready files
                  </span>
                </div>

                {/* Serve URLs */}
                {originResult.serve_urls && (
                  <div className="mb-3 space-y-1.5">
                    <p className="text-[9px] font-bold text-[#888] tracking-wider uppercase">Static Serve URLs (add to your site):</p>
                    {Object.entries(originResult.serve_urls).map(([key, path]) => (
                      <div key={key} className="flex items-center gap-2 p-2 bg-[#1A1A2E]/5 rounded-lg">
                        <code className="text-[9px] font-mono text-[#FF6B00] flex-1 truncate">{API_URL}{path}</code>
                        <button onClick={() => navigator.clipboard.writeText(`${API_URL}${path}`)}
                          className="text-[8px] px-2 py-1 rounded bg-[#FF6B00]/10 text-[#FF6B00] font-bold hover:bg-[#FF6B00]/20 transition-all"
                          data-testid={`copy-${key}-url`}>
                          COPY
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Integration instructions */}
                {originResult.instructions && (
                  <details className="text-[10px]">
                    <summary className="cursor-pointer font-bold text-[#D4AF37] hover:text-[#B88759]">
                      View Integration Instructions
                    </summary>
                    <div className="mt-2 space-y-3">
                      {Object.entries(originResult.instructions).map(([platform, info]) => (
                        <div key={platform} className="p-3 bg-white/80 rounded-lg">
                          <h4 className="font-bold text-[#1A1A2E] mb-1">{info.title}</h4>
                          {info.steps.map((step, i) => (
                            <p key={i} className="text-[#888] ml-2">{step}</p>
                          ))}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}

            {/* Verification result */}
            {verifyResult && (
              <div className={`mb-4 p-4 rounded-xl border ${
                verifyResult.match ? 'border-[#4ade80]/30 bg-[#4ade80]/5' : 'border-[#D4AF37]/30 bg-[#D4AF37]/5'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {verifyResult.match
                    ? <CheckCircle className="size-4 text-[#4ade80]" />
                    : <AlertTriangle className="size-4 text-[#D4AF37]" />}
                  <span className="text-xs font-bold text-[#1A1A2E]">{verifyResult.message}</span>
                </div>
                {verifyResult.external_scores && (
                  <div className="grid grid-cols-4 gap-2 mt-2">
                    {Object.entries(verifyResult.external_scores).map(([cat, score]) => (
                      <div key={cat} className="text-center p-2 rounded-lg bg-white/60">
                        <div className={`text-sm font-bold ${score >= 90 ? 'text-[#4ade80]' : score >= 70 ? 'text-[#D4AF37]' : 'text-[#FF6B6B]'}`}>
                          {score}
                        </div>
                        <div className="text-[8px] text-[#888] capitalize">{cat.replace(/-/g, ' ')}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-3">
              <button onClick={handleOriginCommit} disabled={originLoading} data-testid="commit-origin-btn"
                className="px-5 py-2.5 rounded-lg font-bold text-sm text-white hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
                style={{ background: 'linear-gradient(135deg, #FF6B00, #1a5c33)' }}>
                {originLoading ? <Loader2 className="size-4 animate-spin" /> : <Lock className="size-4" />}
                {originLoading ? 'Compiling...' : originResult ? 'Re-Compile Origin' : 'Commit to Origin'}
              </button>

              {originResult && (
                <button onClick={handleOriginVerify} disabled={verifyLoading} data-testid="verify-origin-btn"
                  className="px-5 py-2.5 rounded-lg font-bold text-sm text-[#1A1A2E] hover:bg-white/60 transition-all disabled:opacity-50 flex items-center gap-2 border border-[#D4AF37]/30">
                  {verifyLoading ? <Loader2 className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
                  {verifyLoading ? 'Scanning Google...' : 'Verify with PageSpeed'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════ */}
        {/* ═══ DEPLOY ALL SECTION ═══ */}
        {/* ═══════════════════════════════════════════════════════ */}
        {hasApprovedFixes && !deployStatus && (
          <div className="mb-6 p-6 rounded-2xl border-2 border-[#D4AF37]/30 bg-gradient-to-br from-[#D4AF37]/5 to-white/50" data-testid="deploy-section">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #D4AF37, #B88759)' }}>
                  <Zap className="size-5 text-white" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">DEPLOY ALL APPROVED FIXES</h2>
                  <p className="text-[10px] text-[#888]">{approvedCount} fixes ready for deployment</p>
                </div>
              </div>
              {!deployPreview && (
                <button onClick={handleDeployPreview} disabled={deployLoading} data-testid="preview-deploy-btn"
                  className="px-5 py-2.5 rounded-lg font-bold text-sm text-white hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
                  style={{ background: 'linear-gradient(135deg, #D4AF37, #B88759)' }}>
                  {deployLoading ? <Loader2 className="size-4 animate-spin" /> : <Eye className="size-4" />}
                  {deployLoading ? 'Generating Preview...' : 'Preview & Deploy'}
                </button>
              )}
            </div>

            {/* ── Code Diff (Copper Wireframe) ── */}
            {deployPreview && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-xs font-bold tracking-[1.5px] text-[#888] uppercase mb-3">Live Code Diff, Before vs ORA-Optimized</h3>
                  <CopperDiffViewer diffs={deployPreview.diffs} />
                </div>

                {/* ── Tier Selection ── */}
                <div>
                  <h3 className="text-xs font-bold tracking-[1.5px] text-[#888] uppercase mb-3">Select Deployment Tier</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <DeployTierCard
                      tier="free" name="Free Tier" price={0}
                      description="Full access deployment for testing. Unlock with PIN to deploy all fixes at no cost."
                      selected={selectedTier === 'free'} onSelect={(t) => { if (freeUnlocked) setSelectedTier(t); else setShowPinModal(true); }}
                      icon={Unlock} locked={!freeUnlocked}
                      lockMessage="Enter PIN to unlock"
                    />
                    <DeployTierCard
                      tier="basic" name="Basic Patch" price={29}
                      description="One-time downloadable HTML/CSS patch file. Apply changes manually to your site."
                      selected={selectedTier === 'basic'} onSelect={setSelectedTier}
                      icon={Download} locked={false}
                    />
                    <DeployTierCard
                      tier="pro" name="Pro Deploy" price={99}
                      description="ORA automatically creates a GitHub Pull Request with all fixes. The effortless path."
                      selected={selectedTier === 'pro'} onSelect={setSelectedTier}
                      icon={Github} locked={!githubConnected}
                      lockMessage="Connect GitHub in Nexus to unlock"
                    />
                  </div>
                </div>

                {/* GitHub Repo input for Pro */}
                {selectedTier === 'pro' && githubConnected && (
                  <div data-testid="github-repo-input">
                    <label className="block text-[10px] text-[#888] mb-1 uppercase tracking-[1.5px] font-bold">Target Repository (optional)</label>
                    <input type="text" value={githubRepo} onChange={(e) => setGithubRepo(e.target.value)}
                      placeholder="owner/repo-name"
                      className="w-full px-4 py-2.5 bg-white/60 border border-[#D4AF37]/20 rounded-lg text-[#1A1A2E] placeholder-[#aaa] text-sm focus:outline-none focus:border-[#D4AF37]" />
                    <p className="text-[9px] text-[#888] mt-1">Leave blank to create a private GitHub Gist with all fixes</p>
                  </div>
                )}

                {/* ── Pay / Deploy Button ── */}
                {selectedTier === 'free' && freeUnlocked ? (
                  <button onClick={handleFreeDeploy} disabled={actionLoading} data-testid="free-deploy-btn"
                    className="w-full py-4 rounded-xl font-bold text-white text-sm transition-all flex items-center justify-center gap-2 shadow-xl disabled:opacity-50"
                    style={{ background: 'linear-gradient(135deg, #FF6B00 0%, #1a5c33 100%)' }}>
                    {actionLoading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                    {actionLoading ? 'Deploying...' : `Deploy ${deployPreview.fix_count} Fixes — Free`}
                  </button>
                ) : (
                <button onClick={handleCheckout} disabled={checkoutLoading} data-testid="checkout-btn"
                  className="w-full py-4 rounded-xl font-bold text-white text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-xl"
                  style={{ background: 'linear-gradient(135deg, #D4AF37 0%, #B88759 50%, #D4AF37 100%)', backgroundSize: '200% 200%' }}>
                  {checkoutLoading ? (
                    <><Loader2 className="size-4 animate-spin" /> Redirecting to Stripe…</>
                  ) : (
                    <><CreditCard className="size-4" /> Pay ${selectedTier === 'pro' ? 99 : 29} — Deploy {deployPreview.fix_count} Fixes</>
                  )}
                </button>
                )}
                <p className="text-center text-[9px] text-[#888]">
                  <Lock className="size-2.5 inline mr-1" />Secure payment via Stripe. {selectedTier === 'pro' ? 'GitHub PR created automatically after payment.' : 'Patch file available immediately after payment.'}
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── AI Summary ── */}
        {(seoResult || a11yResult || geoResult) && fixes.length > 0 && (
          <div className="p-5 rounded-2xl border border-[#D4B977]/20 bg-gradient-to-r from-[#D4B977]/5 to-[#4ade80]/5" data-testid="ai-summary">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="size-5 text-[#D4B977]" />
              <h3 className="text-sm font-bold text-[#1A1A2E]">ORA Analysis Summary</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="p-3 bg-white/50 rounded-xl text-center">
                <div className="text-lg font-bold text-[#1A1A2E]">{fixes.length}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Total Fixes</div>
              </div>
              <div className="p-3 bg-white/50 rounded-xl text-center">
                <div className="text-lg font-bold text-[#D4B977]">{pendingCount}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Awaiting</div>
              </div>
              <div className="p-3 bg-white/50 rounded-xl text-center">
                <div className="text-lg font-bold text-[#4ade80]">{approvedCount}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Approved</div>
              </div>
              <div className="p-3 bg-white/50 rounded-xl text-center">
                <div className="text-lg font-bold text-[#A855F7]">{geoFixes.length}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">GEO Fixes</div>
              </div>
              <div className="p-3 bg-white/50 rounded-xl text-center">
                <div className="text-lg font-bold text-[#64C8FF]">{a11yResult?.images_analyzed || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Images</div>
              </div>
            </div>
          </div>
        )}

        {/* ── Empty State ── */}
        {!seoResult && !a11yResult && !geoResult && !isAnalyzing && !rescanComparison && (
          <div className="text-center py-16" data-testid="repair-empty-state">
            <div className="size-16 rounded-2xl mx-auto mb-4 flex items-center justify-center bg-gradient-to-br from-[#D4AF37]/20 to-[#4ade80]/20">
              <Wrench className="size-8 text-[#D4AF37]" />
            </div>
            <h2 className="text-lg font-bold text-[#1A1A2E] mb-2">Enter a URL to begin</h2>
            <p className="text-sm text-[#888] max-w-md mx-auto">
              ORA analyzes pages for SEO, GEO (AI search optimization), and accessibility issues using
              <span className="font-bold text-[#4ade80]"> Gemini 3.1 Pro</span> and
              <span className="font-bold text-[#64C8FF]"> Nano Banana 2</span>.
            </p>
          </div>
        )}

        </>)}
      </div>

      {/* Free Tier PIN Modal */}
      <FreePinModal open={showPinModal} onClose={() => setShowPinModal(false)} onUnlock={() => { setFreeUnlocked(true); setSelectedTier('free'); }} />
    </div>
  );
};

export default ORARepairEngine;
