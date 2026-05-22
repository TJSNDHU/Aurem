/**
 * EmailHealthCard.jsx — iter 326ee (Phase 3 P2.3)
 *
 * Compact admin card showing email channel health over the last 24h.
 * Sent / failed / success-rate, plus the top failure reasons so a
 * regression like the iter 326x `resend.logs` outage is visible at a
 * glance instead of buried in deploy logs.
 *
 * Backed by /api/admin/ora/email-health.
 *
 * Drop-in: <EmailHealthCard /> — no props required.
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const _verdictBadge = (verdict) => {
  const base =
    "inline-block text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border";
  if (verdict === "healthy")
    return `${base} bg-emerald-500/15 text-emerald-300 border-emerald-500/30`;
  if (verdict === "warning")
    return `${base} bg-amber-500/15 text-amber-300 border-amber-500/30`;
  if (verdict === "critical")
    return `${base} bg-rose-500/15 text-rose-300 border-rose-500/30`;
  return `${base} bg-zinc-700/40 text-zinc-300 border-zinc-600/40`;
};

export default function EmailHealthCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hours, setHours] = useState(24);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(
        `${API}/api/admin/ora/email-health?hours=${hours}`,
        { headers: { Authorization: `Bearer ${_getAdminToken()}` } }
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  const sent = data?.sent || 0;
  const failed = data?.failed || 0;
  const total = data?.total || 0;
  const rate = data?.success_rate;
  const verdict = data?.verdict || "no signal";
  const topErrors = Array.isArray(data?.top_errors) ? data.top_errors : [];

  const ratePct =
    rate == null ? "—" : `${Math.round(Number(rate) * 100)}%`;

  return (
    <div
      className="rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-100 p-4 shadow-sm"
      data-testid="email-health-card"
    >
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold tracking-wide text-zinc-200">
            Email Channel Health
          </h3>
          <span
            className={_verdictBadge(verdict)}
            data-testid="email-health-verdict"
          >
            {verdict.replace("_", " ")}
          </span>
        </div>
        <select
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          data-testid="email-health-window-select"
          className="bg-zinc-900 text-zinc-300 text-[11px] border border-zinc-700 rounded px-1.5 py-0.5"
        >
          <option value={1}>1h</option>
          <option value={24}>24h</option>
          <option value={72}>3d</option>
          <option value={168}>7d</option>
        </select>
      </div>

      {error ? (
        <div
          className="text-xs text-rose-300"
          data-testid="email-health-error"
        >
          Couldn't load email health: {error}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div>
              <div
                className="text-xl font-semibold text-emerald-300 tabular-nums"
                data-testid="email-health-sent"
              >
                {sent.toLocaleString()}
              </div>
              <div className="text-[11px] text-zinc-500">sent</div>
            </div>
            <div>
              <div
                className="text-xl font-semibold text-rose-300 tabular-nums"
                data-testid="email-health-failed"
              >
                {failed.toLocaleString()}
              </div>
              <div className="text-[11px] text-zinc-500">failed</div>
            </div>
            <div>
              <div
                className="text-xl font-semibold text-zinc-50 tabular-nums"
                data-testid="email-health-rate"
              >
                {ratePct}
              </div>
              <div className="text-[11px] text-zinc-500">
                success rate · {total.toLocaleString()} total
              </div>
            </div>
          </div>

          {topErrors.length > 0 ? (
            <div
              className="border-t border-zinc-800 pt-3"
              data-testid="email-health-errors-list"
            >
              <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2">
                Top failure reasons
              </div>
              <div className="space-y-1">
                {topErrors.slice(0, 5).map((e) => (
                  <div
                    key={e.error}
                    className="flex items-center justify-between text-[12px]"
                    data-testid="email-health-error-row"
                  >
                    <span
                      className="font-mono text-zinc-300 truncate pr-3"
                      title={e.error}
                    >
                      {e.error}
                    </span>
                    <span className="text-zinc-100 tabular-nums">
                      {e.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : failed === 0 && sent > 0 ? (
            <div
              className="text-xs text-emerald-400/80"
              data-testid="email-health-clean"
            >
              No failures in this window.
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
