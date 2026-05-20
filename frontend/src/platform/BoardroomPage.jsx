/**
 * AUREM Sovereign Boardroom — Founder P&L Cockpit
 * Iter 288.9
 *
 * Reads:
 *   GET  /api/agents/board/rollup?days=N
 *   GET  /api/agents/board/rates
 *   GET  /api/agents/board/kill-switch?days=N
 *   POST /api/agents/board/meeting?days=N
 *   PUT  /api/agents/board/rates/{key}
 */
import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Loader2, Flame, Trophy, AlertTriangle, ArrowUpRight, ArrowDownRight,
  Skull, Save, Pencil, Check, X, Brain, RefreshCw, Calendar, Crown,
} from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';
import { BACKEND_URL } from '../lib/api';

const API = BACKEND_URL;

const fmtUSD = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const fmtUSDmicro = (n) => `$${(Number(n) || 0).toFixed(4)}`;

const AGENT_META = {
  hunter_ora:   { title: 'Hunter',   role: 'Cold-call closer',     accent: '#EF4444' },
  followup_ora: { title: 'Follow-up',role: 'Persistent re-engager',accent: '#F59E0B' },
  closer_ora:   { title: 'Closer',   role: 'Conversion specialist',accent: '#22C55E' },
  referral_ora: { title: 'Referral', role: 'Network amplifier',    accent: '#8B5CF6' },
  scout_ora:    { title: 'Scout',    role: 'Lead enrichment',      accent: '#06B6D4' },
  envoy_ora:    { title: 'Envoy',    role: 'Outreach delivery',    accent: '#D4AF37' },
  ora_brain:    { title: 'ORA Brain',role: 'Command interpreter',  accent: '#E8E6E1' },
};

const RANGES = [
  { days: 1, label: '24h' },
  { days: 7, label: '7d' },
  { days: 30, label: '30d' },
];

const BoardroomPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const token = getPlatformToken();
  const [days, setDays] = useState(7);
  const [rollup, setRollup] = useState(null);
  const [rates, setRates] = useState({});
  const [losers, setLosers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [meetingBusy, setMeetingBusy] = useState(false);
  const [meetingOut, setMeetingOut] = useState('');
  const [editingRate, setEditingRate] = useState(null);
  const [rateDraft, setRateDraft] = useState('');
  const [excludeSynthetic, setExcludeSynthetic] = useState(() => {
    return localStorage.getItem('boardroom_exclude_synthetic') === '1';
  });

  const headers = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }), [token]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const synFlag = excludeSynthetic ? '&exclude_synthetic=true' : '';
      const [rRes, ratesRes, kRes] = await Promise.all([
        fetch(`${API}/api/agents/board/rollup?days=${days}${synFlag}`, { headers: headers() }),
        fetch(`${API}/api/agents/board/rates`, { headers: headers() }),
        fetch(`${API}/api/agents/board/kill-switch?days=${days}`, { headers: headers() }),
      ]);
      if (rRes.status === 401 || rRes.status === 403) { navigate('/admin/login'); return; }
      setRollup(await rRes.json());
      setRates(await ratesRes.json());
      const kData = await kRes.json();
      setLosers(kData.losers || []);
    } catch {
      /* swallow */
    }
    setLoading(false);
  }, [days, headers, navigate, excludeSynthetic]);

  useEffect(() => { if (!token) { navigate('/admin/login'); return; } load(); }, [load, navigate, token]);

  const toggleSynthetic = () => {
    const next = !excludeSynthetic;
    setExcludeSynthetic(next);
    localStorage.setItem('boardroom_exclude_synthetic',
                            next ? '1' : '0');
  };

  // Scroll to & pulse the agent card when navigated with #agent-<id>
  const { hash } = location;
  useEffect(() => {
    if (!hash || loading) return;
    const id = decodeURIComponent(hash.slice(1));
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('agent-card-pulse');
    const t = setTimeout(() => el.classList.remove('agent-card-pulse'), 1400);
    return () => clearTimeout(t);
  }, [hash, loading, rollup]);

  const runMeeting = async () => {
    setMeetingBusy(true);
    setMeetingOut('');
    try {
      const r = await fetch(`${API}/api/agents/board/meeting?days=${days}`, {
        method: 'POST', headers: headers(),
      });
      const d = await r.json();
      setMeetingOut(JSON.stringify(d, null, 2));
    } catch (e) {
      setMeetingOut(String(e));
    }
    setMeetingBusy(false);
  };

  const saveRate = async (key) => {
    const newRate = parseFloat(rateDraft);
    if (isNaN(newRate) || newRate < 0) { setEditingRate(null); return; }
    await fetch(`${API}/api/agents/board/rates/${encodeURIComponent(key)}`, {
      method: 'PUT', headers: headers(), body: JSON.stringify({ rate: newRate }),
    });
    setEditingRate(null);
    load();
  };

  const board = rollup?.board || [];
  const isLoser = (id) => losers.some((l) => l.agent_id === id);

  return (
    <div className="min-h-screen px-6 py-10"
      style={{ background: '#050507', color: '#E8E6E1', fontFamily: "'Inter', sans-serif" }}
      data-testid="admin-boardroom-page">
      <style>{`
        @keyframes agent-card-pulse-kf {
          0%   { box-shadow: 0 0 0 0 rgba(212,175,55,0.55); border-color: rgba(212,175,55,0.9); }
          100% { box-shadow: 0 0 0 18px rgba(212,175,55,0);  border-color: rgba(255,255,255,0.06); }
        }
        .agent-card-pulse { animation: agent-card-pulse-kf 1.4s ease-out 1; }
      `}</style>
      {/* HEADER */}
      <div className="max-w-7xl mx-auto mb-8 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Crown className="w-5 h-5 text-[#D4AF37]" />
            <span className="text-[10px] tracking-[0.3em] text-[#666] uppercase">Sovereign Boardroom</span>
          </div>
          <h1 className="text-2xl tracking-[0.08em]" style={{ fontFamily: "'Cinzel', serif" }}>
            Revenue · Reflector
          </h1>
          <p className="text-xs text-[#666] mt-1">Live P&L per AI employee · founder-only</p>
        </div>
        <div className="flex items-center gap-2">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              data-testid={`range-${r.label}`}
              className="px-3 py-1.5 rounded-lg text-xs transition-all"
              style={{
                background: days === r.days ? 'rgba(212,175,55,0.15)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${days === r.days ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.06)'}`,
                color: days === r.days ? '#D4AF37' : '#888',
              }}>
              <Calendar className="w-3 h-3 inline mr-1" />{r.label}
            </button>
          ))}
          <button
            onClick={load}
            disabled={loading}
            data-testid="boardroom-refresh"
            className="px-3 py-1.5 rounded-lg text-xs ml-2"
            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', color: '#888' }}>
            {loading ? <Loader2 className="w-3 h-3 inline animate-spin" /> : <RefreshCw className="w-3 h-3 inline" />}
          </button>
          <button
            onClick={toggleSynthetic}
            data-testid="boardroom-toggle-synthetic"
            className="px-3 py-1.5 rounded-lg text-xs ml-2"
            title="Hide manual/seed ledger entries with no lead_id"
            style={{
              background: excludeSynthetic ? 'rgba(245,158,11,0.18)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${excludeSynthetic ? 'rgba(245,158,11,0.55)' : 'rgba(255,255,255,0.06)'}`,
              color: excludeSynthetic ? '#F59E0B' : '#888',
            }}>
            <AlertTriangle className="w-3 h-3 inline mr-1" />
            {excludeSynthetic ? 'SYNTHETIC HIDDEN' : 'HIDE SYNTHETIC'}
          </button>
        </div>
      </div>

      {/* SYNTHETIC NOTICE — present whenever rollup contains seed/manual entries */}
      {!loading && (rollup?.synthetic_count || 0) > 0 && (
        <div className="max-w-7xl mx-auto mb-4 p-3 rounded-xl flex items-center gap-3"
          style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.25)' }}
          data-testid="boardroom-synthetic-banner">
          <AlertTriangle className="w-4 h-4 text-[#F59E0B] shrink-0" />
          <div className="text-xs text-[#F59E0B] leading-relaxed">
            <strong>{rollup.synthetic_count} synthetic ledger entries detected</strong>
            {' — '}
            ${(rollup.synthetic_realized_usd || 0).toFixed(2)} realized + ${(rollup.synthetic_potential_usd || 0).toFixed(2)} pipeline are <em>seed/manual entries with no lead_id and no Stripe match</em>.
            {excludeSynthetic
              ? <span className="ml-1 text-[#888]"> Currently hidden from totals.</span>
              : <span className="ml-1 text-[#888]"> Click <strong>HIDE SYNTHETIC</strong> to see real-only revenue.</span>}
          </div>
        </div>
      )}

      {/* KPI STRIP */}
      <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <Kpi label="Gross burn" value={fmtUSD(rollup?.gross_burn_usd)} accent="#EF4444" icon={<Flame className="w-4 h-4" />} testid="kpi-burn" />
        <Kpi label="Realized $" value={fmtUSD(rollup?.realized_revenue_usd)} accent="#22C55E" icon={<Trophy className="w-4 h-4" />} testid="kpi-realized" />
        <Kpi label="Pipeline $" value={fmtUSD(rollup?.potential_pipeline_usd)} accent="#06B6D4" icon={<ArrowUpRight className="w-4 h-4" />} testid="kpi-pipeline" />
        <Kpi
          label="Net margin"
          value={fmtUSD(rollup?.net_margin_usd)}
          accent={(rollup?.net_margin_usd || 0) >= 0 ? '#22C55E' : '#EF4444'}
          icon={(rollup?.net_margin_usd || 0) >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
          testid="kpi-margin"
        />
      </div>

      {/* KILL-SWITCH WARNING */}
      {losers.length > 0 && (
        <div className="max-w-7xl mx-auto mb-6 p-4 rounded-xl flex items-center gap-3"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.25)' }}
          data-testid="boardroom-killlist">
          <Skull className="w-4 h-4 text-[#EF4444]" />
          <div className="text-xs text-[#EF4444]">
            <strong>{losers.length} agent{losers.length === 1 ? '' : 's'} losing money</strong> over the last {days}d:
            <span className="text-[#888] ml-2">{losers.map((l) => l.agent_id).join(' · ')}</span>
          </div>
        </div>
      )}

      {/* AGENT GRID */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
        {board.map((row) => (
          <AgentCard
            key={row.agent_id}
            row={row}
            meta={AGENT_META[row.agent_id] || { title: row.agent_id, role: 'Unknown role', accent: '#888' }}
            losing={isLoser(row.agent_id)}
            days={days}
          />
        ))}
        {board.length === 0 && !loading && (
          <div className="col-span-full text-center text-xs text-[#666] py-12">
            No ledger entries yet — the board is silent.
          </div>
        )}
      </div>

      {/* MEETING + RATES */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Run meeting */}
        <div className="rounded-xl p-5"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-[#D4AF37]" />
              <span className="text-xs tracking-[0.2em] uppercase text-[#888]">Board meeting</span>
            </div>
            <button
              onClick={runMeeting}
              disabled={meetingBusy}
              data-testid="boardroom-meeting-btn"
              className="px-4 py-2 rounded-lg text-xs disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg,#D4AF37,#8B7355)', color: '#050507' }}>
              {meetingBusy ? <Loader2 className="w-3 h-3 inline animate-spin mr-1" /> : null}
              Run reflection ({days}d)
            </button>
          </div>
          <p className="text-[11px] text-[#666] leading-relaxed mb-3">
            Triggers each agent's LLM-driven self-reflection on their P&L over the selected window.
            Updates `SOUL.md` per agent and surfaces strategic recommendations.
          </p>
          <AnimatePresence>
            {meetingOut && (
              <motion.pre
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="text-[10px] p-3 rounded-lg overflow-auto max-h-64 font-mono"
                style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.06)', color: '#06B6D4' }}
                data-testid="boardroom-meeting-output"
              >
                {meetingOut}
              </motion.pre>
            )}
          </AnimatePresence>
        </div>

        {/* Rate editor */}
        <div className="rounded-xl p-5"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="flex items-center gap-2 mb-3">
            <Pencil className="w-4 h-4 text-[#D4AF37]" />
            <span className="text-xs tracking-[0.2em] uppercase text-[#888]">Rate card</span>
            <span className="text-[10px] text-[#444] ml-auto">USD per unit</span>
          </div>
          <div className="space-y-1.5 max-h-[440px] overflow-y-auto pr-1">
            {Object.values(rates || {}).sort((a, b) => (b.rate || 0) - (a.rate || 0)).map((r) => (
              <div key={r.key} className="flex items-center gap-3 py-2 px-3 rounded-lg text-xs"
                style={{ background: 'rgba(0,0,0,0.25)' }}
                data-testid={`rate-row-${r.key}`}>
                <div className="flex-1 min-w-0">
                  <div className="text-[#E8E6E1] truncate">{r.label || r.key}</div>
                  <div className="text-[9px] text-[#555] uppercase tracking-wider">{r.unit}</div>
                </div>
                {editingRate === r.key ? (
                  <>
                    <input
                      type="number"
                      step="0.0001"
                      value={rateDraft}
                      onChange={(e) => setRateDraft(e.target.value)}
                      autoFocus
                      data-testid={`rate-input-${r.key}`}
                      className="w-24 px-2 py-1 rounded text-xs text-right font-mono"
                      style={{ background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.3)', color: '#D4AF37' }}
                    />
                    <button onClick={() => saveRate(r.key)} data-testid={`rate-save-${r.key}`}
                      className="text-[#22C55E] hover:opacity-70"><Check className="w-3.5 h-3.5" /></button>
                    <button onClick={() => setEditingRate(null)} className="text-[#666] hover:text-[#EF4444]">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </>
                ) : (
                  <>
                    <span className="font-mono text-[#D4AF37] w-24 text-right">{Number(r.rate).toFixed(4)}</span>
                    <button
                      onClick={() => { setEditingRate(r.key); setRateDraft(String(r.rate)); }}
                      data-testid={`rate-edit-${r.key}`}
                      className="text-[#666] hover:text-[#D4AF37]">
                      <Save className="w-3 h-3" />
                    </button>
                  </>
                )}
              </div>
            ))}
            {Object.keys(rates || {}).length === 0 && (
              <div className="text-[#666] text-xs py-6 text-center">No rate card loaded.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const Kpi = ({ label, value, accent, icon, testid }) => (
  <div className="rounded-xl p-4"
    style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
    data-testid={testid}>
    <div className="flex items-center gap-2 text-[10px] tracking-[0.2em] uppercase mb-2"
      style={{ color: accent }}>
      {icon}{label}
    </div>
    <div className="text-2xl font-mono" style={{ color: '#E8E6E1' }}>{value}</div>
  </div>
);

const AgentCard = ({ row, meta, losing, days }) => {
  const profit = (row.revenue_realized_usd || 0) + (row.revenue_potential_usd || 0) - (row.cost_usd || 0);
  const positive = profit >= 0;
  return (
    <motion.div
      id={`agent-${row.agent_id}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl p-5 relative overflow-hidden agent-card"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: `1px solid ${losing ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.06)'}`,
        scrollMarginTop: 90,
      }}
      data-testid={`agent-card-${row.agent_id}`}>
      <div className="absolute top-0 left-0 right-0 h-[2px]" style={{ background: meta.accent }} />
      {losing && (
        <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px]"
          style={{ background: 'rgba(239,68,68,0.15)', color: '#EF4444' }}
          data-testid={`agent-loser-${row.agent_id}`}>
          <Skull className="w-2.5 h-2.5" /> LOSING
        </div>
      )}
      <div className="mb-3">
        <div className="text-[10px] tracking-[0.25em] uppercase text-[#666]">{row.agent_id}</div>
        <div className="text-lg" style={{ color: meta.accent, fontFamily: "'Cinzel', serif" }}>{meta.title}</div>
        <div className="text-[10px] text-[#555]">{meta.role}</div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div>
          <div className="text-[9px] uppercase tracking-wider text-[#555]">Burn ({days}d)</div>
          <div className="font-mono text-[#EF4444]">{fmtUSD(row.cost_usd)}</div>
        </div>
        <div>
          <div className="text-[9px] uppercase tracking-wider text-[#555]">Realized</div>
          <div className="font-mono text-[#22C55E]">{fmtUSD(row.revenue_realized_usd)}</div>
        </div>
        <div>
          <div className="text-[9px] uppercase tracking-wider text-[#555]">Pipeline</div>
          <div className="font-mono text-[#06B6D4]">{fmtUSD(row.revenue_potential_usd)}</div>
        </div>
        <div>
          <div className="text-[9px] uppercase tracking-wider text-[#555]">ROI</div>
          <div className={`font-mono ${row.roi_potential >= 1 ? 'text-[#22C55E]' : 'text-[#F59E0B]'}`}>
            {Number(row.roi_potential || 0).toFixed(2)}×
          </div>
        </div>
      </div>
      {Object.keys(row.cost_by_source || {}).length > 0 && (
        <div className="pt-3 border-t border-white/5">
          <div className="text-[9px] uppercase tracking-wider text-[#555] mb-1.5">Cost breakdown</div>
          <div className="space-y-1">
            {Object.entries(row.cost_by_source).map(([src, cost]) => (
              <div key={src} className="flex items-center justify-between text-[10px]">
                <span className="text-[#888]">{src}</span>
                <span className="font-mono text-[#888]">{fmtUSDmicro(cost)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-[10px]">
        <div className={positive ? 'text-[#22C55E]' : 'text-[#EF4444]'}>
          {positive ? '+' : ''}{fmtUSD(profit)} <span className="text-[#555]">net</span>
        </div>
        {losing && <AlertTriangle className="w-3 h-3 text-[#EF4444]" />}
      </div>
    </motion.div>
  );
};

export default BoardroomPage;
