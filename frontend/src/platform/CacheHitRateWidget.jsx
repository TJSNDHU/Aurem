/* CacheHitRateWidget — iter D-71/D-71b perf observability
 *
 * Lives in the admin sidebar (between A2A rail and Founder Timeline).
 * Polls /api/admin/poll-cache/stats every 30s. Renders:
 *   - Overall hit-rate gauge (% across all cached endpoints)
 *   - DB-ops-saved counter (sum of cache hits since boot)
 *   - Top 5 endpoints by call volume with per-endpoint hit-rate bars
 *   - Auto-tune ⚡ button per row when hit-rate < 40% (iter D-71b)
 *
 * Color coding:
 *   ≥80% hit-rate  green  (cache earning its keep)
 *   40-79%         amber  (TTL likely too short — bump it)
 *   <40%           red    (poll interval >= TTL → cache useless)
 *
 * Click endpoint name to copy the key for manual invalidate.
 * Click ⚡ to 2× the TTL (one click per endpoint, no manual math).
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Database, Zap } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const POLL_MS = 30_000;


const fmt = (n) => {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'k';
  return String(n);
};

const rateColor = (pct) => {
  if (pct >= 80) return '#22C55E';
  if (pct >= 40) return '#F59E0B';
  return '#EF4444';
};


const CacheHitRateWidget = () => {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState(null);
  const [tuning, setTuning] = useState(null);   // key currently being tuned
  const [flash, setFlash] = useState(null);     // brief "TTL 15s → 30s" confirmation

  const load = useCallback(async () => {
    try {
      const token = localStorage.getItem('aurem_token') || localStorage.getItem('token') || localStorage.getItem('platform_token');
      if (!token) return;
      const r = await fetch(`${API_URL}/api/admin/poll-cache/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        setErr(`${r.status}`);
        return;
      }
      const j = await r.json();
      setStats(j);
      setErr(null);
    } catch (e) {
      setErr(String(e?.message || e));
    }
  }, []);

  const autoTune = useCallback(async (key) => {
    const token = localStorage.getItem('aurem_token') || localStorage.getItem('token') || localStorage.getItem('platform_token');
    if (!token) return;
    setTuning(key);
    try {
      const r = await fetch(`${API_URL}/api/admin/poll-cache/tune`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ key, multiplier: 2.0 }),
      });
      if (r.ok) {
        const j = await r.json();
        setFlash({ key, prev: j.previous_ttl_sec, next: j.new_ttl_sec });
        setTimeout(() => setFlash(null), 4000);
        load();
      }
    } finally {
      setTuning(null);
    }
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (!cancelled) await load();
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [load]);

  if (err || !stats || stats.total_keys === 0) return null;

  const overall = stats.overall_hit_rate_pct ?? 0;
  const saved   = stats.db_ops_saved_estimate ?? 0;
  const topKeys = (stats.keys || []).slice(0, 5);

  return (
    <div
      data-testid="cache-hitrate-widget"
      style={{
        padding: '8px 14px',
        borderBottom: '1px solid rgba(212,175,55,0.06)',
      }}>
      {/* Header */}
      <div
        style={{
          fontSize: 8, color: '#7A7468', letterSpacing: '0.2em',
          textTransform: 'uppercase', marginBottom: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Database style={{ width: 9, height: 9, color: '#D4AF37' }} />
          Poll Cache · {stats.total_keys} keys
        </span>
        <span
          data-testid="cache-overall-pct"
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10, fontWeight: 700, color: rateColor(overall),
          }}>
          {overall.toFixed(0)}%
        </span>
      </div>

      {/* DB ops saved counter */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 5, marginBottom: 8,
          fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#EDE8DF',
        }}>
        <Zap style={{ width: 9, height: 9, color: '#22C55E' }} />
        <span data-testid="cache-db-saved">
          {fmt(saved)} DB ops saved
        </span>
      </div>

      {/* Top 5 endpoints */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {topKeys.map((k) => {
          const pct = k.hit_rate_pct ?? 0;
          const color = rateColor(pct);
          const short = k.key.length > 18 ? k.key.slice(0, 18) + '…' : k.key;
          const isTuning = tuning === k.key;
          const isFlashing = flash?.key === k.key;
          // Only offer auto-tune for keys with enough calls AND poor hit-rate.
          // Backend computes this via the `tunable` flag.
          const showTune = !!k.tunable && !k.tuned;
          return (
            <div
              key={k.key}
              title={`${k.key} · ${k.calls} calls · ${pct}% hit · ${k.last_load_ms}ms loader · TTL ${k.effective_ttl_sec}s${k.tuned ? ' (tuned)' : ''}`}
              data-testid={`cache-key-${k.key.replace(/[:/]/g, '-')}`}
              style={{
                fontSize: 8, fontFamily: 'JetBrains Mono, monospace',
                color: '#9A9388',
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 1 }}>
                <span
                  onClick={() => navigator.clipboard?.writeText(k.key)}
                  style={{
                    flex: 1, whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis', cursor: 'pointer',
                  }}>
                  {short}
                  {k.tuned && (
                    <span style={{ color: '#06B6D4', marginLeft: 3, fontWeight: 700 }}>·tuned</span>
                  )}
                </span>
                {showTune && (
                  <button
                    type="button"
                    disabled={isTuning}
                    onClick={(e) => { e.stopPropagation(); autoTune(k.key); }}
                    data-testid={`cache-tune-${k.key.replace(/[:/]/g, '-')}`}
                    title={`Auto-tune: double TTL from ${k.effective_ttl_sec}s to ${k.effective_ttl_sec * 2}s`}
                    style={{
                      background: isTuning ? 'rgba(245,158,11,0.15)' : 'rgba(212,175,55,0.18)',
                      border: '1px solid rgba(212,175,55,0.4)',
                      borderRadius: 3,
                      color: '#D4AF37',
                      cursor: isTuning ? 'wait' : 'pointer',
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 7, fontWeight: 700,
                      padding: '1px 4px',
                      lineHeight: 1.2,
                      letterSpacing: '0.08em',
                    }}>
                    {isTuning ? '…' : '⚡2×'}
                  </button>
                )}
                <span style={{ color, fontWeight: 700, minWidth: 26, textAlign: 'right' }}>
                  {pct.toFixed(0)}%
                </span>
              </div>
              <div style={{
                height: 2, background: 'rgba(154,147,136,0.15)', borderRadius: 1,
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${Math.min(100, pct)}%`,
                  height: '100%',
                  background: color,
                  transition: 'width 220ms ease',
                }} />
              </div>
              {isFlashing && (
                <div
                  data-testid={`cache-tune-confirm-${k.key.replace(/[:/]/g, '-')}`}
                  style={{
                    fontSize: 7, color: '#22C55E', marginTop: 2,
                    fontFamily: 'JetBrains Mono, monospace',
                  }}>
                  ✓ TTL {flash.prev}s → {flash.next}s
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{
        fontSize: 7, color: '#7A7468', marginTop: 6,
        fontStyle: 'italic',
      }}>
        Click name to copy · ⚡2× to auto-tune · refreshes 30s
      </div>
    </div>
  );
};

export default CacheHitRateWidget;
