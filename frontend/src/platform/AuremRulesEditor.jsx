/**
 * AuremRulesEditor.jsx — iter D-79
 *
 * Per-customer `.aurem-rules.md` editor. Lets the user paste their
 * house style / stack constraints / "never do X" rules into a
 * Markdown blob that the CTO agent will inject as system context
 * on every chat turn.
 *
 * NO MOCKS: GET /api/cto/rules + PUT /api/cto/rules are real,
 * per-user, JWT-scoped. Empty state is honest — no fake sample.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Save, Trash2, FileText, RefreshCw } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const MAX_BYTES = 16 * 1024;

function authHeaders() {
  const t =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") || "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function AuremRulesEditor() {
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState("");
  const [meta, setMeta] = useState({ version: 0, updated_at: null });
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`${API}/api/cto/rules`,
        { headers: { ...authHeaders() } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setDraft(j.rules_md || "");
      setSaved(j.rules_md || "");
      setMeta({ version: j.version || 0, updated_at: j.updated_at });
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = useCallback(async () => {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const r = await fetch(`${API}/api/cto/rules`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ rules_md: draft }),
      });
      if (!r.ok) {
        const b = await r.text().catch(() => "");
        throw new Error(`HTTP ${r.status} ${b.slice(0, 160)}`);
      }
      const j = await r.json();
      setSaved(j.rules_md || "");
      setDraft(j.rules_md || "");
      setMeta({ version: j.version || 0, updated_at: j.updated_at });
      setMsg(
        j.truncated
          ? `Saved (v${j.version}) — content over 16 KB was truncated`
          : `Saved (v${j.version}, ${j.size_bytes} bytes)`,
      );
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }, [draft]);

  const wipe = useCallback(async () => {
    if (!window.confirm("Wipe all your .aurem-rules.md? This cannot be undone.")) {
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const r = await fetch(`${API}/api/cto/rules`,
        { method: "DELETE", headers: { ...authHeaders() } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setDraft("");
      setSaved("");
      setMeta({ version: 0, updated_at: null });
      setMsg("Cleared.");
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }, []);

  const dirty = draft !== saved;
  const bytes = new Blob([draft]).size;
  const over = bytes > MAX_BYTES;

  return (
    <div
      data-testid="aurem-rules-editor"
      className="border border-zinc-800 rounded-xl bg-zinc-950/70 p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-blue-300" />
          <h3 className="text-sm font-semibold tracking-wide text-zinc-100 uppercase">
            .aurem-rules.md
          </h3>
          {meta.version > 0 && (
            <span
              data-testid="aurem-rules-version"
              className="text-[10px] text-zinc-500"
            >
              v{meta.version}
            </span>
          )}
        </div>
        <button
          data-testid="aurem-rules-refresh"
          onClick={load}
          disabled={loading || busy}
          className="text-xs text-zinc-300 hover:text-white inline-flex items-center gap-1 disabled:opacity-40"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          reload
        </button>
      </div>

      <p className="text-xs text-zinc-500 mb-3 leading-relaxed">
        Your personal &quot;house style&quot; rules. The CTO agent will inject this
        into every chat as system context — so it stops asking which
        package manager you use, knows your stack preferences, and respects
        your &quot;never do X&quot; constraints. Plain Markdown, max 16 KB.
      </p>

      <textarea
        data-testid="aurem-rules-textarea"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={
          "# my house style\n" +
          "- use yarn, never npm\n" +
          "- never write to / outside /app/data\n" +
          "- React components ≤ 50 lines; extract sub-components first\n" +
          "- backend routes always under /api/* prefix"
        }
        spellCheck={false}
        rows={12}
        className="w-full font-mono text-xs bg-black border border-zinc-800 rounded-lg p-3 text-zinc-200 focus:outline-none focus:border-blue-500/60 leading-relaxed resize-vertical"
      />

      <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
        <div className="text-[10px] text-zinc-500 font-mono">
          <span className={over ? "text-red-400" : ""}>{bytes}</span>
          /{MAX_BYTES} bytes
          {dirty && (
            <span data-testid="aurem-rules-dirty" className="ml-3 text-amber-400">
              unsaved
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            data-testid="aurem-rules-delete"
            onClick={wipe}
            disabled={busy || (!saved && !draft)}
            className="text-xs border border-red-900/50 text-red-300 hover:bg-red-950/40 px-3 py-1.5 rounded inline-flex items-center gap-1 disabled:opacity-40"
          >
            <Trash2 size={12} /> clear
          </button>
          <button
            data-testid="aurem-rules-save"
            onClick={save}
            disabled={busy || !dirty}
            className="text-xs bg-blue-900/40 border border-blue-700/60 text-blue-200 hover:bg-blue-900/60 px-3 py-1.5 rounded inline-flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Save size={12} /> {busy ? "saving…" : "save"}
          </button>
        </div>
      </div>

      {msg && (
        <div
          data-testid="aurem-rules-msg"
          className="mt-3 text-xs text-emerald-300 bg-emerald-950/30 border border-emerald-900/40 rounded px-3 py-2"
        >
          {msg}
        </div>
      )}
      {err && (
        <div
          data-testid="aurem-rules-error"
          className="mt-3 text-xs text-red-300 bg-red-950/40 border border-red-900/50 rounded px-3 py-2"
        >
          {err}
        </div>
      )}

      {meta.updated_at && (
        <div className="mt-3 text-[10px] text-zinc-600 font-mono">
          last saved: {meta.updated_at}
        </div>
      )}
    </div>
  );
}
