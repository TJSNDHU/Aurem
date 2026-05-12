/**
 * AdminMemoir — browse the Git-versioned semantic memory.
 *
 * Route: /admin/memoir
 *
 * Quick UX:
 *   - Top: store info + perf stats
 *   - Path input → list children + commit history
 *   - Click any (ns,key) to view value JSON + per-key Git history
 */
import React, { useCallback, useEffect, useState } from "react";
import { Loader2, GitBranch, Database, Search, History, FileText } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COLORS = {
  bg: "#08080F", panel: "rgba(255,255,255,0.04)",
  border: "rgba(155,109,212,0.22)", accent: "#9B6DD4",
  accent2: "#64C8FF", text: "#F0EADC", textD: "#A8A08F",
  ok: "#22C55E", warn: "#F59E0B",
};

const fetchJSON = (path) => fetch(`${API}${path}`).then(r => r.ok ? r.json() : Promise.reject(r.status));

export default function AdminMemoir() {
  const [info, setInfo] = useState(null);
  const [stats, setStats] = useState(null);
  const [path, setPath] = useState("aurem.ora.sessions");
  const [items, setItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const loadInfo = useCallback(async () => {
    try {
      const [i, s] = await Promise.all([fetchJSON("/api/admin/memoir/info"), fetchJSON("/api/admin/memoir/stats")]);
      setInfo(i); setStats(s);
    } catch (e) { /* ignore */ }
  }, []);

  const loadPath = useCallback(async () => {
    if (!path.trim()) return;
    setLoading(true); setErr(""); setSelectedItem(null); setHistory([]);
    try {
      const j = await fetchJSON(`/api/admin/memoir/search?path=${encodeURIComponent(path)}&limit=100`);
      setItems(j.items || []);
    } catch (e) {
      setErr(`Search failed: ${e}`);
    }
    setLoading(false);
  }, [path]);

  useEffect(() => { loadInfo(); const t = setInterval(loadInfo, 20000); return () => clearInterval(t); }, [loadInfo]);
  useEffect(() => { loadPath(); }, [loadPath]);

  const openItem = async (item) => {
    setSelectedItem(item);
    try {
      const j = await fetchJSON(`/api/admin/memoir/history?path=${encodeURIComponent(item.namespace.join("."))}&key=${encodeURIComponent(item.key)}&limit=30`);
      setHistory(j.history || []);
    } catch (e) {
      setHistory([]);
    }
  };

  const presets = [
    "aurem.ora.sessions",
    "aurem.customers",
    "aurem.skills.broadcast",
    "aurem.founder.saves",
    "aurem.agents",
  ];

  const perf = stats?.performance || {};

  return (
    <div data-testid="admin-memoir" style={{
      minHeight: "100vh", background: COLORS.bg, color: COLORS.text,
      padding: "26px 28px", fontFamily: "system-ui,-apple-system,sans-serif",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 22 }}>
        <GitBranch size={28} style={{ color: COLORS.accent }} />
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>Memoir — Git for AI Memory</h1>
          <div style={{ fontSize: 12, color: COLORS.textD, marginTop: 4 }}>
            {info?.available ? <span style={{ color: COLORS.ok }}>● ONLINE</span> : <span style={{ color: COLORS.warn }}>● WARMING UP</span>}
            {" · "}{info?.store_path || "/app/data/memoir/store"}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 18 }}>
        <Stat label="MEMORY KEYS" value={(stats?.total_keys ?? 0).toLocaleString()} color={COLORS.accent} icon={<Database size={14} />} />
        <Stat label="NAMESPACES" value={(stats?.total_namespaces ?? 0).toLocaleString()} color={COLORS.accent2} icon={<FileText size={14} />} />
        <Stat label="READS" value={(perf.reads ?? 0).toLocaleString()} color={COLORS.ok} />
        <Stat label="WRITES" value={(perf.writes ?? 0).toLocaleString()} color={COLORS.warn} />
        <Stat label="SEARCHES" value={(perf.searches ?? 0).toLocaleString()} color="#C9A84C" />
      </div>

      {/* Path search */}
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 280, position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 12, top: 13, color: COLORS.textD }} />
          <input data-testid="memoir-path"
            value={path} onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadPath()}
            placeholder="aurem.ora.sessions or aurem.customers.{email}"
            style={{ width: "100%", padding: "10px 12px 10px 34px", borderRadius: 10,
              background: COLORS.panel, border: `1px solid ${COLORS.border}`,
              color: COLORS.text, fontSize: 13, outline: "none", fontFamily: "ui-monospace, monospace" }}
          />
        </div>
        <button onClick={loadPath} disabled={loading} data-testid="memoir-search-btn"
          style={btnAccent}>
          {loading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : "Search"}
        </button>
      </div>

      {/* Preset paths */}
      <div style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        {presets.map(p => (
          <button key={p} data-testid={`memoir-preset-${p}`}
            onClick={() => setPath(p)}
            style={{
              padding: "5px 10px", borderRadius: 7,
              background: path === p ? COLORS.accent + "33" : "rgba(255,255,255,0.03)",
              border: `1px solid ${path === p ? COLORS.accent : COLORS.border}`,
              color: COLORS.text, fontSize: 10, cursor: "pointer",
              fontFamily: "ui-monospace, monospace",
            }}>
            {p}
          </button>
        ))}
      </div>

      {err && <div style={{ color: "#EF4444", fontSize: 12, marginBottom: 12, fontFamily: "monospace" }}>error: {err}</div>}

      <div style={{ display: "grid", gridTemplateColumns: selectedItem ? "1fr 1fr" : "1fr", gap: 16 }}>
        {/* Items list */}
        <div data-testid="memoir-items" style={cardStyle}>
          <div style={{ fontSize: 11, color: COLORS.textD, letterSpacing: 1, marginBottom: 10 }}>
            ITEMS UNDER PATH ({items.length})
          </div>
          {!loading && items.length === 0 && (
            <div style={{ color: COLORS.textD, fontSize: 12, padding: "14px 0" }}>
              No items at this path. Try one of the presets above.
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 520, overflowY: "auto" }}>
            {items.map((it, i) => {
              const isSel = selectedItem && selectedItem.key === it.key &&
                JSON.stringify(selectedItem.namespace) === JSON.stringify(it.namespace);
              return (
                <button key={i} onClick={() => openItem(it)} data-testid={`memoir-item-${i}`}
                  style={{
                    textAlign: "left", padding: "8px 10px", borderRadius: 8,
                    background: isSel ? COLORS.accent + "22" : "rgba(255,255,255,0.02)",
                    border: `1px solid ${isSel ? COLORS.accent : COLORS.border}`,
                    color: COLORS.text, cursor: "pointer", display: "flex", flexDirection: "column", gap: 3,
                  }}>
                  <div style={{ fontSize: 11, color: COLORS.accent, fontFamily: "ui-monospace, monospace" }}>
                    {it.namespace.join(".")} → {it.key}
                  </div>
                  <div style={{ fontSize: 11, color: COLORS.textD, fontFamily: "ui-monospace, monospace",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {JSON.stringify(it.value).slice(0, 100)}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail panel */}
        {selectedItem && (
          <div data-testid="memoir-detail" style={cardStyle}>
            <div style={{ fontSize: 11, color: COLORS.textD, letterSpacing: 1, marginBottom: 6 }}>
              VALUE · {selectedItem.namespace.join(".")} / {selectedItem.key}
            </div>
            <pre style={{
              fontSize: 11, color: COLORS.text, background: "rgba(0,0,0,0.4)",
              padding: 12, borderRadius: 8, maxHeight: 200, overflowY: "auto",
              fontFamily: "ui-monospace, monospace",
            }}>
{JSON.stringify(selectedItem.value, null, 2)}
            </pre>
            <div style={{ display: "flex", alignItems: "center", gap: 6, margin: "14px 0 8px" }}>
              <History size={13} style={{ color: COLORS.accent2 }} />
              <span style={{ fontSize: 11, color: COLORS.textD, letterSpacing: 1 }}>GIT HISTORY ({history.length})</span>
            </div>
            <div style={{ maxHeight: 220, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
              {history.length === 0 && (
                <div style={{ color: COLORS.textD, fontSize: 11 }}>No commit history yet (may be a fresh write).</div>
              )}
              {history.map((h, i) => (
                <div key={i} style={{ padding: "6px 8px", background: "rgba(0,0,0,0.3)", borderRadius: 6,
                  borderLeft: `3px solid ${COLORS.accent2}` }}>
                  <div style={{ fontSize: 10, color: COLORS.accent2, fontFamily: "ui-monospace, monospace" }}>
                    {(h.id || "").slice(0, 12)}
                  </div>
                  <div style={{ fontSize: 11, color: COLORS.text }}>{h.message}</div>
                  <div style={{ fontSize: 9, color: COLORS.textD }}>
                    {h.author || "—"} · {h.timestamp ? new Date(h.timestamp * 1000).toLocaleString() : "—"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

const Stat = ({ label, value, color, icon }) => (
  <div style={{
    padding: "12px 14px", borderRadius: 10,
    background: "rgba(255,255,255,0.03)", border: `1px solid ${color}25`,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 9, color: "#6A6070", letterSpacing: 1.2 }}>
      {icon} {label}
    </div>
    <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
  </div>
);

const cardStyle = {
  padding: 18, borderRadius: 14,
  background: "rgba(255,255,255,0.03)", border: `1px solid ${COLORS.border}`,
  color: COLORS.text,
};
const btnAccent = {
  display: "flex", alignItems: "center", gap: 6,
  padding: "10px 16px", borderRadius: 10,
  background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accent2})`,
  color: "#08080F", fontWeight: 700, border: "none", cursor: "pointer", fontSize: 12,
};
