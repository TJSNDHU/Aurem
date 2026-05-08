/**
 * Public Shared Report Viewer
 * Accessible without login at /report/:shareId
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Shield, Globe, Zap, Eye, Code, Server, CheckCircle, XCircle, AlertTriangle, Wrench, ExternalLink, Loader2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const CATEGORY_ICONS = { security: Shield, seo: Globe, performance: Zap, accessibility: Eye, technology: Code, infrastructure: Server, connection: Globe };
const GRADE_COLORS = { A: '#4ade80', B: '#22c55e', C: '#D4B977', D: '#f59e0b', F: '#FF6B6B' };

const getGrade = (score) => {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 65) return 'C';
  if (score >= 50) return 'D';
  return 'F';
};

const ScoreGauge = ({ score, label }) => {
  const grade = getGrade(score);
  const color = GRADE_COLORS[grade];
  const circumference = 2 * Math.PI * 36;
  const dashoffset = circumference - (score / 100) * circumference;
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="6" />
          <circle cx="40" cy="40" r="36" fill="none" stroke={color} strokeWidth="6"
            strokeDasharray={circumference} strokeDashoffset={dashoffset} strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold" style={{ color }}>{score}</span>
          <span className="text-[8px] font-bold" style={{ color }}>{grade}</span>
        </div>
      </div>
      <span className="text-[10px] text-[#888] mt-1 capitalize tracking-wider">{label}</span>
    </div>
  );
};

const SharedReportPage = () => {
  const { shareId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/public/report/${shareId}`)
      .then(r => { if (!r.ok) throw new Error('Report not found'); return r.json(); })
      .then(data => setReport(data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [shareId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #f0f4f1, #e8ede9)' }}>
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-[#D4AF37] animate-spin mx-auto mb-3" />
          <p className="text-sm text-[#888] tracking-wider">Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #f0f4f1, #e8ede9)' }}>
        <div className="text-center p-8 bg-white/70 rounded-xl border border-white/40 max-w-md">
          <AlertTriangle className="w-10 h-10 text-[#D4B977] mx-auto mb-3" />
          <h1 className="text-lg font-bold text-[#1A1A2E] mb-2">Report Not Found</h1>
          <p className="text-sm text-[#888] mb-4">This report link may have expired or is invalid.</p>
          <Link to="/login" className="text-sm text-[#D4AF37] font-semibold hover:underline">Go to AUREM</Link>
        </div>
      </div>
    );
  }

  const categories = report.categories || {};
  const categoryOrder = ['connection', 'performance', 'security', 'seo', 'accessibility', 'technology', 'infrastructure'];
  const repairs = report.repairs || [];

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(135deg, #f0f4f1, #e8ede9)' }} data-testid="shared-report-page">
      <div className="max-w-4xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #FF6B00, #B38659)', boxShadow: '0 0 20px rgba(212,163,115,0.3)' }}>
              <span className="text-sm font-black text-[#1A3026]">A</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-[#1A1A2E] tracking-wider">SCAN REPORT</h1>
              <p className="text-[10px] text-[#888] tracking-wider">by AUREM ORA System Scanner</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-[#888]">{new Date(report.created_at).toLocaleDateString()}</div>
            <a href={report.website_url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-[#D4AF37] font-medium flex items-center gap-1 justify-end hover:underline mt-0.5">
              {report.website_url} <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Score Dashboard */}
        <div className="p-6 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl mb-6" data-testid="report-scores">
          <h2 className="text-[11px] font-bold tracking-[2px] text-[#1A1A2E] mb-5 uppercase">Scores</h2>
          <div className="flex justify-around mb-6 flex-wrap gap-4">
            <ScoreGauge score={report.overall_score || 0} label="Overall" />
            {Object.entries(report.scores || {}).map(([key, score]) => (
              <ScoreGauge key={key} score={score} label={key} />
            ))}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 bg-[#4ade80]/10 rounded-lg text-center">
              <div className="text-2xl font-bold text-[#FF6B00]">{report.summary?.passed || 0}</div>
              <div className="text-[9px] text-[#888] uppercase tracking-wider">Passed</div>
            </div>
            <div className="p-3 bg-[#D4B977]/10 rounded-lg text-center">
              <div className="text-2xl font-bold text-[#D4B977]">{report.summary?.warnings || 0}</div>
              <div className="text-[9px] text-[#888] uppercase tracking-wider">Warnings</div>
            </div>
            <div className="p-3 bg-[#FF6B6B]/10 rounded-lg text-center">
              <div className="text-2xl font-bold text-[#FF6B6B]">{report.summary?.failed || 0}</div>
              <div className="text-[9px] text-[#888] uppercase tracking-wider">Failed</div>
            </div>
          </div>
        </div>

        {/* Category Details */}
        {categoryOrder.map(cat => {
          const catTests = categories[cat] || [];
          if (catTests.length === 0) return null;
          const CatIcon = CATEGORY_ICONS[cat] || Globe;
          const passed = catTests.filter(t => t.result === 'pass').length;
          const total = catTests.length;

          return (
            <div key={cat} className="mb-4 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl overflow-hidden" data-testid={`report-category-${cat}`}>
              <div className="px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CatIcon className="w-4 h-4 text-[#FF6B00]" />
                  <span className="text-sm font-bold text-[#1A1A2E] capitalize tracking-wider">{cat}</span>
                </div>
                <span className="text-[10px] text-[#888]">{passed}/{total} passed</span>
              </div>
              <div className="px-5 pb-4 space-y-1.5">
                {catTests.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 py-1.5 px-2 rounded-lg" style={{ background: t.result === 'pass' ? 'rgba(74,222,128,0.05)' : t.result === 'fail' ? 'rgba(255,107,107,0.05)' : 'rgba(212,185,119,0.05)' }}>
                    {t.result === 'pass' ? <CheckCircle className="w-3.5 h-3.5 text-[#4ade80] flex-shrink-0" />
                      : t.result === 'fail' ? <XCircle className="w-3.5 h-3.5 text-[#FF6B6B] flex-shrink-0" />
                      : <AlertTriangle className="w-3.5 h-3.5 text-[#D4B977] flex-shrink-0" />}
                    <span className="text-xs text-[#1A1A2E] flex-1">{t.test || t.name}</span>
                    <span className={`text-[9px] font-bold uppercase tracking-wider ${t.result === 'pass' ? 'text-[#4ade80]' : t.result === 'fail' ? 'text-[#FF6B6B]' : 'text-[#D4B977]'}`}>
                      {t.result}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* Repairs */}
        {repairs.length > 0 && (
          <div className="mb-6 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-5" data-testid="report-repairs">
            <div className="flex items-center gap-2 mb-4">
              <Wrench className="w-4 h-4 text-[#FF6B00]" />
              <span className="text-sm font-bold text-[#1A1A2E] tracking-wider">ORA Fixes Applied</span>
              <span className="text-[10px] text-[#888] ml-auto">{repairs.length} fixes</span>
            </div>
            <div className="space-y-2">
              {repairs.map((fix, i) => (
                <div key={i} className="flex items-center gap-2 p-2 rounded-lg" style={{ background: 'rgba(255,107,0,0.04)' }}>
                  <CheckCircle className="w-3.5 h-3.5 text-[#FF6B00] flex-shrink-0" />
                  <span className="text-xs text-[#1A1A2E] flex-1">{fix.test}</span>
                  <span className="text-[9px] font-bold text-[#FF6B00] uppercase">{fix.status || 'fixed'}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="text-center py-6">
          <p className="text-[10px] text-[#888] tracking-wider mb-2">Powered by AUREM ORA — Automated Business Intelligence</p>
          <Link to="/login" className="text-xs text-[#D4AF37] font-semibold hover:underline">Scan your own website →</Link>
        </div>
      </div>
    </div>
  );
};

export default SharedReportPage;
