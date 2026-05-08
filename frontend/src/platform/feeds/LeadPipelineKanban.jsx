/**
 * 3.11 Lead Pipeline Kanban
 * 7-column drag-and-drop board for the AUREM lifecycle state machine.
 * Columns: new → contacted → engaged → called_no_response → following_up → won → cold
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import useLivePolling from '../../hooks/useLivePolling';
import {
  Flame, Mail, MessageCircle, Phone, Check, Snowflake, MoreVertical,
  RefreshCw, TrendingUp, Users, DollarSign, Zap, StickyNote, X, PhoneOutgoing
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const STAGE_ORDER = ['new', 'contacted', 'engaged', 'called_no_response', 'following_up', 'won', 'cold'];

const STAGE_META = {
  new:                 { title: 'New',           icon: Users,          color: '#6b9fff', accent: 'rgba(100,150,255,0.15)' },
  contacted:           { title: 'Contacted',     icon: Mail,           color: '#a855f7', accent: 'rgba(168,85,247,0.15)' },
  engaged:             { title: 'Engaged',       icon: Flame,          color: '#ffab00', accent: 'rgba(255,171,0,0.18)' },
  called_no_response:  { title: 'Called',        icon: Phone,          color: '#FF6B00', accent: 'rgba(255,107,0,0.18)' },
  following_up:        { title: 'Following Up',  icon: Zap,            color: '#ff1744', accent: 'rgba(255,23,68,0.18)' },
  won:                 { title: 'Won ✅',         icon: Check,          color: '#16a34a', accent: 'rgba(22,163,74,0.18)' },
  cold:                { title: 'Cold ❄️',        icon: Snowflake,      color: '#64748b', accent: 'rgba(100,116,139,0.18)' },
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
};

export default function LeadPipelineKanban({ token }) {
  const [board, setBoard] = useState({});
  const [counts, setCounts] = useState({});
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedLead, setSelectedLead] = useState(null);
  const [toast, setToast] = useState(null);
  const dragRef = useRef(null);
  const [dragOver, setDragOver] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, mRes] = await Promise.all([
        fetch(`${API}/api/lifecycle/pipeline?limit_per_stage=30`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/lifecycle/metrics`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      const p = await pRes.json();
      const m = await mRes.json();
      setBoard(p.board || {});
      setCounts(p.counts || {});
      setMetrics(m);
    } catch (e) {
      console.error('pipeline load failed', e);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);
  // iter 270 — live refresh every 15s (pauses in background)
  useLivePolling(load, 15000);

  const moveStage = async (leadId, toStage) => {
    try {
      const r = await fetch(`${API}/api/lifecycle/move-stage`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id: leadId, to_stage: toStage, reason: 'manual_drag', force: true }),
      });
      const j = await r.json();
      if (j.ok) {
        setToast(`Moved → ${STAGE_META[toStage].title}`);
        load();
      } else {
        setToast(`⚠️ ${j.error || 'failed'}`);
      }
      setTimeout(() => setToast(null), 3000);
    } catch (e) {
      setToast(`Error: ${e.message}`);
      setTimeout(() => setToast(null), 3000);
    }
  };

  const onDragStart = (lead, fromStage) => {
    dragRef.current = { lead, fromStage };
  };

  const onDragOver = (stage, e) => {
    e.preventDefault();
    setDragOver(stage);
  };

  const onDrop = (toStage) => {
    const ctx = dragRef.current;
    setDragOver(null);
    if (!ctx) return;
    if (ctx.fromStage === toStage) return;
    moveStage(ctx.lead.lead_id, toStage);
    dragRef.current = null;
  };

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="pipeline-kanban">
      <div className="max-w-[1800px] mx-auto">
        {toast && (
          <div className="fixed top-20 right-6 z-50 px-4 py-3 rounded-lg shadow-2xl text-sm font-medium"
               style={{ background: 'linear-gradient(135deg, #ff6b00, #ffab00)', color: '#fff' }}
               data-testid="pipeline-toast">
            {toast}
          </div>
        )}

        {/* Header + metrics */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Lead Pipeline — Kanban</h1>
            <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>
              Zero leads lost. Drag any card to change its lifecycle stage.
            </p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
            style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00' }}
            data-testid="pipeline-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>

        {/* Metrics strip */}
        {metrics && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5" data-testid="pipeline-metrics">
            <MetricCard label="Total Leads" value={metrics.total_leads} icon={<Users className="w-4 h-4" />} color="#6b9fff" />
            <MetricCard label="Active" value={metrics.active_leads} icon={<Zap className="w-4 h-4" />} color="#FF6B00" />
            <MetricCard label="Pipeline Value" value={`$${(metrics.pipeline_value || 0).toLocaleString()}`} icon={<DollarSign className="w-4 h-4" />} color="#16a34a" />
            <MetricCard label="Won" value={metrics.by_stage?.won || 0} icon={<Check className="w-4 h-4" />} color="#16a34a" />
            <MetricCard label="Avg Days → Close" value={metrics.avg_days_to_close || 0} icon={<TrendingUp className="w-4 h-4" />} color="#ffab00" />
          </div>
        )}

        {/* Board */}
        <div className="grid grid-cols-7 gap-3 overflow-x-auto" style={{ minWidth: 1400 }}>
          {STAGE_ORDER.map(stage => {
            const meta = STAGE_META[stage];
            const Icon = meta.icon;
            const leads = board[stage] || [];
            const count = counts[stage] ?? leads.length;
            const isDragOver = dragOver === stage;
            return (
              <div
                key={stage}
                onDragOver={(e) => onDragOver(stage, e)}
                onDragLeave={() => setDragOver(null)}
                onDrop={() => onDrop(stage)}
                className="flex flex-col rounded-lg p-2 min-h-[500px] transition"
                style={{
                  background: isDragOver ? meta.accent : 'rgba(255,255,255,0.03)',
                  border: isDragOver ? `2px dashed ${meta.color}` : '1px solid rgba(255,255,255,0.06)',
                }}
                data-testid={`pipeline-column-${stage}`}
              >
                <div className="flex items-center justify-between mb-3 px-1">
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4" style={{ color: meta.color }} />
                    <span className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>{meta.title}</span>
                  </div>
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: meta.accent, color: meta.color }}>{count}</span>
                </div>

                <div className="flex-1 space-y-2 overflow-y-auto aurem-scroll max-h-[calc(100vh-320px)]">
                  {leads.length === 0 && (
                    <div className="text-center text-xs py-6" style={{ color: 'rgba(255,255,255,0.3)' }}>
                      No leads
                    </div>
                  )}
                  {leads.map((lead, i) => (
                    <LeadCard
                      key={lead.lead_id || i}
                      lead={lead}
                      stage={stage}
                      meta={meta}
                      onDragStart={() => onDragStart(lead, stage)}
                      onClick={() => setSelectedLead(lead)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Drawer */}
        {selectedLead && (
          <LeadDrawer
            lead={selectedLead}
            token={token}
            onClose={() => setSelectedLead(null)}
            onRefresh={load}
          />
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon, color }) {
  return (
    <div className="aurem-glass-card p-3">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>
        <span style={{ color }}>{icon}</span>{label}
      </div>
      <div className="text-xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}

function LeadCard({ lead, stage, meta, onDragStart, onClick }) {
  const drip = lead.drip || {};
  const touchpoints = lead.touchpoints || [];
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="rounded-md p-2.5 cursor-grab active:cursor-grabbing transition hover:brightness-110"
      style={{ background: 'rgba(255,255,255,0.05)', border: `1px solid ${meta.accent}` }}
      data-testid={`lead-card-${lead.lead_id}`}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="font-semibold text-sm truncate flex-1" style={{ color: 'var(--aurem-heading)' }}>
          {lead.business_name || '(no name)'}
        </div>
        {lead.flame_score > 50 && (
          <span title="Flame Score" className="text-xs font-bold flex items-center gap-0.5" style={{ color: '#ff1744' }}>
            <Flame className="w-3 h-3" />{Math.round(lead.flame_score)}
          </span>
        )}
      </div>
      {lead.contact_name && (
        <div className="text-xs truncate" style={{ color: 'var(--aurem-body-secondary)' }}>
          {lead.contact_name}
        </div>
      )}
      <div className="flex items-center gap-2 mt-2 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
        <span>⏱ {lead.days_in_stage}d in stage</span>
        {drip.next_action_at && (
          <span>· 📅 {fmtDate(drip.next_action_at)}</span>
        )}
      </div>
      {touchpoints.length > 0 && (
        <div className="flex items-center gap-1 mt-1.5">
          {touchpoints.slice(-4).map((t, i) => {
            const Icon =
              t.channel === 'email' ? Mail :
              t.channel === 'whatsapp' ? MessageCircle :
              t.channel === 'sms' ? MessageCircle :
              t.channel === 'call' ? Phone : Zap;
            const c = t.status === 'sent' ? '#16a34a' : t.status === 'failed' ? '#ef4444' : t.status === 'skipped_gated' ? '#64748b' : '#ffab00';
            return <Icon key={i} className="w-3 h-3" style={{ color: c }} title={`${t.channel} · ${t.kind} · ${t.status}`} />;
          })}
        </div>
      )}
    </div>
  );
}

function LeadDrawer({ lead, token, onClose, onRefresh }) {
  const [detail, setDetail] = useState(lead);
  const [note, setNote] = useState('');
  const [blastChannel, setBlastChannel] = useState('whatsapp');
  const [blastBody, setBlastBody] = useState('');
  const [blastSubject, setBlastSubject] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/lifecycle/lead/${lead.lead_id}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setDetail).catch(() => {});
  }, [lead.lead_id, token]);

  const addNote = async () => {
    if (!note.trim()) return;
    setBusy(true);
    await fetch(`${API}/api/lifecycle/add-note`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: lead.lead_id, note }),
    });
    setNote('');
    setBusy(false);
    const r = await fetch(`${API}/api/lifecycle/lead/${lead.lead_id}`, { headers: { Authorization: `Bearer ${token}` } });
    setDetail(await r.json());
  };

  const sendBlast = async () => {
    if (!blastBody.trim()) return;
    setBusy(true);
    const r = await fetch(`${API}/api/lifecycle/manual-blast`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: lead.lead_id, channel: blastChannel, body: blastBody, subject: blastSubject }),
    });
    const j = await r.json();
    setBusy(false);
    setBlastBody('');
    onRefresh();
    alert(j.ok ? `Blast sent via ${blastChannel}` : `Failed: ${j.error || 'unknown'}`);
  };

  const stage = detail.lifecycle_stage || 'new';
  const meta = STAGE_META[stage];
  const gate = (detail.verification?.channel_gating) || {};

  return (
    <div className="fixed inset-0 z-40 flex justify-end" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl h-full overflow-y-auto p-6"
        style={{ background: '#111', borderLeft: '1px solid rgba(255,255,255,0.1)' }}
        data-testid="lead-drawer"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold" style={{ color: '#fff' }}>{detail.business_name || '(no name)'}</h2>
            <span className="text-xs px-2 py-0.5 rounded-full font-bold mt-1 inline-block" style={{ background: meta.accent, color: meta.color }}>
              {meta.title}
            </span>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-white/10"><X className="w-5 h-5 text-white" /></button>
        </div>

        {/* Basic info */}
        <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
          <Kv label="Contact" value={detail.contact_name || '—'} />
          <Kv label="Phone" value={detail.phone || '—'} />
          <Kv label="Email" value={detail.email || '—'} />
          <Kv label="Website" value={detail.website_url || '—'} />
        </div>

        {/* Channel gates */}
        <div className="mb-4 flex gap-2 flex-wrap">
          {['whatsapp', 'email', 'sms', 'call'].map(ch => {
            const ok = gate[ch] !== false;
            return (
              <span key={ch} className="text-[10px] px-2 py-1 rounded-full"
                    style={{ background: ok ? 'rgba(22,163,74,0.15)' : 'rgba(239,68,68,0.15)', color: ok ? '#16a34a' : '#ef4444' }}>
                {ch}: {ok ? 'OK' : 'GATED'}
              </span>
            );
          })}
          {detail.dnc && <span className="text-[10px] px-2 py-1 rounded-full" style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444' }}>DNC</span>}
        </div>

        {/* Move-stage buttons */}
        <div className="mb-4">
          <div className="text-xs uppercase mb-2" style={{ color: '#888' }}>Move stage</div>
          <div className="flex flex-wrap gap-1">
            {STAGE_ORDER.map(s => (
              <button
                key={s}
                onClick={async () => {
                  await fetch(`${API}/api/lifecycle/move-stage`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lead_id: lead.lead_id, to_stage: s, reason: 'manual_drawer', force: true }),
                  });
                  onRefresh();
                  onClose();
                }}
                disabled={s === stage}
                className="text-xs px-2 py-1 rounded disabled:opacity-40"
                style={{ background: STAGE_META[s].accent, color: STAGE_META[s].color }}
                data-testid={`drawer-move-${s}`}
              >
                {STAGE_META[s].title}
              </button>
            ))}
          </div>
        </div>

        {/* Add note */}
        <div className="mb-4">
          <div className="text-xs uppercase mb-2 flex items-center gap-1" style={{ color: '#888' }}>
            <StickyNote className="w-3 h-3" /> Add note
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder="Note for the CRM…"
            className="w-full text-xs p-2 rounded border"
            style={{ background: 'rgba(0,0,0,0.3)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff' }}
            data-testid="drawer-note-input"
          />
          <button
            onClick={addNote}
            disabled={busy || !note.trim()}
            className="mt-2 text-xs px-3 py-1.5 rounded"
            style={{ background: 'rgba(255,107,0,0.15)', color: '#FF6B00' }}
            data-testid="drawer-add-note-btn"
          >Add note</button>
        </div>

        {/* Manual blast */}
        <div className="mb-4">
          <div className="text-xs uppercase mb-2 flex items-center gap-1" style={{ color: '#888' }}>
            <PhoneOutgoing className="w-3 h-3" /> Manual blast
          </div>
          <div className="flex gap-1 mb-2">
            {['whatsapp', 'email', 'sms'].map(ch => (
              <button
                key={ch}
                onClick={() => setBlastChannel(ch)}
                className="text-xs px-2 py-1 rounded"
                style={{
                  background: blastChannel === ch ? '#FF6B00' : 'rgba(255,255,255,0.05)',
                  color: blastChannel === ch ? '#fff' : '#ccc',
                }}
                data-testid={`drawer-blast-ch-${ch}`}
              >{ch}</button>
            ))}
          </div>
          {blastChannel === 'email' && (
            <input
              value={blastSubject}
              onChange={(e) => setBlastSubject(e.target.value)}
              placeholder="Subject"
              className="w-full text-xs p-2 rounded border mb-2"
              style={{ background: 'rgba(0,0,0,0.3)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff' }}
              data-testid="drawer-blast-subject"
            />
          )}
          <textarea
            value={blastBody}
            onChange={(e) => setBlastBody(e.target.value)}
            rows={3}
            placeholder="Message body…"
            className="w-full text-xs p-2 rounded border"
            style={{ background: 'rgba(0,0,0,0.3)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff' }}
            data-testid="drawer-blast-body"
          />
          <button
            onClick={sendBlast}
            disabled={busy || !blastBody.trim()}
            className="mt-2 text-xs px-3 py-1.5 rounded"
            style={{ background: '#FF6B00', color: '#fff' }}
            data-testid="drawer-blast-send"
          >Send blast</button>
        </div>

        {/* Touchpoints history */}
        <div className="mb-4">
          <div className="text-xs uppercase mb-2" style={{ color: '#888' }}>Touchpoints ({(detail.touchpoints || []).length})</div>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {(detail.touchpoints || []).slice(-20).reverse().map((t, i) => (
              <div key={i} className="text-[10px] p-2 rounded flex items-start justify-between" style={{ background: 'rgba(255,255,255,0.04)' }}>
                <div>
                  <span className="font-bold" style={{ color: '#fff' }}>{t.channel}</span>
                  <span className="mx-1 text-[#888]">·</span>
                  <span style={{ color: '#ccc' }}>{t.kind}</span>
                </div>
                <div className="text-right">
                  <span className="font-medium" style={{ color: t.status === 'sent' ? '#16a34a' : t.status === 'failed' ? '#ef4444' : '#ffab00' }}>
                    {t.status}
                  </span>
                  <div className="text-[9px]" style={{ color: '#666' }}>{new Date(t.at).toLocaleString()}</div>
                </div>
              </div>
            ))}
            {(!detail.touchpoints || detail.touchpoints.length === 0) && (
              <div className="text-xs text-center py-3" style={{ color: '#666' }}>No touchpoints yet</div>
            )}
          </div>
        </div>

        {/* Notes */}
        {(detail.notes_log || []).length > 0 && (
          <div className="mb-4">
            <div className="text-xs uppercase mb-2" style={{ color: '#888' }}>Notes</div>
            <div className="space-y-1">
              {(detail.notes_log || []).slice(-5).reverse().map((n, i) => (
                <div key={i} className="text-xs p-2 rounded" style={{ background: 'rgba(255,107,0,0.08)', color: '#fff' }}>
                  <div>{n.note}</div>
                  <div className="text-[10px] mt-1" style={{ color: '#888' }}>{n.by} · {new Date(n.at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Kv({ label, value }) {
  return (
    <div>
      <div className="uppercase tracking-wider" style={{ color: '#888', fontSize: 9 }}>{label}</div>
      <div className="truncate" style={{ color: '#fff' }}>{value}</div>
    </div>
  );
}
