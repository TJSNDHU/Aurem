/**
 * OraChatViews.jsx — Rich tool-result renderers for OraChat (iter 326uu).
 *
 * Closes 10 UX gaps the founder flagged vs Emergent E1 chat:
 *   1. Approval→error opacity              → ErrorContext
 *   2. No live preview pane                → PreviewPane
 *   3. No inline file diffs                → DiffView
 *   4. Test results buried                 → TestResultBlock
 *   5. Errors with no context              → ErrorContext + retry hint
 *   6. No step tracker                     → StepTracker
 *   7. Approval card state confusion       → handled in OraChat.decide() (iter 326rr)
 *   8. No upfront plan preview             → PlanPreview
 *   9. Tool output silently truncated      → ExpandableOutput
 *  10. No clickable file links             → FileLink
 *
 * One file, one responsibility per component. Every component carries
 * a data-testid for E2E selection.
 */
import React, { useState, useMemo } from "react";
import {
  Check, X, ChevronRight, FileText, ExternalLink,
  AlertTriangle, RefreshCw, Wand2,
} from "lucide-react";

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GREEN = "#67E8A0";
const RED = "#FF7676";
const AMBER = "#FFB36B";
const BLUE = "#6FB8FF";

const BG_LIGHT = "rgba(255,255,255,0.04)";
const BG_DARK = "rgba(0,0,0,0.4)";
const MONO = "ui-monospace, SF Mono, Menlo, monospace";

/* ─────────────────────────────────────────────────────────────
 * classifyResult — decides how to render a tool result.
 * Pure function, no React state, easy to test.
 * ─────────────────────────────────────────────────────────── */
export function classifyResult(toolName, result) {
  if (!result || typeof result !== "object") return "generic";
  const r = result;
  if (!r.ok && r.error) return "error";

  const name = (toolName || "").toLowerCase();
  if (name.includes("safe_edit") || name === "append_to_file") {
    // safe_edit_with_council includes a find/replace echo + council verdict.
    if (r.find_string || r.replace_string || r.preview_diff) return "diff";
    return "edit_summary";
  }
  if (name.includes("view_file") || name === "view_bulk") return "file_content";
  if (name.includes("lint_")) return "lint";
  if (name.startsWith("shell_exec") || name === "ora_run_natural") {
    const stdout = r.stdout || "";
    if (/\b\d+\s+passed\b/i.test(stdout) || /\bcollected \d+ items\b/i.test(stdout)) {
      return "test_output";
    }
    return "shell_output";
  }
  if (name === "council_consult" || name === "peer_review") return "council";
  return "generic";
}

/* ─────────────────────────────────────────────────────────────
 * SmartToolResult — dispatcher
 * ─────────────────────────────────────────────────────────── */
export function SmartToolResult({ tool, result }) {
  const kind = useMemo(() => classifyResult(tool, result), [tool, result]);
  const r = result || {};

  return (
    <div data-testid={`smart-tool-result-${kind}`}
         style={{ margin: "6px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                       fontSize: 11, color: TEXT_DIM, marginBottom: 4 }}>
        <Wand2 size={12} color={r.ok ? GREEN : RED} />
        <span style={{ fontFamily: MONO, color: r.ok ? GREEN : RED }}>
          {tool}
        </span>
        {r.elapsed_ms != null && (
          <span style={{ color: TEXT_DIM, opacity: 0.7 }}>
            · {r.elapsed_ms}ms
          </span>
        )}
      </div>

      {kind === "diff" && <DiffView tool={tool} result={r} />}
      {kind === "test_output" && <TestResultBlock result={r} />}
      {kind === "shell_output" && <ShellOutputBlock result={r} />}
      {kind === "file_content" && <FileContentBlock tool={tool} result={r} />}
      {kind === "lint" && <LintBlock result={r} />}
      {kind === "council" && <CouncilBlock result={r} />}
      {kind === "error" && <ErrorContext tool={tool} result={r} />}
      {kind === "edit_summary" && <EditSummary result={r} />}
      {kind === "generic" && <GenericJsonBlock result={r} />}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * DiffView — green/red line-by-line for safe_edit results
 * ─────────────────────────────────────────────────────────── */
export function DiffView({ tool, result }) {
  const find = result.find_string || "";
  const repl = result.replace_string || "";
  const path = result.path || result.file_path || "(unknown file)";
  const lines = useMemo(() => buildDiffLines(find, repl), [find, repl]);

  return (
    <div data-testid="diff-view"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK, overflow: "hidden" }}>
      <div style={{ padding: "6px 10px", background: BG_LIGHT,
                       borderBottom: `1px solid ${BORDER}`,
                       display: "flex", alignItems: "center", gap: 8,
                       fontSize: 11, fontFamily: MONO, color: TEXT_DIM }}>
        <FileText size={11} />
        <FileLink path={path} />
        {result.occurrences && (
          <span style={{ marginLeft: "auto", color: GREEN }}>
            ✓ {result.occurrences} replacement{result.occurrences > 1 ? "s" : ""}
          </span>
        )}
      </div>
      <pre style={{ margin: 0, padding: 8, fontFamily: MONO, fontSize: 11,
                       lineHeight: 1.5, color: TEXT, maxHeight: 300,
                       overflow: "auto" }}>
        {lines.map((ln, i) => (
          <div key={i} data-testid={`diff-line-${ln.kind}`}
               style={{
                 background: ln.kind === "del" ? "rgba(255,118,118,0.10)" :
                             ln.kind === "add" ? "rgba(103,232,160,0.10)" : "transparent",
                 color: ln.kind === "del" ? RED :
                        ln.kind === "add" ? GREEN : TEXT,
                 padding: "0 6px",
                 whiteSpace: "pre-wrap",
                 wordBreak: "break-word",
               }}>
            <span style={{ opacity: 0.5, marginRight: 6 }}>
              {ln.kind === "del" ? "-" : ln.kind === "add" ? "+" : " "}
            </span>
            {ln.text || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}

// Pure helper — exposed for testing.
export function buildDiffLines(find, replace) {
  const a = String(find ?? "").split("\n");
  const b = String(replace ?? "").split("\n");
  const out = [];
  // For now, naive line-by-line: each `find` line as "del", each `replace` as "add".
  // Future: real LCS diff. For 326uu's goal (visibility), this is enough.
  for (const ln of a) out.push({ kind: "del", text: ln });
  for (const ln of b) out.push({ kind: "add", text: ln });
  return out;
}

/* ─────────────────────────────────────────────────────────────
 * TestResultBlock — parses pytest output
 * ─────────────────────────────────────────────────────────── */
export function TestResultBlock({ result }) {
  const stdout = result.stdout || "";
  const stderr = result.stderr || "";
  const all = stdout + "\n" + stderr;
  const summary = parsePytestSummary(all);

  return (
    <div data-testid="test-result-block"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK, overflow: "hidden" }}>
      <div data-testid="test-result-header"
           style={{ padding: "8px 12px", background: BG_LIGHT,
                       display: "flex", alignItems: "center", gap: 10 }}>
        {summary.passed > 0 && summary.failed === 0 ? (
          <Check size={14} color={GREEN} />
        ) : summary.failed > 0 ? (
          <X size={14} color={RED} />
        ) : (
          <ChevronRight size={14} color={TEXT_DIM} />
        )}
        <span style={{ fontSize: 13, fontWeight: 600,
                          color: summary.failed === 0 && summary.passed > 0 ? GREEN :
                                 summary.failed > 0 ? RED : TEXT }}>
          {summary.headerLabel}
        </span>
        {summary.elapsed && (
          <span style={{ color: TEXT_DIM, fontSize: 11 }}>
            in {summary.elapsed}
          </span>
        )}
      </div>
      <ExpandableOutput
        text={all}
        previewLines={summary.failed > 0 ? 12 : 4}
        testid="test-output-body"
      />
    </div>
  );
}

export function parsePytestSummary(text) {
  const out = { passed: 0, failed: 0, skipped: 0, errors: 0,
                elapsed: "", headerLabel: "(no pytest output)" };
  if (!text) return out;
  // "X passed, Y failed, Z skipped in 4.56s"
  const finalLine = (text.match(/=+\s*(\d+\s+(?:passed|failed)[^=]*?)\s*=+/gi) || []).pop();
  if (finalLine) {
    const pa = finalLine.match(/(\d+)\s+passed/);  if (pa) out.passed = parseInt(pa[1], 10);
    const fa = finalLine.match(/(\d+)\s+failed/);  if (fa) out.failed = parseInt(fa[1], 10);
    const sk = finalLine.match(/(\d+)\s+skipped/); if (sk) out.skipped = parseInt(sk[1], 10);
    const er = finalLine.match(/(\d+)\s+error/);   if (er) out.errors = parseInt(er[1], 10);
    const tm = finalLine.match(/in\s+([\d.]+\s*s)/); if (tm) out.elapsed = tm[1];
  }
  const parts = [];
  if (out.passed)  parts.push(`✓ ${out.passed} passing`);
  if (out.failed)  parts.push(`✗ ${out.failed} failing`);
  if (out.errors)  parts.push(`! ${out.errors} errors`);
  if (out.skipped) parts.push(`↷ ${out.skipped} skipped`);
  out.headerLabel = parts.length ? parts.join(" · ") : "Test output";
  return out;
}

/* ─────────────────────────────────────────────────────────────
 * ShellOutputBlock — generic stdout/stderr collapsible
 * ─────────────────────────────────────────────────────────── */
export function ShellOutputBlock({ result }) {
  const stdout = result.stdout || "";
  const stderr = result.stderr || "";
  const exit = result.exit_code != null ? result.exit_code :
               result.returncode != null ? result.returncode : null;
  return (
    <div data-testid="shell-output-block"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK }}>
      <div style={{ padding: "6px 12px", background: BG_LIGHT,
                       display: "flex", gap: 12, fontSize: 11,
                       color: exit === 0 ? GREEN : exit != null ? RED : TEXT_DIM }}>
        <span>shell</span>
        {exit != null && <span>exit {exit}</span>}
        {result.elapsed_ms && <span style={{ marginLeft: "auto", color: TEXT_DIM }}>
          {result.elapsed_ms}ms
        </span>}
      </div>
      {stdout && <ExpandableOutput text={stdout} previewLines={6}
                                     testid="shell-stdout" label="stdout" />}
      {stderr && <ExpandableOutput text={stderr} previewLines={4}
                                     testid="shell-stderr" label="stderr"
                                     accent={RED} />}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * FileContentBlock — for view_file / view_bulk
 * ─────────────────────────────────────────────────────────── */
export function FileContentBlock({ tool, result }) {
  const path = result.path || result.file_path || "";
  const content = result.content || result.text || "";
  const lines = result.lines || (content ? content.split("\n").length : 0);
  return (
    <div data-testid="file-content-block"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK }}>
      <div style={{ padding: "6px 12px", background: BG_LIGHT,
                       display: "flex", alignItems: "center", gap: 8,
                       fontSize: 11, fontFamily: MONO, color: TEXT_DIM }}>
        <FileText size={11} />
        <FileLink path={path} />
        {lines > 0 && <span style={{ marginLeft: "auto" }}>{lines} lines</span>}
      </div>
      <ExpandableOutput text={content} previewLines={8}
                          testid="file-content-body" />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * LintBlock — show lint findings clearly
 * ─────────────────────────────────────────────────────────── */
export function LintBlock({ result }) {
  const issues = result.issues || result.findings || [];
  const clean = result.ok && issues.length === 0;
  return (
    <div data-testid="lint-block"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK, padding: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                       fontSize: 12, color: clean ? GREEN : AMBER, marginBottom: 6 }}>
        {clean ? <Check size={12} /> : <AlertTriangle size={12} />}
        <span>{clean ? "Lint clean" : `${issues.length} lint issue${issues.length > 1 ? "s" : ""}`}</span>
      </div>
      {issues.length > 0 && (
        <ul style={{ margin: 0, padding: "0 0 0 20px", fontSize: 11,
                       fontFamily: MONO, color: TEXT, lineHeight: 1.6 }}>
          {issues.slice(0, 12).map((it, i) => (
            <li key={i}>
              {typeof it === "string" ? it
                : `${it.line || "?"}: ${it.rule || it.code || ""} — ${it.message || it.text || ""}`}
            </li>
          ))}
          {issues.length > 12 && (
            <li style={{ color: TEXT_DIM }}>… +{issues.length - 12} more</li>
          )}
        </ul>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * CouncilBlock — show each peer's verdict
 * ─────────────────────────────────────────────────────────── */
export function CouncilBlock({ result }) {
  const opinions = result.opinions || [];
  return (
    <div data-testid="council-block"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK, padding: 8 }}>
      <div style={{ fontSize: 11, color: TEXT_DIM, marginBottom: 6 }}>
        Council · {result.consensus || `${opinions.length} peers`}
      </div>
      {opinions.map((o, i) => (
        <details key={i} style={{ marginBottom: 6 }}>
          <summary style={{ cursor: "pointer", fontSize: 12, color: TEXT,
                              display: "inline-flex", alignItems: "center",
                              gap: 6 }}>
            <span style={{ color: o.ok ? GREEN : RED, fontFamily: MONO,
                              fontSize: 10 }}>
              {o.ok ? "●" : "○"}
            </span>
            <strong>{o.role}</strong>
            {o.provider && <span style={{ color: TEXT_DIM, fontSize: 10 }}>
              via {o.provider}
            </span>}
          </summary>
          <pre style={{ margin: "6px 0 0", padding: 8, background: BG_DARK,
                          borderRadius: 4, fontSize: 11, lineHeight: 1.5,
                          whiteSpace: "pre-wrap", color: TEXT,
                          maxHeight: 240, overflow: "auto" }}>
            {o.opinion || "(no opinion)"}
          </pre>
        </details>
      ))}
      {result.invalid_roles_ignored && (
        <div style={{ marginTop: 6, fontSize: 11, color: AMBER }}>
          ⓘ Ignored invalid roles: {result.invalid_roles_ignored.join(", ")}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * ErrorContext — error + likely cause + suggested action
 * ─────────────────────────────────────────────────────────── */
export function ErrorContext({ tool, result, onRetry }) {
  const errMsg = String(result?.error || result?.detail || "Unknown error");
  const hint = inferErrorHint(errMsg, tool);
  return (
    <div data-testid="error-context"
         style={{ border: `1px solid ${RED}55`, borderRadius: 8,
                    background: "rgba(255,118,118,0.08)", padding: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                       color: RED, fontSize: 12, fontWeight: 600,
                       marginBottom: 4 }}>
        <AlertTriangle size={12} /> Tool failed: {tool}
      </div>
      <pre style={{ margin: "4px 0", fontFamily: MONO, fontSize: 11,
                      color: TEXT, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
        {errMsg.slice(0, 600)}
      </pre>
      {hint && (
        <div data-testid="error-hint"
             style={{ marginTop: 6, fontSize: 11, color: AMBER,
                        background: "rgba(255,179,107,0.10)", padding: 8,
                        borderRadius: 6 }}>
          <strong>Likely cause:</strong> {hint.cause}<br />
          <strong>Try:</strong> {hint.fix}
        </div>
      )}
      {onRetry && (
        <button onClick={onRetry} data-testid="error-retry-btn"
                style={{ marginTop: 8, padding: "4px 10px", fontSize: 11,
                          background: "transparent", border: `1px solid ${AMBER}`,
                          color: AMBER, borderRadius: 6, cursor: "pointer" }}>
          <RefreshCw size={10} /> Ask ORA to retry
        </button>
      )}
    </div>
  );
}

// Pure — exposed for testing.
export function inferErrorHint(errMsg, tool) {
  const m = String(errMsg).toLowerCase();
  if (m.includes("not found, already processed, or expired"))
    return { cause: "Approval card expired (60-min window) or was already approved/rejected elsewhere.",
             fix:   "Ask ORA again — she'll propose a fresh action." };
  if (m.includes("path not allowed"))
    return { cause: "ORA tried to touch a path outside /app/{backend,frontend/src,memory,ora_skills,scripts}.",
             fix:   "Use a path inside the allowed roots, or run via legion_exec." };
  if (m.includes("bad args for"))
    return { cause: "ORA passed the wrong argument shape for this tool.",
             fix:   "She'll see args_spec in the recovery directive and self-correct next turn." };
  if (m.includes("unknown tool"))
    return { cause: "ORA hallucinated a tool name that doesn't exist in the registry.",
             fix:   "Available tools are now surfaced — she'll pick a real one next turn." };
  if (m.includes("no valid roles after filter"))
    return { cause: "ORA called council with role slugs not in the whitelist.",
             fix:   "Council now falls back to the safe trio (security/backend/qa) — should not recur." };
  if (m.includes("timeout") || m.includes("timed out"))
    return { cause: "Upstream call took too long (LLM, Mongo, or external HTTP).",
             fix:   "Transient — retry on next iteration (counts toward 5-strike transient cap, not 2-strike fail cap)." };
  if (m.includes("http 5"))
    return { cause: "Upstream service returned a 5xx — environment issue, not code.",
             fix:   "Transient — ORA will retry automatically (transient bucket)." };
  if (m.includes("rate limit") || m.includes("429"))
    return { cause: "Upstream provider throttled the call.",
             fix:   "Wait 30-60s, then ORA will retry." };
  if (m.includes("dissent") || m.includes("rejected by"))
    return { cause: "A peer in the council blocked this edit (security/QA concern).",
             fix:   "Read each peer opinion in the council panel; override only with a documented reason." };
  if (m.includes("creds_missing") || m.includes("api_key"))
    return { cause: "API key for an upstream service is missing from the env.",
             fix:   "Set the relevant env var in /app/backend/.env and restart the backend." };
  return null;
}

/* ─────────────────────────────────────────────────────────────
 * EditSummary — for safe_edit without find/replace echo
 * ─────────────────────────────────────────────────────────── */
export function EditSummary({ result }) {
  return (
    <div data-testid="edit-summary"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK, padding: 8, fontSize: 12 }}>
      <FileLink path={result.path || result.file_path} />
      {result.bytes_written != null && (
        <span style={{ marginLeft: 8, color: TEXT_DIM, fontSize: 11 }}>
          {result.bytes_written} bytes
        </span>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * GenericJsonBlock — fallback, collapsed by default
 * ─────────────────────────────────────────────────────────── */
export function GenericJsonBlock({ result }) {
  const [open, setOpen] = useState(false);
  const json = useMemo(() => JSON.stringify(result, null, 2), [result]);
  const preview = json.slice(0, 200);
  return (
    <div data-testid="generic-json-block"
         style={{ border: `1px solid ${BORDER}`, borderRadius: 8,
                    background: BG_DARK, padding: 8 }}>
      <div onClick={() => setOpen((v) => !v)}
            data-testid="generic-json-toggle"
            style={{ cursor: "pointer", display: "flex", alignItems: "center",
                       gap: 6, fontSize: 11, color: TEXT_DIM }}>
        <ChevronRight size={11}
                        style={{ transform: open ? "rotate(90deg)" : "none",
                                  transition: "transform 0.15s" }} />
        <span>{open ? "Hide" : "Show"} raw result · {json.length} chars</span>
      </div>
      <pre style={{ margin: "6px 0 0", padding: 6, fontFamily: MONO,
                      fontSize: 10.5, lineHeight: 1.5, color: TEXT,
                      maxHeight: open ? 360 : 36, overflow: "auto",
                      whiteSpace: "pre-wrap", wordBreak: "break-word",
                      transition: "max-height 0.2s" }}>
        {open ? json : preview + (json.length > 200 ? "…" : "")}
      </pre>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * ExpandableOutput — long stdout/file content with show more
 * ─────────────────────────────────────────────────────────── */
export function ExpandableOutput({ text, previewLines = 6, testid, label, accent }) {
  const [open, setOpen] = useState(false);
  const all = String(text || "");
  const lines = all.split("\n");
  const truncated = lines.length > previewLines;
  const shown = open ? all : lines.slice(0, previewLines).join("\n");
  const color = accent || TEXT;
  return (
    <div data-testid={testid || "expandable-output"} style={{ position: "relative" }}>
      {label && (
        <div style={{ padding: "4px 12px", fontSize: 10, color: TEXT_DIM,
                         fontFamily: MONO, opacity: 0.7 }}>
          {label}
        </div>
      )}
      <pre style={{ margin: 0, padding: "6px 12px", fontFamily: MONO,
                      fontSize: 11, lineHeight: 1.5, color,
                      whiteSpace: "pre-wrap", wordBreak: "break-word",
                      maxHeight: open ? "60vh" : `${previewLines * 1.6 + 1}em`,
                      overflow: "auto" }}>
        {shown}
      </pre>
      {truncated && (
        <button onClick={() => setOpen((v) => !v)}
                data-testid="expand-toggle"
                style={{ margin: "4px 12px 8px", padding: "2px 8px",
                          fontSize: 10, fontFamily: MONO,
                          background: "transparent", color: BLUE,
                          border: `1px solid ${BLUE}44`,
                          borderRadius: 4, cursor: "pointer" }}>
          {open ? "Show less" : `Show all ${lines.length} lines`}
        </button>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * StepTracker — "Step 2 of 6 · running pytest"
 * ─────────────────────────────────────────────────────────── */
export function StepTracker({ steps, current, label }) {
  if (!Array.isArray(steps) || steps.length === 0) return null;
  const n = current != null ? Math.min(current, steps.length) : steps.length;
  return (
    <div data-testid="step-tracker"
         style={{ display: "flex", flexDirection: "column", gap: 4,
                    margin: "4px 0", padding: 8,
                    background: "rgba(212,175,55,0.05)",
                    border: `1px dashed ${BORDER}`, borderRadius: 8 }}>
      <div style={{ fontSize: 11, color: TEXT_DIM, marginBottom: 4 }}>
        <strong style={{ color: GOLD }}>Step {n} of {steps.length}</strong>
        {label && <span> · {label}</span>}
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {steps.map((_, i) => (
          <div key={i} data-testid={`step-bar-${i}`}
               style={{ flex: 1, height: 4, borderRadius: 2,
                          background: i < n - 1 ? GREEN
                                       : i === n - 1 ? GOLD
                                       : `${TEXT_DIM}33` }} />
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * PlanPreview — checklist parsed from ORA's plan
 * ─────────────────────────────────────────────────────────── */
export function PlanPreview({ steps, completed = [] }) {
  if (!Array.isArray(steps) || steps.length === 0) return null;
  const done = new Set(completed);
  return (
    <div data-testid="plan-preview"
         style={{ margin: "4px 0", padding: 10,
                    background: "rgba(111,184,255,0.06)",
                    border: `1px solid ${BLUE}33`, borderRadius: 8 }}>
      <div style={{ fontSize: 11, color: BLUE, fontWeight: 600,
                       marginBottom: 6, letterSpacing: 0.3 }}>
        PLAN
      </div>
      {steps.map((s, i) => {
        const isDone = done.has(i) || done.has(s);
        return (
          <div key={i} data-testid={`plan-step-${i}`}
               style={{ display: "flex", alignItems: "flex-start", gap: 8,
                          fontSize: 12.5, lineHeight: 1.5, color: TEXT,
                          padding: "2px 0",
                          opacity: isDone ? 0.6 : 1,
                          textDecoration: isDone ? "line-through" : "none" }}>
            <span style={{ color: isDone ? GREEN : TEXT_DIM,
                              fontFamily: MONO, fontSize: 12,
                              minWidth: 18 }}>
              {isDone ? "✓" : `${i + 1}.`}
            </span>
            <span>{s}</span>
          </div>
        );
      })}
    </div>
  );
}

// Pure — exposed for testing
export function extractPlanSteps(text) {
  if (!text || typeof text !== "string") return [];
  // Match patterns like "1. foo", "2) bar", "- baz", "* qux"
  const lines = text.split("\n");
  const out = [];
  for (const ln of lines) {
    const m = ln.match(/^\s*(?:\d+[.)]|[-*•])\s+(.+)$/);
    if (m && m[1].trim().length > 3) out.push(m[1].trim());
  }
  // Only treat it as a plan if we found at least 2 steps.
  return out.length >= 2 ? out : [];
}

/* ─────────────────────────────────────────────────────────────
 * FileLink — clickable, fires onClick callback (router or modal)
 * ─────────────────────────────────────────────────────────── */
export function FileLink({ path, onClick }) {
  if (!path) return <span style={{ color: TEXT_DIM }}>(no path)</span>;
  return (
    <a href="#"
       data-testid="file-link"
       onClick={(e) => {
         e.preventDefault();
         if (onClick) onClick(path);
         else if (typeof window !== "undefined") {
           // Default: copy to clipboard so founder can paste anywhere
           try { window.navigator.clipboard.writeText(path); } catch (_) { /* noop */ }
         }
       }}
       style={{ color: BLUE, textDecoration: "none",
                  fontFamily: MONO, fontSize: 11,
                  display: "inline-flex", alignItems: "center", gap: 4 }}>
      {path}
      <ExternalLink size={10} />
    </a>
  );
}

/* ─────────────────────────────────────────────────────────────
 * PreviewPane — right-side mini panel mirroring latest result
 * ─────────────────────────────────────────────────────────── */
export function PreviewPane({ latestResult, latestTool }) {
  if (!latestResult) {
    return (
      <div data-testid="preview-pane-empty"
           style={{ ...paneStyle(),
                      display: "flex", alignItems: "center",
                      justifyContent: "center", color: TEXT_DIM,
                      fontSize: 12, textAlign: "center", padding: 24 }}>
        <div>
          <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.4 }}>◇</div>
          <div>ORA's latest output will appear here.</div>
        </div>
      </div>
    );
  }
  return (
    <div data-testid="preview-pane" style={paneStyle()}>
      <div style={{ padding: "8px 12px", fontSize: 11, color: TEXT_DIM,
                       borderBottom: `1px solid ${BORDER}`,
                       background: BG_LIGHT }}>
        Last result · <span style={{ color: GOLD, fontFamily: MONO }}>
          {latestTool}
        </span>
      </div>
      <div style={{ padding: 10, flex: 1, overflow: "auto" }}>
        <SmartToolResult tool={latestTool} result={latestResult} />
      </div>
    </div>
  );
}

function paneStyle() {
  return {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    background: "linear-gradient(160deg, rgba(22,22,32,0.5), rgba(10,10,18,0.7))",
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    overflow: "hidden",
  };
}

export default SmartToolResult;
