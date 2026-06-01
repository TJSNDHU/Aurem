/**
 * AdminApiKeysPage.jsx — iter D-59 Part B
 *
 * Admin page to issue, view, revoke, and inspect usage of the
 * Public AUREM API keys consumed by `/api/v1/public/*` endpoints.
 *
 * Secrets are returned ONCE on issue — UI shows a single-time reveal
 * card with copy button + "I saved it" acknowledgement. Server only
 * keeps the sha256 hash.
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  KeyRound, Plus, Copy, CheckCircle2, RefreshCw, ShieldOff,
  Activity, AlertTriangle, BookOpen,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const ALL_SCOPES = ["ora_chat", "cto_chat", "leads_read"];

function adminHeaders() {
  let token = "";
  try {
    token = sessionStorage.getItem("platform_token") ||
            localStorage.getItem("platform_token") ||
            localStorage.getItem("aurem_admin_token") ||
            sessionStorage.getItem("aurem_admin_token") ||
            localStorage.getItem("token") ||
            localStorage.getItem("aurem.admin_jwt") ||
            localStorage.getItem("aurem.dev_jwt") ||
            "";
  } catch { /* ignore */ }
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const C = {
  ink:   "#F0EDE8",
  dim:   "#a1958a",
  gold:  "#E8C86A",
  amber: "#FF8C35",
  red:   "#FF6060",
  green: "#4ade80",
  panel: "rgba(255,255,255,0.04)",
  border:"rgba(255,255,255,0.10)",
};

const mono = "'JetBrains Mono', monospace";


function CopyButton({ value, testId }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value || "");
      setCopied(true); setTimeout(() => setCopied(false), 1400);
    } catch { /* ignore */ }
  }
  return (
    <button onClick={copy} data-testid={testId}
            style={{ background: "transparent",
                     border: `1px solid ${C.border}`,
                     color: copied ? C.green : C.dim,
                     padding: "4px 9px", borderRadius: 4,
                     fontSize: 11, cursor: "pointer",
                     display: "inline-flex", alignItems: "center", gap: 4 }}>
      {copied ? <CheckCircle2 size={11} /> : <Copy size={11} />}
      {copied ? "copied" : "copy"}
    </button>
  );
}


function IssuedKeyCard({ secret, info, onAcknowledge }) {
  return (
    <div data-testid="issued-key-reveal"
         style={{ marginBottom: 18, padding: 16,
                  background: "rgba(255,200,87,0.08)",
                  border: "1px solid rgba(255,200,87,0.45)",
                  borderRadius: 6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                    marginBottom: 10 }}>
        <AlertTriangle size={14} style={{ color: C.gold }} />
        <strong style={{ color: C.gold, fontSize: 13 }}>
          One-time reveal — copy now, we never store the secret.
        </strong>
      </div>
      <div style={{ padding: 10, background: "rgba(0,0,0,0.30)",
                    border: `1px solid ${C.border}`, borderRadius: 4,
                    fontFamily: mono, fontSize: 12, color: C.ink,
                    wordBreak: "break-all", marginBottom: 10 }}>
        <span data-testid="issued-key-secret">{secret}</span>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <CopyButton value={secret} testId="copy-issued-secret" />
        <span style={{ color: C.dim, fontSize: 11, fontFamily: mono }}>
          {info?.name} · {info?.scopes?.join(", ")} · {info?.rate_limit_per_day}/day
        </span>
        <button onClick={onAcknowledge}
                data-testid="acknowledge-issued-key"
                style={{ marginLeft: "auto",
                         background: "rgba(74,222,128,0.15)",
                         border: `1px solid ${C.green}`,
                         color: C.green, padding: "5px 12px",
                         borderRadius: 4, fontSize: 11, cursor: "pointer" }}>
          I saved it
        </button>
      </div>
    </div>
  );
}


function IssueForm({ onIssue, busy }) {
  const [name, setName] = useState("Founder primary");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [scopes, setScopes] = useState(["ora_chat", "cto_chat", "leads_read"]);
  const [perDay, setPerDay] = useState(5000);

  function toggleScope(s) {
    setScopes(prev => prev.includes(s)
      ? prev.filter(x => x !== s) : [...prev, s]);
  }

  return (
    <div style={{ padding: 14, background: C.panel,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  marginBottom: 18 }}>
      <h2 style={{ fontSize: 13, color: C.gold, margin: "0 0 10px",
                   fontFamily: "'Cinzel', serif", letterSpacing: "0.05em" }}>
        Issue new API key
      </h2>
      <div style={{ display: "grid",
                    gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ fontSize: 11, color: C.dim, fontFamily: mono }}>
          name
          <input value={name} onChange={e => setName(e.target.value)}
                 data-testid="api-key-name"
                 style={{ width: "100%", marginTop: 4,
                          padding: "6px 8px",
                          background: "rgba(0,0,0,0.30)",
                          border: `1px solid ${C.border}`,
                          color: C.ink, borderRadius: 4,
                          fontFamily: mono, fontSize: 12 }} />
        </label>
        <label style={{ fontSize: 11, color: C.dim, fontFamily: mono }}>
          owner email
          <input value={ownerEmail}
                 onChange={e => setOwnerEmail(e.target.value)}
                 placeholder="founder@aurem.live"
                 data-testid="api-key-owner-email"
                 style={{ width: "100%", marginTop: 4,
                          padding: "6px 8px",
                          background: "rgba(0,0,0,0.30)",
                          border: `1px solid ${C.border}`,
                          color: C.ink, borderRadius: 4,
                          fontFamily: mono, fontSize: 12 }} />
        </label>
        <label style={{ fontSize: 11, color: C.dim, fontFamily: mono,
                        gridColumn: "1/3" }}>
          scopes
          <div style={{ marginTop: 6, display: "flex", gap: 8,
                        flexWrap: "wrap" }}>
            {ALL_SCOPES.map(s => (
              <label key={s} style={{ display: "inline-flex",
                                       alignItems: "center", gap: 5,
                                       padding: "4px 10px",
                                       background: scopes.includes(s)
                                         ? "rgba(255,140,53,0.15)"
                                         : "rgba(255,255,255,0.02)",
                                       border: `1px solid ${scopes.includes(s)
                                         ? C.amber : C.border}`,
                                       borderRadius: 4, cursor: "pointer",
                                       color: scopes.includes(s)
                                         ? C.amber : C.dim,
                                       fontSize: 11 }}>
                <input type="checkbox" checked={scopes.includes(s)}
                       onChange={() => toggleScope(s)}
                       data-testid={`scope-${s}`}
                       style={{ accentColor: C.amber }} />
                {s}
              </label>
            ))}
          </div>
        </label>
        <label style={{ fontSize: 11, color: C.dim, fontFamily: mono }}>
          daily limit
          <input type="number" min={1} max={1000000} value={perDay}
                 onChange={e => setPerDay(Number(e.target.value))}
                 data-testid="api-key-per-day"
                 style={{ width: "100%", marginTop: 4,
                          padding: "6px 8px",
                          background: "rgba(0,0,0,0.30)",
                          border: `1px solid ${C.border}`,
                          color: C.ink, borderRadius: 4,
                          fontFamily: mono, fontSize: 12 }} />
        </label>
      </div>
      <button onClick={() => onIssue({ name, ownerEmail, scopes, perDay })}
              disabled={busy || !ownerEmail || scopes.length === 0}
              data-testid="api-key-issue-btn"
              style={{ marginTop: 12,
                       background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                       border: "none", color: "#fff",
                       padding: "8px 16px", borderRadius: 4,
                       fontSize: 12, fontWeight: 500,
                       cursor: busy ? "wait" : "pointer",
                       display: "inline-flex", alignItems: "center", gap: 6,
                       opacity: (busy || !ownerEmail || scopes.length === 0) ? 0.6 : 1 }}>
        <Plus size={13} /> Issue key
      </button>
    </div>
  );
}


function KeyRow({ row, onRevoke, onShowUsage, busy }) {
  const revoked = !!row.revoked;
  return (
    <div data-testid={`api-key-row-${row.key_id}`}
         style={{ padding: 12, marginBottom: 8,
                  background: revoked
                    ? "rgba(255,96,96,0.04)" : "rgba(255,255,255,0.02)",
                  border: `1px solid ${revoked
                    ? "rgba(255,96,96,0.25)" : C.border}`,
                  borderRadius: 5,
                  opacity: revoked ? 0.55 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <KeyRound size={14}
                  style={{ color: revoked ? C.red : C.amber }} />
        <strong style={{ color: C.ink, fontSize: 13,
                         fontFamily: mono }}>
          {row.name || "(unnamed)"}
        </strong>
        <span style={{ color: C.dim, fontSize: 11, fontFamily: mono }}>
          {row.key_prefix}…
        </span>
        <span style={{ color: C.dim, fontSize: 11, marginLeft: 6 }}>
          {row.owner_email}
        </span>
        <span style={{ color: C.dim, fontSize: 11, fontFamily: mono,
                       marginLeft: "auto" }}>
          {row.usage_today || 0} / {row.rate_limit_per_day} today
        </span>
        <button onClick={() => onShowUsage(row.key_id)}
                disabled={busy}
                data-testid={`api-key-usage-${row.key_id}`}
                style={{ background: "transparent",
                         border: `1px solid ${C.border}`,
                         color: C.dim, padding: "4px 10px",
                         borderRadius: 4, fontSize: 11, cursor: "pointer",
                         display: "inline-flex", alignItems: "center", gap: 4 }}>
          <Activity size={11} /> usage
        </button>
        {!revoked && (
          <button onClick={() => onRevoke(row.key_id)}
                  disabled={busy}
                  data-testid={`api-key-revoke-${row.key_id}`}
                  style={{ background: "rgba(255,96,96,0.10)",
                           border: `1px solid ${C.red}`,
                           color: C.red, padding: "4px 10px",
                           borderRadius: 4, fontSize: 11, cursor: "pointer",
                           display: "inline-flex", alignItems: "center", gap: 4 }}>
            <ShieldOff size={11} /> revoke
          </button>
        )}
      </div>
      <div style={{ marginTop: 6, fontSize: 11, color: C.dim,
                    fontFamily: mono }}>
        scopes: {(row.scopes || []).join(", ")} ·
        created {row.created_at?.slice(0, 19)} ·
        {revoked ? ` REVOKED @ ${(row.revoked_at || "")?.slice(0, 19)}`
                  : ` last used ${row.last_used_at?.slice(0, 19) || "—"}`}
      </div>
    </div>
  );
}


export default function AdminApiKeysPage() {
  const [keys, setKeys]         = useState([]);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [busy, setBusy]         = useState(false);
  const [reveal, setReveal]     = useState(null);     // {secret, key}
  const [usageRow, setUsageRow] = useState(null);     // {key_id, data}

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const r = await fetch(`${API}/api/admin/public-api-keys`,
                              { headers: adminHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "load_failed");
      setKeys(j.items || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function onIssue({ name, ownerEmail, scopes, perDay }) {
    setBusy(true); setError("");
    try {
      const r = await fetch(`${API}/api/admin/public-api-keys/issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...adminHeaders() },
        body: JSON.stringify({
          name, owner_email: ownerEmail, scopes,
          rate_per_day: perDay, rate_per_min: 30,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "issue_failed");
      setReveal({ secret: j.secret, key: j.key });
      load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(keyId) {
    if (!window.confirm(`Revoke key ${keyId}? This is irreversible.`)) return;
    setBusy(true);
    try {
      await fetch(`${API}/api/admin/public-api-keys/${keyId}/revoke`,
                    { method: "POST", headers: adminHeaders() });
      load();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function onShowUsage(keyId) {
    try {
      const r = await fetch(`${API}/api/admin/public-api-keys/${keyId}/usage?days=7`,
                              { headers: adminHeaders() });
      const j = await r.json();
      setUsageRow({ key_id: keyId, data: j });
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  return (
    <div data-testid="admin-api-keys-page"
         style={{ padding: "24px 28px", maxWidth: 1100, margin: "0 auto",
                  color: C.ink }}>

      <div style={{ display: "flex", alignItems: "center", gap: 12,
                    marginBottom: 18 }}>
        <KeyRound size={18} style={{ color: C.amber }} />
        <h1 style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                     color: C.gold, margin: 0 }}>
          Public API Keys
        </h1>
        <span style={{ marginLeft: "auto", color: C.dim, fontSize: 11,
                       fontFamily: mono }}>
          {keys.length} key{keys.length === 1 ? "" : "s"}
        </span>
        <button onClick={load} disabled={loading}
                data-testid="api-keys-refresh"
                style={{ background: C.panel, border: `1px solid ${C.border}`,
                         color: C.dim, padding: "6px 12px",
                         borderRadius: 4, fontSize: 11,
                         cursor: loading ? "wait" : "pointer",
                         display: "inline-flex", alignItems: "center", gap: 5 }}>
          <RefreshCw size={12}
                     className={loading ? "aurem-anim-spin" : ""} />
          Refresh
        </button>
        <a href="/docs/aurem-public-api" target="_blank" rel="noreferrer"
           data-testid="api-keys-docs-link"
           style={{ background: "transparent",
                    border: `1px solid ${C.border}`,
                    color: C.gold, padding: "6px 12px",
                    borderRadius: 4, fontSize: 11, cursor: "pointer",
                    textDecoration: "none",
                    display: "inline-flex", alignItems: "center", gap: 5 }}>
          <BookOpen size={12} /> Docs
        </a>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 14, color: C.red,
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12 }}>
          {error}
        </div>
      )}

      {reveal && (
        <IssuedKeyCard secret={reveal.secret} info={reveal.key}
                       onAcknowledge={() => setReveal(null)} />
      )}

      <IssueForm onIssue={onIssue} busy={busy} />

      <div>
        <h2 style={{ fontSize: 13, color: C.gold, margin: "16px 0 8px",
                     fontFamily: "'Cinzel', serif",
                     letterSpacing: "0.05em" }}>
          Active keys
        </h2>
        {keys.length === 0 && !loading && (
          <div style={{ padding: 14, color: C.dim, fontSize: 12,
                        fontFamily: mono,
                        border: `1px dashed ${C.border}`,
                        borderRadius: 5 }}>
            No keys issued yet — mint the first one above.
          </div>
        )}
        {keys.map(k => (
          <KeyRow key={k.key_id} row={k}
                  onRevoke={onRevoke} onShowUsage={onShowUsage}
                  busy={busy} />
        ))}
      </div>

      {usageRow && (
        <div data-testid="api-key-usage-panel"
             style={{ marginTop: 18, padding: 12, background: C.panel,
                      border: `1px solid ${C.border}`, borderRadius: 5 }}>
          <div style={{ display: "flex", alignItems: "center",
                        marginBottom: 6 }}>
            <strong style={{ color: C.gold, fontSize: 12 }}>
              Usage · last 7 days · {usageRow.key_id}
            </strong>
            <button onClick={() => setUsageRow(null)}
                    style={{ marginLeft: "auto", background: "transparent",
                             border: "none", color: C.dim,
                             fontSize: 11, cursor: "pointer" }}>
              close
            </button>
          </div>
          <div style={{ fontSize: 11, fontFamily: mono, color: C.ink }}>
            total calls: <strong>{usageRow.data?.total || 0}</strong>
          </div>
          <div style={{ marginTop: 6, fontSize: 11, fontFamily: mono,
                        color: C.dim }}>
            {Object.entries(usageRow.data?.by_endpoint || {}).length === 0
              ? "no calls yet"
              : Object.entries(usageRow.data?.by_endpoint || {})
                  .map(([ep, n]) => (
                    <div key={ep}>{ep} → {n}</div>
                  ))}
          </div>
        </div>
      )}
    </div>
  );
}
