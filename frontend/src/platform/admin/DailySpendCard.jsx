/**
 * DailySpendCard.jsx — iter 326w (Phase 3 P2.2)
 *
 * Compact admin card showing the last 7 days of ORA LLM spend with a
 * sparkline + per-provider rollup. Founder glance: "did I burn $50
 * overnight on a runaway ORA loop?". Backed by /api/admin/ora/cost-summary
 * (shipped in iter 326w; this is just the UI surface).
 *
 * Drop-in: <DailySpendCard /> — no props required.
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const _fmtUsd = (n) => {
  const v = Number(n || 0);
  if (v === 0) return "$0";
  if (v < 0.01) return "<$0.01";
  if (v < 1) return `$${v.toFixed(3)}`;
  return `$${v.toFixed(2)}`;
};

const _Sparkline = ({ values, color = "#34d399" }) => {
  if (!values || values.length === 0) return null;
  const max = Math.max(...values, 0.0001);
  const w = 120;
  const h = 28;
  const step = values.length > 1 ? w / (values.length - 1) : 0;
  const pts = values
    .map((v, i) => `${i * step},${h - (v / max) * h}`)
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      data-testid="daily-spend-sparkline"
      aria-hidden="true"
    >
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={pts}
      />
    </svg>
  );
};

export default function DailySpendCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [days, setDays] = useState(7);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(
        `${API}/api/admin/ora/cost-summary?days=${days}`,
        { headers: { Authorization: `Bearer ${_getAdminToken()}` } }
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  const total = data?.total_cost_usd || 0;
  const calls = data?.total_calls || 0;
  const daily = Array.isArray(data?.daily) ? data.daily : [];
  const providers = Array.isArray(data?.by_provider) ? data.by_provider : [];
  const sparkValues = daily.map((d) => Number(d.cost_usd || 0));

  // Spike detection — last day > 2× the median of prior days
  const sortedHistory = sparkValues.slice(0, -1).sort((a, b) => a - b);
  const median =
    sortedHistory.length === 0
      ? 0
      : sortedHistory[Math.floor(sortedHistory.length / 2)];
  const todaySpend = sparkValues[sparkValues.length - 1] || 0;
  const spiked = median > 0 && todaySpend > median * 2 && todaySpend > 0.05;

  return (
    <div
      className="rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-100 p-4 shadow-sm"
      data-testid="daily-spend-card"
    >
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold tracking-wide text-zinc-200">
            ORA LLM Spend
          </h3>
          {spiked ? (
            <span
              data-testid="daily-spend-spike-warning"
              className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-500/15 text-amber-300"
            >
              spike
            </span>
          ) : null}
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          data-testid="daily-spend-days-select"
          className="bg-zinc-900 text-zinc-300 text-[11px] border border-zinc-700 rounded px-1.5 py-0.5"
        >
          <option value={7}>7d</option>
          <option value={14}>14d</option>
          <option value={30}>30d</option>
        </select>
      </div>

      {error ? (
        <div
          className="text-xs text-rose-300"
          data-testid="daily-spend-error"
        >
          Couldn't load spend: {error}
        </div>
      ) : (
        <>
          <div className="flex items-baseline gap-4 mb-3">
            <div>
              <div
                className="text-2xl font-semibold text-zinc-50"
                data-testid="daily-spend-total"
              >
                {_fmtUsd(total)}
              </div>
              <div className="text-[11px] text-zinc-500">
                last {days}d · {calls.toLocaleString()} calls
              </div>
            </div>
            <div className="ml-auto">
              <_Sparkline values={sparkValues} color={spiked ? "#fbbf24" : "#34d399"} />
            </div>
          </div>

          {providers.length > 0 ? (
            <div
              className="border-t border-zinc-800 pt-3 space-y-1.5"
              data-testid="daily-spend-providers"
            >
              {providers.slice(0, 5).map((p) => (
                <div
                  key={p.provider}
                  className="flex items-center justify-between text-[12px]"
                  data-testid={`daily-spend-provider-${p.provider}`}
                >
                  <span className="font-mono text-zinc-300">{p.provider}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-zinc-500">
                      {Number(p.calls || 0).toLocaleString()} calls
                    </span>
                    <span className="text-zinc-100 font-medium tabular-nums">
                      {_fmtUsd(p.cost_usd)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-zinc-500 italic">
              {loading ? "loading…" : "No spend yet in this window."}
            </div>
          )}
        </>
      )}
    </div>
  );
}
