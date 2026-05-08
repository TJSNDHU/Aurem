/**
 * ORA Desktop Context Sidebar
 * Shows live business snapshot on desktop (>768px)
 * Left panel (320px) with Business ID, stats, pipeline, economic data
 */
import React, { useState, useEffect } from 'react';
import { ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const Stat = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0' }}>
    <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#8A8070' }}>{label}</span>
    <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600, color: color || '#E8E0D0' }}>{value}</span>
  </div>
);

export default function OraDesktopSidebar({ token, isFounder, founderBriefing }) {
  const [context, setContext] = useState(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [boardroom, setBoardroom] = useState(null);
  const [meetingLoading, setMeetingLoading] = useState(false);
  const [customers, setCustomers] = useState([]);

  useEffect(() => {
    const load = async () => {
      if (!token) { setLoading(false); return; }
      try {
        const headers = { 'Authorization': `Bearer ${token}` };
        const res = await fetch(`${API}/api/ora/context`, { headers });
        if (res.ok) {
          const data = await res.json();
          setContext(data);
        } else if (res.status === 401) {
          // Stop polling on auth failure
          return;
        }
      } catch {}
      setLoading(false);
    };
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, [token]);

  // ── Iter 288.0 — Boardroom rollup polling (founder only) ──
  useEffect(() => {
    if (!token || !isFounder) return;
    const loadBoard = async () => {
      try {
        const r = await fetch(`${API}/api/agents/board/rollup?days=7`,
          { headers: { 'Authorization': `Bearer ${token}` } });
        if (r.ok) setBoardroom(await r.json());
      } catch {}
    };
    loadBoard();
    const itv = setInterval(loadBoard, 90000);
    return () => clearInterval(itv);
  }, [token, isFounder]);

  // ── Iter 288.2 — Customer Contacts auto-feed (founder only) ──
  useEffect(() => {
    if (!token || !isFounder) return;
    const loadCustomers = async () => {
      try {
        const r = await fetch(`${API}/api/admin/founder/customers/list?limit=20`,
          { headers: { 'Authorization': `Bearer ${token}` } });
        if (r.ok) {
          const d = await r.json();
          setCustomers(d.customers || []);
        }
      } catch {}
    };
    loadCustomers();
    const itv = setInterval(loadCustomers, 30000);  // 30s refresh — auto-pulls new signups
    return () => clearInterval(itv);
  }, [token, isFounder]);

  const summonMeeting = async () => {
    if (!token || meetingLoading) return;
    setMeetingLoading(true);
    try {
      const r = await fetch(`${API}/api/agents/board/meeting?days=7`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (r.ok) {
        const d = await r.json();
        setBoardroom(d.rollup || null);
        // Show a quick toast / could be replaced with proper modal later
        if (typeof window !== 'undefined' && d.summary) {
          window.alert(d.summary.slice(0, 1500));
        }
      }
    } catch {}
    setMeetingLoading(false);
  };

  const copyBID = () => {
    if (context?.business_id) {
      navigator.clipboard?.writeText(context.business_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div data-testid="ora-desktop-sidebar" style={{ width: 320, flexShrink: 0, background: 'rgba(12,12,20,0.98)', borderRight: '1px solid rgba(255,107,0,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 20, height: 20, border: '2px solid rgba(255,107,0,0.3)', borderTop: '2px solid #FF6B00', borderRadius: '50%', animation: 'oraSpin 1s linear infinite' }} />
      </div>
    );
  }

  const c = context || {};
  const pipelineStatus = c.last_pipeline_run?.status || 'No runs yet';
  const pipelineTime = c.last_pipeline_run?.completed_at
    ? new Date(c.last_pipeline_run.completed_at).toLocaleString('en', { hour: '2-digit', minute: '2-digit', hour12: true })
    : '--';

  return (
    <div data-testid="ora-desktop-sidebar" style={{ width: 320, flexShrink: 0, background: 'rgba(12,12,20,0.98)', borderRight: '1px solid rgba(255,107,0,0.08)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Business Identity Header */}
      <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid rgba(255,107,0,0.08)' }}>
        {isFounder && (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 6, background: 'rgba(201,168,76,0.12)', border: '1px solid rgba(201,168,76,0.25)', marginBottom: 8 }}>
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#C9A84C' }} />
            <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 700, color: '#C9A84C', letterSpacing: '0.15em', textTransform: 'uppercase' }}>FOUNDER</span>
          </div>
        )}
        <div style={{ fontFamily: "'Cinzel',serif", fontSize: 14, fontWeight: 700, color: '#E8E0D0', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 4 }}>
          {isFounder ? 'AUREM AI GLOBAL INC.' : (c.business_name || 'Your Business')}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: '#FF6B00', letterSpacing: '0.05em' }}>
            ID: {c.business_id || '---'}
          </span>
          <button data-testid="sidebar-copy-bid" onClick={copyBID} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, display: 'flex' }}>
            {copied ? <Check size={12} color="#4ADE80" /> : <Copy size={12} color="#6A6070" />}
          </button>
        </div>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 6, background: 'rgba(255,107,0,0.08)', border: '1px solid rgba(255,107,0,0.15)' }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#4ADE80' }} />
          <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, fontWeight: 600, color: '#FF6B00', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Plan: {c.plan || 'Starter'}
          </span>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }} className="ora-hide-scroll">
        {/* FOUNDER PLATFORM STATS */}
        {isFounder && founderBriefing && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#C9A84C', marginBottom: 8 }}>PLATFORM OVERVIEW</div>
            <div style={{ background: 'rgba(201,168,76,0.04)', border: '1px solid rgba(201,168,76,0.12)', borderRadius: 10, padding: '10px 14px' }}>
              <Stat label="Tenants" value={founderBriefing.tenants?.total || 0} color="#C9A84C" />
              <Stat label="Active Today" value={founderBriefing.tenants?.active_today || 0} color="#4ADE80" />
              <Stat label="Total Leads" value={founderBriefing.leads?.total || 0} color="#4FC3F7" />
              <Stat label="API Keys" value={`${founderBriefing.api_keys?.active || 0} active`} color="#FF6B00" />
              <Stat label="Voice Calls" value={founderBriefing.voice_calls_total || 0} color="#CE93D8" />
              <Stat label="Connections" value={founderBriefing.team_connections || 0} color="#81C784" />
            </div>
          </div>
        )}
        {/* TODAY section */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 8 }}>TODAY</div>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}>
            <Stat label="Leads" value={`${c.leads_count || 0} new`} color="#4FC3F7" />
            <Stat label="Approvals" value={`${c.pending_approvals || 0} pending`} color={c.pending_approvals > 0 ? '#FFB347' : '#8A8070'} />
            <Stat label="Revenue" value={`$${(c.revenue_this_month || 0).toLocaleString()}`} color="#4ADE80" />
            <Stat label="Health" value={`${c.website_health_score || 0}/100`} color={c.website_health_score >= 80 ? '#4ADE80' : '#FFB347'} />
          </div>
        </div>

        {/* Outstanding */}
        {c.outstanding_invoices > 0 && (
          <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 10, background: 'rgba(255,179,71,0.06)', border: '1px solid rgba(255,179,71,0.15)' }}>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#FFB347', fontWeight: 600, marginBottom: 4 }}>OUTSTANDING</div>
            <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 14, fontWeight: 700, color: '#FFB347' }}>
              ${(c.outstanding_revenue || 0).toLocaleString()} ({c.outstanding_invoices} invoices)
            </div>
          </div>
        )}

        {/* PIPELINE section */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 8 }}>PIPELINE</div>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}>
            <Stat label="Last run" value={pipelineTime} />
            <Stat label="Status" value={pipelineStatus === 'completed' ? 'Complete' : pipelineStatus} color={pipelineStatus === 'completed' ? '#4ADE80' : '#8A8070'} />
            {c.last_pipeline_run?.actions_taken > 0 && (
              <Stat label="Actions" value={c.last_pipeline_run.actions_taken} color="#4FC3F7" />
            )}
          </div>
        </div>

        {/* ECONOMIC section */}
        {c.economic_context && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 8 }}>ECONOMIC</div>
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}>
              {c.economic_context.cad_usd && <Stat label="CAD/USD" value={c.economic_context.cad_usd} color="#C9A84C" />}
              {c.economic_context.boc_rate && <Stat label="BoC Rate" value={`${c.economic_context.boc_rate}%`} color="#C9A84C" />}
              {c.economic_context.next_decision && <Stat label="Next BoC" value={c.economic_context.next_decision} />}
            </div>
          </div>
        )}

        {/* Iter 288.2 — Customer Contacts auto-feed (founder only) */}
        {isFounder && (
          <div style={{ marginBottom: 16 }} data-testid="customer-contacts-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#64C8FF' }}>👥 CUSTOMER CONTACTS · LIVE</div>
              <span data-testid="customer-count" style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#64C8FF', fontWeight: 600 }}>{customers.length}</span>
            </div>
            <div style={{ background: 'rgba(100,200,255,0.04)', border: '1px solid rgba(100,200,255,0.15)', borderRadius: 10, padding: '10px 12px', maxHeight: 220, overflowY: 'auto' }}>
              {customers.length === 0 ? (
                <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#6A6070', fontStyle: 'italic' }}>No customer signups yet. New ones auto-appear here within 30s.</div>
              ) : customers.map((c, i) => (
                <div key={c.email + i} data-testid={`customer-row-${i}`} style={{ padding: '6px 0', borderBottom: i < customers.length - 1 ? '1px solid rgba(100,200,255,0.06)' : 'none' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                    <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, fontWeight: 700, color: '#64C8FF' }}>{c.business_id || '—'}</span>
                    <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, color: c.wizard_complete ? '#4ADE80' : '#FFB347' }}>{c.wizard_complete ? '✅ wizard' : '⏳ pending'}</span>
                  </div>
                  <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#E8E0D0', fontWeight: 500 }}>{c.company_name || c.full_name || c.email}</div>
                  <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#8A8070' }}>{c.email}{c.city ? ` · ${c.city}` : ''}{c.industry ? ` · ${c.industry}` : ''}</div>
                  {c.website && <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: '#6A6070', marginTop: 1 }}>{c.website}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Iter 288.0 — Sovereign Boardroom (founder only) */}
        {isFounder && boardroom && (
          <div style={{ marginBottom: 16 }} data-testid="boardroom-panel">
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#C9A84C', marginBottom: 8 }}>👔 SOVEREIGN BOARDROOM · 7d</div>
            <div style={{ background: 'linear-gradient(135deg, rgba(201,168,76,0.06), rgba(255,107,0,0.03))', border: '1px solid rgba(201,168,76,0.2)', borderRadius: 10, padding: '10px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#8A8070' }}>Gross burn</span>
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600, color: '#FF6B00' }} data-testid="boardroom-burn">${Number(boardroom.gross_burn_usd || 0).toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#8A8070' }}>Pipeline</span>
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600, color: '#FFB347' }} data-testid="boardroom-pipeline">${Number(boardroom.potential_pipeline_usd || 0).toFixed(0)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#8A8070' }}>Realized</span>
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 700, color: '#4ADE80' }} data-testid="boardroom-realized">${Number(boardroom.realized_revenue_usd || 0).toFixed(0)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, paddingTop: 6, borderTop: '1px solid rgba(201,168,76,0.15)' }}>
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#C9A84C', fontWeight: 600 }}>Net margin</span>
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: Number(boardroom.net_margin_usd || 0) >= 0 ? '#4ADE80' : '#EF4444' }} data-testid="boardroom-margin">${Number(boardroom.net_margin_usd || 0).toFixed(2)}</span>
              </div>
              {boardroom.firing_line?.length > 0 && (
                <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#EF4444', marginBottom: 8 }} data-testid="boardroom-firing-line">
                  🔴 Firing line: {boardroom.firing_line.join(', ')}
                </div>
              )}
              <button data-testid="boardroom-summon-btn" onClick={summonMeeting} disabled={meetingLoading} style={{ width: '100%', marginTop: 4, padding: '8px 10px', borderRadius: 8, background: meetingLoading ? 'rgba(201,168,76,0.1)' : 'linear-gradient(135deg,#C9A84C,#FF6B00)', border: 'none', cursor: meetingLoading ? 'wait' : 'pointer', fontFamily: "'Jost',sans-serif", fontSize: 11, fontWeight: 600, color: '#0A0505', letterSpacing: '0.05em' }}>
                {meetingLoading ? 'Convening…' : '👔 Summon Board Meeting'}
              </button>
            </div>
          </div>
        )}

        {/* Morning Brief summary */}
        {c.todays_brief && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 8 }}>MORNING BRIEF</div>
            <div style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(255,107,0,0.1)', borderRadius: 10, padding: '10px 14px' }}>
              <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#E8E0D0', lineHeight: 1.5, marginBottom: 6 }}>
                {c.todays_brief.summary?.slice(0, 120) || 'Brief loading...'}
                {c.todays_brief.summary?.length > 120 && '...'}
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#4ADE80' }}>
                  {c.todays_brief.handled_count || 0} handled
                </span>
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#FFB347' }}>
                  {c.todays_brief.attention_count || 0} need you
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Recent leads */}
        {c.leads_today?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 8 }}>TOP LEADS TODAY</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {c.leads_today.map((lead, i) => (
                <div key={i} style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 12, color: '#E8E0D0', fontWeight: 500 }}>{lead.name || 'Unknown'}</div>
                    <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#6A6070' }}>{lead.company || lead.city || ''}</div>
                  </div>
                  {lead.score && (
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 700, color: lead.score >= 80 ? '#4ADE80' : '#FFB347' }}>{lead.score}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,107,0,0.08)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <a data-testid="sidebar-open-dashboard" href="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(255,107,0,0.1)', textDecoration: 'none', transition: 'background 0.2s' }}>
          <ExternalLink size={12} color="#FF6B00" />
          <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#FF6B00', fontWeight: 500, flex: 1 }}>Open Full Dashboard</span>
          <ChevronRight size={12} color="#FF6B00" />
        </a>
        <a data-testid="sidebar-view-brief" href="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', textDecoration: 'none' }}>
          <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#8A8070', fontWeight: 500, flex: 1 }}>View Morning Brief</span>
          <ChevronRight size={12} color="#6A6070" />
        </a>
      </div>
    </div>
  );
}
