/**
 * /developers/settings — Account settings (Auth-gated)
 */
import React, { useEffect, useState } from "react";
import { RotateCcw, ShieldOff, Activity, AlertTriangle } from "lucide-react";
import DeveloperShell, { devAuthHeaders, setDevJwt } from "./DeveloperShell";
import { PageHeader, SectionTitle } from "./DevDashboard";
import ConsentToggleCard from "./ConsentToggleCard";
import PlatformCredentialsBlock from "./PlatformCredentialsBlock"; // iter D-43

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevSettings() {
  const [sessions, setSessions] = useState({ active: [], limit: 2 });
  const [byok, setByok] = useState({ anthropic: "", deepseek: "", gemini: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg]   = useState(null);
  const [err, setErr]   = useState(null);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");

  async function loadSessions() {
    const r = await fetch(`${API}/api/developers/sessions`,
                           { headers: devAuthHeaders() });
    if (r.ok) setSessions(await r.json());
  }
  useEffect(() => { loadSessions(); }, []);

  async function rotateByok() {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await fetch(`${API}/api/developers/byok`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify(byok),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "rotation failed");
      setMsg(`Rotated. Active providers: ${j.providers.join(", ")}`);
      setByok({ anthropic: "", deepseek: "", gemini: "" });
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function closeSession(sid) {
    await fetch(`${API}/api/developers/session/release`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...devAuthHeaders() },
      body: JSON.stringify({ session_id: sid }),
    });
    loadSessions();
  }

  async function deleteAccount() {
    if (deleteConfirm !== "DELETE") return;
    setBusy(true);
    try {
      await fetch(`${API}/api/developers/delete-request`, {
        method: "POST", headers: devAuthHeaders(),
      });
      setDevJwt("");
      window.location.href = "/developers";
    } finally { setBusy(false); }
  }

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="SETTINGS" title="Account & security"
                  sub="Rotate keys, close sessions, toggle data sharing, or delete your account." />

      {/* iter D-43 — founder-controlled platform-wide secrets (AES-256
          encrypted, applied live to os.environ). Admin-gated by the
          backend; non-admin devs will just see an empty card. */}
      <PlatformCredentialsBlock />

      {/* iter D-44 — Rotate BYOK keys moved to /developers/connect
          (lives next to the BYOK paste form so all key-management is
          on one page). */}

      <div data-testid="settings-sessions-list" className="av2-card">
        <SectionTitle title="Active sessions" />
        <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                     marginBottom: 12 }}>
          <Activity size={12} style={{ display: "inline", marginRight: 6 }} />
          Max {sessions.limit ?? 2} concurrent. Close any to free a slot.
        </p>
        {(sessions.active || []).length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
            No active sessions.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {sessions.active.map((s, i) => (
              <li key={i}
                   style={{ display: "flex", alignItems: "center",
                             justifyContent: "space-between",
                             fontFamily: "'JetBrains Mono', monospace",
                             fontSize: 12, padding: "10px 0",
                             borderTop: i > 0
                               ? "1px solid var(--dash-divider)" : "none",
                             color: "var(--dash-text)" }}>
                <span>{s.session_id}</span>
                <span style={{ color: "var(--dash-text-muted)" }}>
                  {new Date(s.heartbeat).toLocaleTimeString()}
                </span>
                <button data-testid={`settings-close-session-${s.session_id}`}
                         onClick={() => closeSession(s.session_id)}
                         style={{
                           background: "transparent", border: "none",
                           color: "var(--dash-red)",
                           fontSize: 12, cursor: "pointer",
                         }}>close</button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Consent toggle reuses the existing card */}
      <ConsentToggleCard />

      {/* Danger zone */}
      <div className="av2-card"
            style={{ borderColor: "rgba(255,96,96,0.30)",
                      background: "rgba(255,96,96,0.04)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8,
                       marginBottom: 12 }}>
          <AlertTriangle size={16} style={{ color: "var(--dash-red)" }} />
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11, letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--dash-red)",
          }}>Danger zone</span>
        </div>
        <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                     marginBottom: 14 }}>
          30-day soft delete. Recoverable inside that window; hard-purged
          afterwards.
        </p>
        {!showDelete ? (
          <button data-testid="settings-delete-account-btn"
                   onClick={() => setShowDelete(true)}
                   style={{
                     padding: "9px 18px",
                     background: "transparent",
                     border: "1px solid rgba(255,96,96,0.40)",
                     color: "var(--dash-red)", borderRadius: 6,
                     fontSize: 13, cursor: "pointer",
                     display: "inline-flex", alignItems: "center", gap: 8,
                   }}>
            <ShieldOff size={13} /> Delete account
          </button>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>
              Type <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: "var(--dash-red)",
              }}>DELETE</span> to confirm.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <input data-testid="settings-delete-confirm-input"
                      value={deleteConfirm}
                      onChange={e => setDeleteConfirm(e.target.value)}
                      className="dev-input"
                      style={{ maxWidth: 200, fontSize: 12 }} />
              <button data-testid="settings-delete-confirm-btn"
                       onClick={deleteAccount}
                       disabled={deleteConfirm !== "DELETE" || busy}
                       style={{
                         padding: "9px 18px",
                         background: "var(--dash-red)", color: "#fff",
                         border: "none", borderRadius: 6, fontSize: 13,
                         cursor: "pointer",
                         opacity: (deleteConfirm !== "DELETE" || busy)
                           ? 0.4 : 1,
                       }}>
                Confirm delete
              </button>
            </div>
          </div>
        )}
      </div>
    </DeveloperShell>
  );
}
