import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { AlertTriangle, Activity, Shield, Loader2, RefreshCw, CheckCircle, TrendingUp, Clock, CreditCard, Zap } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, PageTransition, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

function ScoreBar({ score }) {
  const color = score >= 8 ? '#EF4444' : score >= 5 ? '#EAB308' : '#22C55E';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(61,58,57,0.15)' }}>
        <motion.div className="h-full rounded-full" style={{ background: color }}
          initial={{ width: 0 }} animate={{ width: `${score * 10}%` }} transition={{ duration: 0.6 }} />
      </div>
      <span className="text-xs font-bold" style={{ color }}>{score}/10</span>
    </div>
  );
}

export default function SentinelAnomalyDashboard({ token }) {
  const [scanResult, setScanResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [histRes, statsRes] = await Promise.all([
        fetch(`${API}/api/sentinel-anomaly/history?limit=10`, { headers }),
        fetch(`${API}/api/sentinel-anomaly/stats`, { headers }),
      ]);
      if (histRes.ok) { const d = await histRes.json(); setHistory(d.history || []); if (d.history?.length > 0) setScanResult(d.history[0]); }
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (e) { console.error('Sentinel anomaly:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API}/api/sentinel-anomaly/scan`, {
        method: 'POST', headers, body: JSON.stringify({ tenant_id: 'aurem_platform' }),
      });
      if (res.ok) {
        const data = await res.json();
        setScanResult(data);
      }
      await fetchData();
    } catch (e) { console.error('Scan error:', e); }
    setScanning(false);
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 className="size-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
    </div>
  );

  const metricIcons = {
    api_calls: Zap,
    outreach_volume: TrendingUp,
    login_hours: Clock,
    invoice_amount: CreditCard,
  };

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="sentinel-anomaly-dashboard">
      <PageTransition>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)' }}>Sentinel Anomaly Detection</h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
              7-day rolling baseline. Alert on {'>'} 3x deviation. Score 1-10. {'>'}7 = critical alert.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleScan}
              disabled={scanning}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold tracking-wider transition-all hover:scale-[1.02] disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)', color: '#0A0A00' }}
              data-testid="anomaly-scan-btn"
            >
              {scanning ? <Loader2 className="size-3 animate-spin" /> : <Shield className="size-3" />}
              Run Scan
            </button>
            <button onClick={fetchData} className="p-2 rounded-lg hover:bg-white/10 transition-colors">
              <RefreshCw className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />
            </button>
          </div>
        </div>

        {/* Stats bar */}
        {stats && (
          <StaggerGrid className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: 'Total Scans', value: stats.total_scans || 0, icon: Activity, color: '#3B82F6' },
              { label: 'Critical Alerts', value: stats.critical_alerts || 0, icon: AlertTriangle, color: '#EF4444' },
              { label: 'Alert Rate', value: `${stats.alert_rate || 0}%`, icon: Shield, color: '#F97316' },
            ].map(card => (
              <MotionCard key={card.label} variant={cardVariant} className="aurem-glass-card p-4">
                <div className="flex items-center gap-2 mb-1">
                  <card.icon className="size-4" style={{ color: card.color }} />
                  <span className="text-lg font-bold" style={{ color: card.color }}>{card.value}</span>
                </div>
                <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{card.label}</div>
              </MotionCard>
            ))}
          </StaggerGrid>
        )}

        {/* Current Scan Result */}
        {scanResult && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="aurem-glass-card p-5 mb-6" data-testid="anomaly-result">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                {scanResult.has_critical ? (
                  <AlertTriangle className="size-5" style={{ color: '#EF4444' }} />
                ) : (
                  <CheckCircle className="size-5" style={{ color: '#22C55E' }} />
                )}
                <span className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>
                  {scanResult.has_critical ? 'Anomaly Detected' : 'All Clear'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs px-2 py-1 rounded-full font-bold" style={{
                  background: scanResult.max_score > 7 ? 'rgba(239,68,68,0.12)' : scanResult.max_score > 4 ? 'rgba(234,179,8,0.12)' : 'rgba(34,197,94,0.12)',
                  color: scanResult.max_score > 7 ? '#EF4444' : scanResult.max_score > 4 ? '#EAB308' : '#22C55E',
                }}>
                  Max Score: {scanResult.max_score}/10
                </span>
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {scanResult.triggered_count} triggered
                </span>
              </div>
            </div>

            {/* Per-metric breakdown */}
            <div className="space-y-3">
              {(scanResult.anomalies || []).map((a, i) => {
                const Icon = metricIcons[a.metric] || Activity;
                return (
                  <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.05 * i }}
                    className="p-3 rounded-lg" style={{ background: a.anomaly ? 'rgba(239,68,68,0.04)' : 'rgba(255,107,0,0.03)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className="size-4" style={{ color: a.anomaly ? '#EF4444' : '#22C55E' }} />
                      <span className="text-xs font-bold capitalize" style={{ color: 'var(--aurem-heading)' }}>
                        {a.metric.replace(/_/g, ' ')}
                      </span>
                      {a.anomaly && <span className="text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.12)', color: '#EF4444' }}>ANOMALY</span>}
                      <span className="ml-auto text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        Current: {typeof a.current === 'number' ? a.current : '-'} | Baseline: {typeof a.baseline === 'number' ? a.baseline : a.baseline || '-'}
                        {a.ratio > 0 ? ` | ${a.ratio}x` : ''}
                      </span>
                    </div>
                    <ScoreBar score={a.score} />
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* History */}
        {history.length > 1 && (
          <div className="aurem-glass-card overflow-hidden" data-testid="anomaly-history">
            <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)' }}>
              <Activity className="size-4" style={{ color: '#3B82F6' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Scan History</span>
            </div>
            <div className="max-h-[200px] overflow-y-auto aurem-scroll">
              {history.map((h, i) => (
                <div key={i} className="px-5 py-2 border-b flex items-center gap-3" style={{ borderColor: 'rgba(255,107,0,0.05)' }}>
                  <div className="size-2 rounded-full" style={{ background: h.has_critical ? '#EF4444' : '#22C55E' }} />
                  <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                    Score {h.max_score}/10 | {h.triggered_count} triggered
                  </span>
                  <span className="ml-auto text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {h.timestamp ? new Date(h.timestamp).toLocaleString() : '-'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </PageTransition>
    </div>
  );
}
