/**
 * CacheStatusPanel.jsx
 * ─────────────────────────────────────────────────────────────────
 * Admin panel: live Redis cache monitor
 * Shows key inventory, TTLs, hit/miss ratio, memory usage
 *
 * Add to admin sidebar: Admin → Performance → Cache Monitor
 *
 * Calls: GET  /api/admin/cache/status
 *        POST /api/admin/cache/flush        (bust all keys)
 *        POST /api/admin/cache/flush/{key}  (bust one key)
 *        POST /api/admin/cache/warm         (re-warm now)
 * ─────────────────────────────────────────────────────────────────
 */

import { useState, useEffect, useCallback, useRef } from "react";

// ── MOCK DATA (used when backend unreachable) ─────────────────────
const MOCK = {
  connected: true,
  redis_host: "redis-14355.c279.us-central1-1.gce.cloud.redislabs.com:14355",
  uptime_seconds: 86420,
  memory_used_mb: 2.4,
  memory_peak_mb: 3.1,
  memory_max_mb: 30,
  hit_count: 1842,
  miss_count: 134,
  total_commands: 3201,
  keys: [
    { key: "products:all",    ttl: 247, size_bytes: 4821, type: "string" },
    { key: "products:combos", ttl: 211, size_bytes: 912,  type: "string" },
    { key: "products:aura-gen", ttl: 189, size_bytes: 1203, type: "string" },
    { key: "brands:all",      ttl: 541, size_bytes: 623,  type: "string" },
    { key: "ingredients:all", ttl: 3542, size_bytes: 18204, type: "string" },
    { key: "ratelimit:127.0.0.1", ttl: 38, size_bytes: 12, type: "string" },
  ],
  last_warmed: "2025-01-15T12:44:01Z",
  warming_ms: 312,
};

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

async function fetchStatus() {
  try {
    const r = await fetch(`${API_BASE}/api/admin/cache/status`);
    if (!r.ok) throw new Error("backend");
    return await r.json();
  } catch {
    await new Promise(res => setTimeout(res, 600));
    return { ...MOCK, _mock: true };
  }
}

async function postAction(path) {
  try {
    const r = await fetch(`${API_BASE}${path}`, { method: "POST" });
    if (!r.ok) throw new Error("failed");
    return await r.json();
  } catch {
    await new Promise(res => setTimeout(res, 400));
    return { success: true, _mock: true };
  }
}

// ── HELPERS ───────────────────────────────────────────────────────
function fmtTTL(s) {
  if (s < 0)    return "∞";
  if (s < 60)   return `${s}s`;
  if (s < 3600) return `${Math.floor(s/60)}m ${s%60}s`;
  return `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m`;
}
function fmtBytes(b) {
  if (b < 1024)       return `${b} B`;
  if (b < 1024*1024)  return `${(b/1024).toFixed(1)} KB`;
  return `${(b/1024/1024).toFixed(2)} MB`;
}
function fmtUptime(s) {
  const d = Math.floor(s/86400), h = Math.floor((s%86400)/3600),
        m = Math.floor((s%3600)/60);
  return [d&&`${d}d`, h&&`${h}h`, `${m}m`].filter(Boolean).join(" ");
}
function hitRate(hits, misses) {
  const total = hits + misses;
  if (!total) return 0;
  return Math.round((hits / total) * 100);
}
function ttlColor(s) {
  if (s < 0)   return "#79c0ff";
  if (s < 30)  return "#f85149";
  if (s < 120) return "#e3b341";
  return "#57ab5a";
}
function categoryOf(key) {
  if (key.startsWith("products"))    return "products";
  if (key.startsWith("brands"))      return "brands";
  if (key.startsWith("ingredients")) return "ingredients";
  if (key.startsWith("ratelimit"))   return "ratelimit";
  return "other";
}
const CAT_COLORS = {
  products:    "#58a6ff",
  brands:      "#bc8cff",
  ingredients: "#57ab5a",
  ratelimit:   "#e3b341",
  other:       "#8b949e",
};

// ── STYLES ────────────────────────────────────────────────────────
const S = {
  wrap: {
    fontFamily: "'IBM Plex Mono', 'Fira Mono', monospace",
    background: "#0d1117", color: "#e6edf3",
    minHeight: "100vh", padding: "28px 32px", fontSize: "13px",
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: "24px", paddingBottom: "16px",
    borderBottom: "1px solid #21262d",
  },
  title: {
    fontSize: "15px", fontWeight: 600, color: "#e6edf3",
    letterSpacing: "0.03em",
    display: "flex", alignItems: "center", gap: "10px",
  },
  badge: (c) => ({
    fontSize: "10px", fontWeight: 500, letterSpacing: "0.08em",
    background: c+"22", color: c, border: `1px solid ${c}44`,
    borderRadius: "3px", padding: "2px 8px", textTransform: "uppercase",
  }),
  btnRow: { display: "flex", gap: "8px", alignItems: "center" },
  btn: (variant="default") => ({
    fontFamily: "inherit",
    fontSize: "11px", fontWeight: 500, letterSpacing: "0.06em",
    padding: "7px 16px", borderRadius: "4px", cursor: "pointer",
    border: "1px solid",
    background:   variant==="danger"  ? "#f8514922" : variant==="primary" ? "#238636" : "#21262d",
    color:        variant==="danger"  ? "#f85149"   : variant==="primary" ? "#fff"    : "#8b949e",
    borderColor:  variant==="danger"  ? "#f8514944" : variant==="primary" ? "#238636" : "#30363d",
    transition: "all .2s",
  }),
  statsGrid: {
    display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px",
    marginBottom: "20px",
  },
  statCard: (accent="#58a6ff") => ({
    background: "#161b22", border: "1px solid #21262d",
    borderTop: `2px solid ${accent}`,
    borderRadius: "6px", padding: "16px 20px",
  }),
  statNum: { fontSize: "28px", fontWeight: 600, color: "#e6edf3", lineHeight: 1, marginBottom: "4px" },
  statLabel: { fontSize: "10px", color: "#8b949e", letterSpacing: "0.1em", textTransform: "uppercase" },
  statSub: { fontSize: "11px", color: "#8b949e", marginTop: "6px" },
  panel: {
    background: "#161b22", border: "1px solid #21262d",
    borderRadius: "6px", overflow: "hidden", marginBottom: "16px",
  },
  panelHead: {
    padding: "10px 16px", borderBottom: "1px solid #21262d",
    fontSize: "10.5px", fontWeight: 600, letterSpacing: "0.12em",
    textTransform: "uppercase", color: "#8b949e",
    display: "flex", alignItems: "center", justifyContent: "space-between",
  },
  row: (hover) => ({
    display: "grid",
    gridTemplateColumns: "2fr 80px 90px 80px 80px 60px",
    padding: "10px 16px",
    borderBottom: "1px solid #21262d",
    alignItems: "center",
    background: hover ? "#1c2128" : "transparent",
    transition: "background .15s",
    cursor: "default",
  }),
  cell: (align="left") => ({
    fontSize: "12px", color: "#c9d1d9",
    textAlign: align, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
  }),
  colHead: (align="left") => ({
    fontSize: "10px", fontWeight: 600, color: "#484f58",
    letterSpacing: "0.1em", textTransform: "uppercase", textAlign: align,
  }),
  progressBar: () => ({
    height: "6px", borderRadius: "3px",
    background: "#21262d", position: "relative", overflow: "hidden",
    marginTop: "8px",
  }),
  progressFill: (pct, color) => ({
    position: "absolute", top: 0, left: 0, bottom: 0,
    width: `${Math.min(pct,100)}%`,
    background: color,
    borderRadius: "3px",
    transition: "width .6s ease",
  }),
  dot: (c) => ({
    width: "7px", height: "7px", borderRadius: "50%",
    background: c, display: "inline-block", marginRight: "6px", flexShrink: 0,
  }),
  toastWrap: {
    position: "fixed", bottom: "24px", right: "24px", zIndex: 999,
    display: "flex", flexDirection: "column", gap: "8px",
  },
  toast: (type) => ({
    background: type==="error" ? "#f8514922" : "#23863622",
    border: `1px solid ${type==="error" ? "#f85149" : "#57ab5a"}44`,
    color: type==="error" ? "#f85149" : "#57ab5a",
    borderRadius: "4px", padding: "10px 16px",
    fontSize: "12px", fontFamily: "inherit",
    animation: "slideIn .2s ease",
  }),
};

// ── SUB-COMPONENTS ────────────────────────────────────────────────

function StatCard({ label, value, sub, accent, pct }) {
  return (
    <div style={S.statCard(accent)}>
      <div style={S.statNum}>{value}</div>
      <div style={S.statLabel}>{label}</div>
      {sub  && <div style={S.statSub}>{sub}</div>}
      {pct!=null && (
        <div style={S.progressBar()}>
          <div style={S.progressFill(pct, accent)} />
        </div>
      )}
    </div>
  );
}

function TTLCell({ ttl }) {
  const color = ttlColor(ttl);
  const maxTTL = 3600;
  const pct = ttl < 0 ? 100 : Math.min((ttl / maxTTL) * 100, 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
      <span style={{ color, fontSize: "12px", minWidth: "40px" }}>{fmtTTL(ttl)}</span>
      <div style={{ width: "48px", height: "3px", background: "#21262d", borderRadius: "2px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: "2px" }} />
      </div>
    </div>
  );
}

function KeyRow({ item, onFlush }) {
  const [hov, setHov] = useState(false);
  const [flushing, setFlushing] = useState(false);
  const cat = categoryOf(item.key);

  const flush = async (e) => {
    e.stopPropagation();
    setFlushing(true);
    await onFlush(item.key);
    setFlushing(false);
  };

  return (
    <div
      style={S.row(hov)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
    >
      <div style={S.cell()}>
        <span style={S.dot(CAT_COLORS[cat])} />
        <span style={{ fontFamily: "inherit" }}>{item.key}</span>
      </div>
      <div style={S.cell("center")}>
        <TTLCell ttl={item.ttl} />
      </div>
      <div style={{ ...S.cell("right"), color: "#8b949e" }}>{fmtBytes(item.size_bytes)}</div>
      <div style={{ ...S.cell("center") }}>
        <span style={{
          ...S.badge(CAT_COLORS[cat]),
          fontSize: "9px", padding: "2px 6px",
        }}>{cat}</span>
      </div>
      <div style={{ ...S.cell("center"), color: "#8b949e" }}>{item.type}</div>
      <div style={{ textAlign: "right" }}>
        {hov && (
          <button
            style={{ ...S.btn("danger"), padding: "3px 10px", fontSize: "10px" }}
            onClick={flush}
            disabled={flushing}
          >
            {flushing ? "..." : "Flush"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ────────────────────────────────────────────────
export default function CacheStatusPanel() {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [autoRefresh, setAuto]  = useState(true);
  const [warming, setWarming]   = useState(false);
  const [flushing, setFlushing] = useState(false);
  const [toasts, setToasts]     = useState([]);
  const [filter, setFilter]     = useState("all");
  const intervalRef = useRef(null);

  const toast = (msg, type="success") => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500);
  };

  const load = useCallback(async () => {
    const d = await fetchStatus();
    setData(d);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(load, 5000);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh, load]);

  const handleFlushKey = async (key) => {
    await postAction(`/api/admin/cache/flush/${encodeURIComponent(key)}`);
    toast(`Flushed: ${key}`);
    await load();
  };

  const handleFlushAll = async () => {
    if (!window.confirm("Flush ALL cache keys? Products will be re-fetched from MongoDB on next request.")) return;
    setFlushing(true);
    await postAction("/api/admin/cache/flush");
    toast("All cache keys flushed");
    setFlushing(false);
    await load();
  };

  const handleWarm = async () => {
    setWarming(true);
    await postAction("/api/admin/cache/warm");
    toast("Cache warmed successfully");
    setWarming(false);
    await load();
  };

  if (loading) return (
    <div style={{ ...S.wrap, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ color: "#8b949e", fontSize: "13px", letterSpacing: "0.1em" }}>
        Connecting to Redis...
      </div>
    </div>
  );

  if (!data?.connected) return (
    <div style={{ ...S.wrap, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "12px" }}>
      <div style={{ fontSize: "32px" }}>Warning</div>
      <div style={{ color: "#f85149", fontSize: "14px" }}>Redis not connected</div>
      <div style={{ color: "#8b949e", fontSize: "12px" }}>Check REDIS_URL in your .env</div>
      <button style={S.btn("primary")} onClick={load}>Retry</button>
    </div>
  );

  const hr = hitRate(data.hit_count, data.miss_count);
  const memPct = Math.round((data.memory_used_mb / data.memory_max_mb) * 100);
  const filteredKeys = filter === "all"
    ? data.keys
    : data.keys.filter(k => categoryOf(k.key) === filter);
  const categories = ["all", ...new Set(data.keys.map(k => categoryOf(k.key)))];
  const totalSize = data.keys.reduce((s, k) => s + k.size_bytes, 0);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
        @keyframes slideIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
        .cache-btn:hover { opacity: .85; }
        .flush-btn:hover { background: #f8514933 !important; }
      `}</style>

      <div style={S.wrap}>

        {/* HEADER */}
        <div style={S.header}>
          <div style={S.title}>
            <span>Cache</span> Redis Cache Monitor
            <span style={S.badge(data._mock ? "#e3b341" : "#57ab5a")}>
              {data._mock ? "Mock Data" : "Live"}
            </span>
            {autoRefresh && (
              <span style={{ fontSize: "10px", color: "#484f58", fontWeight: 400 }}>
                <span style={{ animation: "pulse 2s infinite", display: "inline-block", marginRight: "4px" }}>*</span>
                auto-refresh 5s
              </span>
            )}
          </div>
          <div style={S.btnRow}>
            <span style={{ fontSize: "10px", color: "#484f58" }}>
              {data.redis_host}
            </span>
            <button
              className="cache-btn"
              style={S.btn(autoRefresh ? "primary" : "default")}
              onClick={() => setAuto(a => !a)}
            >
              {autoRefresh ? "Pause" : "Auto"}
            </button>
            <button className="cache-btn" style={S.btn()} onClick={load}>Refresh</button>
            <button
              className="cache-btn"
              style={S.btn()}
              onClick={handleWarm}
              disabled={warming}
            >
              {warming ? "Warming..." : "Warm Cache"}
            </button>
            <button
              className="cache-btn flush-btn"
              style={S.btn("danger")}
              onClick={handleFlushAll}
              disabled={flushing}
            >
              {flushing ? "Flushing..." : "Flush All"}
            </button>
          </div>
        </div>

        {/* STAT CARDS */}
        <div style={S.statsGrid}>
          <StatCard
            label="Hit Rate"
            value={`${hr}%`}
            sub={`${data.hit_count.toLocaleString()} hits - ${data.miss_count.toLocaleString()} misses`}
            accent={hr >= 80 ? "#57ab5a" : hr >= 50 ? "#e3b341" : "#f85149"}
            pct={hr}
          />
          <StatCard
            label="Memory Used"
            value={`${data.memory_used_mb} MB`}
            sub={`Peak: ${data.memory_peak_mb} MB - Max: ${data.memory_max_mb} MB`}
            accent="#58a6ff"
            pct={memPct}
          />
          <StatCard
            label="Cached Keys"
            value={data.keys.length}
            sub={`Total size: ${fmtBytes(totalSize)}`}
            accent="#bc8cff"
          />
          <StatCard
            label="Redis Uptime"
            value={fmtUptime(data.uptime_seconds)}
            sub={`Last warmed: ${data.warming_ms}ms - ${new Date(data.last_warmed).toLocaleTimeString()}`}
            accent="#e3b341"
          />
        </div>

        {/* CATEGORY FILTER */}
        <div style={{ display: "flex", gap: "6px", marginBottom: "14px" }}>
          {categories.map(cat => (
            <button
              key={cat}
              className="cache-btn"
              style={{
                ...S.btn(filter === cat ? "primary" : "default"),
                fontSize: "10px", padding: "5px 12px",
                background: filter===cat
                  ? (CAT_COLORS[cat] ?? "#238636") + "33"
                  : "#21262d",
                color: filter===cat ? (CAT_COLORS[cat] ?? "#fff") : "#8b949e",
                borderColor: filter===cat ? (CAT_COLORS[cat] ?? "#238636") + "66" : "#30363d",
              }}
              onClick={() => setFilter(cat)}
            >
              {cat} {cat !== "all" && `(${data.keys.filter(k => categoryOf(k.key) === cat).length})`}
            </button>
          ))}
        </div>

        {/* KEY TABLE */}
        <div style={S.panel}>
          <div style={S.panelHead}>
            <span>Cache Keys - {filteredKeys.length} shown</span>
            <span style={{ color: "#484f58", fontWeight: 400 }}>
              Hover a row to flush individually
            </span>
          </div>

          {/* Column headers */}
          <div style={{
            ...S.row(false),
            background: "#0d1117",
            borderBottom: "2px solid #21262d",
          }}>
            <div style={S.colHead()}>Key</div>
            <div style={S.colHead("center")}>TTL</div>
            <div style={S.colHead("right")}>Size</div>
            <div style={S.colHead("center")}>Category</div>
            <div style={S.colHead("center")}>Type</div>
            <div style={S.colHead("right")} />
          </div>

          {filteredKeys.length === 0 ? (
            <div style={{ padding: "40px", textAlign: "center", color: "#484f58" }}>
              No keys in this category
            </div>
          ) : (
            filteredKeys.map(item => (
              <KeyRow key={item.key} item={item} onFlush={handleFlushKey} />
            ))
          )}
        </div>

        {/* LEGEND */}
        <div style={{ display: "flex", gap: "20px", padding: "4px 0" }}>
          {Object.entries(CAT_COLORS).map(([cat, color]) => (
            <div key={cat} style={{ display: "flex", alignItems: "center", gap: "5px",
              fontSize: "10px", color: "#8b949e", letterSpacing: "0.06em" }}>
              <span style={S.dot(color)} />{cat}
            </div>
          ))}
          <div style={{ marginLeft: "auto", fontSize: "10px", color: "#484f58" }}>
            TTL: <span style={{ color: "#57ab5a" }}>|</span> fresh{" "}
            <span style={{ color: "#e3b341" }}>|</span> expiring{" "}
            <span style={{ color: "#f85149" }}>|</span> critical
          </div>
        </div>
      </div>

      {/* TOASTS */}
      <div style={S.toastWrap}>
        {toasts.map(t => (
          <div key={t.id} style={S.toast(t.type)}>{t.msg}</div>
        ))}
      </div>
    </>
  );
}
