/**
 * AdminBrainGraph — Build + share a portable AUREM codebase knowledge graph
 * ═══════════════════════════════════════════════════════════════════════════
 * Route: /admin/brain-graph
 * Access: super_admin
 *
 * Problem solved: External AIs (Claude.ai, ChatGPT, Gemini) can't read the
 * live codebase. Admin builds a Graphify snapshot (deterministic AST, $0 cost)
 * which gets a public share URL + a ready-to-paste prompt. Paste the URL or
 * prompt into any AI chat to get an informed second-opinion / debugging.
 */
import React, { useState, useEffect, useCallback } from "react";
import useAuthFetch from "../hooks/useAuthFetch";
import {
  Brain, Zap, Share2, Download, Copy, RefreshCw, CheckCircle2,
  ExternalLink, Trash2, Clock, FileJson, FileText, MessageSquare,
} from "lucide-react";
import { BACKEND_URL } from "../lib/api";

const G = "#C9A227";
const API = BACKEND_URL;

export default function AdminBrainGraph() {
  const { apiJson, token } = useAuthFetch();
  const [snapshots, setSnapshots] = useState([]);
  const [building, setBuilding] = useState(false);
  const [includeFrontend, setIncludeFrontend] = useState(true);
  const [note, setNote] = useState("");
  const [expiresDays, setExpiresDays] = useState(7);
  const [latest, setLatest] = useState(null);
  const [promptOpen, setPromptOpen] = useState(null); // snapshot_id or null
  const [promptText, setPromptText] = useState("");
  const [toast, setToast] = useState(null);

  const push = useCallback((m, t = "info") => {
    setToast({ m, t });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(async () => {
    try {
      const d = await apiJson("/api/graphify/snapshots");
      setSnapshots(d.snapshots || []);
    } catch (e) {
      push(`Load failed: ${e.message}`, "error");
    }
  }, [apiJson, push]);

  useEffect(() => { load(); }, [load]);

  const build = async () => {
    setBuilding(true);
    setLatest(null);
    try {
      const d = await apiJson("/api/graphify/snapshot", {
        method: "POST",
        body: {
          include_frontend: includeFrontend,
          note: note || null,
          expires_in_days: Number(expiresDays) || 7,
        },
      });
      setLatest(d);
      push(`Snapshot ready — ${d?.stats?.nodes || 0} nodes, ${d?.stats?.edges || 0} edges`, "ok");
      load();
    } catch (e) {
      push(`Build failed: ${e.message}`, "error");
    } finally {
      setBuilding(false);
    }
  };

  const revoke = async (sid) => {
    if (!window.confirm(`Revoke snapshot ${sid}? External AIs will no longer be able to access it.`)) return;
    try {
      await apiJson(`/api/graphify/snapshot/${sid}`, { method: "DELETE" });
      push("Revoked", "ok");
      load();
    } catch (e) {
      push(`Revoke failed: ${e.message}`, "error");
    }
  };

  const copy = (text, label = "Copied") => {
    try {
      navigator.clipboard.writeText(text);
      push(label, "ok");
    } catch {
      push("Copy not supported — select manually", "error");
    }
  };

  const shareUrl = (sid) => `${window.location.origin}/graph/share/${sid}`;

  const loadPrompt = async (sid) => {
    try {
      // Public endpoint — no auth header required
      const r = await fetch(`${API}/api/graphify/share/${sid}/prompt`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setPromptText(d.prompt || "");
      setPromptOpen(sid);
    } catch (e) {
      push(`Prompt load failed: ${e.message}`, "error");
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#F4F4F4] p-6 md:p-10" data-testid="admin-brain-graph">
      {/* Header */}
      <div className="max-w-6xl mx-auto">
        <div className="flex items-start gap-4 mb-8">
          <div
            className="size-14 rounded-2xl flex items-center justify-center"
            style={{ background: `linear-gradient(135deg, ${G}22, ${G}08)`, border: `1px solid ${G}44` }}
          >
            <Brain size={28} style={{ color: G }} />
          </div>
          <div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight" style={{ fontFamily: "Cinzel, serif" }}>
              AUREM Brain Graph
            </h1>
            <p className="text-sm text-[#999] mt-1 max-w-2xl">
              Build a portable knowledge graph of the codebase. Share the link with any external AI
              (Claude.ai / ChatGPT / Gemini) for second-opinion debugging, no repo access needed.
            </p>
          </div>
        </div>

        {/* Build panel */}
        <div
          className="rounded-2xl p-6 md:p-8 mb-8"
          style={{
            background: "rgba(12,12,16,0.8)",
            border: `1px solid ${G}33`,
            backdropFilter: "blur(18px)",
          }}
          data-testid="build-panel"
        >
          <div className="flex items-center gap-2 mb-4">
            <Zap size={18} style={{ color: G }} />
            <h2 className="text-lg font-semibold">Forge new snapshot</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <label className="flex items-center gap-3 px-4 py-3 rounded-lg bg-black/40 border border-white/10 cursor-pointer">
              <input
                type="checkbox"
                checked={includeFrontend}
                onChange={(e) => setIncludeFrontend(e.target.checked)}
                className="accent-[#C9A227]"
                data-testid="include-frontend-toggle"
              />
              <span className="text-sm">Include frontend (<code>/app/frontend/src</code>)</span>
            </label>

            <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-black/40 border border-white/10">
              <Clock size={16} className="text-[#999]" />
              <input
                type="number"
                min="1"
                max="30"
                value={expiresDays}
                onChange={(e) => setExpiresDays(e.target.value)}
                className="w-16 bg-transparent text-sm outline-none"
                data-testid="expires-days-input"
              />
              <span className="text-sm text-[#999]">days until expiry</span>
            </div>

            <input
              type="text"
              placeholder="Note for AI (what to review)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="px-4 py-3 rounded-lg bg-black/40 border border-white/10 text-sm outline-none focus:border-[#C9A227]/60"
              maxLength={300}
              data-testid="note-input"
            />
          </div>

          <button
            onClick={build}
            disabled={building}
            className="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all disabled:opacity-60"
            style={{
              background: `linear-gradient(135deg, ${G}, #8B6F1A)`,
              color: "#0A0A0A",
              boxShadow: building ? "none" : `0 6px 24px ${G}55`,
            }}
            data-testid="build-button"
          >
            {building ? <RefreshCw size={16} className="animate-spin" /> : <Brain size={16} />}
            {building ? "Building graph… (30–90s)" : "Build & share snapshot"}
          </button>

          {latest && (
            <div
              className="mt-5 p-4 rounded-xl"
              style={{ background: `${G}0A`, border: `1px solid ${G}55` }}
              data-testid="latest-snapshot"
            >
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 size={16} style={{ color: G }} />
                <span className="text-sm font-semibold">Snapshot ready</span>
                <code className="ml-auto text-xs text-[#999]">{latest.snapshot_id}</code>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center mb-3">
                <Stat label="Nodes" value={latest.stats?.nodes} />
                <Stat label="Edges" value={latest.stats?.edges} />
                <Stat label="Files" value={latest.stats?.files_scanned} />
                <Stat label="Communities" value={latest.stats?.communities} />
                <Stat label="Expires" value={fmtDate(latest.expires_at)} />
              </div>
              <SnapshotActions
                sid={latest.snapshot_id}
                shareUrl={shareUrl(latest.snapshot_id)}
                onCopy={copy}
                onPrompt={() => loadPrompt(latest.snapshot_id)}
              />
            </div>
          )}
        </div>

        {/* Snapshots list */}
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Share2 size={18} style={{ color: G }} /> Past snapshots
          </h2>
          <button onClick={load} className="text-xs text-[#999] hover:text-[#C9A227] flex items-center gap-1" data-testid="refresh-snapshots">
            <RefreshCw size={12} /> refresh
          </button>
        </div>

        <div className="space-y-3">
          {snapshots.length === 0 && (
            <div className="text-center py-10 text-sm text-[#666] border border-dashed border-white/10 rounded-xl">
              No snapshots yet. Forge one above to get started.
            </div>
          )}
          {snapshots.map((s) => (
            <div
              key={s.snapshot_id}
              className="p-4 rounded-xl flex flex-col md:flex-row md:items-center gap-4"
              style={{
                background: "rgba(10,10,14,0.7)",
                border: `1px solid ${s.is_active ? G + "33" : "#444444"}`,
                opacity: s.is_active ? 1 : 0.55,
              }}
              data-testid={`snapshot-${s.snapshot_id}`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <code className="text-xs" style={{ color: G }}>{s.snapshot_id}</code>
                  {s.is_active ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      active
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30">
                      {s.revoked ? "revoked" : "expired"}
                    </span>
                  )}
                  {s.include_frontend && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-[#999]">+frontend</span>
                  )}
                </div>
                <div className="text-xs text-[#999] flex flex-wrap gap-x-3">
                  <span>{s.stats?.nodes || 0} nodes · {s.stats?.edges || 0} edges</span>
                  <span>built {fmtDate(s.created_at)}</span>
                  <span>expires {fmtDate(s.expires_at)}</span>
                </div>
                {s.note && <div className="text-xs text-[#bbb] mt-1 italic">“{s.note}”</div>}
              </div>

              {s.is_active && (
                <div className="flex flex-wrap items-center gap-2">
                  <SnapshotActions
                    sid={s.snapshot_id}
                    shareUrl={shareUrl(s.snapshot_id)}
                    onCopy={copy}
                    onPrompt={() => loadPrompt(s.snapshot_id)}
                    compact
                  />
                  <button
                    onClick={() => revoke(s.snapshot_id)}
                    className="p-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10"
                    title="Revoke"
                    data-testid={`revoke-${s.snapshot_id}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Prompt modal */}
      {promptOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setPromptOpen(null)}
          data-testid="prompt-modal"
        >
          <div
            className="w-full max-w-3xl rounded-2xl p-6 max-h-[85vh] flex flex-col"
            style={{ background: "#0C0C10", border: `1px solid ${G}55` }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare size={18} style={{ color: G }} />
              <h3 className="font-semibold">AI-ready prompt</h3>
              <code className="ml-auto text-xs text-[#999]">{promptOpen}</code>
            </div>
            <p className="text-xs text-[#999] mb-3">
              Paste this into <strong>Claude.ai</strong>, ChatGPT, Gemini or any AI chat.
              It includes context, links to the graph, and instructions.
            </p>
            <textarea
              readOnly
              value={promptText}
              className="flex-1 min-h-[240px] w-full p-4 rounded-lg bg-black border border-white/10 text-xs font-mono resize-none outline-none"
              data-testid="prompt-textarea"
            />
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => copy(promptText, "Prompt copied — paste into your AI chat")}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: G, color: "#0A0A0A" }}
                data-testid="copy-prompt-button"
              >
                <Copy size={14} /> Copy prompt
              </button>
              <button
                onClick={() => setPromptOpen(null)}
                className="px-4 py-2 rounded-lg border border-white/10 text-sm"
                data-testid="close-prompt-button"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm z-50"
          style={{
            background: toast.t === "error" ? "#7F1D1D" : toast.t === "ok" ? "#14532D" : "#1F2937",
            color: "#fff",
            border: `1px solid ${toast.t === "error" ? "#DC2626" : toast.t === "ok" ? "#16A34A" : "#C9A227"}55`,
          }}
          data-testid="toast"
        >
          {toast.m}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="p-2 rounded-lg bg-black/40">
      <div className="text-lg font-semibold" style={{ color: G }}>{value ?? "—"}</div>
      <div className="text-[10px] text-[#999] uppercase tracking-wide">{label}</div>
    </div>
  );
}

function SnapshotActions({ sid, shareUrl, onCopy, onPrompt, compact = false }) {
  const jsonUrl = `${API}/api/graphify/share/${sid}/download/graph.json`;
  const mdUrl = `${API}/api/graphify/share/${sid}/download/report.md`;
  const btn = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition";
  return (
    <div className="flex flex-wrap gap-2" data-testid={`actions-${sid}`}>
      <button
        onClick={() => onCopy(shareUrl, "Share URL copied")}
        className={btn}
        style={{ borderColor: `${G}55`, color: G, background: `${G}11` }}
        data-testid={`copy-share-${sid}`}
      >
        <Share2 size={12} /> {compact ? "Link" : "Copy share link"}
      </button>
      <button
        onClick={onPrompt}
        className={btn}
        style={{ borderColor: `${G}55`, color: G, background: `${G}11` }}
        data-testid={`copy-prompt-${sid}`}
      >
        <MessageSquare size={12} /> {compact ? "Prompt" : "AI prompt"}
      </button>
      <a
        href={jsonUrl}
        target="_blank"
        rel="noreferrer"
        className={btn}
        style={{ borderColor: "#ffffff22", color: "#F4F4F4" }}
        data-testid={`download-json-${sid}`}
      >
        <FileJson size={12} /> JSON
      </a>
      <a
        href={mdUrl}
        target="_blank"
        rel="noreferrer"
        className={btn}
        style={{ borderColor: "#ffffff22", color: "#F4F4F4" }}
        data-testid={`download-md-${sid}`}
      >
        <FileText size={12} /> Report
      </a>
      <a
        href={shareUrl}
        target="_blank"
        rel="noreferrer"
        className={btn}
        style={{ borderColor: "#ffffff22", color: "#F4F4F4" }}
        data-testid={`open-share-${sid}`}
      >
        <ExternalLink size={12} /> Open
      </a>
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
      " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch { return iso.slice(0, 10); }
}
