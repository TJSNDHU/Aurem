/**
 * MorningBriefMobile.jsx — iter 326gg-UI (Phase 3 P3.2 — mobile PWA route)
 *
 * Standalone, big-text, mobile-first morning brief. Designed for the
 * founder to open at 7am on their phone and see yesterday's numbers
 * in one glance. No app chrome, no navigation — just the brief.
 *
 * Route: /admin/morning-brief
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const _sev = (s) => {
  if (s === "critical") return "bg-rose-500/20 text-rose-200 border-rose-500/40";
  if (s === "warning") return "bg-amber-500/20 text-amber-200 border-amber-500/40";
  return "bg-zinc-700/40 text-zinc-200 border-zinc-600/40";
};

export default function MorningBriefMobile() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`${API}/api/admin/ora/morning-brief`, {
        headers: { Authorization: `Bearer ${_getAdminToken()}` },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const camp = data?.campaigns || {};
  const alerts = Array.isArray(data?.alerts) ? data.alerts : [];
  const focus = Array.isArray(data?.focus_leads) ? data.focus_leads : [];
  const decisions = Array.isArray(data?.decisions) ? data.decisions : [];

  return (
    <div
      className="min-h-screen bg-zinc-950 text-zinc-100"
      data-testid="morning-brief-mobile"
    >
      <div className="max-w-md mx-auto px-5 py-6">
        <header className="mb-5">
          <div className="text-xs uppercase tracking-widest text-emerald-400">
            Morning Brief
          </div>
          <div
            className="text-3xl font-semibold mt-1"
            data-testid="morning-brief-mobile-date"
          >
            {data?.date || "—"}
          </div>
          {error ? (
            <div
              className="text-xs text-rose-300 mt-2"
              data-testid="morning-brief-mobile-error"
            >
              {error}
            </div>
          ) : null}
        </header>

        {/* Headline numbers — huge */}
        <section
          className="grid grid-cols-3 gap-3 mb-6"
          data-testid="morning-brief-mobile-kpis"
        >
          <div className="bg-zinc-900/60 rounded-xl p-4">
            <div className="text-3xl font-bold tabular-nums">
              {(camp.sent || 0).toLocaleString()}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">sent</div>
          </div>
          <div className="bg-zinc-900/60 rounded-xl p-4">
            <div className="text-3xl font-bold tabular-nums text-emerald-300">
              {(camp.replies || 0).toLocaleString()}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">replies</div>
          </div>
          <div className="bg-zinc-900/60 rounded-xl p-4">
            <div className="text-3xl font-bold tabular-nums">
              {(camp.leads_blasted || 0).toLocaleString()}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">leads</div>
          </div>
        </section>

        {/* Alerts — only render if there are any */}
        {alerts.length > 0 ? (
          <section className="mb-6" data-testid="morning-brief-mobile-alerts">
            <h2 className="text-xs uppercase tracking-widest text-zinc-500 mb-2">
              Needs your attention ({alerts.length})
            </h2>
            <div className="space-y-2">
              {alerts.map((a, i) => (
                <div
                  key={i}
                  className={`rounded-lg border p-3 ${_sev(a.severity)}`}
                >
                  <div className="text-sm font-medium">{a.title}</div>
                  <div className="text-[11px] opacity-70 mt-0.5">
                    {a.source} · {a.severity}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {/* Today's focus leads */}
        {focus.length > 0 ? (
          <section className="mb-6" data-testid="morning-brief-mobile-focus">
            <h2 className="text-xs uppercase tracking-widest text-zinc-500 mb-2">
              Today's focus leads ({focus.length})
            </h2>
            <div className="space-y-2">
              {focus.slice(0, 10).map((l) => (
                <div
                  key={l.lead_id}
                  className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-3"
                >
                  <div className="text-sm font-medium text-zinc-100">
                    {l.business_name || l.lead_id}
                  </div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">
                    {[l.city, l.industry, l.status].filter(Boolean).join(" · ")}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {/* Recent ORA decisions — what happened overnight */}
        {decisions.length > 0 ? (
          <section className="mb-6" data-testid="morning-brief-mobile-decisions">
            <h2 className="text-xs uppercase tracking-widest text-zinc-500 mb-2">
              ORA did overnight
            </h2>
            <div className="space-y-2">
              {decisions.map((d, i) => (
                <div
                  key={i}
                  className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-3"
                >
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
                    {d.outcome?.replace("_", " ")} · {d.tool}
                  </div>
                  <div className="text-sm text-zinc-200 line-clamp-2">
                    {d.summary}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <button
          type="button"
          onClick={load}
          disabled={loading}
          data-testid="morning-brief-mobile-refresh"
          className="w-full mt-4 py-3 rounded-lg bg-zinc-100 text-zinc-900 text-sm font-semibold disabled:opacity-40"
        >
          {loading ? "loading…" : "Refresh brief"}
        </button>

        <div className="text-center text-[10px] text-zinc-600 mt-6">
          generated {data?.generated_at?.slice(11, 19) || "—"} UTC
        </div>
      </div>
    </div>
  );
}
