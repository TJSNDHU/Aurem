/**
 * BrainGraphShare — PUBLIC landing page for a Graphify snapshot
 * ═══════════════════════════════════════════════════════════════════════════
 * Route: /graph/share/:id    (NO auth required)
 *
 * This page is what an external AI (or a human reviewer) sees when the admin
 * sends them a share link. It offers:
 *   - Snapshot stats (nodes / edges / files / god-nodes)
 *   - One-click downloads: graph.json, GRAPH_REPORT.md
 *   - A ready-to-paste AI prompt with clear instructions
 *   - Native share menu (navigator.share) + copy-link + WhatsApp/X/LinkedIn
 *   - Copy-to-clipboard for everything
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Brain, Download, Copy, Share2, FileJson, FileText, MessageSquare,
  Link as LinkIcon, Sparkles, CheckCircle2, AlertTriangle, Clock,
} from "lucide-react";
import { BACKEND_URL } from "../lib/api";

const G = "#C9A227";
const API = BACKEND_URL;

export default function BrainGraphShare() {
  const { id } = useParams();
  const [meta, setMeta] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [loadErr, setLoadErr] = useState(null);
  const [copied, setCopied] = useState(null);

  const shareUrl = useMemo(
    () => `${typeof window !== "undefined" ? window.location.origin : ""}/graph/share/${id}`,
    [id]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [m, p] = await Promise.all([
          fetch(`${API}/api/graphify/share/${id}/meta`).then((r) =>
            r.ok ? r.json() : Promise.reject(new Error(`meta ${r.status}`))
          ),
          fetch(`${API}/api/graphify/share/${id}/prompt`).then((r) =>
            r.ok ? r.json() : Promise.reject(new Error(`prompt ${r.status}`))
          ),
        ]);
        if (cancelled) return;
        setMeta(m);
        setPrompt(p.prompt || "");
      } catch (e) {
        if (!cancelled) setLoadErr(e.message || "Failed to load snapshot");
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const copy = useCallback((text, label) => {
    try {
      navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    } catch { /* ignore */ }
  }, []);

  const nativeShare = useCallback(async () => {
    const shareData = {
      title: "AUREM Brain Graph",
      text: "Here's an AUREM codebase knowledge graph for your review.",
      url: shareUrl,
    };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else {
        copy(shareUrl, "Link copied");
      }
    } catch { /* user cancelled */ }
  }, [shareUrl, copy]);

  // ERROR STATE
  if (loadErr) {
    return (
      <div className="min-h-screen bg-[#050505] text-[#F4F4F4] flex items-center justify-center p-6" data-testid="share-error">
        <div
          className="max-w-md w-full p-8 rounded-2xl text-center"
          style={{ background: "rgba(12,12,16,0.85)", border: `1px solid ${G}33` }}
        >
          <AlertTriangle size={32} className="mx-auto mb-3 text-red-400" />
          <h1 className="text-xl font-semibold mb-1">Snapshot unavailable</h1>
          <p className="text-sm text-[#999]">{loadErr}</p>
          <p className="text-xs text-[#666] mt-4">
            The link may have expired or been revoked by the owner.
          </p>
        </div>
      </div>
    );
  }

  // LOADING STATE
  if (!meta) {
    return (
      <div className="min-h-screen bg-[#050505] text-[#F4F4F4] flex items-center justify-center" data-testid="share-loading">
        <div className="flex items-center gap-3 text-sm text-[#999]">
          <div className="size-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: G }} />
          Loading knowledge graph…
        </div>
      </div>
    );
  }

  const stats = meta.stats || {};
  const jsonUrl = `${API}/api/graphify/share/${id}/download/graph.json`;
  const mdUrl = `${API}/api/graphify/share/${id}/download/report.md`;
  const gods = (stats.god_nodes || []).slice(0, 8);

  const shareLinks = [
    {
      name: "WhatsApp",
      href: `https://wa.me/?text=${encodeURIComponent(`AUREM Brain Graph — ${shareUrl}`)}`,
    },
    {
      name: "Twitter",
      href: `https://twitter.com/intent/tweet?text=${encodeURIComponent("AUREM Brain Graph — ")}&url=${encodeURIComponent(shareUrl)}`,
    },
    {
      name: "LinkedIn",
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
    },
    {
      name: "Email",
      href: `mailto:?subject=${encodeURIComponent("AUREM Brain Graph")}&body=${encodeURIComponent(`Review link:\n${shareUrl}`)}`,
    },
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-[#F4F4F4]" data-testid="share-page">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
        {/* Hero */}
        <div className="flex flex-col sm:flex-row sm:items-start gap-5 mb-8">
          <div
            className="size-16 rounded-2xl flex items-center justify-center shrink-0"
            style={{ background: `linear-gradient(135deg, ${G}22, ${G}08)`, border: `1px solid ${G}44` }}
          >
            <Brain size={32} style={{ color: G }} />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2 text-xs uppercase tracking-widest text-[#999]">
              <Sparkles size={12} style={{ color: G }} /> AUREM Knowledge Graph Snapshot
            </div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight mb-2" style={{ fontFamily: "Cinzel, serif" }}>
              Second-opinion review, ready to ship
            </h1>
            <p className="text-sm text-[#bbb] max-w-2xl">
              A portable, read-only map of the AUREM codebase. Hand this to any AI (Claude,
              ChatGPT, Gemini, Cursor) for architecture review, debugging help, or a fresh
              pair of eyes, without granting live repo access.
            </p>
          </div>
        </div>

        {/* Stats */}
        <div
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6 p-4 rounded-2xl"
          style={{ background: "rgba(12,12,16,0.8)", border: `1px solid ${G}33`, backdropFilter: "blur(18px)" }}
          data-testid="stats-grid"
        >
          <Stat label="Nodes" value={stats.nodes} />
          <Stat label="Edges" value={stats.edges} />
          <Stat label="Files scanned" value={stats.files_scanned} />
          <Stat label="Communities" value={stats.communities} />
        </div>

        {/* God nodes */}
        {gods.length > 0 && (
          <div
            className="mb-6 p-4 rounded-2xl"
            style={{ background: "rgba(12,12,16,0.8)", border: "1px solid #ffffff11" }}
            data-testid="god-nodes"
          >
            <div className="text-xs uppercase tracking-wide text-[#999] mb-2">Highest connectivity (god-nodes)</div>
            <div className="flex flex-wrap gap-2">
              {gods.map((g, i) => (
                <span
                  key={i}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{ background: `${G}1A`, color: G, border: `1px solid ${G}44` }}
                >
                  {g}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Snapshot note */}
        {meta.note && (
          <div
            className="mb-6 p-4 rounded-xl text-sm italic"
            style={{ background: `${G}0A`, border: `1px solid ${G}33` }}
            data-testid="note"
          >
            “{meta.note}” <span className="not-italic text-[#666]">— from the owner</span>
          </div>
        )}

        {/* AI prompt — the hero action */}
        <div
          className="mb-6 p-5 md:p-6 rounded-2xl"
          style={{ background: "rgba(12,12,16,0.85)", border: `1px solid ${G}55`, backdropFilter: "blur(18px)" }}
          data-testid="prompt-section"
        >
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare size={18} style={{ color: G }} />
            <h2 className="font-semibold">Paste this into any AI</h2>
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full text-[#999]" style={{ background: "#ffffff08" }}>
              one-click
            </span>
          </div>
          <textarea
            readOnly
            value={prompt}
            className="w-full min-h-[220px] p-4 rounded-lg bg-black/60 border border-white/10 text-xs font-mono resize-none outline-none"
            data-testid="prompt-textarea"
          />
          <div className="flex flex-col sm:flex-row gap-2 mt-3">
            <button
              onClick={() => copy(prompt, "Prompt copied")}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold"
              style={{ background: G, color: "#0A0A0A" }}
              data-testid="copy-prompt-btn"
            >
              <Copy size={14} /> Copy prompt
            </button>
            <a
              href="https://claude.ai/new"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border"
              style={{ borderColor: `${G}55`, color: G }}
              data-testid="open-claude-btn"
            >
              Open Claude.ai →
            </a>
            <a
              href="https://chatgpt.com/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border"
              style={{ borderColor: "#ffffff22" }}
              data-testid="open-chatgpt-btn"
            >
              Open ChatGPT →
            </a>
          </div>
        </div>

        {/* Downloads */}
        <div
          className="mb-6 p-5 rounded-2xl"
          style={{ background: "rgba(12,12,16,0.8)", border: "1px solid #ffffff11" }}
          data-testid="downloads"
        >
          <div className="flex items-center gap-2 mb-3">
            <Download size={18} style={{ color: G }} />
            <h2 className="font-semibold">Attach these to your AI chat</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <DownloadCard
              icon={<FileJson size={18} style={{ color: G }} />}
              title="graph.json"
              sub="Full graph (nodes + edges + metadata). Best for structured AI ingestion."
              href={jsonUrl}
              testid="download-json"
            />
            <DownloadCard
              icon={<FileText size={18} style={{ color: G }} />}
              title="GRAPH_REPORT.md"
              sub="Human-readable summary: god-nodes, surprising connections, suggested questions."
              href={mdUrl}
              testid="download-md"
            />
          </div>
        </div>

        {/* Share bar */}
        <div
          className="p-5 rounded-2xl"
          style={{ background: "rgba(12,12,16,0.8)", border: "1px solid #ffffff11" }}
          data-testid="share-bar"
        >
          <div className="flex items-center gap-2 mb-3">
            <Share2 size={18} style={{ color: G }} />
            <h2 className="font-semibold">Share this snapshot</h2>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 mb-3">
            <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-black border border-white/10 text-xs font-mono truncate">
              <LinkIcon size={12} className="text-[#999] shrink-0" />
              <span className="truncate">{shareUrl}</span>
            </div>
            <button
              onClick={() => copy(shareUrl, "Link copied")}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
              style={{ background: G, color: "#0A0A0A" }}
              data-testid="copy-link-btn"
            >
              <Copy size={14} /> Copy link
            </button>
            <button
              onClick={nativeShare}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border"
              style={{ borderColor: `${G}55`, color: G }}
              data-testid="native-share-btn"
            >
              <Share2 size={14} /> Share
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {shareLinks.map((s) => (
              <a
                key={s.name}
                href={s.href}
                target="_blank"
                rel="noreferrer"
                className="text-xs px-3 py-1.5 rounded-lg border hover:bg-white/5"
                style={{ borderColor: "#ffffff22", color: "#ddd" }}
                data-testid={`share-${s.name.toLowerCase()}`}
              >
                {s.name}
              </a>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 flex items-center justify-between text-xs text-[#666] flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Clock size={12} />
            Expires {fmtDate(meta.expires_at)} · snapshot <code>{id}</code>
          </div>
          <div className="flex items-center gap-1">
            Powered by <span style={{ color: G }}>AUREM</span> · Graphify
          </div>
        </div>
      </div>

      {/* Copied toast */}
      {copied && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm z-50 flex items-center gap-2"
          style={{ background: "#14532D", color: "#fff", border: "1px solid #16A34A55" }}
          data-testid="copied-toast"
        >
          <CheckCircle2 size={14} /> {copied}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="p-3 rounded-lg bg-black/40 text-center">
      <div className="text-2xl font-semibold" style={{ color: G }}>{value ?? "—"}</div>
      <div className="text-[10px] text-[#999] uppercase tracking-wide mt-1">{label}</div>
    </div>
  );
}

function DownloadCard({ icon, title, sub, href, testid }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="flex items-start gap-3 p-4 rounded-xl border border-white/10 hover:border-[#C9A227]/50 transition"
      style={{ background: "#00000055" }}
      data-testid={testid}
    >
      <div>{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-sm mb-0.5">{title}</div>
        <div className="text-xs text-[#999]">{sub}</div>
      </div>
      <Download size={16} className="text-[#999] shrink-0" />
    </a>
  );
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch { return iso.slice(0, 10); }
}
