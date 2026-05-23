/**
 * /developers/terms — Plain English terms (Auth-gated)
 */
import React from "react";
import { ScrollText } from "lucide-react";
import DeveloperShell from "./DeveloperShell";
import { PageHeader } from "./DevDashboard";

export default function DevTerms() {
  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="TERMS" title="Plain English Terms"
                  sub="The contract is short on purpose. No dark patterns." />

      <article data-testid="terms-content" className="av2-card"
                style={{ maxWidth: 760, padding: 28,
                          fontSize: 14, color: "var(--dash-text)",
                          lineHeight: 1.7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10,
                       marginBottom: 16, color: "var(--dash-orange)" }}>
          <ScrollText size={20} />
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11, letterSpacing: "0.18em",
            textTransform: "uppercase",
          }}>Version 1 — Feb 2026</span>
        </div>

        <Section title="1. As-is delivery">
          <p>
            AUREM CTO writes code as best it can. We don't promise it's bug-free.
            You're responsible for reviewing every pull request before
            merging it into production. Tests passing doesn't mean the
            logic is correct — it means the logic doesn't crash.
          </p>
        </Section>

        <Section title="2. BYOK responsibility">
          <p>
            When you connect Anthropic, DeepSeek or Gemini keys, calls
            count against <strong>your</strong> usage and your billing
            relationship with that provider. We pass the request through
            untouched. We don't monitor, throttle, or store your prompts.
          </p>
          <p>
            If your key gets rate-limited or rejected, we surface the
            provider's error verbatim. Rotating a leaked key is on you —
            we never email it back or display it.
          </p>
        </Section>

        <Section title="3. Abuse = instant suspension">
          <p>We block these patterns automatically, no warning:</p>
          <ul style={{ paddingLeft: 20, marginTop: 8, marginBottom: 8,
                        color: "var(--dash-text-muted)" }}>
            <li>Port scanning (nmap / masscan / zmap)</li>
            <li>Crypto miners (xmrig / monero stratum)</li>
            <li>SQL injection attempts against any non-yours target</li>
            <li>Mass email scraping or sending outside AUREM's CASL-gated pipeline</li>
            <li>Network recon (hping3 / nc -l / tcpdump)</li>
            <li>SSRF against private/loopback/internal IPs</li>
          </ul>
          <p>
            Account is flagged on first match and disabled pending review.
            We don't refund tokens on suspension.
          </p>
        </Section>

        <Section title="4. PIPEDA deletion rights">
          <p>
            Canadian law gives you the right to ask us to delete your
            personal info. Hit the <em>Delete account</em> button on the
            Settings page. We start a 30-day window during which your data
            is soft-deleted (recoverable if you change your mind). After
            30 days it's hard-purged from primary and backup collections.
          </p>
          <p>
            What we keep beyond 30 days: redacted audit logs of any abuse
            events flagged on your account, for fraud defense. These
            contain no PII.
          </p>
        </Section>

        <Section title="5. The honest stuff">
          <p>
            We will lower prices when our costs go down. We will raise
            them if usage gets out of hand. You'll get 30 days notice
            either way. The 1,000-token welcome grant doesn't expire if
            you're an active builder.
          </p>
        </Section>
      </article>
    </DeveloperShell>
  );
}

function Section({ title, children }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{
        fontFamily: "'Cinzel', serif",
        fontSize: 16, fontWeight: 600,
        color: "var(--dash-gold-bright)",
        marginBottom: 10, letterSpacing: "0.01em",
      }}>{title}</h2>
      <div style={{ color: "var(--dash-text-muted)", fontSize: 14 }}>
        {children}
      </div>
    </section>
  );
}
