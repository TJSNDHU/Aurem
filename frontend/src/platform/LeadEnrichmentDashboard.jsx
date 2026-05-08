import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Users, Zap, TrendingUp, Target, MessageSquare, RefreshCw, Loader2, CheckCircle, AlertTriangle, Building2 } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, PageTransition, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

export default function LeadEnrichmentDashboard({ token }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [result, setResult] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/enrichment/stats`, { headers });
      if (res.ok) setStats(await res.json());
    } catch (e) { console.error('Enrichment stats:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const handleEnrichAll = async () => {
    setEnriching(true);
    try {
      const res = await fetch(`${API}/api/enrichment/enrich-all`, {
        method: 'POST', headers, body: JSON.stringify({ tenant_id: 'aurem_platform' }),
      });
      if (res.ok) setResult(await res.json());
      await fetchStats();
    } catch (e) { console.error('Enrich error:', e); }
    setEnriching(false);
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
    </div>
  );

  const cards = stats ? [
    { label: 'Total Leads', value: stats.total_leads || 0, icon: Users, color: '#3B82F6' },
    { label: 'Enriched', value: stats.enriched_leads || 0, icon: CheckCircle, color: '#22C55E' },
    { label: 'Enrichment Rate', value: `${stats.enrichment_rate || 0}%`, icon: TrendingUp, color: '#F97316' },
    { label: 'Decision Makers', value: stats.decision_makers || 0, icon: Target, color: '#8B5CF6' },
  ] : [];

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="lead-enrichment-dashboard">
      <PageTransition>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)' }}>Lead Enrichment Agent</h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
              Auto-enrich leads with company intel, decision maker flags, social scores, and ABM hooks
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleEnrichAll}
              disabled={enriching}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold tracking-wider transition-all hover:scale-[1.02] disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)', color: '#0A0A00' }}
              data-testid="enrich-all-btn"
            >
              {enriching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              Enrich All New
            </button>
            <button onClick={fetchStats} className="p-2 rounded-lg hover:bg-white/10 transition-colors" data-testid="refresh-enrichment">
              <RefreshCw className="w-4 h-4" style={{ color: 'var(--aurem-body-secondary)' }} />
            </button>
          </div>
        </div>

        <StaggerGrid className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {cards.map((card, i) => (
            <MotionCard key={card.label} variant={cardVariant} className="aurem-glass-card p-4" data-testid={`enrichment-card-${card.label.toLowerCase().replace(/\s/g,'-')}`}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${card.color}15` }}>
                  <card.icon className="w-4 h-4" style={{ color: card.color }} />
                </div>
                <span className="text-lg font-bold" style={{ color: card.color }}>{card.value}</span>
              </div>
              <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{card.label}</div>
            </MotionCard>
          ))}
        </StaggerGrid>

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="aurem-glass-card p-4 mb-6" data-testid="enrichment-result"
          >
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="w-4 h-4" style={{ color: '#22C55E' }} />
              <span className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Enrichment Complete</span>
            </div>
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
              {result.enriched || 0} leads enriched out of {result.total_checked || 0} checked.
            </p>
          </motion.div>
        )}

        <div className="aurem-glass-card p-5">
          <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--aurem-heading)' }}>How It Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { icon: Building2, title: 'Company Intelligence', desc: 'Estimates company size from domain and name signals. Enterprise, mid-market, or small.' },
              { icon: Target, title: 'Decision Maker Detection', desc: 'Flags CEOs, CTOs, Founders, VPs, Directors from title and email patterns.' },
              { icon: MessageSquare, title: 'ABM Hook Generation', desc: 'Creates personalized outreach messages based on enriched company data and role.' },
            ].map((item, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 * i }}
                className="p-4 rounded-lg" style={{ background: 'rgba(255,107,0,0.04)' }}>
                <item.icon className="w-5 h-5 mb-2" style={{ color: '#FF6B00' }} />
                <div className="text-xs font-bold mb-1" style={{ color: 'var(--aurem-heading)' }}>{item.title}</div>
                <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{item.desc}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </PageTransition>
    </div>
  );
}
