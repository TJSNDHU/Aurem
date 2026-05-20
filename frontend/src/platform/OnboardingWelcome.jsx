/**
 * AUREM Post-Payment Welcome / Onboarding Dashboard
 * =================================================
 * Route: /welcome?session_id={stripe_session}
 * Shows ORA greeting by name, 4-step task checklist, 7-day countdown.
 */
import React, { useState, useEffect } from 'react';
import {
  CheckCircle, Loader2, Clock, Sparkles, MessageCircle,
  ArrowRight, Phone, Zap, TrendingUp, Star, AlertCircle, MapPin, Globe,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const GOLD = '#C9A227';
const BG = '#0A0A0A';

const STATUS_CONFIG = {
  done:    { icon: CheckCircle, color: '#4ADE80', label: 'Complete',   pulse: false },
  running: { icon: Loader2,     color: GOLD,      label: 'Running',    pulse: true  },
  queued:  { icon: Clock,       color: GOLD,      label: 'Queued',     pulse: false },
  pending: { icon: Clock,       color: '#9ca3af', label: 'Pending',    pulse: false },
};

const TaskCard = ({ task }) => {
  const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  const eta = task.eta_minutes ? `~${task.eta_minutes} min`
    : task.eta_hours ? `~${task.eta_hours}h`
    : task.eta_days ? `${task.eta_days} days`
    : '';
  return (
    <div data-testid={`task-${task.key}`}
      className="p-5 rounded-xl border flex items-center gap-4 transition-all"
      style={{
        background: task.status === 'done' ? 'rgba(74,222,128,0.06)' : 'rgba(255,255,255,0.02)',
        borderColor: task.status === 'done' ? 'rgba(74,222,128,0.3)' : 'rgba(201,162,39,0.18)',
      }}>
      <div className="size-11 shrink-0 rounded-lg flex items-center justify-center"
        style={{ background: `${cfg.color}22` }}>
        <Icon className={`size-5 ${cfg.pulse ? 'animate-spin' : ''}`} style={{ color: cfg.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-white">{task.label}</div>
        <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.55)' }}>
          {cfg.label}{eta && ` · ${eta}`}
        </div>
      </div>
      {task.status === 'done' && (
        <div className="text-[10px] font-bold tracking-wider" style={{ color: '#4ADE80' }}>DONE ✓</div>
      )}
    </div>
  );
};

const getSessionId = () => {
  const params = new URLSearchParams(window.location.search);
  return params.get('session_id') || '';
};

// iter 322aw — Plan-redirect helper. If user landed at /welcome?plan=XXX
// without a session_id, kick them straight to Stripe checkout for that SKU.
const getPlanParam = () => {
  const params = new URLSearchParams(window.location.search);
  return params.get('plan') || '';
};

const PLAN_TO_SERVICE_ID = {
  security_suite: 'security_suite_bundle',
  vanguard:       'security_vanguard',
  shannon:        'security_shannon_patcher',
  casl:           'security_casl_compliance',
  soc2:           'security_soc2_audit',
  auto_heal:      'security_auto_heal',
};

const OnboardingWelcome = () => {
  const [sessionId] = useState(getSessionId());
  const [planParam] = useState(getPlanParam());
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [retries, setRetries] = useState(0);
  const [redirecting, setRedirecting] = useState(false);

  // iter 322aw — Public-checkout redirect for ?plan= entries (homepage CTA)
  useEffect(() => {
    if (sessionId) return;          // post-payment flow — handled below
    if (!planParam) return;
    const serviceId = PLAN_TO_SERVICE_ID[planParam];
    if (!serviceId) return;
    setRedirecting(true);
    (async () => {
      try {
        const r = await fetch(`${API}/api/public/subscribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service_id: serviceId,
            origin_url: window.location.origin,
          }),
        });
        const j = await r.json();
        if (j?.url) {
          window.location.href = j.url;
        } else {
          setError(j?.detail || 'Checkout could not start. Please try again.');
          setRedirecting(false);
        }
      } catch (e) {
        setError(e.message || 'Checkout failed');
        setRedirecting(false);
      }
    })();
  }, [sessionId, planParam]);

  useEffect(() => {
    if (!sessionId) {
      if (!planParam) setError('Missing session_id in URL');
      return;
    }
    let cancelled = false;
    let retryTimer = null;
    const fetchData = async () => {
      try {
        const r = await fetch(`${API}/api/onboarding/by-session/${sessionId}`);
        if (r.status === 404) {
          // Tenant may still be provisioning — auto-retry up to 10 times every 3s
          if (retries < 10) {
            retryTimer = setTimeout(() => !cancelled && setRetries((x) => x + 1), 3000);
            return;
          }
          throw new Error('Tenant not provisioned yet, please refresh in a minute');
        }
        if (!r.ok) throw new Error('Failed to load onboarding');
        const d = await r.json();
        if (!cancelled) setData(d);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    fetchData();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [sessionId, retries]);

  // Auto-poll while the Google Business scan is still running (max 20 polls @ 8s = 160s)
  useEffect(() => {
    if (!data?.tenant_id) return;
    const scanTask = (data.tasks || []).find((t) => t.key === 'google_scan');
    if (!scanTask || scanTask.status === 'done') return;
    let cancelled = false;
    let count = 0;
    const tick = async () => {
      if (cancelled || count >= 20) return;
      count += 1;
      try {
        const r = await fetch(`${API}/api/onboarding/tenant/${data.tenant_id}`);
        if (r.ok) {
          const fresh = await r.json();
          if (!cancelled) setData((prev) => ({ ...(prev || {}), ...fresh }));
          const st = (fresh.tasks || []).find((t) => t.key === 'google_scan');
          if (st?.status === 'done') return; // stop polling once complete
        }
      } catch (_) { /* ignore transient errors */ }
      if (!cancelled) setTimeout(tick, 8000);
    };
    const id = setTimeout(tick, 8000);
    return () => { cancelled = true; clearTimeout(id); };
  }, [data?.tenant_id, data?.tasks]);

  if (redirecting) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: BG, color: '#fff' }} data-testid="welcome-redirecting-stripe">
        <div className="text-center max-w-md">
          <div className="size-12 rounded-full border-2 border-[#C9A227]/20 border-t-[#C9A227] animate-spin mx-auto mb-4" />
          <div className="text-[11px] tracking-[0.4em] font-semibold mb-2" style={{ color: GOLD }}>
            REDIRECTING TO SECURE CHECKOUT
          </div>
          <h1 className="text-xl font-bold mb-2" style={{ fontFamily: 'Cinzel, serif' }}>
            🛡 AUREM Security Suite
          </h1>
          <p className="text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>
            Hold tight, Stripe is opening with your $197/mo bundle…
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6" style={{ background: BG, color: '#fff' }} data-testid="welcome-error">
        <div className="text-center max-w-md">
          <div className="text-sm tracking-[0.4em] mb-3" style={{ color: GOLD }}>AUREM</div>
          <h1 className="text-2xl font-bold mb-3" style={{ fontFamily: 'Cinzel, serif' }}>Setting up your account…</h1>
          <p className="text-sm mb-6" style={{ color: 'rgba(255,255,255,0.6)' }}>{error}</p>
          <button onClick={() => window.location.reload()} data-testid="welcome-retry"
            className="px-5 py-2.5 rounded-lg text-xs font-bold tracking-wider"
            style={{ background: GOLD, color: '#000' }}>
            RETRY
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: BG, color: '#fff' }} data-testid="welcome-loading">
        <div className="text-center">
          <div className="size-12 rounded-full border-2 border-[#C9A227]/20 border-t-[#C9A227] animate-spin mx-auto" />
          <div className="mt-5 text-xs tracking-[0.4em]" style={{ color: GOLD }}>
            {retries > 0 ? `PROVISIONING YOUR ACCOUNT (${retries}/10)…` : 'WELCOMING YOU TO AUREM…'}
          </div>
        </div>
      </div>
    );
  }

  const { customer = {}, tasks = [], progress_pct = 0, days_remaining = 7, target_first_win, scan_result } = data;
  const firstName = (customer.business_name || customer.email || 'friend').split(/[@\s]/)[0];
  const scanTask = tasks.find((t) => t.key === 'google_scan') || {};
  const found = scan_result?.found || {};
  const analysis = scan_result?.analysis || {};
  const gaps = analysis.gaps || [];

  return (
    <div className="min-h-screen relative" data-testid="welcome-dashboard"
      style={{ background: BG, color: '#fff', fontFamily: 'Jost, Manrope, sans-serif' }}>

      {/* Gold glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] pointer-events-none"
        style={{ background: `radial-gradient(ellipse, ${GOLD}1f 0%, transparent 70%)` }} />

      <div className="relative max-w-4xl mx-auto px-6 md:px-10 py-16" style={{ zIndex: 1 }}>

        {/* Welcome Header */}
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 mb-5">
            <div className="size-2.5 rounded-full animate-pulse" style={{ background: GOLD, boxShadow: `0 0 16px ${GOLD}` }} />
            <div className="text-[11px] tracking-[0.4em] font-semibold" style={{ color: GOLD }}>AUREM</div>
          </div>
          <div className="text-[11px] tracking-[0.5em] mb-4" style={{ color: 'rgba(255,255,255,0.5)' }}>
            SUBSCRIPTION ACTIVATED
          </div>
          <h1 className="text-4xl md:text-5xl font-bold mb-4" style={{ fontFamily: 'Cinzel, serif', lineHeight: 1.15 }}>
            Welcome, {firstName}! 🎉
          </h1>
          <p className="text-base md:text-lg mb-3" style={{ color: 'rgba(255,255,255,0.75)' }}>
            I'm <strong style={{ color: GOLD }}>ORA</strong>, your AI Business Intelligence.
          </p>
          <p className="text-sm max-w-xl mx-auto" style={{ color: 'rgba(255,255,255,0.55)' }}>
            Your <strong className="text-white">{(customer.plan || 'starter').toUpperCase()}</strong> account is active.
            I'm setting up everything behind the scenes, you'll get your first new customers within 7 days or a full refund.
          </p>
        </div>

        {/* Countdown */}
        <div className="rounded-2xl p-6 md:p-8 border mb-10 text-center"
          style={{ background: 'linear-gradient(135deg, rgba(201,162,39,0.10), rgba(0,0,0,0.3))', borderColor: 'rgba(201,162,39,0.3)' }}
          data-testid="welcome-countdown">
          <div className="text-[10px] tracking-[0.4em] mb-3" style={{ color: GOLD }}>YOUR FIRST RESULTS IN</div>
          <div className="flex items-baseline justify-center gap-3">
            <span className="font-bold tabular-nums" style={{ fontFamily: 'Cinzel, serif', color: GOLD, fontSize: 'clamp(3rem, 10vw, 5.5rem)', lineHeight: 1 }}>
              {days_remaining}
            </span>
            <span className="text-2xl md:text-3xl" style={{ color: 'rgba(255,255,255,0.6)' }}>DAYS</span>
          </div>
          <div className="mt-3 text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>
            Target: {target_first_win ? new Date(target_first_win).toLocaleDateString('en-CA', { weekday: 'long', month: 'short', day: 'numeric' }) : '7 days from now'}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between text-[11px] mb-2">
            <span style={{ color: 'rgba(255,255,255,0.6)' }}>Setup Progress</span>
            <span className="font-mono font-bold" style={{ color: GOLD }} data-testid="welcome-progress-pct">{progress_pct}%</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: `${progress_pct}%`, background: `linear-gradient(90deg, ${GOLD}, #e6c34a)`, boxShadow: `0 0 12px ${GOLD}80` }} />
          </div>
        </div>

        {/* Task Checklist */}
        <div className="space-y-3 mb-12" data-testid="welcome-tasks">
          {tasks.map((t) => (
            <TaskCard key={t.key} task={t} />
          ))}
        </div>

        {/* Google Business Scan Results */}
        {scanTask.status === 'done' && scan_result && (
          <div className="rounded-2xl p-6 md:p-8 border mb-10"
            style={{ background: 'linear-gradient(135deg, rgba(74,222,128,0.06), rgba(0,0,0,0.25))', borderColor: 'rgba(74,222,128,0.3)' }}
            data-testid="welcome-scan-result">
            <div className="flex items-center gap-2 mb-5">
              <CheckCircle className="size-5" style={{ color: '#4ADE80' }} />
              <div className="text-[11px] tracking-[0.3em] font-semibold" style={{ color: '#4ADE80' }}>
                GOOGLE BUSINESS SCAN COMPLETE
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div>
                <div className="text-[10px] tracking-wider mb-1" style={{ color: 'rgba(255,255,255,0.5)' }}>BUSINESS</div>
                <div className="text-sm font-semibold text-white truncate">
                  {found.business_name || scan_result.business_name || '—'}
                </div>
              </div>
              <div>
                <div className="text-[10px] tracking-wider mb-1" style={{ color: 'rgba(255,255,255,0.5)' }}>RATING</div>
                <div className="text-sm font-semibold flex items-center gap-1" style={{ color: GOLD }}>
                  {found.rating ? (
                    <>
                      <Star className="size-3.5 fill-current" />
                      {found.rating} <span className="opacity-60 text-[11px]">({found.review_count || 0})</span>
                    </>
                  ) : (
                    <span style={{ color: 'rgba(255,255,255,0.5)' }}>No rating yet</span>
                  )}
                </div>
              </div>
              <div>
                <div className="text-[10px] tracking-wider mb-1" style={{ color: 'rgba(255,255,255,0.5)' }}>GAPS FOUND</div>
                <div className="text-sm font-semibold" style={{ color: '#F59E0B' }} data-testid="scan-issues-count">
                  {analysis.issues_count || gaps.length || 0} fixable
                </div>
              </div>
              <div>
                <div className="text-[10px] tracking-wider mb-1" style={{ color: 'rgba(255,255,255,0.5)' }}>SOURCE</div>
                <div className="text-sm font-semibold" style={{ color: 'rgba(255,255,255,0.8)' }}>
                  {(scan_result.primary_source || 'google_places').replace(/_/g, ' ')}
                </div>
              </div>
            </div>

            {(found.address || found.website) && (
              <div className="flex flex-wrap gap-4 text-xs mb-5 pb-5 border-b" style={{ borderColor: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.7)' }}>
                {found.address && (
                  <div className="flex items-center gap-1.5"><MapPin className="size-3.5" style={{ color: GOLD }} />{found.address}</div>
                )}
                {found.phone && (
                  <div className="flex items-center gap-1.5"><Phone className="size-3.5" style={{ color: GOLD }} />{found.phone}</div>
                )}
                {found.website && (
                  <div className="flex items-center gap-1.5"><Globe className="size-3.5" style={{ color: GOLD }} />
                    <a href={found.website} target="_blank" rel="noreferrer" className="hover:underline truncate max-w-[260px]">{found.website.replace(/^https?:\/\//, '')}</a>
                  </div>
                )}
              </div>
            )}

            {gaps.length > 0 && (
              <div data-testid="welcome-scan-gaps">
                <div className="text-[11px] tracking-[0.25em] mb-3 font-semibold" style={{ color: GOLD }}>
                  ORA WILL FIX THESE FOR YOU
                </div>
                <ul className="space-y-2.5">
                  {gaps.slice(0, 6).map((g) => (
                    <li key={g.key} className="flex items-start gap-3 p-3 rounded-lg border"
                      style={{ borderColor: 'rgba(201,162,39,0.18)', background: 'rgba(255,255,255,0.02)' }}>
                      <AlertCircle className="size-4 mt-0.5 shrink-0"
                        style={{ color: g.severity === 'critical' ? '#EF4444' : g.severity === 'high' ? '#F59E0B' : GOLD }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-white">{g.title}</div>
                        <div className="text-[12px] mt-0.5" style={{ color: 'rgba(255,255,255,0.65)' }}>{g.fix}</div>
                      </div>
                    </li>
                  ))}
                </ul>
                {gaps.length > 6 && (
                  <div className="mt-3 text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>
                    + {gaps.length - 6} more gaps queued for auto-fix…
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {scanTask.status === 'running' && (
          <div className="rounded-2xl p-6 border mb-10 flex items-center gap-3"
            style={{ background: 'rgba(201,162,39,0.05)', borderColor: 'rgba(201,162,39,0.2)' }}
            data-testid="welcome-scan-running">
            <Loader2 className="size-5 animate-spin" style={{ color: GOLD }} />
            <div>
              <div className="text-sm font-semibold text-white">Scanning your Google Business profile…</div>
              <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.6)' }}>
                Results appear here automatically in under 10 minutes.
              </div>
            </div>
          </div>
        )}

        {/* What ORA is doing */}
        <div className="rounded-2xl p-6 md:p-7 border mb-10"
          style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(201,162,39,0.2)' }}>
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="size-4" style={{ color: GOLD }} />
            <div className="text-[11px] tracking-[0.3em] font-semibold" style={{ color: GOLD }}>
              WHAT ORA IS DOING RIGHT NOW
            </div>
          </div>
          <ul className="space-y-2.5 text-sm" style={{ color: 'rgba(255,255,255,0.7)' }}>
            <li className="flex items-start gap-2"><Zap className="size-4 mt-0.5 shrink-0" style={{ color: GOLD }} />Scanning your Google Business profile for optimization opportunities</li>
            <li className="flex items-start gap-2"><TrendingUp className="size-4 mt-0.5 shrink-0" style={{ color: GOLD }} />Drafting your free professional website (ready in 24 hours)</li>
            <li className="flex items-start gap-2"><MessageCircle className="size-4 mt-0.5 shrink-0" style={{ color: GOLD }} />Setting up automated Google review collection</li>
            <li className="flex items-start gap-2"><Phone className="size-4 mt-0.5 shrink-0" style={{ color: GOLD }} />Configuring WhatsApp + SMS + email campaigns</li>
          </ul>
        </div>

        {/* Hybrid Storefront — Your Active Services + Upsell */}
        <div className="rounded-2xl p-6 md:p-7 border mb-10"
          style={{ background: 'linear-gradient(135deg, rgba(212,175,55,0.06), rgba(255,138,61,0.03))', borderColor: 'rgba(212,175,55,0.25)' }}
          data-testid="welcome-services-panel">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="size-4" style={{ color: GOLD }} />
            <div className="text-[11px] tracking-[0.3em] font-semibold" style={{ color: GOLD }}>
              POWER UP · À LA CARTE SERVICES
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <div data-testid="welcome-svc-repair" className="p-3 rounded-lg border" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(212,175,55,0.15)' }}>
              <div className="text-xs font-bold text-white mb-1">🔧 Website Repair</div>
              <div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.55)' }}>$29/mo · Auto-fix 23 issues</div>
            </div>
            <div data-testid="welcome-svc-crm" className="p-3 rounded-lg border" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(212,175,55,0.15)' }}>
              <div className="text-xs font-bold text-white mb-1">📇 CRM Starter</div>
              <div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.55)' }}>$29/mo · 50 calls · 250 SMS · 1k emails</div>
            </div>
            <div data-testid="welcome-svc-voice" className="p-3 rounded-lg border" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(212,175,55,0.15)' }}>
              <div className="text-xs font-bold text-white mb-1">📞 Voice Agent AI</div>
              <div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.55)' }}>$149/mo · 24/7 inbound calls · 400 min</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-[11px]" style={{ color: 'rgba(34,197,94,0.9)' }}>
            <Sparkles className="size-3.5" />
            <span>Pick 3+ → auto <b>15% bundle discount</b> · Pick 5+ → 25% · Pick 8+ → 35%</span>
          </div>
        </div>

        {/* CTAs */}
        <div className="text-center">
          <div className="text-sm mb-4" style={{ color: 'rgba(255,255,255,0.6)' }}>
            I'll WhatsApp you the moment your first results are live.
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            <a href="/my/website" data-testid="welcome-cta-my-website"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs tracking-wider hover:brightness-110 transition-all"
              style={{ background: GOLD, color: '#000' }}>
              GO TO MY DASHBOARD <ArrowRight className="size-4" />
            </a>
            <a href="/my/ora" data-testid="welcome-cta-chat"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs tracking-wider border hover:bg-white/5 transition-all"
              style={{ borderColor: GOLD, color: GOLD }}>
              <MessageCircle className="size-4" /> CHAT WITH ORA
            </a>
          </div>
          <div className="mt-8 pt-8 border-t text-[11px] tracking-wider"
            style={{ borderColor: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.7)' }}>
            Need help? Reply to your welcome WhatsApp or email <a href="mailto:ora@aurem.live" className="hover:underline" style={{ color: GOLD }}>ora@aurem.live</a>
          </div>
        </div>

      </div>
    </div>
  );
};

export default OnboardingWelcome;
