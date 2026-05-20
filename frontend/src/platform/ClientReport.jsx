import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Globe, Shield, Zap, Eye, Search, CheckCircle, AlertTriangle, Clock, TrendingUp, ArrowRight, Printer } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const gold = '#D4AF37';
const goldGrad = 'linear-gradient(135deg, #D4AF37, #B8860B)';

const ScoreDonut = ({ score, label, size = 100 }) => {
  const color = score >= 90 ? '#4ade80' : score >= 70 ? '#facc15' : '#ef4444';
  const circumference = 2 * Math.PI * 38;
  const offset = circumference - (score / 100) * circumference;
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 100 100" className="transform -rotate-90">
        <circle cx="50" cy="50" r="38" fill="none" stroke="#1a1a2e" strokeWidth="8" />
        <circle cx="50" cy="50" r="38" fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" className="transition-all duration-1000" />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-2xl font-bold" style={{ color }}>{score}</span>
      </div>
      <span className="text-[11px] text-[#9ca3af] tracking-wider uppercase">{label}</span>
    </div>
  );
};

const SeverityBadge = ({ severity }) => {
  const c = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    medium: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    low: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  };
  return <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${c[severity] || c.medium}`}>{severity}</span>;
};

const ClientReport = () => {
  const { tenantId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const r = await fetch(`${API}/api/intelligence/report/${tenantId}`);
        if (!r.ok) throw new Error(r.status === 404 ? 'Report not found' : 'Failed to load report');
        setReport(await r.json());
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [tenantId]);

  if (loading) return (
    <div className="min-h-screen bg-[#050507] flex items-center justify-center">
      <div className="animate-pulse text-[#D4AF37] text-sm tracking-widest">Loading report…</div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-[#050507] flex items-center justify-center">
      <div className="text-center">
        <div className="text-red-400 text-sm mb-2">{error}</div>
        <a href="/" className="text-[#D4AF37] text-xs hover:underline">Back to AUREM</a>
      </div>
    </div>
  );

  const d = report;
  const overall = d.overall_score || 0;
  const overallColor = overall >= 90 ? '#4ade80' : overall >= 70 ? '#facc15' : '#ef4444';
  const scoreEntries = Object.entries(d.scores || {}).filter(([, v]) => typeof v === 'number' && v > 0);
  const issues = d.issues || [];
  const fixes = d.auto_fixed || [];
  const needsAttention = issues.filter(i => !i.fixable);
  const fixable = issues.filter(i => i.fixable);

  return (
    <div className="min-h-screen bg-[#050507] text-white" data-testid="client-report-page">
      {/* Print styles */}
      <style>{`
        @media print {
          body { background: white !important; color: black !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .no-print { display: none !important; }
          .print-break { page-break-before: always; }
        }
      `}</style>

      {/* ═══ HEADER ═══ */}
      <header className="border-b border-[#D4AF37]/10" style={{ background: 'rgba(5,5,7,0.95)' }}>
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: goldGrad }}>
              <Shield className="size-4 text-[#050507]" />
            </div>
            <div>
              <span className="text-sm tracking-[0.2em] font-light" style={{ color: gold }}>AUREM</span>
              <span className="text-[9px] text-[#9ca3af] block -mt-0.5 tracking-wider">WEBSITE INTELLIGENCE REPORT</span>
            </div>
          </div>
          <button
            onClick={() => window.print()}
            className="no-print flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] text-[#9ca3af] border border-[#1a1a2e] hover:border-[#D4AF37]/30 hover:text-[#D4AF37] transition-all"
            aria-label="Print report"
            data-testid="print-report-btn"
          >
            <Printer className="size-3" /> Print / PDF
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {/* ═══ CLIENT IDENTITY ═══ */}
        <section className="text-center space-y-3" data-testid="report-header">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-wide">{d.business_name}</h1>
          <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-sm text-[#D4AF37] hover:underline">{d.url}</a>
          {d.industry && <p className="text-xs text-[#9ca3af] tracking-wider uppercase">{d.industry}</p>}
          <div className="flex items-center justify-center gap-2 text-[10px] text-[#9ca3af]">
            <Clock className="size-3" />
            <span>Scanned {d.scanned_at ? new Date(d.scanned_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'N/A'}</span>
            {d.scan_duration_seconds > 0 && <span>({d.scan_duration_seconds}s)</span>}
          </div>
        </section>

        {/* ═══ OVERALL SCORE ═══ */}
        <section className="flex flex-col items-center py-6" data-testid="overall-score">
          <div className="relative">
            <svg width="160" height="160" viewBox="0 0 100 100" className="transform -rotate-90">
              <circle cx="50" cy="50" r="42" fill="none" stroke="#1a1a2e" strokeWidth="6" />
              <circle cx="50" cy="50" r="42" fill="none" stroke={overallColor} strokeWidth="6"
                strokeDasharray={2 * Math.PI * 42} strokeDashoffset={2 * Math.PI * 42 - (overall / 100) * 2 * Math.PI * 42}
                strokeLinecap="round" className="transition-all duration-1000" />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ width: 160, height: 160 }}>
              <span className="text-4xl font-bold" style={{ color: overallColor }}>{overall}</span>
              <span className="text-[10px] text-[#9ca3af]">/100</span>
            </div>
          </div>
          <p className="mt-3 text-sm text-[#9ca3af]">
            {overall >= 90 ? 'Excellent — Your website is performing great.' :
             overall >= 70 ? 'Good — A few optimizations will push you to elite status.' :
             'Needs Work — Significant improvements available.'}
          </p>
        </section>

        {/* ═══ CATEGORY SCORES ═══ */}
        <section className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4" data-testid="category-scores">
          {scoreEntries.map(([key, val]) => {
            const icons = { performance: Zap, accessibility: Eye, seo: Search, best_practices: CheckCircle, security: Shield, uptime: Globe };
            const Icon = icons[key] || Globe;
            const color = val >= 90 ? '#4ade80' : val >= 70 ? '#facc15' : '#ef4444';
            return (
              <div key={key} className="flex flex-col items-center p-4 rounded-xl border border-[#1a1a2e]" style={{ background: 'rgba(10,10,20,0.5)' }}>
                <Icon className="size-4 mb-2" style={{ color }} />
                <span className="text-xl font-bold" style={{ color }}>{val}</span>
                <span className="text-[9px] text-[#9ca3af] tracking-wider uppercase mt-1 text-center">{key.replace(/_/g, ' ')}</span>
              </div>
            );
          })}
        </section>

        {/* ═══ CORE WEB VITALS ═══ */}
        {d.pagespeed_raw && (
          <section className="p-5 rounded-xl border border-[#1a1a2e]" style={{ background: 'rgba(10,10,20,0.5)' }} data-testid="web-vitals">
            <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <Zap className="size-4 text-[#D4AF37]" /> Core Web Vitals
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'LCP', value: d.pagespeed_raw.lcp, desc: 'Largest Contentful Paint' },
                { label: 'FCP', value: d.pagespeed_raw.fcp, desc: 'First Contentful Paint' },
                { label: 'CLS', value: d.pagespeed_raw.cls, desc: 'Cumulative Layout Shift' },
                { label: 'TBT', value: d.pagespeed_raw.tbt, desc: 'Total Blocking Time' },
              ].map(v => (
                <div key={v.label} className="text-center p-3 rounded-lg bg-[#0a0a14]">
                  <div className="text-lg font-bold text-white">{v.value || 'N/A'}</div>
                  <div className="text-[10px] text-[#D4AF37] font-bold tracking-wider">{v.label}</div>
                  <div className="text-[9px] text-[#9ca3af] mt-0.5">{v.desc}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ═══ ISSUES FOUND ═══ */}
        {issues.length > 0 && (
          <section className="print-break" data-testid="issues-section">
            <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <AlertTriangle className="size-4 text-yellow-400" /> Issues Found ({issues.length})
            </h2>
            <div className="space-y-2">
              {issues.map((issue, i) => (
                <div key={i} className="flex items-center justify-between p-4 rounded-xl border border-[#1a1a2e]" style={{ background: 'rgba(10,10,20,0.5)' }} data-testid={`report-issue-${i}`}>
                  <div className="flex items-center gap-3">
                    <SeverityBadge severity={issue.severity} />
                    <div>
                      <span className="text-sm text-white">{issue.title}</span>
                      {issue.detail && <span className="text-xs text-[#9ca3af] ml-2">({issue.detail})</span>}
                    </div>
                  </div>
                  <div className="text-[10px] flex-shrink-0">
                    {issue.fixable ? (
                      <span className="text-green-400 flex items-center gap-1"><CheckCircle className="size-3" /> Auto-fixable</span>
                    ) : (
                      <span className="text-[#9ca3af]">Manual fix needed</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ═══ AUTO-FIXES APPLIED ═══ */}
        {fixes.length > 0 && (
          <section data-testid="fixes-section">
            <h2 className="text-sm font-bold text-green-400 mb-4 flex items-center gap-2">
              <CheckCircle className="size-4" /> Auto-Fixed by AUREM ({fixes.length})
            </h2>
            <div className="space-y-2">
              {fixes.map((fix, i) => (
                <div key={i} className="p-4 rounded-xl border border-green-500/20" style={{ background: 'rgba(74,222,128,0.03)' }}>
                  <div className="text-sm text-white mb-2">{fix.title || fix.fix_type}</div>
                  {fix.instruction && (
                    <pre className="text-[10px] text-[#9ca3af] whitespace-pre-wrap font-mono bg-[#050510] p-3 rounded-lg border border-[#1a1a2e] mt-1">{fix.instruction}</pre>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ═══ SCORE TREND ═══ */}
        {d.history && d.history.length > 1 && (
          <section className="p-5 rounded-xl border border-[#1a1a2e]" style={{ background: 'rgba(10,10,20,0.5)' }} data-testid="score-trend">
            <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <TrendingUp className="size-4 text-[#D4AF37]" /> Score History
            </h2>
            <div className="flex items-end gap-1 h-20">
              {d.history.slice().reverse().map((h, i) => {
                const s = h.overall_score || 0;
                const c = s >= 90 ? '#4ade80' : s >= 70 ? '#facc15' : '#ef4444';
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <span className="text-[8px] text-[#9ca3af]">{s}</span>
                    <div className="w-full rounded-t" style={{ height: `${Math.max(s * 0.7, 5)}%`, background: c, minHeight: 4 }} />
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* ═══ SUMMARY ═══ */}
        <section className="p-6 rounded-xl text-center" style={{ background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.15)' }} data-testid="report-summary">
          <h2 className="text-base font-bold text-white mb-2">Report Summary</h2>
          <p className="text-sm text-[#9ca3af] max-w-lg mx-auto">
            {d.business_name}'s website scored <strong style={{ color: overallColor }}>{overall}/100</strong>.
            {issues.length > 0 && ` We found ${issues.length} issue${issues.length > 1 ? 's' : ''}.`}
            {fixes.length > 0 && ` ${fixes.length} ${fixes.length === 1 ? 'was' : 'were'} auto-fixed by AUREM.`}
            {needsAttention.length > 0 && ` ${needsAttention.length} need${needsAttention.length === 1 ? 's' : ''} manual attention.`}
            {issues.length === 0 && ' No critical issues detected.'}
          </p>
        </section>

        {/* ═══ CTA ═══ */}
        <section className="no-print text-center py-8 space-y-4" data-testid="report-cta">
          <p className="text-[#9ca3af] text-sm">Want AUREM to monitor and auto-fix your website 24/7?</p>
          <a
            href="/platform/signup"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-lg text-sm font-bold tracking-wider text-[#050507] hover:shadow-lg hover:shadow-[#D4AF37]/20 transition-all"
            style={{ background: goldGrad }}
            data-testid="report-cta-btn"
          >
            Start Free Trial <ArrowRight className="size-4" />
          </a>
          <p className="text-[9px] text-[#9ca3af]">No credit card required. Scan unlimited websites.</p>
        </section>

        {/* ═══ FOOTER ═══ */}
        <footer className="border-t border-[#1a1a2e] pt-6 pb-8 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="size-5 rounded flex items-center justify-center" style={{ background: goldGrad }}>
              <Shield className="size-3 text-[#050507]" />
            </div>
            <span className="text-[10px] tracking-[0.2em]" style={{ color: gold }}>AUREM</span>
          </div>
          <p className="text-[9px] text-[#9ca3af]">Autonomous Website Intelligence &mdash; Powered by AI</p>
          <p className="text-[8px] text-[#9ca3af]/50 mt-2">This report was generated automatically. Scores may vary between scans.</p>
        </footer>
      </main>
    </div>
  );
};

export default ClientReport;
