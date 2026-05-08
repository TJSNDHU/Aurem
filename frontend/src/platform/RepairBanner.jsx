/**
 * RepairBanner — auto-polls /api/admin/repair/status every 10s.
 * Shows amber banner only when stage != "idle". System stays online.
 */
import React, { useEffect, useRef, useState } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const POLL_MS = 10000;

const AMBER = '#F59E0B';
const AMBER_BG = 'rgba(245,158,11,0.10)';
const AMBER_BORDER = 'rgba(245,158,11,0.45)';

function _fmtAgo(iso) {
  if (!iso) return '';
  try {
    const diffS = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diffS < 60) return `${Math.max(1, Math.floor(diffS))}s ago`;
    if (diffS < 3600) return `${Math.floor(diffS / 60)}m ago`;
    if (diffS < 86400) return `${Math.floor(diffS / 3600)}h ago`;
    return `${Math.floor(diffS / 86400)}d ago`;
  } catch { return ''; }
}

export default function RepairBanner() {
  const [info, setInfo] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      const token = sessionStorage.getItem('platform_token')
        || sessionStorage.getItem('aurem_platform_token')
        || localStorage.getItem('aurem_token')
        || localStorage.getItem('token');
      if (!token) return;
      try {
        const r = await fetch(`${API}/api/admin/repair/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) { if (!cancelled) setInfo(null); return; }
        const d = await r.json();
        if (!cancelled) setInfo(d);
      } catch {
        if (!cancelled) setInfo(null);
      }
    }
    probe();
    timerRef.current = setInterval(probe, POLL_MS);
    return () => { cancelled = true; clearInterval(timerRef.current); };
  }, []);

  const stage = info?.status?.stage || 'idle';
  if (!info || stage === 'idle' || !info.in_progress) return null;

  const label = info.status?.label || info.lock?.reason || 'self_repair';
  const startedTs = info.lock?.ts || info.status?.ts;

  return (
    <div
      data-testid="repair-banner"
      style={{
        margin: '0 auto 16px',
        padding: '12px 18px',
        borderRadius: 12,
        background: AMBER_BG,
        border: `1px solid ${AMBER_BORDER}`,
        boxShadow: '0 0 14px rgba(245,158,11,0.18)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
        fontFamily: "'JetBrains Mono', monospace",
        animation: 'repair-banner-fade 0.4s ease',
      }}
    >
      <style>{`
        @keyframes repair-banner-fade {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes repair-banner-pulse {
          0%, 100% { opacity: 1; }
          50%      { opacity: 0.55; }
        }
      `}</style>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: '1 1 auto' }}>
        <div
          aria-hidden
          style={{
            width: 10, height: 10, borderRadius: '50%', background: AMBER,
            boxShadow: `0 0 10px ${AMBER}`,
            animation: 'repair-banner-pulse 1.4s ease-in-out infinite',
          }}
        />
        <span style={{ color: AMBER, fontWeight: 700, fontSize: 13, letterSpacing: 1 }}>
          🔧 REPAIR IN PROGRESS
        </span>
        <span style={{ color: '#9AA0A6', fontSize: 12 }}>·</span>
        <span style={{ color: '#4ADE80', fontWeight: 700, fontSize: 12 }}>
          System: FULLY ONLINE ✅
        </span>
      </div>
      <div
        data-testid="repair-banner-detail"
        style={{ color: '#E8E0D0', fontSize: 12, opacity: 0.85 }}
      >
        Fixing: <span style={{ color: AMBER }}>{stage}</span>
        {' · '}
        Stage label: <span style={{ color: '#E8E0D0' }}>{label}</span>
        {startedTs && (
          <>
            {' · '}
            Started: <span style={{ color: '#E8E0D0' }}>{_fmtAgo(startedTs)}</span>
          </>
        )}
      </div>
    </div>
  );
}
