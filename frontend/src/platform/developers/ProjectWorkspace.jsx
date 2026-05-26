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
import { ExternalLink, Coins, Loader2 } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import DevCtoChatPanel from "./DevCtoChatPanel";
import { GoLiveChecklist } from "./NewProjectFlow";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function ProjectWorkspace() {
  const { project_id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [wallet, setWallet]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr]         = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [p, w] = await Promise.all([
        fetch(`${API}/api/onboarding/projects/${project_id}`,
              { headers: devAuthHeaders() }).then(r => r.json()),
        fetch(`${API}/api/onboarding/wallet`,
              { headers: devAuthHeaders() }).then(r => r.json()),
      ]);
      if (p?.detail) throw new Error(p.detail);
      setProject(p); setWallet(w);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setLoading(false); }
  }, [project_id]);

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
                          gap: 8, fontSize: 12,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace" }}>
              <Coins size={14} style={{ color: "#C9A84C" }} />
              {(wallet.balance || 0).toLocaleString()} tokens left
            </div>
          )}
        </div>

        {/* Preview surface */}
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
