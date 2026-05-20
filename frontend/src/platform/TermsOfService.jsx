import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, FileText } from 'lucide-react';

const EMAIL = 'ora@aurem.live';
const ENTITY = 'Polaris Built Inc.';
const ADDRESS = '7221 Sigsbee Drive, Mississauga, ON L4T 3L6, Canada';

export default function TermsOfService() {
  return (
    <div className="min-h-screen" style={{ background: 'var(--aurem-bg, #050505)', color: 'var(--aurem-heading, #F4F4F4)' }}>
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity" style={{ color: 'var(--aurem-accent, #D4AF37)' }} data-testid="terms-back-link">
          <ArrowLeft className="size-4" /> Back to AUREM
        </Link>

        <div className="flex items-center gap-3 mb-4">
          <FileText className="size-8" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
          <h1 className="text-3xl font-bold tracking-tight" data-testid="terms-title">Terms of Service</h1>
        </div>

        <p className="text-sm mb-1" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Effective: April 20, 2026 · Governed by the laws of Ontario, Canada</p>
        <p className="text-sm mb-8" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Operated by <strong>{ENTITY}</strong>, {ADDRESS}</p>

        <div className="space-y-8 text-sm leading-relaxed" style={{ color: 'var(--aurem-body, #CCC)' }}>
          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>1. Acceptance of Terms</h2>
            <p>By accessing the AUREM platform or engaging our Website Repair, Audit or Automation services (collectively, the “Services”), you (“Client”) enter into a binding agreement with {ENTITY} operating as AUREM (“we”, “us”). If you do not accept these Terms, do not use the Services.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>2. Scope of Services</h2>
            <p>AUREM provides: (a) automated and human-assisted <strong>Website Audits</strong> that identify technical, SEO, schema/JSON-LD, compliance and performance issues; (b) <strong>Website Repair</strong> labor performed against the findings in the Audit; and (c) ongoing <strong>Automation &amp; Monitoring</strong> via our AI agents (ORA, Hunter, Sentinel, Critic).</p>
            <p className="mt-2">Work performed is strictly <strong>limited to the scope captured in the initial Audit</strong>. Any additional items discovered mid-engagement are classified as Out-of-Scope and require a new statement of work.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>3. Client Responsibilities &amp; Access</h2>
            <p>To perform Website Repair we may require collaborator-level access to your Shopify store, Google Search Console, Google Analytics, domain registrar, DNS provider, or other systems. You represent that you are authorized to grant such access. You agree to revoke access promptly when work is complete.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>4. Third-Party Platforms &amp; API Changes</h2>
            <p>AUREM integrates with third-party platforms (Shopify, Google, Meta, Stripe, email/SMS providers, etc.). Changes to these platforms’ APIs, policies, billing, or availability are <strong>outside our control and outside our liability</strong>. If a third-party change breaks a completed Repair, we will offer remediation at our then-current rates, not free of charge.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>5. Subscriptions &amp; Payment</h2>
            <p>Retainers and subscription plans are billed in advance via Stripe on a monthly or annual cycle as selected. One-off Repair engagements are billed upon scope confirmation. All prices are quoted in USD unless otherwise stated and exclude applicable taxes. Late or failed payment may result in service suspension.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>6. Refunds</h2>
            <p>Refund eligibility is governed by our <Link to="/refund" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>Refund Policy</Link>. In summary: a full refund is available within 14 days provided <strong>work has not commenced</strong>. Once repair labor has begun, partial pro-rated credits may apply where the failure is caused by our deliverable (not by client-side or third-party limitations).</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>7. AI Agents &amp; Automated Output</h2>
            <p>Our AI agents assist with drafting, analysis, outreach, and operational tasks. AI output may contain inaccuracies and must be reviewed before use. You are responsible for any action taken on AI recommendations. AUREM is not liable for commercial decisions made solely on AI-generated output.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>8. Scope Creep Protection</h2>
            <p>A quoted Repair includes the specific issues listed in the Audit report. New issues, additional stores, design changes, content writing, or platform migrations are <strong>not covered</strong> without written approval and a separate fee.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>9. Intellectual Property</h2>
            <p>You retain ownership of your brand, content, and business data. Upon full payment, custom code written by AUREM for your site is licensed to you for continued use. AUREM retains ownership of its proprietary tooling, AI agents, playbooks, and underlying platform.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>10. Warranty &amp; Limitation of Liability</h2>
            <p>We warrant that Repair work will be performed in a professional manner against the issues agreed in the Audit. Beyond that, the Services are provided “as-is”. To the maximum extent permitted by law, our aggregate liability for any claim shall not exceed the fees paid by you to AUREM in the <strong>three (3) months</strong> preceding the claim.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>11. Confidentiality</h2>
            <p>Each party agrees to protect the other’s confidential information with the same care it applies to its own, and to use it solely for the purpose of delivering the Services.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>12. Termination</h2>
            <p>Either party may terminate with 14 days’ written notice to {EMAIL}. Fees already invoiced for work in progress remain payable. Upon termination we will export your data and revoke access within 30 days.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>13. Governing Law &amp; Disputes</h2>
            <p>These Terms are governed by the laws of the Province of Ontario, Canada, without regard to conflict-of-law principles. Any dispute will first be addressed in good-faith discussion; if unresolved within 30 days, it shall be settled by binding arbitration seated in Mississauga, Ontario.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>14. Contact</h2>
            <p>Questions about these Terms? Contact <a href={`mailto:${EMAIL}`} style={{ color: 'var(--aurem-accent, #D4AF37)' }}>{EMAIL}</a> — {ENTITY}, {ADDRESS}.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
