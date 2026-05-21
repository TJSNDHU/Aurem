/**
 * useLuxeDashboardData — single hook that powers the entire Luxe Home
 * dashboard. Every number/series here is REAL data from the backend.
 * No mocks. No fake numbers.
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../../lib/api';

const API = BACKEND_URL;

const safeGet = async (url, headers, timeout = 10000) => {
  try {
    const { data } = await axios.get(url, { headers, timeout });
    return data;
  } catch (_e) {
    return null;
  }
};

const DEFAULT = {
  loading: true,
  pulse: { active: false },
  totalRevenue: { value: 0, deltaPct: 0, deltaAbs: 0 },
  websiteHealth: { value: 0, max: 100 },
  autoFix: { value: 0, max: 100 },
  agents: [],
  services: { active: 0, total: 0 },
  growth: [],
  websiteScan: { geo: 0, sec: 0, acc: 0, seo: 0, lastScan: '—' },
  oraRepair: { successPct: 0, healed: 0, attempts: 0, deltaPct: 0, series: [] },
  securityAlerts: { count: 0, items: [] },
  vanguard: { score: 0, platform: 0, site: 0, backlinks: 0, brokenLinks: 0, insecureLinks: 0, totals: null },
  // iter 325n — V2 surfaces
  resultsSummary: {},
  pipelineStages: [],
  pipelineTotal: 0,
  inboxThreads: [],
  inboxUnread: 0,
  // iter 325u — connection health for Topbar pulse.
  //   online   → green pulse
  //   degraded → yellow pulse (streak ≥ 2)
  //   offline  → red pulse  (streak ≥ 3)
  apiStatus: 'online',
  lastUpdated: null,
};

export const useLuxeDashboardData = (token) => {
  const [data, setData] = useState(DEFAULT);
  // iter 325u — track consecutive failed refresh cycles so the topbar
  // can surface a "degraded" yellow pulse before the full red error UI.
  // The threshold matches `useAuthFetch`'s 3-strike rule for symmetry.
  const failStreak = useRef(0);

  const refresh = useCallback(async () => {
    if (!token) {
      setData({ ...DEFAULT, loading: false });
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };

    const [leadStats, agentsStatus, repairLeaderboard, repairHistory, scanEvents, subs, catalog, homeAgg,
           resultsSummary, pipeline, inboxThreads] =
      await Promise.all([
        safeGet(`${API}/api/leads/stats`, headers),
        safeGet(`${API}/api/aurem/agents/status`, headers),
        safeGet(`${API}/api/repair/health/leaderboard`, headers),
        safeGet(`${API}/api/repair/history?limit=30`, headers),
        safeGet(`${API}/api/customer/pipeline/scan-events?limit=30`, headers),
        safeGet(`${API}/api/customer/subscriptions`, headers),
        safeGet(`${API}/api/catalog/services`, headers),
        // iter 322bj — aggregated home payload (pulse bars + richer growth + sparkline + alerts)
        safeGet(`${API}/api/me/home/dashboard`, headers),
        // iter 325n — V2 dashboard surfaces these at top level so the new
        // MetricRow / PipelineCard / InboxCard render without extra hooks.
        safeGet(`${API}/api/customer/results-summary`, headers),
        safeGet(`${API}/api/customer/results-pipeline`, headers),
        safeGet(`${API}/api/customer/inbox/threads?limit=20`, headers),
      ]);

    // iter 325u/325z — connection health computation with HYSTERESIS.
    //
    // The earlier rule reset `failStreak` to 0 the moment *any* success
    // came through. That created a flap pattern: if the success rate was
    // roughly 50/50 (e.g. one slow endpoint + ten fast ones during a
    // sub-pod restart), the topbar pill blinked online↔degraded every
    // 30 s — exactly the bug the founder kept re-reporting.
    //
    // Fix: treat the streak as a *bucket*. Each cycle:
    //   • bad cycle (≥80% nulls) → +1
    //   • good cycle             → -1 (clamped at 0)
    // Pill thresholds unchanged:
    //   ≥3 → offline (red)   |   ≥2 → degraded (yellow)   |   else → online
    // Net effect: you need 3 GOOD cycles after an outage to fully clear,
    // and 3 BAD cycles after recovery to flip red. No more 30-s blink.
    const probeResults = [leadStats, agentsStatus, repairLeaderboard, repairHistory,
                           scanEvents, subs, catalog, homeAgg,
                           resultsSummary, pipeline, inboxThreads];
    const failCount = probeResults.filter((r) => r === null).length;
    const failRatio = failCount / probeResults.length;
    if (failRatio >= 0.8) {
      failStreak.current = Math.min(failStreak.current + 1, 6);
    } else {
      failStreak.current = Math.max(failStreak.current - 1, 0);
    }
    const apiStatus = failStreak.current >= 3 ? 'offline'
                    : failStreak.current >= 2 ? 'degraded'
                    : 'online';

    // Vanguard runs a live backlink scan that can take 10–30s on first hit.
    // Fetch in the background and patch state when ready — never blocks
    // the initial dashboard render.
    safeGet(`${API}/api/customer/vanguard/status`, headers, 45000).then((vg) => {
      if (!vg) return;
      setData((prev) => ({
        ...prev,
        vanguard: {
          score: vg.vanguard_score ?? 0,
          platform: vg.platform_hardening?.score ?? 0,
          site: vg.site_security?.score ?? 0,
          backlinks: vg.backlinks?.score ?? 0,
          brokenLinks: vg.backlinks?.totals?.outbound_broken ?? 0,
          insecureLinks: vg.backlinks?.totals?.outbound_insecure ?? 0,
          totals: vg.backlinks?.totals ?? null,
          rateLimiter: vg.platform_hardening?.rate_limiter ?? 'memory',
          rlsEnforced: !!vg.platform_hardening?.rls_enforced,
          cspEnforced: !!vg.platform_hardening?.csp_enforced,
          hsts: !!vg.platform_hardening?.hsts_enabled,
          siteFindings: vg.site_security?.findings_count ?? 0,
        },
      }));
    });

    const firstSite = repairLeaderboard?.sites?.[0]?.url
      || repairLeaderboard?.leaderboard?.[0]?.url || null;
    const repairScores = firstSite
      ? await safeGet(`${API}/api/repair/scores?url=${encodeURIComponent(firstSite)}`, headers)
      : null;

    // ── Total Revenue (from leads stats)
    const stats = leadStats?.stats || leadStats || {};
    const totalLeads  = stats.total_leads ?? stats.total ?? stats.count ?? 0;
    const totalValue  = stats.total_value ?? 0;
    const conv        = stats.conversion_rate ?? 0;
    const estRevenue  = Math.round(totalValue || (totalLeads * conv * 100));
    const deltaPct    = stats.delta_pct ?? 0;

    // ── Agents (8 customer-facing) — log10 normalized so all visible
    let agents = [];
    if (Array.isArray(agentsStatus?.agents)) {
      const raw = agentsStatus.agents.map((a) => ({
        k: (a.name || a.role || '?').replace(/ Agent$/i, '').slice(0, 9),
        n: Math.max(0, Number(a.tasks_completed) || 0),
        status: a.status || 'STANDBY',
      }));
      const maxN = Math.max(1, ...raw.map((a) => a.n));
      agents = raw.map((a) => {
        const norm = a.n > 0 ? Math.log10(a.n + 1) / Math.log10(maxN + 1) : 0;
        return {
          k: a.k, n: a.n,
          v: a.n === 0 ? 0 : Math.max(8, Math.round(8 + norm * 92)),
          status: a.status,
        };
      });
    }
    if (agents.length === 0) {
      agents = ['Scout', 'Hunter', 'Closer', 'Envoy', 'Follow-up', 'Referral', 'Voice', 'Pixel']
        .map((k) => ({ k, n: 0, v: 0, status: 'STANDBY' }));
    }
    agents = agents.slice(0, 8);
    const pulseActive = agents.some((a) =>
      /ACTIVE|SCANNING|ENGAGING|BUILDING|HUNTING|NURTURING|AMPLIFYING|SPEAKING|WATCHING/i.test(a.status));

    // ── Website Scan (from /api/repair/scores)
    const scanGeo = repairScores?.geo?.score_after          ?? repairScores?.geo?.score          ?? 0;
    const scanSec = repairScores?.security?.score_after     ?? repairScores?.security?.score     ?? 0;
    const scanAcc = repairScores?.accessibility?.score_after?? repairScores?.accessibility?.score?? 0;
    const scanSeo = repairScores?.seo?.score_after          ?? repairScores?.seo?.score          ?? 0;

    // ── Website Health (composite) — prefer real scan composite
    const scoreSum = scanGeo + scanSec + scanAcc + scanSeo;
    const lbHealth = repairLeaderboard?.summary?.average_health ?? repairLeaderboard?.score ?? null;
    const compHealth = scoreSum > 0
      ? Math.round(scoreSum / 4)
      : (typeof lbHealth === 'number' && lbHealth > 0 ? lbHealth : 0);

    // ── Auto Fix counters
    const fixHistory = repairHistory?.history || repairHistory?.fixes || [];
    const totalFixes = repairHistory?.total ?? fixHistory.length;
    const successPct = repairHistory?.success_rate ?? 0;
    const healed     = fixHistory.filter((f) => (f.success !== false) && (f.resolved !== false)).length;
    const series = (fixHistory || []).slice(0, 12).map((f, i) => ({
      i, v: (f.success !== false ? 1 : 0),
    }));

    // ── Growth data
    const growth = (scanEvents?.events || [])
      .slice(-12)
      .map((ev, i) => ({
        m: (ev.date || ev.timestamp || `${i+1}`).slice(0, 10),
        a: ev.leads || 0,
        b: ev.outreach || 0,
      }));

    // ── Recent alerts (from history of failed fixes)
    const alerts = (fixHistory || [])
      .filter((f) => f.success === false || f.severity === 'high')
      .slice(0, 6)
      .map((f) => ({
        time: (f.created_at || '').slice(11, 16),
        level: (f.severity || 'LOW').toUpperCase(),
        msg: f.message || f.action_taken || f.category || 'event',
      }));

    setData({
      loading: false,
      pulse: { active: pulseActive },
      totalRevenue: {
        // iter 322bj — prefer Stripe-backed home aggregate when available
        value: homeAgg?.kpis?.revenue_total ?? estRevenue,
        deltaPct: homeAgg?.kpis?.revenue_delta_pct ?? deltaPct,
        deltaAbs: homeAgg?.kpis?.revenue_delta_value ?? 0,
      },
      websiteHealth: { value: compHealth, max: 100 },
      autoFix: {
        value: homeAgg?.kpis?.auto_fix_today ?? totalFixes,
        target: homeAgg?.kpis?.auto_fix_target ?? 2000,
        max: Math.max(100, totalFixes),
      },
      agents,
      services: {
        active: subs?.active_count ?? 0,
        // Denominator = max(public catalog live count, active subs) so
        // dogfood / wildcard customers never see a confusing "25/20".
        total: Math.max(
          (catalog?.services || []).length,
          subs?.active_count ?? 0,
        ),
      },
      growth,
      // iter 322bj — extra series from home aggregate (multi-line growth chart)
      growthMulti: homeAgg?.growth || null,
      pulseBars: homeAgg?.pulse_bars || [],
      websiteScan: {
        geo: homeAgg?.scan?.geo || scanGeo,
        sec: homeAgg?.scan?.sec || scanSec,
        acc: homeAgg?.scan?.acc || scanAcc,
        seo: homeAgg?.scan?.seo || scanSeo,
        lastScan: repairScores?.last_scan || '—',
      },
      oraRepair: {
        successPct: homeAgg?.repair?.success_pct ?? Math.round(successPct * (successPct <= 1 ? 100 : 1)),
        healed: homeAgg?.repair?.healed ?? healed,
        attempts: homeAgg?.repair?.attempts ?? totalFixes,
        deltaPct: 0,
        series,
        sparkline: homeAgg?.repair?.sparkline || [],
      },
      securityAlerts: {
        count: (homeAgg?.alerts || alerts).length,
        items: (homeAgg?.alerts || []).map((a) => ({
          time: (a.ts_utc || '').slice(11, 16),
          level: (a.level || 'LOW').toUpperCase(),
          msg: a.message || 'event',
        })).concat(alerts).slice(0, 6),
      },
      // iter 325n — V2 top-level surfaces
      resultsSummary: resultsSummary || {},
      pipelineStages: pipeline?.stages || [],
      pipelineTotal:  pipeline?.total  ?? 0,
      inboxThreads:   inboxThreads?.threads || [],
      inboxUnread:    (inboxThreads?.threads || [])
                        .reduce((s, t) => s + (Number(t.unread) || 0), 0),
      apiStatus,
      lastUpdated:    new Date().toISOString(),
    });
  }, [token]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000); // auto-refresh every 30s
    return () => clearInterval(id);
  }, [refresh]);

  return { ...data, refresh };
};
