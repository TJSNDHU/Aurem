import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, RotateCcw } from 'lucide-react';

const EMAIL = 'ora@aurem.live';
const ENTITY = 'Polaris Built Inc.';

export default function RefundPolicy() {
  return (
    <div className="min-h-screen" style={{ background: 'var(--aurem-bg, #050505)', color: 'var(--aurem-heading, #F4F4F4)' }}>
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity" style={{ color: 'var(--aurem-accent, #D4AF37)' }} data-testid="refund-back-link">
          <ArrowLeft className="size-4" /> Back to AUREM
        </Link>

        <div className="flex items-center gap-3 mb-4">
          <RotateCcw className="size-8" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
          <h1 className="text-3xl font-bold tracking-tight" data-testid="refund-title">Refund Policy</h1>
        </div>

        <p className="text-sm mb-8" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Effective: April 20, 2026 · 14-Day Satisfaction Guarantee</p>

        <div
          className="mb-10 p-5 rounded-xl"
          style={{
            background: 'rgba(212,175,55,0.06)',
            border: '1px solid rgba(212,175,55,0.22)',
            color: 'var(--aurem-body, #E8E0D0)',
          }}
        >
          <p className="text-sm leading-relaxed">
            <strong style={{ color: 'var(--aurem-accent, #D4AF37)' }}>TL;DR —</strong>
            &nbsp;If we haven’t started working on your repair yet, you get a <strong>full refund</strong> within 14 days, no questions asked. If repair labor has already begun and the work is unsuccessful due to a fault on our side, you get a <strong>partial credit</strong>. Fees for work already delivered, and platform-side failures (Shopify/Google/etc.) are non-refundable.
          </p>
        </div>

        <div className="space-y-8 text-sm leading-relaxed" style={{ color: 'var(--aurem-body, #CCC)' }}>
          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>1. 14-Day Full Refund Window</h2>
            <p>You may request a <strong>100% refund</strong> of any one-off Repair fee or the first month of a subscription within <strong>14 days of purchase</strong>, provided that:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>Repair work has <strong>not yet commenced</strong> (defined as: our technicians have not written, deployed, or pushed any code, content, or configuration to your systems); and</li>
              <li>No audit deliverable marked “final” has been released to you.</li>
            </ul>
            <p className="mt-2">Audit-only engagements are refundable only if the Audit report has not been delivered.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>2. Partial Credit When Repair Is Unsuccessful</h2>
            <p>If repair work has commenced and we are unable to resolve the specific items identified in your Audit due to a fault on our side (not a platform or third-party limitation), we will issue a <strong>pro-rated credit</strong> usable toward a future AUREM engagement. The credit is calculated against the unresolved line items and is valid for 12 months.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>3. Client-Side &amp; Platform-Side Failures Are Non-Refundable</h2>
            <p>Fees are <strong>not refundable</strong> when a Repair is blocked or reversed because of factors outside AUREM’s control, including but not limited to:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>Platform API deprecation or policy changes (Shopify, Google, Meta, Stripe, Twilio, Resend, etc.).</li>
              <li>Client-managed plugins, themes or scripts that overwrite our fixes after deployment.</li>
              <li>Access, credentials, or OAuth scopes withdrawn by the client mid-engagement.</li>
              <li>Content, branding, or product decisions that the client requested and later reverses.</li>
              <li>Events of force majeure (outages, legal orders, ISP issues).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>4. Subscription Cancellation</h2>
            <p>You may cancel a monthly or annual subscription at any time. Cancellation takes effect at the end of the current billing period. Unused time on an annual subscription is <strong>not refunded</strong>, but you retain full access until the cycle ends.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>5. Chargebacks</h2>
            <p>We ask that you reach out to us at <a href={`mailto:${EMAIL}`} style={{ color: 'var(--aurem-accent, #D4AF37)' }}>{EMAIL}</a> before initiating a chargeback. Most disputes can be resolved amicably within 2 business days. Unjustified chargebacks may result in service suspension and a $25 CAD chargeback handling fee.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>6. How to Request a Refund</h2>
            <p>Email <a href={`mailto:${EMAIL}?subject=${encodeURIComponent('Refund Request')}`} style={{ color: 'var(--aurem-accent, #D4AF37)' }}>{EMAIL}</a> with:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>The email on your AUREM account.</li>
              <li>The Stripe receipt number or invoice ID.</li>
              <li>A short note on why you’re requesting the refund.</li>
            </ul>
            <p className="mt-2">We respond within <strong>2 business days</strong>. Approved refunds are issued back to the original payment method within 5–10 business days.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>7. Contact</h2>
            <p>{ENTITY} · <a href={`mailto:${EMAIL}`} style={{ color: 'var(--aurem-accent, #D4AF37)' }}>{EMAIL}</a></p>
          </section>
        </div>
      </div>
    </div>
  );
}
