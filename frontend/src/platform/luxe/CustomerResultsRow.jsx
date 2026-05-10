/**
 * CustomerResultsRow — Tiles A, B, C + Inbox (Wires 3 & 4).
 *
 * GOLD-MINE LOCKED:
 *   • No lead names, no phone, no email visible.
 *   • Numbers, anonymous outcomes, masked handles only.
 *   • Reply box auto-routes by channel (email/sms/whatsapp).
 */
import React, { useCallback, useEffect, useState } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;
const COMP_BG = 'rgba(20,18,15,0.55)';
const COMP_BORDER = 'rgba(212,163,115,0.18)';
const GOLD_HI = '#FFE4A8';
const TEXT_HI = '#E8E2D4';
const TEXT_LO = '#7A7468';
const TEXT_MD = '#A89B7E';
const fontDisplay = "'Cormorant Garamond', serif";
const fontMono = "'JetBrains Mono', monospace";

const headers = () => {
  const t = localStorage.getItem('aurem_customer_token')
    || localStorage.getItem('platform_token')
    || localStorage.getItem('token') || '';
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` };
};

// ─── shared card ──────────────────────────────────────────────────────
const Card = ({ children, testid, style }) => (
  <div data-testid={testid} style={{
    background: COMP_BG, border: `1px solid ${COMP_BORDER}`,
    borderRadius: 10, padding: 16, ...style,
  }}>{children}</div>
);

const TileHeader = ({ label }) => (
  <div style={{
    fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11,
    letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 14,
  }}>{label}</div>
);

// ─── TILE A — AUREM Working For You ────────────────────────────────────
const TileA = () => {
  const [s, setS] = useState({ leads_found: 0, outreach_sent: 0, responses: 0, meetings_booked: 0, loading: true });
  useEffect(() => {
    fetch(`${API}/api/customer/results-summary`, { headers: headers() })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setS({ ...d, loading: false }))
      .catch(() => setS(p => ({ ...p, loading: false })));
  }, []);
  const items = [
    { k: 'Leads Found', v: s.leads_found, tid: 'a-leads' },
    { k: 'Outreach Sent', v: s.outreach_sent, tid: 'a-outreach' },
    { k: 'Responses', v: s.responses, tid: 'a-responses' },
    { k: 'Meetings Booked', v: s.meetings_booked, tid: 'a-meetings' },
  ];
  return (
    <Card testid="tile-a-aurem-working">
      <TileHeader label="AUREM Working For You" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 10 }}>
        {items.map(it => (
          <div key={it.k} data-testid={it.tid} style={{
            padding: '12px 10px', borderRadius: 8,
            background: 'rgba(10,8,5,0.5)', border: '1px solid rgba(212,163,115,0.10)',
          }}>
            <div style={{ fontFamily: fontMono, color: TEXT_HI, fontSize: 26, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
              {Number(it.v ?? 0).toLocaleString()}
            </div>
            <div style={{ color: TEXT_LO, fontSize: 11, marginTop: 4, letterSpacing: '0.06em' }}>
              {it.k}
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 10, color: TEXT_LO, fontSize: 10, letterSpacing: '0.05em' }}>
        Last 30 days · outcomes only
      </div>
    </Card>
  );
};

// ─── TILE B — Recent Activity ──────────────────────────────────────────
const TileB = () => {
  const [items, setItems] = useState([]);
  useEffect(() => {
    fetch(`${API}/api/customer/results-activity?limit=10`, { headers: headers() })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setItems(d.items || []))
      .catch(() => {});
  }, []);
  return (
    <Card testid="tile-b-recent-activity">
      <TileHeader label="Recent Activity" />
      {items.length === 0 ? (
        <div style={{ color: TEXT_LO, fontSize: 12, padding: '8px 0' }}>
          No activity in the last 14 days.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.slice(0, 8).map((it, i) => (
            <div key={i} data-testid={`b-item-${i}`} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 10px', borderRadius: 6,
              background: 'rgba(10,8,5,0.4)', border: '1px solid rgba(212,163,115,0.08)',
            }}>
              <span style={{ color: TEXT_HI, fontSize: 12 }}>{it.line}</span>
              <span style={{ color: TEXT_LO, fontSize: 10, fontFamily: fontMono }}>
                {it.at ? new Date(it.at).toLocaleDateString() : ''}
              </span>
            </div>
          ))}
        </div>
      )}
      <div style={{ marginTop: 10, color: TEXT_LO, fontSize: 10 }}>
        Last 14 days · anonymous outcomes
      </div>
    </Card>
  );
};

// ─── TILE C — Pipeline This Month ──────────────────────────────────────
const TileC = () => {
  const [pipe, setPipe] = useState({ total: 0, stages: [] });
  useEffect(() => {
    fetch(`${API}/api/customer/results-pipeline`, { headers: headers() })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setPipe(d))
      .catch(() => {});
  }, []);
  const max = Math.max(1, ...(pipe.stages || []).map(s => s.count));
  return (
    <Card testid="tile-c-pipeline">
      <TileHeader label="Pipeline This Month" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {(pipe.stages || []).map((s, i) => {
          const pct = Math.max(2, Math.round((s.count / max) * 100));
          return (
            <div key={s.stage} data-testid={`c-stage-${s.stage.toLowerCase()}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: TEXT_MD, marginBottom: 4 }}>
                <span style={{ letterSpacing: '0.08em' }}>{s.stage.toUpperCase()}</span>
                <span style={{ fontFamily: fontMono, color: TEXT_HI }}>{s.count}</span>
              </div>
              <div style={{ height: 8, background: 'rgba(10,8,5,0.5)', borderRadius: 6, overflow: 'hidden' }}>
                <div style={{
                  width: `${pct}%`, height: '100%',
                  background: i === 4
                    ? 'linear-gradient(90deg, #bef264 0%, #84cc16 100%)'
                    : 'linear-gradient(90deg, #FFE4A8 0%, #C9A84C 100%)',
                  borderRadius: 6,
                }} />
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 12, color: TEXT_LO, fontSize: 10, display: 'flex', justifyContent: 'space-between' }}>
        <span>Numbers only · no names</span>
        <span style={{ fontFamily: fontMono, color: TEXT_HI }}>Total: {pipe.total}</span>
      </div>
    </Card>
  );
};

// ─── TILE D — Inbox (threads + reply) ──────────────────────────────────
const TileInbox = () => {
  const [threads, setThreads] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState(null);

  const loadThreads = useCallback(() => {
    fetch(`${API}/api/customer/inbox/threads?limit=20`, { headers: headers() })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setThreads(d.threads || []))
      .catch(() => {});
  }, []);
  useEffect(() => { loadThreads(); }, [loadThreads]);

  const openThread = useCallback(async (tid) => {
    setActive(tid);
    setStatus(null);
    const r = await fetch(`${API}/api/customer/inbox/thread/${encodeURIComponent(tid)}?limit=50`, { headers: headers() });
    const d = r.ok ? await r.json() : { messages: [] };
    setMessages(d.messages || []);
  }, []);

  const sendReply = useCallback(async () => {
    if (!active || !reply.trim()) return;
    setSending(true);
    setStatus(null);
    try {
      const r = await fetch(`${API}/api/customer/inbox/reply`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ thread_id: active, message: reply }),
      });
      const d = await r.json();
      setStatus(d.ok ? `✅ Sent via ${d.sent_via}` : `❌ ${d.error || d.detail || 'send failed'}`);
      if (d.ok) {
        setReply('');
        openThread(active);
        loadThreads();
      }
    } catch (e) {
      setStatus(`❌ ${e.message}`);
    }
    setSending(false);
  }, [active, reply, openThread, loadThreads]);

  return (
    <Card testid="tile-inbox" style={{ gridColumn: 'span 2' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <TileHeader label="Inbox (All Channels)" />
        <span style={{ color: TEXT_LO, fontSize: 10 }}>
          {threads.reduce((s, t) => s + (t.unread || 0), 0)} unread
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '0.9fr 1.4fr', gap: 12, minHeight: 280 }}>
        {/* Thread list */}
        <div data-testid="inbox-threads" style={{
          maxHeight: 360, overflowY: 'auto',
          borderRight: '1px solid rgba(212,163,115,0.08)', paddingRight: 8,
        }}>
          {threads.length === 0 ? (
            <div style={{ color: TEXT_LO, fontSize: 12, padding: 8 }}>No conversations yet.</div>
          ) : threads.map(t => (
            <div key={t.thread_id} data-testid={`thread-${t.thread_id}`}
              onClick={() => openThread(t.thread_id)}
              style={{
                padding: 10, cursor: 'pointer', borderRadius: 6, marginBottom: 4,
                background: active === t.thread_id ? 'rgba(212,163,115,0.10)' : 'transparent',
                border: active === t.thread_id ? '1px solid rgba(212,163,115,0.30)' : '1px solid transparent',
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
                <span style={{
                  fontSize: 9, padding: '2px 6px', borderRadius: 4, letterSpacing: '0.06em',
                  background: t.channel === 'email' ? '#1A3A5A' : t.channel === 'sms' ? '#3A2A5A' : '#1E3024',
                  color: t.channel === 'email' ? '#88C5FF' : t.channel === 'sms' ? '#C9A6FF' : '#9FE3B5',
                }}>{(t.channel || '').toUpperCase()}</span>
                {t.unread > 0 && (
                  <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 999, background: '#5A1A18', color: '#FF8B85' }}>
                    {t.unread} new
                  </span>
                )}
              </div>
              <div style={{ color: TEXT_MD, fontSize: 10, fontFamily: fontMono, marginTop: 4 }}>{t.from_handle}</div>
              <div style={{ color: TEXT_HI, fontSize: 11, marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {t.last_message_preview}
              </div>
            </div>
          ))}
        </div>
        {/* Active thread + reply */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 280 }}>
          {!active ? (
            <div style={{ flex: 1, color: TEXT_LO, fontSize: 12, padding: 16, textAlign: 'center' }}>
              Select a conversation to view and reply.
            </div>
          ) : (
            <>
              <div data-testid="inbox-messages" style={{
                flex: 1, overflowY: 'auto', padding: '6px 4px', maxHeight: 280,
              }}>
                {messages.map((m, i) => (
                  <div key={i} style={{
                    display: 'flex',
                    justifyContent: m.direction === 'outbound' ? 'flex-end' : 'flex-start',
                    marginBottom: 6,
                  }}>
                    <div style={{
                      maxWidth: '78%', padding: '8px 10px', borderRadius: 8, fontSize: 12,
                      background: m.direction === 'outbound' ? 'rgba(212,163,115,0.12)' : 'rgba(10,8,5,0.5)',
                      border: `1px solid ${m.direction === 'outbound' ? 'rgba(212,163,115,0.25)' : 'rgba(212,163,115,0.08)'}`,
                      color: TEXT_HI,
                    }}>
                      <div style={{ color: TEXT_LO, fontSize: 9, marginBottom: 4, letterSpacing: '0.04em' }}>
                        {m.direction === 'outbound' ? 'YOU' : (m.from_handle || '—')} · {new Date(m.timestamp).toLocaleString()}
                      </div>
                      {m.message}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <input
                  data-testid="inbox-reply-input"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) sendReply(); }}
                  placeholder="Type a reply…"
                  style={{
                    flex: 1, padding: '8px 10px', borderRadius: 6,
                    background: 'rgba(10,8,5,0.7)', border: '1px solid rgba(212,163,115,0.20)',
                    color: TEXT_HI, fontSize: 12, outline: 'none',
                  }}
                />
                <button
                  data-testid="inbox-reply-send"
                  onClick={sendReply}
                  disabled={sending || !reply.trim()}
                  style={{
                    padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: sending ? '#3A3530' : 'linear-gradient(180deg, #FFE4A8 0%, #C9A84C 100%)',
                    color: sending ? TEXT_LO : '#0E1014', border: 'none',
                    cursor: sending ? 'wait' : 'pointer',
                  }}>
                  {sending ? '…' : 'Reply'}
                </button>
              </div>
              {status && <div style={{ marginTop: 6, fontSize: 11, color: status.startsWith('✅') ? '#bef264' : '#FF8B85' }}>{status}</div>}
            </>
          )}
        </div>
      </div>
    </Card>
  );
};

// ─── Row container ─────────────────────────────────────────────────────
export const CustomerResultsRow = () => (
  <>
    <div data-testid="customer-results-row" style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
      gap: 12,
    }}>
      <TileA />
      <TileB />
      <TileC />
    </div>
    <div data-testid="customer-inbox-row" style={{ marginTop: 14 }}>
      <TileInbox />
    </div>
  </>
);

export default CustomerResultsRow;
