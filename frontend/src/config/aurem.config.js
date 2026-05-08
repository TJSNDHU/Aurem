/**
 * ═══════════════════════════════════════════════════════════════════════════
 * AUREM FRONTEND CONFIG — Single Source of Truth
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * Change ANY value here and it propagates everywhere automatically.
 * DO NOT hardcode prices, copy, emails, trial days, or feature lists in any
 * other file. Import from this module instead:
 *
 *     import { AUREM, getPlan, trialCta } from '../config/aurem.config';
 *
 * Backend mirror: /app/backend/config/aurem_config.py
 * Live API:        GET /api/public/config (auto-syncs from backend)
 */

export const AUREM = {

  company: {
    name: 'Polaris Built Inc.',
    brand: 'AUREM',
    tagline: 'Your website is losing you customers right now.',
    email: 'ora@aurem.live',
    emailSupport: 'ora@aurem.live',
    emailAbuse: 'abuse@aurem.live',
    website: 'https://aurem.live',
    address: 'Mississauga, Ontario, Canada',
    phone: '+14314500004',
  },

  trial: {
    days: 7,
    reminderDay: 6,
    cardCaptureDay: 5,
  },

  pricing: {
    starter: {
      id: 'starter',
      name: 'Starter',
      price: 97,
      display: '$97',
      currency: 'CAD/month',
      voiceMinutes: 0,
      aiActions: 500,
      tag: 'Independent businesses',
      popular: false,
    },
    growth: {
      id: 'growth',
      name: 'Growth',
      price: 449,
      display: '$449',
      currency: 'CAD/month',
      voiceMinutes: 300,
      aiActions: 5000,
      tag: 'Most popular',
      popular: true,
    },
    enterprise: {
      id: 'enterprise',
      name: 'Enterprise',
      price: 997,
      display: '$997',
      currency: 'CAD/month',
      voiceMinutes: -1,
      aiActions: -1,
      tag: 'Agencies + multi-location',
      popular: false,
    },
  },

  planFeatures: {
    starter: [
      'Website pixel — nightly scan + repair',
      'SEO auto-repair — weekly fixes deployed',
      'ORA Chat on your website — 24/7',
      'Lead follow-up by email + SMS',
      'Morning Brief at 7am daily',
      '500 AI actions/month',
      'GEO Optimization',
      'CASL-compliant outreach',
    ],
    growth: [
      'Everything in Starter',
      'ORA Voice AI — 300 min/month included',
      '5,000 AI actions/month',
      'Economic Intelligence dashboard',
      '3 workspaces',
      'Partner referral access',
      'Priority support',
    ],
    enterprise: [
      'Everything in Growth',
      'Unlimited AI actions',
      '25 concurrent voice sessions',
      'White-label — your brand, your domain',
      'WordPress plugin — zero manual install',
      'Unlimited workspaces',
      'Dedicated onboarding call',
      'Slack support channel',
    ],
  },

  copy: {
    heroHeadlinePrefix: 'Your website is losing you',
    heroHeadlineSuffix: 'customers right now.',
    heroSub: "AUREM scans your site tonight, fixes the problems automatically, and sends AI agents to follow up on every lead you've been too busy to call back. Starting at $97 CAD/month.",
    trialNote: 'No credit card required',
    cancelNote: 'Cancel anytime',
  },

  routes: {
    signup: '/platform/signup',
    login: '/platform/login',
    demo: '/demo',
    dashboard: '/dashboard',
    contactMailto: 'mailto:ora@aurem.live?subject=AUREM%20Inquiry',
    onboardingPixel: '/onboarding/pixel',
  },
};

// ─── Helpers ────────────────────────────────────────────────────────────────

export const getPlan = (planId) =>
  AUREM.pricing[(planId || '').toLowerCase()] || null;

export const trialCta = () => `Start Free ${AUREM.trial.days}-Day Trial`;

export const trialNoteFull = () =>
  `${AUREM.copy.trialNote} · ${AUREM.copy.cancelNote}`;

export default AUREM;
