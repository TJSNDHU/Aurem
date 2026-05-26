/**
 * PublicGallery.jsx — Gap 3 (iter D-33)
 *
 * Public showcase of customer projects who opted in. Reads only the
 * /aurem-cto/gallery endpoint (no auth) which serves opted-in rows
 * hydrated with name/tagline/progress/preview_url.
 */
import React, { useEffect, useState } from "react";
import SEO from "../components/SEO";
import { ExternalLink } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function PublicGallery() {
  const [rows, setRows] = useState(null);
  const [err, setErr]   = useState(null);

  useEffect(() => {
    fetch(`${API}/aurem-cto/gallery`)
      .then(r => r.json())
      .then(j => setRows(j.projects || []))
      .catch(e => setErr(String(e.message || e)));
  }, []);

  return (
    <div data-testid="public-gallery"
         style={{ minHeight: "100vh", background: "#0B0B0E",
                   color: "#F0EDE8", padding: "60px 28px" }}>
      <SEO title="Built with AUREM — Project Gallery"
           description="Live customer builds shipped with AUREM CTO."
           path="/gallery" />
      <div style={{ maxWidth: 1080, margin: "0 auto" }}>
        <div style={{ fontSize: 11, letterSpacing: "0.22em",
                       textTransform: "uppercase",
                       color: "#FF8C35", marginBottom: 8 }}>
          Built with AUREM
        </div>
        <h1 style={{ margin: 0, fontSize: 40,
                      letterSpacing: "-0.02em" }}>
          Live customer projects
        </h1>
        <p style={{ marginTop: 10, fontSize: 14,
                     color: "rgba(240,237,232,0.65)",
                     maxWidth: 640 }}>
          Every project below was built live with AUREM CTO and shared
          publicly by the customer. Click any tile to see the live
          preview.
        </p>

        {err && (
          <div data-testid="gallery-error"
               style={{ marginTop: 24, color: "#FF6060" }}>
            {err}
          </div>
        )}

        {rows === null && (
          <div data-testid="gallery-loading"
               style={{ marginTop: 24,
                         color: "rgba(240,237,232,0.55)" }}>
            Loading…
          </div>
        )}

        {rows && rows.length === 0 && (
          <div data-testid="gallery-empty"
               style={{ marginTop: 32, padding: 20, borderRadius: 6,
                         background: "rgba(255,255,255,0.04)",
                         border: "1px dashed rgba(255,255,255,0.10)",
                         color: "rgba(240,237,232,0.55)",
                         fontSize: 13 }}>
            No public builds yet. Want yours featured? Build something
            with AUREM CTO and flip the "Show on gallery" switch on the
            workspace.
          </div>
        )}

        {rows && rows.length > 0 && (
          <div style={{ marginTop: 28,
                         display: "grid",
                         gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                         gap: 16 }}>
            {rows.map(p => (
              <a key={p.project_id}
                 data-testid={`gallery-card-${p.project_id}`}
                 href={p.preview_url || `/preview/${p.project_id}`}
                 target="_blank" rel="noreferrer"
                 style={{ display: "block", padding: 18,
                           borderRadius: 8,
                           background: "rgba(255,255,255,0.04)",
                           border: "1px solid rgba(255,255,255,0.08)",
                           color: "#F0EDE8",
                           textDecoration: "none",
                           transition: "transform 160ms ease, border 160ms ease" }}
                 onMouseEnter={e => {
                   e.currentTarget.style.transform = "translateY(-2px)";
                   e.currentTarget.style.borderColor = "rgba(255,107,0,0.45)";
                 }}
                 onMouseLeave={e => {
                   e.currentTarget.style.transform = "";
                   e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                 }}>
                <div style={{ fontSize: 11, letterSpacing: "0.15em",
                                textTransform: "uppercase",
                                color: "rgba(240,237,232,0.45)" }}>
                  {p.phase || "drafting"} · {Math.round((p.progress || 0) * 100)}% built
                </div>
                <div style={{ marginTop: 6, fontSize: 18,
                                fontWeight: 600 }}>
                  {p.name || p.project_id}
                </div>
                {p.tagline && (
                  <div style={{ marginTop: 6, fontSize: 13,
                                  color: "rgba(240,237,232,0.65)" }}>
                    {p.tagline}
                  </div>
                )}
                <div style={{ marginTop: 14, fontSize: 11,
                                color: "#FF8C35",
                                display: "inline-flex",
                                alignItems: "center", gap: 4 }}>
                  Open live preview <ExternalLink size={11} />
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
