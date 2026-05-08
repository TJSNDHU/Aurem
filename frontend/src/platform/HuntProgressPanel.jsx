/**
 * HuntProgressPanel — memoized stage timeline + animated progress bar.
 *
 * Subscribes to the shared SSE feed via props (does NOT open its own connection).
 * Parent passes `progressEvents` — an array of events with agent/step/status/message.
 * Pure presentational + internal derive — wrapped in React.memo so flooding SSE
 * events re-render ONLY this panel, not the whole ORA Command Console.
 */

import React, { useMemo } from "react";

const G = "#C9A227";

const STAGES = [
  { key: "scout",   label: "Scout",   hint: "Google Places lookup" },
  { key: "verify",  label: "Verify",  hint: "Phone / email / website check" },
  { key: "website", label: "Website", hint: "Auto-generate business site" },
  { key: "blast",   label: "Blast",   hint: "SMS / Email / WhatsApp outreach" },
];

const STATUS_COLORS = {
  started: "#C9A227",
  ok:      "#7EC8A0",
  fail:    "#d44",
  skipped: "#888",
};

const STATUS_ICONS = {
  started: "🔄",
  ok:      "✅",
  fail:    "❌",
  skipped: "⚠️",
};

function deriveStages(events) {
  // Only keep events that look like hunt_progress (have `step` + `status`)
  const progress = events.filter((e) => e && e.step && e.status);
  // Latest status per stage
  const map = {};
  progress.forEach((e) => { map[e.step] = e; });
  // Summary — count ok / fail / skipped
  const summary = { ok: 0, fail: 0, skipped: 0, total: progress.length };
  progress.forEach((e) => { if (summary[e.status] != null) summary[e.status]++; });
  // Compute pct — stages completed (ok+fail+skipped count each as "done")
  const done = STAGES.filter((s) => map[s.key] && map[s.key].status !== "started").length;
  const pct = Math.round((done / STAGES.length) * 100);
  const isActive = progress.length > 0 && progress.some((e) => e.status === "started");
  const latestMessage = progress.length ? progress[progress.length - 1].message : "";
  return { map, summary, pct, isActive, latestMessage };
}

function HuntProgressPanel({ progressEvents, active }) {
  const { map, summary, pct, isActive, latestMessage } = useMemo(
    () => deriveStages(progressEvents || []),
    [progressEvents]
  );

  const showEmpty = !progressEvents?.length && !active;

  return (
    <div
      data-testid="hunt-progress-panel"
      style={{
        padding: "13px 17px",
        borderBottom: "1px solid #1c1c1c",
        background: (isActive || active) ? "#0e0f10" : "#0c0c0d",
        transition: "background .25s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9 }}>
        <span style={{ fontSize: 9.5, color: G, letterSpacing: ".14em", textTransform: "uppercase", fontWeight: 700 }}>
          ◆ Hunt Progress
        </span>
        <span style={{ fontSize: 10, color: "#555", letterSpacing: ".06em" }}>
          {showEmpty ? "Idle — run a hunt to see the live pipeline" : `${pct}% · ${summary.ok} ok · ${summary.fail} fail · ${summary.skipped} skip`}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: "#151515", borderRadius: 2, overflow: "hidden", marginBottom: 11 }}>
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: pct === 100 ? "#7EC8A0" : G,
            transition: "width .3s ease",
            boxShadow: isActive ? `0 0 6px ${G}80` : "none",
          }}
        />
      </div>

      {/* Stage timeline */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 7 }}>
        {STAGES.map((stage) => {
          const e = map[stage.key];
          const status = e?.status || "idle";
          const color = STATUS_COLORS[status] || "#333";
          const icon = STATUS_ICONS[status] || "◦";
          return (
            <div
              key={stage.key}
              data-testid={`hunt-stage-${stage.key}`}
              title={e?.message || stage.hint}
              style={{
                padding: "8px 10px",
                borderRadius: 4,
                border: `1px solid ${color}28`,
                background: e ? `${color}08` : "#0e0e10",
                opacity: e ? 1 : 0.45,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: e ? "#e4ddd3" : "#444" }}>
                  {stage.label}
                </span>
                <span style={{ fontSize: 11, lineHeight: 1 }}>
                  {e ? icon : "◦"}
                </span>
              </div>
              <div style={{ fontSize: 9, color: "#555", letterSpacing: ".05em", textTransform: "uppercase" }}>
                {e ? status : "waiting"}
              </div>
            </div>
          );
        })}
      </div>

      {/* Latest message */}
      {latestMessage && (
        <div style={{ marginTop: 9, fontSize: 10.5, color: "#888", fontStyle: "italic" }}>
          ↳ {latestMessage}
        </div>
      )}
    </div>
  );
}

// Memo: re-render only when the events array reference or `active` prop changes.
export default React.memo(HuntProgressPanel, (prev, next) => {
  return prev.active === next.active
      && prev.progressEvents === next.progressEvents;
});
