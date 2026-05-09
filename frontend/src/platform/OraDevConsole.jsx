/* eslint-disable react-hooks/exhaustive-deps */
/**
 * ORA Dev Console (iter 281.2 — Phase 2.2)
 * ==========================================
 * Admin-only review queue for ORA's Mode 2 (Software Engineer)
 * code-change proposals. ORA never auto-applies — it queues
 * proposals here for manual approve/reject/applied/rollback.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Loader2,
  Check,
  X,
  RotateCcw,
  PlayCircle,
  ShieldAlert,
  CircleDot,
  Code2,
  RefreshCw,
  GitBranch,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STATUS_STYLE = {
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  approved: "bg-blue-500/15 text-blue-300 border-blue-500/40",
  rejected: "bg-rose-500/15 text-rose-300 border-rose-500/40",
  applied: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  rolled_back: "bg-zinc-500/15 text-zinc-300 border-zinc-500/40",
};

function readToken() {
  try {
    return (
      sessionStorage.getItem("platform_token") ||
      localStorage.getItem("platform_token") ||
      localStorage.getItem("aurem_admin_token") ||
      sessionStorage.getItem("aurem_admin_token") ||
      localStorage.getItem("admin_token") ||
      sessionStorage.getItem("admin_token") ||
      localStorage.getItem("token") ||
      ""
    );
  } catch (_) {
    return "";
  }
}

function authHeaders() {
  const t = readToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function fmtTs(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch (_) {
    return iso;
  }
}

const StatusFilter = ({ value, onChange }) => {
  const opts = ["all", "pending", "approved", "rejected", "applied", "rolled_back"];
  return (
    <div className="flex gap-2 flex-wrap" data-testid="ora-dev-filter-row">
      {opts.map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          data-testid={`ora-dev-filter-${s}`}
          className={`text-[11px] px-3 py-1 rounded-full border tracking-wide uppercase transition ${
            value === s
              ? "bg-amber-500 text-black border-amber-400"
              : "bg-zinc-900 text-zinc-300 border-zinc-700 hover:border-zinc-500"
          }`}
        >
          {s.replace("_", " ")}
        </button>
      ))}
    </div>
  );
};

const StatPill = ({ label, value, tone = "default", testid }) => {
  const toneCls =
    tone === "warn"
      ? "border-amber-500/40 text-amber-300"
      : tone === "good"
      ? "border-emerald-500/40 text-emerald-300"
      : tone === "bad"
      ? "border-rose-500/40 text-rose-300"
      : "border-zinc-700 text-zinc-200";
  return (
    <div
      data-testid={testid}
      className={`rounded-lg border px-3 py-2 bg-zinc-950/60 ${toneCls}`}
    >
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  );
};

// ── iter 322t — Safety badge palette
const SAFETY_STYLE = {
  LOW: {
    cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    label: "🔒 LOW RISK",
    desc: "config / cache / rate-limit only",
  },
  MEDIUM: {
    cls: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    label: "⚠️ MEDIUM RISK",
    desc: "new feature or new route",
  },
  HIGH: {
    cls: "bg-rose-500/15 text-rose-300 border-rose-500/40",
    label: "🚨 HIGH RISK",
    desc: "database / billing / auth",
  },
};

const PlainBlock = ({ icon, label, body, tone = "default" }) => {
  const toneCls = tone === "bad"
    ? "border-rose-700/40 bg-rose-950/30"
    : tone === "good"
    ? "border-emerald-700/40 bg-emerald-950/30"
    : tone === "warn"
    ? "border-amber-700/40 bg-amber-950/30"
    : "border-zinc-800 bg-zinc-950/50";
  return (
    <div className={`rounded-lg border ${toneCls} p-3`}>
      <div className="text-[11px] uppercase tracking-wider text-zinc-400 mb-1 flex items-center gap-1">
        <span>{icon}</span><span>{label}</span>
      </div>
      <div className="text-[13px] text-zinc-100 leading-relaxed">
        {body || "—"}
      </div>
    </div>
  );
};

const ProposalCard = ({ p, onAct, busyId, onTranslate }) => {
  const id = p.proposal_id;
  const short = id ? id.slice(0, 8) : "??";
  const statusKey = (p.status || "pending").toLowerCase();
  const sealed = !!p.sealed_blocked;
  const busy = busyId === id;
  const [showDetails, setShowDetails] = React.useState(false);
  const [translating, setTranslating] = React.useState(false);

  const plain = p.plain_language || null;
  const safety = (p.safety_level || "MEDIUM").toUpperCase();
  const safetyStyle = SAFETY_STYLE[safety] || SAFETY_STYLE.MEDIUM;
  const tier = p.tier || "tier_2";
  const autoExecAt = p.auto_execute_at;

  const handleTranslate = async () => {
    if (translating) return;
    setTranslating(true);
    try {
      await onTranslate(id);
    } finally {
      setTranslating(false);
    }
  };

  return (
    <div
      data-testid={`ora-dev-card-${short}`}
      className={`rounded-xl border bg-zinc-950/70 p-4 mb-3 ${
        sealed ? "border-rose-700/60" : "border-zinc-800"
      }`}
    >
      {/* Header row: id, status, safety, tier, sealed */}
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <Code2 className="w-4 h-4 text-amber-400" />
          <span className="font-mono text-sm text-amber-300">#{short}</span>
          <span
            data-testid={`ora-dev-card-${short}-status`}
            className={`text-[10px] uppercase px-2 py-0.5 rounded border ${
              STATUS_STYLE[statusKey] || STATUS_STYLE.pending
            }`}
          >
            {statusKey.replace("_", " ")}
          </span>
          <span
            data-testid={`ora-dev-card-${short}-safety`}
            className={`text-[10px] uppercase px-2 py-0.5 rounded border ${safetyStyle.cls}`}
            title={safetyStyle.desc}
          >
            {safetyStyle.label}
          </span>
          {tier === "tier_1" && statusKey === "pending" && autoExecAt && (
            <span
              data-testid={`ora-dev-card-${short}-tier1-auto`}
              className="text-[10px] uppercase px-2 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-200"
              title={`Will auto-execute at ${autoExecAt}`}
            >
              ⏱ AUTO @ {new Date(autoExecAt).toLocaleTimeString()}
            </span>
          )}
          {sealed && (
            <span className="text-[10px] uppercase px-2 py-0.5 rounded border border-rose-500/50 bg-rose-500/10 text-rose-300 flex items-center gap-1">
              <ShieldAlert className="w-3 h-3" /> sealed-blocked
            </span>
          )}
        </div>
        <div className="text-[11px] text-zinc-500">
          {fmtTs(p.created_at)} · {p.user || "admin"}
        </div>
      </div>

      {/* Plain-Hinglish founder view (default visible) */}
      {plain ? (
        <div
          data-testid={`ora-dev-card-${short}-plain`}
          className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2"
        >
          <PlainBlock icon="🔴" label="Issue Found"        body={plain.problem_found}      tone="bad" />
          <PlainBlock icon="🔧" label="What Will Change"   body={plain.what_will_change}   tone="good" />
          <PlainBlock icon="⚡" label="Impact If Approved" body={plain.impact_if_approved} tone="good" />
          <PlainBlock icon="⚠️" label="Risk If Rejected"   body={plain.risk_if_rejected}   tone="warn" />
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
            Plain-language translation not yet generated
          </div>
          <div className="text-[12px] text-zinc-400 italic">
            {p.request_text || "—"}
          </div>
          <button
            onClick={handleTranslate}
            disabled={translating}
            data-testid={`ora-dev-translate-${short}`}
            className="mt-2 text-[11px] px-3 py-1 rounded bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 disabled:opacity-50"
          >
            {translating ? "Translating…" : "🇮🇳 Translate to Hinglish"}
          </button>
        </div>
      )}

      {/* Action row */}
      <div className="mt-4 flex flex-wrap gap-2 items-center">
        {statusKey === "pending" && !sealed && (
          <button
            onClick={() => onAct(id, "approve")}
            disabled={busy}
            data-testid={`ora-dev-approve-${short}`}
            className="text-[12px] px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-black font-medium flex items-center gap-1 disabled:opacity-40"
          >
            <Check className="w-3.5 h-3.5" /> Approve
          </button>
        )}
        {statusKey === "pending" && (
          <button
            onClick={() => onAct(id, "reject")}
            disabled={busy}
            data-testid={`ora-dev-reject-${short}`}
            className="text-[12px] px-3 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-medium flex items-center gap-1 disabled:opacity-40"
          >
            <X className="w-3.5 h-3.5" /> Reject
          </button>
        )}
        {/* Tier-1 cancel-auto button */}
        {statusKey === "pending" && tier === "tier_1" && autoExecAt && (
          <button
            onClick={() => onAct(id, "cancel-auto")}
            disabled={busy}
            data-testid={`ora-dev-cancel-auto-${short}`}
            className="text-[12px] px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 flex items-center gap-1 disabled:opacity-40"
            title="Cancel auto-execute window"
          >
            ⏱ Cancel Auto
          </button>
        )}
        {statusKey === "approved" && (
          <>
            <button
              onClick={() => onAct(id, "applied")}
              disabled={busy}
              data-testid={`ora-dev-applied-${short}`}
              className="text-[12px] px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium flex items-center gap-1 disabled:opacity-40"
            >
              <PlayCircle className="w-3.5 h-3.5" /> Mark Applied
            </button>
            <button
              onClick={() => onAct(id, "prepare-pr")}
              disabled={busy}
              data-testid={`ora-dev-pr-${short}`}
              className="text-[12px] px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-black font-medium flex items-center gap-1 disabled:opacity-40"
              title="Generate commit message + branch suggestion. Then use 'Save to GitHub'."
            >
              <GitBranch className="w-3.5 h-3.5" /> Apply via PR
            </button>
            <button
              onClick={() => onAct(id, "reject")}
              disabled={busy}
              data-testid={`ora-dev-reject-${short}`}
              className="text-[12px] px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium flex items-center gap-1 disabled:opacity-40"
            >
              <X className="w-3.5 h-3.5" /> Revert to Reject
            </button>
          </>
        )}
        {statusKey === "applied" && (
          <button
            onClick={() => onAct(id, "rollback")}
            disabled={busy}
            data-testid={`ora-dev-rollback-${short}`}
            className="text-[12px] px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-black font-medium flex items-center gap-1 disabled:opacity-40"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Rollback
          </button>
        )}
        {/* Details toggle */}
        <button
          onClick={() => setShowDetails((s) => !s)}
          data-testid={`ora-dev-details-${short}`}
          className="text-[12px] px-3 py-1.5 rounded bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700 text-zinc-300 ml-auto flex items-center gap-1"
        >
          🔍 {showDetails ? "Hide" : "Details"}
        </button>
        {busy && <Loader2 className="w-4 h-4 animate-spin text-zinc-400 ml-1" />}
      </div>

      {/* Technical details — collapsed by default */}
      {showDetails && (
        <div
          data-testid={`ora-dev-card-${short}-tech`}
          className="mt-3 rounded-lg border border-zinc-800 bg-black/60 p-3"
        >
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
            Technical request
          </div>
          <div className="text-[12px] text-zinc-300 italic mb-3">
            {p.request_text || "—"}
          </div>
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
            Technical proposal
          </div>
          <pre
            data-testid={`ora-dev-card-${short}-proposal`}
            className="max-h-72 overflow-auto bg-zinc-950 border border-zinc-900 rounded p-3 text-[12px] text-zinc-200 whitespace-pre-wrap"
          >
            {p.proposal_text || "(no proposal body)"}
          </pre>
          {p.tier_reason && (
            <div className="text-[10px] text-zinc-500 mt-2">
              tier: <span className="text-amber-300">{tier}</span> · {p.tier_reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const OraDevConsole = () => {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [toast, setToast] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const path =
        filter === "all"
          ? "/api/admin/ora-dev/list?limit=100"
          : `/api/admin/ora-dev/list?status=${filter}&limit=100`;
      const [listRes, statsRes] = await Promise.all([
        fetch(`${API}${path}`, { headers: { ...authHeaders() } }),
        fetch(`${API}/api/admin/ora-dev/stats`, { headers: { ...authHeaders() } }),
      ]);
      if (listRes.status === 401 || listRes.status === 403) {
        setErr("Admin login required.");
        setItems([]);
        setStats(null);
        return;
      }
      const list = await listRes.json();
      const st = statsRes.ok ? await statsRes.json() : null;
      setItems(list?.items || []);
      setStats(st);
    } catch (e) {
      setErr(`Fetch failed: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 30000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const showToast = (msg, kind = "info") => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  };

  const onAct = useCallback(
    async (id, action) => {
      setBusyId(id);
      try {
        const r = await fetch(`${API}/api/admin/ora-dev/${id}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
        });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) {
          showToast(`✗ ${action}: ${body?.detail || r.status}`, "bad");
        } else if (action === "prepare-pr") {
          // Special-case: copy commit message to clipboard so admin can
          // paste into the platform's "Save to GitHub" feature.
          const cm = body?.commit_message || "";
          try {
            await navigator.clipboard.writeText(cm);
            showToast(`✓ commit copied: ${cm.slice(0, 60)}`, "good");
          } catch (_) {
            showToast(`✓ PR ready · commit: ${cm.slice(0, 60)}`, "info");
          }
          fetchAll();
        } else {
          showToast(`✓ ${action} ok (${id.slice(0, 8)})`, "good");
          fetchAll();
        }
      } catch (e) {
        showToast(`✗ ${action}: ${e.message || e}`, "bad");
      } finally {
        setBusyId(null);
      }
    },
    [fetchAll]
  );

  const onTranslate = useCallback(
    async (id) => {
      try {
        const r = await fetch(`${API}/api/admin/ora-dev/${id}/translate`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
        });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) {
          showToast(`✗ translate: ${body?.detail || r.status}`, "bad");
        } else {
          showToast(`✓ translated (${id.slice(0, 8)})`, "good");
          fetchAll();
        }
      } catch (e) {
        showToast(`✗ translate: ${e.message || e}`, "bad");
      }
    },
    [fetchAll]
  );

  const counts = useMemo(() => {
    const c = stats || {};
    return {
      pending: c.pending || 0,
      approved: c.approved || 0,
      applied: c.applied || 0,
      rejected: c.rejected || 0,
      rolled_back: c.rolled_back || 0,
      total: c.total || 0,
    };
  }, [stats]);

  return (
    <div
      data-testid="ora-dev-console-panel"
      className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-950 to-black p-5"
    >
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <CircleDot className="w-4 h-4 text-amber-400" />
            <h3 className="text-base font-semibold text-zinc-100">
              ORA Dev Console
            </h3>
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 border border-zinc-800 px-2 py-0.5 rounded">
              Phase 2.2
            </span>
          </div>
          <p className="text-[12px] text-zinc-500 mt-1">
            Mode 2 (Software Engineer) proposals queue. ORA never auto-applies —
            human approval required.
          </p>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          data-testid="ora-dev-refresh-btn"
          className="text-[12px] px-3 py-1.5 rounded bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-zinc-200 flex items-center gap-1 disabled:opacity-40"
        >
          {loading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Refresh
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-4">
        <StatPill label="Pending" value={counts.pending} tone="warn" testid="ora-dev-stat-pending" />
        <StatPill label="Approved" value={counts.approved} testid="ora-dev-stat-approved" />
        <StatPill label="Applied" value={counts.applied} tone="good" testid="ora-dev-stat-applied" />
        <StatPill label="Rejected" value={counts.rejected} tone="bad" testid="ora-dev-stat-rejected" />
        <StatPill label="Rolled Back" value={counts.rolled_back} testid="ora-dev-stat-rolled-back" />
        <StatPill label="Total" value={counts.total} testid="ora-dev-stat-total" />
      </div>

      <div className="mt-4">
        <StatusFilter value={filter} onChange={setFilter} />
      </div>

      {err && (
        <div
          data-testid="ora-dev-error"
          className="mt-4 rounded-lg border border-rose-900 bg-rose-950/40 p-3 text-[12px] text-rose-300"
        >
          {err}
        </div>
      )}

      <div className="mt-4">
        {loading && items.length === 0 && (
          <div className="flex items-center gap-2 text-zinc-400 text-sm py-8 justify-center">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading proposals…
          </div>
        )}

        {!loading && items.length === 0 && (
          <div
            data-testid="ora-dev-empty"
            className="text-zinc-500 text-sm py-8 text-center border border-dashed border-zinc-800 rounded-lg"
          >
            Koi {filter === "all" ? "" : filter} proposals nahi hain. ORA Mode 2 idle hai.
          </div>
        )}

        {items.map((p) => (
          <ProposalCard key={p.proposal_id} p={p} onAct={onAct} busyId={busyId} onTranslate={onTranslate} />
        ))}
      </div>

      {toast && (
        <div
          data-testid="ora-dev-toast"
          className={`fixed right-6 bottom-6 z-50 px-4 py-2 rounded-lg shadow-lg text-sm border ${
            toast.kind === "good"
              ? "bg-emerald-600 text-black border-emerald-400"
              : toast.kind === "bad"
              ? "bg-rose-700 text-white border-rose-500"
              : "bg-zinc-800 text-zinc-100 border-zinc-700"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
};

export default OraDevConsole;
