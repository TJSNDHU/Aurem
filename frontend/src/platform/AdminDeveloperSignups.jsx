/**
 * /admin/developer-signups — iter 332b D-7
 *
 * Minimal page: founder asked "I want one thing — just emails of
 * who signed up in my dev panel". So this page renders exactly that:
 * email, signup date, verified flag, tokens remaining, GitHub status.
 * Plus a CSV-copy button so the list can be pasted into a CRM.
 *
 * Backend: GET /api/admin/developers (already exists from iter 331f).
 */
import React, { useEffect, useState } from "react";
import { adminHeaders, ENT_API } from "./enterprise/EnterpriseAdminShell";

export default function AdminDeveloperSignups() {
  const [rows, setRows]       = useState([]);
  const [total, setTotal]     = useState(0);
  const [flagged, setFlagged] = useState(0);
  const [filter, setFilter]   = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");
  const [copied, setCopied]   = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await fetch(`${ENT_API}/api/admin/developers?limit=500`,
                              { headers: adminHeaders() });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (cancelled) return;
        setRows(j.rows || []);
        setTotal(j.total || 0);
        setFlagged(j.flagged || 0);
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const visible = filter
    ? rows.filter(r =>
        (r.email || "").toLowerCase().includes(filter.toLowerCase()) ||
        (r.name  || "").toLowerCase().includes(filter.toLowerCase()))
    : rows;

  const copyEmails = async () => {
    const text = visible.map(r => r.email).filter(Boolean).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable */ }
  };

  // iter 332b D-8 — CSV export. Streams the full file (not just the
  // filtered subset) so the admin always gets the complete cohort.
  const downloadCsv = async () => {
    try {
      const r = await fetch(`${ENT_API}/api/admin/developers/export.csv`,
                            { headers: adminHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aurem-developer-signups-${new Date().toISOString().slice(0,10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(String(e.message || e));
    }
  };

  return (
    <div data-testid="admin-dev-signups-page"
         style={{ padding: "32px 40px", color: "#F0EDE8",
                  fontFamily: "'Jost', sans-serif", minHeight: "100vh" }}>
      <div style={{ marginBottom: 6 }}>
        <span data-testid="admin-dev-signups-eyebrow"
              style={{ fontFamily: "'JetBrains Mono', monospace",
                       fontSize: 11, letterSpacing: "0.2em",
                       color: "#FF6B00", textTransform: "uppercase" }}>
          ADMIN · DEVELOPER PORTAL
        </span>
      </div>
      <h1 data-testid="admin-dev-signups-title"
          style={{ fontFamily: "'Cinzel', serif",
                   fontSize: 32, fontWeight: 600,
                   margin: "8px 0 24px",
                   letterSpacing: "0.01em" }}>
        Developer signups
      </h1>

      <div style={{ display: "flex", gap: 16, marginBottom: 22,
                    flexWrap: "wrap" }}>
        <Tile testid="admin-dev-total" label="Total signups" value={total} />
        <Tile testid="admin-dev-verified" label="Showing"
              value={visible.length} />
        <Tile testid="admin-dev-flagged" label="Abuse-flagged"
              value={flagged} tone={flagged > 0 ? "red" : "muted"} />
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 16,
                    alignItems: "center", flexWrap: "wrap" }}>
        <input
          data-testid="admin-dev-search"
          placeholder="Filter by email or name…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{ background: "rgba(255,255,255,0.04)",
                   border: "1px solid rgba(255,107,0,0.20)",
                   color: "#F0EDE8", padding: "9px 14px",
                   borderRadius: 4, minWidth: 280, fontSize: 13,
                   fontFamily: "inherit", outline: "none" }} />
        <button data-testid="admin-dev-copy-emails"
                onClick={copyEmails}
                style={{ background: copied
                           ? "rgba(76,175,80,0.18)"
                           : "linear-gradient(135deg, #FF6B00, #FF8C35)",
                         color: "#fff", padding: "9px 18px",
                         border: "none", borderRadius: 4,
                         fontSize: 12, letterSpacing: "0.05em",
                         cursor: "pointer", fontFamily: "inherit" }}>
          {copied ? "Copied to clipboard ✓"
                  : `Copy ${visible.length} email${visible.length === 1 ? "" : "s"}`}
        </button>
        <button data-testid="admin-dev-export-csv"
                onClick={downloadCsv}
                style={{ background: "transparent",
                         color: "#E8C86A",
                         padding: "9px 18px",
                         border: "1px solid rgba(232,200,106,0.45)",
                         borderRadius: 4, fontSize: 12,
                         letterSpacing: "0.05em",
                         cursor: "pointer", fontFamily: "inherit" }}>
          Export CSV
        </button>
      </div>

      {loading && (
        <div data-testid="admin-dev-loading"
             style={{ color: "#7A7590", fontSize: 13 }}>
          Loading signups…
        </div>
      )}
      {error && (
        <div data-testid="admin-dev-error"
             style={{ color: "#E5484D", fontSize: 13,
                      padding: "10px 14px",
                      background: "rgba(229,72,77,0.08)",
                      border: "1px solid rgba(229,72,77,0.25)",
                      borderRadius: 4 }}>
          Could not load: {error}
        </div>
      )}
      {!loading && !error && visible.length === 0 && (
        <div data-testid="admin-dev-empty"
             style={{ color: "#7A7590", fontSize: 13,
                      padding: 32, textAlign: "center",
                      border: "1px dashed rgba(255,107,0,0.20)",
                      borderRadius: 6 }}>
          {rows.length === 0
            ? "Nobody has signed up to the developer portal yet."
            : "No signups match your filter."}
        </div>
      )}

      {!loading && !error && visible.length > 0 && (
        <div data-testid="admin-dev-signups-table"
             style={{ border: "1px solid rgba(255,107,0,0.12)",
                      borderRadius: 6, overflow: "hidden",
                      background: "#0F0F1A" }}>
          <table style={{ width: "100%", borderCollapse: "collapse",
                          fontSize: 13 }}>
            <thead>
              <tr style={{ background: "rgba(255,107,0,0.06)",
                           textAlign: "left",
                           fontFamily: "'JetBrains Mono', monospace",
                           fontSize: 10,
                           letterSpacing: "0.15em",
                           color: "#C9A84C",
                           textTransform: "uppercase" }}>
                <th style={{ padding: "12px 16px" }}>Email</th>
                <th style={{ padding: "12px 16px" }}>Name</th>
                <th style={{ padding: "12px 16px" }}>Plan</th>
                <th style={{ padding: "12px 16px" }}>Verified</th>
                <th style={{ padding: "12px 16px" }}>GitHub</th>
                <th style={{ padding: "12px 16px" }}>Tokens left</th>
                <th style={{ padding: "12px 16px" }}>Signed up</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r, i) => (
                <tr key={r.user_id || i}
                    data-testid="admin-dev-signup-row"
                    style={{ borderTop: i > 0
                               ? "1px solid rgba(255,255,255,0.04)"
                               : "none",
                             color: r.abuse_flagged
                               ? "#E5484D" : "#F0EDE8" }}>
                  <td style={{ padding: "10px 16px",
                               fontFamily: "'JetBrains Mono', monospace",
                               fontSize: 12 }}>
                    {r.email}
                    {r.abuse_flagged && (
                      <span style={{ marginLeft: 8, fontSize: 10,
                                      color: "#E5484D",
                                      letterSpacing: "0.15em" }}>
                        FLAGGED
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "10px 16px" }}>
                    {r.name || "—"}
                  </td>
                  <td style={{ padding: "10px 16px",
                               fontSize: 11,
                               color: r.plan === "internal_admin"
                                 ? "#C9A84C" : "#7A7590",
                               letterSpacing: "0.1em",
                               textTransform: "uppercase" }}>
                    {r.plan || "free"}
                  </td>
                  <td style={{ padding: "10px 16px" }}>
                    {r.email_verified
                      ? <span style={{ color: "#4CAF50" }}>✓</span>
                      : <span style={{ color: "#7A7590" }}>—</span>}
                  </td>
                  <td style={{ padding: "10px 16px",
                               fontFamily: "'JetBrains Mono', monospace",
                               fontSize: 12,
                               color: r.github_username
                                 ? "#F0EDE8" : "#7A7590" }}>
                    {r.github_username ? `@${r.github_username}` : "—"}
                  </td>
                  <td style={{ padding: "10px 16px",
                               fontFamily: "'JetBrains Mono', monospace",
                               fontSize: 12 }}>
                    {Number(r.tokens_remaining ?? 0).toLocaleString()}
                  </td>
                  <td style={{ padding: "10px 16px",
                               fontSize: 12, color: "#7A7590" }}>
                    {(r.created_at || "").slice(0, 10) || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Tile({ testid, label, value, tone }) {
  const color = tone === "red"   ? "#E5484D"
              : tone === "muted" ? "#7A7590"
              :                    "#F0EDE8";
  return (
    <div data-testid={testid}
         style={{ background: "#0F0F1A",
                  border: "1px solid rgba(255,107,0,0.10)",
                  borderRadius: 6, padding: "14px 22px",
                  minWidth: 140 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 10, letterSpacing: "0.15em",
                    color: "#7A7590", textTransform: "uppercase",
                    marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 600, color }}>
        {Number(value || 0).toLocaleString()}
      </div>
    </div>
  );
}
