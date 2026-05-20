/**
 * AdminLinksHub — One folder for every AUREM URL the operator uses
 * ═══════════════════════════════════════════════════════════════════════════
 * Route: /admin/links
 * Access: super_admin
 *
 * Problem solved: Operator was jumping between 14+ admin pages and
 * manually tracking share URLs for brain graphs, case study PDFs, system
 * audits, status pages etc. This page pulls every live URL from the DB,
 * groups them by folder, and gives one-click Open / Copy / Share actions.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import useAuthFetch from "../hooks/useAuthFetch";
import {
  FolderOpen, Search, Copy, ExternalLink, Share2, CheckCircle2,
  Shield, Brain, FileText, Activity, Zap, Monitor, Wrench, Settings,
  Sparkles, Package, BarChart3, Eye, Network, Globe, Radio, Calendar,
  Target, ChevronDown, ChevronRight, RefreshCw, Link as LinkIcon,
} from "lucide-react";

const G = "#C9A227";

const ICON_MAP = {
  Shield, Brain, FileText, Activity, Zap, Monitor, Wrench, Settings,
  Sparkles, Package, BarChart3, Eye, Network, Globe, Radio, Calendar, Target,
};

export default function AdminLinksHub() {
  const { apiJson } = useAuthFetch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(null);
  const [collapsed, setCollapsed] = useState(() => {
    try { return JSON.parse(localStorage.getItem("aurem_links_collapsed") || "{}"); }
    catch { return {}; }
  });

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const d = await apiJson("/api/admin/links-hub");
      setData(d);
    } catch (e) {
      setErr(e.message || "Load failed");
    } finally {
      setLoading(false);
    }
  }, [apiJson]);

  useEffect(() => { load(); }, [load]);

  const toggle = (key) => {
    setCollapsed((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try { localStorage.setItem("aurem_links_collapsed", JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const copy = (text, label = "Copied") => {
    try {
      navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 1800);
    } catch { /* ignore */ }
  };

  const share = async (item) => {
    try {
      if (navigator.share) {
        await navigator.share({ title: item.title, text: item.description || "", url: item.url });
      } else {
        copy(item.url, "Link copied (no native share)");
      }
    } catch { /* user cancelled */ }
  };

  const filtered = useMemo(() => {
    if (!data?.folders) return [];
    const q = query.trim().toLowerCase();
    if (!q) return data.folders;
    return data.folders
      .map((f) => ({
        ...f,
        items: (f.items || []).filter((it) =>
          (it.title || "").toLowerCase().includes(q) ||
          (it.description || "").toLowerCase().includes(q) ||
          (it.url || "").toLowerCase().includes(q)
        ),
      }))
      .filter((f) => f.items.length > 0);
  }, [data, query]);

  const totalShown = filtered.reduce((n, f) => n + (f.items?.length || 0), 0);

  return (
    <div className="min-h-screen bg-[#050505] text-[#F4F4F4] p-6 md:p-10" data-testid="admin-links-hub">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-start gap-4 mb-8">
          <div
            className="size-14 rounded-2xl flex items-center justify-center shrink-0"
            style={{ background: `linear-gradient(135deg, ${G}22, ${G}08)`, border: `1px solid ${G}44` }}
          >
            <FolderOpen size={28} style={{ color: G }} />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight" style={{ fontFamily: "Cinzel, serif" }}>
              Links Hub
            </h1>
            <p className="text-sm text-[#999] mt-1">
              Every AUREM URL in one folder. Open with one click, copy in a beat, share in two.
              {data && <> · <span style={{ color: G }}>{data.total} links</span> across {data.folder_count} folders.</>}
            </p>
          </div>
          <button
            onClick={load}
            className="px-3 py-2 rounded-lg border border-white/10 text-xs flex items-center gap-2 hover:border-[#C9A227]/50"
            data-testid="refresh-links"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        {/* Search */}
        <div
          className="mb-6 flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{ background: "rgba(12,12,16,0.85)", border: `1px solid ${G}33`, backdropFilter: "blur(18px)" }}
        >
          <Search size={16} className="text-[#999] shrink-0" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title, description, URL…"
            className="flex-1 bg-transparent outline-none text-sm"
            data-testid="search-input"
          />
          {query && (
            <span className="text-xs text-[#999]">{totalShown} match{totalShown === 1 ? "" : "es"}</span>
          )}
        </div>

        {/* States */}
        {loading && !data && (
          <div className="text-center py-16 text-sm text-[#999]">Loading links…</div>
        )}
        {err && (
          <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/5 text-red-300 text-sm">{err}</div>
        )}

        {/* Folders */}
        {filtered.map((folder) => {
          const Icon = ICON_MAP[folder.icon] || FolderOpen;
          const isCollapsed = collapsed[folder.key];
          return (
            <div
              key={folder.key}
              className="mb-4 rounded-2xl overflow-hidden"
              style={{ background: "rgba(10,10,14,0.75)", border: "1px solid #ffffff11" }}
              data-testid={`folder-${folder.key}`}
            >
              <button
                onClick={() => toggle(folder.key)}
                className="w-full flex items-center gap-3 px-5 py-4 hover:bg-white/5 transition text-left"
                data-testid={`toggle-${folder.key}`}
              >
                <Icon size={18} style={{ color: G }} />
                <span className="font-semibold flex-1">{folder.label}</span>
                <span className="text-xs text-[#999]">{folder.items.length} link{folder.items.length === 1 ? "" : "s"}</span>
                {isCollapsed ? <ChevronRight size={16} className="text-[#999]" /> : <ChevronDown size={16} className="text-[#999]" />}
              </button>

              {!isCollapsed && (
                <div className="border-t border-white/5">
                  {folder.items.length === 0 ? (
                    <div className="p-4 text-xs text-[#666]">No items in this folder yet.</div>
                  ) : (
                    <ul>
                      {folder.items.map((item) => (
                        <LinkRow
                          key={item.id || item.url}
                          item={item}
                          onCopy={copy}
                          onShare={share}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {data && filtered.length === 0 && !loading && (
          <div className="text-center py-10 text-sm text-[#666] border border-dashed border-white/10 rounded-xl">
            No links match “{query}”.
          </div>
        )}
      </div>

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

function LinkRow({ item, onCopy, onShare }) {
  return (
    <li
      className="group flex items-start md:items-center gap-3 px-5 py-3.5 border-b border-white/5 hover:bg-white/[0.03] flex-col md:flex-row"
      data-testid={`link-${item.id || item.title}`}
    >
      <div className="flex-1 min-w-0 w-full">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-sm">{item.title}</span>
          {item.is_public && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: `${G}1A`, color: G, border: `1px solid ${G}44` }}>
              public
            </span>
          )}
        </div>
        {item.description && (
          <div className="text-xs text-[#999] mt-0.5 truncate">{item.description}</div>
        )}
        <div className="flex items-center gap-1 text-[11px] text-[#666] mt-1 font-mono truncate">
          <LinkIcon size={10} className="shrink-0" />
          <span className="truncate">{item.url}</span>
        </div>
      </div>

      <div className="flex items-center gap-1.5 shrink-0" data-testid={`actions-${item.id || item.title}`}>
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          title="Open"
          className="p-2 rounded-lg border border-white/10 hover:border-[#C9A227]/60 hover:bg-[#C9A227]/10"
          data-testid={`open-${item.id || item.title}`}
        >
          <ExternalLink size={14} style={{ color: G }} />
        </a>
        <button
          onClick={() => onCopy(item.url, "Link copied")}
          title="Copy URL"
          className="p-2 rounded-lg border border-white/10 hover:border-[#C9A227]/60 hover:bg-[#C9A227]/10"
          data-testid={`copy-${item.id || item.title}`}
        >
          <Copy size={14} style={{ color: G }} />
        </button>
        {item.can_share && (
          <button
            onClick={() => onShare(item)}
            title="Share"
            className="p-2 rounded-lg border border-white/10 hover:border-[#C9A227]/60 hover:bg-[#C9A227]/10"
            data-testid={`share-${item.id || item.title}`}
          >
            <Share2 size={14} style={{ color: G }} />
          </button>
        )}
      </div>
    </li>
  );
}
