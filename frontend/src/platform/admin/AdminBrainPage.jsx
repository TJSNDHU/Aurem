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
  const [notif, setNotif] = useState(null);
  const [deploy, setDeploy] = useState(null);
  const [dogfood, setDogfood] = useState(null);
  const [dogfoodOpen, setDogfoodOpen] = useState(false);
  const [auditLog, setAuditLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const refresh = useCallback(async () => {
    try {
      setErr('');
      // allSettled so one failing endpoint doesn't blank the whole page.
      const [ro, rf, rn, rd, rdp, ral] = await Promise.allSettled([
        fetchJSON('/api/admin/autonomous/overview'),
        fetchJSON('/api/admin/autonomous/pipeline-flow?limit=10'),
        fetchJSON('/api/admin/autonomous/notifications?limit=10&unread_only=true'),
        fetchJSON('/api/admin/deploy-readiness'),
        fetchJSON('/api/admin/dogfood/pulse'),
        fetchJSON('/api/admin/audit-log?limit=20'),
      ]);
      if (ro.status === 'fulfilled') setOverview(ro.value);
      if (rf.status === 'fulfilled') setFlow(rf.value);
      if (rn.status === 'fulfilled') setNotif(rn.value);
      if (rd.status === 'fulfilled') setDeploy(rd.value);
      if (rdp.status === 'fulfilled') setDogfood(rdp.value);
      if (ral.status === 'fulfilled') setAuditLog(ral.value);

      // Surface only if EVERYTHING failed
      const allFailed = [ro, rf, rn, rd].every(r => r.status === 'rejected');
      if (allFailed) {
        setErr(String(ro.reason?.message || ro.reason || 'all endpoints failed'));
      }
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
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        }}>
          🧠 Autonomous Stack — Pipeline View
          {notif?.high_risk_unread > 0 && (
            <span
              data-testid="admin-brain-high-risk-badge"
              style={{
                background: '#5A1A18', border: '1px solid #E0524A',
                color: '#FF8B85', fontSize: 12, padding: '4px 10px',
                borderRadius: 999, fontWeight: 600, letterSpacing: '0.02em',
              }}
              title="Unread HIGH-RISK proposals awaiting your review"
            >
              🚨 {notif.high_risk_unread} HIGH RISK
            </span>
          )}
          {notif?.unread_total > (notif?.high_risk_unread || 0) && (
            <span
              data-testid="admin-brain-other-unread-badge"
              style={{
                background: '#2A2317', border: '1px solid #D4AF7A',
                color: '#D4AF7A', fontSize: 12, padding: '4px 10px',
                borderRadius: 999, fontWeight: 600,
              }}
              title="Other unread notifications"
            >
              {(notif.unread_total || 0) - (notif.high_risk_unread || 0)} new
            </span>
          )}
          {dogfood?.summary?.has_dead_zones && (
            <span
              data-testid="admin-brain-dogfood-dead-badge"
              onClick={() => setDogfoodOpen(true)}
              style={{
                background: '#5A1A18', border: '1px solid #E0524A',
                color: '#FF8B85', fontSize: 12, padding: '4px 10px',
                borderRadius: 999, fontWeight: 600, cursor: 'pointer',
              }}
              title="Dogfood services with zero calls in 14 days"
            >
              🩺 {dogfood.summary.dead_zone} DEAD ZONE{dogfood.summary.dead_zone === 1 ? '' : 'S'}
            </span>
          )}
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

      {/* iter 322v — Deploy-Readiness Widget */}
      {deploy && (
        <section
          data-testid="deploy-readiness-widget"
          style={{
            background: COMP_BG,
            border: `1px solid ${deploy.overall === 'ready' ? '#3A4A2A' : '#4A2A1E'}`,
            borderRadius: 10,
            padding: 14,
            marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            color: deploy.overall === 'ready' ? '#4AD4A0' : '#F0A030',
            fontWeight: 600, fontSize: 14,
          }}>
            {deploy.overall === 'ready' ? '✅' : '⚠️'} Deploy Readiness:
            <span data-testid="deploy-readiness-overall">{deploy.overall.replace('_', ' ').toUpperCase()}</span>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12 }}>
            {[
              ['stripe', deploy.stripe],
              ['twilio', deploy.twilio],
              ['vapid', deploy.vapid],
              ['resend', deploy.resend],
              ['llm', deploy.llm],
            ].map(([k, v]) => {
              const ok = v !== 'missing';
              const live = v === 'live';
              const color = live ? '#4AD4A0' : ok ? '#D4AF7A' : '#E0524A';
              return (
                <div
                  key={k}
                  data-testid={`deploy-readiness-${k}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '4px 10px', borderRadius: 999,
                    background: '#14130F', border: `1px solid ${color}40`,
                  }}
                >
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
                  <span style={{ color: '#8B8475', fontWeight: 500 }}>{k}:</span>
                  <span style={{ color, fontWeight: 600 }}>{v}</span>
                </div>
              );
            })}
          </div>
          {deploy.missing?.length > 0 && (
            <div style={{ color: '#E0524A', fontSize: 11, marginLeft: 'auto' }}>
              missing: {deploy.missing.join(', ')}
            </div>
          )}
        </section>
      )}

      {/* Dogfood Health — 14d health snapshot for BIN AUR-FNDR-001 */}
      {dogfood?.summary && (
        <section
          data-testid="dogfood-health-tile"
          style={{
            background: COMP_BG,
            border: `1px solid ${dogfood.summary.has_dead_zones ? '#5A1A18' : '#3A4A2A'}`,
            borderRadius: 10,
            padding: 14,
            marginBottom: 16,
          }}
        >
          <div
            onClick={() => setDogfoodOpen(o => !o)}
            style={{
              display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
              cursor: 'pointer', userSelect: 'none',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              color: dogfood.summary.has_dead_zones ? '#FF8B85' : '#4AD4A0',
              fontWeight: 600, fontSize: 14,
            }}>
              {dogfood.summary.has_dead_zones ? '🩺' : '✅'} Dogfood Health
              <span style={{ color: '#8B8475', fontWeight: 500, fontSize: 12 }}>
                · {dogfood.bin} · last {dogfood.window_days}d
              </span>
            </div>
            <div style={{ display: 'flex', gap: 10, fontSize: 12, flexWrap: 'wrap' }}>
              <span
                data-testid="dogfood-active-pill"
                style={{
                  padding: '4px 10px', borderRadius: 999,
                  background: '#14130F', border: '1px solid #3A4A2A',
                  color: '#4AD4A0', fontWeight: 600,
                }}
              >
                {dogfood.summary.active} active
              </span>
              {dogfood.summary.dead_zone > 0 ? (
                <span
                  data-testid="dogfood-dead-zone-badge"
                  style={{
                    padding: '4px 10px', borderRadius: 999,
                    background: '#5A1A18', border: '1px solid #E0524A',
                    color: '#FF8B85', fontWeight: 600,
                  }}
                  title="Services with zero calls in the last 14 days"
                >
                  🚨 {dogfood.summary.dead_zone} dead zone{dogfood.summary.dead_zone === 1 ? '' : 's'}
                </span>
              ) : (
                <span
                  data-testid="dogfood-all-green-pill"
                  style={{
                    padding: '4px 10px', borderRadius: 999,
                    background: '#14130F', border: '1px solid #3A4A2A',
                    color: '#4AD4A0', fontWeight: 600,
                  }}
                >
                  no dead zones
                </span>
              )}
              <span style={{
                padding: '4px 10px', borderRadius: 999,
                background: '#14130F', border: '1px solid #2A2317',
                color: '#8B8475', fontWeight: 500,
              }}>
                {dogfood.summary.total_calls.toLocaleString()} calls
              </span>
            </div>
            <span
              data-testid="dogfood-toggle"
              style={{ marginLeft: 'auto', color: ACCENT, fontSize: 12 }}
            >
              {dogfoodOpen ? '▾ hide' : '▸ details'}
            </span>
          </div>

          {dogfoodOpen && (
            <div
              data-testid="dogfood-services-table"
              style={{
                marginTop: 12, paddingTop: 12, borderTop: `1px solid ${COMP_BORDER}`,
                maxHeight: 360, overflowY: 'auto',
              }}
            >
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1.8fr 0.7fr 0.7fr 1.3fr 0.7fr',
                fontSize: 11, color: '#8B8475', padding: '4px 0',
                borderBottom: `1px solid ${COMP_BORDER}`, fontWeight: 600,
                letterSpacing: '0.04em', textTransform: 'uppercase',
              }}>
                <div>Service</div>
                <div style={{ textAlign: 'right' }}>Calls</div>
                <div style={{ textAlign: 'right' }}>Success</div>
                <div>Last Used</div>
                <div style={{ textAlign: 'right' }}>Status</div>
              </div>
              {(dogfood.services || [])
                .slice()
                .sort((a, b) => {
                  // dead zones first, then by calls desc
                  if (a.status !== b.status) return a.status === 'dead_zone' ? -1 : 1;
                  return (b.total_calls || 0) - (a.total_calls || 0);
                })
                .map((s) => (
                  <div
                    key={s.service_id}
                    data-testid={`dogfood-row-${s.service_id}`}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1.8fr 0.7fr 0.7fr 1.3fr 0.7fr',
                      fontSize: 12, padding: '8px 0',
                      borderBottom: `1px solid ${COMP_BORDER}`,
                      color: '#E8E2D4',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{s.service_name}</div>
                      <div style={{ color: '#7A7468', fontSize: 10 }}>{s.service_id}</div>
                    </div>
                    <div style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {(s.total_calls || 0).toLocaleString()}
                    </div>
                    <div style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                      color: s.success_rate >= 0.95 ? '#4AD4A0'
                        : s.success_rate >= 0.7 ? '#F0A030'
                        : s.total_calls > 0 ? '#E0524A' : '#7A7468' }}>
                      {s.total_calls > 0 ? `${Math.round(s.success_rate * 100)}%` : '—'}
                    </div>
                    <div style={{ color: '#8B8475', fontSize: 11 }}>
                      {s.last_used ? new Date(s.last_used).toLocaleString() : '—'}
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 999, fontSize: 10,
                        fontWeight: 600, letterSpacing: '0.04em',
                        background: s.status === 'dead_zone' ? '#5A1A18' : '#1E3024',
                        border: `1px solid ${s.status === 'dead_zone' ? '#E0524A' : '#3A4A2A'}`,
                        color: s.status === 'dead_zone' ? '#FF8B85' : '#4AD4A0',
                      }}>
                        {s.status === 'dead_zone' ? 'DEAD' : 'ACTIVE'}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </section>
      )}

      {/* Admin Action Log tile (iter 322aq) — recent admin_audit_log entries */}
      {auditLog && (
        <section
          data-testid="admin-action-log-tile"
          style={{
            background: COMP_BG,
            border: `1px solid ${COMP_BORDER}`,
            borderRadius: 10,
            padding: 14,
            marginBottom: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ color: ACCENT, fontWeight: 600, fontSize: 14 }}>
              📋 Admin Action Log
              <span style={{ color: '#8B8475', fontWeight: 500, fontSize: 12, marginLeft: 8 }}>
                · last {auditLog.count} actions
              </span>
            </div>
          </div>
          {auditLog.count === 0 ? (
            <div style={{ color: '#7A7468', fontSize: 12 }}>No admin actions logged yet.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '160px 130px 110px 1fr 1.2fr', fontSize: 11, color: '#8B8475', padding: '4px 0', borderBottom: `1px solid ${COMP_BORDER}`, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              <div>When</div><div>Action</div><div>BIN</div><div>By</div><div>Details</div>
            </div>
          )}
          <div style={{ maxHeight: 260, overflowY: 'auto' }}>
            {(auditLog.entries || []).map((e, i) => {
              const colors = {
                force_unlock: '#4AD4A0', reset_password: '#F0A030',
                update_account: '#88C5FF', promote_now: '#FFE4A8',
                delete_customer: '#FF8B85', restore_customer: '#9FE3B5',
              };
              return (
                <div key={i} data-testid={`admin-action-log-row-${i}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 130px 110px 1fr 1.2fr',
                    fontSize: 11, padding: '7px 0',
                    borderBottom: `1px solid ${COMP_BORDER}`,
                    color: '#E8E2D4',
                  }}>
                  <div style={{ color: '#7A7468', fontFamily: 'monospace' }}>
                    {e.ts ? new Date(e.ts).toLocaleString() : '—'}
                  </div>
                  <div style={{ color: colors[e.action] || '#E8E2D4', fontWeight: 600 }}>
                    {e.action}
                  </div>
                  <div style={{ fontFamily: 'monospace', color: '#D4AF7A' }}>
                    {e.bin_id || '—'}
                  </div>
                  <div style={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.actor_email || '—'}
                  </div>
                  <div style={{ color: '#8B8475', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.details ? JSON.stringify(e.details).slice(0, 80) : ''}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
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
