/**
 * AdminBrainPage — Single-pane autonomous stack pipeline view
 * ============================================================
 * Reads:
 *   GET /api/admin/autonomous/overview          → 11-component snapshot
 *   GET /api/admin/autonomous/pipeline-flow     → recent flow trace
 *
 * Auto-refresh every 15s. Read-only — no actions, no LLM calls.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  Activity, AlertTriangle, CheckCircle2, Cpu, Database,
  GitBranch, RefreshCw, Sparkles, Zap, BookOpen, ShieldCheck,
} from 'lucide-react';

const API = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

const getAdminToken = () =>
  sessionStorage.getItem('platform_token') ||
  localStorage.getItem('platform_token') ||
  localStorage.getItem('aurem_admin_token') ||
  sessionStorage.getItem('aurem_admin_token') ||
  localStorage.getItem('token') ||
  '';

const fetchJSON = async (path) => {
  const t = getAdminToken();
  const r = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return r.json();
};

const PIPELINE_STEPS = [
  { key: '1_client_errors',          icon: AlertTriangle, label: 'Client Errors',     desc: 'Sentinel signal ingest' },
  { key: '2_sentinel_repair_loop',   icon: RefreshCw,     label: 'Repair Loop',       desc: 'Autonomous 60s tick' },
  { key: '3_sentinel_ai_diagnose',   icon: Sparkles,      label: 'AI Diagnose',       desc: 'Triage → cache → Claude' },
  { key: '4_llm_response_cache',     icon: Database,      label: 'LLM Cache',         desc: 'Token-saving roundtrip' },
  { key: '5_llm_costs',              icon: Zap,           label: 'LLM Costs',         desc: 'Gateway-tracked spend' },
  { key: '6_council_detailed',       icon: ShieldCheck,   label: 'Council Detailed',  desc: 'Voter-level decisions' },
  { key: '7_council_legacy',         icon: ShieldCheck,   label: 'Council Aggregate', desc: 'Cumulative votes' },
  { key: '8_ora_proposal_bridge',    icon: GitBranch,     label: 'Proposal Bridge',   desc: 'Suggestion → Dev Console' },
  { key: '9_repair_suggestions',     icon: Cpu,           label: 'Repair Suggestions',desc: 'Pending Claude diagnoses' },
  { key: '10_ora_dev_actions',       icon: CheckCircle2,  label: 'Dev Console',       desc: 'Awaiting human approval' },
  { key: '11_ora_brain_thoughts',    icon: BookOpen,      label: 'Brain Thoughts',    desc: 'Learning corpus' },
];

const STATUS_COLOR = (h24) => {
  if (h24 < 0)   return '#7A7468'; // unknown / collection missing
  if (h24 === 0) return '#F0A030';
  if (h24 > 0)   return '#4AD4A0';
  return '#7A7468';
};

const COMP_BG = '#0E0E0F';
const COMP_BORDER = '#22201D';
const ACCENT = '#D4AF7A';

export default function AdminBrainPage() {
  const [overview, setOverview] = useState(null);
  const [flow, setFlow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const refresh = useCallback(async () => {
    try {
      setErr('');
      const [o, f] = await Promise.all([
        fetchJSON('/api/admin/autonomous/overview'),
        fetchJSON('/api/admin/autonomous/pipeline-flow?limit=10'),
      ]);
      setOverview(o);
      setFlow(f);
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div data-testid="admin-brain-page" style={{
      padding: '24px', minHeight: '100vh', background: '#08080A', color: '#E8E2D4',
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto',
    }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{
          fontSize: 'clamp(20px, 3.5vw, 28px)', margin: 0, fontWeight: 600,
          letterSpacing: '-0.01em',
        }}>
          🧠 Autonomous Stack — Pipeline View
        </h1>
        <p style={{ color: '#8B8475', margin: '6px 0 0 0', fontSize: 13 }}>
          Read-only single-pane snapshot of the 11-component A2A → Council → ORA loop.
          Auto-refresh every 15s.
        </p>
      </header>

      {loading && (
        <div style={{ color: '#8B8475', padding: 16 }}>Loading pipeline…</div>
      )}

      {err && (
        <div data-testid="admin-brain-error" style={{
          padding: 12, background: '#2A1612', border: '1px solid #5A2A20',
          color: '#E0524A', borderRadius: 8, marginBottom: 16, fontSize: 13,
        }}>
          {err}
        </div>
      )}

      {/* Top row — pipeline component cards */}
      <section style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12, marginBottom: 24,
      }}>
        {PIPELINE_STEPS.map((step, idx) => {
          const data = overview?.components?.[step.key] || {};
          const h24 = typeof data.h24 === 'number' ? data.h24 : -1;
          const total = typeof data.total === 'number' ? data.total : null;
          const Icon = step.icon;
          const dot = STATUS_COLOR(h24);
          return (
            <div
              key={step.key}
              data-testid={`pipeline-card-${idx + 1}`}
              style={{
                background: COMP_BG, border: `1px solid ${COMP_BORDER}`,
                borderRadius: 10, padding: 14,
              }}
            >
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
              }}>
                <Icon size={16} color={ACCENT} />
                <span style={{ fontSize: 12, color: '#8B8475', fontWeight: 500 }}>
                  STEP {idx + 1}
                </span>
                <span style={{
                  marginLeft: 'auto', width: 8, height: 8, borderRadius: '50%',
                  background: dot,
                }} />
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>
                {step.label}
              </div>
              <div style={{ fontSize: 11, color: '#8B8475', marginBottom: 10 }}>
                {step.desc}
              </div>
              <div style={{ display: 'flex', gap: 10, fontSize: 12 }}>
                {total !== null && (
                  <div>
                    <div style={{ color: '#8B8475', fontSize: 10 }}>TOTAL</div>
                    <div style={{ color: '#E8E2D4', fontWeight: 600 }}>
                      {total < 0 ? '—' : total.toLocaleString()}
                    </div>
                  </div>
                )}
                <div>
                  <div style={{ color: '#8B8475', fontSize: 10 }}>24H</div>
                  <div style={{ color: dot, fontWeight: 600 }}>
                    {h24 < 0 ? '—' : h24.toLocaleString()}
                  </div>
                </div>
              </div>
              {/* Inline path-breakdown for AI Diagnose card */}
              {step.key === '3_sentinel_ai_diagnose' && data.diag_path_breakdown && (
                <div style={{
                  marginTop: 8, paddingTop: 8, borderTop: `1px solid ${COMP_BORDER}`,
                  fontSize: 11, color: '#8B8475',
                }}>
                  {Object.entries(data.diag_path_breakdown).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{k}</span><span style={{ color: '#E8E2D4' }}>{v}</span>
                    </div>
                  ))}
                </div>
              )}
              {/* Inline verdict split for Council Detailed card */}
              {step.key === '6_council_detailed' && data.verdicts && (
                <div style={{
                  marginTop: 8, paddingTop: 8, borderTop: `1px solid ${COMP_BORDER}`,
                  fontSize: 11, color: '#8B8475',
                }}>
                  {Object.entries(data.verdicts).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{k}</span><span style={{
                        color: k === 'APPROVED' ? '#4AD4A0' :
                               k === 'REJECTED' ? '#E0524A' : '#E8E2D4',
                      }}>{v}</span>
                    </div>
                  ))}
                </div>
              )}
              {/* Pending count for Dev Console */}
              {step.key === '10_ora_dev_actions' && typeof data.pending === 'number' && (
                <div style={{
                  marginTop: 8, paddingTop: 8, borderTop: `1px solid ${COMP_BORDER}`,
                  fontSize: 11, color: '#F0A030',
                }}>
                  PENDING APPROVAL: <strong>{data.pending}</strong>
                </div>
              )}
            </div>
          );
        })}
      </section>

      {/* Recent flow trace */}
      <section data-testid="pipeline-flow-section">
        <h2 style={{
          fontSize: 16, margin: '0 0 12px 0', fontWeight: 600,
          color: '#E8E2D4',
        }}>
          Recent Pipeline Flow
        </h2>
        <div style={{
          background: COMP_BG, border: `1px solid ${COMP_BORDER}`,
          borderRadius: 10, overflow: 'hidden',
        }}>
          {!flow?.flow?.length ? (
            <div style={{ padding: 16, color: '#8B8475', fontSize: 13 }}>
              No recent suggestions in the flow.
            </div>
          ) : flow.flow.map((row, i) => (
            <div
              key={row.suggestion?.suggestion_id || i}
              data-testid={`flow-row-${i}`}
              style={{
                padding: 14,
                borderBottom: i < flow.flow.length - 1 ? `1px solid ${COMP_BORDER}` : 'none',
                display: 'grid',
                gridTemplateColumns: 'minmax(140px, 0.5fr) minmax(200px, 1.5fr) minmax(140px, 0.7fr) minmax(140px, 0.7fr)',
                gap: 16, alignItems: 'start', fontSize: 12,
              }}
            >
              <div>
                <div style={{ color: '#8B8475', fontSize: 10 }}>SUGGESTION</div>
                <div style={{ color: '#E8E2D4', fontFamily: 'monospace' }}>
                  {row.suggestion?.suggestion_id?.slice(0, 14) || '—'}
                </div>
                <div style={{ color: '#8B8475', fontSize: 10, marginTop: 4 }}>
                  {row.suggestion?.severity} · path={row.suggestion?.diagnose_path || 'unknown'}
                </div>
                {row.suggestion?.triage_category && (
                  <div style={{ color: ACCENT, fontSize: 10, marginTop: 2 }}>
                    triage: {row.suggestion.triage_category}
                  </div>
                )}
              </div>
              <div>
                <div style={{ color: '#8B8475', fontSize: 10 }}>ROOT CAUSE</div>
                <div style={{ color: '#E8E2D4' }}>
                  {(row.suggestion?.root_cause || '—').slice(0, 220)}
                </div>
                {row.suggestion?.error_snapshot?.url && (
                  <div style={{ color: '#8B8475', fontSize: 10, marginTop: 4 }}>
                    {row.suggestion.error_snapshot.method || ''} {row.suggestion.error_snapshot.url}
                  </div>
                )}
              </div>
              <div>
                <div style={{ color: '#8B8475', fontSize: 10 }}>COUNCIL</div>
                <div style={{
                  color: row.council?.verdict === 'APPROVED' ? '#4AD4A0' :
                         row.council?.verdict === 'REJECTED' ? '#E0524A' : '#8B8475',
                  fontWeight: 600,
                }}>
                  {row.council?.verdict || '—'}
                </div>
                {row.council?.confidence !== undefined && (
                  <div style={{ color: '#8B8475', fontSize: 10 }}>
                    conf={row.council.confidence?.toFixed(2)}
                  </div>
                )}
              </div>
              <div>
                <div style={{ color: '#8B8475', fontSize: 10 }}>DEV ACTION</div>
                <div style={{
                  color: row.dev_action?.status === 'pending' ? '#F0A030' :
                         row.dev_action?.status === 'approved' ? '#4AD4A0' :
                         row.dev_action?.status === 'rejected' ? '#E0524A' : '#8B8475',
                  fontWeight: 600,
                }}>
                  {row.dev_action?.status || '—'}
                </div>
                {row.dev_action?.action_id && (
                  <div style={{ color: '#8B8475', fontSize: 10, fontFamily: 'monospace' }}>
                    {row.dev_action.action_id.slice(0, 14)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer style={{ marginTop: 24, color: '#5A5648', fontSize: 11 }}>
        Last refresh: {overview?.ts || '—'} · Agent actions 24h: {overview?.agent_actions_24h ?? '—'}
        <button
          data-testid="admin-brain-refresh"
          onClick={refresh}
          style={{
            marginLeft: 12, padding: '4px 10px', background: 'transparent',
            border: `1px solid ${COMP_BORDER}`, borderRadius: 6, color: ACCENT,
            cursor: 'pointer', fontSize: 11,
          }}
        >
          <RefreshCw size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          Refresh
        </button>
      </footer>
    </div>
  );
}
