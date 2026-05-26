/**
 * PublicProjectPreview.jsx — iter D-32
 *
 * Anonymous-friendly renderer at /preview/:project_id. Reads the public
 * manifest endpoint (no auth) and renders the same inline preview shown
 * inside the workspace. Pointed at preview.aurem.live/<id> via DNS+Caddy
 * once the user wires the apex DNS record.
 */
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import SEO from "../components/SEO";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function PublicProjectPreview() {
  const { project_id } = useParams();
  const [project, setProject] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancel = false;
    async function load() {
      try {
        const r = await fetch(
          `${API}/api/preview/projects/${project_id}/manifest`);
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || "preview_not_found");
        if (!cancel) setProject(j);
      } catch (e) { if (!cancel) setErr(String(e.message || e)); }
    }
    load();
    const tick = setInterval(load, 6000);     // 6-s live refresh
    return () => { cancel = true; clearInterval(tick); };
  }, [project_id]);

  if (err) {
    return (
      <div data-testid="public-preview-error"
           style={errBoxStyle}>
        <div style={{ fontSize: 11, letterSpacing: "0.2em",
                       color: "#FF8C35", textTransform: "uppercase",
                       marginBottom: 8 }}>
          preview.aurem.live
        </div>
        <h1 style={{ margin: 0, fontSize: 24 }}>Project not found</h1>
        <p style={{ marginTop: 8, fontSize: 13,
                     color: "rgba(240,237,232,0.65)" }}>
          The preview ID <code>{project_id}</code> doesn't exist or has
          been removed. If you own this project, sign in to AUREM and
          start a new one.
        </p>
        <a href="/my/projects/new"
           style={{ display: "inline-block", marginTop: 14,
                     padding: "10px 18px",
                     background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                     color: "#fff", textDecoration: "none",
                     borderRadius: 6, fontSize: 13 }}>
          Build your own project →
        </a>
      </div>
    );
  }

  if (!project) {
    return (
      <div data-testid="public-preview-loading" style={loadingStyle}>
        Loading preview…
      </div>
    );
  }

  const m = project.manifest || {};
  const theme = m.theme || {};
  const accent = theme.accent || "#FF6B00";
  const bg = theme.bg || "#0B0B0E";

  return (
    <div data-testid="public-preview"
         style={{ minHeight: "100vh", background: bg, color: "#F0EDE8",
                  fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <SEO title={`${m.title || "Preview"} — AUREM`}
            description={m.tagline || "A live build preview on AUREM."}
            path={`/preview/${project_id}`}
            noindex />
      <header style={{ padding: "14px 28px",
                        borderBottom: "1px solid rgba(255,255,255,0.08)",
                        display: "flex", alignItems: "center",
                        gap: 16,
                        fontSize: 11, letterSpacing: "0.2em",
                        textTransform: "uppercase",
                        color: "rgba(240,237,232,0.55)" }}>
        <span style={{ color: accent }}>preview.aurem.live</span>
        <span data-testid="public-preview-id">{project_id}</span>
        <span data-testid="public-preview-progress"
              style={{ marginLeft: "auto" }}>
          {project.phase} · {Math.round((project.progress || 0) * 100)}% built
        </span>
      </header>

      <main style={{ maxWidth: 880,
                       margin: "0 auto",
                       padding: "48px 28px" }}>
        <h1 data-testid="public-preview-title"
            style={{ margin: 0, fontSize: 44,
                      letterSpacing: "-0.02em" }}>
          {m.title || project.name || "Untitled"}
        </h1>
        {m.tagline && (
          <p data-testid="public-preview-tagline"
             style={{ marginTop: 12, fontSize: 18,
                       color: "rgba(240,237,232,0.65)",
                       maxWidth: 640 }}>
            {m.tagline}
          </p>
        )}
        {(!m.sections || m.sections.length === 0) && (
          <div data-testid="public-preview-empty"
               style={{ marginTop: 32, padding: 20, borderRadius: 6,
                         background: "rgba(255,255,255,0.04)",
                         border: "1px dashed rgba(255,255,255,0.10)",
                         color: "rgba(240,237,232,0.55)",
                         fontSize: 13 }}>
            This preview is still being built. The owner is chatting with
            AUREM CTO right now — refresh in a few seconds.
          </div>
        )}
        {(m.sections || []).slice(0, 30).map((s, i) => (
          <PublicSection key={i} s={s} accent={accent} />
        ))}
        {m.primary_cta && (
          <div style={{ marginTop: 30 }}>
            <a href={m.primary_cta.url || "#"}
               data-testid="public-preview-cta"
               style={{ display: "inline-block",
                         padding: "12px 24px",
                         background: accent, color: "#0B0B0E",
                         textDecoration: "none",
                         borderRadius: 6,
                         fontSize: 14, fontWeight: 500 }}>
              {m.primary_cta.label || "Get started"}
            </a>
          </div>
        )}
      </main>

      <footer style={{ padding: 18, textAlign: "center",
                        fontSize: 11,
                        color: "rgba(240,237,232,0.45)",
                        borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        Built live with{" "}
        <a href="/" style={{ color: accent }}>AUREM</a>
        {" · "}
        <a href="/my/projects/new"
           style={{ color: "rgba(240,237,232,0.65)" }}>
          Build your own
        </a>
      </footer>
    </div>
  );
}


function PublicSection({ s, accent }) {
  if (!s || typeof s !== "object") return null;
  const kind = (s.kind || "block").toLowerCase();
  if (kind === "hero") {
    return (
      <section style={{ marginTop: 36 }}>
        {s.eyebrow && (
          <div style={{ fontSize: 11, letterSpacing: "0.18em",
                         textTransform: "uppercase",
                         color: accent }}>
            {s.eyebrow}
          </div>
        )}
        <h2 style={{ margin: "4px 0 0", fontSize: 30,
                      letterSpacing: "-0.01em" }}>
          {s.heading || s.text || ""}
        </h2>
        {s.text && s.heading && (
          <p style={{ marginTop: 10, fontSize: 15,
                       color: "rgba(240,237,232,0.65)" }}>
            {s.text}
          </p>
        )}
      </section>
    );
  }
  if (kind === "cta") {
    return (
      <div style={{ marginTop: 24 }}>
        <a href={s.url || "#"}
           style={{ display: "inline-block",
                     padding: "12px 24px",
                     background: accent, color: "#0B0B0E",
                     textDecoration: "none", borderRadius: 6,
                     fontSize: 14, fontWeight: 500 }}>
          {s.text || "Call to action"}
        </a>
      </div>
    );
  }
  // feature / block / default
  return (
    <section style={{ marginTop: 22,
                       padding: 18, borderRadius: 6,
                       background: "rgba(255,255,255,0.04)",
                       border: "1px solid rgba(255,255,255,0.08)" }}>
      {s.heading && (
        <div style={{ fontSize: 16, fontWeight: 600,
                       color: "#F0EDE8" }}>
          {s.heading}
        </div>
      )}
      {s.text && (
        <div style={{ marginTop: s.heading ? 8 : 0,
                       fontSize: 14,
                       color: "rgba(240,237,232,0.7)",
                       lineHeight: 1.55 }}>
          {s.text}
        </div>
      )}
    </section>
  );
}


const errBoxStyle = {
  minHeight: "100vh",
  background: "#0B0B0E",
  color: "#F0EDE8",
  padding: "80px 28px",
  textAlign: "center",
  fontFamily: "system-ui, -apple-system, sans-serif",
};

const loadingStyle = {
  minHeight: "100vh",
  background: "#0B0B0E",
  color: "rgba(240,237,232,0.55)",
  display: "grid", placeItems: "center",
  fontSize: 13,
  letterSpacing: "0.18em",
  textTransform: "uppercase",
};
