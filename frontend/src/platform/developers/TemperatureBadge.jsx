/**
 * TemperatureBadge.jsx — iter D-57
 *
 * Tiny inline pill that shows the LLM temperature used on the LAST
 * assistant turn — sourced from the same intent classifier as the
 * backend (`_temperature_for_intent` in dev_cto_chat.py).
 *
 * Mapping:
 *   build / fix_code / diagnostic / refactor / code_review → 0.0
 *   strategic / planning / architecture / design           → 0.2
 *   everything else                                         → 0.1
 *
 * Props:
 *   • intent (string) — the intent label from the last turn metadata
 *
 * Render:
 *   ⚙ T 0.0 (deterministic) — green
 *   ⚙ T 0.1 (default)       — yellow
 *   ⚙ T 0.2 (creative)      — orange
 */
import React from "react";
import { Thermometer } from "lucide-react";

const CODE_INTENTS = new Set([
  "build", "fix_code", "diagnostic", "refactor", "code_review",
]);
const PLAN_INTENTS = new Set([
  "strategic", "planning", "architecture", "design",
]);

export function temperatureFor(intent) {
  if (!intent) return 0.1;
  const lc = String(intent).toLowerCase();
  if (CODE_INTENTS.has(lc)) return 0.0;
  if (PLAN_INTENTS.has(lc)) return 0.2;
  return 0.1;
}

function labelFor(temp) {
  if (temp === 0.0) return "deterministic";
  if (temp === 0.2) return "creative";
  return "default";
}

function tintFor(temp) {
  if (temp === 0.0) return "#4ade80";   // green
  if (temp === 0.2) return "#FF8C35";   // orange
  return "#FFC857";                      // yellow
}

export default function TemperatureBadge({ intent }) {
  const t    = temperatureFor(intent);
  const tint = tintFor(t);
  return (
    <span data-testid="cto-temperature-badge"
          title={`Intent: ${intent || "general"} → temperature ${t.toFixed(1)} (${labelFor(t)})`}
          style={{ display: "inline-flex", alignItems: "center",
                   gap: 4, fontSize: 10,
                   padding: "1px 6px", borderRadius: 999,
                   border: `1px solid ${tint}40`,
                   background: `${tint}10`,
                   color: tint,
                   fontFamily: "'JetBrains Mono', monospace" }}>
      <Thermometer size={9} />
      T {t.toFixed(1)}
    </span>
  );
}
