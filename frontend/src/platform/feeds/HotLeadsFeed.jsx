/**
 * 3.4 Hot Leads (Live) — reads aurem_live_viewers with FLAME SCORE ranking.
 *
 * Formula (backend): duration_seconds × ping_count × referral_bonus
 * Tiers: INFERNO ≥100 · HOT ≥50 · WARM ≥20 · COOL <20
 * Auto-refresh every 10s. When a viewer crosses score 50, the backend
 * fires a WhatsApp alert to the owner (once per session).
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import { Eye, RefreshCw, Flame, ExternalLink, Activity, Bell, Zap, Phone, PhoneOutgoing } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const fmtDur = (s) => {
  if (!s) return '0s';
  const m = Math.floor(s / 60); const ss = s % 60;
  return m > 0 ? `${m}m ${ss}s` : `${ss}s`;
};
const fmtTime = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
};

const TIER_STYLE = {
  INFERNO: { bg: 'linear-gradient(135deg, #ff1744, #ff6b00)', fg: '#fff', glow: '0 0 30px rgba(255,23,68,0.5)' },
  HOT:     { bg: 'linear-gradient(135deg, #ff6b00, #ffab00)', fg: '#fff', glow: '0 0 20px rgba(255,107,0,0.4)' },
  WARM:    { bg: 'rgba(255,171,0,0.18)',                      fg: '#ffab00', glow: 'none' },
  COOL:    { bg: 'rgba(100,150,255,0.12)',                    fg: '#6b9fff', glow: 'none' },
};

// Inline beep (WebAudio) — no extra asset needed
function playFlameSound(freq = 880, dur = 0.25) {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = new AC();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine'; o.frequency.value = freq;
    o.connect(g); g.connect(ctx.destination);
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur);
    o.start(); o.stop(ctx.currentTime + dur);
    // chord — second tone for drama
    setTimeout(() => { try { const o2 = ctx.createOscillator(); const g2 = ctx.createGain(); o2.type = 'sine'; o2.frequency.value = freq * 1.5; o2.connect(g2); g2.connect(ctx.destination); g2.gain.setValueAtTime(0.0001, ctx.currentTime); g2.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.02); g2.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur); o2.start(); o2.stop(ctx.currentTime + dur); } catch {} }, 120);
  } catch {}
}

export default function HotLeadsFeed({ token }) {
  const [data, setData] = useState({ viewers: [], count: 0, unique_ips_24h: 0, total_views_24h: 0, flame_alerts_sent_this_call: 0, auto_dials_fired_this_call: 0 });
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [toast, setToast] = useState(null);
  const timerRef = useRef(null);
  const prevScoresRef = useRef({}); // session_id → score

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/dashboard-feeds/hot-leads?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const j = await res.json();
      setData(j);

      // Sound alert: any viewer crossed 50 since last fetch
      const prev = prevScoresRef.current;
      const next = {};
      let newlyHot = false;
      let newlyInferno = false;
      (j.viewers || []).forEach(v => {
        next[v.session_id] = v.flame_score;
        const old = prev[v.session_id] ?? 0;
        if (old < 50 && v.flame_score >= 50) newlyHot = true;
        if (old < 100 && v.flame_score >= 100) newlyInferno = true;
      });
      if (soundEnabled && (newlyHot || newlyInferno)) {
        playFlameSound(newlyInferno ? 1200 : 880, newlyInferno ? 0.4 : 0.22);
      }
      prevScoresRef.current = next;

      // Toasts
      if ((j.auto_dials_fired_this_call || 0) > 0) {
        const r = j.auto_dial_results?.[0];
        setToast(`☎️ Auto-dialed ${r?.business_name || 'INFERNO lead'} — ${r?.status}`);
        setTimeout(() => setToast(null), 6000);
      } else if ((j.flame_alerts_sent_this_call || 0) > 0) {
        setToast(`🔥 ${j.flame_alerts_sent_this_call} WhatsApp flame alert(s) sent!`);
        setTimeout(() => setToast(null), 5000);
      }
    } catch (e) {
      console.error('hot-leads load failed', e);
    } finally {
      setLoading(false);
    }
  }, [token, soundEnabled]);

  const sendTestAlert = async () => {
    setTesting(true);
    try {
      const res = await fetch(`${API}/api/dashboard-feeds/flame-alerts/test`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const j = await res.json();
      setToast(j.sent ? `✅ Test flame alert sent to ${j.to}` : `⚠️ ${j.message || 'WHAPI not configured'}`);
      setTimeout(() => setToast(null), 5000);
    } catch (e) {
      setToast(`Error: ${e.message}`);
      setTimeout(() => setToast(null), 5000);
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => {
    load();
    timerRef.current = setInterval(load, 10000);
    return () => clearInterval(timerRef.current);
  }, [load]);

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="hot-leads-feed">
      <div className="max-w-7xl mx-auto">
        {toast && (
          <div
            className="fixed top-20 right-6 z-50 px-4 py-3 rounded-lg shadow-2xl text-sm font-medium"
            style={{ background: 'linear-gradient(135deg, #ff6b00, #ffab00)', color: '#fff', boxShadow: '0 8px 30px rgba(255,107,0,0.4)' }}
            data-testid="hot-leads-toast"
          >
            {toast}
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div className="flex items-start gap-3 min-w-0">
            <Flame className="size-7 text-[#FF6B00] flex-shrink-0 mt-1" style={{ filter: 'drop-shadow(0 0 8px rgba(255,107,0,0.6))' }} />
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Hot Leads, Flame Ranked</h1>
              <p className="text-xs sm:text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>
                Prospects currently on their sample site, ranked by Flame Score · Score &gt; {data.flame_alert_threshold ?? 50} auto-fires WhatsApp alert
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap sm:flex-shrink-0">
            <button
              onClick={() => {
                setSoundEnabled(s => !s);
                if (!soundEnabled) playFlameSound(660, 0.15); // preview
              }}
              className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition flex-shrink-0"
              style={{
                background: soundEnabled ? 'rgba(22,163,74,0.15)' : 'rgba(255,255,255,0.06)',
                color: soundEnabled ? '#16a34a' : 'rgba(255,255,255,0.5)',
                border: soundEnabled ? '1px solid rgba(22,163,74,0.3)' : '1px solid rgba(255,255,255,0.1)',
              }}
              data-testid="hot-leads-sound-toggle"
              title={soundEnabled ? 'Sound ON (click to disable)' : 'Sound OFF (click to enable)'}
            >
              <span aria-hidden>🔊</span>
              <span className="hidden sm:inline">{soundEnabled ? 'Sound ON' : 'Sound OFF'}</span>
              <span className="sm:hidden">{soundEnabled ? 'ON' : 'OFF'}</span>
            </button>
            <button
              onClick={sendTestAlert}
              disabled={testing}
              className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition disabled:opacity-50 flex-shrink-0"
              style={{ background: 'rgba(255,23,68,0.15)', color: '#ff1744', border: '1px solid rgba(255,23,68,0.3)' }}
              data-testid="hot-leads-test-alert"
            >
              <Bell className="size-4 flex-shrink-0" />
              <span className="hidden sm:inline">{testing ? 'Sending…' : 'Test WA Alert'}</span>
              <span className="sm:hidden">{testing ? '…' : 'Test'}</span>
            </button>
            <button
              onClick={load}
              className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition flex-shrink-0"
              style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00', border: '1px solid rgba(255,107,0,0.25)' }}
              data-testid="hot-leads-refresh"
            >
              <RefreshCw className={`size-4 flex-shrink-0 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6">
          <StatCard
            label="Live Viewers NOW" value={data.count ?? 0} color="#FF6B00" testid="hot-leads-stat-live"
            icon={<Activity className="size-4 text-[#FF6B00] animate-pulse" />} />
          <StatCard
            label="Hottest Score"
            value={data.viewers?.[0]?.flame_score ?? data.top_engaged?.[0]?.engagement_score ?? 0}
            color="#ff1744" testid="hot-leads-stat-top"
            icon={<Flame className="size-4 text-red-500" />} />
          <StatCard
            label={data.unique_ips_24h ? "Unique (24h)" : "Unique (lifetime)"}
            value={data.unique_ips_24h || data.lifetime_unique_ips || 0}
            color="#16a34a" testid="hot-leads-stat-unique" />
          <StatCard
            label={data.total_views_24h ? "Total Views (24h)" : "Total Views (lifetime)"}
            value={data.total_views_24h || data.lifetime_total_views || 0}
            color="#3b82f6" testid="hot-leads-stat-views" />
        </div>

        {(!data.viewers || data.viewers.length === 0) ? (
          <>
            <div className="aurem-glass-card text-center py-16" data-testid="hot-leads-empty">
              <Eye className="size-12 mx-auto mb-4" style={{ color: 'rgba(255,107,0,0.4)' }} />
              <p className="text-lg font-medium mb-1" style={{ color: 'var(--aurem-heading)' }}>No one viewing right now</p>
              <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>
                When a prospect opens their sample site, their Flame Score grows in real-time. Score &gt; 50 auto-triggers a WhatsApp ping to you.
              </p>
            </div>

            {/* Recent viewers fallback — shows activity from last 7 days */}
            {Array.isArray(data.recent_viewers) && data.recent_viewers.length > 0 && (
              <div className="mt-6" data-testid="hot-leads-recent-section">
                <h2 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
                  Recent Visitors (last 7 days) · {data.recent_viewers.length}
                </h2>
                <div className="space-y-2">
                  {data.recent_viewers.map((v, i) => (
                    <div
                      key={v.session_id || `recent-${i}`}
                      className="aurem-glass-card p-4 flex items-center gap-4"
                      data-testid={`hot-lead-recent-${i}`}
                      style={{ border: '1px solid rgba(255,255,255,0.06)' }}
                    >
                      <div
                        className="flex flex-col items-center justify-center rounded-lg px-3 py-2 min-w-[90px]"
                        style={{ background: 'rgba(100,150,255,0.10)', color: '#6b9fff' }}
                      >
                        <Flame className="size-4 mb-1 opacity-80" />
                        <div className="text-lg font-bold leading-tight">{v.flame_score}</div>
                        <div className="text-[9px] uppercase tracking-wider opacity-90 font-bold">RECENT</div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-semibold truncate" style={{ color: 'var(--aurem-heading)' }}>
                          {v.business_name || 'Unknown Business'}
                        </h3>
                        <div className="text-xs flex items-center gap-3 mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                          <span>{v.minutes_ago != null ? `${v.minutes_ago} min ago` : '—'}</span>
                          <span>·</span>
                          <span>{v.duration_seconds || 0}s viewed</span>
                          <span>·</span>
                          <span>{v.ping_count || 0} pings</span>
                        </div>
                        {v.slug_url && (
                          <a
                            href={v.slug_url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="text-xs underline mt-1 inline-block"
                            style={{ color: '#FF6B00' }}
                            data-testid={`hot-lead-recent-link-${i}`}
                          >
                            View sample site ↗
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Top engaged leads fallback — all-time report/sample view accumulation */}
            {Array.isArray(data.top_engaged) && data.top_engaged.length > 0 && (
              <div className="mt-6" data-testid="hot-leads-top-engaged-section">
                <h2 className="text-sm font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
                  Top Engaged Leads (by views) · {data.top_engaged.length}
                </h2>
                <div className="space-y-2">
                  {data.top_engaged.map((v, i) => {
                    const ago = v.last_view_minutes_ago != null
                      ? `${v.last_view_minutes_ago} min ago`
                      : v.last_view_days_ago != null
                        ? (v.last_view_days_ago === 0 ? 'today' : `${v.last_view_days_ago}d ago`)
                        : '—';
                    return (
                      <div
                        key={v.lead_id || `engaged-${i}`}
                        className="aurem-glass-card p-4 flex items-center gap-4"
                        data-testid={`hot-lead-engaged-${i}`}
                        style={{ border: '1px solid rgba(255,107,0,0.12)' }}
                      >
                        <div
                          className="flex flex-col items-center justify-center rounded-lg px-3 py-2 min-w-[90px]"
                          style={{ background: 'rgba(255,107,0,0.10)', color: '#FF8A3D' }}
                        >
                          <Eye className="size-4 mb-1 opacity-80" />
                          <div className="text-lg font-bold leading-tight">{v.engagement_score}</div>
                          <div className="text-[9px] uppercase tracking-wider opacity-90 font-bold">VIEWS</div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-base font-semibold truncate" style={{ color: 'var(--aurem-heading)' }}>
                            {v.business_name}
                          </h3>
                          <div className="text-xs flex items-center gap-3 mt-1 flex-wrap" style={{ color: 'var(--aurem-body-secondary)' }}>
                            <span>{ago}</span>
                            <span>·</span>
                            <span>📄 {v.report_views} report</span>
                            <span>·</span>
                            <span>🌐 {v.sample_views} sample</span>
                            {v.lifecycle_stage && (
                              <>
                                <span>·</span>
                                <span className="uppercase text-[10px] tracking-wider font-bold" style={{ color: '#FF8A3D' }}>
                                  {v.lifecycle_stage.replace(/_/g, ' ')}
                                </span>
                              </>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs mt-1">
                            {v.slug_url && (
                              <a
                                href={v.slug_url}
                                target="_blank" rel="noreferrer noopener"
                                className="underline" style={{ color: '#FF6B00' }}
                                data-testid={`hot-lead-engaged-sample-${i}`}
                              >View sample ↗</a>
                            )}
                            {v.phone && (
                              <a href={`tel:${v.phone}`} className="underline" style={{ color: '#16a34a' }}>
                                📞 Call
                              </a>
                            )}
                            {v.email && (
                              <a href={`mailto:${v.email}`} className="underline" style={{ color: '#6b9fff' }}>
                                ✉ Email
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-3">
            {data.viewers.map((v, i) => {
              const tier = v.flame_tier || 'COOL';
              const style = TIER_STYLE[tier];
              const isTop = i === 0 && v.flame_score > 20;
              return (
                <div
                  key={v.session_id || i}
                  className="aurem-glass-card p-5 transition"
                  style={{
                    boxShadow: isTop ? style.glow : 'none',
                    border: isTop ? '1px solid rgba(255,107,0,0.5)' : '1px solid rgba(255,255,255,0.08)',
                  }}
                  data-testid={`hot-lead-row-${i}`}
                >
                  <div className="flex items-start gap-4">
                    {/* Score pill */}
                    <div
                      className="flex flex-col items-center justify-center rounded-xl px-4 py-3 min-w-[120px]"
                      style={{ background: style.bg, color: style.fg }}
                      data-testid={`hot-lead-score-${i}`}
                    >
                      <Flame className="size-5 mb-1" />
                      <div className="text-2xl font-bold leading-tight">{v.flame_score}</div>
                      <div className="text-[10px] uppercase tracking-wider opacity-90 font-bold">{tier}</div>
                    </div>

                    {/* Details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        {isTop && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider" style={{ background: 'rgba(255,23,68,0.2)', color: '#ff1744' }}>
                            🏆 Top Lead
                          </span>
                        )}
                        <span className="size-2 rounded-full bg-red-500 animate-pulse" />
                        <h3 className="text-lg font-bold truncate" style={{ color: 'var(--aurem-heading)' }}>
                          {v.business_name || 'Unknown Business'}
                        </h3>
                        {v.flame_alert_fired && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1" style={{ background: 'rgba(255,23,68,0.18)', color: '#ff1744' }} data-testid={`hot-lead-alert-fired-${i}`}>
                            <Zap className="size-3" />
                            WA sent
                          </span>
                        )}
                        {v.auto_dial_status === 'dialed' && (
                          <span className="px-2 py-0.5 rounded text-xs font-bold flex items-center gap-1" style={{ background: 'linear-gradient(135deg, #ff1744, #ff6b00)', color: '#fff' }} data-testid={`hot-lead-auto-dial-${i}`}>
                            <PhoneOutgoing className="size-3" />
                            DIALING
                          </span>
                        )}
                        {v.auto_dial_status === 'mock_dialed' && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1" style={{ background: 'rgba(255,107,0,0.15)', color: '#FF6B00' }}>
                            <Phone className="size-3" />
                            Dial (mock)
                          </span>
                        )}
                        {v.auto_dial_status === 'blocked_gate' && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: 'rgba(234,179,8,0.15)', color: '#eab308' }} title="Accurate-Scout call gate is OFF for this lead">
                            🛑 Call gate OFF
                          </span>
                        )}
                        {v.auto_dial_status === 'no_phone' && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: 'rgba(100,150,255,0.12)', color: '#6b9fff' }}>
                            No phone on file
                          </span>
                        )}
                        {v.engagement_nudge_fired && !v.flame_alert_fired && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: 'rgba(255,107,0,0.18)', color: '#FF6B00' }}>
                            Nudge sent
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mt-3">
                        <Kv label="Watching" value={fmtDur(v.duration_seconds)} />
                        <Kv label="Pings" value={v.ping_count || 1} />
                        <Kv label="Last beat" value={fmtTime(v.last_heartbeat_at)} />
                        <Kv label="Referrer" value={v.referrer || 'direct'} truncate />
                      </div>
                    </div>

                    {/* Action */}
                    <a
                      href={v.slug_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition self-start"
                      style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00' }}
                      data-testid={`hot-lead-open-${i}`}
                    >
                      Open Site
                      <ExternalLink className="size-3" />
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Formula legend */}
        <div className="mt-6 aurem-glass-card p-4 text-xs" style={{ color: 'var(--aurem-body-secondary)' }} data-testid="flame-formula-legend">
          <div className="font-bold mb-2 flex items-center gap-1" style={{ color: 'var(--aurem-heading)' }}>
            <Flame className="size-3 text-[#FF6B00]" /> Flame Score Formula
          </div>
          <code className="block mb-2 font-mono" style={{ color: '#FF6B00' }}>
            flame_score = (duration_seconds / 10) × ping_count × referral_bonus
          </code>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
            <span>• Email referral: <b style={{ color: '#ff1744' }}>×2.5</b></span>
            <span>• Social / Search: <b style={{ color: '#ffab00' }}>×2.0</b></span>
            <span>• Other referred: <b style={{ color: '#6b9fff' }}>×1.5</b></span>
            <span>• Direct: <b>×1.0</b></span>
          </div>
          <div className="mt-3 pt-3 border-t border-white/5 grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
            <div><b style={{ color: '#ff1744' }}>Score &gt; 50</b> → WhatsApp alert fires to owner (once / session)</div>
            <div><b style={{ color: '#ff1744' }}>INFERNO (≥100)</b> → ORA auto-dials the prospect via Twilio</div>
            <div>All dials respect Accurate-Scout's <code>channel_gating.call</code> + DNC list</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, testid, icon }) {
  return (
    <div className="aurem-glass-card p-4" data-testid={testid}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>
        {icon}{label}
      </div>
      <div className="text-3xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}

function Kv({ label, value, truncate = false }) {
  return (
    <div>
      <div className="uppercase tracking-wider mb-0.5" style={{ color: 'var(--aurem-body-secondary)', fontSize: 10 }}>{label}</div>
      <div className={truncate ? 'truncate' : ''} style={{ color: 'var(--aurem-heading)' }}>{value}</div>
    </div>
  );
}
