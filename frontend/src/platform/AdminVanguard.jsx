/**
 * AdminVanguard.jsx — iter 277
 *
 * Dedicated admin surface for the Vanguard Sub-Product SKU.
 *
 * Why: `aurem_vanguard_router` shipped 8 endpoints doing 7,884+ hits/30d
 * on production, but had no dedicated admin UI. Evidence says customers
 * are actively using it — time to make it first-class.
 *
 * Data source: `/api/admin/pillars-map/subproduct/T2_subproduct_vanguard`
 * (iter 277 endpoint on endpoint_audit_router).
 */
import React, { useEffect, useState } from "react";
import { Shield, Activity, AlertTriangle, Zap, RefreshCw } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const DIGNITY_COLORS = {
  alive: "#22C55E",
  ghost: "#F59E0B",
  leaky: "#EF4444",
  dead:  "#6B7280",
};

function pct(n, total) {
  if (!total) return 0;
  return Math.round((n / total) * 100);
}

function MetricTile({ label, value, accent, hint, testId }) {
  return (
    <div
      className="rounded-lg border border-gray-800 bg-gray-900/40 p-4"
      data-testid={testId}
    >
      <div className="text-xs uppercase tracking-wider text-gray-500">
        {label}
      </div>
      <div
        className="mt-1 text-3xl font-light"
        style={{ color: accent || "#E5E7EB" }}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-xs text-gray-500">{hint}</div>
      ) : null}
    </div>
  );
}

function DignityBar({ dignity, total }) {
  const segs = ["alive", "ghost", "leaky", "dead"];
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-gray-800">
      {segs.map((k) => {
        const p = pct(dignity?.[k] || 0, total);
        return p > 0 ? (
          <span
            key={k}
            style={{ width: `${p}%`, background: DIGNITY_COLORS[k] }}
            title={`${k}: ${dignity[k]}`}
          />
        ) : null;
      })}
    </div>
  );
}

export default function AdminVanguard() {
  const [data, setData]     = useState(null);
  const [err, setErr]       = useState("");
  const [loading, setLoad]  = useState(false);

  const load = async () => {
    setLoad(true);
    setErr("");
    try {
      const r = await fetch(
        `${API}/api/admin/pillars-map/subproduct/T2_subproduct_vanguard`,
        { headers: authHeaders() }
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoad(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div
      className="min-h-screen bg-black px-6 py-8 text-gray-200"
      data-testid="admin-vanguard"
    >
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-amber-400">
              <Shield size={16} />
              <span className="text-xs uppercase tracking-[0.2em]">
                Sub-Product · iter 277
              </span>
            </div>
            <h1 className="mt-2 text-4xl font-light tracking-tight">
              Vanguard Swarm
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Elite First-Contact Crew · evidence-based dashboard
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            data-testid="vanguard-refresh-btn"
            className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            <RefreshCw
              size={14}
              className={loading ? "animate-spin" : ""}
            />
            Refresh
          </button>
        </div>

        {err ? (
          <div
            className="mb-4 rounded border border-red-800/50 bg-red-900/20 px-4 py-2 text-sm text-red-300"
            data-testid="vanguard-error"
          >
            {err}
          </div>
        ) : null}

        {/* Metrics */}
        {data ? (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricTile
                label="Endpoints"
                value={data.endpoint_count}
                accent="#60A5FA"
                testId="vanguard-metric-endpoints"
              />
              <MetricTile
                label="Hits · 30d"
                value={data.total_hits_30d?.toLocaleString()}
                accent="#22C55E"
                hint="Live production traffic"
                testId="vanguard-metric-hits"
              />
              <MetricTile
                label="Errors · 30d"
                value={data.error_count_30d || 0}
                accent={(data.error_count_30d || 0) > 0 ? "#EF4444" : "#6B7280"}
                testId="vanguard-metric-errors"
              />
              <MetricTile
                label="Alive / Total"
                value={`${data.dignity?.alive || 0} / ${data.endpoint_count}`}
                accent="#22C55E"
                hint={`${pct(
                  data.dignity?.alive || 0,
                  data.endpoint_count
                )}% fully wired`}
                testId="vanguard-metric-alive"
              />
            </div>

            {/* Dignity bar */}
            <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900/40 p-4">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="uppercase tracking-wider text-gray-500">
                  Dignity Rollup
                </span>
                <span className="text-gray-500">
                  alive {data.dignity?.alive || 0} · ghost{" "}
                  {data.dignity?.ghost || 0} · leaky{" "}
                  {data.dignity?.leaky || 0} · dead{" "}
                  {data.dignity?.dead || 0}
                </span>
              </div>
              <DignityBar
                dignity={data.dignity}
                total={data.endpoint_count}
              />
            </div>

            {/* Endpoint list */}
            <div className="mt-6 overflow-hidden rounded-lg border border-gray-800 bg-gray-900/40">
              <div className="border-b border-gray-800 px-4 py-3 text-xs uppercase tracking-wider text-gray-500">
                Endpoints · sorted by 30-day traffic
              </div>
              <table
                className="w-full text-sm"
                data-testid="vanguard-endpoints-table"
              >
                <thead className="bg-gray-900/60 text-left text-xs text-gray-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Method</th>
                    <th className="px-4 py-2 font-medium">Path</th>
                    <th className="px-4 py-2 font-medium">Dignity</th>
                    <th className="px-4 py-2 text-right font-medium">
                      Hits · 30d
                    </th>
                    <th className="px-4 py-2 font-medium">UI Refs</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.endpoints || []).map((e, i) => (
                    <tr
                      key={`${e.method}-${e.path}-${i}`}
                      className="border-t border-gray-800/70 hover:bg-gray-900/80"
                    >
                      <td className="px-4 py-2 font-mono text-xs text-gray-400">
                        {e.method}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-gray-200">
                        {e.path}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className="inline-block rounded-full px-2 py-0.5 text-[10px] uppercase"
                          style={{
                            background: `${DIGNITY_COLORS[e.dignity]}22`,
                            color: DIGNITY_COLORS[e.dignity],
                          }}
                        >
                          {e.dignity}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-xs">
                        {(e.hits_30d || 0).toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500">
                        {(e.surfaces || []).join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Monetization hook — LIVE SKU (iter 280) */}
            <div className="mt-6 rounded-lg border border-emerald-900/40 bg-emerald-900/10 p-4" data-testid="vanguard-revenue-cta">
              <div className="flex items-start gap-3">
                <Zap className="mt-0.5 text-emerald-400" size={18} />
                <div className="flex-1">
                  <div className="font-medium text-emerald-200">
                    Revenue Engine · LIVE
                  </div>
                  <div className="mt-1 text-sm text-emerald-100/80">
                    Vanguard is doing{" "}
                    <strong>{data.total_hits_30d?.toLocaleString()}</strong>{" "}
                    hits in 30 days. Packaged as{" "}
                    <strong>$49/mo add-on SKU</strong> (<code>security_vanguard</code>) —
                    Stripe-ready via the service catalog. Share the link with any
                    customer to one-click subscribe.
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <a
                      href="/my/website"
                      className="inline-flex items-center gap-1 rounded-md border border-emerald-600/50 bg-emerald-600/20 px-3 py-1.5 text-xs font-medium text-emerald-200 hover:bg-emerald-600/30"
                      data-testid="vanguard-subscribe-link"
                    >
                      → Customer Subscribe Page
                    </a>
                    <a
                      href="/admin/plans"
                      className="inline-flex items-center gap-1 rounded-md border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800"
                      data-testid="vanguard-catalog-link"
                    >
                      → Edit Price in Plans
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : loading ? (
          <div className="py-10 text-center text-gray-500">Loading…</div>
        ) : null}
      </div>
    </div>
  );
}
