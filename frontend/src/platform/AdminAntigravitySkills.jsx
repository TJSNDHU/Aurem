/**
 * AdminAntigravitySkills — browse + broadcast the 1,453+ Antigravity skills
 * to all 28 AUREM agents.
 *
 * Route: /admin/skills-library
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Send, Radio, X, Search, RefreshCw, Library } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COLORS = {
  bg: "#08080F",
  panel: "rgba(255,255,255,0.04)",
  panelHi: "rgba(255,255,255,0.06)",
  border: "rgba(212,175,55,0.18)",
  accent: "#D4AF37",
  accent2: "#FF6B00",
  text: "#F0EADC",
  textD: "#A8A08F",
  ok: "#22C55E",
  danger: "#EF4444",
};

const _authHeader = () => {
  const t =
    localStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("aurem_token") ||
    localStorage.getItem("platform_token") ||
    "";
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const fetchJSON = async (url, opts = {}) => {
  const r = await fetch(`${API}${url}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ..._authHeader(),
      ...(opts.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
};

export default function AdminAntigravitySkills() {
  const [meta, setMeta] = useState(null);
  const [categories, setCategories] = useState([]);
  const [skills, setSkills] = useState([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [risk, setRisk] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [activeBroadcast, setActiveBroadcast] = useState(null);
  const [busyBroadcast, setBusyBroadcast] = useState(false);
  const [busySync, setBusySync] = useState(false);
  const [err, setErr] = useState("");
  const [openSkill, setOpenSkill] = useState(null);

  const loadMeta = useCallback(async () => {
    try {
      const m = await fetchJSON("/api/admin/antigravity-skills/library/meta");
      setMeta(m);
    } catch (e) { /* ignore */ }
  }, []);
  const loadCategories = useCallback(async () => {
    try {
      const c = await fetchJSON("/api/admin/antigravity-skills/library/categories");
      setCategories(c.categories || []);
    } catch (e) { /* ignore */ }
  }, []);
  const loadActive = useCallback(async () => {
    try {
      const a = await fetchJSON("/api/admin/antigravity-skills/broadcast/active");
      setActiveBroadcast(a && a.skill_ids ? a : null);
    } catch (e) { /* ignore */ }
  }, []);
  const loadSkills = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (cat) params.set("category", cat);
      if (risk) params.set("risk", risk);
      params.set("limit", "60");
      const r = await fetchJSON(`/api/admin/antigravity-skills/library?${params}`);
      setSkills(r.items || []);
      setTotal(r.total || 0);
    } catch (e) {
      setErr(`Failed to load: ${e.message}`);
    }
    setLoading(false);
  }, [q, cat, risk]);

  useEffect(() => { loadMeta(); loadCategories(); loadActive(); }, [loadMeta, loadCategories, loadActive]);
  useEffect(() => { loadSkills(); }, [loadSkills]);

  const toggleSelect = (id) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const broadcast = async () => {
    if (selected.size === 0) return;
    setBusyBroadcast(true); setErr("");
    try {
      const r = await fetchJSON("/api/admin/antigravity-skills/broadcast", {
        method: "POST",
        body: JSON.stringify({
          skill_ids: Array.from(selected),
          note: `Admin broadcast at ${new Date().toISOString()}`,
        }),
      });
      await loadActive();
      setSelected(new Set());
      alert(`Broadcasted ${r.skill_count} skills to ALL 28 agents (${r.addendum_chars} chars)`);
    } catch (e) {
      setErr(`Broadcast failed: ${e.message}`);
    }
    setBusyBroadcast(false);
  };

  const clearBroadcast = async () => {
    setBusyBroadcast(true);
    try {
      await fetchJSON("/api/admin/antigravity-skills/broadcast/clear", { method: "POST" });
      await loadActive();
    } catch (e) { /* ignore */ }
    setBusyBroadcast(false);
  };

  const resync = async () => {
    setBusySync(true); setErr("");
    try {
      const r = await fetchJSON("/api/admin/antigravity-skills/sync", { method: "POST" });
      await loadMeta();
      await loadCategories();
      await loadSkills();
      alert(`Sync OK — ${r.result?.upserted} skills upserted`);
    } catch (e) {
      setErr(`Sync failed: ${e.message}`);
    }
    setBusySync(false);
  };

  const openDetail = async (id) => {
    try {
      const d = await fetchJSON(`/api/admin/antigravity-skills/library/${id}`);
      setOpenSkill(d);
    } catch (e) {
      setErr(`Could not load skill: ${e.message}`);
    }
  };

  const selCount = selected.size;

  return (
    <div data-testid="admin-skills-library" style={{ minHeight: "100vh", background: COLORS.bg, color: COLORS.text, padding: "26px 28px", fontFamily: "system-ui,-apple-system,sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Library size={28} style={{ color: COLORS.accent }} />
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>Antigravity Skills Library</h1>
            <div style={{ fontSize: 12, color: COLORS.textD, marginTop: 4 }}>
              {meta?.total_in_db ?? "…"} skills · last sync {meta?.meta?.ingested_at?.slice(0, 19) || "—"}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button data-testid="skills-resync-btn" onClick={resync} disabled={busySync} style={btnGhost}>
            {busySync ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <RefreshCw size={14} />} Re-sync
          </button>
        </div>
      </div>

      {/* Active broadcast banner */}
      {activeBroadcast && (
        <div data-testid="active-broadcast-banner" style={{ marginBottom: 18, padding: "14px 18px", borderRadius: 12, background: `linear-gradient(135deg, rgba(34,197,94,0.12), rgba(212,175,55,0.05))`, border: `1px solid ${COLORS.ok}` }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Radio size={16} style={{ color: COLORS.ok }} />
              <strong>Active broadcast:</strong>
              <span>{activeBroadcast.skill_count} skills live across {activeBroadcast.target_agents === "ALL" ? "all 28 agents" : `${activeBroadcast.target_agents?.length} agents`}</span>
            </div>
            <button onClick={clearBroadcast} disabled={busyBroadcast} style={{ ...btnGhost, padding: "6px 10px" }} data-testid="clear-broadcast-btn">
              <X size={14} /> Clear
            </button>
          </div>
          <div style={{ marginTop: 6, fontSize: 11, color: COLORS.textD, fontFamily: "monospace" }}>
            {(activeBroadcast.skill_ids || []).join(", ")}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 280, position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 12, top: 13, color: COLORS.textD }} />
          <input
            data-testid="skills-search"
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search 1,453 skills — e.g., security, brainstorming, react"
            style={{ width: "100%", padding: "10px 12px 10px 34px", borderRadius: 10, background: COLORS.panel, border: `1px solid ${COLORS.border}`, color: COLORS.text, fontSize: 14, outline: "none" }}
          />
        </div>
        <select data-testid="skills-category" value={cat} onChange={(e) => setCat(e.target.value)} style={selectStyle}>
          <option value="">All categories ({categories.length})</option>
          {categories.map((c) => (
            <option key={c.category} value={c.category}>{c.category} ({c.count})</option>
          ))}
        </select>
        <select data-testid="skills-risk" value={risk} onChange={(e) => setRisk(e.target.value)} style={selectStyle}>
          <option value="">All risk levels</option>
          <option value="safe">safe</option>
          <option value="unknown">unknown</option>
          <option value="high">high</option>
        </select>
      </div>

      {err && (
        <div data-testid="skills-err" style={{ marginBottom: 12, color: COLORS.danger, fontSize: 12, fontFamily: "monospace" }}>error: {err}</div>
      )}

      {/* Selection + broadcast */}
      {selCount > 0 && (
        <div data-testid="skills-selection-bar" style={{ position: "sticky", top: 10, zIndex: 9, marginBottom: 16, padding: "12px 16px", borderRadius: 12, background: `linear-gradient(135deg, rgba(212,175,55,0.18), rgba(255,107,0,0.10))`, border: `1px solid ${COLORS.accent}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span><strong>{selCount}</strong> skill(s) selected, ready to broadcast to all 28 agents</span>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setSelected(new Set())} style={btnGhost} data-testid="skills-clear-sel">Clear</button>
            <button onClick={broadcast} disabled={busyBroadcast} style={btnAccent} data-testid="skills-broadcast-btn">
              {busyBroadcast ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Send size={14} />} Broadcast
            </button>
          </div>
        </div>
      )}

      {/* Results count */}
      <div style={{ fontSize: 12, color: COLORS.textD, marginBottom: 10 }}>
        {loading ? "Loading…" : `Showing ${skills.length} of ${total} skills`}
      </div>

      {/* Skill grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(330px, 1fr))", gap: 12 }}>
        {skills.map((s) => {
          const isSel = selected.has(s.id);
          return (
            <div key={s.id} data-testid={`skill-card-${s.id}`}
              style={{
                padding: 14, borderRadius: 12,
                background: isSel ? "rgba(212,175,55,0.10)" : COLORS.panel,
                border: `1px solid ${isSel ? COLORS.accent : COLORS.border}`,
                transition: "all 0.18s ease",
              }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <button onClick={() => openDetail(s.id)} style={{ background: "none", border: "none", color: COLORS.accent, padding: 0, fontSize: 13, fontWeight: 600, cursor: "pointer", textAlign: "left", lineHeight: 1.3, wordBreak: "break-word" }} data-testid={`skill-name-${s.id}`}>
                    {s.name}
                  </button>
                  <div style={{ fontSize: 10, color: COLORS.textD, marginTop: 4, textTransform: "uppercase", letterSpacing: 1 }}>
                    {s.category} · risk:{s.risk}
                  </div>
                </div>
                <input type="checkbox" checked={isSel} onChange={() => toggleSelect(s.id)} data-testid={`skill-select-${s.id}`}
                  style={{ width: 18, height: 18, cursor: "pointer", accentColor: COLORS.accent }} />
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: COLORS.textD, lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                {s.description}
              </div>
            </div>
          );
        })}
      </div>

      {/* Skill detail modal */}
      {openSkill && (
        <div data-testid="skill-detail-modal" onClick={() => setOpenSkill(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.78)", backdropFilter: "blur(10px)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 820, maxHeight: "85vh", width: "100%", background: "#0E0E18", border: `1px solid ${COLORS.border}`, borderRadius: 16, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "16px 22px", borderBottom: `1px solid ${COLORS.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: COLORS.accent }}>{openSkill.name}</div>
                <div style={{ fontSize: 11, color: COLORS.textD, marginTop: 3 }}>{openSkill.category} · risk:{openSkill.risk} · {openSkill.body_size} bytes</div>
              </div>
              <button onClick={() => setOpenSkill(null)} style={btnGhost} data-testid="skill-modal-close"><X size={14} /></button>
            </div>
            <pre style={{ flex: 1, overflowY: "auto", padding: 22, margin: 0, fontSize: 12, lineHeight: 1.55, color: COLORS.text, fontFamily: "ui-monospace, monospace", whiteSpace: "pre-wrap" }}>
{openSkill.body || "(no body)"}
            </pre>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

const btnGhost = {
  display: "flex", alignItems: "center", gap: 6,
  padding: "8px 12px", background: "rgba(255,255,255,0.04)",
  border: `1px solid ${COLORS.border}`, borderRadius: 10,
  color: COLORS.text, fontSize: 12, cursor: "pointer",
};

const btnAccent = {
  ...btnGhost,
  background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accent2})`,
  color: "#08080F", fontWeight: 700, border: "none",
};

const selectStyle = {
  padding: "10px 12px", borderRadius: 10, background: COLORS.panel,
  border: `1px solid ${COLORS.border}`, color: COLORS.text, fontSize: 13, outline: "none",
  minWidth: 180,
};
