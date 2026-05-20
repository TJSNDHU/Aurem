/**
 * PendingCodeFixesPanel.jsx — iter 285 Auto-Heal Bridge UI
 * ═════════════════════════════════════════════════════════════════════
 *
 * Lists staged Tier-3 code fixes from `pending_code_fixes`. Operator can
 * Approve (marks status=approved_for_deploy + surfaces [auto-heal] commit
 * message for one-click paste into Emergent Save-to-GitHub) or Reject.
 *
 * The [auto-heal] commit prefix triggers `.github/workflows/deploy-reminder.yml`
 * which fires the Emergent deploy webhook if configured.
 *
 * Mounted on /admin/pillars-map below AutonomousRepairPanel.
 */
import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, XCircle, Copy, RefreshCw, AlertTriangle, Clock } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STATUS_COLOR = {
  needs_human_review: "#F59E0B",
  approved_for_deploy: "#22C55E",
  rejected: "#6B7280",
};

const STATUS_LABEL = {
  needs_human_review: "PENDING REVIEW",
  approved_for_deploy: "APPROVED · DEPLOY",
  rejected: "REJECTED",
};

export default function PendingCodeFixesPanel() {
  const [fixes, setFixes] = useState([]);
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [toast, setToast] = useState("");

  const token = (typeof window !== "undefined" && localStorage.getItem("token")) || "";

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [fr, sr] = await Promise.all([
        fetch(`${API}/api/admin/autonomous-repair/pending-fixes?limit=50`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${API}/api/admin/autonomous-repair/pending-fixes/stats`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);
      if (fr.ok) {
        const jf = await fr.json();
        setFixes(jf.fixes || []);
      }
      if (sr.ok) setStats(await sr.json());
      setErr("");
    } catch (e) {
      setErr(String(e).slice(0, 200));
    }
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  const act = async (fixId, action) => {
    if (!token) return;
    setBusy(true);
    try {
      const r = await fetch(
        `${API}/api/admin/autonomous-repair/pending-fixes/${fixId}/${action}`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` } },
      );
      if (r.ok) {
        const j = await r.json();
        if (action === "approve" && j.commit_message) {
          try {
            await navigator.clipboard.writeText(j.commit_message);
            setToast(`Commit message copied to clipboard · paste into Save-to-GitHub`);
          } catch {
            setToast(`Approved · commit: ${j.commit_message.slice(0, 60)}…`);
          }
          setTimeout(() => setToast(""), 5000);
        }
        await load();
      } else {
        setErr(`${action} failed: HTTP ${r.status}`);
      }
    } catch (e) {
      setErr(String(e).slice(0, 200));
    } finally {
      setBusy(false);
    }
  };

  const copyCommit = async (msg) => {
    try {
      await navigator.clipboard.writeText(msg);
      setToast("Commit message copied");
      setTimeout(() => setToast(""), 2500);
    } catch {}
  };

  const pending = stats?.needs_human_review ?? 0;
  const approved = stats?.approved_for_deploy ?? 0;
  const rejected = stats?.rejected ?? 0;

  return (
    <div
      data-testid="pending-code-fixes-panel"
      style={{
        padding: 22,
        borderRadius: 16,
        background: "rgba(15,18,28,0.55)",
        border: "1px solid rgba(212,175,55,0.14)",
        backdropFilter: "blur(22px) saturate(140%)",
        marginBottom: 18,
        color: "#F4F4F4",
        fontFamily: "'Jost',sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle size={16} style={{ color: "#F59E0B" }} />
            <h3 style={{ fontFamily: "'Cinzel',serif", fontSize: 18, margin: 0, letterSpacing: "0.03em" }}>
              Auto-Heal Bridge · Pending Code Fixes
            </h3>
          </div>
          <p style={{ fontSize: 11, color: "#8A8070", margin: "4px 0 0 24px" }}>
            Tier-3 staged fixes awaiting human approval. Approve → [auto-heal] commit → deploy bridge.
          </p>
        </div>
        <button
          data-testid="pending-fixes-refresh"
          onClick={load}
          disabled={busy}
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "8px 14px", borderRadius: 10,
            background: "rgba(212,175,55,0.12)",
            border: "1px solid rgba(212,175,55,0.35)",
            color: "#D4AF37", fontSize: 11, fontWeight: 700,
            cursor: busy ? "not-allowed" : "pointer",
            letterSpacing: "0.08em", textTransform: "uppercase",
          }}
        >
          <RefreshCw size={12} className={busy ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Stats strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 10, marginBottom: 14 }}>
        <StatPill label="Pending Review" value={pending} color="#F59E0B" testid="fixes-pending" />
        <StatPill label="Approved · Deploy" value={approved} color="#22C55E" testid="fixes-approved" />
        <StatPill label="Rejected" value={rejected} color="#6B7280" testid="fixes-rejected" />
      </div>

      {err && (
        <div style={{ padding: 10, borderRadius: 8, background: "rgba(239,68,68,0.14)", border: "1px solid rgba(239,68,68,0.3)", color: "#FCA5A5", fontSize: 12, marginBottom: 10 }}>
          {err}
        </div>
      )}
      {toast && (
        <div data-testid="fixes-toast" style={{ padding: 10, borderRadius: 8, background: "rgba(34,197,94,0.14)", border: "1px solid rgba(34,197,94,0.3)", color: "#86EFAC", fontSize: 12, marginBottom: 10 }}>
          {toast}
        </div>
      )}

      {/* Fix list */}
      {fixes.length === 0 ? (
        <div data-testid="fixes-empty" style={{ padding: 20, textAlign: "center", color: "#8A8070", fontSize: 12, border: "1px dashed rgba(212,175,55,0.14)", borderRadius: 10 }}>
          Koi pending code fix nahi hai, Autonomous Repair Engine idle hai ya Tier 1/2 fixes se sab ho gaya.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 420, overflowY: "auto" }}>
          {fixes.map((f) => (
            <FixCard key={f.id} fix={f} onAct={act} onCopy={copyCommit} busy={busy} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatPill({ label, value, color, testid }) {
  return (
    <div
      data-testid={testid}
      style={{
        padding: 12, borderRadius: 10,
        background: "rgba(255,255,255,0.03)",
        border: `1px solid ${color}33`,
      }}
    >
      <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "#8A8070" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color, marginTop: 4, fontFamily: "'Jost',sans-serif" }}>{value}</div>
    </div>
  );
}

function FixCard({ fix, onAct, onCopy, busy }) {
  const statusColor = STATUS_COLOR[fix.status] || "#8A8070";
  const statusLabel = STATUS_LABEL[fix.status] || fix.status?.toUpperCase();
  const isPending = fix.status === "needs_human_review";
  const isApproved = fix.status === "approved_for_deploy";

  return (
    <div
      data-testid={`fix-card-${fix.id}`}
      style={{
        padding: 14,
        borderRadius: 10,
        background: "rgba(10,12,20,0.6)",
        border: `1px solid ${statusColor}33`,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 250 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{
              fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
              padding: "3px 8px", borderRadius: 4,
              background: `${statusColor}22`, color: statusColor, border: `1px solid ${statusColor}55`,
            }}>{statusLabel}</span>
            <span style={{ fontSize: 11, color: "#D4AF37", fontFamily: "monospace" }}>
              {fix.classification}
            </span>
            <span style={{ fontSize: 10, color: "#8A8070", display: "inline-flex", alignItems: "center", gap: 3 }}>
              <Clock size={10} /> {fix.occurrences_1h}× in 1h
            </span>
          </div>
          <div style={{ fontSize: 11, color: "#C8C8C8", fontFamily: "monospace", marginBottom: 6, wordBreak: "break-word" }}>
            {(fix.sample_message || "(no sample)").slice(0, 200)}
          </div>
          {fix.url && (
            <div style={{ fontSize: 10, color: "#8A8070", fontFamily: "monospace", marginBottom: 6 }}>
              url: {fix.url.slice(0, 80)}
            </div>
          )}
          {fix.commit_message && (
            <div
              onClick={() => onCopy(fix.commit_message)}
              title="Click to copy"
              data-testid={`fix-commit-${fix.id}`}
              style={{
                fontSize: 11, color: "#86EFAC", fontFamily: "monospace",
                padding: "6px 10px", borderRadius: 6,
                background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)",
                cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
                wordBreak: "break-word",
              }}
            >
              <Copy size={11} /> {fix.commit_message}
            </div>
          )}
          <div style={{ fontSize: 10, color: "#6B7280", marginTop: 6 }}>
            id: {fix.id} · staged: {fix.staged_at?.slice(0, 19)?.replace("T", " ")}
            {fix.approved_by && <> · approved by {fix.approved_by}</>}
            {fix.rejected_by && <> · rejected by {fix.rejected_by}</>}
          </div>
        </div>

        {isPending && (
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            <button
              data-testid={`fix-approve-${fix.id}`}
              onClick={() => onAct(fix.id, "approve")}
              disabled={busy}
              style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                padding: "7px 12px", borderRadius: 8,
                background: "rgba(34,197,94,0.15)", border: "1px solid rgba(34,197,94,0.4)",
                color: "#22C55E", fontSize: 11, fontWeight: 700,
                cursor: busy ? "not-allowed" : "pointer",
                letterSpacing: "0.06em", textTransform: "uppercase",
              }}
            >
              <CheckCircle2 size={12} /> Approve
            </button>
            <button
              data-testid={`fix-reject-${fix.id}`}
              onClick={() => onAct(fix.id, "reject")}
              disabled={busy}
              style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                padding: "7px 12px", borderRadius: 8,
                background: "rgba(239,68,68,0.10)", border: "1px solid rgba(239,68,68,0.35)",
                color: "#FCA5A5", fontSize: 11, fontWeight: 700,
                cursor: busy ? "not-allowed" : "pointer",
                letterSpacing: "0.06em", textTransform: "uppercase",
              }}
            >
              <XCircle size={12} /> Reject
            </button>
          </div>
        )}

        {isApproved && (
          <div style={{ flexShrink: 0, fontSize: 11, color: "#86EFAC", display: "inline-flex", alignItems: "center", gap: 6 }}>
            <CheckCircle2 size={12} /> Ready for Save-to-GitHub
          </div>
        )}
      </div>
    </div>
  );
}
