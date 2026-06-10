/**
 * ApprovalInboxPanel.jsx — iter D-76
 *
 * Live queue widget for the autonomous-repair pending_approvals
 * collection. Founder sees every awaiting-action row with its
 * linked LLM proposal inline (diagnosis + suggested fix) and can
 * approve or reject in one click. No mocks — every byte is a real
 * Mongo doc routed through autonomous_repair_admin_router.py.
 *
 * Endpoints (admin-only, JWT required):
 *   GET  /api/admin/autonomous-repair/list?limit=N
 *   POST /api/admin/autonomous-repair/approve/{approval_id}
 *   POST /api/admin/autonomous-repair/reject/{approval_id}
 *
 * After D-73 healed the legacy schema + flushed 442 stale rows,
 * this widget replaces the founder's only previous tool (manual
 * Mongo shell queries) with a real UI surface.
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Inbox, CheckCircle2, XCircle, ChevronDown, ChevronRight,
  Clock, AlertTriangle, RefreshCw,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

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

function relTime(iso) {
  if (!iso) return "?";
  try {
    const sec = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
    return `${Math.round(sec / 86400)}d ago`;
  } catch {
    return "?";
  }
}

function StatusPill({ status }) {
  const map = {
    pending_approval: "bg-amber-900/30 text-amber-200 border-amber-700/40",
    approved:         "bg-emerald-900/30 text-emerald-200 border-emerald-700/40",
    executing:        "bg-blue-900/30 text-blue-200 border-blue-700/40",
    failed:           "bg-red-900/30 text-red-200 border-red-700/40",
  };
  const cls = map[status] || "bg-zinc-800/60 text-zinc-300 border-zinc-700/40";
  return (
    <span
      data-testid={`approval-status-${status}`}
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] uppercase tracking-wider border ${cls}`}
    >
      {status || "unknown"}
    </span>
  );
}

function ApprovalRow({ row, onApprove, onReject, busy }) {
  const [open, setOpen] = useState(false);
  const proposal = row.proposal;
  const summary = row.summary || proposal?.summary || proposal?.title || "(no summary)";

  return (
    <div
      data-testid={`approval-row-${row.approval_id}`}
      className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950/60"
    >
      <div className="flex items-start gap-3 p-3">
        <button
          data-testid={`approval-expand-${row.approval_id}`}
          onClick={() => setOpen((v) => !v)}
          className="mt-1 text-zinc-400 hover:text-zinc-200"
          aria-label="Toggle details"
        >
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <StatusPill status={row.status} />
            <span className="text-[10px] uppercase tracking-wider text-zinc-500">
              {row.type || "legacy"}
            </span>
            {row.tier && (
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">
                · {row.tier}
              </span>
            )}
            {row.source && (
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">
                · {row.source}
              </span>
            )}
            <span className="ml-auto text-[10px] text-zinc-500 flex items-center gap-1">
              <Clock size={11} /> {relTime(row.created_at)}
            </span>
          </div>

          <div className="text-sm text-zinc-200 truncate" title={summary}>
            {summary}
          </div>
          {row.target && (
            <div className="text-xs text-zinc-500 mt-0.5 truncate">
              target: <span className="text-zinc-300">{row.target}</span>
            </div>
          )}
          {!row.proposal_id && (
            <div className="text-[11px] text-amber-400 mt-1 flex items-center gap-1">
              <AlertTriangle size={11} />
              no LLM proposal linked yet — approve will 409 until one attaches
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            data-testid={`approval-approve-${row.approval_id}`}
            onClick={() => onApprove(row.approval_id)}
            disabled={busy || !row.proposal_id || row.status === "approved"}
            className="px-3 py-1.5 rounded text-xs font-medium border border-emerald-700/60 bg-emerald-900/30 text-emerald-200 hover:bg-emerald-900/50 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1"
          >
            <CheckCircle2 size={13} /> Approve
          </button>
          <button
            data-testid={`approval-reject-${row.approval_id}`}
            onClick={() => onReject(row.approval_id)}
            disabled={busy}
            className="px-3 py-1.5 rounded text-xs font-medium border border-red-700/60 bg-red-900/30 text-red-200 hover:bg-red-900/50 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1"
          >
            <XCircle size={13} /> Reject
          </button>
        </div>
      </div>

      {open && (
        <div
          data-testid={`approval-details-${row.approval_id}`}
          className="border-t border-zinc-800 bg-zinc-900/40 px-4 py-3 text-xs space-y-2"
        >
          {proposal ? (
            <>
              <div>
                <span className="text-zinc-500 uppercase tracking-wider text-[10px]">
                  LLM Diagnosis
                </span>
                <pre className="mt-1 text-zinc-200 whitespace-pre-wrap font-mono text-[11px] leading-relaxed">
                  {proposal.diagnosis || proposal.analysis || "(none)"}
                </pre>
              </div>
              <div>
                <span className="text-zinc-500 uppercase tracking-wider text-[10px]">
                  Suggested Fix
                </span>
                <pre className="mt-1 text-zinc-200 whitespace-pre-wrap font-mono text-[11px] leading-relaxed">
                  {proposal.suggested_fix || proposal.fix || proposal.action || "(none)"}
                </pre>
              </div>
              <div className="text-zinc-500 text-[10px]">
                proposal_id: <span className="text-zinc-300">{row.proposal_id}</span>
                {" · "}
                model: <span className="text-zinc-300">{proposal.model || "?"}</span>
              </div>
            </>
          ) : (
            <div className="text-zinc-500 italic">
              No LLM proposal attached. The repair agent hasn&apos;t analyzed this
              row yet — it will attach a proposal on the next poll tick, or
              you can reject to clear the queue.
            </div>
          )}

          <details className="text-zinc-500">
            <summary className="cursor-pointer hover:text-zinc-300">
              raw approval doc
            </summary>
            <pre className="mt-2 font-mono text-[10px] text-zinc-400 whitespace-pre-wrap">
              {JSON.stringify(row.raw || row, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}

export default function ApprovalInboxPanel() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState("");
  const [onlyPending, setOnlyPending] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const qs = new URLSearchParams({ limit: "50" });
      if (onlyPending) qs.set("status", "pending_approval");
      const r = await fetch(
        `${API}/api/admin/autonomous-repair/list?${qs}`,
        { headers: { ...authHeaders() } },
      );
      if (!r.ok) {
        const body = await r.text().catch(() => "");
        throw new Error(`${r.status} ${body.slice(0, 200)}`);
      }
      const j = await r.json();
      setItems(j.items || []);
      setTotal(j.total || 0);
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [onlyPending]);

  useEffect(() => { load(); }, [load]);

  const doAction = useCallback(async (id, action) => {
    setErr("");
    setBusyId(id);
    try {
      const r = await fetch(
        `${API}/api/admin/autonomous-repair/${action}/${id}`,
        { method: "POST", headers: { ...authHeaders() } },
      );
      if (!r.ok) {
        const body = await r.text().catch(() => "");
        let detail = body;
        try { detail = JSON.parse(body).detail || body; } catch (_e) { /* keep raw */ }
        throw new Error(`${action} failed (${r.status}): ${String(detail).slice(0, 200)}`);
      }
      await load();
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusyId(null);
    }
  }, [load]);

  return (
    <div
      data-testid="approval-inbox-panel"
      className="border border-zinc-800 rounded-xl bg-zinc-950/70 p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Inbox size={18} className="text-amber-300" />
          <h3 className="text-sm font-semibold tracking-wide text-zinc-100 uppercase">
            Approval Inbox
          </h3>
          <span
            data-testid="approval-inbox-count"
            className="text-xs text-zinc-500"
          >
            ({items.length}{total > items.length ? ` of ${total}` : ""})
          </span>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs text-zinc-400 flex items-center gap-2 cursor-pointer">
            <input
              data-testid="approval-inbox-only-pending"
              type="checkbox"
              checked={onlyPending}
              onChange={(e) => setOnlyPending(e.target.checked)}
              className="accent-amber-500"
            />
            only pending
          </label>
          <button
            data-testid="approval-inbox-refresh"
            onClick={load}
            disabled={loading}
            className="text-xs text-zinc-300 hover:text-white inline-flex items-center gap-1 disabled:opacity-40"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            refresh
          </button>
        </div>
      </div>

      {err && (
        <div
          data-testid="approval-inbox-error"
          className="mb-3 text-xs text-red-300 bg-red-950/40 border border-red-900/50 rounded px-3 py-2"
        >
          {err}
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="text-xs text-zinc-500 italic">loading…</div>
      ) : items.length === 0 ? (
        <div
          data-testid="approval-inbox-empty"
          className="text-xs text-zinc-500 italic"
        >
          inbox clear — no pending approvals. Repair agent has nothing
          waiting on you.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((row) => (
            <ApprovalRow
              key={row.approval_id}
              row={row}
              onApprove={(id) => doAction(id, "approve")}
              onReject={(id) => doAction(id, "reject")}
              busy={busyId === row.approval_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
