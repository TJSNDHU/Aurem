/**
 * DeveloperSettings.jsx — iter D-43
 *
 * Founder-controlled credentials page. Lets the founder paste API keys
 * (GITHUB_CLIENT_ID, ANTHROPIC_API_KEY, etc.) directly into AUREM. The
 * backend AES-256 (Fernet) encrypts at rest AND applies the plaintext
 * live to os.environ so every existing code path picks it up without a
 * restart.
 *
 * Backend: /api/developers/settings/secrets (PUT/DELETE), GET /secrets
 *          See routers/platform_secrets_router.py (admin-only).
 */
import React, { useEffect, useState } from "react";
import { Eye, EyeOff, Trash2, Save, Check, AlertCircle,
         ShieldCheck } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

// Friendly labels + helper URLs for each whitelisted secret.
const SECRET_META = {
  // GitHub OAuth — pair (registers at github.com/settings/developers)
  GITHUB_CLIENT_ID: {
    label: "GitHub Client ID",
    hint:  "From your GitHub OAuth App at github.com/settings/developers",
    group: "GitHub",
  },
  GITHUB_CLIENT_SECRET: {
    label: "GitHub Client Secret",
    hint:  "Generated on the same page as the Client ID — keep secret",
    group: "GitHub",
    secret: true,
  },
  GITHUB_OAUTH_REDIRECT_URI: {
    label: "GitHub OAuth Redirect URI",
    hint:  "Optional. Defaults to {api_origin}/api/developers/github/oauth/callback",
    group: "GitHub",
  },
  GITHUB_BOT_PAT: { label: "GitHub Bot PAT", group: "GitHub", secret: true },
  // LLM providers
  OPENROUTER_API_KEY: { label: "OpenRouter (free-tier ladder)", group: "LLM", secret: true },
  ANTHROPIC_API_KEY:  { label: "Anthropic (Claude)",            group: "LLM", secret: true },
  OPENAI_API_KEY:     { label: "OpenAI (GPT)",                  group: "LLM", secret: true },
  GEMINI_API_KEY:     { label: "Google Gemini",                 group: "LLM", secret: true },
  EMERGENT_LLM_KEY:   { label: "Emergent Universal Key",        group: "LLM", secret: true },
  // Comms
  RESEND_API_KEY:    { label: "Resend (transactional email)", group: "Comms", secret: true },
  SENDGRID_API_KEY:  { label: "SendGrid (bulk email)",        group: "Comms", secret: true },
  TWILIO_ACCOUNT_SID:{ label: "Twilio Account SID",           group: "Comms" },
  TWILIO_AUTH_TOKEN: { label: "Twilio Auth Token",            group: "Comms", secret: true },
  WHAPI_TOKEN:       { label: "Whapi.cloud (WhatsApp)",       group: "Comms", secret: true },
  TELEGRAM_BOT_TOKEN:{ label: "Telegram Bot Token",           group: "Comms", secret: true },
  // Payment / data
  STRIPE_SECRET_KEY:  { label: "Stripe Secret Key",   group: "Payment", secret: true },
  TAVILY_API_KEY:     { label: "Tavily (web search)", group: "Data",    secret: true },
  SCRAPINGBEE_API_KEY:{ label: "ScrapingBee",         group: "Data",    secret: true },
  LINKEDIN_ACCESS_TOKEN:{label:"LinkedIn Access Token",group: "Data",   secret: true },
  // Infra
  HETZNER_API_TOKEN:    { label: "Hetzner Cloud",      group: "Infra", secret: true },
  CLOUDFLARE_API_TOKEN: { label: "Cloudflare",         group: "Infra", secret: true },
};

const GROUP_ORDER = ["GitHub", "LLM", "Comms", "Payment", "Data", "Infra"];

function groupOf(name) {
  return (SECRET_META[name] || {}).group || "Other";
}

function SecretRow({ row, onSaved, onDeleted }) {
  const meta = SECRET_META[row.name] || {};
  const [value, setValue] = useState("");
  const [shown, setShown] = useState(false);
  const [busy,  setBusy]  = useState(false);
  const [err,   setErr]   = useState(null);
  const [okFlash, setOkFlash] = useState(false);

  async function save() {
    if (!value.trim()) return;
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/settings/secrets/${row.name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ value: value.trim() }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "save_failed");
      setValue("");
      setOkFlash(true);
      setTimeout(() => setOkFlash(false), 1800);
      onSaved && onSaved();
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  async function del() {
    if (!window.confirm(`Delete ${row.name}? Live env will be cleared.`)) return;
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/settings/secrets/${row.name}`, {
        method: "DELETE", headers: devAuthHeaders(),
      });
      if (!r.ok) throw new Error("delete_failed");
      onDeleted && onDeleted();
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  return (
    <div data-testid={`secret-row-${row.name}`}
         style={{
           display: "grid",
           gridTemplateColumns: "1fr 1fr auto auto",
           gap: 10, alignItems: "center",
           padding: "12px 14px",
           borderBottom: "1px solid var(--dash-divider)",
         }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8,
                       fontSize: 13, color: "#F0EDE8" }}>
          {row.has_value && (
            <span data-testid={`secret-dot-${row.name}`}
                  title={`Set via ${row.source}`}
                  style={{ width: 7, height: 7, borderRadius: 999,
                           background: "var(--dash-green, #4ade80)" }} />
          )}
          <strong style={{ fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 12, letterSpacing: 0.2 }}>
            {row.name}
          </strong>
        </div>
        <div style={{ fontSize: 11, color: "var(--dash-text-muted)",
                       marginTop: 2 }}>
          {meta.label || row.name}
          {row.has_value && row.key_tail && (
            <span style={{ marginLeft: 8, color: "var(--dash-text-faint)" }}>
              ••••{row.key_tail}
            </span>
          )}
        </div>
      </div>
      <div style={{ position: "relative" }}>
        <input data-testid={`secret-input-${row.name}`}
               type={shown ? "text" : "password"}
               value={value}
               onChange={e => setValue(e.target.value)}
               placeholder={row.has_value ? "Enter to replace…" : "Paste key…"}
               style={{ width: "100%",
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid var(--dash-border)",
                        color: "#F0EDE8", padding: "8px 32px 8px 10px",
                        borderRadius: 4, fontSize: 12,
                        fontFamily: "'JetBrains Mono', monospace",
                        outline: "none", boxSizing: "border-box" }} />
        <button onClick={() => setShown(s => !s)}
                aria-label={shown ? "Hide" : "Show"}
                data-testid={`secret-toggle-${row.name}`}
                style={{ position: "absolute", right: 6, top: "50%",
                         transform: "translateY(-50%)",
                         background: "transparent", border: "none",
                         color: "var(--dash-text-muted)",
                         cursor: "pointer", padding: 4,
                         display: "flex", alignItems: "center" }}>
          {shown ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
      </div>
      <button data-testid={`secret-save-${row.name}`}
              onClick={save}
              disabled={busy || !value.trim()}
              style={{ padding: "8px 14px",
                       background: okFlash
                         ? "var(--dash-green, #16a34a)"
                         : "linear-gradient(135deg, #FF6B00, #FF8C35)",
                       color: "#fff", border: "none", borderRadius: 4,
                       fontSize: 12, fontWeight: 500,
                       cursor: (busy || !value.trim()) ? "not-allowed" : "pointer",
                       opacity: (busy || !value.trim()) ? 0.5 : 1,
                       display: "inline-flex", alignItems: "center", gap: 6,
                       transition: "background 200ms ease" }}>
        {okFlash ? <Check size={12} /> : <Save size={12} />}
        {okFlash ? "Saved" : (busy ? "Saving…" : "Save")}
      </button>
      <button data-testid={`secret-delete-${row.name}`}
              onClick={del}
              disabled={busy || !row.has_value || row.source !== "db"}
              title={row.source === "env"
                ? "Cleared via .env — remove there to unset"
                : "Delete stored secret"}
              style={{ padding: 8,
                       background: "transparent",
                       border: "1px solid var(--dash-border)",
                       color: (!row.has_value || row.source !== "db")
                         ? "var(--dash-text-faint)"
                         : "#FF6060",
                       borderRadius: 4, cursor: "pointer",
                       display: "inline-flex", alignItems: "center",
                       opacity: (!row.has_value || row.source !== "db") ? 0.4 : 1 }}>
        <Trash2 size={12} />
      </button>
      {err && (
        <div style={{ gridColumn: "1 / -1", fontSize: 11,
                       color: "#FF6060", marginTop: -4 }}>
          {err}
        </div>
      )}
    </div>
  );
}


export default function PlatformCredentialsBlock() {
  const [data, setData] = useState(null);
  const [err,  setErr]  = useState(null);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/settings/secrets`,
                              { headers: devAuthHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "fetch_failed");
      setData(j);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setLoading(false); }
  }

  useEffect(() => { reload(); }, []);

  // Group rows for display
  const grouped = {};
  for (const r of (data?.items || [])) {
    const g = groupOf(r.name);
    grouped[g] = grouped[g] || [];
    grouped[g].push(r);
  }

  return (
    <div data-testid="developer-settings-page"
         style={{ marginBottom: 32 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                     marginBottom: 6 }}>
        <ShieldCheck size={20} style={{ color: "var(--dash-orange)" }} />
        <h2 style={{ fontFamily: "'Cinzel', serif",
                      fontSize: 18, fontWeight: 700, margin: 0,
                      color: "var(--dash-gold-bright)" }}>
          Platform Credentials
        </h2>
      </div>
      <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                   marginBottom: 18, lineHeight: 1.6 }}>
        Paste API keys here instead of editing <code>.env</code> on the
        server. Keys are AES-256 encrypted at rest and applied to the
        live process — no restart needed.
      </p>

      {!loading && data && !data?.encryption_available && (
        <div data-testid="encryption-warning"
             style={{ padding: 12, marginBottom: 16,
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12, color: "#FFB070",
                      display: "flex", alignItems: "center", gap: 10 }}>
          <AlertCircle size={14} />
          <span>
            <strong>AUREM_ENCRYPTION_KEY not set</strong> — secrets you
            save right now will be stored plaintext. Add the env var on
            the server to enable encryption.
          </span>
        </div>
      )}

      {loading && (
        <div style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>
          Loading…
        </div>
      )}
      {err && (
        <div data-testid="settings-error"
             style={{ padding: 12, marginBottom: 16,
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12, color: "#FF6060" }}>
          {err}
        </div>
      )}

      {!loading && data && GROUP_ORDER.map(group => {
        const rows = grouped[group] || [];
        if (rows.length === 0) return null;
        return (
          <div key={group}
               data-testid={`secret-group-${group.toLowerCase()}`}
               style={{ marginBottom: 18,
                        background: "rgba(255,255,255,0.02)",
                        border: "1px solid var(--dash-divider)",
                        borderRadius: 6, overflow: "hidden" }}>
            <div style={{ padding: "10px 14px",
                           borderBottom: "1px solid var(--dash-divider)",
                           background: "rgba(255,107,0,0.04)",
                           fontSize: 10, letterSpacing: "0.18em",
                           textTransform: "uppercase",
                           color: "var(--dash-orange)" }}>
              {group}
            </div>
            {rows.map(r => (
              <SecretRow key={r.name} row={r}
                          onSaved={reload} onDeleted={reload} />
            ))}
          </div>
        );
      })}
    </div>
  );
}
