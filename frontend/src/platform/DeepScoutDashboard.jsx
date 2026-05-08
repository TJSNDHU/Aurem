import React, { useState, useCallback } from 'react';
import { Search, Layers, Target, CheckCircle, XCircle, Loader2, ArrowRight, RefreshCw } from 'lucide-react';
import { motion, PageTransition, MotionCard, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

export default function DeepScoutDashboard({ token }) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const [searchRes, statsRes] = await Promise.all([
        fetch(`${API}/api/deep-scout/search`, {
          method: 'POST', headers,
          body: JSON.stringify({ query, tenant_id: 'aurem_platform' }),
        }),
        fetch(`${API}/api/deep-scout/stats`, { headers }),
      ]);
      if (searchRes.ok) setResult(await searchRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (e) { console.error('Deep scout:', e); }
    setLoading(false);
  };

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="deep-scout-dashboard">
      <PageTransition>
        <div className="mb-6">
          <h1 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)' }}>Deep Scout</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
            Multi-step iterative search with gap analysis. Auto-triggers for complex queries ({'>'}10 words).
          </p>
        </div>

        {/* Search Input */}
        <div className="aurem-glass-card p-4 mb-6">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--aurem-body-secondary)' }} />
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Enter a complex query (>10 words for multi-step analysis)..."
                className="w-full pl-10 pr-4 py-3 rounded-lg text-sm focus:outline-none"
                style={{ background: 'rgba(255,107,0,0.05)', color: 'var(--aurem-heading)', border: '1px solid rgba(61,58,57,0.3)' }}
                data-testid="deep-scout-input"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              className="px-5 py-3 rounded-lg text-xs font-bold tracking-wider transition-all hover:scale-[1.02] disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)', color: '#0A0A00' }}
              data-testid="deep-scout-search-btn"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
            </button>
          </div>
          <div className="text-[10px] mt-2" style={{ color: 'var(--aurem-body-secondary)' }}>
            Word count: {query.split(/\s+/).filter(Boolean).length} {query.split(/\s+/).filter(Boolean).length > 10 ? '(multi-step active)' : '(simple mode)'}
          </div>
        </div>

        {/* Results */}
        {result && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            {result.skipped ? (
              <div className="aurem-glass-card p-4">
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4" style={{ color: '#EAB308' }} />
                  <span className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Simple Query Mode</span>
                </div>
                <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                  Query has {'<'}10 words — deep scout skipped. Use a more detailed query for iterative search.
                </p>
              </div>
            ) : (
              <>
                {/* Summary */}
                <div className="aurem-glass-card p-4" data-testid="deep-scout-result">
                  <div className="flex items-center gap-3 mb-3">
                    <Layers className="w-5 h-5" style={{ color: '#FF6B00' }} />
                    <div>
                      <div className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>
                        {result.steps_taken} step{result.steps_taken !== 1 ? 's' : ''} completed
                      </div>
                      <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {result.total_findings} findings | {result.final_coverage}% coverage
                      </div>
                    </div>
                  </div>
                  {/* Coverage bar */}
                  <div className="relative h-2 rounded-full overflow-hidden mb-1" style={{ background: 'rgba(61,58,57,0.15)' }}>
                    <motion.div
                      className="absolute left-0 top-0 h-full rounded-full"
                      style={{ background: result.final_coverage >= 80 ? '#22C55E' : result.final_coverage >= 50 ? '#EAB308' : '#EF4444' }}
                      initial={{ width: 0 }}
                      animate={{ width: `${result.final_coverage}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                    />
                  </div>
                  <div className="text-[9px] text-right" style={{ color: 'var(--aurem-body-secondary)' }}>{result.final_coverage}% coverage</div>
                </div>

                {/* Step-by-step breakdown */}
                {(result.steps || []).map((step, i) => (
                  <motion.div key={i} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 * i }}
                    className="aurem-glass-card p-4" data-testid={`deep-scout-step-${i}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold" style={{
                        background: step.is_complete ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
                        color: step.is_complete ? '#22C55E' : '#EAB308',
                      }}>{step.step}</div>
                      <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Step {step.step}</span>
                      {step.is_complete && <CheckCircle className="w-3 h-3 ml-auto" style={{ color: '#22C55E' }} />}
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {step.findings?.length || 0} findings | {step.coverage_pct}%
                      </span>
                    </div>
                    {step.missing_keywords?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        <span className="text-[9px]" style={{ color: '#EF4444' }}>Missing:</span>
                        {step.missing_keywords.map((kw, j) => (
                          <span key={j} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444' }}>{kw}</span>
                        ))}
                      </div>
                    )}
                    {step.covered_keywords?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        <span className="text-[9px]" style={{ color: '#22C55E' }}>Covered:</span>
                        {step.covered_keywords.map((kw, j) => (
                          <span key={j} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(34,197,94,0.1)', color: '#22C55E' }}>{kw}</span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))}
              </>
            )}
          </motion.div>
        )}

        {/* Stats */}
        {stats && stats.total_searches > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
            className="aurem-glass-card p-4 mt-6" data-testid="deep-scout-stats">
            <div className="text-xs font-bold mb-2" style={{ color: 'var(--aurem-heading)' }}>Aggregate Stats</div>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-lg font-bold" style={{ color: '#3B82F6' }}>{stats.total_searches}</div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Total</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold" style={{ color: '#F97316' }}>{stats.avg_steps}</div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Avg Steps</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold" style={{ color: '#22C55E' }}>{stats.avg_coverage}%</div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Avg Coverage</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold" style={{ color: '#8B5CF6' }}>{stats.avg_findings}</div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Avg Findings</div>
              </div>
            </div>
          </motion.div>
        )}
      </PageTransition>
    </div>
  );
}
