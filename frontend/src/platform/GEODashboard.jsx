import React, { useState, useEffect, useCallback , useMemo } from 'react';
import {
  Brain, Search, Eye, TrendingUp, Target, Zap, AlertCircle,
  CheckCircle, ChevronRight, RefreshCw, Activity, Globe,
  Loader2, Info, ArrowRight, BarChart3, Shield, Star
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const GRADE_COLORS = {
  'A+': '#10b981', 'A': '#10b981', 'B+': '#FF6B00', 'B': '#3b82f6',
  'C+': '#f59e0b', 'C': '#f59e0b', 'D': '#ef4444', 'F': '#ef4444',
};

export default function GEODashboard({ token }) {
  const [score, setScore] = useState(null);
  const [liveResult, setLiveResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [query, setQuery] = useState('');
  const [brandName, setBrandName] = useState('');
  const [showDetails, setShowDetails] = useState(null);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchScore = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, hRes] = await Promise.all([
        fetch(`${API}/api/geo/score`, { headers }),
        fetch(`${API}/api/geo/history?limit=5`, { headers }),
      ]);
      if (sRes.ok) setScore(await sRes.json());
      if (hRes.ok) setHistory((await hRes.json()).checks || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchScore(); }, [fetchScore]);

  const runLiveCheck = async () => {
    setChecking(true);
    try {
      const res = await fetch(`${API}/api/geo/live-check`, {
        method: 'POST', headers,
        body: JSON.stringify({
          query: query || null,
          brand_name: brandName || null,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setLiveResult(data);
        fetchScore();
      }
    } catch (e) { console.error(e); }
    setChecking(false);
  };

  if (loading) return (
    <div className="flex items-center justify-center p-12">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--aurem-text-secondary)' }} />
    </div>
  );

  if (!score) return (
    <div className="flex flex-col items-center justify-center p-16 text-center" data-testid="geo-empty-state">
      <Globe size={40} style={{ color: 'var(--aurem-text-secondary)', opacity: 0.3 }} />
      <h2 className="text-lg font-bold mt-4" style={{ color: 'var(--aurem-text)' }}>No data yet</h2>
      <p className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>GEO Readiness data will appear here once available.</p>
      <button onClick={fetchScore} className="mt-4 flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold" style={{ background: 'rgba(128,128,128,0.08)', color: 'var(--aurem-text-secondary)' }} data-testid="geo-retry-btn">
        <RefreshCw size={12} /> Retry
      </button>
    </div>
  );

  const gradeColor = GRADE_COLORS[score?.grade] || '#888';
  const breakdown = score?.breakdown || {};

  return (
    <div className="space-y-6" data-testid="geo-dashboard">
      {/* Hero Score */}
      <div className="aurem-glass-card p-6 rounded-2xl" style={{ border: `1px solid ${gradeColor}20` }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-20 h-20 rounded-2xl flex items-center justify-center" style={{ background: `${gradeColor}12` }}>
                <span className="text-3xl font-black" style={{ color: gradeColor }}>{score?.score || 0}</span>
              </div>
              <div className="absolute -top-1 -right-1 px-2 py-0.5 rounded-full text-[10px] font-black text-white" style={{ background: gradeColor }}>
                {score?.grade || '—'}
              </div>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: 'var(--aurem-text)' }}>GEO Readiness Score</h1>
              <p className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>
                Based on structured data analysis and content optimization — not live AI rankings
              </p>
              <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>
                Calculated: {score?.calculated_at?.slice(0, 16).replace('T', ' ')}
              </p>
            </div>
          </div>
          <button onClick={fetchScore} className="p-2 rounded-xl" style={{ background: 'rgba(128,128,128,0.06)' }} data-testid="refresh-geo">
            <RefreshCw size={14} style={{ color: 'var(--aurem-text-secondary)' }} />
          </button>
        </div>

        {/* Score Bar */}
        <div className="mt-4">
          <div className="h-3 rounded-full overflow-hidden" style={{ background: 'rgba(128,128,128,0.1)' }}>
            <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${score?.score || 0}%`, background: `linear-gradient(90deg, ${gradeColor}, ${gradeColor}88)` }} />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[9px]" style={{ color: 'var(--aurem-text-secondary)' }}>0</span>
            <span className="text-[9px]" style={{ color: 'var(--aurem-text-secondary)' }}>Target: 85+</span>
            <span className="text-[9px]" style={{ color: 'var(--aurem-text-secondary)' }}>100</span>
          </div>
        </div>
      </div>

      {/* Breakdown Cards */}
      <div className="grid grid-cols-5 gap-3">
        {Object.entries(breakdown).map(([key, data]) => {
          const icons = { product_quality: Star, ucp_readiness: Globe, schema_density: Shield, citation_signals: TrendingUp, content_freshness: Activity };
          const Icon = icons[key] || BarChart3;
          const pct = data.max > 0 ? Math.round((data.score / data.max) * 100) : 0;
          const clr = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';

          return (
            <div key={key} className="aurem-glass-card p-4 rounded-2xl cursor-pointer hover:scale-[1.02] transition-all"
              onClick={() => setShowDetails(showDetails === key ? null : key)} data-testid={`geo-${key}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} style={{ color: clr }} />
                <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>
                  {key.replace(/_/g, ' ')}
                </span>
                <Info size={10} style={{ color: 'var(--aurem-text-secondary)', opacity: 0.5 }} />
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-xl font-bold" style={{ color: 'var(--aurem-text)' }}>{data.score}</span>
                <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>/{data.max}</span>
              </div>
              <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(128,128,128,0.1)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: clr }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Detail Expansion */}
      {showDetails && breakdown[showDetails] && (
        <div className="aurem-glass-card p-5 rounded-2xl" style={{ border: '1px solid rgba(212,175,55,0.15)' }} data-testid="geo-detail-panel">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold uppercase" style={{ color: '#D4AF37' }}>{showDetails.replace(/_/g, ' ')} — Details</h3>
            <button onClick={() => setShowDetails(null)}><ChevronRight size={14} className="rotate-90" style={{ color: 'var(--aurem-text-secondary)' }} /></button>
          </div>
          <p className="text-xs mb-3" style={{ color: 'var(--aurem-text)' }}>{breakdown[showDetails].details}</p>
          {breakdown[showDetails].recommendations?.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[10px] font-bold uppercase" style={{ color: '#f59e0b' }}>Recommendations:</span>
              {breakdown[showDetails].recommendations.map((r, i) => (
                <div key={i} className="flex items-start gap-2">
                  <ArrowRight size={11} className="shrink-0 mt-0.5" style={{ color: '#f59e0b' }} />
                  <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Top Recommendations */}
      {score?.recommendations?.length > 0 && (
        <div className="aurem-glass-card p-5 rounded-2xl">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-text)' }}>Top Recommendations to Boost GEO Readiness</h3>
          <div className="space-y-2">
            {score.recommendations.map((r, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'rgba(245,158,11,0.04)' }}>
                <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white" style={{ background: '#f59e0b' }}>{i + 1}</span>
                <span className="text-xs flex-1" style={{ color: 'var(--aurem-text)' }}>{r.text}</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: 'rgba(245,158,11,0.08)', color: '#f59e0b' }}>+{r.impact}pts</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live AI Check */}
      <div className="aurem-glass-card p-6 rounded-2xl" style={{ border: '1px solid rgba(139,91,214,0.15)' }}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(139,91,214,0.12)' }}>
            <Brain size={18} style={{ color: '#8B5CF6' }} />
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>Live AI Check</h2>
            <p className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>
              Query GPT-4o to see if your brand is recommended in real-time
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Brand Name</label>
            <input value={brandName} onChange={e => setBrandName(e.target.value)} placeholder="Your Brand" className="w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#8B5CF6]" style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="geo-brand-input" />
          </div>
          <div>
            <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Test Query</label>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Best products in your category?" className="w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#8B5CF6]" style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="geo-query-input" />
          </div>
        </div>

        <button onClick={runLiveCheck} disabled={checking}
          className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-all"
          style={{ background: 'linear-gradient(135deg, #8B5CF6, #6D28D9)' }} data-testid="run-live-check-btn">
          {checking ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          {checking ? 'Querying GPT-4o...' : 'Run Live AI Check'}
        </button>

        {/* Live Check Result */}
        {liveResult && !liveResult.error && (
          <div className="mt-4 p-4 rounded-xl space-y-3" style={{ background: liveResult.mentioned ? 'rgba(16,185,129,0.04)' : 'rgba(245,158,11,0.04)', border: `1px solid ${liveResult.mentioned ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)'}` }} data-testid="live-check-result">
            <div className="flex items-center gap-3">
              {liveResult.mentioned ? (
                <CheckCircle size={20} style={{ color: '#10b981' }} />
              ) : (
                <AlertCircle size={20} style={{ color: '#f59e0b' }} />
              )}
              <div>
                <span className="text-sm font-bold" style={{ color: liveResult.mentioned ? '#10b981' : '#f59e0b' }}>
                  {liveResult.mentioned ? 'Brand Mentioned!' : 'Not Mentioned Yet'}
                </span>
                <span className="ml-2 px-2 py-0.5 rounded text-[10px] font-bold" style={{ background: `${liveResult.mentioned ? '#10b981' : '#f59e0b'}15`, color: liveResult.mentioned ? '#10b981' : '#f59e0b' }}>
                  Score: {liveResult.recommendation_score}/100
                </span>
              </div>
            </div>

            <p className="text-xs" style={{ color: 'var(--aurem-text)' }}>{liveResult.insight}</p>

            {liveResult.citations?.length > 0 && (
              <div>
                <span className="text-[10px] font-bold uppercase" style={{ color: '#10b981' }}>Brand Citations:</span>
                {liveResult.citations.map((c, i) => (
                  <p key={i} className="text-xs mt-1 pl-3" style={{ color: 'var(--aurem-text-secondary)', borderLeft: '2px solid #10b981' }}>{c}</p>
                ))}
              </div>
            )}

            {liveResult.competitor_snippets?.length > 0 && (
              <div>
                <span className="text-[10px] font-bold uppercase" style={{ color: '#ef4444' }}>Competitors Mentioned Instead:</span>
                {liveResult.competitor_snippets.map((c, i) => (
                  <p key={i} className="text-xs mt-1 pl-3 truncate" style={{ color: 'var(--aurem-text-secondary)', borderLeft: '2px solid #ef4444' }}>{c}</p>
                ))}
              </div>
            )}

            <div className="p-3 rounded-lg" style={{ background: 'rgba(128,128,128,0.04)' }}>
              <span className="text-[10px] font-bold uppercase" style={{ color: 'var(--aurem-text-secondary)' }}>AI Response Preview:</span>
              <p className="text-xs mt-1" style={{ color: 'var(--aurem-text)' }}>{liveResult.ai_response_preview}</p>
            </div>
          </div>
        )}
      </div>

      {/* Check History */}
      {history.length > 0 && (
        <div className="aurem-glass-card p-5 rounded-2xl">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-text)' }}>Previous AI Checks</h3>
          <div className="space-y-2">
            {history.map((h, i) => (
              <div key={h.id || i} className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'rgba(128,128,128,0.03)' }}>
                {h.mentioned ? <CheckCircle size={13} style={{ color: '#10b981' }} /> : <AlertCircle size={13} style={{ color: '#f59e0b' }} />}
                <span className="text-xs font-medium flex-1 truncate" style={{ color: 'var(--aurem-text)' }}>"{h.query}"</span>
                <span className="text-[10px]" style={{ color: h.mentioned ? '#10b981' : '#f59e0b' }}>{h.mentioned ? 'Mentioned' : 'Not found'}</span>
                <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{h.checked_at?.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
