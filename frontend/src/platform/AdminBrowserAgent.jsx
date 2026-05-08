/**
 * AdminBrowserAgent — iter 282e · Phase 2.5F
 * ──────────────────────────────────────────────────────────────
 * Dev console UI for ORA's Browser Agent.
 * Three sections:
 *   1. Pending approvals — queued browser_navigate / browser_screenshot
 *      actions from `ora_dev_actions`. Approve → auto-fires, result shown.
 *   2. Recent actions — last 50 captured screenshots + extracts.
 *   3. Ad-hoc screenshot — admin types a URL, hits "Capture".
 *      Internal URLs fire instantly; external URLs get queued.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Camera, CheckCircle2, ExternalLink, Loader2, RefreshCw, ShieldAlert, XCircle } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const GOLD = '#C9A227';
const BORDER = 'rgba(201,162,39,0.18)';
const PANEL = 'rgba(13,13,23,0.72)';

export default function AdminBrowserAgent() {
  const token = getPlatformToken();
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  const [pending, setPending] = useState([]);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adhocUrl, setAdhocUrl] = useState('');
  const [adhocBusy, setAdhocBusy] = useState(false);
  const [adhocResult, setAdhocResult] = useState(null);
  const [error, setError] = useState('');
  const [actingId, setActingId] = useState(null);

  const loadAll = useCallback(async () => {
    if (!token) return;
    setError('');
    try {
      const [pRes, rRes] = await Promise.all([
        fetch(`${API}/api/admin/ora-dev?status=pending&limit=50`, { headers }),
        fetch(`${API}/api/browser-agent-v2/recent?limit=50`, { headers }),
      ]);
      if (pRes.ok) {
        const d = await pRes.json();
        const rows = (d.proposals || d.rows || []).filter(
          p => p.kind === 'browser_action' || (p.action_type || '').startsWith('browser_'),
        );
        setPending(rows);
      }
      if (rRes.ok) {
        const d = await rRes.json();
        setRecent(d.actions || []);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { loadAll(); const iv = setInterval(loadAll, 15000); return () => clearInterval(iv); }, [loadAll]);

  const act = async (proposalId, decision) => {
    setActingId(proposalId);
    try {
      const r = await fetch(
        `${API}/api/admin/ora-dev/${proposalId}/${decision}`,
        { method: 'POST', headers },
      );
      if (!r.ok) {
        const t = await r.text();
        setError(`${decision} failed: ${t}`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setActingId(null);
      loadAll();
    }
  };

  const captureAdhoc = async () => {
    if (!adhocUrl.trim()) return;
    setAdhocBusy(true); setAdhocResult(null); setError('');
    try {
      const r = await fetch(`${API}/api/browser-agent-v2/screenshot`, {
        method: 'POST', headers,
        body: JSON.stringify({
          url: adhocUrl.trim(), full_page: true,
          reason: 'Admin Dev Console ad-hoc screenshot',
        }),
      });
      const d = await r.json();
      setAdhocResult(d);
      loadAll();
    } catch (e) {
      setError(String(e));
    } finally {
      setAdhocBusy(false);
    }
  };

  if (!token) {
    return (
      <div style={{ padding: 40, color: '#E8E0D0' }} data-testid="browser-agent-no-auth">
        Please log in as admin.
      </div>
    );
  }

  return (
    <div
      data-testid="admin-browser-agent"
      style={{
        padding: '28px 32px 60px',
        minHeight: '100vh',
        color: '#E8E0D0',
        fontFamily: "'Jost', sans-serif",
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
        <Camera size={22} style={{ color: GOLD }} />
        <div>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 22, color: '#FFF', letterSpacing: '0.04em' }}>
            ORA Browser Agent
          </div>
          <div style={{ fontSize: 11, color: '#8A8070', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 4 }}>
            Phase 2.5F · Approvals · Screenshots · Extracts
          </div>
        </div>
        <button
          onClick={loadAll}
          data-testid="browser-agent-refresh"
          style={{
            marginLeft: 'auto', padding: '8px 14px', borderRadius: 8,
            background: 'transparent', border: `1px solid ${BORDER}`,
            color: GOLD, cursor: 'pointer', fontSize: 12,
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && (
        <div data-testid="browser-agent-error" style={{
          padding: 12, marginBottom: 18, borderRadius: 10,
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#FCA5A5', fontSize: 13,
        }}>{error}</div>
      )}

      {/* Ad-hoc capture */}
      <section
        data-testid="browser-agent-adhoc"
        style={{
          background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 14,
          padding: 20, marginBottom: 28, backdropFilter: 'blur(14px)',
        }}
      >
        <div style={{ fontSize: 13, color: GOLD, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 12, fontWeight: 700 }}>
          Capture screenshot
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <input
            data-testid="browser-agent-url"
            type="url"
            placeholder="https://example.com"
            value={adhocUrl}
            onChange={(e) => setAdhocUrl(e.target.value)}
            style={{
              flex: 1, minWidth: 260,
              background: 'rgba(0,0,0,0.35)', border: `1px solid ${BORDER}`,
              color: '#E8E0D0', padding: '10px 14px', borderRadius: 8,
              fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') captureAdhoc(); }}
          />
          <button
            data-testid="browser-agent-capture"
            onClick={captureAdhoc}
            disabled={adhocBusy || !adhocUrl.trim()}
            style={{
              padding: '10px 22px', borderRadius: 8,
              background: adhocBusy ? '#55460F' : GOLD, color: '#0A0A00',
              border: 'none', cursor: adhocBusy ? 'wait' : 'pointer',
              fontWeight: 700, letterSpacing: '0.08em', fontSize: 12, textTransform: 'uppercase',
              display: 'inline-flex', alignItems: 'center', gap: 8,
            }}
          >
            {adhocBusy ? <Loader2 size={14} className="animate-spin" /> : <Camera size={14} />}
            {adhocBusy ? 'Capturing…' : 'Capture'}
          </button>
        </div>
        {adhocResult && (
          <div data-testid="browser-agent-adhoc-result" style={{
            marginTop: 14, padding: 12, borderRadius: 10,
            background: adhocResult.ok ? 'rgba(34,197,94,0.08)' : 'rgba(245,158,11,0.08)',
            border: `1px solid ${adhocResult.ok ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.3)'}`,
            fontSize: 12,
          }}>
            {adhocResult.pending ? (
              <span>
                <ShieldAlert size={12} style={{ verticalAlign: 'middle', color: '#F59E0B' }} /> External URL — queued for approval. Proposal id:{' '}
                <code style={{ color: GOLD }}>{adhocResult.proposal_id}</code>
              </span>
            ) : adhocResult.ok ? (
              <span>
                <CheckCircle2 size={12} style={{ verticalAlign: 'middle', color: '#22C55E' }} /> Captured ·{' '}
                <a href={adhocResult.image_url} target="_blank" rel="noopener noreferrer" style={{ color: GOLD }}>
                  View image <ExternalLink size={10} />
                </a>
              </span>
            ) : (
              <span style={{ color: '#FCA5A5' }}>
                <XCircle size={12} style={{ verticalAlign: 'middle' }} /> {adhocResult.error || 'Failed'}
              </span>
            )}
          </div>
        )}
      </section>

      {/* Pending approvals */}
      <section style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 13, color: GOLD, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 14, fontWeight: 700 }}>
          Pending approvals · {pending.length}
        </div>
        {loading && <div style={{ color: '#8A8070', fontSize: 13 }}>Loading…</div>}
        {!loading && pending.length === 0 && (
          <div data-testid="browser-agent-no-pending" style={{
            padding: 18, borderRadius: 12, background: PANEL, border: `1px solid ${BORDER}`,
            color: '#8A8070', fontSize: 13, textAlign: 'center',
          }}>
            No browser actions pending review.
          </div>
        )}
        {pending.map((p) => (
          <div key={p.proposal_id}
            data-testid={`browser-action-pending-${p.proposal_id}`}
            style={{
              padding: 16, marginBottom: 10, borderRadius: 12,
              background: PANEL, border: `1px solid ${BORDER}`,
              display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap',
            }}>
            <div style={{ flex: 1, minWidth: 260 }}>
              <div style={{ fontSize: 11, color: '#8A8070', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                {p.action_type || p.kind}
              </div>
              <div style={{ color: '#E8E0D0', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, marginTop: 4, wordBreak: 'break-all' }}>
                {p.target_url || p.url || '—'}
              </div>
              <div style={{ fontSize: 11, color: '#8A8070', marginTop: 4 }}>
                {p.reason || p.description || 'No reason'} · by <code>{p.triggered_by || 'system'}</code>
              </div>
            </div>
            <button
              data-testid={`browser-action-approve-${p.proposal_id}`}
              onClick={() => act(p.proposal_id, 'approve')}
              disabled={actingId === p.proposal_id}
              style={{
                padding: '8px 16px', borderRadius: 8,
                background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.4)',
                color: '#86EFAC', cursor: 'pointer', fontSize: 12, fontWeight: 700, letterSpacing: '0.08em',
              }}
            >
              {actingId === p.proposal_id ? '…' : 'APPROVE'}
            </button>
            <button
              data-testid={`browser-action-reject-${p.proposal_id}`}
              onClick={() => act(p.proposal_id, 'reject')}
              disabled={actingId === p.proposal_id}
              style={{
                padding: '8px 16px', borderRadius: 8,
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                color: '#FCA5A5', cursor: 'pointer', fontSize: 12, fontWeight: 700, letterSpacing: '0.08em',
              }}
            >
              REJECT
            </button>
          </div>
        ))}
      </section>

      {/* Recent actions */}
      <section>
        <div style={{ fontSize: 13, color: GOLD, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 14, fontWeight: 700 }}>
          Recent actions · {recent.length}
        </div>
        {!loading && recent.length === 0 && (
          <div data-testid="browser-agent-no-recent" style={{
            padding: 18, borderRadius: 12, background: PANEL, border: `1px solid ${BORDER}`,
            color: '#8A8070', fontSize: 13, textAlign: 'center',
          }}>
            No captured actions yet.
          </div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
          {recent.map((a, idx) => (
            <div key={idx}
              data-testid={`browser-action-recent-${idx}`}
              style={{
                padding: 14, borderRadius: 12,
                background: PANEL, border: `1px solid ${BORDER}`,
              }}>
              <div style={{ fontSize: 10, color: '#8A8070', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                {a.kind} · {a.timestamp?.slice(5, 16) || ''}
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#E8E0D0', marginTop: 4, wordBreak: 'break-all' }}>
                {a.url || '—'}
              </div>
              {a.result?.image_url && (
                <a href={a.result.image_url} target="_blank" rel="noopener noreferrer">
                  <img
                    src={a.result.image_url} alt="screenshot"
                    style={{
                      width: '100%', marginTop: 10, borderRadius: 8,
                      border: `1px solid ${BORDER}`, objectFit: 'cover',
                      maxHeight: 180,
                    }}
                  />
                </a>
              )}
              {a.result?.error && (
                <div style={{ marginTop: 8, fontSize: 11, color: '#FCA5A5' }}>
                  Error: {a.result.error}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
