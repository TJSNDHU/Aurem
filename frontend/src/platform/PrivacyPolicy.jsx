import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield } from 'lucide-react';

const EMAIL = 'ora@aurem.live';
const ENTITY = 'Polaris Built Inc.';
const ADDRESS = '7221 Sigsbee Drive, Mississauga, ON L4T 3L6, Canada';

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen" style={{ background: 'var(--aurem-bg, #050505)', color: 'var(--aurem-heading, #F4F4F4)' }}>
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity" style={{ color: 'var(--aurem-accent, #D4AF37)' }} data-testid="privacy-back-link">
          <ArrowLeft className="size-4" /> Back to AUREM
        </Link>

        <div className="flex items-center gap-3 mb-4">
          <Shield className="size-8" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
          <h1 className="text-3xl font-bold tracking-tight" data-testid="privacy-title">Privacy Policy</h1>
        </div>

        <p className="text-sm mb-1" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Effective: April 20, 2026 · PIPEDA-compliant · Governed by Ontario, Canada</p>
        <p className="text-sm mb-8" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Operated by <strong>{ENTITY}</strong>, {ADDRESS}</p>

        <div className="space-y-8 text-sm leading-relaxed" style={{ color: 'var(--aurem-body, #CCC)' }}>
          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>1. Who We Are</h2>
            <p>AUREM is a Website Repair and business-automation service operated by {ENTITY}, a corporation registered in Ontario, Canada. We are committed to handling your personal information in accordance with Canada’s <strong>Personal Information Protection and Electronic Documents Act (PIPEDA)</strong> and applicable Ontario privacy legislation.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>2. Information We Collect</h2>
            <p>We collect three categories of data:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li><strong>Account data:</strong> name, email, company, billing address, payment method (via Stripe).</li>
              <li><strong>Audit &amp; Repair data:</strong> screenshots, SEO/schema scans, performance metrics, and credentials or OAuth tokens you voluntarily grant so we can repair your Shopify store, Google Search Console, domain DNS, or similar platforms.</li>
              <li><strong>Platform telemetry:</strong> usage logs, error traces, AI-agent conversation history, and session metadata used to deliver and improve the service.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>3. How We Use Your Information</h2>
            <p>We use your data only to: deliver the Audit and Repair work you purchased; operate our AI agents on your behalf; process payments; send service notifications; investigate fraud or misuse; and comply with legal obligations. We <strong>do not</strong> sell your data.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>4. Access to Client Dashboards &amp; End-Customer Data</h2>
            <p>During a Website Repair engagement we may access dashboards that contain your <strong>end-customers’</strong> personal information (e.g., Shopify orders, analytics). We act as a <strong>data processor</strong> on your behalf. We:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>Access only what is strictly necessary to perform the Repair.</li>
              <li>Do not export, copy, or store your end-customer data on our systems beyond what is required to complete the work.</li>
              <li>Revoke our access immediately once the Repair is accepted.</li>
              <li>Maintain audit logs of any access for 12 months.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>5. Storage &amp; Security</h2>
            <p>Data is stored in encrypted databases with AES-256 at rest and TLS 1.3 in transit. Access to production systems is restricted to authorized personnel behind multi-factor authentication. We run multi-tenant isolation with per-client scoping enforced at the database layer.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>6. Third-Party Processors</h2>
            <p>We rely on reputable vendors: Stripe (payments), Google (OAuth and Workspace), MongoDB Atlas (database), Redis Cloud (caching), and LLM providers (OpenAI, Anthropic, Google) for AI-agent inference. Each is contractually required to protect your data and we share only what is necessary for each function.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>7. Your Rights Under PIPEDA</h2>
            <p>You have the right to: request access to personal data we hold about you; correct inaccuracies; withdraw consent; request deletion subject to our legal retention obligations; and file a complaint with the Office of the Privacy Commissioner of Canada if you believe your rights have been violated. To exercise any of these rights, email <a href={`mailto:${EMAIL}`} style={{ color: 'var(--aurem-accent, #D4AF37)' }}>{EMAIL}</a>.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>8. Retention</h2>
            <p>Account and engagement data is retained for the duration of your active subscription plus 30 days. Audit reports and invoices are retained for 7 years to meet Canadian tax and accounting requirements. You may request earlier deletion of non-financial data at any time.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>9. Data Location &amp; Cross-Border Transfer</h2>
            <p>Primary data storage is in North America (Canada / United States). Some sub-processors (Stripe, Google) may process data in other jurisdictions. By using the service you consent to such cross-border processing under the safeguards above.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>10. Cookies</h2>
            <p>We use only essential cookies required for authentication and session management. We do not use advertising trackers. You may disable non-essential cookies in your browser settings without losing core functionality.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>11. Children’s Privacy</h2>
            <p>The service is intended for businesses and users aged 18 and above. We do not knowingly collect data from children under 13.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>12. Changes to This Policy</h2>
            <p>We may update this Policy as the service evolves. Material changes will be emailed to active clients at least 14 days before taking effect.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>13. Contact, Privacy Officer</h2>
            <p>For any privacy question, complaint, or access/deletion request, reach our Privacy Officer at <a href={`mailto:${EMAIL}`} style={{ color: 'var(--aurem-accent, #D4AF37)' }}>{EMAIL}</a> or by mail: {ENTITY}, {ADDRESS}. We respond within 30 days as required by PIPEDA.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
