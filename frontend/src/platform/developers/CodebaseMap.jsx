/**
 * CodebaseMap.jsx — iter D-55
 *
 * Collapsible file-tree sidebar for the AUREM CTO chat. Lists files
 * under `/app/backend` (or any allowed sub-tree) and lets the founder
 * one-click any file → injects `/file <path>` into the chat composer
 * so the next message auto-reads the REAL bytes via D-54.
 *
 * Props:
 *   • basePath  (string, default "backend")
 *   • maxDepth  (number, default 3)
 *   • onPick    (fn(path) → ...) — called when a file row is clicked.
 *                Parent wires this to either:
 *                  (a) prepend `/file <path>` to the chat textarea, or
 *                  (b) immediately POST a chat turn with that command.
 *
 * Backend: GET /api/developers/cto/file/tree?path=…&max_depth=…
 */
import React, { useEffect, useState, useMemo } from "react";
import { FileCode, Folder, FolderOpen, ChevronDown, ChevronRight,
         Search, RefreshCw } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";


export default function CodebaseMap({ basePath = "backend",
                                       maxDepth = 3, onPick }) {
  const [tree, setTree]       = useState(null);
  const [error, setError]     = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter]   = useState("");
  const [collapsed, setCollapsed] = useState({});

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const r = await fetch(
        `${API}/api/developers/cto/file/tree` +
        `?path=${encodeURIComponent(basePath)}&max_depth=${maxDepth}`,
        { headers: devAuthHeaders() }
      );
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "tree_load_failed");
      setTree(j);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [basePath, maxDepth]);

  // Group files by parent directory so the render is a true tree.
  const grouped = useMemo(() => {
    if (!tree) return { dirs: [], byDir: {} };
    const byDir = {};
    for (const f of tree.files) {
      const parent = f.path.includes("/")
        ? f.path.slice(0, f.path.lastIndexOf("/"))
        : tree.base;
      (byDir[parent] = byDir[parent] || []).push(f);
    }
    const dirs = [{ path: tree.base, name: tree.base, depth: 0,
                     type: "dir" }, ...tree.dirs];
    return { dirs, byDir };
  }, [tree]);

  const filterLc = filter.trim().toLowerCase();

  function matchesFilter(file) {
    if (!filterLc) return true;
    return file.path.toLowerCase().includes(filterLc) ||
           file.name.toLowerCase().includes(filterLc);
  }

  function dirHasMatches(dirPath) {
    if (!filterLc) return true;
    const list = grouped.byDir[dirPath] || [];
    if (list.some(matchesFilter)) return true;
    // also check nested dirs
    return grouped.dirs.some(d =>
      d.path !== dirPath &&
      d.path.startsWith(dirPath + "/") &&
      (grouped.byDir[d.path] || []).some(matchesFilter)
    );
  }

  function toggle(dirPath) {
    setCollapsed(prev => ({ ...prev, [dirPath]: !prev[dirPath] }));
  }

  function fileColor(ext) {
    if (ext === "py")              return "#FFB454";
    if (["jsx", "tsx"].includes(ext)) return "#82AAFF";
    if (["js", "ts"].includes(ext))   return "#C3E88D";
    if (ext === "css")             return "#C792EA";
    if (ext === "md")              return "#a1958a";
    if (ext === "json")            return "#F78C6C";
    return "#a1958a";
  }

  function fmtSize(b) {
    if (!b) return "";
    if (b < 1024)       return `${b}b`;
    if (b < 1024 * 1024) return `${(b/1024).toFixed(0)}k`;
    return `${(b/1024/1024).toFixed(1)}M`;
  }

  return (
    <div data-testid="cto-codebase-map"
         style={{ display: "flex", flexDirection: "column",
                  height: "100%", color: "#F0EDE8",
                  fontFamily: "'JetBrains Mono', monospace" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 6,
                     padding: "10px 12px",
                     borderBottom: "1px solid var(--dash-divider)",
                     background: "rgba(0,0,0,0.20)" }}>
        <FolderOpen size={14} style={{ color: "#FF8C35" }} />
        <strong style={{ fontSize: 11, letterSpacing: "0.12em",
                          textTransform: "uppercase",
                          color: "#E8C86A" }}>
          Codebase Map
        </strong>
        <button data-testid="codebase-map-refresh"
                 onClick={refresh}
                 disabled={loading}
                 title="Reload file tree"
                 style={{ marginLeft: "auto",
                          background: "transparent", border: "none",
                          color: "#a1958a", cursor: "pointer",
                          padding: 4,
                          opacity: loading ? 0.4 : 1 }}>
          <RefreshCw size={12}
                      className={loading ? "aurem-anim-spin" : ""} />
        </button>
      </div>

      {/* Filter */}
      <div style={{ position: "relative",
                     padding: "8px 12px 4px 12px" }}>
        <Search size={11}
                style={{ position: "absolute", left: 20, top: 13,
                          color: "#a1958a" }} />
        <input data-testid="codebase-map-filter"
                value={filter}
                onChange={e => setFilter(e.target.value)}
                placeholder="Filter…"
                style={{ width: "100%",
                         padding: "5px 8px 5px 24px",
                         background: "rgba(255,255,255,0.04)",
                         border: "1px solid var(--dash-border)",
                         color: "#F0EDE8",
                         borderRadius: 4, fontSize: 11,
                         fontFamily: "inherit", outline: "none" }} />
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto",
                     padding: "4px 0 12px 0", fontSize: 11.5 }}>
        {error && (
          <div style={{ padding: "8px 12px", color: "#FF6060",
                         fontSize: 11 }}>
            {error}
          </div>
        )}
        {!error && !tree && loading && (
          <div style={{ padding: "8px 12px", color: "#a1958a",
                         fontSize: 11 }}>
            Loading {basePath}…
          </div>
        )}
        {tree && grouped.dirs.map(d => {
          const isCollapsed = collapsed[d.path];
          const dirFiles    = grouped.byDir[d.path] || [];
          const visibleFiles = dirFiles.filter(matchesFilter);
          if (filterLc && !dirHasMatches(d.path) && d.depth > 0) {
            return null;
          }
          return (
            <div key={d.path}>
              <div onClick={() => toggle(d.path)}
                   data-testid={`codebase-map-dir-${d.path}`}
                   style={{ display: "flex", alignItems: "center",
                            gap: 4, padding: "3px 12px",
                            paddingLeft: 12 + (d.depth * 12),
                            cursor: "pointer",
                            color: "#a1958a" }}
                   onMouseEnter={e =>
                     e.currentTarget.style.background = "rgba(255,107,0,0.06)"}
                   onMouseLeave={e =>
                     e.currentTarget.style.background = "transparent"}>
                {isCollapsed
                  ? <ChevronRight size={10} />
                  : <ChevronDown  size={10} />}
                {isCollapsed
                  ? <Folder     size={11} style={{ color: "#FF8C35" }} />
                  : <FolderOpen size={11} style={{ color: "#FF8C35" }} />}
                <span style={{ color: "#E8C86A" }}>
                  {d.name === tree.base ? d.name : d.name + "/"}
                </span>
                {dirFiles.length > 0 && (
                  <span style={{ marginLeft: "auto",
                                   color: "#a1958a", fontSize: 10 }}>
                    {dirFiles.length}
                  </span>
                )}
              </div>
              {!isCollapsed && visibleFiles.map(f => (
                <div key={f.path}
                     data-testid={`codebase-map-file-${f.path}`}
                     onClick={() => onPick && onPick(f.path)}
                     style={{ display: "flex", alignItems: "center",
                              gap: 6, padding: "2px 12px",
                              paddingLeft: 24 + (d.depth * 12),
                              cursor: "pointer",
                              color: "#F0EDE8" }}
                     title={`${f.path} · ${fmtSize(f.size)}`}
                     onMouseEnter={e => {
                       e.currentTarget.style.background =
                         "rgba(255,107,0,0.10)";
                     }}
                     onMouseLeave={e => {
                       e.currentTarget.style.background = "transparent";
                     }}>
                  <FileCode size={10}
                              style={{ color: fileColor(f.ext) }} />
                  <span style={{ overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  whiteSpace: "nowrap" }}>
                    {f.name}
                  </span>
                  <span style={{ marginLeft: "auto",
                                   color: "#a1958a", fontSize: 10 }}>
                    {fmtSize(f.size)}
                  </span>
                </div>
              ))}
            </div>
          );
        })}
        {tree && tree.count.files === 0 && (
          <div style={{ padding: "12px", fontSize: 11,
                         color: "#a1958a", textAlign: "center" }}>
            No files under {tree.base}
          </div>
        )}
      </div>

      {tree && (
        <div style={{ padding: "6px 12px",
                       borderTop: "1px solid var(--dash-divider)",
                       fontSize: 10, color: "#a1958a",
                       background: "rgba(0,0,0,0.20)" }}>
          {tree.count.files} files · {tree.count.dirs} dirs · click to inject
        </div>
      )}
    </div>
  );
}
