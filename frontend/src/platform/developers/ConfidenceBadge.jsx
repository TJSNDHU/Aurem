/**
 * ConfidenceBadge.jsx — iter D-53
 *
 * Small badge that shows the CTO's verified success rate on a given
 * task type, e.g. "Used 47× · 94% verified ✅". Renders nothing if no
 * learnings exist yet.
 *
 * Props:
 *   • taskType   (string) — e.g. "mobile_css_fix"
 *   • compact    (bool)   — render as inline pill vs full row
 *
 * Backend: GET /api/developers/cto/learning/confidence?task_type=…
 */
import React, { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";


export default function ConfidenceBadge({ taskType, compact = false }) {
  const [conf, setConf] = useState(null);

  useEffect(() => {
    if (!taskType) return undefined;
    let alive = true;
    fetch(`${API}/api/developers/cto/learning/confidence?` +
            `task_type=${encodeURIComponent(taskType)}`,
            { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (alive) setConf(j); })
      .catch(() => { /* silent — badge just won't render */ });
    return () => { alive = false; };
  }, [taskType]);

  if (!conf || !conf.n) return null;

  const rate    = Math.round((conf.success_rate || 0) * 100);
  const trusted = rate >= 80;
  const tint    = trusted ? "#4ade80" : "#FFC857";

  if (compact) {
    return (
      <span data-testid={`cto-confidence-${taskType}`}
            title={`Best approach: ${conf.best_approach || "—"}`}
            style={{ display: "inline-flex", alignItems: "center",
                     gap: 4, fontSize: 11,
                     padding: "2px 8px", borderRadius: 999,
                     border: `1px solid ${tint}40`,
                     background: `${tint}10`,
                     color: tint,
                     fontFamily: "'JetBrains Mono', monospace" }}>
        <ShieldCheck size={11} />
        {conf.n}× · {rate}%
      </span>
    );
  }

  return (
    <div data-testid={`cto-confidence-${taskType}`}
         style={{ display: "flex", alignItems: "center",
                  gap: 8, padding: "6px 10px",
                  background: `${tint}10`,
                  border: `1px solid ${tint}40`,
                  borderRadius: 4, fontSize: 12, color: tint,
                  fontFamily: "'JetBrains Mono', monospace" }}>
      <ShieldCheck size={13} />
      <span>
        AUREM CTO has shipped this {conf.n} time{conf.n === 1 ? "" : "s"}.
      </span>
      <strong style={{ marginLeft: "auto" }}>{rate}% verified</strong>
    </div>
  );
}
