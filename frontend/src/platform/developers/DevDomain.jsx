/**
 * DevDomain.jsx — iter D-44
 *
 * /developers/domain — DNS / custom domain management. Backend lives
 * in routers/developer_deploy_router.py (/api/developers/domain/config).
 *
 * Two toggles are stored in localStorage only (no backend yet — they're
 * client-side flags consumed by the marketing site's robots.txt + the
 * Nginx redirect rule). When you're ready to enforce them server-side,
 * wire them to a new endpoint and remove the localStorage fallback.
 */
import React, { useEffect, useState } from "react";
import { Globe, ExternalLink, Link2, CheckCircle2, AlertCircle,
         Trash2 } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import { PageHeader, SectionTitle } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

function Toggle({ label, hint, value, onChange, testid }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12,
                  padding: "12px 0",
                  borderTop: "1px solid var(--dash-divider)" }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: "#F0EDE8" }}>{label}</div>
        <div style={{ fontSize: 11, color: "var(--dash-text-muted)",
                       marginTop: 2, lineHeight: 1.45 }}>{hint}</div>
      </div>
      <button data-testid={testid}
              onClick={() => onChange(!value)}
              role="switch" aria-checked={value}
              style={{ width: 44, height: 24, borderRadius: 12,
                       background: value
                         ? "linear-gradient(135deg, #FF6B00, #FF8C35)"
                         : "rgba(255,255,255,0.10)",
                       border: "none", padding: 0, cursor: "pointer",
                       position: "relative",
                       transition: "background 160ms ease" }}>
        <span style={{ position: "absolute", top: 2,
                        left: value ? 22 : 2,
                        width: 20, height: 20, borderRadius: 999,
                        background: "#fff",
                        transition: "left 160ms ease",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.30)" }} />
      </button>
    </div>
  );
}

export default function DevDomain() {
  const [cfg, setCfg]   = useState(null);
  const [dom, setDom]   = useState("");
  const [ip,  setIp]    = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr]   = useState(null);
  const [okMsg, setOk]  = useState(null);
  const [crawl, setCrawl] = useState(() => {
    try { return localStorage.getItem("aurem.domain.crawl") !== "0"; }
    catch { return true; }
  });
  const [rootRedirect, setRoot] = useState(() => {
    try { return localStorage.getItem("aurem.domain.rootRedirect") === "1"; }
    catch { return false; }
  });

  async function load() {
    setErr(null);
    try {
      const r = await fetch(`${API}/api/developers/domain/config`,
                              { headers: devAuthHeaders() });
      const j = await r.json();
      setCfg(j.configured ? j : null);
      if (j.configured) { setDom(j.domain || ""); setIp(j.server_ip || ""); }
    } catch (e) { setErr(String(e.message || e)); }
  }
  useEffect(() => { load(); }, []);

  async function link() {
    setBusy(true); setErr(null); setOk(null);
    try {
      const r = await fetch(`${API}/api/developers/domain/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ domain: dom.trim(), server_ip: ip.trim() }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "link_failed");
      setCfg(j);
      setOk(`Linked ${j.domain}. Update DNS, then your domain will go live.`);
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  function persist(key, val) {
    try { localStorage.setItem(key, val ? "1" : "0"); }
    catch { /* ignore */ }
  }

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="DOMAIN" title="Custom domain & SEO"
                  sub="Link your own domain and control how search engines see your site." />

      {/* Toggles */}
      <div className="av2-card" data-testid="domain-toggles">
        <SectionTitle title="Public-facing settings" />
        <Toggle label="Allow search engine crawling"
                hint="When OFF, robots.txt blocks Google + Bing from indexing aurem.live."
                value={crawl} testid="domain-crawl-toggle"
                onChange={v => { setCrawl(v); persist("aurem.domain.crawl", v); }} />
        <Toggle label="Redirect root domain to www"
                hint="When ON, aurem.live → www.aurem.live (301)."
                value={rootRedirect} testid="domain-rootredirect-toggle"
                onChange={v => { setRoot(v); persist("aurem.domain.rootRedirect", v); }} />
      </div>

      {/* Link form */}
      <div className="av2-card" data-testid="domain-link-card">
        <SectionTitle title="Link a custom domain" />
        <div style={{ display: "grid", gap: 10 }}>
          <label style={{ fontSize: 11, letterSpacing: "0.18em",
                           textTransform: "uppercase",
                           color: "var(--dash-text-muted)" }}>
            Domain
          </label>
          <input data-testid="domain-input"
                  value={dom}
                  onChange={e => setDom(e.target.value)}
                  placeholder="yourapp.com"
                  style={{ padding: "10px 12px", borderRadius: 4,
                           background: "rgba(255,255,255,0.04)",
                           border: "1px solid var(--dash-border)",
                           color: "#F0EDE8", fontSize: 13,
                           fontFamily: "'JetBrains Mono', monospace",
                           outline: "none" }} />
          <label style={{ fontSize: 11, letterSpacing: "0.18em",
                           textTransform: "uppercase",
                           color: "var(--dash-text-muted)",
                           marginTop: 8 }}>
            Server IP
          </label>
          <input data-testid="domain-ip-input"
                  value={ip}
                  onChange={e => setIp(e.target.value)}
                  placeholder="123.45.67.89"
                  style={{ padding: "10px 12px", borderRadius: 4,
                           background: "rgba(255,255,255,0.04)",
                           border: "1px solid var(--dash-border)",
                           color: "#F0EDE8", fontSize: 13,
                           fontFamily: "'JetBrains Mono', monospace",
                           outline: "none" }} />
          <button data-testid="domain-link-btn"
                   onClick={link}
                   disabled={busy || !dom.trim() || !ip.trim()}
                   style={{ marginTop: 8,
                            padding: "10px 18px",
                            background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                            color: "#fff", border: "none", borderRadius: 6,
                            fontSize: 13, fontWeight: 500,
                            cursor: (busy || !dom.trim() || !ip.trim())
                              ? "not-allowed" : "pointer",
                            opacity: (busy || !dom.trim() || !ip.trim()) ? 0.5 : 1,
                            display: "inline-flex", alignItems: "center",
                            justifyContent: "center", gap: 6 }}>
            <Link2 size={13} /> {busy ? "Linking…" : "Link domain"}
          </button>
        </div>

        {err && (
          <div data-testid="domain-error"
               style={{ marginTop: 12, color: "#FF6060", fontSize: 12,
                        display: "flex", gap: 8, alignItems: "center" }}>
            <AlertCircle size={14} /> {err}
          </div>
        )}
        {okMsg && (
          <div data-testid="domain-ok"
               style={{ marginTop: 12,
                        color: "var(--dash-green, #4ade80)",
                        fontSize: 12,
                        display: "flex", gap: 8, alignItems: "center" }}>
            <CheckCircle2 size={14} /> {okMsg}
          </div>
        )}
      </div>

      {/* Currently linked */}
      {cfg && (
        <div className="av2-card" data-testid="domain-current">
          <SectionTitle title="Current domain" />
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Globe size={22} style={{ color: "var(--dash-orange)" }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, color: "#F0EDE8",
                             fontFamily: "'JetBrains Mono', monospace" }}>
                {cfg.domain}
              </div>
              <div style={{ fontSize: 11, color: "var(--dash-text-muted)",
                             marginTop: 2 }}>
                → {cfg.server_ip}
              </div>
            </div>
            <a href={`https://${cfg.domain}`} target="_blank" rel="noreferrer"
               style={{ fontSize: 12, color: "#FF8C35",
                        textDecoration: "none",
                        display: "inline-flex", alignItems: "center", gap: 4 }}>
              Visit <ExternalLink size={11} />
            </a>
          </div>
          {cfg.dns_records && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, letterSpacing: "0.18em",
                             textTransform: "uppercase",
                             color: "var(--dash-text-muted)",
                             marginBottom: 8 }}>
                DNS records to add at your registrar
              </div>
              <pre style={{ background: "#0e0c0a",
                             color: "#E8C86A",
                             padding: 12, borderRadius: 4, fontSize: 11,
                             overflow: "auto", margin: 0,
                             fontFamily: "'JetBrains Mono', monospace" }}>
{cfg.dns_records.map(r =>
  `${r.type}  ${r.name.padEnd(6)} ${r.value}  TTL ${r.ttl}`
).join("\n")}
              </pre>
            </div>
          )}
        </div>
      )}
    </DeveloperShell>
  );
}
