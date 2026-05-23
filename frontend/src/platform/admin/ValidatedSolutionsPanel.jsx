/**
 * ValidatedSolutionsPanel — iter 332a-2
 * "What ORA taught itself this week" — plain English list of the
 * cached fix patterns ORA has learned. Pulls from
 * GET /api/admin/ora/validated-solutions?limit=20. Refreshed on mount.
 */
import React, { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const TEXT     = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER   = "rgba(212,175,55,0.18)";
const GREEN    = "#67E8A0";
const GOLD     = "#E8C86A";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55)",
  padding: 18,
};

function authHeaders() {
  const tok =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("admin_token") ||
    localStorage.getItem("token") ||
    "";
  return tok ? { Authorization: `Bearer ${tok}` } : {};
}

function shortDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined,
                                  { month: "short", day: "numeric" });
  } catch { return iso.slice(0, 10); }
}

export default function ValidatedSolutionsPanel() {
  const [rows, setRows] = useState([]);
  const [err, setErr]   = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await fetch(`${API}/api/admin/ora/validated-solutions?limit=20`,
                               { headers: authHeaders() });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (!cancelled) {
          setRows(j.rows || []);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div data-testid="validated-solutions-panel" style={GLASS}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                     marginBottom: 14 }}>
        <BookOpen size={14} style={{ color: GOLD }} />
        <span style={{ fontSize: 14, fontWeight: 600, color: TEXT }}>
          What ORA taught itself
        </span>
        <span style={{ color: TEXT_DIM, fontSize: 11,
                        marginLeft: "auto" }}>
          {rows.length} pattern{rows.length === 1 ? "" : "s"}
        </span>
      </div>

      {err && (
        <div data-testid="validated-panel-error"
              style={{ color: "#FF6060", fontSize: 12, marginBottom: 8 }}>
          {err}
        </div>
      )}

      {loaded && rows.length === 0 && !err && (
        <p data-testid="validated-panel-empty"
            style={{ fontSize: 12, color: TEXT_DIM,
                      fontStyle: "italic" }}>
          No validated solutions yet. ORA will start learning the
          first time it solves the same problem twice.
        </p>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0,
                   display: "grid", gap: 10 }}>
        {rows.map((r) => (
          <li key={r.signature}
              data-testid="validated-solution-row"
              style={{
                padding: "10px 12px",
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.04)",
                borderRadius: 10,
              }}>
            <div style={{ display: "flex", alignItems: "center",
                            gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 10, letterSpacing: "0.18em",
                              textTransform: "uppercase",
                              color: GOLD,
                              fontFamily: "'JetBrains Mono', monospace" }}>
                {r.task_type}
              </span>
              <span style={{ color: TEXT_DIM, fontSize: 11 }}>
                · used {r.use_count || 0}×
              </span>
              <span style={{ marginLeft: "auto",
                              color: GREEN, fontSize: 11 }}>
                {shortDate(r.last_used_at || r.last_updated_at)}
              </span>
            </div>
            <p style={{ fontSize: 13, color: TEXT, lineHeight: 1.55,
                          margin: 0 }}>
              {r.fix_suggestion || "(no fix recorded)"}
            </p>
            {Array.isArray(r.findings) && r.findings.length > 0 && (
              <p style={{ fontSize: 11, color: TEXT_DIM,
                            marginTop: 4, fontStyle: "italic" }}>
                — {r.findings[0]}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
