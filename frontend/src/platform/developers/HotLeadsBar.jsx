/**
 * HotLeadsBar.jsx — iter D-57
 *
 * Auto-refreshing strip above the chat that surfaces leads who opened
 * (or clicked) our last email within the past 24h. Powered by
 * `GET /api/leads/hot` which queries `campaign_leads.hot_lead_flag`.
 *
 * Renders nothing while idle. As soon as a Resend webhook fires
 * (email.opened / email.clicked), the next poll surfaces:
 *
 *   🔥 <business_name> opened your email N min ago [reply →]
 *
 * Clicking a row fires the optional `onReply(lead)` callback so the
 * parent chat can prefill a Cmd-style turn like:
 *   "draft reply to <business_name>".
 */
import React, { useEffect, useState } from "react";
import { Flame, MailCheck, MousePointerClick } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";


export default function HotLeadsBar({ onReply }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const r = await fetch(`${API}/api/cto/leads/hot?hours=24&limit=8`,
                                { headers: devAuthHeaders() });
        if (!r.ok) return;
        const j = await r.json();
        if (alive) setItems(j.items || []);
      } catch { /* silent */ }
    }
    poll();
    const t = setInterval(poll, 60_000);   // every minute
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!items || items.length === 0) return null;

  return (
    <div data-testid="hot-leads-bar"
         style={{ display: "flex", gap: 8, padding: "8px 12px",
                  borderBottom: "1px solid var(--dash-divider)",
                  background: "rgba(255,107,0,0.04)",
                  overflowX: "auto", whiteSpace: "nowrap" }}>
      <Flame size={13} style={{ color: "#FF6B00",
                                  flex: "0 0 13px", marginTop: 2 }} />
      <span style={{ fontSize: 10, letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: "#FF8C35", flex: "0 0 auto",
                      fontFamily: "'JetBrains Mono', monospace",
                      paddingTop: 2 }}>
        Hot leads
      </span>
      <div style={{ display: "flex", gap: 6, flex: 1, flexWrap: "nowrap" }}>
        {items.map((it) => (
          <button key={it.lead_id}
                  data-testid={`hot-lead-${it.lead_id}`}
                  onClick={() => onReply && onReply(it)}
                  title={`${it.business_name} · ${it.email || it.phone}`}
                  style={{ display: "inline-flex", alignItems: "center",
                           gap: 5,
                           padding: "3px 9px",
                           borderRadius: 999,
                           border: "1px solid rgba(255,107,0,0.40)",
                           background: "rgba(255,107,0,0.08)",
                           color: "#FFB070",
                           fontSize: 11, cursor: "pointer",
                           fontFamily: "'JetBrains Mono', monospace",
                           flex: "0 0 auto" }}>
            {it.hot_lead_reason === "email_clicked"
              ? <MousePointerClick size={10} />
              : <MailCheck size={10} />}
            <strong style={{ color: "#F0EDE8" }}>
              {(it.business_name || it.email || "lead").slice(0, 32)}
            </strong>
            <span style={{ color: "#a1958a", fontSize: 10 }}>
              {it.ago}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
