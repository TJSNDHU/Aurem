/* AdminPillarsMap.jsx — 3-Level Deep-Drill Pulse Engine (iter 269)
 * ================================================================
 * The "Data-Driven Pulses" dashboard — eliminates silent failures by
 * showing status at three depths:
 *
 *   L1  Pillar        → top-of-page cards with overall green/yellow/red
 *   L2  Collection    → modal 1, shows doc count + last_write_at per coll
 *                        + silent-failure flag (worker green, DB stopped)
 *   L3  Service       → modal 2, every Python file that references
 *                        the collection + recent errors + jump-to-Stem-Fix
 *
 * Uses the cached /heartbeat endpoint (20s backend cadence) so the UI
 * loads in <100ms regardless of Mongo load.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2, RefreshCw, Activity, Database, FileCode, AlertTriangle,
  CheckCircle, XCircle, Clock, Zap, ExternalLink, Server, X,
} from "lucide-react";
import MissionControlRibbon from "./MissionControlRibbon";
import BuildBadge from "../lib/BuildBadge";
import DeployStatusPanel from "./DeployStatusPanel";
import AutonomousRepairPanel from "./AutonomousRepairPanel";
import PendingCodeFixesPanel from "./PendingCodeFixesPanel";
import TruthLedgerPanel from "./TruthLedgerPanel";
import MTTHCard from "./MTTHCard";
import TransparencyWall from "./TransparencyWall";
import EmpireHUDMap from "./EmpireHUDMap";
import AutopilotMasterButton from "./AutopilotMasterButton";
import OraDevConsole from "./OraDevConsole";
import OraPhase25Panel from "./OraPhase25Panel";
import { safeFetchJson } from "../lib/safeFetchJson";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_INTERVAL_MS = 10000;

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

const STATUS_META = {
  green:  { color: "#22C55E", bg: "rgba(34,197,94,0.15)",  label: "Healthy",  Icon: CheckCircle },
  yellow: { color: "#F59E0B", bg: "rgba(245,158,11,0.15)", label: "Degraded", Icon: Clock },
  red:    { color: "#EF4444", bg: "rgba(239,68,68,0.15)",  label: "Broken",   Icon: AlertTriangle },
};

function StatusDot({ status, size = 10, pulse = false, testId }) {
  const meta = STATUS_META[status] || STATUS_META.yellow;
  return (
    <span
      data-testid={testId}
      className={pulse ? "pulse-dot" : ""}
      style={{
        display: "inline-block",
        width: size, height: size, borderRadius: "50%",
        background: meta.color,
        boxShadow: pulse ? `0 0 12px ${meta.color}` : "none",
      }}
      title={meta.label}
    />
  );
}

function StatusBadge({ status, testId }) {
  const meta = STATUS_META[status] || STATUS_META.yellow;
  const { Icon } = meta;
  return (
    <span
      data-testid={testId}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold"
      style={{ background: meta.bg, color: meta.color, border: `1px solid ${meta.color}33` }}
    >
      <Icon className="size-3" />
      {meta.label}
    </span>
  );
}

function formatRelative(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const diff = Math.max(0, Date.now() - d.getTime());
    if (diff < 60_000) return `${Math.round(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
    return `${Math.round(diff / 86_400_000)}d ago`;
  } catch {
    return "—";
  }
}

/* ─── Level 1: Pillar grid card ─────────────────────────────────── */
function PillarCard({ pillar, onOpen }) {
  const { label, color, status, workers, collections } = pillar;
  const meta = STATUS_META[status] || STATUS_META.yellow;
  return (
    <button
      data-testid={`pillar-card-${pillar.key}`}
      onClick={onOpen}
      className="text-left rounded-xl border border-gray-800 bg-gray-900/60 hover:bg-gray-900/90 transition-all p-5 group"
      style={{ borderLeft: `4px solid ${color}` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-xs uppercase tracking-widest" style={{ color }}>
            {pillar.key.toUpperCase().replace("_", " · ")}
          </div>
          <h3 className="text-base font-semibold text-gray-100 mt-1">{label}</h3>
        </div>
        <StatusDot status={status} size={14} pulse={status !== "green"} testId={`pillar-dot-${pillar.key}`} />
      </div>

      <div className="grid grid-cols-3 gap-3 mt-4 text-center">
        <div>
          <div className="text-2xl font-bold text-gray-100">{workers.live}</div>
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mt-0.5">Live Workers</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-gray-100">{collections.total}</div>
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mt-0.5">Collections</div>
        </div>
        <div>
          <div className="text-2xl font-bold" style={{ color: collections.silent_failures ? "#EF4444" : "#22C55E" }}>
            {collections.silent_failures || 0}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mt-0.5">Silent Fails</div>
        </div>
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-800">
        <StatusBadge status={status} testId={`pillar-badge-${pillar.key}`} />
        <span className="text-xs text-gray-400 flex items-center gap-1 group-hover:text-gray-200">
          Drill in <ExternalLink className="size-3" />
        </span>
      </div>
    </button>
  );
}

/* ─── Level 2: Collections modal ────────────────────────────────── */
function CollectionModal({ pillar, onClose, onOpenCollection }) {
  if (!pillar) return null;
  const rows = pillar.collections?.rows || [];
  return (
    <div
      data-testid="collection-modal-backdrop"
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        data-testid="collection-modal"
        className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{ borderTop: `4px solid ${pillar.color}` }}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div>
            <div className="text-xs uppercase tracking-widest" style={{ color: pillar.color }}>
              Level 2 · Collection Layer
            </div>
            <h2 className="text-lg font-semibold text-gray-100 mt-1">{pillar.label}</h2>
          </div>
          <button
            data-testid="collection-modal-close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-100 p-2"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="overflow-y-auto p-5">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-gray-500 border-b border-gray-800">
              <tr>
                <th className="text-left py-2 pr-3">Collection</th>
                <th className="text-right py-2 px-3">Docs</th>
                <th className="text-right py-2 px-3">Last Write</th>
                <th className="text-center py-2 px-3" title="DB · Backend · Frontend">Triple-Pulse</th>
                <th className="text-center py-2 px-3">Status</th>
                <th className="text-right py-2 pl-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const tp = row.triple_pulse || {};
                const db = tp.db || {}, be = tp.backend || {}, fe = tp.frontend || {};
                return (
                <tr
                  key={row.collection}
                  data-testid={`coll-row-${row.collection}`}
                  className="border-b border-gray-900 hover:bg-gray-900/50"
                >
                  <td className="py-2 pr-3">
                    <div className="font-mono text-gray-100">{row.collection}</div>
                    <div className="text-xs text-gray-500">{row.label}</div>
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {row.count === null ? "—" : row.count.toLocaleString()}
                  </td>
                  <td className="py-2 px-3 text-right text-xs text-gray-400">
                    {row.expects_writes ? formatRelative(row.last_write_at) : <span className="text-gray-600">n/a</span>}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex items-center justify-center gap-1.5" data-testid={`triple-${row.collection}`}>
                      <span title={`DB · ${db.reason || ''}`} className="inline-flex items-center gap-0.5">
                        <span className="text-[9px] text-gray-500 font-bold">DB</span>
                        <StatusDot status={db.status || 'yellow'} size={8} pulse={db.status === 'red'} />
                      </span>
                      <span className="text-gray-700">·</span>
                      <span title={`Backend · ${be.reason || ''}`} className="inline-flex items-center gap-0.5">
                        <span className="text-[9px] text-gray-500 font-bold">BE</span>
                        <StatusDot status={be.status || 'yellow'} size={8} pulse={be.status === 'red'} />
                      </span>
                      <span className="text-gray-700">·</span>
                      <span title={`Frontend · ${fe.reason || ''}`} className="inline-flex items-center gap-0.5">
                        <span className="text-[9px] text-gray-500 font-bold">FE</span>
                        <StatusDot status={fe.status || 'yellow'} size={8} />
                      </span>
                    </div>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <StatusDot status={row.status} pulse={row.silent_failure} />
                      {row.silent_failure && (
                        <span className="text-[10px] text-red-400 font-semibold" title="Worker green but no DB writes in threshold window">
                          SILENT
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-2 pl-3 text-right">
                    <button
                      data-testid={`coll-drill-${row.collection}`}
                      onClick={() => onOpenCollection(row)}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 ml-auto"
                    >
                      Services <ExternalLink className="size-3" />
                    </button>
                  </td>
                </tr>
              );})}
            </tbody>
          </table>
        </div>

        <div className="px-5 py-3 border-t border-gray-800 text-xs text-gray-500 flex justify-between">
          <span>Worker tasks alive: <span className="text-gray-200 font-semibold">{pillar.workers.live}</span></span>
          <span>Silent failures: <span className="text-red-400 font-semibold">{pillar.collections.silent_failures || 0}</span> · Unreachable: <span className="text-red-400 font-semibold">{pillar.collections.unreachable}</span></span>
        </div>
      </div>
    </div>
  );
}

/* ─── Level 3: Service + Errors modal ───────────────────────────── */
function ServiceModal({ collection, onClose }) {
  const navigate = useNavigate();
  const [svcData, setSvcData] = useState(null);
  const [errData, setErrData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!collection) return;
    const ac = new AbortController();
    (async () => {
      setLoading(true); setErr("");
      try {
        // iter 325v — safeFetchJson never throws on HTML/non-JSON, so a
        // single Cloudflare 520 page no longer takes down the modal.
        const [sRes, eRes] = await Promise.all([
          safeFetchJson(`${API}/api/admin/pillars-map/collection/${collection.collection}/services`,
                        { headers: authHeaders(), signal: ac.signal }),
          safeFetchJson(`${API}/api/admin/pillars-map/collection/${collection.collection}/errors`,
                        { headers: authHeaders(), signal: ac.signal }),
        ]);
        if (sRes.isGatewayError || eRes.isGatewayError) {
          setErr(`Backend gateway unreachable (HTTP ${sRes.status || eRes.status}).`);
          return;
        }
        if (!sRes.ok && !sRes.isAuthError) { setErr(sRes.error); return; }
        setSvcData(sRes.data); setErrData(eRes.data);
      } catch (e2) {
        if (e2.name !== "AbortError") setErr(String(e2));
      } finally {
        setLoading(false);
      }
    })();
    return () => ac.abort();
  }, [collection]);

  if (!collection) return null;

  return (
    <div
      data-testid="service-modal-backdrop"
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        data-testid="service-modal"
        className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{ borderTop: "4px solid #A855F7" }}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div>
            <div className="text-xs uppercase tracking-widest text-purple-400">Level 3 · Service Layer</div>
            <h2 className="text-lg font-semibold text-gray-100 mt-1 font-mono">{collection.collection}</h2>
            <div className="text-xs text-gray-500 mt-0.5">{collection.label}</div>
            {collection.triple_pulse && (
              <div className="flex items-center gap-3 mt-3" data-testid="l3-triple-pulse">
                {[
                  { key: "db", label: "DB Side",        data: collection.triple_pulse.db },
                  { key: "be", label: "Backend Side",   data: collection.triple_pulse.backend },
                  { key: "fe", label: "Frontend Side",  data: collection.triple_pulse.frontend },
                ].map((p) => (
                  <div
                    key={p.key}
                    data-testid={`l3-pulse-${p.key}`}
                    className="flex items-center gap-2 px-2.5 py-1 rounded bg-gray-900/70 border border-gray-800"
                    title={p.data?.reason || ""}
                  >
                    <StatusDot status={p.data?.status || "yellow"} size={10} pulse={p.data?.status === "red"} />
                    <span className="text-[11px] text-gray-300 font-semibold">{p.label}</span>
                    <span className="text-[10px] text-gray-500">· {p.data?.reason || "n/a"}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            data-testid="service-modal-close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-100 p-2"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="overflow-y-auto p-5 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="size-6 text-gray-400 animate-spin" />
            </div>
          )}
          {err && <div className="text-red-400 text-sm">{err}</div>}

          {!loading && svcData && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-100 flex items-center gap-2">
                  <FileCode className="size-4 text-purple-400" />
                  Services referencing this collection
                </h3>
                <span className="text-xs text-gray-500">{svcData.count || 0} files</span>
              </div>
              <div className="space-y-1 max-h-80 overflow-y-auto" data-testid="service-refs-list">
                {(svcData.service_refs || []).length === 0 && (
                  <div className="text-xs text-gray-500 py-4 text-center">No references found, may be a read-only log collection.</div>
                )}
                {(svcData.service_refs || []).map((h, i) => (
                  <div
                    key={`${h.file}-${h.line}-${i}`}
                    className="flex items-start gap-3 py-1.5 px-2 rounded hover:bg-gray-900/60 text-xs"
                  >
                    <div className="font-mono text-blue-400 w-48 flex-shrink-0 truncate" title={h.file}>
                      {h.file}
                    </div>
                    <div className="text-gray-500 w-10 flex-shrink-0">:{h.line}</div>
                    <div className="text-gray-300 font-mono truncate" title={h.snippet}>{h.snippet}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && errData && (
            <div>
              <h3 className="text-sm font-semibold text-gray-100 flex items-center gap-2 mb-3">
                <AlertTriangle className="size-4 text-amber-400" />
                Recent errors touching this collection
              </h3>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-gray-900/60 rounded p-3 border border-gray-800">
                  <div className="text-gray-500 uppercase tracking-wide">Client errors</div>
                  <div className="text-2xl font-bold text-gray-100 mt-1">{errData.counts?.client_errors || 0}</div>
                </div>
                <div className="bg-gray-900/60 rounded p-3 border border-gray-800">
                  <div className="text-gray-500 uppercase tracking-wide">Stem-Fix tickets</div>
                  <div className="text-2xl font-bold text-gray-100 mt-1">{errData.counts?.stem_fixes || 0}</div>
                </div>
              </div>
              {(errData.client_errors || []).slice(0, 5).map((e, i) => (
                <div key={i} className="mt-2 text-xs bg-gray-900/40 rounded p-2 border-l-2 border-red-500/50">
                  <div className="text-gray-300 font-mono truncate">{e.message || "—"}</div>
                  <div className="text-gray-500 mt-0.5">{e.classification} · {e.status_code || "?"} · {formatRelative(e.created_at)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-gray-800 flex justify-end gap-2">
          <button
            data-testid="go-stem-fix-btn"
            onClick={() => navigate("/admin/stem-fix")}
            className="px-3 py-1.5 text-xs rounded bg-purple-600/20 text-purple-300 border border-purple-600/40 hover:bg-purple-600/30 flex items-center gap-1"
          >
            <Zap className="size-3" /> Open Stem-Fix Queue
          </button>
          <button
            data-testid="go-root-command-btn"
            onClick={() => navigate("/admin/root-command")}
            className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-300 border border-blue-600/40 hover:bg-blue-600/30 flex items-center gap-1"
          >
            <Activity className="size-3" /> Root Command
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Inter-Pillar Wiring: Global Flow Map ──────────────────────── */
const WIRE_COLOR = { green: "#22C55E", yellow: "#F59E0B", red: "#EF4444", idle: "#4B5563" };

function WiresFlowMap({ wires, onOpenTrace }) {
  if (!wires || wires.length === 0) return null;
  return (
    <div
      data-testid="wires-flow-map"
      className="mb-5 rounded-lg border border-gray-800 bg-gray-900/40 p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-widest text-amber-400 font-semibold">
            Inter-Pillar Wiring · Global Flow Map
          </span>
          <span className="text-[10px] text-gray-500">Click a wire to trace</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1"><StatusDot status="green" size={7} /> healthy</span>
          <span className="flex items-center gap-1"><StatusDot status="yellow" size={7} /> slow</span>
          <span className="flex items-center gap-1"><StatusDot status="red" size={7} /> broken</span>
          <span className="flex items-center gap-1">
            <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: WIRE_COLOR.idle }} /> idle
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-1.5">
        {wires.map((w) => (
          <button
            key={w.id}
            data-testid={`wire-row-${w.id}`}
            onClick={() => onOpenTrace(w)}
            className="flex items-center justify-between gap-3 px-3 py-2 rounded hover:bg-gray-900/70 text-left transition-colors"
            style={{ borderLeft: `3px solid ${WIRE_COLOR[w.status] || WIRE_COLOR.idle}` }}
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 flex-shrink-0">
                {(w.source_pillar || "").replace("_", "").toUpperCase().slice(0, 2)}
              </span>
              <div className="relative flex items-center flex-1 min-w-[120px]">
                <div
                  className="h-0.5 flex-1"
                  style={{
                    background: WIRE_COLOR[w.status] || WIRE_COLOR.idle,
                    boxShadow: w.status === "red"
                      ? `0 0 8px ${WIRE_COLOR.red}`
                      : w.status === "yellow" ? `0 0 6px ${WIRE_COLOR.yellow}` : "none",
                    animation: w.status === "red" || w.status === "yellow"
                      ? "wireFlow 1.2s linear infinite" : "none",
                  }}
                />
                <div
                  className="absolute left-1/2 -translate-x-1/2 size-2 rounded-full"
                  style={{
                    background: WIRE_COLOR[w.status] || WIRE_COLOR.idle,
                    boxShadow: `0 0 8px ${WIRE_COLOR[w.status] || WIRE_COLOR.idle}`,
                  }}
                />
              </div>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 flex-shrink-0">
                {(w.target_pillar || "").replace("_", "").toUpperCase().slice(0, 2)}
              </span>
              <div className="flex flex-col min-w-0 flex-1 ml-2">
                <span className="text-xs text-gray-200 font-semibold truncate">{w.label}</span>
                <span className="text-[10px] text-gray-500 truncate">{w.reason}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {w.lag_seconds !== null && w.lag_seconds !== undefined && (
                <span className="text-[10px] font-mono text-gray-400">
                  lag {w.lag_seconds}s
                </span>
              )}
              <StatusDot status={w.status === "idle" ? "green" : w.status} size={10}
                         pulse={w.status === "red"} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ─── Wiring Trace Modal ────────────────────────────────────────── */
function WireTraceModal({ wire, onClose }) {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!wire) return;
    const ac = new AbortController();
    (async () => {
      setLoading(true); setErr("");
      try {
        const res = await safeFetchJson(`${API}/api/admin/pillars-map/wire/${wire.id}/trace`,
                              { headers: authHeaders(), signal: ac.signal });
        if (!res.ok) {
          if (res.isGatewayError) {
            setErr(`Backend gateway unreachable (HTTP ${res.status || "—"})`);
          } else {
            setErr(res.error);
          }
          return;
        }
        setTrace(res.data);
      } catch (e) {
        if (e.name !== "AbortError") setErr(String(e));
      } finally {
        setLoading(false);
      }
    })();
    return () => ac.abort();
  }, [wire]);

  if (!wire) return null;
  const status = wire.status || "idle";
  return (
    <div
      data-testid="wire-trace-backdrop"
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        data-testid="wire-trace-modal"
        className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{ borderTop: `4px solid ${WIRE_COLOR[status]}` }}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div>
            <div className="text-xs uppercase tracking-widest" style={{ color: WIRE_COLOR[status] }}>
              Wiring Trace · {status.toUpperCase()}
            </div>
            <h2 className="text-lg font-semibold text-gray-100 mt-1">{wire.label}</h2>
            <div className="text-xs text-gray-500 mt-0.5 font-mono">
              {wire.source_pillar} <span className="mx-1">›</span> {wire.target_pillar}
            </div>
          </div>
          <button
            data-testid="wire-trace-close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-100 p-2"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="overflow-y-auto p-5 space-y-5">
          {loading && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="size-6 text-gray-400 animate-spin" />
            </div>
          )}
          {err && <div className="text-red-400 text-sm">{err}</div>}

          {trace && (
            <>
              <div
                data-testid="wire-trace-text"
                className="rounded-lg p-4 border"
                style={{
                  background: status === "red" ? "rgba(239,68,68,0.08)" :
                              status === "yellow" ? "rgba(245,158,11,0.08)" :
                              status === "idle" ? "rgba(75,85,99,0.10)" :
                                                  "rgba(34,197,94,0.08)",
                  borderColor: `${WIRE_COLOR[status]}40`,
                }}
              >
                <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Diagnosis</div>
                <p className="text-sm text-gray-100 leading-relaxed">{trace.trace}</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
                    Source · <span className="font-mono text-gray-300">{wire.source_collection}</span>
                  </div>
                  <div className="text-[10px] text-gray-500">Last 5 doc timestamps:</div>
                  <div className="mt-1 space-y-0.5 font-mono text-[11px] text-gray-300">
                    {(trace.source_recent_docs || []).length === 0
                      ? <div className="text-gray-600">— no docs —</div>
                      : (trace.source_recent_docs || []).map((d, i) => (
                        <div key={i} className="truncate">{d.ts || d.error || "—"}</div>
                      ))}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">
                    Target · <span className="font-mono text-gray-300">{wire.target_collection}</span>
                  </div>
                  <div className="text-[10px] text-gray-500">Last 5 doc timestamps:</div>
                  <div className="mt-1 space-y-0.5 font-mono text-[11px] text-gray-300">
                    {(trace.target_recent_docs || []).length === 0
                      ? <div className="text-gray-600">— no docs —</div>
                      : (trace.target_recent_docs || []).map((d, i) => (
                        <div key={i} className="truncate">{d.ts || d.error || "—"}</div>
                      ))}
                  </div>
                </div>
              </div>

              {wire.description && (
                <div className="text-xs text-gray-500 italic border-l-2 border-gray-800 pl-3">
                  {wire.description}
                </div>
              )}
            </>
          )}
        </div>

        <div className="px-5 py-3 border-t border-gray-800 text-xs text-gray-500 flex justify-between items-center">
          <span>
            Tolerance: <span className="text-gray-300 font-mono">{wire.lag_seconds ?? "—"}s</span>{" "}
            · Activity window: <span className="text-gray-300 font-mono">{wire.activity_minutes ?? "—"}m</span>
          </span>
          <span>
            {wire.src_last_write && <>src: {formatRelative(wire.src_last_write)} · </>}
            {wire.tgt_last_write && <>tgt: {formatRelative(wire.tgt_last_write)}</>}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ─── System Interface Flows (Admin + Customer) — "Main-Screen X-Ray" ─── */
function PulseBadge({ label, data, testId }) {
  const st = data?.status || "yellow";
  const http = data?.http_status;
  return (
    <span
      data-testid={testId}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gray-900/70 border border-gray-800"
      title={data?.reason || ""}
    >
      <StatusDot status={st} size={7} pulse={st === "red"} />
      <span className="text-[10px] font-bold text-gray-400">{label}</span>
      {typeof http === "number" && (
        <span className="text-[9px] font-mono text-gray-500">{http}</span>
      )}
    </span>
  );
}

function FlowRow({ flow, testId }) {
  const tp = flow.triple_pulse || {};
  return (
    <div
      data-testid={testId}
      className="flex items-center gap-3 py-2 px-3 rounded hover:bg-gray-900/60 transition-colors"
      style={{
        borderLeft: `3px solid ${
          flow.status === "red" ? "#EF4444" :
          flow.status === "yellow" ? "#F59E0B" : "#22C55E"
        }`,
      }}
    >
      <StatusDot status={flow.status} size={9} pulse={flow.status === "red"} />
      <div className="min-w-0 flex-1">
        <div className="text-sm text-gray-100 font-semibold truncate">{flow.label}</div>
        <div className="text-[10px] font-mono text-gray-500 truncate">
          {flow.fe_route} <span className="text-gray-700 mx-1">·</span> {flow.be_endpoint}
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <PulseBadge label="DB" data={tp.db}       testId={`flow-${flow.id}-db`} />
        <PulseBadge label="BE" data={tp.backend}  testId={`flow-${flow.id}-be`} />
        <PulseBadge label="FE" data={tp.frontend} testId={`flow-${flow.id}-fe`} />
      </div>
    </div>
  );
}

function SystemFlowsPanel({ flows }) {
  if (!flows || flows.length === 0) return null;
  const admin = flows.filter((f) => f.surface === "admin");
  const customer = flows.filter((f) => f.surface === "customer");
  const red = flows.filter((f) => f.status === "red").length;
  const yellow = flows.filter((f) => f.status === "yellow").length;

  return (
    <div
      data-testid="system-flows-panel"
      className="mb-5 rounded-lg border border-gray-800 bg-gray-900/40 p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-widest text-amber-400 font-semibold">
            System Interface Flows · Main-Screen X-Ray
          </span>
          <span className="text-[10px] text-gray-500">DB · BE · FE per critical route</span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          {red > 0 && (
            <span className="px-2 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-800/50">
              {red} red
            </span>
          )}
          {yellow > 0 && (
            <span className="px-2 py-0.5 rounded bg-amber-900/40 text-amber-300 border border-amber-800/50">
              {yellow} yellow
            </span>
          )}
          {red === 0 && yellow === 0 && (
            <span className="px-2 py-0.5 rounded bg-green-900/40 text-green-300 border border-green-800/50">
              all green
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div data-testid="flows-admin-col">
          <div className="text-[10px] uppercase tracking-widest text-gray-500 font-semibold mb-2 px-1">
            ▸ Admin Panel ({admin.length})
          </div>
          <div className="space-y-1">
            {admin.map((f) => (
              <FlowRow key={f.id} flow={f} testId={`flow-row-${f.id}`} />
            ))}
          </div>
        </div>
        <div data-testid="flows-customer-col">
          <div className="text-[10px] uppercase tracking-widest text-gray-500 font-semibold mb-2 px-1">
            ▸ Customer Portal ({customer.length})
          </div>
          <div className="space-y-1">
            {customer.map((f) => (
              <FlowRow key={f.id} flow={f} testId={`flow-row-${f.id}`} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


/* ─── Endpoint Evidence Audit Panel (iter 275) ─── */
const TIER_LABELS = {
  T0_infra:                 "Infra",
  T1_P1_acquisition:        "P1 Acquisition",
  T1_P2_monetization:       "P2 Monetization",
  T1_P3_sentinel:           "P3 Sentinel",
  T1_P4_cognition:          "P4 Cognition",
  T2_subproduct_free_apis:  "Sub · Free APIs",
  T2_subproduct_aurem_ai:   "Sub · Aurem AI",
  T2_subproduct_daily_intel:"Sub · Daily Intel",
  T2_subproduct_builder:    "Sub · Builder",
  T2_subproduct_live_support:"Sub · Live Support",
  T2_subproduct_owner_panel:"Sub · Owner Panel",
  T2_subproduct_universal:  "Sub · Universal",
  T2_subproduct_tier1:      "Sub · Tier1",
  T2_subproduct_customer_portal:"Sub · Customer Portal",
  T2_subproduct_vanguard:   "Sub · Vanguard",
  T2_subproduct_omnidim:    "Sub · OmniDim",
  T2_subproduct_aurem_suite:"Sub · Aurem Suite",
  T3_experimental:          "R&D",
  T4_unclassified:          "Unclassified",
};
const DIGNITY_COLORS = { alive: "#22C55E", ghost: "#F59E0B", leaky: "#EF4444", dead: "#6B7280" };

function DignityBar({ dist, total }) {
  const segs = [
    { k: "alive", c: DIGNITY_COLORS.alive },
    { k: "ghost", c: DIGNITY_COLORS.ghost },
    { k: "leaky", c: DIGNITY_COLORS.leaky },
    { k: "dead",  c: DIGNITY_COLORS.dead  },
  ];
  return (
    <div className="flex h-1.5 w-full rounded-full overflow-hidden bg-gray-800" title={`alive ${dist.alive} · ghost ${dist.ghost} · leaky ${dist.leaky} · dead ${dist.dead}`}>
      {segs.map((s) => {
        const pct = total > 0 ? (dist[s.k] / total) * 100 : 0;
        return pct > 0 ? <span key={s.k} style={{ width: `${pct}%`, background: s.c }} /> : null;
      })}
    </div>
  );
}

function EndpointAuditPanel() {
  const [data, setData] = React.useState(null);
  const [err, setErr]   = React.useState("");
  const [loading, setL] = React.useState(true);

  const load = React.useCallback(async () => {
    const res = await safeFetchJson(`${API}/api/admin/pillars-map/endpoint-audit/summary`, { headers: authHeaders() });
    if (!res.ok) {
      setErr(res.isGatewayError
        ? `Backend gateway unreachable (HTTP ${res.status || "—"})`
        : res.error);
    } else {
      setData(res.data);
      setErr("");
    }
    setL(false);
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const totals = data?.totals;
  const tiers = data?.tier_summary ? [...data.tier_summary].sort((a, b) => b.endpoint_count - a.endpoint_count) : [];

  return (
    <div
      data-testid="endpoint-audit-panel"
      className="mb-5 rounded-lg border border-gray-800 bg-gray-900/40 p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileCode className="size-4 text-blue-400" />
          <span className="text-xs uppercase tracking-widest text-blue-400 font-semibold">
            Endpoint Governance · Evidence Classifier
          </span>
          {totals && (
            <span className="text-[10px] text-gray-500">
              {totals.endpoints} endpoints · {totals.with_audit} with audit · {totals.with_surface} with UI surface
            </span>
          )}
        </div>
        {data?.cached && <span className="text-[10px] text-gray-600">cached</span>}
      </div>

      {loading && <div className="text-xs text-gray-500 py-3">Classifying…</div>}
      {err && !data && <div className="text-xs text-red-400 py-3">{err}</div>}

      {totals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {["alive", "ghost", "leaky", "dead"].map((k) => (
            <div
              key={k}
              data-testid={`dignity-${k}`}
              className="rounded border border-gray-800 bg-black/30 px-3 py-2"
              style={{ borderLeft: `3px solid ${DIGNITY_COLORS[k]}` }}
            >
              <div className="text-[10px] uppercase tracking-widest text-gray-500">{k}</div>
              <div className="text-lg font-bold font-mono" style={{ color: DIGNITY_COLORS[k] }}>
                {totals.by_dignity[k]}
              </div>
            </div>
          ))}
        </div>
      )}

      {tiers.length > 0 && (
        <div className="space-y-1" data-testid="tier-rows">
          {tiers.map((t) => (
            <div
              key={t.tier}
              data-testid={`tier-${t.tier}`}
              className="grid grid-cols-12 gap-2 items-center px-2 py-1.5 rounded hover:bg-gray-900/60 text-xs"
            >
              <div className="col-span-3 truncate">
                <span className="font-semibold text-gray-200">{TIER_LABELS[t.tier] || t.tier}</span>
              </div>
              <div className="col-span-1 font-mono text-gray-300 text-right">{t.endpoint_count}</div>
              <div className="col-span-3"><DignityBar dist={t.dignity} total={t.endpoint_count} /></div>
              <div className="col-span-2 font-mono text-[10px] text-gray-500 text-right">
                {t.total_hits_30d.toLocaleString()} hits/30d
              </div>
              <div className="col-span-3 text-[10px] text-gray-500 truncate">
                {(t.top_routers || []).slice(0, 3).join(" · ")}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ─── Dev Stack Section (iter 322ar) ─────────────────────────────── */
function DevStackSection() {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const res = await safeFetchJson(`${API}/api/admin/dev-stack/health`, { headers: authHeaders() });
      if (!cancelled && res.ok) setData(res.data);
      if (!cancelled) setLoading(false);
    };
    tick();
    const id = setInterval(tick, 20000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const components = data?.components || [];
  const summary = data?.summary || { total: 0, green: 0, red: 0 };

  return (
    <div
      data-testid="dev-stack-section"
      className="mb-5 rounded-lg border border-gray-800 bg-gray-900/40 p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Server className="size-4 text-emerald-400" />
          <span className="text-xs uppercase tracking-widest text-emerald-400 font-semibold">
            Dev Stack Health · Live (auto-refresh 20s)
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-800/50">
            {summary.green}/{summary.total} green
          </span>
          {summary.red > 0 && (
            <span className="px-2 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-800/50">
              {summary.red} red
            </span>
          )}
        </div>
      </div>

      {loading && <div className="text-xs text-gray-500 py-3">Loading stack health…</div>}

      {!loading && components.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {components.map((c, i) => {
            const ok = c.status === "green";
            return (
              <div
                key={i}
                data-testid={`dev-stack-${i}`}
                className="rounded border px-3 py-2"
                style={{
                  background: ok ? "rgba(34,197,94,0.05)" : "rgba(239,68,68,0.05)",
                  borderColor: ok ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)",
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <StatusDot status={c.status} size={8} pulse={!ok} />
                  <span className="text-xs font-semibold text-gray-200 truncate">{c.name}</span>
                </div>
                {c.detail && (
                  <div className="text-[10px] text-gray-500 truncate" title={c.detail}>
                    {c.detail}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


/* ─── Page ──────────────────────────────────────────────────────── */
export default function AdminPillarsMap() {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [openPillar, setOpenPillar] = useState(null);
  const [openCollection, setOpenCollection] = useState(null);
  const [openWire, setOpenWire] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(null);

  const load = useCallback(async () => {
    setErr("");
    const res = await safeFetchJson(`${API}/api/admin/pillars-map/heartbeat`, { headers: authHeaders() });
    if (!res.ok) {
      setErr(res.isGatewayError
        ? `Backend gateway unreachable (HTTP ${res.status || "—"}). Origin may be restarting — auto-retrying every 10s.`
        : res.error);
    } else {
      setSnapshot(res.data);
    }
    setLoading(false);
  }, []);

  // iter 280.3 — Force-sync: POST /sync purges cache, rebuilds live snapshot,
  // then /heartbeat will return served_from:"live" for the next tick.
  const forceSync = useCallback(async () => {
    setSyncing(true);
    try {
      const res = await safeFetchJson(`${API}/api/admin/pillars-map/sync`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) {
        setErr(res.isGatewayError
          ? `Sync failed: backend gateway HTTP ${res.status || "—"}`
          : `sync ${res.error}`);
        return;
      }
      setLastSync({
        at: new Date().toISOString(),
        overall: res.data.overall_status,
        sentinel: res.data.sentinel_overlay,
      });
      await load();
    } finally {
      setSyncing(false);
    }
  }, [load]);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const overall = snapshot?.overall_status;
  const totals = snapshot?.totals || {};
  const servedFrom = snapshot?.served_from || (snapshot?.cached ? "cache" : "live");
  const cacheAge = snapshot?.cached_age_sec || 0;
  const stale = !!snapshot?.stale;
  const sentinelOverlay = snapshot?.sentinel_overlay;

  const openPillarObj = useMemo(() => {
    if (!openPillar || !snapshot) return null;
    return snapshot.pillars.find(p => p.key === openPillar) || null;
  }, [openPillar, snapshot]);

  return (
    <div data-testid="admin-pillars-map" className="min-h-screen bg-gray-950 text-gray-100 pb-20">
      <MissionControlRibbon />
      <style>{`
        .pulse-dot { animation: pulseDot 1.4s ease-in-out infinite; }
        @keyframes pulseDot {
          0%,100% { transform: scale(1); opacity: 1; }
          50%     { transform: scale(1.4); opacity: 0.55; }
        }
        @keyframes wireFlow {
          0%   { background-position: 0px 0; }
          100% { background-position: 20px 0; }
        }
      `}</style>

      <div className="max-w-7xl mx-auto px-6 pt-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-amber-400 flex items-center gap-2">
              <span>Deep-Drill Diagnostic</span>
              <span className="text-gray-600">·</span>
              <BuildBadge />
            </div>
            <h1 className="text-3xl font-bold text-gray-100 mt-1 flex items-center gap-3">
              <Database className="size-7 text-amber-400" />
              Pillars Map
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Pillar <span className="text-gray-500">›</span> Collection <span className="text-gray-500">›</span> Service, silent-failure aware (15 min write window)
            </p>
          </div>
          <div className="flex items-center gap-3">
            {overall && <StatusBadge status={overall} testId="overall-status-badge" />}
            <button
              data-testid="refresh-btn"
              onClick={load}
              className="text-xs flex items-center gap-1 text-gray-300 hover:text-gray-100 px-3 py-1.5 rounded border border-gray-800 bg-gray-900/60"
            >
              <RefreshCw className="size-3" /> Refresh
            </button>
            <button
              data-testid="sync-pillars-now-btn"
              onClick={forceSync}
              disabled={syncing}
              title="Purge cache + rebuild live snapshot — makes Console & Map agree instantly"
              className="text-xs flex items-center gap-1.5 text-amber-200 hover:text-amber-100 px-3 py-1.5 rounded border border-amber-700/50 bg-amber-900/20 disabled:opacity-50"
            >
              <RefreshCw className={`size-3 ${syncing ? "animate-spin" : ""}`} />
              {syncing ? "Syncing…" : "Sync Pillars Now"}
            </button>
          </div>
        </div>

        {/* iter 280.3 — Served-from indicator (transparency: cache vs live + age) */}
        {snapshot ? (
          <div
            data-testid="served-from-strip"
            className="mb-3 flex items-center gap-3 text-[11px] text-gray-400"
          >
            <span>
              Source:{" "}
              <span
                className={servedFrom === "live" ? "text-emerald-400" : stale ? "text-amber-400" : "text-gray-300"}
                data-testid="served-from-value"
              >
                {servedFrom}
              </span>
            </span>
            {servedFrom === "cache" ? (
              <span data-testid="cache-age">
                · cache age{" "}
                <span className={stale ? "text-amber-400" : "text-gray-300"}>
                  {Math.round(cacheAge)}s
                </span>
                {stale ? " (STALE — hit Sync)" : ""}
              </span>
            ) : null}
            {lastSync ? (
              <span className="text-emerald-400" data-testid="last-sync-label">
                · last sync {new Date(lastSync.at).toLocaleTimeString()} → {lastSync.overall}
              </span>
            ) : null}
          </div>
        ) : null}

        {/* iter 280.3 — Sentinel Overlay banner (makes Dev Console ↔ Map agree) */}
        {sentinelOverlay ? (
          <div
            data-testid="sentinel-overlay-banner"
            className={`mb-4 rounded-lg border p-3 text-sm ${
              sentinelOverlay.verdict === "red"
                ? "border-red-800/60 bg-red-950/30 text-red-200"
                : sentinelOverlay.verdict === "yellow"
                  ? "border-amber-800/60 bg-amber-950/30 text-amber-200"
                  : "border-gray-800 bg-gray-900/40 text-gray-300"
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              <span>Sentinel Overlay</span>
              <span className="text-[10px] uppercase tracking-widest">
                {sentinelOverlay.verdict}
              </span>
            </div>
            <div className="mt-1 text-xs">
              errors_1h:{" "}
              <span data-testid="sentinel-errors-1h" className="font-mono">
                {sentinelOverlay.errors_1h || 0}
              </span>{" "}
              · errors_24h:{" "}
              <span data-testid="sentinel-errors-24h" className="font-mono">
                {sentinelOverlay.errors_24h || 0}
              </span>{" "}
              · critical_alerts:{" "}
              <span data-testid="sentinel-critical-alerts" className="font-mono">
                {sentinelOverlay.critical_alerts || 0}
              </span>
              <span className="text-gray-500">
                {" "}
                (warm@{sentinelOverlay.warm_threshold_1h} · hot@{sentinelOverlay.hot_threshold_1h})
              </span>
            </div>
            {sentinelOverlay.reason ? (
              <div className="mt-0.5 text-[11px] text-gray-400">
                Reason: {sentinelOverlay.reason}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* iter 280.2 — Deploy Drift Panel (always visible at top) */}
        <div className="mb-6">
          <DeployStatusPanel />
        </div>

        {/* iter 285.4 — Transparency Wall (top-level trust card) */}
        <div className="mb-6">
          <TransparencyWall />
        </div>

        {/* iter 285.8 — Master Autopilot · Morning Blast (HERO CTA) */}
        <div className="mb-6">
          <AutopilotMasterButton />
        </div>

        {/* iter 285.6 — Empire HUD · Sovereign Map */}
        <div className="mb-6">
          <EmpireHUDMap />
        </div>

        {/* iter 285.4 — MTTH metric card */}
        <div className="mb-6">
          <MTTHCard />
        </div>

        {/* iter 281 — Autonomous Repair Engine live feed */}
        <div className="mb-6">
          <AutonomousRepairPanel />
        </div>

        {/* iter 285 — Auto-Heal Bridge · Pending Code Fixes approval queue */}
        <div className="mb-6">
          <PendingCodeFixesPanel />
        </div>

        {/* iter 281.2 — ORA Dev Console (Phase 2.2 — Sovereign Brain) */}
        <div className="mb-6">
          <OraDevConsole />
        </div>

        {/* iter 281.5 — ORA Sovereign Customer Handler (Phase 2.5) */}
        <div className="mb-6">
          <OraPhase25Panel />
        </div>

        {/* iter 283 — Truth Ledger (Honesty DNA) */}
        <div className="mb-6">
          <TruthLedgerPanel />
        </div>

        {loading && !snapshot && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="size-6 text-gray-400 animate-spin" />
            <span className="ml-3 text-gray-400">Loading pillar telemetry…</span>
          </div>
        )}

        {err && !snapshot && (
          <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
            {err}
          </div>
        )}

        {snapshot && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
                <div className="text-xs uppercase tracking-widest text-gray-500">Collections</div>
                <div className="text-2xl font-bold text-gray-100 mt-1">{totals.collections || 0}</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
                <div className="text-xs uppercase tracking-widest text-gray-500">Silent fails</div>
                <div className="text-2xl font-bold mt-1" style={{ color: totals.silent_failures ? "#EF4444" : "#22C55E" }}>
                  {totals.silent_failures || 0}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
                <div className="text-xs uppercase tracking-widest text-gray-500">Backend red</div>
                <div className="text-2xl font-bold mt-1" style={{ color: totals.backend_red ? "#EF4444" : "#22C55E" }}>
                  {totals.backend_red || 0}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
                <div className="text-xs uppercase tracking-widest text-gray-500">Unreachable</div>
                <div className="text-2xl font-bold mt-1" style={{ color: totals.unreachable ? "#EF4444" : "#22C55E" }}>
                  {totals.unreachable || 0}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4" data-testid="kpi-wires-broken">
                <div className="text-xs uppercase tracking-widest text-gray-500">Broken wires</div>
                <div className="text-2xl font-bold mt-1" style={{ color: totals.wires_red ? "#EF4444" : "#22C55E" }}>
                  {totals.wires_red || 0}
                  <span className="text-xs text-gray-500 ml-1">/ {totals.wires_total || 0}</span>
                </div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4" data-testid="kpi-flows-broken">
                <div className="text-xs uppercase tracking-widest text-gray-500">Broken flows</div>
                <div className="text-2xl font-bold mt-1" style={{ color: totals.flows_red ? "#EF4444" : (totals.flows_yellow ? "#F59E0B" : "#22C55E") }}>
                  {totals.flows_red || 0}
                  <span className="text-xs text-gray-500 ml-1">/ {totals.flows_total || 0}</span>
                </div>
              </div>
            </div>

            <div className="mb-5 flex flex-wrap items-center gap-3 text-xs text-gray-400 border border-gray-800 rounded-lg bg-gray-900/40 p-3" data-testid="triple-pulse-legend">
              <span className="uppercase tracking-widest text-gray-500 font-semibold">Triple-Pulse</span>
              <span className="flex items-center gap-1"><StatusDot status="green" size={8} /> <b className="text-gray-300">DB</b> = last_write_at fresh (&lt;15m)</span>
              <span className="flex items-center gap-1"><StatusDot status="green" size={8} /> <b className="text-gray-300">BE</b> = mapped scheduler alive</span>
              <span className="flex items-center gap-1"><StatusDot status="green" size={8} /> <b className="text-gray-300">FE</b> = /heartbeat 200 OK</span>
              <span className="text-gray-600">·  red pulse = silent failure · worst-of-three wins</span>
            </div>

            <SystemFlowsPanel flows={snapshot.flows || []} />

            <DevStackSection />

            <EndpointAuditPanel />

            <WiresFlowMap wires={snapshot.wires || []} onOpenTrace={(w) => setOpenWire(w)} />

            <div data-testid="pillars-grid" className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {snapshot.pillars.map((p) => (
                <PillarCard key={p.key} pillar={p} onOpen={() => setOpenPillar(p.key)} />
              ))}
            </div>

            <div className="mt-5 text-xs text-gray-600 flex items-center gap-2">
              <Server className="size-3" />
              snapshot {snapshot.cached ? "cached" : "live"} · generated {formatRelative(snapshot.generated_at)} · auto-refresh {POLL_INTERVAL_MS / 1000}s
            </div>
          </>
        )}
      </div>

      {openPillarObj && (
        <CollectionModal
          pillar={openPillarObj}
          onClose={() => setOpenPillar(null)}
          onOpenCollection={(row) => setOpenCollection(row)}
        />
      )}
      {openCollection && (
        <ServiceModal
          collection={openCollection}
          onClose={() => setOpenCollection(null)}
        />
      )}
      {openWire && (
        <WireTraceModal
          wire={openWire}
          onClose={() => setOpenWire(null)}
        />
      )}
    </div>
  );
}
