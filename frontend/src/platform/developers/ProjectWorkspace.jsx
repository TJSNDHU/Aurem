/**
 * ProjectWorkspace.jsx — iter D-32
 *
 * The live workspace per project. Left: chat (reuses DevCtoChatPanel).
 * Right: live preview iframe from preview.aurem.live/<project_id>.
 * Bottom: Go-Live checklist (locked until progress >= 0.80).
 *
 * Progress is read from the backend project doc; each chat turn that
 * triggers a build update PATCHes the progress field. The customer sees
 * the bar advance in real time.
 */
import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ExternalLink, Coins, Loader2, Flame, Eye, EyeOff,
         AlertTriangle, ShieldCheck, RefreshCcw, PlayCircle,
         Rocket, Github, Server } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import DevCtoChatPanel from "./DevCtoChatPanel";
import { GoLiveChecklist } from "./NewProjectFlow";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function ProjectWorkspace() {
  const { project_id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [wallet, setWallet]   = useState(null);
  const [streak, setStreak]   = useState(null);
  const [galleryOptedIn, setGalleryOptedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr]         = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [p, w, s, g] = await Promise.all([
        fetch(`${API}/api/onboarding/projects/${project_id}`,
              { headers: devAuthHeaders() }).then(r => r.json()),
        fetch(`${API}/api/onboarding/wallet`,
              { headers: devAuthHeaders() }).then(r => r.json()),
        fetch(`${API}/aurem-cto/streak/me`,
              { headers: devAuthHeaders() }).then(r => r.json()).catch(()=>null),
        fetch(`${API}/aurem-cto/gallery`)
              .then(r => r.json()).catch(() => ({projects:[]})),
      ]);
      if (p?.detail) throw new Error(p.detail);
      setProject(p); setWallet(w); setStreak(s);
      setGalleryOptedIn(
        (g?.projects || []).some(x => x.project_id === project_id));
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setLoading(false); }
  }, [project_id]);

  async function toggleGallery() {
    const target = galleryOptedIn ? "opt-out" : "opt-in";
    try {
      await fetch(`${API}/aurem-cto/gallery/${target}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ project_id }),
      });
      setGalleryOptedIn(!galleryOptedIn);
    } catch (e) { /* silent */ }
  }

  useEffect(() => { refresh(); }, [refresh]);
  // Poll every 8s so progress + manifest stay fresh while the build runs.
  useEffect(() => {
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  if (loading) {
    return (
      <DeveloperShell requireAuth>
        <div data-testid="project-loading"
             style={{ padding: 40, textAlign: "center",
                       color: "var(--dash-text-muted)" }}>
          <Loader2 size={20} className="onb-spin" />
        </div>
        <style>{`.onb-spin{animation:onb-spin 1s linear infinite}@keyframes onb-spin{to{transform:rotate(360deg)}}`}</style>
      </DeveloperShell>
    );
  }

  if (err || !project) {
    return (
      <DeveloperShell requireAuth>
        <div data-testid="project-error" className="av2-card"
             style={{ color: "#FF6060" }}>
          {err || "Project not found"}
          <button onClick={() => navigate("/my/projects/new")}
                   style={{ marginLeft: 12, color: "#FF8C35",
                            background: "transparent", border: "none",
                            cursor: "pointer", textDecoration: "underline" }}>
            Start a new project
          </button>
        </div>
      </DeveloperShell>
    );
  }

  const pct = Math.round((project.progress || 0) * 100);

  return (
    <DeveloperShell requireAuth>
      <div data-testid="project-workspace"
           style={{ display: "grid", gap: 18 }}>

        {/* D-35 — production-dogfood warning banner */}
        {project.is_production_dogfood && (
          <div data-testid="production-warning-banner"
               style={{ display: "flex", alignItems: "flex-start",
                          gap: 12, padding: "14px 18px",
                          borderRadius: 6,
                          background: "rgba(255,96,96,0.08)",
                          border: "1px solid rgba(255,96,96,0.45)" }}>
            <AlertTriangle size={20} style={{ color: "#FF6060",
                                                flexShrink: 0,
                                                marginTop: 2 }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600,
                             color: "#FF8C8C",
                             letterSpacing: "0.04em",
                             textTransform: "uppercase" }}>
                Production system — deploy carefully
              </div>
              <div style={{ marginTop: 4, fontSize: 13,
                             color: "rgba(240,237,232,0.82)",
                             lineHeight: 1.5 }}>
                {project.production_warning ||
                  "This is your production system — deploy carefully."}
              </div>
            </div>
          </div>
        )}

        {/* Top bar — name + progress + wallet */}
        <div data-testid="project-header" className="av2-card"
             style={{ display: "grid",
                       gridTemplateColumns: "1fr auto",
                       gap: 18, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 11,
                           letterSpacing: "0.18em",
                           textTransform: "uppercase",
                           color: "var(--dash-text-muted)" }}>
              {project.phase} · {pct}% built
              {project.go_live_ready && " · ready to ship"}
            </div>
            <h1 style={{ margin: "4px 0 0", fontSize: 24,
                          color: "#F0EDE8" }}>
              {project.name}
            </h1>
            <div style={{ marginTop: 8, height: 6, borderRadius: 3,
                           background: "rgba(255,255,255,0.06)",
                           overflow: "hidden", maxWidth: 480 }}>
              <div data-testid="project-progress-bar"
                    style={{ height: "100%", width: `${pct}%`,
                              background: project.go_live_ready
                                ? "linear-gradient(90deg, #50C878, #C9A84C)"
                                : "linear-gradient(90deg, #FF6B00, #FF8C35)",
                              transition: "width 400ms ease" }} />
            </div>
          </div>

          {wallet && (
            <div data-testid="project-wallet"
                 style={{ display: "flex", alignItems: "center",
                          gap: 14, fontSize: 12,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace" }}>
              {streak && streak.current_streak > 0 && (
                <span data-testid="project-streak"
                      style={{ display: "inline-flex", alignItems: "center",
                                gap: 5, color: "#FF8C35" }}>
                  <Flame size={14} />
                  {streak.current_streak}-day build streak
                </span>
              )}
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Coins size={14} style={{ color: "#C9A84C" }} />
                {(wallet.balance || 0).toLocaleString()} tokens left
              </span>
              <button data-testid="gallery-toggle-btn"
                       onClick={toggleGallery}
                       title={galleryOptedIn
                         ? "Currently shown on the public gallery"
                         : "Show this project on /gallery"}
                       style={{ display: "inline-flex",
                                 alignItems: "center", gap: 5,
                                 padding: "4px 10px",
                                 borderRadius: 4, fontSize: 11,
                                 cursor: "pointer",
                                 background: galleryOptedIn
                                   ? "rgba(80,200,120,0.10)"
                                   : "transparent",
                                 border: galleryOptedIn
                                   ? "1px solid rgba(80,200,120,0.40)"
                                   : "1px solid var(--dash-border)",
                                 color: galleryOptedIn
                                   ? "#50C878" : "var(--dash-text-muted)" }}>
                {galleryOptedIn ? <Eye size={11} /> : <EyeOff size={11} />}
                {galleryOptedIn ? "On gallery" : "Show on gallery"}
              </button>
            </div>
          )}
        </div>

        {/* Preview surface — skipped for production-dogfood projects */}
        {!project.is_production_dogfood && (
          <div data-testid="project-preview-card" className="av2-card">
            <div style={{ display: "flex", alignItems: "center",
                            gap: 8, marginBottom: 8,
                            color: "var(--dash-text-muted)",
                            fontSize: 11, letterSpacing: "0.15em",
                            textTransform: "uppercase" }}>
              Live preview
              <a href={project.preview_url} target="_blank" rel="noreferrer"
                 data-testid="project-preview-link"
                 style={{ marginLeft: "auto",
                           color: "#FF8C35", fontSize: 11,
                           textDecoration: "none",
                           display: "inline-flex", alignItems: "center",
                           gap: 4 }}>
                {project.preview_url} <ExternalLink size={11} />
              </a>
            </div>
            <ProjectPreviewRender manifest={project.manifest || {}}
                                   projectId={project.project_id} />
          </div>
        )}

        {/* Dogfood deploy panel (production projects only) */}
        {project.is_production_dogfood && (
          <DogfoodDeployPanel projectId={project.project_id}
                              onChange={refresh} />
        )}

        {/* Chat — every turn debits wallet + may PATCH project progress */}
        <div data-testid="project-chat-card" className="av2-card"
             style={{ padding: 0, overflow: "hidden", minHeight: 520 }}>
          <DevCtoChatPanel projectId={project.project_id}
                            modelTier="cheap"
                            onTokensUpdate={refresh} />
        </div>

        {/* Go-Live checklist (locked until progress >= 0.80) */}
        <GoLiveChecklist project={project} onChange={refresh} />
      </div>
      <style>{`.onb-spin{animation:onb-spin 1s linear infinite}@keyframes onb-spin{to{transform:rotate(360deg)}}`}</style>
    </DeveloperShell>
  );
}


// ─── Inline preview renderer (no iframe — multi-tenant FastAPI route
//     answer = c: render the manifest inline so we don't need a separate
//     container per project) ─────────────────────────────────────────
function ProjectPreviewRender({ manifest, projectId }) {
  const title    = manifest.title    || "Untitled project";
  const tagline  = manifest.tagline  || "Your build will appear here as you chat.";
  const sections = Array.isArray(manifest.sections) ? manifest.sections : [];
  const theme    = manifest.theme || {};
  const accent   = theme.accent || "#FF6B00";
  const bg       = theme.bg     || "#0B0B0E";

  return (
    <div data-testid={`preview-${projectId}`}
         style={{ background: bg, color: "#F0EDE8",
                   minHeight: 320,
                   borderRadius: 6,
                   padding: "32px 28px",
                   border: "1px solid rgba(255,255,255,0.06)",
                   overflow: "hidden",
                   position: "relative" }}>
      <div style={{ fontSize: 11, letterSpacing: "0.2em",
                     textTransform: "uppercase",
                     color: accent, marginBottom: 10 }}>
        preview.aurem.live
      </div>
      <h2 style={{ margin: 0, fontSize: 32,
                    color: "#F0EDE8", letterSpacing: "-0.02em" }}>
        {title}
      </h2>
      <p style={{ marginTop: 8, fontSize: 14,
                   color: "rgba(240,237,232,0.65)",
                   maxWidth: 640 }}>
        {tagline}
      </p>
      {sections.length === 0 && (
        <div data-testid="preview-empty"
             style={{ marginTop: 22, padding: 18, borderRadius: 4,
                       background: "rgba(255,255,255,0.04)",
                       border: "1px dashed rgba(255,255,255,0.10)",
                       color: "rgba(240,237,232,0.55)",
                       fontSize: 12 }}>
          Tell AUREM CTO what to build in the chat — the preview will
          update live as code lands.
        </div>
      )}
      {sections.slice(0, 12).map((s, i) => (
        <SectionRender key={i} s={s} accent={accent} />
      ))}
    </div>
  );
}

function SectionRender({ s, accent }) {
  if (!s || typeof s !== "object") return null;
  const kind = (s.kind || "block").toLowerCase();
  switch (kind) {
    case "hero":
      return (
        <div style={{ marginTop: 22 }}>
          <div style={{ fontSize: 12, color: accent,
                         letterSpacing: "0.15em",
                         textTransform: "uppercase" }}>{s.eyebrow || "hero"}</div>
          <div style={{ fontSize: 22, color: "#F0EDE8", marginTop: 4 }}>
            {s.text || s.heading || ""}
          </div>
        </div>
      );
    case "cta":
      return (
        <div style={{ marginTop: 18 }}>
          <span style={{ display: "inline-flex",
                          alignItems: "center", gap: 6,
                          padding: "10px 18px",
                          borderRadius: 6,
                          background: accent, color: "#0B0B0E",
                          fontSize: 13, fontWeight: 500 }}>
            {s.text || "Call to action"}
          </span>
        </div>
      );
    case "feature":
    case "block":
    default:
      return (
        <div style={{ marginTop: 14,
                       padding: 14, borderRadius: 4,
                       background: "rgba(255,255,255,0.04)",
                       border: "1px solid rgba(255,255,255,0.08)" }}>
          {s.heading && (
            <div style={{ fontSize: 13, fontWeight: 600,
                           color: "#F0EDE8" }}>{s.heading}</div>
          )}
          {s.text && (
            <div style={{ marginTop: s.heading ? 6 : 0,
                           fontSize: 12,
                           color: "rgba(240,237,232,0.7)" }}>{s.text}</div>
          )}
        </div>
      );
  }
}


// ─── Dogfood Deploy Panel (D-35) ──────────────────────────────────────
// Shown only when the project is `is_production_dogfood=true`. Surfaces
// the three wiring states (GitHub, Server, Indexer), the last dry-run /
// real-deploy result, and gates the real-deploy button on a successful
// dry-run within the last 24h.

function DogfoodDeployPanel({ projectId, onChange }) {
  const [status, setStatus] = useState(null);
  const [busy,   setBusy]   = useState("");
  const [msg,    setMsg]    = useState("");
  const [err,    setErr]    = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetch(
        `${API}/api/onboarding/projects/dogfood/aurem-live-status`,
        { headers: devAuthHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail?.msg || j.detail || "load_failed");
      setStatus(j); setErr("");
    } catch (e) { setErr(String(e.message || e)); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, [load]);

  async function refreshIndex() {
    setBusy("index"); setMsg(""); setErr("");
    try {
      const r = await fetch(
        `${API}/aurem-cto/codebase/refresh?project_id=${encodeURIComponent(projectId)}`,
        { method: "POST", headers: devAuthHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail?.msg || j.detail || "refresh_failed");
      setMsg(`Indexed ${j.file_count} files from ${j.owner}/${j.name}@${j.branch}.`);
      await load(); onChange?.();
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(""); }
  }

  async function runDeploy(mode) {
    if (mode === "deploy" &&
        !window.confirm(
          "This will push the latest commit to PRODUCTION aurem.live. " +
          "Proceed?")) return;
    setBusy(mode); setMsg(""); setErr("");
    try {
      const r = await fetch(`${API}/aurem-cto/deploy/run`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body:    JSON.stringify({ mode, project_id: projectId }),
      });
      const j = await r.json();
      if (!r.ok) {
        const code = j.detail?.code || j.detail || "run_failed";
        throw new Error(code === "dry_run_required"
          ? "Run a successful dry-run first."
          : (j.detail?.msg || String(code)));
      }
      setMsg(`${mode} started — run_id ${j.run_id}.`);
      await load(); onChange?.();
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(""); }
  }

  if (!status) {
    return (
      <div data-testid="dogfood-deploy-loading" className="av2-card"
           style={{ color: "var(--dash-text-muted)" }}>
        Loading deploy status…
      </div>
    );
  }

  const ghLinked    = status.github_linked;
  const cfgReady    = status.deploy_configured;
  const idxFresh    = status.indexer_fresh;
  const lastDry     = status.last_dry_run;
  const lastReal    = status.last_real_run;
  const realUnlocked = status.real_deploy_unlocked;

  const Pill = ({ ok, label, hint }) => (
    <div data-testid={`dogfood-pill-${label.toLowerCase().replace(/\s+/g,'-')}`}
         style={{ display: "flex", flexDirection: "column", gap: 2,
                   padding: "10px 12px", borderRadius: 4,
                   background: ok ? "rgba(80,200,120,0.07)"
                                  : "rgba(255,140,53,0.05)",
                   border: "1px solid " + (ok
                     ? "rgba(80,200,120,0.35)"
                     : "rgba(255,140,53,0.30)") }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6,
                     fontSize: 12, fontWeight: 600,
                     color: ok ? "#50C878" : "#FF8C35" }}>
        {ok ? <ShieldCheck size={13} /> : <AlertTriangle size={13} />}
        {label}
      </div>
      <div style={{ fontSize: 11,
                     color: "var(--dash-text-muted)" }}>{hint}</div>
    </div>
  );

  return (
    <div data-testid="dogfood-deploy-panel" className="av2-card">
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                     marginBottom: 14 }}>
        <Rocket size={16} style={{ color: "#FF8C35" }} />
        <h3 style={{ margin: 0, fontSize: 14, color: "#F0EDE8",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase" }}>
          Production Deploy — aurem.live
        </h3>
      </div>

      <div style={{ display: "grid",
                     gridTemplateColumns: "repeat(3, 1fr)",
                     gap: 10, marginBottom: 14 }}>
        <Pill ok={ghLinked}  label="GitHub linked"
              hint={ghLinked
                ? `${status.github?.login || "linked"} · ${status.github?.repos_count ?? "?"} repos`
                : "Link a PAT in /developers/connect"} />
        <Pill ok={cfgReady}  label="Server configured"
              hint={cfgReady
                ? `${status.deploy_config?.host} · branch ${status.deploy_config?.branch || "main"}`
                : "Save SSH host + key under Deploy card"} />
        <Pill ok={idxFresh}  label="Codebase indexed"
              hint={idxFresh
                ? `${status.index?.file_count} files · ${status.index?.repo_owner}/${status.index?.repo_name}`
                : "Hit Refresh Index after linking GitHub"} />
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button data-testid="dogfood-refresh-index-btn"
                disabled={!ghLinked || busy === "index"}
                onClick={refreshIndex}
                style={btnStyle(!ghLinked || busy === "index", "neutral")}>
          <RefreshCcw size={13} />
          {busy === "index" ? "Indexing…" : "Refresh codebase index"}
        </button>
        <button data-testid="dogfood-dry-run-btn"
                disabled={!cfgReady || busy === "dry_run"}
                onClick={() => runDeploy("dry_run")}
                style={btnStyle(!cfgReady || busy === "dry_run", "primary")}>
          <PlayCircle size={13} />
          {busy === "dry_run" ? "Running dry-run…" : "Run dry-run deploy"}
        </button>
        <button data-testid="dogfood-real-deploy-btn"
                disabled={!realUnlocked || !cfgReady || busy === "deploy"}
                onClick={() => runDeploy("deploy")}
                title={!realUnlocked
                  ? "Locked — run a successful dry-run first"
                  : "Push latest commit to aurem.live"}
                style={btnStyle(!realUnlocked || !cfgReady || busy === "deploy",
                                 "danger")}>
          <Server size={13} />
          {busy === "deploy" ? "Deploying…" : "Real deploy to aurem.live"}
        </button>
      </div>

      {(msg || err) && (
        <div data-testid="dogfood-msg"
             style={{ marginTop: 12, fontSize: 12, fontFamily: "monospace",
                       color: err ? "#FF6060" : "#50C878" }}>
          {err || msg}
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 11,
                     color: "var(--dash-text-muted)",
                     fontFamily: "JetBrains Mono, monospace" }}>
        Last dry-run:&nbsp;
        <span data-testid="dogfood-last-dry-run">
          {lastDry
            ? `${lastDry.status} (${lastDry.run_id})`
            : "never"}
        </span>
        &nbsp;·&nbsp;Last real run:&nbsp;
        <span data-testid="dogfood-last-real-run">
          {lastReal
            ? `${lastReal.mode}/${lastReal.status} (${lastReal.run_id})`
            : "never"}
        </span>
      </div>
    </div>
  );
}

function btnStyle(disabled, tone) {
  const palette = {
    neutral: { fg: "#F0EDE8", bg: "rgba(255,255,255,0.06)",
                bd: "var(--dash-border)" },
    primary: { fg: "#FF8C35", bg: "rgba(255,140,53,0.08)",
                bd: "rgba(255,140,53,0.45)" },
    danger:  { fg: "#FF6060", bg: "rgba(255,96,96,0.06)",
                bd: "rgba(255,96,96,0.40)" },
  }[tone] || {};
  return {
    display: "inline-flex", alignItems: "center", gap: 6,
    padding: "8px 14px", borderRadius: 4, fontSize: 12,
    background: palette.bg, color: palette.fg,
    border: `1px solid ${palette.bd}`,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.55 : 1,
  };
}
