/**
 * /developers/dashboard — iter 332b D-19
 *
 * Founder redesign:
 *   - The 4 stat cards (tokens / GitHub / sessions / lifetime) move into
 *     a compact pill row in the top-right of the page header.
 *   - The AUREM CTO chat panel becomes the dashboard. Full height,
 *     fills the viewport (minus the developer shell + page header).
 *   - Recent activity & purchases drop to a thin strip below the chat
 *     so they don't crowd the build surface.
 */
import React, { useState } from "react";
import SEO from "../../components/SEO";
import DeveloperShell from "./DeveloperShell";
import DevCtoChatPanel from "./DevCtoChatPanel";

export default function DevDashboard() {
  // Track live token deductions emitted by the chat stream — read by
  // the sidebar's token bar (D-43) via the `aurem-tokens-updated`
  // CustomEvent path. We just hold the latest value so re-renders
  // are coherent here.
  const [_liveTokens, setLiveTokens] = useState(null);

  return (
    <DeveloperShell requireAuth>
      <SEO
        title="Developer Dashboard"
        description="Your AUREM developer dashboard — chat with CTO, view tokens, GitHub, sessions and lifetime usage. Save projects + sidebar history."
        path="/developers/dashboard"
        noindex
        breadcrumbs={[
          { name: "Home", url: "/" },
          { name: "Developers", url: "/developers" },
          { name: "Dashboard", url: "/developers/dashboard" },
        ]}
      />
      {/* iter D-49 — top header bar (DASHBOARD eyebrow + welcome line +
          4 stat chips: tokens / GitHub / sessions / lifetime) removed.
          That information is already visible in the sidebar (GitHub
          status pill, Maxx toggle, token progress bar). The chat panel
          now claims the full remaining viewport. */}

      <DevCtoChatPanel onTokensUpdate={setLiveTokens} fullScreen />
    </DeveloperShell>
  );
}

// ─── Re-exports kept for backwards compat with other dev pages ────────
export function PageHeader({ eyebrow, title, sub }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.2em",
        textTransform: "uppercase",
        color: "var(--dash-orange)",
      }}>{eyebrow}</span>
      <h1 style={{
        fontFamily: "'Cinzel', serif",
        fontSize: 26, fontWeight: 600, letterSpacing: "0.01em",
        color: "var(--dash-text)", margin: "8px 0 6px",
      }}>{title}</h1>
      {sub && (
        <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
          {sub}
        </p>
      )}
    </div>
  );
}

export function MetricTile({ testid, icon: Icon, label, value, sub,
                              valueColor = "var(--dash-text)" }) {
  return (
    <div data-testid={testid} className="av2-card">
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--dash-text-muted)", marginBottom: 10,
      }}>
        <Icon size={11} /> {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em",
                     color: valueColor }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: "var(--dash-text-faint)",
                       marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

export function SectionTitle({ title, pill }) {
  return (
    <div style={{ display: "flex", alignItems: "center",
                   justifyContent: "space-between", marginBottom: 12 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600,
                    color: "var(--dash-text)" }}>{title}</h3>
      {pill && <span className="av2-pill av2-pill-live">{pill}</span>}
    </div>
  );
}
