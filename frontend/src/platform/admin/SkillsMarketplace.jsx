/**
 * SkillsMarketplace.jsx — iter 326hh-UI (Phase 3 P3.3 frontend)
 *
 * Browse the ORA skills marketplace and install a skill for a tenant.
 * Backed by:
 *   GET  /api/admin/ora/skills                       (list)
 *   GET  /api/admin/ora/skills/{skill_id}            (detail)
 *   POST /api/admin/ora/skills/{skill_id}/install
 *
 * Route: /admin/ora-skills
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const CATEGORIES = [
  "all", "tax", "compliance", "marketing", "outreach",
  "operations", "customer_success",
];

export default function SkillsMarketplace() {
  const [skills, setSkills] = useState([]);
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [installTenantId, setInstallTenantId] = useState("");
  const [installing, setInstalling] = useState(false);
  const [installMessage, setInstallMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      if (category !== "all") qs.set("category", category);
      qs.set("limit", "50");
      const r = await fetch(
        `${API}/api/admin/ora/skills?${qs.toString()}`,
        { headers: { Authorization: `Bearer ${_getAdminToken()}` } }
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setSkills(Array.isArray(data?.skills) ? data.skills : []);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => { load(); }, [load]);

  const install = useCallback(async () => {
    if (!selected || !installTenantId) return;
    setInstalling(true);
    setInstallMessage("");
    try {
      const r = await fetch(
        `${API}/api/admin/ora/skills/${encodeURIComponent(selected.skill_id)}/install`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${_getAdminToken()}`,
          },
          body: JSON.stringify({ tenant_id: installTenantId }),
        }
      );
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
      setInstallMessage(
        `Installed v${data.version} for ${data.tenant_id}.`
      );
      load();
    } catch (e) {
      setInstallMessage(`Install failed: ${String(e?.message || e)}`);
    } finally {
      setInstalling(false);
    }
  }, [selected, installTenantId, load]);

  return (
    <div
      className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-8"
      data-testid="skills-marketplace"
    >
      <div className="max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">
            ORA Skills Marketplace
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Versioned skill bundles published by domain experts.
            Install per-tenant to extend ORA's behaviour.
          </p>
        </header>

        <div className="flex items-center gap-2 mb-4 flex-wrap" data-testid="skills-filters">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              data-testid={`skills-cat-${c}`}
              className={
                "text-[11px] uppercase tracking-wider px-2.5 py-1 rounded border transition " +
                (category === c
                  ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                  : "bg-transparent text-zinc-400 border-zinc-700 hover:border-zinc-500")
              }
            >
              {c.replace("_", " ")}
            </button>
          ))}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            data-testid="skills-refresh"
            className="ml-auto text-[11px] text-zinc-400 hover:text-zinc-100 disabled:opacity-40"
          >
            {loading ? "…" : "refresh"}
          </button>
        </div>

        {error ? (
          <div className="text-xs text-rose-300 mb-4" data-testid="skills-error">
            {error}
          </div>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="skills-grid">
          {skills.length === 0 && !loading ? (
            <div
              className="col-span-full text-sm text-zinc-500 italic"
              data-testid="skills-empty"
            >
              No skills published yet in this category. Marketplace seeds
              automatically when the backend boots.
            </div>
          ) : null}
          {skills.map((s) => (
            <button
              key={s.skill_id}
              type="button"
              onClick={() => { setSelected(s); setInstallMessage(""); }}
              data-testid={`skills-card-${s.skill_id}`}
              className="text-left rounded-lg border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 transition p-4"
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="text-sm font-semibold text-zinc-100 line-clamp-2">
                  {s.name}
                </div>
                <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400 whitespace-nowrap">
                  {s.category}
                </span>
              </div>
              <div className="text-xs text-zinc-400 line-clamp-3 mb-2">
                {s.description}
              </div>
              <div className="flex items-center justify-between text-[11px] text-zinc-500">
                <span>v{s.latest_version || "1.0.0"}</span>
                <span>{(s.downloads || 0).toLocaleString()} installs</span>
              </div>
            </button>
          ))}
        </div>

        {selected ? (
          <div
            className="fixed inset-x-0 bottom-0 md:inset-auto md:bottom-6 md:right-6 md:w-96 bg-zinc-900 border-t md:border md:rounded-lg border-zinc-700 p-4 shadow-2xl"
            data-testid="skills-install-panel"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="text-sm font-semibold text-zinc-100">
                  {selected.name}
                </div>
                <div className="text-[11px] text-zinc-500">
                  by {selected.author_email} · v{selected.latest_version}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                data-testid="skills-install-close"
                className="text-zinc-400 hover:text-zinc-100"
              >
                ×
              </button>
            </div>
            <p className="text-xs text-zinc-400 mb-3 line-clamp-3">
              {selected.description}
            </p>
            <label className="block text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
              Install for tenant
            </label>
            <input
              type="text"
              value={installTenantId}
              onChange={(e) => setInstallTenantId(e.target.value.trim())}
              placeholder="tenant_id"
              data-testid="skills-install-tenant-input"
              className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-zinc-500 mb-3"
            />
            <button
              type="button"
              onClick={install}
              disabled={!installTenantId || installing}
              data-testid="skills-install-btn"
              className="w-full px-4 py-2 rounded bg-emerald-500 text-zinc-900 text-sm font-semibold hover:bg-emerald-400 transition disabled:opacity-40"
            >
              {installing ? "installing…" : "Install"}
            </button>
            {installMessage ? (
              <div
                className={
                  "text-[11px] mt-2 " +
                  (installMessage.startsWith("Install failed")
                    ? "text-rose-300"
                    : "text-emerald-300")
                }
                data-testid="skills-install-message"
              >
                {installMessage}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
