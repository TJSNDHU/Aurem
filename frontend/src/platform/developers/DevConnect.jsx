/**
 * /developers/connect — Tool connection center (Auth-gated)
 * LuxeDashboardV2 av2-card style.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Github, Database, Code2, KeyRound } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import { PageHeader, SectionTitle } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevConnect() {
  const navigate = useNavigate();
  const [byok, setByok]   = useState({ anthropic: "", deepseek: "", gemini: "" });
  const [mongo, setMongo] = useState("");
  const [busy, setBusy]   = useState(false);
  const [msg, setMsg]     = useState(null);
  const [err, setErr]     = useState(null);

  async function save() {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await fetch(`${API}/api/developers/byok`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify(byok),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "byok failed");
      setMsg(`Saved. Active providers: ${j.providers.join(", ")}`);
    } catch (e) {
      setErr(String(e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="CONNECT" title="Wire up ORA's tools."
                  sub="One BYOK key is required so we can talk to a real LLM. The rest are optional but unlock more autonomy." />

      <div className="av2-grid-2">
        {/* GitHub */}
        <div className="av2-card">
          <SectionTitle title="GitHub" />
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 16 }}>
            Read-only OAuth by default. AUREM CTO writes only when you approve a PR.
          </p>
          <a data-testid="connect-github-btn"
              href={`${API}/api/auth/github/connect`}
              style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "10px 18px",
                background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                color: "#fff", borderRadius: 6,
                fontSize: 13, fontWeight: 500, textDecoration: "none",
              }}>
            <Github size={14} /> Connect GitHub
          </a>
        </div>

        {/* MongoDB */}
        <div className="av2-card">
          <SectionTitle title="MongoDB (optional)" />
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 16 }}>
            Connection string is encrypted with AES-128 GCM before storage.
          </p>
          <input data-testid="connect-mongo-input" value={mongo}
                  onChange={e => setMongo(e.target.value)}
                  placeholder="mongodb+srv://user:pass@host/db"
                  className="dev-input"
                  style={{ width: "100%", fontSize: 12 }} />
        </div>

        {/* VS Code */}
        <div className="av2-card">
          <SectionTitle title="VS Code extension" />
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 16 }}>
            Run AUREM CTO inside your editor. Install the AUREM extension.
          </p>
          <button data-testid="connect-vscode-btn"
                   onClick={() => window.open(
                     "https://marketplace.visualstudio.com/items?itemName=aurem.ora-cto",
                     "_blank")}
                   style={{
                     display: "inline-flex", alignItems: "center", gap: 8,
                     padding: "10px 18px",
                     background: "transparent",
                     border: "1px solid rgba(201,168,76,0.30)",
                     color: "#C9A84C", borderRadius: 6,
                     fontSize: 13, fontWeight: 500, cursor: "pointer",
                   }}>
            <Code2 size={14} /> Install extension
          </button>
        </div>

        {/* BYOK */}
        <div className="av2-card">
          <SectionTitle title="BYOK keys" />
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 12 }}>
            At least one required. Encrypted at rest.
          </p>
          {["anthropic", "deepseek", "gemini"].map(p => (
            <label key={p} style={{ display: "block", marginBottom: 10 }}>
              <span style={{
                display: "block",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10, letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--dash-text-muted)", marginBottom: 4,
              }}>{p}</span>
              <input data-testid={`byok-${p}-input`} type="password"
                      value={byok[p]} placeholder="sk-…"
                      onChange={e => setByok({ ...byok, [p]: e.target.value })}
                      className="dev-input"
                      style={{ width: "100%", fontSize: 12 }} />
            </label>
          ))}
        </div>
      </div>

      {msg && (
        <div data-testid="connect-success-msg" className="av2-card"
             style={{ borderColor: "rgba(80,200,120,0.30)",
                       background: "rgba(80,200,120,0.05)",
                       color: "var(--dash-green)", fontSize: 13 }}>
          {msg}
        </div>
      )}
      {err && (
        <div data-testid="connect-error-msg" className="av2-card"
             style={{ borderColor: "rgba(255,96,96,0.30)",
                       background: "rgba(255,96,96,0.05)",
                       color: "var(--dash-red)", fontSize: 13 }}>
          {err}
        </div>
      )}

      <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
        <button data-testid="connect-save-btn"
                 onClick={save} disabled={busy}
                 style={{
                   padding: "10px 24px",
                   background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                   color: "#fff", border: "none", borderRadius: 6,
                   fontSize: 13, fontWeight: 500, cursor: "pointer",
                   opacity: busy ? 0.5 : 1,
                 }}>
          {busy ? "Saving…" : "Save BYOK keys"}
        </button>
        <button onClick={() => navigate("/developers/dashboard")}
                 data-testid="connect-skip-btn"
                 style={{
                   padding: "10px 24px",
                   background: "transparent",
                   border: "1px solid var(--dash-border)",
                   color: "var(--dash-text-muted)", borderRadius: 6,
                   fontSize: 13, cursor: "pointer",
                 }}>
          Skip for now
        </button>
      </div>
    </DeveloperShell>
  );
}
