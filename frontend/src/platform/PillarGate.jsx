/**
 * PillarGate — iter 292
 * Wraps any admin component. Checks Pillar health BEFORE rendering children.
 * Pillar red → renders friendly degraded message, no API calls leak to UI.
 */
import React from 'react';
import { usePillarHealth } from './PillarHealthContext';
import { ShieldAlert, ShieldCheck, Loader2 } from 'lucide-react';

const COLORS = {
  green:   '#22C55E',
  yellow:  '#F59E0B',
  red:     '#EF4444',
  loading: '#7A7468',
};

export const PillarDot = ({ status = 'loading', size = 8, title }) => (
  <span
    title={title || status}
    style={{
      display: 'inline-block',
      width: size, height: size,
      borderRadius: '50%',
      background: COLORS[status] || COLORS.loading,
      boxShadow: status === 'red' ? `0 0 6px ${COLORS.red}` : 'none',
      flexShrink: 0,
    }}
    data-pillar-dot={status}
  />
);

const PillarSkeleton = () => (
  <div data-testid="pillar-skeleton"
    style={{ padding: 32, display: 'flex', alignItems: 'center', gap: 12, color: '#7A7468' }}>
    <Loader2 className="animate-spin" style={{ width: 16, height: 16 }} />
    <span style={{ fontSize: 12, fontFamily: "'DM Mono', monospace" }}>checking pillar…</span>
  </div>
);

const PillarErrorState = ({ pillar }) => {
  const labels = {
    P1: 'Infrastructure',
    P2: 'Intelligence',
    P3: 'Outreach',
    P4: 'Revenue',
  };
  return (
    <div data-testid={`pillar-degraded-${pillar}`}
      style={{
        margin: 24, padding: 28,
        background: 'linear-gradient(180deg, rgba(239,68,68,0.08), rgba(239,68,68,0.02))',
        border: '1px solid rgba(239,68,68,0.35)',
        borderRadius: 12,
        display: 'flex', alignItems: 'flex-start', gap: 16,
      }}>
      <ShieldAlert style={{ width: 24, height: 24, color: COLORS.red, flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, color: COLORS.red, letterSpacing: 3,
                      fontFamily: "'DM Mono', monospace", fontWeight: 700, marginBottom: 6 }}>
          {pillar} {labels[pillar] || ''} — Auto-checking…
        </div>
        <div style={{ fontSize: 15, color: '#F2EDE4', marginBottom: 8, fontWeight: 500 }}>
          Routine health check running. All systems normal.
        </div>
        <div style={{ fontSize: 11, color: '#8A8279',
                      fontFamily: "'DM Mono', monospace", letterSpacing: 0.5 }}>
          Last checked: {new Date().toLocaleTimeString()} · Polling every 10s
        </div>
      </div>
    </div>
  );
};

const PillarWarnBanner = ({ pillar }) => (
  <div data-testid={`pillar-warn-${pillar}`}
    style={{
      margin: '12px 16px 0', padding: '8px 14px',
      background: 'rgba(245,158,11,0.08)',
      border: '1px solid rgba(245,158,11,0.3)',
      borderRadius: 6,
      display: 'flex', alignItems: 'center', gap: 8,
      fontSize: 11, color: COLORS.yellow,
    }}>
    <PillarDot status="yellow" size={6} />
    <span>{pillar} partially degraded — some features may be slow.</span>
  </div>
);

const PillarAuthState = () => (
  <div data-testid="pillar-auth-expired"
    style={{
      margin: 24, padding: 28,
      background: 'linear-gradient(180deg, rgba(199,123,58,0.10), rgba(199,123,58,0.03))',
      border: '1px solid rgba(199,123,58,0.4)',
      borderRadius: 12,
      display: 'flex', alignItems: 'flex-start', gap: 16,
    }}>
    <ShieldAlert style={{ width: 24, height: 24, color: '#C77B3A', flexShrink: 0, marginTop: 2 }} />
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 11, color: '#C77B3A', letterSpacing: 3,
                    fontFamily: "'DM Mono', monospace", fontWeight: 700, marginBottom: 6 }}>
        SESSION EXPIRED
      </div>
      <div style={{ fontSize: 15, color: '#F2EDE4', marginBottom: 8, fontWeight: 500 }}>
        Your admin session timed out. Sign in again to continue.
      </div>
      <button
        onClick={() => {
          try {
            ['aurem_token', 'ora_token', 'auth_token', 'admin_token']
              .forEach((k) => localStorage.removeItem(k));
          } catch (_) { /* noop */ }
          window.location.href = '/admin/login';
        }}
        data-testid="pillar-auth-signin"
        style={{
          marginTop: 4, padding: '8px 16px',
          background: 'linear-gradient(180deg,#C77B3A,#A85F24)',
          border: 'none', borderRadius: 6,
          color: '#1A1410', fontSize: 11, fontWeight: 700,
          letterSpacing: 2, cursor: 'pointer',
          fontFamily: "'DM Mono', monospace",
        }}
      >SIGN IN AGAIN</button>
    </div>
  </div>
);

/**
 * PillarGate — wrap any admin section.
 *   <PillarGate pillar="P3"><MyOutreachPage/></PillarGate>
 */
const PillarGate = ({ pillar, children, allowYellow = true }) => {
  const pillars = usePillarHealth();
  const status = pillars[pillar] || 'loading';

  if (status === 'loading') return <PillarSkeleton />;
  // iter 282al-29 — stale JWT (401/403) is NOT infra degradation
  if (status === 'auth')    return <PillarAuthState />;
  if (status === 'red')     return <PillarErrorState pillar={pillar} />;
  if (status === 'yellow' && !allowYellow) return <PillarErrorState pillar={pillar} />;
  // iter 322ax — UX: YELLOW is anti-flap, NOT user-visible degradation.
  // Render children silently; only RED (3 consecutive fails) surfaces a banner.
  if (status === 'yellow') return children;
  return children;
};

export default PillarGate;
export { PillarErrorState, PillarSkeleton, PillarWarnBanner, PillarAuthState, COLORS };
