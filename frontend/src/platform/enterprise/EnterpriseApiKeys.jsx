/**
 * /enterprise/admin/keys — API key management
 * Create / list / rotate / revoke per-org keys.
 */
import React, { useEffect, useState, useCallback } from "react";
import { KeyRound, Plus, RotateCcw, Trash2, Copy } from "lucide-react";
import EnterpriseAdminShell, {
  Field, PrimaryButton, Banner, ENT_API, adminHeaders,
} from "./EnterpriseAdminShell";

export default function EnterpriseApiKeys() {
  const [rows, setRows]   = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState({ name: "", scope: "read" });
  const [revealed, setRevealed] = useState(null);   // {key, key_preview, name}
  const [busy, setBusy]   = useState(false);
  const [err, setErr]     = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${ENT_API}/api/enterprise/keys`,
                             { headers: adminHeaders() });
      const j = await r.json();
      if (j.ok) setRows(j.rows || []);
    } catch (e) { /* swallow */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function create() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${ENT_API}/api/enterprise/keys`, {
        method: "POST", headers: adminHeaders(),
        body: JSON.stringify(newKey),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "create_failed");
      setRevealed({ key: j.key, key_preview: j.key_preview, name: newKey.name });
      setNewKey({ name: "", scope: "read" });
      setShowCreate(false);
      load();
    } catch (e) {
      setErr(String(e.message || e));
    } finally { setBusy(false); }
  }

  async function rotate(key_id) {
    if (!window.confirm("Rotate this key? The old key will stop working immediately.")) return;
    setBusy(true);
    try {
      const r = await fetch(`${ENT_API}/api/enterprise/keys/${key_id}/rotate`,
                             { method: "POST", headers: adminHeaders() });
      const j = await r.json();
      if (r.ok) setRevealed({ key: j.key, key_preview: j.key_preview, name: "(rotated)" });
      load();
    } finally { setBusy(false); }
  }

  async function revoke(key_id) {
    if (!window.confirm("Revoke this key permanently?")) return;
    setBusy(true);
    try {
      await fetch(`${ENT_API}/api/enterprise/keys/${key_id}`,
                   { method: "DELETE", headers: adminHeaders() });
      load();
    } finally { setBusy(false); }
  }

  return (
    <EnterpriseAdminShell
      eyebrow="ENTERPRISE / ADMIN"
      title="API key management"
      sub="Create, rotate, or revoke API keys for your team."
    >
      {revealed && (
        <Banner tone="warn" testid="apikey-revealed">
          <strong>New key created:</strong>{" "}
          <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {revealed.key}
          </span>{" "}
          <button onClick={() => navigator.clipboard?.writeText(revealed.key)}
                   style={{ marginLeft: 8, background: "transparent",
                             color: "inherit", border: "1px solid currentColor",
                             borderRadius: 4, padding: "2px 8px",
                             cursor: "pointer", fontSize: 11 }}>
            <Copy size={10} style={{ display: "inline" }} /> Copy
          </button>
          <button onClick={() => setRevealed(null)}
                   style={{ marginLeft: 8, background: "transparent",
                             color: "inherit", border: "none",
                             cursor: "pointer", fontSize: 11 }}>×</button>
          <p style={{ marginTop: 6, fontSize: 11 }}>
            This is the only time we'll show the full key — save it now.
          </p>
        </Banner>
      )}

      <div className="av2-card" data-testid="apikey-list">
        <div style={{ display: "flex", justifyContent: "space-between",
                       alignItems: "center", marginBottom: 14 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600,
                        color: "var(--dash-text)" }}>
            Active keys
          </h3>
          {!showCreate && (
            <PrimaryButton onClick={() => setShowCreate(true)} busy={false}
                            testid="apikey-create-btn">
              <Plus size={13} /> New key
            </PrimaryButton>
          )}
        </div>

        {showCreate && (
          <div data-testid="apikey-create-form"
                style={{ display: "grid", gap: 12, marginBottom: 16,
                          padding: 14,
                          background: "rgba(0,0,0,0.20)",
                          border: "1px solid rgba(255,107,0,0.10)",
                          borderRadius: 6 }}>
            <Field label="Key name" value={newKey.name}
                    placeholder="e.g. CI/CD deploy bot"
                    onChange={v => setNewKey({ ...newKey, name: v })}
                    testid="apikey-name" />
            <label>
              <span style={{ display: "block",
                              fontFamily: "'JetBrains Mono', monospace",
                              fontSize: 10, letterSpacing: "0.18em",
                              textTransform: "uppercase",
                              color: "var(--dash-text-muted)", marginBottom: 6 }}>
                Scope
              </span>
              <select data-testid="apikey-scope" value={newKey.scope}
                       onChange={e => setNewKey({ ...newKey, scope: e.target.value })}
                       className="dev-input" style={{ width: "100%" }}>
                <option value="read">Read only</option>
                <option value="write">Read + write</option>
                <option value="admin">Admin (everything)</option>
              </select>
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <PrimaryButton onClick={create} busy={busy}
                              testid="apikey-confirm-create">
                Create key
              </PrimaryButton>
              <button onClick={() => setShowCreate(false)}
                       style={{ padding: "10px 18px", background: "transparent",
                                 border: "1px solid var(--dash-border)",
                                 color: "var(--dash-text-muted)",
                                 borderRadius: 6, cursor: "pointer",
                                 fontSize: 13 }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {rows.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
            No keys yet. Create your first one above.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {rows.map((r) => (
              <li key={r.key_id}
                  data-testid="apikey-row"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1.4fr 0.8fr 1fr 100px 80px 80px",
                    gap: 10, padding: "10px 0",
                    borderTop: "1px solid var(--dash-divider)",
                    alignItems: "center",
                    fontSize: 13,
                  }}>
                <span style={{ color: "var(--dash-text)" }}>{r.name}</span>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11, color: "var(--dash-text-muted)",
                }}>{r.key_preview}</span>
                <span style={{ color: "var(--dash-text-muted)", fontSize: 11 }}>
                  {(r.created_at || "").slice(0, 10)}
                </span>
                <span style={{
                  textTransform: "uppercase",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10, letterSpacing: "0.18em",
                  color: r.scope === "admin" ? "var(--dash-orange)"
                       : r.scope === "write" ? "var(--dash-gold-bright)"
                       :                       "var(--dash-text-muted)",
                }}>{r.scope}</span>
                <button onClick={() => rotate(r.key_id)} disabled={busy}
                         data-testid={`apikey-rotate-${r.key_id}`}
                         style={{ background: "transparent",
                                   color: "var(--dash-amber)",
                                   border: "1px solid currentColor",
                                   borderRadius: 4, padding: "4px 8px",
                                   fontSize: 11, cursor: "pointer",
                                   display: "inline-flex", alignItems: "center",
                                   gap: 4 }}>
                  <RotateCcw size={10} /> Rotate
                </button>
                <button onClick={() => revoke(r.key_id)} disabled={busy}
                         data-testid={`apikey-revoke-${r.key_id}`}
                         style={{ background: "transparent",
                                   color: "var(--dash-red)",
                                   border: "1px solid currentColor",
                                   borderRadius: 4, padding: "4px 8px",
                                   fontSize: 11, cursor: "pointer",
                                   display: "inline-flex", alignItems: "center",
                                   gap: 4 }}>
                  <Trash2 size={10} /> Revoke
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {err && <Banner tone="err" testid="apikey-error">{err}</Banner>}
    </EnterpriseAdminShell>
  );
}
