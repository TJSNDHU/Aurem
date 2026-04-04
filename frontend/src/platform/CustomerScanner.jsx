/**
 * Customer System Scanner
 * Scan customer websites and generate comprehensive reports
 */

import React, { useState } from 'react';
import { Search, AlertCircle, CheckCircle, TrendingUp, Shield, Globe, Eye, Download, ExternalLink, Zap } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const CustomerScanner = ({ token }) => {
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [error, setError] = useState(null);

  const handleScan = async () => {
    if (!websiteUrl) {
      setError('Please enter a website URL');
      return;
    }

    try {
      setIsScanning(true);
      setError(null);
      setScanResult(null);

      const response = await fetch(`${API_URL}/api/scanner/scan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          website_url: websiteUrl,
          include_performance: true,
          include_security: true,
          include_seo: true,
          include_accessibility: true
        })
      });

      if (response.ok) {
        const data = await response.json();
        setScanResult(data);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Scan failed');
      }
    } catch (err) {
      console.error('Scan error:', err);
      setError(err.message || 'Failed to scan website');
    } finally {
      setIsScanning(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-[#4CAF50]';
    if (score >= 60) return 'text-[#FFB74D]';
    return 'text-[#FF6B6B]';
  };

  const getSeverityColor = (severity) => {
    if (severity === 'critical') return 'text-[#FF6B6B]';
    if (severity === 'warning') return 'text-[#FFB74D]';
    return 'text-[#64C8FF]';
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#050505] p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-light text-[#F4F4F4] tracking-wider mb-2">Customer System Scanner</h1>
          <p className="text-sm text-[#666]">
            Analyze customer websites and show them exactly how AUREM improves their business
          </p>
        </div>

        {/* Scan Input */}
        <div className="mb-8 p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
          <label className="block text-sm text-[#888] mb-3 uppercase tracking-wider">Website URL to Scan</label>
          <div className="flex gap-3">
            <input
              type="url"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://customer-website.com"
              className="flex-1 px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:outline-none focus:border-[#D4AF37]"
              disabled={isScanning}
            />
            <button
              onClick={handleScan}
              disabled={isScanning}
              className="px-8 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg font-medium hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              {isScanning ? 'Scanning...' : 'Scan System'}
            </button>
          </div>
          {error && (
            <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-400 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
        </div>

        {/* Loading State */}
        {isScanning && (
          <div className="p-12 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
            <div className="w-16 h-16 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-[#888]">Analyzing website...</p>
            <p className="text-xs text-[#555] mt-2">Scanning performance, security, SEO, and accessibility</p>
          </div>
        )}

        {/* Scan Results */}
        {scanResult && !isScanning && (
          <div className="space-y-6">
            {/* Overall Score Card */}
            <div className="p-6 bg-gradient-to-br from-[#0A0A0A] to-[#0F0F0F] border border-[#1A1A1A] rounded-lg">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-medium text-[#F4F4F4] mb-1">Scan Complete</h2>
                  <p className="text-xs text-[#666]">{scanResult.website_url}</p>
                </div>
                <button className="px-4 py-2 bg-[#1A1A1A] border border-[#252525] rounded-lg text-sm text-[#888] hover:text-[#D4AF37] hover:border-[#D4AF37]/30 transition-all flex items-center gap-2">
                  <Download className="w-4 h-4" />
                  Export Report
                </button>
              </div>

              <div className="grid grid-cols-4 gap-4">
                {/* Overall Score */}
                <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg text-center">
                  <div className={`text-4xl font-bold mb-2 ${getScoreColor(scanResult.overall_score)}`}>
                    {scanResult.overall_score}
                  </div>
                  <div className="text-xs text-[#666] uppercase tracking-wider">Overall Score</div>
                </div>

                {/* Issues Found */}
                <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg text-center">
                  <div className="text-4xl font-bold text-[#FF6B6B] mb-2">
                    {scanResult.issues_found}
                  </div>
                  <div className="text-xs text-[#666] uppercase tracking-wider">Issues Found</div>
                </div>

                {/* Critical Issues */}
                <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg text-center">
                  <div className="text-4xl font-bold text-[#FF4444] mb-2">
                    {scanResult.critical_issues}
                  </div>
                  <div className="text-xs text-[#666] uppercase tracking-wider">Critical</div>
                </div>

                {/* Potential Improvement */}
                <div className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg text-center">
                  <div className="text-4xl font-bold text-[#4CAF50] mb-2">
                    +{scanResult.aurem_impact.automation_coverage}
                  </div>
                  <div className="text-xs text-[#666] uppercase tracking-wider">Automation %</div>
                </div>
              </div>
            </div>

            {/* Category Scores */}
            <div className="grid grid-cols-4 gap-4">
              <ScoreCard
                title="Performance"
                icon={Zap}
                score={scanResult.performance.score}
                issues={scanResult.performance.issues.length}
                color="#64C8FF"
              />
              <ScoreCard
                title="Security"
                icon={Shield}
                score={scanResult.security.score}
                issues={scanResult.security.issues.length}
                color="#4CAF50"
              />
              <ScoreCard
                title="SEO"
                icon={Globe}
                score={scanResult.seo.score}
                issues={scanResult.seo.issues.length}
                color="#FFB74D"
              />
              <ScoreCard
                title="Accessibility"
                icon={Eye}
                score={scanResult.accessibility.score}
                issues={scanResult.accessibility.issues.length}
                color="#9C27B0"
              />
            </div>

            {/* AUREM Impact - THE MONEY SHOT */}
            <div className="p-6 bg-gradient-to-br from-[#D4AF37]/10 to-[#8B7355]/10 border border-[#D4AF37]/30 rounded-lg">
              <div className="flex items-center gap-3 mb-4">
                <TrendingUp className="w-6 h-6 text-[#D4AF37]" />
                <h3 className="text-lg font-medium text-[#D4AF37]">Expected Impact with AUREM</h3>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
                  <div className="text-2xl font-bold text-[#4CAF50] mb-1">
                    +{scanResult.aurem_impact.speed_improvement_percent}%
                  </div>
                  <div className="text-xs text-[#888]">Speed Improvement</div>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
                  <div className="text-2xl font-bold text-[#4CAF50] mb-1">
                    +{scanResult.aurem_impact.security_score_improvement}
                  </div>
                  <div className="text-xs text-[#888]">Security Score</div>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
                  <div className="text-2xl font-bold text-[#4CAF50] mb-1">
                    +{scanResult.aurem_impact.seo_ranking_boost}%
                  </div>
                  <div className="text-xs text-[#888]">SEO Ranking Boost</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-[#0A0A0A] border border-[#D4AF37]/20 rounded-lg">
                  <div className="text-sm text-[#666] mb-2">Time Saved Monthly</div>
                  <div className="text-xl font-bold text-[#D4AF37]">
                    {scanResult.aurem_impact.estimated_time_saved_monthly}
                  </div>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#D4AF37]/20 rounded-lg">
                  <div className="text-sm text-[#666] mb-2">Cost Savings Monthly</div>
                  <div className="text-xl font-bold text-[#4CAF50]">
                    {scanResult.aurem_impact.estimated_cost_savings_monthly}
                  </div>
                </div>
              </div>

              <div className="mt-4 p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
                <div className="text-sm text-[#888] mb-3">Before vs After AUREM:</div>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <div className="text-xs text-red-400 mb-2">❌ Before</div>
                    <div className="space-y-1 text-xs text-[#888]">
                      <div>• {scanResult.aurem_impact.before_aurem.critical_issues} Critical Issues</div>
                      <div>• {scanResult.aurem_impact.before_aurem.warnings} Warnings</div>
                      <div>• {scanResult.aurem_impact.before_aurem.manual_work_hours_weekly}h/week manual work</div>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-[#4CAF50] mb-2">✅ After</div>
                    <div className="space-y-1 text-xs text-[#888]">
                      <div>• {scanResult.aurem_impact.after_aurem.critical_issues} Critical Issues</div>
                      <div>• {scanResult.aurem_impact.after_aurem.warnings} Warnings</div>
                      <div>• {scanResult.aurem_impact.after_aurem.manual_work_hours_weekly}h/week manual work</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Top Recommendations */}
            <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
              <h3 className="text-lg font-medium text-[#F4F4F4] mb-4">Top Recommendations</h3>
              <div className="space-y-3">
                {scanResult.recommendations.map((rec, idx) => (
                  <div key={idx} className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg">
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        rec.priority === 'high' ? 'bg-red-500/10' : 'bg-yellow-500/10'
                      }`}>
                        <AlertCircle className={`w-5 h-5 ${
                          rec.priority === 'high' ? 'text-red-400' : 'text-yellow-400'
                        }`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h4 className="text-sm font-medium text-[#F4F4F4]">{rec.title}</h4>
                          <span className={`px-2 py-0.5 text-[9px] rounded uppercase ${
                            rec.priority === 'high' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'
                          }`}>
                            {rec.priority}
                          </span>
                          <span className="px-2 py-0.5 text-[9px] bg-[#1A1A1A] text-[#888] rounded uppercase">
                            {rec.category}
                          </span>
                        </div>
                        <p className="text-xs text-[#888] mb-2">{rec.description}</p>
                        <div className="p-3 bg-[#D4AF37]/5 border border-[#D4AF37]/20 rounded">
                          <div className="text-[10px] text-[#666] uppercase tracking-wider mb-1">AUREM Solution:</div>
                          <div className="text-xs text-[#D4AF37]">{rec.solution}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* CTA */}
            <div className="p-6 bg-gradient-to-r from-[#D4AF37]/20 to-[#8B7355]/20 border border-[#D4AF37]/30 rounded-lg text-center">
              <h3 className="text-xl font-medium text-[#F4F4F4] mb-2">Ready to Fix These Issues?</h3>
              <p className="text-sm text-[#888] mb-4">
                AUREM can automate and fix {scanResult.issues_found} issues, saving {scanResult.aurem_impact.estimated_time_saved_monthly} monthly
              </p>
              <button className="px-8 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg font-medium hover:opacity-90 transition-all">
                Deploy AUREM for This Customer
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const ScoreCard = ({ title, icon: Icon, score, issues, color }) => {
  const getScoreColor = (score) => {
    if (score >= 80) return 'text-[#4CAF50]';
    if (score >= 60) return 'text-[#FFB74D]';
    return 'text-[#FF6B6B]';
  };

  return (
    <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}10` }}>
          <Icon className="w-5 h-5" style={{ color }} />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-[#F4F4F4]">{title}</h3>
        </div>
      </div>
      <div className={`text-3xl font-bold mb-2 ${getScoreColor(score)}`}>{score}</div>
      <div className="text-xs text-[#666]">{issues} issues found</div>
    </div>
  );
};

export default CustomerScanner;
