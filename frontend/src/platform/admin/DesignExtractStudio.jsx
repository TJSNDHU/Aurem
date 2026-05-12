/**
 * DesignExtractStudio — iter 322ep
 * Admin UI for /api/admin/design-extract — pull DTCG / Tailwind /
 * shadcn variables off any competitor URL.
 *
 * Route: /admin/design-extract
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2, Sparkles, Palette, Copy, Download, RefreshCw,
  AlertTriangle, Type, ExternalLink, CheckCircle,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};

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

function copy(text) {
  if (!text) return;
  navigator.clipboard?.writeText(text).catch(() => {});
}

function downloadFile(filename, text) {
  const blob = new Blob([text || ""], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function DesignExtractStudio() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("https://stripe.com");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [extract, setExtract] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [exportFmt, setExportFmt] = useState(null);
  const [exportContent, setExportContent] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([
        fetch(`${API}/api/admin/design-extract/summary`, { headers: authHeaders() }).then(r => r.json()),
        fetch(`${API}/api/admin/design-extract/history?limit=10`, { headers: authHeaders() }).then(r => r.json()),
      ]);
      if (s?.ok) setSummary(s);
      if (h?.ok) setHistory(h.rows || []);
    } catch (e) {
      // soft fail
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const runExtract = async () => {
    setLoading(true);
    setError(null);
    setExtract(null);
    setExportFmt(null);
    setExportContent("");
    try {
      const res = await fetch(`${API}/api/admin/design-extract/run`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || "Extraction failed");
      } else {
        setExtract(data.extract);
        refresh();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const runExport = async (fmt) => {
    if (!extract) return;
    setExportFmt(fmt);
    setExportContent("Loading...");
    try {
      const r = await fetch(
        `${API}/api/admin/design-extract/export/${fmt}?url=${encodeURIComponent(extract.url || extract.source_url)}`,
        { headers: authHeaders() },
      );
      const data = await r.json();
      if (data.ok) setExportContent(data.content || "");
      else setExportContent(`/* ${data.detail || "not available"} */`);
    } catch (e) {
      setExportContent(`/* ${e} */`);
    }
  };

  const colors = extract?.colors || {};
  const fonts = extract?.fonts || {};
  const palette = colors.palette || [];

  return (
    <div data-testid="design-extract-studio" style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Sparkles size={26} color={GOLD} />
            <h1 style={{ fontSize: 26, fontWeight: 700, margin: 0, letterSpacing: 0.3 }}>
              Design Extract Studio
            </h1>
          </div>
          <p style={{ color: TEXT_DIM, marginTop: 6, fontSize: 13 }}>
            Pull DTCG tokens, Tailwind config, shadcn variables & CSS from any URL. Powered by <code style={{ color: GOLD }}>npx designlang</code>.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button data-testid="back-btn" onClick={() => navigate("/admin/boardroom")}
                  style={btn(false)}>← Back</button>
          <button data-testid="refresh-btn" onClick={refresh} style={btn(false)}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Summary tiles */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
          <Tile label="Total extracts" value={summary.total_logs} sub={`${summary.success_rate ?? 0}% success`} />
          <Tile label="Last 7 days" value={summary.last_7d} sub="recent runs" />
          <Tile label="Saved" value={summary.saved_extracts} sub="persisted tokens" />
          <Tile label="Failures" value={summary.failed} sub={`vs ${summary.success} ok`} accent={summary.failed > summary.success ? "warn" : null} />
        </div>
      )}

      {/* Run form */}
      <div style={{ ...GLASS, padding: 18, marginBottom: 18 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Palette size={18} color={GOLD} />
          <span style={{ fontWeight: 600 }}>Extract design from URL</span>
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
          <input data-testid="design-url-input" value={url} onChange={(e) => setUrl(e.target.value)}
                 placeholder="https://anycompany.com"
                 style={{
                   flex: 1, background: "rgba(0,0,0,0.4)", border: `1px solid ${BORDER}`,
                   borderRadius: 10, padding: "10px 14px", color: TEXT, fontSize: 14,
                 }} />
          <button data-testid="extract-run-btn" disabled={loading || !url} onClick={runExtract}
                  style={btn(true, loading || !url)}>
            {loading ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            {loading ? "Extracting…" : "Run"}
          </button>
        </div>
        {error && (
          <div style={{ marginTop: 12, color: "#FF7676", fontSize: 13, display: "flex", gap: 8, alignItems: "center" }}>
            <AlertTriangle size={14} /> {error}
          </div>
        )}
      </div>

      {/* Result */}
      {extract && (
        <div style={{ ...GLASS, padding: 18, marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <CheckCircle size={18} color="#67E8A0" />
              <span style={{ fontWeight: 600 }}>{extract.url || extract.source_url}</span>
              {extract.score != null && (
                <span style={{ background: "rgba(212,175,55,0.16)", color: GOLD,
                               padding: "2px 8px", borderRadius: 6, fontSize: 11 }}>
                  Score {extract.score}/100
                </span>
              )}
            </div>
            <a href={extract.url || extract.source_url} target="_blank" rel="noopener noreferrer"
               style={{ color: TEXT_DIM, fontSize: 12, display: "flex", gap: 4 }}>
              <ExternalLink size={12} /> open
            </a>
          </div>

          {/* Colors grid */}
          <SectionTitle icon={Palette} text="Colors" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginBottom: 14 }}>
            {[
              ["primary", colors.primary],
              ["secondary", colors.secondary],
              ["accent", colors.accent],
              ["bg", colors.bg],
              ["text", colors.text],
            ].filter(([_, v]) => v).map(([k, v]) => (
              <Swatch key={k} label={k} hex={v} onCopy={() => copy(v)} />
            ))}
          </div>

          {palette.length > 0 && (
            <>
              <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>Palette ({palette.length})</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 6, marginBottom: 16 }}>
                {palette.slice(0, 12).map((c, i) => (
                  <button data-testid={`palette-hex-${i}`} key={i} title={c} onClick={() => copy(c)}
                          style={{
                            height: 38, background: c, border: `1px solid ${BORDER}`,
                            borderRadius: 8, cursor: "pointer",
                          }} />
                ))}
              </div>
            </>
          )}

          {/* Fonts */}
          <SectionTitle icon={Type} text="Fonts" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 14 }}>
            <FontTile label="Heading" value={fonts.heading} />
            <FontTile label="Body" value={fonts.body} />
          </div>

          {/* Export buttons */}
          <SectionTitle icon={Download} text="Export tokens" />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {[
              ["tailwind", "tailwind.config.js"],
              ["css", "variables.css"],
              ["shadcn", "shadcn-theme.css"],
              ["tokens", "tokens.json (DTCG)"],
              ["theme", "theme.js"],
            ].map(([fmt, label]) => (
              <button data-testid={`export-${fmt}-btn`} key={fmt} onClick={() => runExport(fmt)}
                      style={btn(exportFmt === fmt)}>
                {label}
              </button>
            ))}
          </div>

          {exportFmt && (
            <div style={{ background: "rgba(0,0,0,0.55)", border: `1px solid ${BORDER}`,
                          borderRadius: 10, padding: 12, marginTop: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ color: TEXT_DIM, fontSize: 12 }}>{exportFmt}</span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button data-testid="copy-export-btn" onClick={() => copy(exportContent)} style={btn(false)}>
                    <Copy size={12} /> Copy
                  </button>
                  <button data-testid="download-export-btn"
                          onClick={() => downloadFile(`aurem-${exportFmt}.txt`, exportContent)}
                          style={btn(false)}>
                    <Download size={12} /> Download
                  </button>
                </div>
              </div>
              <pre style={{
                color: TEXT, fontSize: 12, margin: 0, whiteSpace: "pre-wrap",
                maxHeight: 320, overflow: "auto", fontFamily: "ui-monospace,monospace",
              }}>
                {exportContent}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div style={{ ...GLASS, padding: 18 }}>
          <SectionTitle icon={RefreshCw} text={`Recent extracts (${history.length})`} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 100px 80px 130px", gap: 8, padding: "6px 0",
                        color: TEXT_DIM, fontSize: 11, textTransform: "uppercase", borderBottom: `1px solid ${BORDER}` }}>
            <div>URL</div><div>Status</div><div>Palette</div><div>When</div>
          </div>
          {history.map((row, i) => (
            <div data-testid={`history-row-${i}`} key={i}
                 style={{ display: "grid", gridTemplateColumns: "1fr 100px 80px 130px",
                          gap: 8, padding: "8px 0", fontSize: 13,
                          borderBottom: `1px solid rgba(212,175,55,0.06)` }}>
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {row.url || row.source_url || "?"}
              </div>
              <div style={{ color: row.ok ? "#67E8A0" : "#FF7676" }}>
                {row.ok ? "✓ ok" : "✗ fail"}
              </div>
              <div style={{ color: TEXT_DIM }}>{row.palette_size ?? (row.colors?.palette?.length ?? "?")}</div>
              <div style={{ color: TEXT_DIM, fontSize: 11 }}>{(row.ts || "").slice(0, 19)}</div>
            </div>
          ))}
        </div>
      )}

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "8px 14px", fontSize: 13,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}

function Tile({ label, value, sub, accent }) {
  return (
    <div data-testid={`tile-${label.replace(/\s+/g, "-").toLowerCase()}`} style={{ ...GLASS, padding: 14 }}>
      <div style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, marginTop: 4,
                    color: accent === "warn" ? "#FFB36B" : TEXT }}>
        {value ?? "—"}
      </div>
      <div style={{ color: TEXT_DIM, fontSize: 11 }}>{sub}</div>
    </div>
  );
}

function SectionTitle({ icon: Icon, text }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
      <Icon size={14} color={GOLD} />
      <span style={{ fontWeight: 600, fontSize: 13, color: TEXT }}>{text}</span>
    </div>
  );
}

function Swatch({ label, hex, onCopy }) {
  return (
    <div data-testid={`swatch-${label}`} onClick={onCopy}
         style={{ cursor: "pointer", border: `1px solid ${BORDER}`, borderRadius: 10, overflow: "hidden" }}>
      <div style={{ height: 50, background: hex }} />
      <div style={{ padding: "6px 10px", fontSize: 11 }}>
        <div style={{ color: TEXT_DIM, textTransform: "uppercase" }}>{label}</div>
        <div style={{ fontFamily: "ui-monospace,monospace" }}>{hex}</div>
      </div>
    </div>
  );
}

function FontTile({ label, value }) {
  return (
    <div data-testid={`font-${label.toLowerCase()}`}
         style={{ border: `1px solid ${BORDER}`, borderRadius: 10, padding: 12 }}>
      <div style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 16, marginTop: 4, color: TEXT,
                    fontFamily: value || "ui-sans-serif,system-ui" }}>
        {value || "—"}
      </div>
    </div>
  );
}
