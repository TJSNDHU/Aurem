/**
 * NewProjectFlow.jsx — iter D-32
 *
 * Watchdog-approved post-signup landing: customer goes STRAIGHT to project
 * creation. No GitHub / server / domain prompts. Project runs as a free
 * preview at preview.aurem.live/<project_id>. Go-Live checklist only
 * unlocks at progress >= 0.80.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, ArrowRight, Coins, Share2, Rocket,
         Github, Server, Globe, KeyRound, Check, Loader2 } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COST_CHEAP    = 1;
const COST_FRONTIER = 5;
const LOW_THRESHOLD = 100;

export default function NewProjectFlow() {
  const navigate = useNavigate();
  const [wallet, setWallet]     = useState(null);
  const [projects, setProjects] = useState([]);
  const [stacks, setStacks]     = useState([]);
  const [stackId, setStackId]   = useState("react-fastapi");
  const [name, setName]         = useState("");
  const [intent, setIntent]     = useState("");
  const [busy, setBusy]         = useState(false);
  const [err, setErr]           = useState(null);

  useEffect(() => { refresh(); }, []);

  async function refresh() {
    try {
      const [w, p, s] = await Promise.all([
        fetch(`${API}/api/onboarding/wallet`, { headers: devAuthHeaders() }).then(r => r.json()),
        fetch(`${API}/api/onboarding/projects`, { headers: devAuthHeaders() }).then(r => r.json()),
        fetch(`${API}/aurem-cto/stacks`).then(r => r.json()).catch(() => ({stacks:[]})),
      ]);
      setWallet(w); setProjects(p.projects || []);
      setStacks(s.stacks || []);
    } catch (e) { /* silent */ }
  }

  async function createProject(e) {
    e?.preventDefault?.();
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/api/onboarding/projects`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body:    JSON.stringify({ name, intent, stack: stackId }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "create_failed");
      navigate(`/my/projects/${j.project_id}`);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  return (
    <DeveloperShell requireAuth>
      <div data-testid="new-project-flow"
           style={{ display: "grid", gap: 24 }}>

        {/* Token wallet strip — visible from the start */}
        <TokenStrip wallet={wallet} />

        {/* D-35 — Admin-only dogfood seed card (silently hides for
            non-admins via 403). Lets the founder add aurem.live as a
            self-managed project in one click. */}
        <DogfoodSeedCard onSeeded={refresh} />

        {/* Existing projects (if any) */}
        {projects.length > 0 && (
          <ExistingProjectsList projects={projects} />
        )}

        {/* Create new project form */}
        <div className="av2-card"
             data-testid="new-project-card"
             style={{ background:
                       "linear-gradient(135deg, rgba(255,107,0,0.06), rgba(232,200,106,0.04))",
                      border: "1px solid rgba(255,107,0,0.30)" }}>
          <div style={{ display: "flex", alignItems: "center",
                        gap: 10, marginBottom: 8 }}>
            <Sparkles size={20} style={{ color: "#FF8C35" }} />
            <h2 style={{ fontSize: 22, color: "#F0EDE8", margin: 0 }}>
              What are we building?
            </h2>
          </div>
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                       marginBottom: 16, maxWidth: 640 }}>
            Describe your project in plain words. AUREM CTO writes the code
            and you'll see it live on a free preview URL within seconds —
            no GitHub, no server setup, nothing to configure yet. We'll
            walk you through Go-Live only when the build is ready.
          </p>

          <form onSubmit={createProject}
                 style={{ display: "grid", gap: 10 }}>
            <input data-testid="new-project-name"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="Name your project (e.g. My Bakery Site)"
                    autoFocus
                    style={inputStyle} />
            <textarea data-testid="new-project-intent"
                       value={intent}
                       onChange={e => setIntent(e.target.value)}
                       placeholder="What should it do? Example: a landing page for my bakery with photos, hours, and an online order form."
                       rows={5}
                       style={{ ...inputStyle, resize: "vertical",
                                fontFamily: "inherit" }} />
            {stacks.length > 0 && (
              <div data-testid="stack-selector"
                   style={{ display: "grid", gap: 6, marginTop: 4 }}>
                <div style={{ fontSize: 10, letterSpacing: "0.18em",
                                textTransform: "uppercase",
                                color: "var(--dash-text-muted)" }}>
                  Stack — React + FastAPI is the default
                </div>
                <div style={{ display: "grid",
                                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                                gap: 8 }}>
                  {stacks.map(s => (
                    <button key={s.id}
                            data-testid={`stack-${s.id}`}
                            type="button"
                            onClick={() => setStackId(s.id)}
                            style={{
                              padding: "10px 12px", borderRadius: 4,
                              textAlign: "left",
                              cursor: "pointer",
                              background: stackId === s.id
                                ? "rgba(255,107,0,0.10)"
                                : "rgba(255,255,255,0.03)",
                              border: stackId === s.id
                                ? "1px solid rgba(255,107,0,0.45)"
                                : "1px solid var(--dash-border)",
                              color: "#F0EDE8",
                            }}>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>
                        {s.label}
                      </div>
                      <div style={{ fontSize: 10, marginTop: 4,
                                      color: "var(--dash-text-muted)",
                                      lineHeight: 1.4 }}>
                        {s.tagline}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div style={{ display: "flex", gap: 10,
                            alignItems: "center", marginTop: 4 }}>
              <button data-testid="new-project-submit"
                       type="submit"
                       disabled={busy || !name.trim() || intent.trim().length < 5}
                       style={primaryBtn}>
                {busy ? <Loader2 size={14} className="onb-spin" /> : <ArrowRight size={14} />}
                {busy ? "Creating…" : "Start building"}
              </button>
              <span style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>
                First chat turn = 1 token (cheap model) or 5 (frontier).
              </span>
            </div>
            {err && (
              <div data-testid="new-project-error"
                   style={{ color: "#FF6060", fontSize: 12, marginTop: 4 }}>
                {err}
              </div>
            )}
          </form>
        </div>

        {/* Earn more tokens — share card */}
        <ShareForTokensCard onClaim={refresh} />
      </div>
      <style>{`
        .onb-spin { animation: onb-spin 1s linear infinite; }
        @keyframes onb-spin { to { transform: rotate(360deg); } }
      `}</style>
    </DeveloperShell>
  );
}


// ─── Token strip ──────────────────────────────────────────────────────
function TokenStrip({ wallet }) {
  if (!wallet) return null;
  const low = wallet.balance <= (wallet.low_threshold || LOW_THRESHOLD);
  const pct = Math.max(0, Math.min(100,
    Math.round((wallet.balance / Math.max(1, wallet.lifetime_earned)) * 100)));
  return (
    <div data-testid="token-strip"
         className="av2-card"
         style={{ display: "flex", alignItems: "center", gap: 18,
                   background: "rgba(255,255,255,0.03)" }}>
      <Coins size={20}
              style={{ color: low ? "#FF6060" : "#C9A84C", flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline",
                       gap: 10, flexWrap: "wrap" }}>
          <span data-testid="token-balance"
                style={{ fontSize: 22, fontWeight: 600,
                          color: low ? "#FF6060" : "#F0EDE8",
                          fontFamily: "'JetBrains Mono', monospace" }}>
            {(wallet.balance || 0).toLocaleString()}
          </span>
          <span style={{ fontSize: 11, letterSpacing: "0.15em",
                          textTransform: "uppercase",
                          color: "var(--dash-text-muted)" }}>
            tokens remaining
          </span>
          {low && (
            <span data-testid="token-low-warning"
                  style={{ fontSize: 10, padding: "2px 8px", borderRadius: 3,
                            background: "rgba(255,96,96,0.15)",
                            border: "1px solid rgba(255,96,96,0.40)",
                            color: "#FF6060",
                            fontFamily: "'JetBrains Mono', monospace",
                            letterSpacing: "0.1em" }}>
              LOW — share to earn +2500
            </span>
          )}
        </div>
        <div style={{ marginTop: 6, height: 4, borderRadius: 2,
                       background: "rgba(255,255,255,0.06)",
                       overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`,
                         background: low
                           ? "linear-gradient(90deg, #FF6060, #FF8C35)"
                           : "linear-gradient(90deg, #C9A84C, #FF8C35)",
                         transition: "width 250ms ease" }} />
        </div>
        <div style={{ marginTop: 4, fontSize: 10,
                       color: "var(--dash-text-muted)" }}>
          Cheap model = {wallet.cost_cheap || COST_CHEAP} tok ·
          Frontier = {wallet.cost_frontier || COST_FRONTIER} tok ·
          Lifetime earned {(wallet.lifetime_earned || 0).toLocaleString()},
          spent {(wallet.lifetime_spent || 0).toLocaleString()}
        </div>
      </div>
    </div>
  );
}


// ─── D-35: Dogfood seed card (admin-only, auto-hides on 403) ─────────
function DogfoodSeedCard({ onSeeded }) {
  const navigate = useNavigate();
  const [show, setShow]   = useState(false);
  const [exists, setExists] = useState(false);
  const [busy, setBusy]   = useState(false);
  const [err, setErr]     = useState("");

  useEffect(() => {
    fetch(`${API}/api/onboarding/projects/dogfood/aurem-live-status`,
          { headers: devAuthHeaders() })
      .then(r => { if (r.status === 200) { setShow(true); return r.json(); }
                   return null; })
      .then(j => { if (j?.project) setExists(true); })
      .catch(() => {});
  }, []);

  if (!show) return null;

  async function seed() {
    setBusy(true); setErr("");
    try {
      const r = await fetch(
        `${API}/api/onboarding/projects/dogfood/aurem-live-init`,
        { method: "POST",
          headers: { "Content-Type": "application/json", ...devAuthHeaders() },
          body:    JSON.stringify({}) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail?.msg || j.detail || "init_failed");
      onSeeded?.();
      navigate(`/my/projects/${j.project_id}`);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  return (
    <div className="av2-card"
         data-testid="dogfood-seed-card"
         style={{ background:
                   "linear-gradient(135deg, rgba(255,96,96,0.06), rgba(255,140,53,0.04))",
                  border: "1px solid rgba(255,96,96,0.30)" }}>
      <div style={{ display: "flex", alignItems: "flex-start",
                     gap: 12 }}>
        <Rocket size={20} style={{ color: "#FF6060",
                                     flexShrink: 0, marginTop: 2 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600,
                         color: "#F0EDE8" }}>
            Dogfood: aurem.live as a self-managed project
          </div>
          <p style={{ fontSize: 12, marginTop: 4, marginBottom: 10,
                       color: "var(--dash-text-muted)",
                       maxWidth: 640, lineHeight: 1.5 }}>
            Add aurem.live as a project in your own Developer page —
            same flow as any customer. After you wire GitHub + server,
            every fix flows through AUREM CTO and Emergent stays
            watchdog-only. A dry-run is required before each real deploy.
          </p>
          <button data-testid="dogfood-seed-btn"
                  disabled={busy}
                  onClick={() => exists
                    ? navigate("/my/projects/aurem-live-production")
                    : seed()}
                  style={{ display: "inline-flex", alignItems: "center",
                            gap: 6, padding: "8px 14px", borderRadius: 4,
                            border: "1px solid rgba(255,96,96,0.45)",
                            background: "rgba(255,96,96,0.08)",
                            color: "#FF8C8C", fontSize: 12,
                            cursor: busy ? "not-allowed" : "pointer",
                            opacity: busy ? 0.55 : 1 }}>
            {busy
              ? <Loader2 size={13} className="onb-spin" />
              : <ArrowRight size={13} />}
            {exists ? "Open aurem-live-production"
                    : (busy ? "Seeding…" : "Add aurem.live as project")}
          </button>
          {err && (
            <div data-testid="dogfood-seed-error"
                 style={{ color: "#FF6060", fontSize: 11,
                           marginTop: 6 }}>
              {err}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}



// ─── Existing projects ────────────────────────────────────────────────
function ExistingProjectsList({ projects }) {
  const navigate = useNavigate();
  return (
    <div className="av2-card"
         data-testid="existing-projects-card">
      <div style={{ fontSize: 10, letterSpacing: "0.18em",
                     textTransform: "uppercase",
                     color: "var(--dash-text-muted)",
                     marginBottom: 8 }}>
        Your projects
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        {projects.slice(0, 10).map(p => (
          <button key={p.project_id}
                  data-testid={`existing-project-${p.project_id}`}
                  onClick={() => navigate(`/my/projects/${p.project_id}`)}
                  style={{ display: "grid",
                            gridTemplateColumns: "1fr auto auto",
                            gap: 12, alignItems: "center",
                            padding: "12px 14px", borderRadius: 4,
                            background: "rgba(255,255,255,0.03)",
                            border: "1px solid var(--dash-border)",
                            color: "#F0EDE8", cursor: "pointer",
                            textAlign: "left" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{p.name}</div>
              <div style={{ fontSize: 11,
                             color: "var(--dash-text-muted)",
                             marginTop: 2 }}>
                {p.phase} · {Math.round((p.progress || 0) * 100)}% built
                {p.go_live_ready && " · ready to ship"}
              </div>
            </div>
            <div style={{ width: 120, height: 4, borderRadius: 2,
                           background: "rgba(255,255,255,0.06)",
                           overflow: "hidden" }}>
              <div style={{ height: "100%",
                             width: `${Math.round((p.progress || 0) * 100)}%`,
                             background: p.go_live_ready
                               ? "linear-gradient(90deg, #50C878, #C9A84C)"
                               : "linear-gradient(90deg, #FF6B00, #FF8C35)" }} />
            </div>
            <ArrowRight size={14} style={{ opacity: 0.5 }} />
          </button>
        ))}
      </div>
    </div>
  );
}


// ─── Share for tokens (auto-scrape, admin fallback) ───────────────────
function ShareForTokensCard({ onClaim }) {
  const [url, setUrl] = useState("");
  const [handle, setHandle] = useState("");
  const [platform, setPlatform] = useState("twitter");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);

  async function submit(e) {
    e?.preventDefault?.();
    setBusy(true); setErr(null); setResult(null);
    try {
      const r = await fetch(`${API}/api/onboarding/share/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ url, handle, platform }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "share_failed");
      setResult(j);
      if (j.status === "approved") onClaim?.();
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  return (
    <div className="av2-card"
         data-testid="share-for-tokens-card">
      <div style={{ display: "flex", alignItems: "center",
                     gap: 8, marginBottom: 6 }}>
        <Share2 size={16} style={{ color: "#C9A84C" }} />
        <h3 style={{ fontSize: 14, margin: 0, color: "#F0EDE8",
                      letterSpacing: "0.05em" }}>
          Share AUREM → earn 2500 tokens
        </h3>
      </div>
      <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                   marginBottom: 12, maxWidth: 640 }}>
        Post about AUREM on any social platform, paste the public URL
        here, and we'll auto-credit your wallet the moment we verify the
        post mentions AUREM or aurem.live. If our scraper can't see the
        mention (e.g. the post is in a screenshot), an admin reviews
        within 24h.
      </p>
      <form onSubmit={submit} style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "grid",
                       gridTemplateColumns: "140px 1fr 2fr",
                       gap: 8 }}>
          <select data-testid="share-platform"
                   value={platform}
                   onChange={e => setPlatform(e.target.value)}
                   style={inputStyle}>
            <option value="twitter">X / Twitter</option>
            <option value="linkedin">LinkedIn</option>
            <option value="reddit">Reddit</option>
            <option value="other">Other</option>
          </select>
          <input data-testid="share-handle"
                  value={handle}
                  onChange={e => setHandle(e.target.value)}
                  placeholder="@yourhandle"
                  style={inputStyle} />
          <input data-testid="share-url"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://x.com/.../status/..."
                  style={inputStyle} />
        </div>
        <button data-testid="share-submit"
                 type="submit"
                 disabled={busy || !url.trim() || !handle.trim()}
                 style={{ ...ghostBtn, alignSelf: "flex-start",
                          borderColor: "rgba(201,168,76,0.45)",
                          color: "#C9A84C" }}>
          {busy ? "Verifying…" : "Verify & claim"}
        </button>
      </form>
      {result && (
        <div data-testid="share-result"
             style={{ marginTop: 10, fontSize: 12,
                       padding: 10, borderRadius: 4,
                       background: result.status === "approved"
                         ? "rgba(80,200,120,0.08)"
                         : "rgba(255,179,107,0.08)",
                       border: result.status === "approved"
                         ? "1px solid rgba(80,200,120,0.30)"
                         : "1px solid rgba(255,179,107,0.30)",
                       color: result.status === "approved"
                         ? "#50C878" : "#FFD194" }}>
          {result.status === "approved"
            ? "Approved — 2500 tokens credited."
            : `Pending — our admin will review (${result.reason}).`}
        </div>
      )}
      {err && (
        <div style={{ marginTop: 10, color: "#FF6060", fontSize: 12 }}>
          {err}
        </div>
      )}
    </div>
  );
}


// ─── Shared styles ────────────────────────────────────────────────────
const inputStyle = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid var(--dash-border)",
  color: "#F0EDE8",
  padding: "10px 12px",
  borderRadius: 4,
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
  width: "100%",
};

const primaryBtn = {
  display: "inline-flex", alignItems: "center", gap: 8,
  padding: "10px 20px",
  background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
  color: "#fff", border: "none", borderRadius: 6,
  fontSize: 13, fontWeight: 500, cursor: "pointer",
};

const ghostBtn = {
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "9px 16px",
  background: "transparent",
  border: "1px solid var(--dash-border)",
  color: "var(--dash-text-muted)", borderRadius: 6,
  fontSize: 12, cursor: "pointer",
};


// ─── Go-Live checklist (exported for project page reuse) ──────────────
export function GoLiveChecklist({ project, onChange }) {
  const navigate = useNavigate();
  const ready = project?.go_live_ready;
  if (!ready) {
    const pct = Math.round((project?.progress || 0) * 100);
    return (
      <div data-testid="go-live-locked"
           className="av2-card"
           style={{ background: "rgba(255,255,255,0.02)",
                     border: "1px dashed var(--dash-border)" }}>
        <div style={{ display: "flex", alignItems: "center",
                       gap: 8, marginBottom: 4 }}>
          <Rocket size={16} style={{ opacity: 0.5 }} />
          <h3 style={{ fontSize: 14, margin: 0,
                        color: "var(--dash-text-muted)" }}>
            Go-Live checklist — unlocks at 80%
          </h3>
        </div>
        <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                     margin: 0 }}>
          Currently {pct}% built. Once AUREM CTO marks the build ready,
          we'll walk you through connecting GitHub, server, domain, and
          your own LLM keys.
        </p>
      </div>
    );
  }

  const items = [
    { key: "github", label: "Connect GitHub",   icon: Github,
      route: "/developers/connect#github" },
    { key: "server", label: "Connect server",   icon: Server,
      route: "/developers/connect#deploy" },
    { key: "domain", label: "Link your domain", icon: Globe,
      route: "/developers/connect#domain" },
    { key: "byok",   label: "Bring your own LLM keys", icon: KeyRound,
      route: "/developers/connect#byok" },
  ];

  return (
    <div data-testid="go-live-ready"
         className="av2-card"
         style={{ background:
                   "linear-gradient(135deg, rgba(80,200,120,0.06), rgba(201,168,76,0.04))",
                  border: "1px solid rgba(80,200,120,0.30)" }}>
      <div style={{ display: "flex", alignItems: "center",
                     gap: 8, marginBottom: 6 }}>
        <Rocket size={18} style={{ color: "#50C878" }} />
        <h3 style={{ fontSize: 16, margin: 0, color: "#F0EDE8" }}>
          Ready to ship — Go-Live checklist
        </h3>
      </div>
      <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                   marginBottom: 14 }}>
        Your build is at {Math.round((project.progress || 0) * 100)}%.
        Complete these four steps to take it off the preview and live on
        your own domain.
      </p>
      <div style={{ display: "grid", gap: 6 }}>
        {items.map(it => {
          const done = project?.go_live?.[it.key]?.done;
          const Icon = it.icon;
          return (
            <button key={it.key}
                    data-testid={`go-live-${it.key}`}
                    onClick={() => navigate(it.route)}
                    style={{ display: "grid",
                              gridTemplateColumns: "auto 1fr auto",
                              gap: 12, alignItems: "center",
                              padding: "12px 14px", borderRadius: 4,
                              background: done
                                ? "rgba(80,200,120,0.08)"
                                : "rgba(255,255,255,0.03)",
                              border: done
                                ? "1px solid rgba(80,200,120,0.35)"
                                : "1px solid var(--dash-border)",
                              color: "#F0EDE8", cursor: "pointer",
                              textAlign: "left" }}>
              <Icon size={16}
                     style={{ color: done ? "#50C878" : "#FF8C35" }} />
              <div style={{ fontSize: 13 }}>{it.label}</div>
              {done
                ? <Check size={14} style={{ color: "#50C878" }} />
                : <ArrowRight size={14} style={{ opacity: 0.55 }} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
