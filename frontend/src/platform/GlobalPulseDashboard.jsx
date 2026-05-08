/**
 * AUREM Global Pulse Dashboard — Economic Intelligence Hub
 * Real-time news, Bank of Canada data, market indicators, learning deltas
 * COMPLIANCE: Economic data for business context only. Not investment advice.
 */
import React, { useState, useEffect, useCallback , useMemo } from 'react';
import {
  Globe, TrendingUp, TrendingDown, Activity, RefreshCw, Zap,
  AlertTriangle, ExternalLink, Brain, DollarSign, Percent, Calendar,
  Shield, Info,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SENTIMENT_COLORS = {
  stable: { bg: 'rgba(34,197,94,0.08)', color: '#22C55E', label: 'STABLE' },
  neutral: { bg: 'rgba(59,130,246,0.08)', color: '#3B82F6', label: 'NEUTRAL' },
  cautious: { bg: 'rgba(245,158,11,0.08)', color: '#F59E0B', label: 'CAUTIOUS' },
  elevated_risk: { bg: 'rgba(239,68,68,0.08)', color: '#EF4444', label: 'ELEVATED RISK' },
};

export default function GlobalPulseDashboard({ token }) {
  const [pulse, setPulse] = useState(null);
  const [deltas, setDeltas] = useState([]);
  const [bocData, setBocData] = useState(null);
  const [geoContext, setGeoContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchPulse = useCallback(async () => {
    try {
      const [pRes, dRes, bRes, gRes] = await Promise.all([
        fetch(`${API_URL}/api/global-pulse/latest`, { headers }),
        fetch(`${API_URL}/api/global-pulse/deltas`, { headers }),
        fetch(`${API_URL}/api/global-pulse/boc`, { headers }),
        fetch(`${API_URL}/api/global-pulse/geo-context`, { headers }),
      ]);
      if (pRes.ok) setPulse(await pRes.json());
      if (dRes.ok) { const d = await dRes.json(); setDeltas(d.deltas || []); }
      if (bRes.ok) setBocData(await bRes.json());
      if (gRes.ok) setGeoContext(await gRes.json());
    } catch (e) { console.error('Pulse fetch:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { if (token) fetchPulse(); }, [token, fetchPulse]);

  const triggerScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API_URL}/api/global-pulse/scan`, { method: 'POST', headers });
      if (res.ok) { setPulse(await res.json()); }
    } catch (e) { console.error('Scan error:', e); }
    setScanning(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="global-pulse-loading">
        <RefreshCw className="w-6 h-6 animate-spin text-[#C9A84C]" />
      </div>
    );
  }

  const market = pulse?.market || {};
  const news = pulse?.news_items || [];
  const topKw = pulse?.top_keywords || [];
  const sentimentStyle = SENTIMENT_COLORS[market.market_sentiment] || SENTIMENT_COLORS.neutral;
  const isBocCached = market.boc_is_cached || bocData?.is_cached;
  const cachedDate = isBocCached ? (bocData?.fetched_at || market.fetched_at || '').slice(0, 10) : null;

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-8" data-testid="global-pulse-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }}
              data-testid="global-pulse-title">
              Global Pulse
            </h2>
            <span className="px-2.5 py-1 rounded-full text-[8px] font-bold tracking-wider" data-testid="data-source-badge" style={{
              background: 'rgba(201,168,76,0.08)', color: '#C9A84C', border: '1px solid rgba(201,168,76,0.15)',
            }}>
              Powered by Bank of Canada &middot; Alpha Vantage &middot; Public Data
            </span>
          </div>
          <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
            Economic Intelligence Hub {geoContext ? `| ${geoContext.label}` : ''}
          </p>
        </div>
        <button
          onClick={triggerScan}
          disabled={scanning}
          data-testid="global-pulse-scan-btn"
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[10px] font-bold tracking-wider transition-all hover:scale-[1.02] disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #C9A84C, #A08636)', color: '#050507' }}
        >
          {scanning ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Globe className="w-3 h-3" />}
          {scanning ? 'SCANNING...' : 'SCAN NOW'}
        </button>
      </div>

      {/* Bank of Canada Primary Data */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3" data-testid="boc-cards">
        {/* CAD/USD */}
        <div className="aurem-glass-card p-4" data-testid="cad-usd-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>CAD/USD</span>
            <DollarSign className="w-3 h-3" style={{ color: '#C9A84C' }} />
          </div>
          <div className="text-2xl font-black" style={{ color: '#C9A84C' }}>
            {market.cad_usd || bocData?.cad_usd_rate || '--'}
          </div>
          {market.cad_usd_change_pct != null && (
            <div className="flex items-center gap-1 mt-1">
              {market.cad_usd_change_pct > 0 ? (
                <TrendingUp className="w-3 h-3 text-[#22C55E]" />
              ) : market.cad_usd_change_pct < 0 ? (
                <TrendingDown className="w-3 h-3 text-[#EF4444]" />
              ) : null}
              <span className={`text-[10px] font-bold ${market.cad_usd_change_pct >= 0 ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
                {market.cad_usd_change_pct >= 0 ? '+' : ''}{market.cad_usd_change_pct?.toFixed(3)}%
              </span>
            </div>
          )}
          {isBocCached && cachedDate && (
            <span className="text-[8px] mt-1 block" style={{ color: 'var(--aurem-body-secondary)' }}>As of {cachedDate}</span>
          )}
        </div>

        {/* BoC Policy Rate */}
        <div className="aurem-glass-card p-4" data-testid="boc-rate-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>BoC RATE</span>
            <Percent className="w-3 h-3" style={{ color: '#C9A84C' }} />
          </div>
          <div className="text-2xl font-black" style={{ color: 'var(--aurem-heading)' }}>
            {market.policy_rate ?? bocData?.policy_rate ?? '--'}%
          </div>
          <span className="text-[8px]" style={{ color: 'var(--aurem-body-secondary)' }}>
            Overnight target {market.bank_rate ? `| Bank ${market.bank_rate}%` : ''}
          </span>
        </div>

        {/* VIX */}
        <div className="aurem-glass-card p-4" data-testid="vix-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>VIX INDEX</span>
            {market.vix_alert && <AlertTriangle className="w-3 h-3 text-[#EF4444]" />}
          </div>
          <div className="text-2xl font-black" style={{ color: market.vix_alert ? '#EF4444' : 'var(--aurem-heading)' }}>
            {market.vix_estimate || '--'}
          </div>
          <span className="px-2 py-0.5 rounded-full text-[8px] font-bold mt-1 inline-block" style={{
            background: sentimentStyle.bg, color: sentimentStyle.color,
          }} data-testid="market-sentiment-badge">
            {sentimentStyle.label}
          </span>
        </div>

        {/* Next BoC Decision */}
        <div className="aurem-glass-card p-4" data-testid="next-boc-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>NEXT BoC</span>
            <Calendar className="w-3 h-3" style={{ color: '#C9A84C' }} />
          </div>
          <div className="text-lg font-black" style={{ color: 'var(--aurem-heading)' }}>
            {market.next_boc_decision || bocData?.next_boc_decision || '--'}
          </div>
          <span className="text-[8px]" style={{ color: 'var(--aurem-body-secondary)' }}>Rate decision</span>
        </div>

        {/* News Count */}
        <div className="aurem-glass-card p-4" data-testid="news-count-card">
          <div className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--aurem-body-secondary)' }}>NEWS ITEMS</div>
          <div className="text-2xl font-black" style={{ color: '#C9A84C' }}>
            {pulse?.news_count || 0}
          </div>
          <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Industry-relevant</span>
        </div>
      </div>

      {/* Learning Score (Oracle Accuracy) */}
      {deltas.length > 0 && (
        <div className="aurem-glass-card p-4 flex items-center gap-4" data-testid="learning-accuracy-bar">
          <Brain className="w-5 h-5 text-[#C9A84C] flex-shrink-0" />
          <div>
            <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>RECURSIVE BRAIN ACCURACY</span>
            <div className="text-lg font-black" style={{ color: '#C9A84C' }}>
              {Math.round(deltas[0].new_weight * 100)}%
            </div>
          </div>
          <div className="flex-1">
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(201,168,76,0.1)' }}>
              <div className="h-full rounded-full transition-all" style={{
                width: `${Math.round(deltas[0].new_weight * 100)}%`,
                background: 'linear-gradient(90deg, #C9A84C, #A08636)',
              }} />
            </div>
          </div>
        </div>
      )}

      {/* Trending Keywords */}
      {topKw.length > 0 && (
        <div className="aurem-glass-card p-5" data-testid="trending-keywords">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>
            <Zap className="w-4 h-4 inline mr-1.5 text-[#C9A84C]" /> Trending Industry Topics
          </h3>
          <div className="flex flex-wrap gap-2">
            {topKw.map((kw, i) => (
              <span key={i} className="px-3 py-1.5 rounded-full text-[10px] font-bold" style={{
                background: i === 0 ? 'rgba(201,168,76,0.12)' : 'rgba(255,255,255,0.05)',
                color: i === 0 ? '#C9A84C' : 'var(--aurem-heading)',
                border: `1px solid ${i === 0 ? 'rgba(201,168,76,0.2)' : 'rgba(255,255,255,0.08)'}`,
              }}>
                {kw.keyword} ({kw.count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* News Feed */}
      {news.length > 0 && (
        <div className="aurem-glass-card p-5" data-testid="news-feed">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>
            <Activity className="w-4 h-4 inline mr-1.5 text-[#3B82F6]" /> Intelligence Feed
          </h3>
          <div className="space-y-3">
            {news.slice(0, 8).map((item, i) => (
              <div key={i} className="flex items-start gap-3 py-2 px-3 rounded-lg transition-all hover:bg-white/5" style={{
                borderBottom: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div className="w-6 h-6 rounded-md flex-shrink-0 flex items-center justify-center mt-0.5" style={{
                  background: 'rgba(201,168,76,0.08)',
                }}>
                  <Globe className="w-3 h-3 text-[#C9A84C]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-xs font-medium leading-snug truncate" style={{ color: 'var(--aurem-heading)' }}>
                      {item.title}
                    </h4>
                    {item.link && (
                      <a href={item.link} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
                        <ExternalLink className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                      </a>
                    )}
                  </div>
                  <p className="text-[10px] mt-0.5 line-clamp-2" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {item.summary?.substring(0, 120)}...
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[8px] font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>{item.source}</span>
                    <div className="flex gap-1">
                      {item.keywords?.slice(0, 3).map((kw, ki) => (
                        <span key={ki} className="px-1.5 py-0.5 rounded text-[7px] font-bold" style={{
                          background: 'rgba(201,168,76,0.06)', color: '#C9A84C',
                        }}>{kw}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning Deltas (Recursive Brain) */}
      {deltas.length > 0 && (
        <div className="aurem-glass-card p-5" data-testid="learning-deltas">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>
            <Brain className="w-4 h-4 inline mr-1.5 text-[#C9A84C]" /> Recursive Brain — Delta History
          </h3>
          <div className="space-y-2">
            {deltas.slice(0, 7).map((d, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg" style={{
                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)',
              }}>
                <span className="text-[10px] font-mono" style={{ color: 'var(--aurem-heading)' }}>{d.date}</span>
                <div className="flex items-center gap-3">
                  <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {d.actual_sentiment}
                  </span>
                  <span className={`text-[10px] font-bold ${d.accuracy_delta >= 0 ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
                    {d.accuracy_delta >= 0 ? '+' : ''}{(d.accuracy_delta * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] font-mono" style={{ color: '#C9A84C' }}>
                    {(d.new_weight * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Compliance Disclaimer */}
      <div className="aurem-glass-card p-4 flex items-start gap-3" data-testid="compliance-disclaimer"
        style={{ borderColor: 'rgba(201,168,76,0.15)' }}>
        <Shield className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#C9A84C' }} />
        <div>
          <p className="text-[10px] font-bold tracking-wider" style={{ color: '#C9A84C' }}>
            COMPLIANCE NOTICE
          </p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Economic data for business context only. Not investment advice. Data sourced from Bank of Canada Valet API (public, free) and Alpha Vantage (free tier). All indicators are historical data points, not recommendations.
          </p>
          <a href="/legal/economic-intelligence" target="_blank" rel="noopener noreferrer"
            className="text-[9px] mt-1.5 inline-block hover:underline" style={{ color: '#C9A84C' }}
            data-testid="compliance-full-link">
            Read full Economic Intelligence Disclaimer &rarr;
          </a>
        </div>
      </div>
    </div>
  );
}
