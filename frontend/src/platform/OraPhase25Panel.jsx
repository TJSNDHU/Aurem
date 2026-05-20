/* eslint-disable react-hooks/exhaustive-deps */
/**
 * ORA Phase 2.5 Admin Panel (iter 281.5)
 * =========================================
 * Compact 3-column dashboard:
 *   - Retention candidates queue (send / blocked)
 *   - Upsell candidates queue (send / blocked)
 *   - Next-Best-Actions (latest 10) + Guardian policy log tail
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  RefreshCw,
  Heart,
  TrendingUp,
  Sparkles,
  Shield,
  Send,
  CheckCircle2,
  AlertOctagon,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

function readToken() {
  try {
    return (
      localStorage.getItem("admin_token") ||
      localStorage.getItem("token") ||
      sessionStorage.getItem("admin_token") ||
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

const Stat = ({ icon: Icon, label, value, tone = "default", testid }) => {
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
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-zinc-500">
        {Icon ? <Icon className="size-3" /> : null}
        {label}
      </div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  );
};

const OraPhase25Panel = () => {
  const [retention, setRetention] = useState([]);
  const [upsell, setUpsell] = useState([]);
  const [nbas, setNbas] = useState([]);
  const [policy, setPolicy] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, kind = "info") => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const headers = authHeaders();
      const [r, u, n, p] = await Promise.all([
        fetch(`${API}/api/admin/ora-25/retention?status=queued&limit=20`, { headers }),
        fetch(`${API}/api/admin/ora-25/upsell?status=queued&limit=20`, { headers }),
        fetch(`${API}/api/admin/ora-25/next-actions?limit=10`, { headers }),
        fetch(`${API}/api/admin/ora-25/policy-log?limit=15&only_blocked=false`, { headers }),
      ]);
      const [rb, ub, nb, pb] = await Promise.all([r.json(), u.json(), n.json(), p.json()]);
      setRetention(rb?.items || []);
      setUpsell(ub?.items || []);
      setNbas(nb?.items || []);
      setPolicy(pb?.items || []);
    } catch (_) {
      // soft fail — likely auth
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 45000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const onScan = useCallback(async () => {
    setBusy("scan");
    try {
      const r = await fetch(`${API}/api/admin/ora-25/scan-now`, {
        method: "POST",
        headers: { ...authHeaders() },
      });
      const body = await r.json().catch(() => ({}));
      if (r.ok) {
        showToast(
          `✓ Scan: ${body.retention_found || 0} retention · ${body.upsell_found || 0} upsell`,
          "good"
        );
        fetchAll();
      } else {
        showToast(`✗ Scan failed: ${body?.detail || r.status}`, "bad");
      }
    } finally {
      setBusy(null);
    }
  }, [fetchAll]);

  const sendRetention = useCallback(async (item) => {
    const id = item.kind || "ret";
    setBusy(`r:${item.email}`);
    try {
      // Use email as the lookup key (router does kind+email fallback)
      const r = await fetch(
        `${API}/api/admin/ora-25/retention/${encodeURIComponent(item.email || id)}/send`,
        { method: "POST", headers: { ...authHeaders() } }
      );
      const body = await r.json().catch(() => ({}));
      if (!r.ok || body?.blocked) {
        showToast(
          `✗ Retention blocked: ${body?.policy?.reason || body?.detail || "unknown"}`,
          "bad"
        );
      } else {
        showToast(`✓ Retention sent to ${item.email}`, "good");
        fetchAll();
      }
    } finally {
      setBusy(null);
    }
  }, [fetchAll]);

  const sendUpsell = useCallback(async (item) => {
    setBusy(`u:${item.email}`);
    try {
      const r = await fetch(
        `${API}/api/admin/ora-25/upsell/${encodeURIComponent(item.email)}/send`,
        { method: "POST", headers: { ...authHeaders() } }
      );
      const body = await r.json().catch(() => ({}));
      if (!r.ok || body?.blocked) {
        showToast(
          `✗ Upsell blocked: ${body?.policy?.reason || body?.detail || "unknown"}`,
          "bad"
        );
      } else {
        showToast(`✓ Upsell sent to ${item.email}`, "good");
        fetchAll();
      }
    } finally {
      setBusy(null);
    }
  }, [fetchAll]);

  return (
    <div
      data-testid="ora-phase-25-panel"
      className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-950 to-black p-5"
    >
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-amber-400" />
            <h3 className="text-base font-semibold text-zinc-100">
              ORA Sovereign Customer Handler
            </h3>
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 border border-zinc-800 px-2 py-0.5 rounded">
              Phase 2.5
            </span>
          </div>
          <p className="text-[12px] text-zinc-500 mt-1">
            Retention · Upsell · Next-Best-Action · Guardian Policy. ORA never
            sends without you.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onScan}
            disabled={busy === "scan"}
            data-testid="ora-25-scan-now-btn"
            className="text-[12px] px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-black flex items-center gap-1 disabled:opacity-40"
          >
            {busy === "scan" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            Scan now
          </button>
          <button
            onClick={fetchAll}
            disabled={loading}
            data-testid="ora-25-refresh-btn"
            className="text-[12px] px-3 py-1.5 rounded bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-zinc-200 flex items-center gap-1 disabled:opacity-40"
          >
            {loading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        <Stat icon={Heart} label="Retention" value={retention.length} tone="warn" testid="ora-25-stat-retention" />
        <Stat icon={TrendingUp} label="Upsell" value={upsell.length} tone="good" testid="ora-25-stat-upsell" />
        <Stat icon={Sparkles} label="Next Actions" value={nbas.length} testid="ora-25-stat-nbas" />
        <Stat icon={Shield} label="Policy Log" value={policy.length} tone={policy.some(p => !p.allowed) ? "bad" : "default"} testid="ora-25-stat-policy" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Retention column */}
        <div data-testid="ora-25-retention-col" className="rounded-xl border border-zinc-800 bg-black/40 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Heart className="size-3.5 text-amber-400" />
            <span className="text-[12px] uppercase tracking-wider text-zinc-300">Retention</span>
          </div>
          {retention.length === 0 && (
            <div className="text-[12px] text-zinc-500 py-3 text-center" data-testid="ora-25-retention-empty">
              No queued candidates. ORA scanning…
            </div>
          )}
          {retention.map((it, i) => (
            <div
              key={i}
              data-testid={`ora-25-retention-${i}`}
              className="border border-zinc-900 bg-zinc-950/60 rounded-lg p-2 mb-2"
            >
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-[12px] text-zinc-200 font-medium">{it.email || it.phone}</div>
                  <div className="text-[10px] uppercase tracking-wider text-amber-400">
                    {(it.kind || "").replace("_", " ")}
                  </div>
                </div>
                <button
                  onClick={() => sendRetention(it)}
                  disabled={busy === `r:${it.email}`}
                  data-testid={`ora-25-retention-send-${i}`}
                  className="text-[11px] px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-black font-medium flex items-center gap-1 disabled:opacity-40"
                >
                  <Send className="size-3" /> Send
                </button>
              </div>
              <div className="mt-1 text-[11px] text-zinc-400 line-clamp-2">{it.suggested_msg}</div>
            </div>
          ))}
        </div>

        {/* Upsell column */}
        <div data-testid="ora-25-upsell-col" className="rounded-xl border border-zinc-800 bg-black/40 p-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="size-3.5 text-emerald-400" />
            <span className="text-[12px] uppercase tracking-wider text-zinc-300">Upsell</span>
          </div>
          {upsell.length === 0 && (
            <div className="text-[12px] text-zinc-500 py-3 text-center" data-testid="ora-25-upsell-empty">
              No upsell signals yet.
            </div>
          )}
          {upsell.map((it, i) => (
            <div
              key={i}
              data-testid={`ora-25-upsell-${i}`}
              className="border border-zinc-900 bg-zinc-950/60 rounded-lg p-2 mb-2"
            >
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-[12px] text-zinc-200 font-medium">{it.email}</div>
                  <div className="text-[10px] uppercase tracking-wider text-emerald-400">
                    {it.current_plan || "?"} → {it.suggested_plan}
                  </div>
                </div>
                <button
                  onClick={() => sendUpsell(it)}
                  disabled={busy === `u:${it.email}`}
                  data-testid={`ora-25-upsell-send-${i}`}
                  className="text-[11px] px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-black font-medium flex items-center gap-1 disabled:opacity-40"
                >
                  <Send className="size-3" /> Send
                </button>
              </div>
              <div className="mt-1 text-[11px] text-zinc-400 line-clamp-2">{it.suggested_msg}</div>
            </div>
          ))}
        </div>

        {/* NBA + Policy column */}
        <div className="space-y-3">
          <div data-testid="ora-25-nbas-col" className="rounded-xl border border-zinc-800 bg-black/40 p-3">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="size-3.5 text-amber-400" />
              <span className="text-[12px] uppercase tracking-wider text-zinc-300">ORA Recommends</span>
            </div>
            {nbas.length === 0 && (
              <div className="text-[12px] text-zinc-500 py-3 text-center" data-testid="ora-25-nbas-empty">
                No recent actions yet.
              </div>
            )}
            {nbas.slice(0, 5).map((n, i) => (
              <div
                key={i}
                data-testid={`ora-25-nba-${i}`}
                className="border border-zinc-900 bg-zinc-950/60 rounded-lg p-2 mb-2"
              >
                <div className="text-[11px]">
                  <span className="uppercase text-amber-400 font-medium">{n.action || "wait"}</span>
                  <span className="text-zinc-500"> · {n.when || "today"}</span>
                </div>
                <div className="text-[11px] text-zinc-300 mt-0.5">{n.for_user}</div>
                <div className="text-[11px] text-zinc-500 line-clamp-2">{n.reason}</div>
              </div>
            ))}
          </div>

          <div data-testid="ora-25-policy-col" className="rounded-xl border border-zinc-800 bg-black/40 p-3">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="size-3.5 text-blue-400" />
              <span className="text-[12px] uppercase tracking-wider text-zinc-300">Policy Log</span>
            </div>
            {policy.length === 0 && (
              <div className="text-[12px] text-zinc-500 py-3 text-center" data-testid="ora-25-policy-empty">
                No policy events.
              </div>
            )}
            {policy.slice(0, 5).map((p, i) => (
              <div
                key={i}
                data-testid={`ora-25-policy-${i}`}
                className="flex items-start gap-2 text-[11px] mb-1"
              >
                {p.allowed ? (
                  <CheckCircle2 className="size-3 text-emerald-400 mt-0.5 shrink-0" />
                ) : (
                  <AlertOctagon className="size-3 text-rose-400 mt-0.5 shrink-0" />
                )}
                <span className="text-zinc-400">
                  <span className="text-zinc-200">{p.action_kind}</span> →{" "}
                  {p.target?.slice(0, 24) || "?"}
                  {p.reason ? <span className="text-rose-300"> · {p.reason}</span> : null}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {toast && (
        <div
          data-testid="ora-25-toast"
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

export default OraPhase25Panel;
