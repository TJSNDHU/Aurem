/**
 * GitCommitGate — iter 322er
 * Founder approval UI for every ORA-proposed commit.
 *
 * Pending → click row → see full diff → Approve or Reject (with reason).
 * Approve runs the real `git commit` and records the SHA.
 * Reject marks the proposal; optional hard-reset undoes the file edits.
 *
 * Route: /admin/git-gate
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  GitBranch, CheckCircle, XCircle, RefreshCw, Loader2,
  AlertTriangle, FileCode, ChevronRight, RotateCcw,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 20000;

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const RED = "#FF7676";
const GREEN = "#67E8A0";
const AMBER = "#FFB36B";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function GitCommitGate() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("pending");
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    try {
      const headers = authHeaders();
      const [s, l] = await Promise.all([
        fetch(`${API}/api/admin/git-gate/summary`, { headers }).then(r => r.json()),
        fetch(`${API}/api/admin/git-gate/proposals?status=${tab}&limit=40`, { headers }).then(r => r.json()),
      ]);
      if (s?.ok) setSummary(s);
      if (l?.ok) setRows(l.rows || []);
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    }
  }, [tab]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const openProposal = async (id) => {
    setSelected(null);
    setDecisionNote("");
    try {
      const r = await fetch(`${API}/api/admin/git-gate/proposals/${id}`,
                             { headers: authHeaders() });
      const j = await r.json();
      if (j?.ok) setSelected(j.proposal);
      else setToast({ kind: "err", text: j?.detail || "load failed" });
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    }
  };

  const decide = async (action, opts = {}) => {
    if (!selected) return;
    if (action === "reject" && (!decisionNote || decisionNote.trim().length < 3)) {
      setToast({ kind: "err", text: "Reject requires a note (≥3 chars)" });
      return;
    }
    setBusy(true);
    setToast(null);
    try {
      const r = await fetch(
        `${API}/api/admin/git-gate/proposals/${selected.id}/${action}`,
        {
          method: "POST",
          headers: { ...authHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ note: decisionNote }),
        }
      );
      const j = await r.json();
      if (j?.ok) {
        setToast({
          kind: "ok",
          text: action === "approve"
            ? `✓ Committed — SHA ${(j.commit_sha || "?").slice(0, 12)}`
            : `✓ Rejected`,
        });
        setSelected(null);
        load();
        if (action === "reject" && opts.hardReset) {
          await fetch(
            `${API}/api/admin/git-gate/proposals/${selected.id}/hard-reset`,
            { method: "POST", headers: authHeaders() }
          );
        }
      } else {
        setToast({ kind: "err", text: j?.detail || "decision failed" });
      }
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="git-commit-gate" style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <GitBranch size={26} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }}>Git Commit Gate</h1>
          </div>
          <p style={{ color: TEXT_DIM, marginTop: 6, fontSize: 13 }}>
            Founder approval required for every ORA-proposed commit · zero auto-merge
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button data-testid="refresh-btn" onClick={load} style={btn(false)}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button data-testid="back-btn" onClick={() => navigate("/admin/ora-cto")} style={btn(false)}>← Back</button>
        </div>
      </div>

      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 18 }}>
          <Tile testid="kpi-pending" label="Pending review" value={summary.pending}
                accent={summary.pending > 0 ? "warn" : null} sub="awaiting decision" />
          <Tile testid="kpi-approved" label="Approved" value={summary.approved} sub="lifetime" />
          <Tile testid="kpi-rejected" label="Rejected" value={summary.rejected} sub="lifetime" />
          <Tile testid="kpi-approval-rate" label="Approval rate" value={`${summary.approval_rate ?? 0}%`}
                sub={`${summary.total} total proposals`} />
        </div>
      )}

      {toast && (
        <div data-testid="toast" style={{
          ...GLASS, padding: 12, marginBottom: 14,
          borderColor: toast.kind === "ok" ? GREEN : RED,
          color: toast.kind === "ok" ? GREEN : RED,
        }}>
          {toast.text}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {["pending", "approved", "rejected", "all"].map((t) => (
          <button data-testid={`tab-${t}`} key={t} onClick={() => { setTab(t); setSelected(null); }}
                  style={btn(tab === t)}>
            {t}
            {tab === t && summary && t !== "all" && ` (${summary[t]})`}
          </button>
        ))}
      </div>

      {/* Body: 2-pane */}
      <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 14 }}>
        {/* Left — list */}
        <div style={{ ...GLASS, padding: 14, maxHeight: 700, overflow: "auto" }}>
          {rows.length === 0 ? (
            <div style={{ color: TEXT_DIM, fontSize: 13, padding: 8 }}>
              {tab === "pending"
                ? "✓ No commits waiting for review."
                : `No ${tab} proposals yet.`}
            </div>
          ) : rows.map((r) => (
            <div data-testid={`prop-row-${r.id}`} key={r.id}
                 onClick={() => openProposal(r.id)}
                 style={{
                   padding: 12, marginBottom: 8, cursor: "pointer",
                   border: `1px solid ${BORDER}`, borderRadius: 10,
                   background: selected?.id === r.id ? "rgba(212,175,55,0.08)" : "rgba(0,0,0,0.28)",
                 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{r.title}</span>
                <StatusPill status={r.status} />
              </div>
              <div style={{ color: TEXT_DIM, fontSize: 11, display: "flex", gap: 10 }}>
                <span>{r.files?.length || 0} files</span>
                <span style={{ color: GREEN }}>+{r.lines_added}</span>
                <span style={{ color: RED }}>−{r.lines_removed}</span>
                <span style={{ marginLeft: "auto" }}>{(r.proposed_at || "").slice(0, 19)}</span>
              </div>
              {r.commit_sha && (
                <div style={{ color: GREEN, fontSize: 11, marginTop: 4, fontFamily: "ui-monospace,monospace" }}>
                  ✓ {r.commit_sha.slice(0, 14)}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Right — diff + decide */}
        <div style={{ ...GLASS, padding: 18, maxHeight: 700, overflow: "auto" }}>
          {!selected ? (
            <div style={{ color: TEXT_DIM, fontSize: 13, padding: 14 }}>
              <ChevronRight size={14} style={{ verticalAlign: "middle" }} /> Pick a proposal to review.
            </div>
          ) : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{selected.title}</div>
                  <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 4 }}>
                    Proposed {(selected.proposed_at || "").slice(0, 19)} by {selected.proposed_by} · {selected.files?.length || 0} files
                  </div>
                </div>
                <StatusPill status={selected.status} />
              </div>

              {selected.body && (
                <div style={{ fontSize: 13, color: TEXT_DIM, padding: "8px 0",
                              borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`, margin: "8px 0" }}>
                  {selected.body}
                </div>
              )}
              <div style={{ fontSize: 12.5, marginBottom: 10 }}>
                <strong style={{ color: AMBER }}>ORA rationale: </strong>
                <span style={{ color: TEXT_DIM }}>{selected.rationale}</span>
              </div>

              {/* Files + numstat */}
              <div style={{ marginBottom: 10 }}>
                <SectionTitle icon={FileCode} text="Files" />
                {(selected.per_file_stat || []).map((f, i) => (
                  <div data-testid={`file-stat-${i}`} key={f.path}
                       style={{ display: "grid", gridTemplateColumns: "1fr 60px 60px",
                                gap: 8, padding: "4px 0", fontSize: 12 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.path}</div>
                    <div style={{ color: GREEN }}>+{f.added}</div>
                    <div style={{ color: RED }}>−{f.removed}</div>
                  </div>
                ))}
              </div>

              {/* Diff */}
              <div style={{ background: "rgba(0,0,0,0.55)", border: `1px solid ${BORDER}`,
                            borderRadius: 8, padding: 12, marginBottom: 14 }}>
                <pre style={{
                  margin: 0, fontSize: 11.5, whiteSpace: "pre",
                  fontFamily: "ui-monospace,monospace", color: TEXT,
                  maxHeight: 320, overflow: "auto",
                }}>
                  {colorizeDiff(selected.diff || "(no diff available)")}
                </pre>
                {selected.diff_truncated && (
                  <div style={{ color: AMBER, fontSize: 11, marginTop: 8 }}>
                    ⚠ Diff truncated at 200KB. Full diff in `git diff HEAD` against the files listed above.
                  </div>
                )}
              </div>

              {selected.status === "pending" && (
                <>
                  <textarea data-testid="decision-note" value={decisionNote}
                            onChange={(e) => setDecisionNote(e.target.value)}
                            placeholder="Optional approval note · required for rejection"
                            style={{
                              width: "100%", minHeight: 60,
                              background: "rgba(0,0,0,0.4)", color: TEXT,
                              border: `1px solid ${BORDER}`, borderRadius: 8,
                              padding: 10, fontSize: 13, marginBottom: 10,
                            }} />
                  <div style={{ display: "flex", gap: 10 }}>
                    <button data-testid="approve-btn" disabled={busy} onClick={() => decide("approve")}
                            style={primaryBtn(GREEN, busy)}>
                      {busy ? <Loader2 size={14} className="spin" /> : <CheckCircle size={14} />} Approve & Commit
                    </button>
                    <button data-testid="reject-btn" disabled={busy} onClick={() => decide("reject")}
                            style={primaryBtn(RED, busy)}>
                      <XCircle size={14} /> Reject
                    </button>
                    <button data-testid="reject-hard-btn" disabled={busy}
                            onClick={() => decide("reject", { hardReset: true })}
                            style={primaryBtn(AMBER, busy)}>
                      <RotateCcw size={14} /> Reject + revert files
                    </button>
                  </div>
                </>
              )}

              {selected.status !== "pending" && (
                <div style={{ ...GLASS, padding: 12, marginTop: 10 }}>
                  <div style={{ display: "flex", gap: 16, fontSize: 12 }}>
                    <div>
                      <span style={{ color: TEXT_DIM }}>Decided by: </span>
                      <strong>{selected.decided_by}</strong>
                    </div>
                    <div>
                      <span style={{ color: TEXT_DIM }}>At: </span>
                      {(selected.decided_at || "").slice(0, 19)}
                    </div>
                    {selected.commit_sha && (
                      <div>
                        <span style={{ color: TEXT_DIM }}>SHA: </span>
                        <code style={{ color: GREEN }}>{selected.commit_sha.slice(0, 14)}</code>
                      </div>
                    )}
                  </div>
                  {selected.decision_note && (
                    <div style={{ marginTop: 8, fontSize: 12.5 }}>
                      <span style={{ color: TEXT_DIM }}>Note: </span>
                      {selected.decision_note}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function colorizeDiff(diff) {
  // Cheap line-prefix colorizer rendered as React fragments
  return diff.split("\n").map((line, i) => {
    let color = TEXT;
    if (line.startsWith("+++") || line.startsWith("---")) color = AMBER;
    else if (line.startsWith("+")) color = GREEN;
    else if (line.startsWith("-")) color = RED;
    else if (line.startsWith("@@")) color = "#7ED7FF";
    else if (line.startsWith("diff --git")) color = GOLD;
    return <span key={i} style={{ color }}>{line}{"\n"}</span>;
  });
}

function StatusPill({ status }) {
  const map = {
    pending:  { bg: "rgba(255,179,107,0.18)", color: AMBER, label: "PENDING" },
    approved: { bg: "rgba(103,232,160,0.18)", color: GREEN, label: "APPROVED" },
    rejected: { bg: "rgba(255,118,118,0.18)", color: RED,   label: "REJECTED" },
  };
  const m = map[status] || { bg: "rgba(255,255,255,0.06)", color: TEXT_DIM, label: status };
  return (
    <span style={{
      background: m.bg, color: m.color, padding: "2px 8px",
      borderRadius: 6, fontSize: 10, fontWeight: 700, letterSpacing: 0.3,
    }}>
      {m.label}
    </span>
  );
}

function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "6px 12px", fontSize: 12.5,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    textTransform: "uppercase",
    opacity: disabled ? 0.5 : 1,
  };
}

function primaryBtn(color, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: color, color: "#0A0A12",
    border: `1px solid ${color}`,
    borderRadius: 8, padding: "8px 16px", fontSize: 13,
    fontWeight: 700, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}

function Tile({ testid, label, value, sub, accent }) {
  return (
    <div data-testid={testid} style={{ ...GLASS, padding: 14 }}>
      <div style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6,
                    color: accent === "warn" ? AMBER : TEXT }}>{value}</div>
      <div style={{ color: TEXT_DIM, fontSize: 11 }}>{sub}</div>
    </div>
  );
}

function SectionTitle({ icon: Icon, text }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
      <Icon size={13} color={GOLD} />
      <span style={{ fontWeight: 600, fontSize: 12, color: TEXT }}>{text}</span>
    </div>
  );
}
