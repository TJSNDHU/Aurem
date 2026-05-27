/**
 * /developers/connect — Tool connection center (Auth-gated)
 * iter 332b D-10 — Free-tier banner + optional GitHub/MongoDB + expanded BYOK
 * with cost-per-1M comparison so devs make smart choices.
 */
import React, { useState } from "react";
import SEO from "../../components/SEO";
import { useNavigate } from "react-router-dom";
import { Github, Code2, Sparkles, Check, Server, Globe, Rocket,
         RotateCcw, Copy, Loader2 } from "lucide-react";
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
      <SEO
        title="Connect — Optional GitHub, BYOK & Tools"
        description="Connect your DeepSeek, Anthropic, or OpenAI API key to AUREM (BYOK saves up to 98% on LLM costs). Optional GitHub integration for auto-provisioned dev sandboxes."
        path="/developers/connect"
        noindex
        keywords={["BYOK", "DeepSeek API", "Anthropic API", "GitHub integration"]}
        breadcrumbs={[
          { name: "Home", url: "/" },
          { name: "Developers", url: "/developers" },
          { name: "Connect", url: "/developers/connect" },
        ]}
      />
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
        {/* GitHub — PAT-based, works without OAuth app setup */}
        <GitHubConnectCard />

        {/* VS Code — direct deep-links to vscode.dev / Codespaces */}
        <VSCodeConnectCard />
      </div>

      {/* Deploy module — SSH-driven git pull + docker compose */}
      <DeployModuleCard />

      {/* Domain linking — DNS instructions + Caddy snippet */}
      <DomainLinkingCard />

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


// ─── GitHub via PAT (iter 332b D-30) ─────────────────────────────────
// Why PAT not OAuth: setting up an OAuth app needs a callback URL +
// client_id/secret rotation. PAT works the moment the dev pastes it —
// zero setup on their side, zero new env vars on ours. Token is stored
// AES-encrypted server-side (developer_byok pattern reused).
function GitHubConnectCard() {
  const [pat, setPat] = useState("");
  const [info, setInfo] = useState(null);  // {login, avatar, repos_count} or null
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  React.useEffect(() => {
    fetch(`${API}/api/developers/github/me`, { headers: devAuthHeaders() })
      .then(r => (r.ok ? r.json() : null))
      .then(j => { if (j?.login) setInfo(j); })
      .catch(() => {});
  }, []);

  async function save() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/github/link`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ pat }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "link failed");
      setInfo(j);
      setPat("");
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  async function unlink() {
    if (!window.confirm("Disconnect GitHub? Stored PAT will be erased.")) return;
    setBusy(true);
    try {
      await fetch(`${API}/api/developers/github/link`,
                  { method: "DELETE", headers: devAuthHeaders() });
      setInfo(null);
    } finally { setBusy(false); }
  }

  return (
    <div className="av2-card" data-testid="connect-github-card">
      <SectionTitle title="GitHub" />
      {info ? (
        <>
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 12 }}>
            Connected as <strong style={{ color: "#F0EDE8" }}>@{info.login}</strong>
            {" · "}{info.repos_count} repos accessible.
          </p>
          <button data-testid="connect-github-unlink"
                   onClick={unlink} disabled={busy}
                   style={{ padding: "8px 14px",
                            background: "transparent",
                            border: "1px solid var(--dash-border)",
                            color: "var(--dash-text-muted)",
                            borderRadius: 6, fontSize: 12, cursor: "pointer" }}>
            Disconnect
          </button>
        </>
      ) : (
        <>
          {/* iter D-42 — one-click GitHub OAuth (popup + postMessage).
              PAT fallback is below for users whose server admin has not
              configured GITHUB_CLIENT_ID/SECRET yet. */}
          <OneClickGitHubOAuth onConnected={(j) => setInfo(j)} />
          <div style={{ display: "flex", alignItems: "center", gap: 10,
                         margin: "16px 0", color: "var(--dash-text-muted)",
                         fontSize: 11, letterSpacing: 0.5 }}>
            <span style={{ flex: 1, height: 1,
                            background: "var(--dash-border)" }} />
            OR PASTE A TOKEN MANUALLY
            <span style={{ flex: 1, height: 1,
                            background: "var(--dash-border)" }} />
          </div>
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 12 }}>
            Paste a fine-grained <a href="https://github.com/settings/tokens?type=beta"
              target="_blank" rel="noreferrer"
              style={{ color: "#FF8C35" }}>Personal Access Token</a>
            {" "}with <code>contents:read</code> + <code>contents:write</code>.
            Stored encrypted. Lets AUREM CTO read repos, open PRs, and
            push code on your behalf.
          </p>
          <input data-testid="connect-github-pat"
                  type="password" value={pat}
                  onChange={e => setPat(e.target.value)}
                  placeholder="github_pat_…"
                  style={{ width: "100%", marginBottom: 10,
                           background: "rgba(255,255,255,0.04)",
                           border: "1px solid var(--dash-border)",
                           color: "#F0EDE8", padding: "9px 11px",
                           borderRadius: 4, fontSize: 12,
                           fontFamily: "'JetBrains Mono', monospace",
                           outline: "none", boxSizing: "border-box" }} />
          <button data-testid="connect-github-save"
                   onClick={save}
                   disabled={busy || !pat.trim().startsWith("github_pat_")}
                   style={{
                     display: "inline-flex", alignItems: "center", gap: 8,
                     padding: "10px 18px",
                     background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                     color: "#fff", border: "none", borderRadius: 6,
                     fontSize: 13, fontWeight: 500, cursor: "pointer",
                     opacity: (busy || !pat) ? 0.5 : 1 }}>
            <Github size={14} /> {busy ? "Linking…" : "Connect GitHub"}
          </button>
          {err && <div style={{ marginTop: 10, color: "#FF6060",
                                  fontSize: 12 }}>{err}</div>}
        </>
      )}
    </div>
  );
}


// iter D-42 — one-click GitHub OAuth button.
// Opens /api/developers/github/oauth/start in a centered popup, then
// listens for the postMessage from the callback HTML to close the loop.
function OneClickGitHubOAuth({ onConnected }) {
  const [busy, setBusy] = React.useState(false);
  const [err,  setErr]  = React.useState(null);

  React.useEffect(() => {
    function handle(ev) {
      // Only accept messages that look like our envelope. The callback
      // page sends a JSON object (already parsed) or a JSON string.
      let payload = ev.data;
      if (typeof payload === "string") {
        try { payload = JSON.parse(payload); } catch { return; }
      }
      if (!payload || payload.source !== "aurem-github-oauth") return;
      setBusy(false);
      if (payload.status === "success") {
        setErr(null);
        // Refresh /github/me so the parent card flips to "Connected".
        fetch(`${API}/api/developers/github/me`,
              { headers: devAuthHeaders() })
          .then(r => (r.ok ? r.json() : null))
          .then(j => { if (j?.login && onConnected) onConnected(j); })
          .catch(() => {});
      } else if (payload.status === "error") {
        setErr(payload.message || "GitHub OAuth failed.");
      }
    }
    window.addEventListener("message", handle);
    return () => window.removeEventListener("message", handle);
  }, [onConnected]);

  async function start() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/github/oauth/start`,
                              { headers: devAuthHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "oauth_start_failed");
      const w = 600, h = 720;
      const left = window.screenX + (window.outerWidth  - w) / 2;
      const top  = window.screenY + (window.outerHeight - h) / 2;
      const popup = window.open(
        j.auth_url, "aurem-github-oauth",
        `width=${w},height=${h},left=${left},top=${top},resizable,scrollbars`,
      );
      if (!popup) {
        setBusy(false);
        setErr("Popup blocked — please allow popups for this site.");
        return;
      }
      // Detect manual close so we don't sit in "Connecting…" forever.
      const t = setInterval(() => {
        if (popup.closed) { clearInterval(t); setBusy(b => b); }
      }, 600);
    } catch (e) {
      setBusy(false);
      const msg = String(e.message || e);
      if (msg.includes("not_configured")) {
        setErr("Admin: set GITHUB_CLIENT_ID + GITHUB_CLIENT_SECRET " +
               "in /admin/integrations to enable one-click.");
      } else {
        setErr(msg);
      }
    }
  }

  return (
    <div data-testid="github-oauth-block">
      <button data-testid="github-oauth-start"
              onClick={start} disabled={busy}
              style={{
                display: "inline-flex", alignItems: "center", gap: 10,
                padding: "12px 22px",
                background: "#24292F",
                color: "#fff", border: "1px solid #1B1F23",
                borderRadius: 6, fontSize: 14, fontWeight: 500,
                cursor: busy ? "default" : "pointer",
                opacity: busy ? 0.7 : 1,
                transition: "transform 120ms var(--ease-out, ease-out)",
              }}
              onMouseDown={(e) => { e.currentTarget.style.transform = "scale(0.97)"; }}
              onMouseUp={(e)   => { e.currentTarget.style.transform = "scale(1)"; }}
              onMouseLeave={(e)=> { e.currentTarget.style.transform = "scale(1)"; }}>
        <Github size={16} />
        {busy ? "Connecting…" : "Connect with GitHub"}
      </button>
      <p style={{ marginTop: 8, fontSize: 11,
                   color: "var(--dash-text-muted)" }}>
        One click, no token paste. Authorizes <code>repo</code> + <code>read:user</code>.
      </p>
      {err && (
        <div data-testid="github-oauth-error"
             style={{ marginTop: 8, color: "#FF6060", fontSize: 12 }}>
          {err}
        </div>
      )}
    </div>
  );
}

// ─── VS Code — vscode.dev / Codespaces / local protocol (iter 332b D-30) ─
function VSCodeConnectCard() {
  const [repo, setRepo] = useState("");          // e.g. owner/name
  const ghBase = repo
    ? `github.com/${repo.replace(/^https?:\/\/(www\.)?github\.com\//, "")}`
    : "";

  const open = (url) => window.open(url, "_blank", "noopener");

  return (
    <div className="av2-card" data-testid="connect-vscode-card">
      <SectionTitle title="VS Code" />
      <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                   marginBottom: 12 }}>
        Open any GitHub repo straight in <strong>vscode.dev</strong>
        {" "}(zero install), <strong>Codespaces</strong> (1-click cloud
        IDE), or your local desktop VS Code. Paste the repo path —
        owner/name format.
      </p>
      <input data-testid="connect-vscode-repo"
              value={repo}
              onChange={e => setRepo(e.target.value)}
              placeholder="aurem/aurem-platform   or   https://github.com/owner/repo"
              style={{ width: "100%", marginBottom: 10,
                       background: "rgba(255,255,255,0.04)",
                       border: "1px solid var(--dash-border)",
                       color: "#F0EDE8", padding: "9px 11px",
                       borderRadius: 4, fontSize: 12,
                       fontFamily: "'JetBrains Mono', monospace",
                       outline: "none", boxSizing: "border-box" }} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button data-testid="connect-vscode-web"
                 disabled={!ghBase}
                 onClick={() => open(`https://vscode.dev/${ghBase}`)}
                 style={vsBtn}>
          <Code2 size={14} /> Open vscode.dev
        </button>
        <button data-testid="connect-vscode-codespaces"
                 disabled={!ghBase}
                 onClick={() => open(`https://${ghBase}/codespaces`)}
                 style={vsBtn}>
          <Code2 size={14} /> Codespaces
        </button>
        <button data-testid="connect-vscode-local"
                 disabled={!ghBase}
                 onClick={() => open(`vscode://vscode.git/clone?url=https://${ghBase}.git`)}
                 style={vsBtn}>
          <Code2 size={14} /> Local VS Code
        </button>
      </div>
    </div>
  );
}

const vsBtn = {
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "8px 14px",
  background: "transparent",
  border: "1px solid rgba(201,168,76,0.30)",
  color: "#C9A84C", borderRadius: 6,
  fontSize: 12, fontWeight: 500, cursor: "pointer",
};


// ─── Deploy module (iter 332b D-30) ──────────────────────────────────
// SSH-driven `git pull && docker compose up -d --build` with live log
// streaming + history + rollback. Private key is stored encrypted server
// side via the same fernet path BYOK uses.

const EMPTY_DEPLOY = {
  host: "", port: 22, username: "root",
  private_key: "", repo_path: "/opt/aurem",
  branch: "main", compose_file: "docker-compose.yml",
};

function DeployModuleCard() {
  const [cfg, setCfg] = useState(EMPTY_DEPLOY);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [err, setErr] = useState(null);
  const [run, setRun] = useState(null);
  const [history, setHistory] = useState([]);
  const pollRef = React.useRef(null);

  React.useEffect(() => {
    fetch(`${API}/api/developers/deploy/config`,
          { headers: devAuthHeaders() })
      .then(r => r.json())
      .then(j => { if (j?.configured) { setSaved(j); }
                   else { setEditing(true); } })
      .catch(() => setEditing(true));
    fetch(`${API}/api/developers/deploy/history`,
          { headers: devAuthHeaders() })
      .then(r => r.json())
      .then(j => setHistory(j?.runs || []))
      .catch(() => {});
  }, []);

  const update = (k, v) => setCfg(p => ({ ...p, [k]: v }));

  async function saveCfg() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/deploy/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify(cfg),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "save_failed");
      const r2 = await fetch(`${API}/api/developers/deploy/config`,
                             { headers: devAuthHeaders() });
      const j2 = await r2.json();
      setSaved(j2); setEditing(false); setCfg(EMPTY_DEPLOY);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  async function disconnect() {
    if (!window.confirm("Forget the SSH key + server config?")) return;
    await fetch(`${API}/api/developers/deploy/config`,
                { method: "DELETE", headers: devAuthHeaders() });
    setSaved(null); setEditing(true);
  }

  async function startRun(mode) {
    setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/deploy/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ mode }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "run_failed");
      setRun({ run_id: j.run_id, mode: j.mode, status: "running",
               lines: [], cursor: 0 });
      pollLog(j.run_id, 0, mode);
    } catch (e) { setErr(String(e.message || e)); }
  }

  function pollLog(run_id, cursor, mode) {
    clearTimeout(pollRef.current);
    fetch(`${API}/api/developers/deploy/log/${run_id}?since=${cursor}`,
          { headers: devAuthHeaders() })
      .then(r => r.json())
      .then(j => {
        setRun(prev => prev ? ({
          ...prev,
          status: j.status,
          exit_code: j.exit_code,
          lines: [...(prev.lines || []), ...(j.lines || [])],
          cursor: j.next_cursor,
          finished_at: j.finished_at,
        }) : prev);
        if (j.status === "running") {
          pollRef.current = setTimeout(
            () => pollLog(run_id, j.next_cursor, mode), 1800);
        } else {
          fetch(`${API}/api/developers/deploy/history`,
                { headers: devAuthHeaders() })
            .then(r => r.json())
            .then(jj => setHistory(jj?.runs || []));
        }
      })
      .catch(() => {
        pollRef.current = setTimeout(
          () => pollLog(run_id, cursor, mode), 3000);
      });
  }

  React.useEffect(() => () => clearTimeout(pollRef.current), []);

  return (
    <div className="av2-card"
         data-testid="connect-deploy-card"
         style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                    marginBottom: 6 }}>
        <Server size={16} style={{ color: "#FF8C35" }} />
        <SectionTitle title="Deploy to your server" />
      </div>
      <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                  marginBottom: 14 }}>
        Push to your own Docker host over SSH. We run
        <code style={{ color: "#FF8C35", margin: "0 4px" }}>git pull && docker compose up -d</code>
        live-stream the logs, and keep the last 20 runs so you can roll
        back to the previous build in one click.
      </p>

      {saved && !editing && (
        <div data-testid="deploy-saved-summary"
             style={{ fontSize: 12, color: "var(--dash-text-muted)",
                      padding: "10px 12px", borderRadius: 4,
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid var(--dash-border)",
                      marginBottom: 12 }}>
          <div>Target: <strong style={{ color: "#F0EDE8" }}>
            {saved.username}@{saved.host}:{saved.port}
          </strong> · Path <code>{saved.repo_path}</code> · Branch
          <code style={{ marginLeft: 4 }}>{saved.branch}</code></div>
          <div style={{ marginTop: 4, fontSize: 11, opacity: 0.7 }}>
            Compose file: <code>{saved.compose_file}</code> · Key {saved.private_key}
          </div>
        </div>
      )}

      {editing ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ display: "grid",
                        gridTemplateColumns: "2fr 80px 1fr", gap: 8 }}>
            <input data-testid="deploy-host"
                    value={cfg.host}
                    placeholder="server.example.com or IP"
                    onChange={e => update("host", e.target.value)}
                    style={dInput} />
            <input data-testid="deploy-port" type="number"
                    value={cfg.port} placeholder="22"
                    onChange={e => update("port", Number(e.target.value || 22))}
                    style={dInput} />
            <input data-testid="deploy-user"
                    value={cfg.username} placeholder="root / ubuntu"
                    onChange={e => update("username", e.target.value)}
                    style={dInput} />
          </div>
          <div style={{ display: "grid",
                        gridTemplateColumns: "2fr 1fr 1fr", gap: 8 }}>
            <input data-testid="deploy-repo-path"
                    value={cfg.repo_path}
                    placeholder="/opt/aurem (remote checkout path)"
                    onChange={e => update("repo_path", e.target.value)}
                    style={dInput} />
            <input data-testid="deploy-branch"
                    value={cfg.branch} placeholder="main"
                    onChange={e => update("branch", e.target.value)}
                    style={dInput} />
            <input data-testid="deploy-compose"
                    value={cfg.compose_file}
                    placeholder="docker-compose.yml"
                    onChange={e => update("compose_file", e.target.value)}
                    style={dInput} />
          </div>
          <textarea data-testid="deploy-ssh-key"
                     value={cfg.private_key}
                     onChange={e => update("private_key", e.target.value)}
                     placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n…\n-----END OPENSSH PRIVATE KEY-----"}
                     rows={6}
                     style={{ ...dInput,
                              fontFamily: "'JetBrains Mono', monospace",
                              resize: "vertical" }} />
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button data-testid="deploy-save-btn"
                     onClick={saveCfg} disabled={busy}
                     style={primaryBtn}>
              {busy ? "Saving…" : "Save target"}
            </button>
            {saved && (
              <button onClick={() => { setEditing(false);
                                       setCfg(EMPTY_DEPLOY); }}
                       style={ghostBtn}>
                Cancel
              </button>
            )}
          </div>
          <div style={{ fontSize: 11, color: "var(--dash-text-muted)",
                         marginTop: 2 }}>
            The key is encrypted server-side using the same fernet path as
            your BYOK secrets. We never log or echo it back in plaintext.
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button data-testid="deploy-run-btn"
                   onClick={() => startRun("deploy")}
                   disabled={!!run && run.status === "running"}
                   style={primaryBtn}>
            {run && run.status === "running" && run.mode === "deploy"
              ? <><Loader2 size={14} className="dev-spin" /> Deploying…</>
              : <><Rocket size={14} /> Deploy now</>}
          </button>
          <button data-testid="deploy-rollback-btn"
                   onClick={() => {
                     if (window.confirm("Roll back to the previous commit on the server?"))
                       startRun("rollback");
                   }}
                   disabled={!!run && run.status === "running"}
                   style={ghostBtn}>
            <RotateCcw size={14} /> Roll back
          </button>
          <button data-testid="deploy-edit-btn"
                   onClick={() => setEditing(true)}
                   style={ghostBtn}>
            Edit target
          </button>
          <button data-testid="deploy-disconnect-btn"
                   onClick={disconnect}
                   style={{ ...ghostBtn, color: "#FF6060",
                            borderColor: "rgba(255,96,96,0.30)" }}>
            Disconnect
          </button>
        </div>
      )}

      {err && (
        <div data-testid="deploy-error"
             style={{ marginTop: 10, color: "#FF6060", fontSize: 12,
                       padding: 8, background: "rgba(255,96,96,0.08)",
                       border: "1px solid rgba(255,96,96,0.25)",
                       borderRadius: 4 }}>
          {err}
        </div>
      )}

      {run && (
        <div data-testid="deploy-log-panel"
             style={{ marginTop: 14, background: "#0B0B0E",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: 4, padding: 10,
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 11, color: "#9CA3AF",
                      maxHeight: 280, overflow: "auto",
                      whiteSpace: "pre-wrap" }}>
          <div style={{ display: "flex",
                         justifyContent: "space-between",
                         marginBottom: 6,
                         color: run.status === "ok"      ? "#50C878"
                              : run.status === "running" ? "#FF8C35"
                              :                            "#FF6060",
                         fontSize: 10, letterSpacing: "0.15em",
                         textTransform: "uppercase" }}>
            <span>{run.mode} · {run.status}
                  {typeof run.exit_code === "number"
                    ? ` · exit ${run.exit_code}` : ""}</span>
            <span>{(run.lines || []).length} lines</span>
          </div>
          {(run.lines || []).slice(-300).map((l, i) => (
            <div key={i}>{l}</div>
          ))}
          {(!run.lines || run.lines.length === 0)
              && run.status === "running" && (
            <div style={{ opacity: 0.6 }}>Waiting for first output…</div>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div data-testid="deploy-history" style={{ marginTop: 14 }}>
          <div style={{ fontSize: 10, letterSpacing: "0.18em",
                         textTransform: "uppercase",
                         color: "var(--dash-text-muted)",
                         marginBottom: 6 }}>
            Recent deploys
          </div>
          <div style={{ display: "grid", gap: 4 }}>
            {history.slice(0, 8).map(h => (
              <div key={h.run_id}
                   data-testid={`deploy-history-row-${h.run_id}`}
                   style={{ display: "grid",
                            gridTemplateColumns: "auto 70px 1fr 90px",
                            gap: 10, fontSize: 11, alignItems: "center",
                            color: "var(--dash-text-muted)",
                            padding: "6px 8px", borderRadius: 3,
                            background: "rgba(255,255,255,0.02)" }}>
                <span style={{ color:
                  h.status === "ok"      ? "#50C878"
                : h.status === "running" ? "#FF8C35"
                : h.status === "timeout" ? "#FFD194"
                :                          "#FF6060",
                  fontWeight: 600, textTransform: "uppercase" }}>
                  {h.status || "?"}
                </span>
                <span>{h.mode}</span>
                <span style={{ fontFamily:
                                "'JetBrains Mono', monospace",
                                fontSize: 10, opacity: 0.85,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis" }}>
                  {h.started_at?.slice(0, 19).replace("T", " ")}
                  {h.host ? `  ·  ${h.host}` : ""}
                </span>
                <span style={{ textAlign: "right", opacity: 0.7 }}>
                  {typeof h.exit_code === "number"
                    ? `exit ${h.exit_code}` : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      <style>{`
        .dev-spin { animation: dev-spin 1s linear infinite; }
        @keyframes dev-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}


// ─── Domain linking (iter 332b D-30) ─────────────────────────────────
function DomainLinkingCard() {
  const [domain, setDomain] = useState("");
  const [ip, setIp] = useState("");
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState("");

  React.useEffect(() => {
    fetch(`${API}/api/developers/domain/config`,
          { headers: devAuthHeaders() })
      .then(r => r.json())
      .then(j => { if (j?.configured) {
                     setInfo(j);
                     setDomain(j.domain || "");
                     setIp(j.server_ip || "");
                   } })
      .catch(() => {});
  }, []);

  async function save() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/domain/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ domain, server_ip: ip }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "save_failed");
      setInfo(j);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  async function copyText(label, text) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(""), 1600);
    } catch { /* no-op */ }
  }

  return (
    <div className="av2-card"
         data-testid="connect-domain-card"
         style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                    marginBottom: 6 }}>
        <Globe size={16} style={{ color: "#FF8C35" }} />
        <SectionTitle title="Link a custom domain" />
      </div>
      <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                  marginBottom: 12 }}>
        Save your apex domain + server IP — we'll generate the DNS
        records you need to add at your registrar, plus a one-paste
        Caddyfile that auto-provisions a Let's Encrypt TLS cert on
        first request.
      </p>

      <div style={{ display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 8, marginBottom: 10 }}>
        <input data-testid="domain-input"
                value={domain}
                onChange={e => setDomain(e.target.value)}
                placeholder="aurem.live"
                style={dInput} />
        <input data-testid="domain-ip-input"
                value={ip}
                onChange={e => setIp(e.target.value)}
                placeholder="203.0.113.42"
                style={dInput} />
      </div>
      <button data-testid="domain-save-btn"
               onClick={save}
               disabled={busy || !domain.trim() || !ip.trim()}
               style={primaryBtn}>
        {busy ? "Generating…" : "Generate DNS + Caddy config"}
      </button>

      {err && (
        <div data-testid="domain-error"
             style={{ marginTop: 10, color: "#FF6060",
                       fontSize: 12 }}>
          {err}
        </div>
      )}

      {info && (
        <div data-testid="domain-output" style={{ marginTop: 14 }}>
          <div style={{ fontSize: 10, letterSpacing: "0.18em",
                         textTransform: "uppercase",
                         color: "var(--dash-text-muted)",
                         marginBottom: 6 }}>
            Step 1 — Add these DNS records at your registrar
          </div>
          <table style={{ width: "100%", fontSize: 12,
                           fontFamily: "'JetBrains Mono', monospace",
                           borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "var(--dash-text-muted)",
                            fontSize: 10, textAlign: "left" }}>
                <th style={th}>Type</th>
                <th style={th}>Name</th>
                <th style={th}>Value</th>
                <th style={th}>TTL</th>
              </tr>
            </thead>
            <tbody>
              {(info.dns_records || []).map((r, i) => (
                <tr key={i}
                    data-testid={`domain-dns-row-${i}`}
                    style={{ color: "#F0EDE8",
                             borderTop:
                               "1px solid var(--dash-divider)" }}>
                  <td style={td}>{r.type}</td>
                  <td style={td}>{r.name}</td>
                  <td style={td}>{r.value}</td>
                  <td style={td}>{r.ttl}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 14, fontSize: 10,
                         letterSpacing: "0.18em",
                         textTransform: "uppercase",
                         color: "var(--dash-text-muted)",
                         display: "flex",
                         alignItems: "center", gap: 8 }}>
            Step 2 — Drop this into <code>/etc/caddy/Caddyfile</code>
            <button data-testid="domain-caddy-copy"
                     onClick={() => copyText("caddy", info.caddyfile)}
                     style={{ marginLeft: "auto",
                              display: "inline-flex", gap: 4,
                              alignItems: "center",
                              padding: "4px 10px",
                              background: "transparent",
                              border: "1px solid var(--dash-border)",
                              color: copied === "caddy"
                                ? "#50C878"
                                : "var(--dash-text-muted)",
                              borderRadius: 4, fontSize: 10,
                              cursor: "pointer", letterSpacing: 0 }}>
              {copied === "caddy"
                ? <><Check size={11} /> Copied</>
                : <><Copy size={11} /> Copy</>}
            </button>
          </div>
          <pre data-testid="domain-caddy-snippet"
                style={{ marginTop: 6, background: "#0B0B0E",
                          border: "1px solid rgba(255,255,255,0.08)",
                          borderRadius: 4, padding: 10,
                          fontSize: 11, color: "#E8E8E8",
                          fontFamily: "'JetBrains Mono', monospace",
                          whiteSpace: "pre-wrap", overflow: "auto" }}>
{info.caddyfile}
          </pre>

          <div style={{ marginTop: 10, fontSize: 12,
                         color: "var(--dash-text-muted)" }}>
            Step 3 — Reload Caddy with
            <code style={{ margin: "0 4px", color: "#FF8C35" }}>
              sudo systemctl reload caddy
            </code>
            then hit <code style={{ color: "#FF8C35" }}>
              https://{info.domain}
            </code> from your browser. Caddy issues the TLS cert on
            first request. {info.ssl_note}
          </div>

          <div style={{ marginTop: 8, fontSize: 11,
                         color: "var(--dash-text-muted)",
                         fontFamily:
                           "'JetBrains Mono', monospace" }}>
            Verify DNS:
            <button data-testid="domain-verify-copy"
                     onClick={() =>
                       copyText("verify", info.verify_cmd)}
                     style={{ marginLeft: 8, padding: "2px 8px",
                              background: "transparent",
                              border: "1px solid var(--dash-border)",
                              color: copied === "verify"
                                ? "#50C878"
                                : "var(--dash-text-muted)",
                              borderRadius: 4, fontSize: 10,
                              cursor: "pointer" }}>
              {copied === "verify" ? "copied" : "copy cmd"}
            </button>
            <div style={{ marginTop: 4 }}>
              <code>{info.verify_cmd}</code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


const dInput = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid var(--dash-border)",
  color: "#F0EDE8", padding: "9px 11px",
  borderRadius: 4, fontSize: 12,
  fontFamily: "'JetBrains Mono', monospace",
  outline: "none", boxSizing: "border-box",
  width: "100%",
};

const primaryBtn = {
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "9px 16px",
  background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
  color: "#fff", border: "none", borderRadius: 6,
  fontSize: 12, fontWeight: 500, cursor: "pointer",
};

const ghostBtn = {
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "9px 14px",
  background: "transparent",
  border: "1px solid var(--dash-border)",
  color: "var(--dash-text-muted)", borderRadius: 6,
  fontSize: 12, cursor: "pointer",
};

const th = { padding: "4px 8px", fontWeight: 500 };
const td = { padding: "6px 8px" };
