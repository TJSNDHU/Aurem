/**
 * DevDatabase.jsx — iter D-44
 *
 * /developers/database — read-only DB info (admin-only). Backend at
 * GET /api/developers/database/info returns app name + masked Mongo
 * URL + Atlas link. We NEVER show the plaintext URL.
 */
import React, { useEffect, useState } from "react";
import { Database, ExternalLink, Eye, EyeOff, Copy, Check,
         AlertCircle } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import { PageHeader, SectionTitle } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevDatabase() {
  const [info, setInfo] = useState(null);
  const [err, setErr]   = useState(null);
  const [revealed, setReveal] = useState(false);
  const [copied,   setCopied] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/developers/database/info`, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : r.json().then(j => Promise.reject(j)))
      .then(setInfo)
      .catch(j => setErr(j?.detail || "Failed to load DB info"));
  }, []);

  function copyMasked() {
    if (!info?.mongo_url_masked) return;
    navigator.clipboard.writeText(info.mongo_url_masked);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="DATABASE" title="Database info"
                  sub="Read-only details for your AUREM MongoDB instance." />

      {err && (
        <div data-testid="database-error" className="av2-card"
             style={{ borderColor: "rgba(255,96,96,0.30)",
                       background: "rgba(255,96,96,0.05)",
                       color: "#FF6060", fontSize: 13,
                       display: "flex", gap: 8, alignItems: "center" }}>
          <AlertCircle size={14} /> {String(err)}
        </div>
      )}

      {info && (
        <>
          <div className="av2-card" data-testid="database-card">
            <div style={{ display: "flex", alignItems: "center", gap: 14,
                           marginBottom: 18 }}>
              <div style={{ width: 52, height: 52, borderRadius: 8,
                             background: "linear-gradient(135deg, #13AA52, #0E7C3A)",
                             display: "flex", alignItems: "center",
                             justifyContent: "center" }}>
                <Database size={24} style={{ color: "#fff" }} />
              </div>
              <div style={{ flex: 1 }}>
                <div data-testid="database-app-name"
                     style={{ fontSize: 15, fontWeight: 600, color: "#F0EDE8" }}>
                  {info.app_name}
                </div>
                <div style={{ fontSize: 11, color: "var(--dash-text-muted)",
                               marginTop: 2 }}>
                  {info.provider}
                </div>
              </div>
              <a href={info.atlas_link} target="_blank" rel="noreferrer"
                  data-testid="database-go-btn"
                  style={{ padding: "8px 14px",
                           background: "rgba(255,107,0,0.10)",
                           border: "1px solid rgba(255,107,0,0.40)",
                           color: "#FF8C35", borderRadius: 6,
                           fontSize: 12, fontWeight: 500,
                           textDecoration: "none",
                           display: "inline-flex", alignItems: "center",
                           gap: 6 }}>
                Go to database <ExternalLink size={11} />
              </a>
            </div>

            <SectionTitle title="Connection details" />
            <div style={{ display: "grid",
                           gridTemplateColumns: "140px 1fr",
                           gap: 10, fontSize: 12, marginBottom: 4 }}>
              <span style={{ color: "var(--dash-text-muted)" }}>DB name</span>
              <span data-testid="database-db-name"
                    style={{ color: "#F0EDE8",
                             fontFamily: "'JetBrains Mono', monospace" }}>
                {info.db_name}
              </span>
              <span style={{ color: "var(--dash-text-muted)" }}>Mongo URL</span>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span data-testid="database-mongo-url"
                      style={{ color: "#F0EDE8",
                               fontFamily: "'JetBrains Mono', monospace",
                               fontSize: 11,
                               wordBreak: "break-all", flex: 1 }}>
                  {revealed
                    ? info.mongo_url_masked
                    : "•".repeat(Math.min(48, info.mongo_url_masked.length))}
                </span>
                <button onClick={() => setReveal(r => !r)}
                         data-testid="database-toggle-reveal"
                         title={revealed ? "Hide" : "Show masked"}
                         style={{ background: "transparent", border: "none",
                                  color: "var(--dash-text-muted)",
                                  cursor: "pointer", padding: 4,
                                  display: "inline-flex" }}>
                  {revealed ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
                <button onClick={copyMasked}
                         data-testid="database-copy"
                         title="Copy masked URL"
                         style={{ background: "transparent", border: "none",
                                  color: copied ? "var(--dash-green, #4ade80)"
                                                : "var(--dash-text-muted)",
                                  cursor: "pointer", padding: 4,
                                  display: "inline-flex" }}>
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                </button>
              </div>
            </div>

            <p style={{ marginTop: 14, fontSize: 11,
                         color: "var(--dash-text-faint)" }}>
              The connection string is masked for security. The full URL
              is only available via the server <code>.env</code> or the
              Platform Credentials page.
            </p>
          </div>
        </>
      )}

      {!info && !err && (
        <div style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>
          Loading…
        </div>
      )}
    </DeveloperShell>
  );
}
