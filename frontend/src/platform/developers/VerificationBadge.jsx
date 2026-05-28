/**
 * VerificationBadge.jsx — iter D-52
 *
 * Three-layer auto-verification panel that mounts at the top of the
 * CTO chat. Each layer (code / GitHub push / deploy) is one of:
 *
 *    ⏳ "checking…"   (yellow)
 *    ✅ "verified"    (green)
 *    ❌ "failed"      (red)
 *
 * The badge is system-driven. Callers push fact-rows in via
 * `pushVerifyEvent()` (a module-level event bus) so the chat panel
 * doesn't need to thread props through five layers.
 *
 * Public surface (named exports):
 *   • <VerificationBadge />          — the UI component
 *   • pushVerifyEvent(kind, payload) — let any code update a row
 *
 * Allowed kinds: "code" | "github" | "deploy"
 * Allowed payload.status: "checking" | "green" | "red"
 */
import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, Loader2, ExternalLink } from "lucide-react";

const EVENT = "aurem-verify-event";

export function pushVerifyEvent(kind, payload) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENT, {
    detail: { kind, payload: payload || {} },
  }));
}

const DEFAULTS = {
  code:   { status: "idle", label: "Code",   detail: "" },
  github: { status: "idle", label: "GitHub", detail: "" },
  deploy: { status: "idle", label: "Deploy", detail: "" },
};

const ICON = {
  checking: <Loader2  size={13} className="aurem-anim-spin"
                       style={{ color: "#FFC857" }} />,
  green:    <CheckCircle2 size={13} style={{ color: "#4ade80" }} />,
  red:      <AlertCircle  size={13} style={{ color: "#FF6060" }} />,
  idle:     <span style={{ width: 13, height: 13, borderRadius: 999,
                            background: "rgba(255,255,255,0.10)",
                            display: "inline-block" }} />,
};

const COLOR = {
  checking: "#FFC857",
  green:    "#4ade80",
  red:      "#FF6060",
  idle:     "var(--dash-text-muted)",
};

export default function VerificationBadge() {
  const [rows, setRows] = useState(DEFAULTS);

  useEffect(() => {
    const onEvt = (e) => {
      const { kind, payload } = e.detail || {};
      if (!kind || !DEFAULTS[kind]) return;
      setRows((cur) => ({
        ...cur,
        [kind]: {
          ...cur[kind],
          status: payload.status || cur[kind].status,
          detail: payload.detail || "",
          url:    payload.url    || "",
        },
      }));
    };
    window.addEventListener(EVENT, onEvt);
    return () => window.removeEventListener(EVENT, onEvt);
  }, []);

  // Hide entirely until at least one row has moved off idle.
  const anyActive = Object.values(rows).some((r) => r.status !== "idle");
  if (!anyActive) return null;

  return (
    <div data-testid="cto-verify-badge"
         style={{
           display: "flex", flexDirection: "column", gap: 2,
           padding: "8px 12px",
           borderBottom: "1px solid var(--dash-divider)",
           background: "rgba(0,0,0,0.18)",
         }}>
      <div style={{ fontSize: 10, letterSpacing: "0.18em",
                     textTransform: "uppercase",
                     color: "var(--dash-text-muted)",
                     marginBottom: 2,
                     fontFamily: "'JetBrains Mono', monospace" }}>
        Last action status
      </div>
      {Object.entries(rows).map(([kind, r]) => (
        <div key={kind}
             data-testid={`cto-verify-row-${kind}`}
             style={{ display: "flex", alignItems: "center", gap: 8,
                      fontSize: 12, color: COLOR[r.status],
                      fontFamily: "'JetBrains Mono', monospace" }}>
          {ICON[r.status]}
          <span style={{ minWidth: 56,
                          color: "var(--dash-text-muted)" }}>
            {r.label}
          </span>
          <span data-testid={`cto-verify-${kind}-status`}>
            {r.status === "idle"     ? "—"           :
             r.status === "checking" ? "checking…"   :
             r.status === "green"    ? "verified"    :
             r.status === "red"      ? "failed"      : r.status}
          </span>
          {r.detail && (
            <span style={{ color: "var(--dash-text-muted)",
                            fontSize: 11 }}>
              · {r.detail}
            </span>
          )}
          {r.url && (
            <a href={r.url} target="_blank" rel="noreferrer"
                style={{ marginLeft: "auto",
                         color: COLOR[r.status],
                         display: "inline-flex", alignItems: "center",
                         gap: 3, fontSize: 11, textDecoration: "none" }}>
              view <ExternalLink size={10} />
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Helper: returns true iff all three rows are green. Components can
 * gate the Deploy button on this.
 */
export function allVerifyGreen(rows) {
  if (!rows) return false;
  return rows.code?.status   === "green" &&
         rows.github?.status === "green" &&
         rows.deploy?.status === "green";
}
