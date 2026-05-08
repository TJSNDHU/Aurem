/**
 * AUREM Acceptable Use Policy
 */
import React from 'react';
import { Link } from 'react-router-dom';

export default function AcceptableUsePolicy() {
  return (
    <div data-testid="acceptable-use-page"
      style={{
        minHeight: '100vh', background: '#0A0A0B', color: '#F2EDE4',
        fontFamily: "'DM Sans', system-ui, sans-serif",
        padding: '60px 24px',
      }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <Link to="/" style={{ fontFamily: "'Cinzel Decorative',serif", fontSize: 12,
                              letterSpacing: 4, color: '#C9A227', textDecoration: 'none' }}>
          AUREM
        </Link>
        <h1 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 44,
                     fontWeight: 300, marginTop: 32, marginBottom: 8 }}>
          Acceptable Use Policy
        </h1>
        <p style={{ color: '#8A8279', fontSize: 12, marginBottom: 32 }}>
          Last updated: April 26, 2026 · Polaris Built Inc.
        </p>

        <Section title="1. Purpose">
          This Acceptable Use Policy ("AUP") governs how customers may use AUREM. By using
          our services, you agree to follow these rules. Violations may result in
          immediate suspension or termination.
        </Section>

        <Section title="2. Prohibited content">
          You may not use AUREM to scan, monitor, or auto-repair sites that contain or
          promote: illegal goods or services; child sexual abuse material; content that
          incites violence; deceptive financial schemes; phishing or malware; or any
          content that violates Canadian or applicable foreign law.
        </Section>

        <Section title="3. Prohibited outreach">
          AUREM is CASL and PIPEDA compliant. You may not use AUREM's outreach features
          (email, SMS, voice) to: contact recipients without legal basis; impersonate
          another business; send unsolicited commercial messages outside CASL exemptions;
          or contact recipients on the National Do Not Call list (Canada) or equivalent
          registries.
        </Section>

        <Section title="4. Site authorization">
          By installing the AUREM pixel or registering a workspace, you confirm you own
          or have written authorization to modify the websites and assets listed. AUREM
          will refuse fixes on sites where ownership cannot be verified.
        </Section>

        <Section title="5. Rate limits & abuse">
          You may not use AUREM to circumvent rate limits, exhaust shared resources, run
          DDoS attacks, or scrape websites in violation of those sites' terms of service.
          AUREM reserves the right to throttle or suspend accounts engaging in abusive
          patterns.
        </Section>

        <Section title="6. Reporting violations">
          If you believe an AUREM customer is violating this AUP, email
          {' '}<a href="mailto:abuse@aurem.live" style={{ color: '#C9A227' }}>abuse@aurem.live</a>{' '}
          with details. We respond to all reports within 48 hours.
        </Section>

        <Section title="7. Changes">
          We may update this policy. Material changes will be communicated by email or
          in-platform notification at least 30 days before they take effect. Continued
          use of AUREM after changes take effect constitutes acceptance.
        </Section>

        <p style={{ marginTop: 48, fontSize: 12, color: '#8A8279' }}>
          Questions? Contact{' '}
          <a href="mailto:ora@aurem.live" style={{ color: '#C9A227' }}>ora@aurem.live</a>.
        </p>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 22,
                   fontWeight: 400, color: '#C9A227', marginBottom: 10 }}>{title}</h2>
      <p style={{ fontSize: 14, lineHeight: 1.8, color: '#C5BDB1', fontWeight: 300 }}>
        {children}
      </p>
    </section>
  );
}
