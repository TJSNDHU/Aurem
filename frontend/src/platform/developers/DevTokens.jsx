/**
 * /developers/tokens — Pricing & purchase (Auth-gated)
 */
import React, { useState } from "react";
import { Check, Coins } from "lucide-react";
import DeveloperShell, { devAuthHeaders, useDevMe } from "./DeveloperShell";
import { PageHeader } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

const TIERS = [
  { id: "starter", name: "Starter", price: "$9", cadence: "one-time",
    tokens: "10,000 tokens",
    perks: ["Same token cost table",
             "30-day expiry",
             "No card on file"] },
  { id: "builder", name: "Builder", price: "$39", cadence: "one-time",
    tokens: "50,000 tokens", featured: true,
    perks: ["Everything in Starter",
             "Priority queue (no throttling)",
             "60-day expiry"] },
  { id: "pro", name: "Pro", price: "$99", cadence: "per month",
    tokens: "Unlimited tokens",
    perks: ["Everything in Builder",
             "BYOK bypasses deductions",
             "Cancel any time"] },
];

export default function DevTokens() {
  const { me } = useDevMe();
  const [busy, setBusy] = useState("");
  const [msg, setMsg]   = useState(null);

  async function checkout(tier) {
    setBusy(tier); setMsg(null);
    try {
      const r = await fetch(`${API}/api/developers/checkout/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ tier }),
      });
      if (r.status === 404) {
        setMsg("Checkout opens in Batch C — back here in a few days.");
        return;
      }
      const j = await r.json();
      if (j.url) window.location.href = j.url;
      else if (!r.ok) throw new Error(j.detail || "checkout failed");
    } catch (e) {
      setMsg(String(e.message || e));
    } finally { setBusy(""); }
  }

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="TOKENS" title="Pay only for what you ship."
                  sub={`You currently have ${(me?.tokens_remaining ?? 0).toLocaleString()} tokens.`} />

      <div className="av2-grid-3-2"
           style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        {TIERS.map(t => (
          <div key={t.id} data-testid={`pricing-${t.id}-tier`}
               className={t.featured ? "av2-card-accent" : "av2-card"}
               style={{ display: "flex", flexDirection: "column" }}>
            {t.featured && (
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10, letterSpacing: "0.2em",
                color: "var(--dash-orange)",
                textTransform: "uppercase",
                marginBottom: 14,
              }}>Most popular</span>
            )}
            <h3 style={{ fontFamily: "'Cinzel', serif", fontSize: 18,
                          color: "var(--dash-text)", marginBottom: 6 }}>
              {t.name}
            </h3>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6,
                           marginBottom: 4 }}>
              <span style={{ fontSize: 36, fontWeight: 600,
                              letterSpacing: "-0.02em",
                              color: "var(--dash-text)" }}>{t.price}</span>
              <span style={{ fontSize: 12,
                              color: "var(--dash-text-muted)" }}>
                {t.cadence}
              </span>
            </div>
            <p style={{ fontSize: 13, color: "var(--dash-orange)",
                         marginBottom: 18, display: "flex",
                         alignItems: "center", gap: 6 }}>
              <Coins size={12} /> {t.tokens}
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px",
                          display: "grid", gap: 8, flex: 1 }}>
              {t.perks.map((p, i) => (
                <li key={i} style={{ display: "flex", gap: 8,
                                      fontSize: 13,
                                      color: "var(--dash-text-muted)" }}>
                  <Check size={14} style={{ color: "var(--dash-green)",
                                              flexShrink: 0, marginTop: 2 }} />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
            <button data-testid={`checkout-${t.id}-btn`}
                     onClick={() => checkout(t.id)} disabled={busy === t.id}
                     style={{
                       padding: "11px 0",
                       background: t.featured
                         ? "linear-gradient(135deg, #FF6B00, #FF8C35)"
                         : "transparent",
                       color: t.featured ? "#fff" : "var(--dash-orange)",
                       border: t.featured
                         ? "none"
                         : "1px solid rgba(255,107,0,0.30)",
                       borderRadius: 6,
                       fontSize: 13, fontWeight: 500,
                       cursor: "pointer",
                       opacity: busy === t.id ? 0.5 : 1,
                     }}>
              {busy === t.id ? "Loading…" : `Get ${t.name}`}
            </button>
          </div>
        ))}
      </div>

      {msg && (
        <div data-testid="tokens-msg" className="av2-card"
             style={{ borderColor: "rgba(201,168,76,0.30)",
                       background: "rgba(201,168,76,0.06)",
                       color: "var(--dash-amber)", fontSize: 13 }}>
          {msg}
        </div>
      )}
    </DeveloperShell>
  );
}
