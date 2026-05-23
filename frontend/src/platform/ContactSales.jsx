/**
 * /enterprise — Contact Sales (PUBLIC)
 * AUREM homepage aesthetic — Cinzel serif, orange→gold gradient on key
 * words, dark void with subtle grid + glow, gold form CTA.
 * On submit: POST /api/enterprise/leads → Telegram alert + auto-reply.
 */
import React, { useState } from "react";
import { ArrowRight, ShieldCheck, MapPin, Users } from "lucide-react";
import DeveloperShell from "./developers/DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

const TIERS = [
  { id: "team",       name: "Team",       price: "$200",
    period: "/ month",
    sub: "5 – 20 developers",
    perks: ["Everything in Pro",
             "RBAC + audit logs",
             "Email support"] },
  { id: "business",   name: "Business",   price: "$800",
    period: "/ month", featured: true,
    sub: "20 – 100 developers",
    perks: ["Everything in Team",
             "SSO (SAML 2.0) — coming",
             "Canadian data residency",
             "Dedicated support channel"] },
  { id: "enterprise", name: "Enterprise", price: "Custom",
    period: "contract",
    sub: "100+ developers",
    perks: ["Everything in Business",
             "Dedicated instance option",
             "Custom SLA + signed MSA",
             "PIPEDA-only Canadian cluster"] },
];

export default function ContactSales() {
  const [form, setForm] = useState({
    company: "", email: "", team_size: "20-100", intent: "",
  });
  const [busy, setBusy]       = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError]     = useState(null);
  const sessionIdRef = React.useRef(
    `ent-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  );
  const mountedAtRef = React.useRef(Date.now());

  // iter 332b — scroll-depth + tier-hover ping
  React.useEffect(() => {
    let maxDepth = 0;
    let throttled = false;
    function track(event, tier) {
      if (throttled) return;
      throttled = true;
      setTimeout(() => { throttled = false; }, 1000);
      const depthPct = Math.round(
        (window.scrollY + window.innerHeight) /
        document.documentElement.scrollHeight * 100
      );
      maxDepth = Math.max(maxDepth, depthPct);
      fetch(`${API}/api/enterprise/leads/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          event, tier,
          depth_pct: maxDepth,
          ms_on_page: Date.now() - mountedAtRef.current,
        }),
      }).catch(() => {});
    }
    function onScroll() { track("scroll", ""); }
    window.addEventListener("scroll", onScroll, { passive: true });
    // Initial page-view ping
    track("view", "");
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function pingTierHover(tier) {
    fetch(`${API}/api/enterprise/leads/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionIdRef.current,
        event: "tier_hover", tier,
        ms_on_page: Date.now() - mountedAtRef.current,
      }),
    }).catch(() => {});
  }

  function update(k, v) { setForm(prev => ({ ...prev, [k]: v })); }

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await fetch(`${API}/api/enterprise/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "submit_failed");
      setSubmitted(true);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <DeveloperShell mode="landing">
      <section style={{ minHeight: "60vh", padding: "120px 5% 40px",
                         textAlign: "center" }}>
        <div className="dev-eyebrow" style={{ marginBottom: 28 }}>
          <span className="dot" />
          AUREM / ENTERPRISE
        </div>
        <h1 data-testid="enterprise-hero-headline" className="dev-title">
          <span className="t1">AUREM CTO</span>
          <span className="t2">for Enterprise.</span>
        </h1>
        <p className="dev-punch" style={{
              margin: "20px auto 40px", maxWidth: 620,
            }}>
          <strong>SSO, RBAC, audit logs, Canadian data residency,
          dedicated support.</strong> Sized for teams that need
          procurement, security review, and a real human on call.
        </p>
      </section>

      {/* Bullet strip */}
      <section style={{ padding: "0 5% 80px", maxWidth: 1000,
                         margin: "0 auto",
                         display: "grid",
                         gridTemplateColumns: "repeat(3, 1fr)",
                         gap: 16 }}>
        {[
          { icon: ShieldCheck, tag: "SECURITY",
            text: "SOC 2 ready · SAML 2.0 SSO · RBAC enforced · IP allowlisting · per-org rate limits" },
          { icon: MapPin, tag: "RESIDENCY",
            text: "Canadian-cluster option · PIPEDA-only data path · audit log export anytime" },
          { icon: Users, tag: "SUPPORT",
            text: "Named contact · 4-hour SLA · onboarding workshop · custom MSA + DPA" },
        ].map((b, i) => (
          <div key={i} className="dev-feature-card"
                data-testid="enterprise-pillar-card">
            <b.icon size={20} style={{ color: "#FF6B00", marginBottom: 14 }} />
            <span style={{ display: "block",
                             fontFamily: "'JetBrains Mono', monospace",
                             fontSize: 10, letterSpacing: "0.18em",
                             color: "#C9A84C", marginBottom: 10 }}>
              {b.tag}
            </span>
            <p style={{ fontSize: 13, color: "#F0EDE8", lineHeight: 1.6,
                          margin: 0 }}>{b.text}</p>
          </div>
        ))}
      </section>

      {/* Pricing tiers */}
      <section style={{ padding: "0 5% 80px", maxWidth: 1000,
                         margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <span className="dev-section-label">Plans</span>
          <h2 className="dev-section-title">Tier sizes.</h2>
        </div>
        <div style={{ display: "grid",
                       gridTemplateColumns: "repeat(3, 1fr)",
                       gap: 16 }}>
          {TIERS.map(t => (
            <div key={t.id}
                  data-testid={`enterprise-tier-${t.id}`}
                  onMouseEnter={() => pingTierHover(t.id)}
                  className="dev-feature-card"
                  style={{
                    borderColor: t.featured
                      ? "rgba(255,107,0,0.40)" : undefined,
                    boxShadow: t.featured
                      ? "0 18px 40px rgba(255,107,0,0.10)" : undefined,
                  }}>
              {t.featured && (
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10, letterSpacing: "0.2em",
                  color: "#FF6B00", marginBottom: 10, display: "block",
                  textTransform: "uppercase",
                }}>Most common</span>
              )}
              <h3 style={{ fontFamily: "'Cinzel', serif", fontSize: 18,
                            color: "#F0EDE8", marginBottom: 4 }}>
                {t.name}
              </h3>
              <p style={{ fontSize: 12, color: "#7A7590",
                           marginBottom: 18 }}>{t.sub}</p>
              <div style={{ display: "flex", alignItems: "baseline",
                             gap: 6, marginBottom: 18 }}>
                <span style={{ fontSize: 32, fontWeight: 600,
                                letterSpacing: "-0.02em",
                                color: "#F0EDE8" }}>{t.price}</span>
                <span style={{ fontSize: 12, color: "#7A7590" }}>
                  {t.period}
                </span>
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0,
                            display: "grid", gap: 6 }}>
                {t.perks.map((p, i) => (
                  <li key={i} style={{ fontSize: 13, color: "#7A7590",
                                          lineHeight: 1.5 }}>
                    · {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Contact form */}
      <section style={{ padding: "0 5% 100px" }}>
        <div style={{ maxWidth: 520, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <span className="dev-section-label">Talk to us</span>
            <h2 className="dev-section-title">Let's start a thread.</h2>
            <p className="dev-punch" style={{ margin: "10px auto 0" }}>
              Real human reply within one business day.
            </p>
          </div>

          {submitted ? (
            <div data-testid="enterprise-submit-success"
                  style={{
                    background: "#0F0F1A",
                    border: "1px solid rgba(80,200,120,0.30)",
                    borderRadius: 8, padding: 28,
                    textAlign: "center",
                  }}>
              <h3 style={{ fontFamily: "'Cinzel', serif",
                            fontSize: 18, color: "#67E8A0",
                            marginBottom: 8 }}>
                Got your note.
              </h3>
              <p style={{ fontSize: 14, color: "#7A7590" }}>
                We'll be in touch on the email you gave us. Check
                your spam folder if you don't see it within a few hours.
              </p>
            </div>
          ) : (
            <form onSubmit={submit} style={{
                background: "#0F0F1A",
                border: "1px solid rgba(255,107,0,0.10)",
                borderRadius: 8, padding: 28,
                display: "grid", gap: 14,
              }}>
              <Field label="Company name"
                      testid="enterprise-company-input"
                      value={form.company}
                      onChange={v => update("company", v)} />
              <Field label="Work email" type="email"
                      testid="enterprise-email-input"
                      value={form.email}
                      onChange={v => update("email", v)} />
              <label>
                <span style={{ display: "block",
                                fontFamily: "'JetBrains Mono', monospace",
                                fontSize: 10, letterSpacing: "0.18em",
                                textTransform: "uppercase",
                                color: "#7A7590", marginBottom: 6 }}>
                  Team size
                </span>
                <select data-testid="enterprise-size-select"
                         value={form.team_size}
                         onChange={e => update("team_size", e.target.value)}
                         className="dev-input"
                         style={{ width: "100%" }}>
                  <option value="5-20">5 – 20 developers</option>
                  <option value="20-100">20 – 100 developers</option>
                  <option value="100+">100+ developers</option>
                </select>
              </label>
              <label>
                <span style={{ display: "block",
                                fontFamily: "'JetBrains Mono', monospace",
                                fontSize: 10, letterSpacing: "0.18em",
                                textTransform: "uppercase",
                                color: "#7A7590", marginBottom: 6 }}>
                  Tell us what you need
                </span>
                <textarea data-testid="enterprise-intent-textarea"
                           value={form.intent} rows={4}
                           onChange={e => update("intent", e.target.value)}
                           placeholder="What are you trying to build, what does success look like, any deadlines?"
                           className="dev-input"
                           style={{ width: "100%", resize: "vertical" }} />
              </label>
              {error && (
                <div data-testid="enterprise-form-error"
                      style={{ fontSize: 12, color: "#FF6060" }}>
                  {error}
                </div>
              )}
              <button type="submit" disabled={busy}
                       data-testid="enterprise-submit-btn"
                       className="dev-btn-primary"
                       style={{ width: "100%", justifyContent: "center" }}>
                {busy ? "Sending…" : <>Talk to us <ArrowRight size={14} /></>}
              </button>
              <p style={{ fontSize: 11, color: "#4A4560",
                           textAlign: "center", marginTop: 4 }}>
                We don't sell data, share your email, or call you cold.
              </p>
            </form>
          )}
        </div>
      </section>
    </DeveloperShell>
  );
}

function Field({ label, value, onChange, type = "text", testid }) {
  return (
    <label>
      <span style={{
        display: "block",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "#7A7590", marginBottom: 6,
      }}>{label}</span>
      <input data-testid={testid} type={type} required
              value={value} onChange={e => onChange(e.target.value)}
              className="dev-input"
              style={{ width: "100%" }} />
    </label>
  );
}
