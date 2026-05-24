/**
 * SystemOverviewPublic — read-only mirror of 14.10 System Overview.
 * Route: /share/system-overview
 * No auth required. Fetches public stats + renders same layout but hides admin-only KPIs.
 */
import React from 'react';
import SystemOverview from './SystemOverview';

export default function SystemOverviewPublic() {
  return (
    <div data-testid="system-overview-public" style={{ minHeight: '100vh' }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 40,
        padding: '10px 24px', background: 'rgba(201,168,76,0.12)',
        borderBottom: '1px solid rgba(201,168,76,0.25)',
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.18em',
        color: '#C9A84C', textAlign: 'center', fontWeight: 700,
      }}>
        READ-ONLY PUBLIC VIEW · SHARED BY AUREM · APPLY AT
        <a href="/login" style={{ color: '#C9A84C', marginLeft: 8, textDecoration: 'underline' }}>AUREM.LIVE</a>
      </div>
      <SystemOverview publicMode={true} />
    </div>
  );
}
