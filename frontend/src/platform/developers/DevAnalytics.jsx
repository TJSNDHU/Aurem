/**
 * /developers/analytics — Pixel + token analytics (Auth-gated)
 */
import React, { useEffect, useState } from "react";
import { MousePointer2, TrendingUp, Coins } from "lucide-react";
import DeveloperShell, { devAuthHeaders, useDevMe } from "./DeveloperShell";
import { PageHeader, MetricTile, SectionTitle } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevAnalytics() {
  const { me } = useDevMe();
  const [tokenUsage, setTokenUsage] = useState([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/developers/me`, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (cancelled || !j) return;
        setTokenUsage([
          { day: "Mon", n: 0 }, { day: "Tue", n: 0 },
          { day: "Wed", n: 0 }, { day: "Thu", n: 0 },
          { day: "Fri", n: 0 }, { day: "Sat", n: 0 },
          { day: "Sun", n: Math.min(j.tokens_total_used || 0, 500) },
        ]);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const pixelConnected = !!me?.pixel_verified;
  const max = Math.max(...tokenUsage.map(d => d.n), 1);

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="ANALYTICS" title="What's working."
                  sub="Pixel data plus your token usage, in one place." />

      <div className="av2-grid-3-2">
        <MetricTile testid="analytics-visitors-metric" icon={MousePointer2}
                    label="Visitors (7d)"
                    value={pixelConnected ? "0" : "—"}
                    sub={pixelConnected ? "" : "Connect pixel"} />
        <MetricTile testid="analytics-lead-scores" icon={TrendingUp}
                    label="Lead score avg"
                    value={pixelConnected ? "—" : "—"} />
        <MetricTile testid="analytics-tokens-week" icon={Coins}
                    label="Tokens this week"
                    value={(me?.tokens_total_used ?? 0).toLocaleString()} />
      </div>

      {/* Token usage chart */}
      <div data-testid="analytics-token-usage-chart" className="av2-card">
        <SectionTitle title="Token usage (last 7 days)" />
        <div style={{ display: "flex", alignItems: "flex-end", gap: 16,
                       height: 120 }}>
          {tokenUsage.map((d, i) => {
            const h = (d.n / max) * 100;
            return (
              <div key={i}
                   style={{ flex: 1, display: "flex",
                             flexDirection: "column", alignItems: "center",
                             gap: 6 }}>
                <div className="av2-bar"
                     style={{
                       width: "100%",
                       height: `${h}%`,
                       minHeight: 2,
                       background: "linear-gradient(180deg, #FF8C35, #C9A84C)",
                       borderRadius: "3px 3px 0 0",
                     }} />
                <span style={{ fontSize: 10,
                                color: "var(--dash-text-muted)",
                                fontFamily: "'JetBrains Mono', monospace",
                                letterSpacing: "0.1em" }}>
                  {d.day}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Top pages */}
      <div data-testid="analytics-top-pages-table" className="av2-card">
        <SectionTitle title="Top pages" />
        {!pixelConnected ? (
          <p data-testid="analytics-pixel-empty"
              style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
            Connect your pixel domain at{" "}
            <span style={{ color: "var(--dash-orange)" }}>
              /developers/settings
            </span> to start collecting page data.
          </p>
        ) : (
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
            No traffic yet.
          </p>
        )}
      </div>
    </DeveloperShell>
  );
}
