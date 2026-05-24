/**
 * /developers/connect — Tool connection center (Auth-gated)
 * iter 332b D-10 — Free-tier banner + optional GitHub/MongoDB + expanded BYOK
 * with cost-per-1M comparison so devs make smart choices.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Github, Code2, Sparkles, Check } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import { PageHeader, SectionTitle } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

// Provider catalogue with cost-per-1M-tokens so devs can compare.
// Ordered cheapest-first so DeepSeek lands at the top of the list.
const PROVIDERS = [
  { key: "deepseek",  label: "DeepSeek",        cost: "$0.27 / 1M",
    badge: "RECOMMENDED — cheapest, ~GPT-4o quality",
    url:   "https://platform.deepseek.com",  testid: "byok-deepseek-input" },
  { key: "groq",      label: "Groq",            cost: "Free tier",
    badge: "Llama 3.3 70B — generous free tier",
    url:   "https://console.groq.com",       testid: "byok-groq-input" },
  { key: "gemini",    label: "Gemini",          cost: "$0.35 / 1M",
    badge: "Gemini 2.0 Flash — huge context",
    url:   "https://aistudio.google.com/apikey",  testid: "byok-gemini-input" },
  { key: "openai",    label: "OpenAI",          cost: "$0.60 / 1M",
    badge: "GPT-4o-mini — most popular",
    url:   "https://platform.openai.com/api-keys", testid: "byok-openai-input" },
  { key: "anthropic", label: "Anthropic Claude", cost: "$1.00 / 1M",
    badge: "Claude Haiku — best for code review",
    url:   "https://console.anthropic.com",   testid: "byok-anthropic-input" },
  { key: "mistral",   label: "Mistral",         cost: "$0.20 / 1M",
    badge: "EU-hosted, small models",
    url:   "https://console.mistral.ai",      testid: "byok-mistral-input" },
];

const EMPTY_BYOK = {
  deepseek: "", groq: "", gemini: "", openai: "",
  anthropic: "", mistral: "",
  custom_url: "", custom_model: "", custom_api_key: "",
};

export default function DevConnect() {
  const navigate = useNavigate();
  const [byok, setByok]   = useState(EMPTY_BYOK);
  const [busy, setBusy]   = useState(false);
  const [msg, setMsg]     = useState(null);
  const [err, setErr]     = useState(null);
  const [showCustom, setShowCustom] = useState(false);

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

  const updateField = (k, v) => setByok(prev => ({ ...prev, [k]: v }));

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="CONNECT" title="Optional setup."
                  sub="Free tier is active — you can chat with AUREM CTO right now from the Dashboard. Connect tools here to unlock more autonomy." />

      {/* Free-tier banner */}
      <div data-testid="connect-free-tier-banner"
           className="av2-card"
           style={{ background: "linear-gradient(135deg, rgba(255,107,0,0.06), rgba(232,200,106,0.06))",
                    border: "1px solid rgba(255,107,0,0.30)",
                    marginBottom: 24, display: "flex",
                    alignItems: "center", gap: 16 }}>
        <Sparkles size={28} style={{ color: "#FF8C35", flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#F0EDE8",
                        marginBottom: 4 }}>
            Free tier active — start building now
          </div>
          <div style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>
            We route every chat through OpenRouter — DeepSeek V3 first,
            with Llama 3.3 70B (free) and Mistral 7B (free) as automatic
            fallbacks. No keys needed. When your 1000 free tokens run
            low, add your own key below for unlimited usage.
          </div>
        </div>
        <button data-testid="connect-go-dashboard-btn"
                onClick={() => navigate("/developers/dashboard")}
                style={{ marginLeft: "auto", padding: "8px 16px",
                         background: "rgba(255,107,0,0.15)",
                         border: "1px solid rgba(255,107,0,0.45)",
                         color: "#FF8C35", borderRadius: 6, fontSize: 12,
                         fontWeight: 500, cursor: "pointer",
                         whiteSpace: "nowrap" }}>
          → Open chat
        </button>
      </div>

      <div className="av2-grid-2">
        {/* GitHub — OPTIONAL */}
        <div className="av2-card">
          <SectionTitle title="GitHub (optional)" />
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 16 }}>
            Skip for now and set up later. Read-only OAuth by default —
            AUREM CTO writes only when you approve a PR.
          </p>
          <a data-testid="connect-github-btn"
              href={`${API}/api/auth/github/connect`}
              style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "10px 18px",
                background: "transparent",
                border: "1px solid rgba(255,107,0,0.45)",
                color: "#FF8C35", borderRadius: 6,
                fontSize: 13, fontWeight: 500, textDecoration: "none",
              }}>
            <Github size={14} /> Connect GitHub
          </a>
        </div>

        {/* VS Code — OPTIONAL */}
        <div className="av2-card">
          <SectionTitle title="VS Code (optional)" />
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 16 }}>
            Run AUREM CTO inside your editor. Skip and install later.
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
      </div>

      {/* BYOK — full provider table */}
      <div className="av2-card" data-testid="connect-byok-card"
           style={{ marginTop: 16 }}>
        <SectionTitle title="Add your own keys (BYOK)" />
        <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                     marginBottom: 18 }}>
          Skip the platform's free tier and use your own API key. Cheaper
          per token, unlimited usage, encrypted at rest. Pick any provider
          — DeepSeek is currently the best value.
        </p>

        <div style={{ display: "grid", gap: 14 }}>
          {PROVIDERS.map(p => (
            <div key={p.key}
                 data-testid={`byok-row-${p.key}`}
                 style={{ display: "grid",
                          gridTemplateColumns: "160px 1fr 110px",
                          gap: 12, alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600,
                              color: "#F0EDE8" }}>
                  {p.label}
                </div>
                <a href={p.url} target="_blank" rel="noopener noreferrer"
                   style={{ fontSize: 11, color: "var(--dash-text-muted)",
                            textDecoration: "underline" }}>
                  Get key →
                </a>
              </div>
              <input data-testid={p.testid} type="password"
                      value={byok[p.key]} placeholder="sk-… (paste your key)"
                      onChange={e => updateField(p.key, e.target.value)}
                      className="dev-input"
                      style={{ fontSize: 12 }} />
              <div data-testid={`byok-${p.key}-cost`}
                   style={{ fontSize: 11, color: p.key === "deepseek" ? "#FF8C35"
                                              : p.key === "groq"     ? "#50C878"
                                              : "var(--dash-text-muted)",
                            fontFamily: "'JetBrains Mono', monospace",
                            textAlign: "right" }}>
                {p.cost}
              </div>
              {p.badge && (
                <div style={{ gridColumn: "1 / -1",
                              fontSize: 10, color: "var(--dash-text-muted)",
                              letterSpacing: "0.05em",
                              marginTop: -8 }}>
                  {p.badge}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Custom provider toggle */}
        <button data-testid="byok-custom-toggle"
                onClick={() => setShowCustom(s => !s)}
                style={{ marginTop: 18, background: "transparent",
                         border: "1px dashed var(--dash-border)",
                         color: "var(--dash-text-muted)",
                         padding: "8px 14px", fontSize: 12,
                         borderRadius: 4, cursor: "pointer", width: "100%" }}>
          {showCustom ? "− Hide custom provider" : "+ Add a custom OpenAI-compatible provider"}
        </button>
        {showCustom && (
          <div data-testid="byok-custom-form"
               style={{ marginTop: 12, display: "grid", gap: 8 }}>
            <input data-testid="byok-custom-url-input"
                    value={byok.custom_url}
                    onChange={e => updateField("custom_url", e.target.value)}
                    placeholder="Endpoint URL (e.g. https://api.together.xyz/v1)"
                    className="dev-input" style={{ fontSize: 12 }} />
            <input data-testid="byok-custom-model-input"
                    value={byok.custom_model}
                    onChange={e => updateField("custom_model", e.target.value)}
                    placeholder="Model name (e.g. meta-llama/Llama-3.3-70B-Instruct-Turbo)"
                    className="dev-input" style={{ fontSize: 12 }} />
            <input data-testid="byok-custom-key-input" type="password"
                    value={byok.custom_api_key}
                    onChange={e => updateField("custom_api_key", e.target.value)}
                    placeholder="API key"
                    className="dev-input" style={{ fontSize: 12 }} />
          </div>
        )}
      </div>

      {msg && (
        <div data-testid="connect-success-msg" className="av2-card"
             style={{ borderColor: "rgba(80,200,120,0.30)",
                       background: "rgba(80,200,120,0.05)",
                       color: "var(--dash-green)", fontSize: 13,
                       display: "flex", gap: 8, alignItems: "center" }}>
          <Check size={14} /> {msg}
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
          Skip — I'll use free tier
        </button>
      </div>
    </DeveloperShell>
  );
}
