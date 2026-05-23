/**
 * LessonSources.jsx — iter 327p+q frontend
 *
 * Founder-only admin surface showing what ORA reads on boot:
 *   • Tier-1 files (always injected, with sha256 + size + status)
 *   • Tier-2 keyword-gated rules (when each fires)
 *   • Recent journal snapshots (rollback / audit trail)
 *   • Manual "Snapshot now" button (re-reads disk + writes journal row
 *     if anything changed; iter 327q)
 *   • Latest nightly self-test row (iter 327q FIX 2)
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw, BookOpen, ShieldCheck, History, Sparkles,
  CheckCircle, XCircle, Clock,
} from "lucide-react";

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const PANEL_BG = "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))";
const OK_GREEN = "#22c55e";
const ERR_RED = "#ef4444";

function readToken() {
  try {
    return (
      sessionStorage.getItem("platform_token") ||
      localStorage.getItem("platform_token") ||
      localStorage.getItem("aurem_admin_token") ||
      sessionStorage.getItem("aurem_admin_token") ||
      localStorage.getItem("token") ||
      ""
    );
  } catch { return ""; }
}

async function apiCall(path, opts = {}) {
  const url = `${process.env.REACT_APP_BACKEND_URL || ""}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(opts.headers || {}),
  };
  const tok = readToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const r = await fetch(url, { ...opts, headers });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`HTTP ${r.status}: ${text.slice(0, 200)}`);
  }
  return r.json();
}

export default function LessonSources() {
  const [sources, setSources] = useState(null);
  const [journal, setJournal] = useState([]);
  const [selfTests, setSelfTests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snapBusy, setSnapBusy] = useState(false);
  const [snapMsg, setSnapMsg] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, j, n] = await Promise.all([
        apiCall("/api/admin/ora/lesson-sources"),
        apiCall("/api/admin/ora/lesson-journal?limit=15"),
        apiCall("/api/admin/ora/nightly-self-tests?limit=7").catch(() => ({ entries: [] })),
      ]);
      setSources(s);
      setJournal(j.entries || []);
      setSelfTests(n.entries || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function snapshotNow() {
    setSnapBusy(true);
    setSnapMsg(null);
    try {
      const r = await apiCall("/api/admin/ora/lesson-snapshot", { method: "POST" });
      if (r.changed) {
        setSnapMsg(`New snapshot written — ${(r.changed_paths || []).length} file(s) changed.`);
      } else {
        setSnapMsg("No changes detected — nothing to snapshot.");
      }
      await load();
    } catch (e) {
      setSnapMsg(`Snapshot failed: ${e.message || e}`);
    } finally {
      setSnapBusy(false);
      setTimeout(() => setSnapMsg(null), 6000);
    }
  }

  return (
    <div
      data-testid="lesson-sources-page"
      style={{ padding: "24px 28px", color: TEXT, maxWidth: 1100 }}
    >
      <header style={{
        display: "flex", alignItems: "center", gap: 12, marginBottom: 20,
        flexWrap: "wrap",
      }}>
        <BookOpen size={20} color={GOLD} />
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>
          ORA Memory Sources
        </h1>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          Tier-1 always-on · Tier-2 keyword-gated · audit journal
        </span>
        <div style={{ flex: 1 }} />
        <button
          data-testid="lesson-sources-refresh"
          onClick={load}
          style={iconBtn}
          title="Refresh"
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} />
        </button>
        <button
          data-testid="lesson-sources-snapshot"
          onClick={snapshotNow}
          disabled={snapBusy}
          style={primaryBtn(snapBusy)}
          title="Force a tier-1 snapshot (re-reads disk, records diff)"
        >
          {snapBusy ? "Snapshotting…" : "Snapshot now"}
        </button>
      </header>

      {snapMsg && (
        <div
          data-testid="lesson-sources-snapshot-msg"
          style={{
            marginBottom: 16, padding: "10px 14px", borderRadius: 8,
            background: "rgba(212,175,55,0.10)", border: `1px solid ${BORDER}`,
            color: TEXT, fontSize: 13,
          }}
        >
          {snapMsg}
        </div>
      )}

      {error && (
        <div
          data-testid="lesson-sources-error"
          style={{
            padding: "12px 14px", borderRadius: 8,
            background: "rgba(239,68,68,0.10)", border: `1px solid ${ERR_RED}`,
            color: TEXT, fontSize: 13, marginBottom: 16,
          }}
        >
          {error}
        </div>
      )}

      {loading && !sources ? (
        <div style={{ color: TEXT_DIM, fontSize: 13 }}>Loading…</div>
      ) : sources ? (
        <>
          <Tier1Panel sources={sources} />
          <Tier2Panel rules={sources?.tier2?.rules || []} />
          <JournalPanel entries={journal} />
          <NightlyPanel entries={selfTests} />
        </>
      ) : null}

      <style>{`.spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}
      </style>
    </div>
  );
}

function Tier1Panel({ sources }) {
  const files = sources?.tier1?.files || [];
  const total = sources?.tier1?.total_chars || 0;
  const capTotal = sources?.tier1?.cap_total || 8000;
  const pct = Math.min(100, Math.round((total / capTotal) * 100));

  return (
    <section data-testid="tier1-panel" style={card}>
      <div style={cardHeader}>
        <ShieldCheck size={16} color={GOLD} />
        <span style={cardTitle}>Tier 1 — Always Injected</span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          {total.toLocaleString()} / {capTotal.toLocaleString()} chars ({pct}%)
        </span>
      </div>
      <div style={{
        height: 6, background: "rgba(255,255,255,0.04)", borderRadius: 999,
        marginBottom: 12, overflow: "hidden",
      }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: pct > 95 ? ERR_RED : pct > 80 ? GOLD : OK_GREEN,
          transition: "width 220ms ease",
        }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {files.map((f, i) => (
          <div
            key={f.path || i}
            data-testid={`tier1-file-${i}`}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 12px", borderRadius: 8,
              background: f.loaded ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
              border: `1px solid ${f.loaded ? "rgba(34,197,94,0.30)" : "rgba(239,68,68,0.30)"}`,
              fontSize: 13,
            }}
          >
            {f.loaded
              ? <CheckCircle size={14} color={OK_GREEN} />
              : <XCircle size={14} color={ERR_RED} />}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600 }}>{f.label}</div>
              <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 2, wordBreak: "break-all" }}>
                {f.path}
              </div>
            </div>
            <div style={{ textAlign: "right", color: TEXT_DIM, fontSize: 11 }}>
              <div>{(f.size || 0).toLocaleString()} chars</div>
              {f.sha256 && (
                <div title={f.sha256} style={{ fontFamily: "monospace" }}>
                  {f.sha256.slice(0, 10)}…
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Tier2Panel({ rules }) {
  return (
    <section data-testid="tier2-panel" style={card}>
      <div style={cardHeader}>
        <Sparkles size={16} color={GOLD} />
        <span style={cardTitle}>Tier 2 — Keyword-Gated</span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          {rules.length} rule(s)
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {rules.map((r, i) => (
          <div
            key={`${r.path}-${i}`}
            data-testid={`tier2-rule-${i}`}
            style={{
              padding: "10px 12px", borderRadius: 8,
              background: "rgba(255,255,255,0.02)",
              border: `1px solid ${BORDER}`, fontSize: 13,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {r.exists
                ? <CheckCircle size={12} color={OK_GREEN} />
                : <XCircle size={12} color={ERR_RED} />}
              <span style={{ fontWeight: 600 }}>{r.label}</span>
              <span style={{ color: TEXT_DIM, fontSize: 11, marginLeft: "auto" }}>
                cap {(r.cap || 0).toLocaleString()}
              </span>
            </div>
            <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 4 }}>{r.path}</div>
            <div style={{ marginTop: 6, display: "flex", gap: 4, flexWrap: "wrap" }}>
              {(r.keywords || []).map((k) => (
                <span key={k} style={{
                  fontSize: 11, padding: "2px 6px", borderRadius: 4,
                  background: "rgba(212,175,55,0.10)", color: GOLD,
                }}>{k}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function JournalPanel({ entries }) {
  return (
    <section data-testid="journal-panel" style={card}>
      <div style={cardHeader}>
        <History size={16} color={GOLD} />
        <span style={cardTitle}>Learning Journal</span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          {entries.length} entr{entries.length === 1 ? "y" : "ies"}
        </span>
      </div>
      {entries.length === 0 ? (
        <div style={{ color: TEXT_DIM, fontSize: 13 }}>
          No journal entries yet — they appear when a tier-1 file changes
          or a lesson is approved.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {entries.map((e, i) => (
            <details
              key={i}
              data-testid={`journal-entry-${i}`}
              style={{
                padding: "10px 12px", borderRadius: 8,
                background: "rgba(255,255,255,0.02)",
                border: `1px solid ${BORDER}`, fontSize: 13,
              }}
            >
              <summary style={{ cursor: "pointer", display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{
                  fontSize: 11, padding: "2px 6px", borderRadius: 4,
                  background: "rgba(212,175,55,0.10)", color: GOLD, fontWeight: 600,
                }}>{e.kind || "snapshot"}</span>
                <span style={{ color: TEXT }}>{(e.ts || "").slice(0, 19).replace("T", " ")}</span>
                <span style={{ color: TEXT_DIM, fontSize: 11, marginLeft: "auto" }}>
                  {e.kind === "lesson_proposal_applied"
                    ? `+${(e.lesson_text || "").length} chars`
                    : `${(e.total_chars || 0).toLocaleString()} chars`}
                </span>
              </summary>
              <div style={{ marginTop: 8, color: TEXT_DIM, fontSize: 12 }}>
                {e.kind === "lesson_proposal_applied" ? (
                  <>
                    <div><strong style={{ color: TEXT }}>Mistake:</strong> {e.mistake_summary}</div>
                    <div style={{ marginTop: 4 }}><strong style={{ color: TEXT }}>Lesson:</strong> {e.lesson_text}</div>
                    {e.unified_diff && (
                      <pre style={{
                        marginTop: 8, padding: 10, background: "#0A0A12",
                        border: `1px solid ${BORDER}`, borderRadius: 6,
                        fontSize: 11, color: TEXT_DIM, overflow: "auto",
                        maxHeight: 200,
                      }}>{e.unified_diff}</pre>
                    )}
                  </>
                ) : (
                  <div>
                    {e.first_snapshot && (
                      <div style={{ color: GOLD, marginBottom: 4 }}>★ First-ever snapshot</div>
                    )}
                    <div>Changed paths: {(e.changed_paths || []).length}</div>
                    <div style={{ fontSize: 11, marginTop: 4 }}>
                      pod: {e.pod} · user: {e.process_user}
                    </div>
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}

function NightlyPanel({ entries }) {
  return (
    <section data-testid="nightly-panel" style={card}>
      <div style={cardHeader}>
        <Clock size={16} color={GOLD} />
        <span style={cardTitle}>Nightly Self-Tests</span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          02:00 UTC daily
        </span>
      </div>
      {entries.length === 0 ? (
        <div style={{ color: TEXT_DIM, fontSize: 13 }}>
          No nightly run yet. The first run will land at 02:00 UTC.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {entries.map((e, i) => {
            const allGreen = e.passed === e.total;
            return (
              <div
                key={i}
                data-testid={`nightly-row-${i}`}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 12px", borderRadius: 6,
                  background: allGreen ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
                  border: `1px solid ${allGreen ? "rgba(34,197,94,0.30)" : "rgba(239,68,68,0.30)"}`,
                  fontSize: 12,
                }}
              >
                {allGreen
                  ? <CheckCircle size={12} color={OK_GREEN} />
                  : <XCircle size={12} color={ERR_RED} />}
                <span style={{ color: TEXT }}>{(e.ts || "").slice(0, 16).replace("T", " ")}</span>
                <span style={{ color: TEXT_DIM, marginLeft: "auto" }}>
                  {e.passed} / {e.total} checks passed
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ── styles ────────────────────────────────────────────────────────────
const card = {
  marginBottom: 18, padding: 18, borderRadius: 12,
  background: PANEL_BG, border: `1px solid ${BORDER}`,
};
const cardHeader = {
  display: "flex", alignItems: "center", gap: 8, marginBottom: 12,
};
const cardTitle = { fontSize: 15, fontWeight: 600, color: TEXT };
const iconBtn = {
  width: 32, height: 32, display: "inline-flex", alignItems: "center",
  justifyContent: "center", background: "transparent",
  border: `1px solid ${BORDER}`, borderRadius: 6, color: TEXT_DIM,
  cursor: "pointer",
};
const primaryBtn = (busy) => ({
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "8px 14px", borderRadius: 8,
  background: busy ? "rgba(212,175,55,0.30)" : GOLD,
  color: "#0B0B16", border: "none",
  fontSize: 13, fontWeight: 600,
  cursor: busy ? "not-allowed" : "pointer",
  opacity: busy ? 0.7 : 1,
});
