/* AdminSidebarBlocks.jsx — "Data > Lights" Command Interface (iter 272)
 * ==========================================================================
 * Strict projection of pillar snapshot into 5 merged sidebar blocks + live
 * payment toast. NO independent DB queries — pure consumer of the cached
 * /api/admin/pillars-map/sidebar-blocks endpoint.
 *
 * Consumed by: AdminShortcuts layout or mounted at /admin/command.
 * Polls every 10s (same cadence as other admin telemetry).
 *
 * Tenets:
 *   - If pillar is red, the block is red. No escape hatch.
 *   - If DB-pulse red, the count shows with ⚠ and tooltip "stale".
 *   - Live-events poll every 8s surfaces new payments as sliding toasts.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2, RefreshCw, AlertTriangle, CheckCircle, Clock,
  DollarSign, ExternalLink,
} from "lucide-react";
import MissionControlRibbon from "./MissionControlRibbon";
import BuildBadge from "../lib/BuildBadge";

const API = process.env.REACT_APP_BACKEND_URL || "";
const BLOCKS_POLL_MS = 10_000;
const EVENTS_POLL_MS = 8_000;

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

const STATUS_COLOR = {
  green:  "#22C55E",
  yellow: "#F59E0B",
  red:    "#EF4444",
};

function StatusDot({ status, size = 9, pulse = false }) {
  const c = STATUS_COLOR[status] || STATUS_COLOR.yellow;
  return (
    <span
      className={pulse ? "sb-pulse" : ""}
      style={{
        display: "inline-block",
        width: size, height: size, borderRadius: "50%",
        background: c,
        boxShadow: pulse ? `0 0 12px ${c}` : "none",
      }}
    />
  );
}

function BlockCard({ block, onOpen }) {
  const c = STATUS_COLOR[block.status] || STATUS_COLOR.yellow;
  return (
    <button
      data-testid={`sidebar-block-${block.id}`}
      onClick={onOpen}
      className="text-left rounded-xl border border-gray-800 bg-gray-900/60 hover:bg-gray-900/90 transition-all p-5 group"
      style={{ borderLeft: `4px solid ${c}` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-2xl" style={{ color: c }}>{block.glyph}</span>
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-widest text-gray-500">
              {block.primary_sidebar_section}
            </div>
            <h3 className="text-base font-semibold text-gray-100 truncate">{block.label}</h3>
          </div>
        </div>
        <StatusDot status={block.status} size={12} pulse={block.status !== "green"} />
      </div>

      <div className="grid grid-cols-2 gap-2 mt-3">
        {(block.badges || []).map((b) => (
          <div
            key={b.label}
            data-testid={`badge-${block.id}-${b.collection}`}
            className="flex items-center justify-between px-2 py-1.5 rounded bg-gray-950/60 border border-gray-800"
            title={b.reason || ""}
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <StatusDot status={b.status} size={6} />
              <span className="text-[10px] text-gray-400 truncate">{b.label}</span>
            </div>
            <div className="flex items-center gap-0.5 flex-shrink-0">
              <span className="text-sm font-mono font-semibold text-gray-100">
                {b.count === null || b.count === undefined ? "—" : b.count.toLocaleString()}
              </span>
              {b.stale && (
                <span
                  className="text-amber-400 text-xs"
                  title={`Stale: ${b.reason || "last DB write older than threshold"}`}
                  data-testid={`stale-${block.id}-${b.collection}`}
                >⚠</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-800 text-[10px]">
        <span className="text-gray-500">
          {(block.pillar_snapshots || []).map((p) => (
            <span key={p.key} className="mr-2">
              {p.key.replace("_", "·")}{" "}
              <span style={{ color: STATUS_COLOR[p.status] }}>●</span>
            </span>
          ))}
        </span>
        <span className="text-gray-600 flex items-center gap-1 group-hover:text-gray-300">
          drill <ExternalLink className="w-3 h-3" />
        </span>
      </div>
    </button>
  );
}

/* Sliding payment toast */
function PaymentToast({ event, onDismiss }) {
  useEffect(() => {
    const id = setTimeout(onDismiss, 5000);
    return () => clearTimeout(id);
  }, [onDismiss]);

  return (
    <div
      data-testid={`payment-toast-${event.id}`}
      className="fixed top-6 right-6 z-50 rounded-lg border bg-gray-950/95 backdrop-blur border-emerald-700/60 shadow-2xl px-4 py-3 min-w-[280px]"
      style={{
        animation: "sbToastIn 0.35s cubic-bezier(0.3, 1.1, 0.5, 1.0), sbToastOut 0.4s ease-in 4.6s forwards",
      }}
    >
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-full bg-emerald-600/20 border border-emerald-500/40">
          <DollarSign className="w-4 h-4 text-emerald-300" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs uppercase tracking-widest text-emerald-400 font-bold">Payment received</div>
          <div className="text-sm text-gray-100 font-semibold mt-0.5 truncate">
            ${Number(event.amount || 0).toLocaleString()} {event.currency || "USD"}
          </div>
          <div className="text-[10px] text-gray-500 truncate">from {event.customer}</div>
        </div>
      </div>
    </div>
  );
}

/* Page */
export default function AdminSidebarBlocks() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  // Live event state
  const [toasts, setToasts] = useState([]);
  const lastSeenTs = useRef(new Date().toISOString());
  const seenIds = useRef(new Set());

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/admin/pillars-map/sidebar-blocks`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setErr("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const pollEvents = useCallback(async () => {
    try {
      const r = await fetch(
        `${API}/api/admin/pillars-map/live-events?since=${encodeURIComponent(lastSeenTs.current)}`,
        { headers: authHeaders() },
      );
      if (!r.ok) return;
      const d = await r.json();
      lastSeenTs.current = d.now || lastSeenTs.current;
      const fresh = (d.events || []).filter((e) => e.kind === "payment" && e.id && !seenIds.current.has(e.id));
      if (fresh.length === 0) return;
      fresh.forEach((e) => seenIds.current.add(e.id));
      setToasts((prev) => [...prev, ...fresh].slice(-5)); // cap at 5 visible
    } catch {
      /* ignore network errors for polling */
    }
  }, []);

  useEffect(() => {
    load();
    const id1 = setInterval(load, BLOCKS_POLL_MS);
    const id2 = setInterval(pollEvents, EVENTS_POLL_MS);
    return () => { clearInterval(id1); clearInterval(id2); };
  }, [load, pollEvents]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <div data-testid="admin-sidebar-blocks" className="min-h-screen bg-gray-950 text-gray-100 pb-20">
      <MissionControlRibbon />
      <style>{`
        .sb-pulse { animation: sbPulse 1.4s ease-in-out infinite; }
        @keyframes sbPulse {
          0%,100% { transform: scale(1); opacity: 1; }
          50%     { transform: scale(1.4); opacity: 0.55; }
        }
        @keyframes sbToastIn {
          from { opacity: 0; transform: translateX(40px) scale(0.95); }
          to   { opacity: 1; transform: translateX(0)    scale(1); }
        }
        @keyframes sbToastOut {
          from { opacity: 1; transform: translateX(0) }
          to   { opacity: 0; transform: translateX(40px) }
        }
      `}</style>

      <div className="max-w-7xl mx-auto px-6 pt-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-amber-400 flex items-center gap-2">
              <span>Data &gt; Lights</span>
              <span className="text-gray-600">·</span>
              <BuildBadge />
            </div>
            <h1 className="text-3xl font-bold text-gray-100 mt-1">Command Blocks</h1>
            <p className="text-sm text-gray-400 mt-1">
              Pillar-inherited health · strict single-source projection · live payment stream
            </p>
          </div>
          <div className="flex items-center gap-3">
            {data?.overall_status && (
              <span
                className="px-2.5 py-1 rounded text-xs font-semibold border"
                style={{
                  color: STATUS_COLOR[data.overall_status],
                  background: `${STATUS_COLOR[data.overall_status]}1a`,
                  borderColor: `${STATUS_COLOR[data.overall_status]}55`,
                }}
                data-testid="blocks-overall-status"
              >
                Overall: {data.overall_status.toUpperCase()}
              </span>
            )}
            <button
              data-testid="blocks-refresh"
              onClick={load}
              className="text-xs flex items-center gap-1 text-gray-300 hover:text-gray-100 px-3 py-1.5 rounded border border-gray-800 bg-gray-900/60"
            >
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
        </div>

        {loading && !data && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
            <span className="ml-3 text-gray-400">Projecting pillar snapshot…</span>
          </div>
        )}

        {err && !data && (
          <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
            {err}
          </div>
        )}

        {data && (
          <>
            <div data-testid="blocks-grid" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.blocks.map((b) => (
                <BlockCard
                  key={b.id}
                  block={b}
                  onOpen={() => navigate("/admin/pillars-map")}
                />
              ))}
            </div>

            <div className="mt-6 text-xs text-gray-500 flex items-center gap-3">
              <Clock className="w-3 h-3" />
              snapshot {data.cached ? "cached" : "live"} · auto-refresh {BLOCKS_POLL_MS / 1000}s · events {EVENTS_POLL_MS / 1000}s
              <span className="text-gray-700">·</span>
              <span>Wired to /admin/pillars-map · no independent DB queries</span>
            </div>
          </>
        )}
      </div>

      {/* Live payment toasts */}
      {toasts.map((t) => (
        <PaymentToast key={t.id} event={t} onDismiss={() => dismissToast(t.id)} />
      ))}
    </div>
  );
}
