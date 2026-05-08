/**
 * /admin/ssot — Single Source of Truth Console (iter 294)
 * Lives under SETTINGS (P4). Reads /api/admin/ssot/config, edits via /update,
 * shows last 50 changes from /log. Every save logged to ssot_change_log.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Save, RefreshCw, History, AlertTriangle, Check, Loader2 } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const GOLD = '#C9A227';

const SECTIONS = [
  {
    title: 'Pricing (CAD)', fields: [
      { path: 'pricing.starter.price_cad', label: 'Starter Price', kind: 'int', prefix: '$' },
      { path: 'pricing.growth.price_cad', label: 'Growth Price', kind: 'int', prefix: '$' },
      { path: 'pricing.enterprise.price_cad', label: 'Enterprise Price', kind: 'int', prefix: '$' },
    ],
  },
  {
    title: 'Trial', fields: [
      { path: 'trial.days', label: 'Trial Days', kind: 'int' },
      { path: 'trial.reminder_day', label: 'Reminder Day (day-N email)', kind: 'int' },
    ],
  },
  {
    title: 'Company', fields: [
      { path: 'company.name', label: 'Company Name' },
      { path: 'company.tagline', label: 'Hero Tagline' },
      { path: 'company.email_support', label: 'Support Email' },
      { path: 'company.email_sales', label: 'Sales Email' },
      { path: 'company.phone', label: 'Phone' },
      { path: 'company.address', label: 'Address' },
    ],
  },
];

const getPath = (obj, path) => path.split('.').reduce((a, p) => (a == null ? a : a[p]), obj);

export default function AdminSSOT() {
  const token = getPlatformToken();
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
  const [config, setConfig] = useState(null);
  const [overrides, setOverrides] = useState({});
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState({});
  const [savedAt, setSavedAt] = useState({});
  const [errors, setErrors] = useState({});
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setBusy(true);
    try {
      const [cRes, lRes] = await Promise.all([
        fetch(`${API}/api/admin/ssot/config`, { headers }),
        fetch(`${API}/api/admin/ssot/log?limit=50`, { headers }),
      ]);
      const c = cRes.ok ? await cRes.json() : null;
      const l = lRes.ok ? await lRes.json() : { changes: [] };
      if (c) { setConfig(c.config); setOverrides(c.overrides || {}); }
      setLog(l.changes || []);
      setEdits({});
    } finally { setBusy(false); }
  }, [headers]);

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, []);

  const onSave = async (path) => {
    if (!(path in edits)) return;
    const val = edits[path];
    setSaving(s => ({ ...s, [path]: true }));
    setErrors(e => ({ ...e, [path]: null }));
    try {
      const r = await fetch(`${API}/api/admin/ssot/update`, {
        method: 'PUT', headers,
        body: JSON.stringify({ path, value: val }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Update failed');
      setSavedAt(s => ({ ...s, [path]: Date.now() }));
      await reload();
    } catch (e) {
      setErrors(er => ({ ...er, [path]: String(e.message || e) }));
    }
    setSaving(s => ({ ...s, [path]: false }));
  };

  const onResetAll = async () => {
    if (!window.confirm('Clear ALL overrides — config returns to defaults from aurem_config.py?')) return;
    setBusy(true);
    await fetch(`${API}/api/admin/ssot/reset`, { method: 'POST', headers });
    await reload();
  };

  if (!config) {
    return (
      <div data-testid="ssot-loading"
        style={{ padding: 40, color: '#7A7468', display: 'flex', gap: 10, alignItems: 'center' }}>
        <Loader2 className="animate-spin" style={{ width: 16, height: 16 }} />
        <span>Loading SSOT config…</span>
      </div>
    );
  }

  return (
    <div data-testid="admin-ssot-page"
      style={{ padding: '32px 40px', color: '#F2EDE4', maxWidth: 1100, margin: '0 auto',
               fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 32 }}>
        <div>
          <div style={{ fontSize: 10, color: GOLD, letterSpacing: 4, fontWeight: 700,
                        fontFamily: "'DM Mono',monospace", marginBottom: 6 }}>
            P4 · REVENUE · SSOT
          </div>
          <h1 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 38,
                       fontWeight: 300, letterSpacing: -0.5, margin: 0 }}>
            Single Source of Truth
          </h1>
          <p style={{ color: '#8A8279', fontSize: 13, marginTop: 6 }}>
            Edit once. Updates everywhere. Every change is logged.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button data-testid="ssot-reload" onClick={reload} disabled={busy}
            style={btnSecondary}>
            <RefreshCw style={{ width: 12, height: 12 }} /> Reload
          </button>
          <button data-testid="ssot-reset-all" onClick={onResetAll} disabled={busy}
            style={{ ...btnSecondary, color: '#EF4444', borderColor: 'rgba(239,68,68,0.4)' }}>
            <AlertTriangle style={{ width: 12, height: 12 }} /> Reset to defaults
          </button>
        </div>
      </div>

      {/* Form */}
      {SECTIONS.map((sec, si) => (
        <section key={si} data-testid={`ssot-section-${si}`}
          style={{ marginBottom: 28, border: '1px solid rgba(201,162,39,0.18)',
                   borderRadius: 10, background: 'rgba(255,255,255,0.02)' }}>
          <div style={{ padding: '14px 22px', borderBottom: '1px solid rgba(201,162,39,0.12)',
                        fontFamily: "'DM Mono',monospace", fontSize: 10,
                        letterSpacing: 3, color: GOLD, fontWeight: 700 }}>
            {sec.title.toUpperCase()}
          </div>
          <div style={{ padding: '18px 22px', display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill,minmax(320px,1fr))', gap: 14 }}>
            {sec.fields.map((f) => {
              const cur = getPath(config, f.path);
              const overridden = f.path in overrides ||
                                 f.path.endsWith('.price_cad') &&
                                 (f.path.replace('.price_cad', '.price_display')) in overrides;
              const value = (f.path in edits) ? edits[f.path] : cur;
              const dirty = (f.path in edits) && edits[f.path] !== cur;
              return (
                <label key={f.path} data-testid={`ssot-field-${f.path}`}
                  style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <span style={{ fontSize: 11, color: '#8A8279', display: 'flex', gap: 6, alignItems: 'center' }}>
                    {f.label}
                    {overridden && (
                      <span style={{ fontSize: 8, padding: '1px 6px', borderRadius: 3,
                                     background: 'rgba(201,162,39,0.2)', color: GOLD }}>OVERRIDDEN</span>
                    )}
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {f.prefix && (
                      <span style={{ padding: '10px 8px', background: '#000',
                                     border: '1px solid rgba(201,162,39,0.2)',
                                     borderRight: 'none', borderRadius: '6px 0 0 6px',
                                     color: GOLD, fontSize: 13 }}>{f.prefix}</span>
                    )}
                    <input type={f.kind === 'int' ? 'number' : 'text'}
                      value={value ?? ''}
                      onChange={(e) => setEdits(ed => ({ ...ed, [f.path]:
                        f.kind === 'int' ? Number(e.target.value) : e.target.value }))}
                      data-testid={`ssot-input-${f.path}`}
                      style={{
                        flex: 1, padding: '10px 12px', fontSize: 13,
                        background: '#000', color: '#F2EDE4',
                        border: '1px solid ' + (dirty ? GOLD : 'rgba(201,162,39,0.2)'),
                        borderRadius: f.prefix ? '0 6px 6px 0' : 6,
                        outline: 'none',
                        fontFamily: f.kind === 'int' ? "'DM Mono',monospace" : 'inherit',
                      }} />
                    <button onClick={() => onSave(f.path)} disabled={!dirty || saving[f.path]}
                      data-testid={`ssot-save-${f.path}`}
                      style={{
                        padding: '0 14px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                        background: dirty ? GOLD : 'rgba(201,162,39,0.15)',
                        color: dirty ? '#0A0A0A' : '#7A7468',
                        border: 'none', cursor: dirty ? 'pointer' : 'not-allowed',
                        display: 'flex', alignItems: 'center', gap: 4,
                      }}>
                      {saving[f.path]
                        ? <Loader2 className="animate-spin" style={{ width: 12, height: 12 }} />
                        : (savedAt[f.path] && Date.now() - savedAt[f.path] < 3000)
                          ? <><Check style={{ width: 12, height: 12 }} /> Saved</>
                          : <><Save style={{ width: 12, height: 12 }} /> Save</>}
                    </button>
                  </div>
                  {errors[f.path] && (
                    <span style={{ fontSize: 10, color: '#EF4444' }}>{errors[f.path]}</span>
                  )}
                </label>
              );
            })}
          </div>
        </section>
      ))}

      {/* Change history */}
      <section data-testid="ssot-changelog"
        style={{ border: '1px solid rgba(201,162,39,0.18)', borderRadius: 10,
                 background: 'rgba(255,255,255,0.02)' }}>
        <div style={{ padding: '14px 22px', borderBottom: '1px solid rgba(201,162,39,0.12)',
                      display: 'flex', alignItems: 'center', gap: 8 }}>
          <History style={{ width: 14, height: 14, color: GOLD }} />
          <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 10,
                         letterSpacing: 3, color: GOLD, fontWeight: 700 }}>
            CHANGE HISTORY · LAST {log.length}
          </span>
        </div>
        <div style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                {['When', 'Field', 'From', 'To', 'By'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left',
                                       color: '#8A8279', fontWeight: 500, fontSize: 10,
                                       letterSpacing: 1.5, textTransform: 'uppercase',
                                       fontFamily: "'DM Mono',monospace" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {log.length === 0 && (
                <tr><td colSpan={5} style={{ padding: 28, textAlign: 'center', color: '#7A7468' }}>
                  No changes yet. Edit a field above and save to see audit entries.
                </td></tr>
              )}
              {log.map((c, i) => (
                <tr key={i} data-testid={`ssot-log-row-${i}`}
                  style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={tdMono}>{formatTs(c.timestamp)}</td>
                  <td style={tdMono}>{c.field}</td>
                  <td style={{ ...tdMono, color: '#EF4444' }}>{String(c.old_value)}</td>
                  <td style={{ ...tdMono, color: '#22C55E' }}>{String(c.new_value)}</td>
                  <td style={tdMono}>{c.changed_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const btnSecondary = {
  padding: '8px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
  background: 'transparent', color: '#8A8279',
  border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', gap: 6,
  fontFamily: 'inherit',
};

const tdMono = { padding: '10px 16px', fontFamily: "'DM Mono', monospace", fontSize: 11, color: '#C5BDB1' };

const formatTs = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso.slice(0, 16); }
};
