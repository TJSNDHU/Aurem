import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Shield, CheckCircle, XCircle, AlertTriangle, Loader2, FileSearch, Cpu, Code } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SecurityDashboard({ token }) {
  const [asvsResult, setAsvsResult] = useState(null);
  const [agenticResult, setAgenticResult] = useState(null);
  const [scanResult, setScanResult] = useState(null);
  const [badge, setBadge] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/security/compliance/badge`, { headers });
      if (res.ok) setBadge(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runAudit = async (type) => {
    setScanning(type);
    try {
      const url = type === 'asvs' ? `${API}/api/security/audit/asvs`
        : type === 'agentic' ? `${API}/api/security/audit/agentic`
        : `${API}/api/security/scan/full`;
      const res = await fetch(url, { headers });
      if (res.ok) {
        const data = await res.json();
        if (type === 'asvs') setAsvsResult(data);
        else if (type === 'agentic') setAgenticResult(data);
        else setScanResult(data);
      }
    } catch (e) { console.error(e); }
    setScanning(null);
    fetchData();
  };

  const StatusIcon = ({ status }) => {
    if (status === 'PASS') return <CheckCircle className="w-4 h-4" style={{ color: '#22C55E' }} />;
    if (status === 'FAIL') return <XCircle className="w-4 h-4" style={{ color: '#EF4444' }} />;
    return <AlertTriangle className="w-4 h-4" style={{ color: '#EAB308' }} />;
  };

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="security-dashboard">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Security Audit Center</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            OWASP Agentic AI + ASVS L1 + CI/CD Security Gate
          </p>
        </div>
        {badge && (
          <div className="flex items-center gap-3">
            <div className="px-3 py-1.5 rounded-lg text-[10px] font-bold" style={{
              background: badge.asvs_l1?.compliant ? 'rgba(34,197,94,0.1)' : 'rgba(234,179,8,0.1)',
              color: badge.asvs_l1?.compliant ? '#22C55E' : '#EAB308',
              border: `1px solid ${badge.asvs_l1?.compliant ? 'rgba(34,197,94,0.2)' : 'rgba(234,179,8,0.2)'}`,
            }}>
              ASVS L1: {badge.asvs_l1?.score || 0}%
            </div>
            <div className="px-3 py-1.5 rounded-lg text-[10px] font-bold" style={{
              background: 'rgba(139,92,246,0.1)', color: '#8B5CF6',
              border: '1px solid rgba(139,92,246,0.2)',
            }}>
              AGENTIC: {badge.agentic_ai?.score || 0}%
            </div>
          </div>
        )}
      </div>

      {/* Audit Action Buttons */}
      <StaggerGrid className="grid grid-cols-3 gap-4 mb-6">
        {[
          { type: 'asvs', label: 'ASVS L1 Audit', icon: Shield, desc: 'Auth, sessions, access, input, errors, data protection', color: '#22C55E' },
          { type: 'agentic', label: 'Agentic AI Audit', icon: Cpu, desc: 'Prompt injection, tool poisoning, excessive agency, memory safety', color: '#8B5CF6' },
          { type: 'full', label: 'Full Code Scan', icon: FileSearch, desc: 'Hardcoded secrets, eval/exec, verify=False, DEBUG=True', color: '#3B82F6' },
        ].map(({ type, label, icon: Icon, desc, color }) => (
          <MotionCard key={type}
            as="button"
            onClick={() => runAudit(type)}
            disabled={scanning === type}
            className="aurem-glass-card p-4 text-left"
            variants={cardVariant}
            data-testid={`run-${type}-btn`}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${color}15` }}>
                {scanning === type ? <Loader2 className="w-4 h-4 animate-spin" style={{ color }} /> : <Icon className="w-4 h-4" style={{ color }} />}
              </div>
              <div className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{label}</div>
            </div>
            <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{desc}</div>
          </MotionCard>
        ))}
      </StaggerGrid>

      {/* Results Grid */}
      <div className="grid grid-cols-2 gap-6">
        {/* ASVS Results */}
        <div className="aurem-glass-card overflow-hidden" data-testid="asvs-results">
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(34,197,94,0.03)' }}>
            <Shield className="w-4 h-4" style={{ color: '#22C55E' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>ASVS L1 Compliance</span>
            {asvsResult && (
              <span className="text-[10px] ml-auto px-2 py-0.5 rounded-full" style={{
                background: asvsResult.compliant ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                color: asvsResult.compliant ? '#22C55E' : '#EF4444',
              }}>{asvsResult.score}%</span>
            )}
          </div>
          {!asvsResult ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Shield className="w-8 h-8 mb-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.3 }} />
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Run ASVS audit to see results</p>
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto aurem-scroll">
              {asvsResult.checks?.map((check, i) => (
                <div key={i} className="px-5 py-3 border-b" style={{ borderColor: 'rgba(255,107,0,0.05)' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <StatusIcon status={check.status} />
                    <span className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{check.id}: {check.name}</span>
                    <span className="text-[10px] ml-auto px-1.5 py-0.5 rounded" style={{
                      background: check.status === 'PASS' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      color: check.status === 'PASS' ? '#22C55E' : '#EF4444',
                    }}>{check.status}</span>
                  </div>
                  {check.findings?.map((f, fi) => (
                    <div key={fi} className="text-[10px] ml-6" style={{ color: 'var(--aurem-body-secondary)' }}>{f}</div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Agentic AI Results */}
        <div className="aurem-glass-card overflow-hidden" data-testid="agentic-results">
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(139,92,246,0.03)' }}>
            <Cpu className="w-4 h-4" style={{ color: '#8B5CF6' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>OWASP Agentic AI Top 10</span>
            {agenticResult && (
              <span className="text-[10px] ml-auto px-2 py-0.5 rounded-full" style={{
                background: agenticResult.score >= 80 ? 'rgba(34,197,94,0.1)' : 'rgba(234,179,8,0.1)',
                color: agenticResult.score >= 80 ? '#22C55E' : '#EAB308',
              }}>{agenticResult.score}%</span>
            )}
          </div>
          {!agenticResult ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Cpu className="w-8 h-8 mb-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.3 }} />
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Run Agentic AI audit to see results</p>
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto aurem-scroll">
              {agenticResult.checks?.map((check, i) => (
                <div key={i} className="px-5 py-3 border-b" style={{ borderColor: 'rgba(255,107,0,0.05)' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <StatusIcon status={check.status} />
                    <span className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{check.id}: {check.name}</span>
                    <span className="text-[10px] ml-auto px-1.5 py-0.5 rounded" style={{
                      background: check.status === 'PASS' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      color: check.status === 'PASS' ? '#22C55E' : '#EF4444',
                    }}>{check.status}</span>
                  </div>
                  {check.findings?.map((f, fi) => (
                    <div key={fi} className="text-[10px] ml-6" style={{ color: 'var(--aurem-body-secondary)' }}>{f}</div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Full Scan Results */}
      {scanResult && (
        <div className="aurem-glass-card mt-6 overflow-hidden" data-testid="full-scan-results">
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(59,130,246,0.03)' }}>
            <Code className="w-4 h-4" style={{ color: '#3B82F6' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Full Codebase Scan</span>
            <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{scanResult.scanned} files</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full" style={{
              background: scanResult.status === 'clean' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
              color: scanResult.status === 'clean' ? '#22C55E' : '#EF4444',
            }}>{scanResult.status?.toUpperCase()}</span>
          </div>
          <div className="p-5">
            {scanResult.criticals?.length > 0 && (
              <div className="mb-3">
                <div className="text-[10px] font-bold mb-2" style={{ color: '#EF4444' }}>CRITICAL ({scanResult.criticals.length})</div>
                {scanResult.criticals.slice(0, 10).map((c, i) => (
                  <div key={i} className="text-[10px] flex items-center gap-2 py-1">
                    <XCircle className="w-3 h-3 flex-shrink-0" style={{ color: '#EF4444' }} />
                    <span style={{ color: 'var(--aurem-heading)' }}>{c.file}:{c.line}</span>
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>{c.pattern}</span>
                  </div>
                ))}
              </div>
            )}
            {scanResult.warnings?.length > 0 && (
              <div>
                <div className="text-[10px] font-bold mb-2" style={{ color: '#EAB308' }}>WARNINGS ({scanResult.warnings.length})</div>
                {scanResult.warnings.slice(0, 10).map((w, i) => (
                  <div key={i} className="text-[10px] flex items-center gap-2 py-1">
                    <AlertTriangle className="w-3 h-3 flex-shrink-0" style={{ color: '#EAB308' }} />
                    <span style={{ color: 'var(--aurem-heading)' }}>{w.file}:{w.line}</span>
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>{w.pattern}</span>
                  </div>
                ))}
              </div>
            )}
            {(scanResult.criticals?.length === 0 && scanResult.warnings?.length === 0) && (
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4" style={{ color: '#22C55E' }} />
                <span className="text-xs" style={{ color: '#22C55E' }}>Codebase is clean.</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* PentAGI Full Pentest — Enterprise Only */}
      <PentAGISection token={token} headers={headers} />
    </div>
  );
}

function PentAGISection({ token, headers }) {
  const [target, setTarget] = useState('');
  const [scanType, setScanType] = useState('full');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [health, setHealth] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');

  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${API}/api/security/pentest/health`, { headers });
        if (res.ok) setHealth(await res.json());
      } catch (e) { /* PentAGI offline */ }
    };
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API}/api/security/pentest/history?limit=5`, { headers });
        if (res.ok) { const d = await res.json(); setHistory(d.pentests || []); }
      } catch (e) { /* ignore */ }
    };
    fetchHealth();
    fetchHistory();
  }, []);

  const runPentest = async () => {
    if (!target.trim()) return;
    setRunning(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch(`${API}/api/security/pentest/run`, {
        method: 'POST', headers,
        body: JSON.stringify({ target, scan_type: scanType }),
      });
      if (res.status === 403) {
        setError('Enterprise plan required for full penetration testing');
      } else if (res.ok) {
        setResult(await res.json());
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Pentest failed');
      }
    } catch (e) { setError(e.message); }
    setRunning(false);
  };

  const SCAN_TYPES = [
    { id: 'full', label: 'Full Pentest', desc: 'Recon + vuln scan + exploitation' },
    { id: 'recon', label: 'Recon Only', desc: 'Port scan, service detection' },
    { id: 'vuln_scan', label: 'Vuln Scan', desc: 'CVE check, misconfigurations' },
    { id: 'web_app', label: 'Web App', desc: 'OWASP Top 10, API testing' },
  ];

  return (
    <div className="mt-6 rounded-2xl p-5 space-y-4" data-testid="pentagi-section"
      style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid rgba(239,68,68,0.1)' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.1)' }}>
            <Shield className="w-4 h-4" style={{ color: '#ef4444' }} />
          </div>
          <div>
            <h3 className="text-sm font-black" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>PentAGI Full Pentest</h3>
            <p className="text-[9px]" style={{ color: 'var(--aurem-text-secondary, #888)' }}>Autonomous AI penetration testing — Enterprise only</p>
          </div>
        </div>
        <span className="text-[9px] font-bold px-2.5 py-1 rounded-full" data-testid="pentagi-status"
          style={{
            background: health?.online ? 'rgba(34,197,94,0.1)' : 'rgba(128,128,128,0.1)',
            color: health?.online ? '#22c55e' : '#888',
            border: `1px solid ${health?.online ? 'rgba(34,197,94,0.2)' : 'rgba(128,128,128,0.2)'}`,
          }}>
          {health?.online ? 'LEGION ONLINE' : 'LEGION OFFLINE'}
        </span>
      </div>

      {/* Target Input */}
      <div>
        <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: '#888' }}>Target URL / IP *</label>
        <input type="text" value={target} onChange={e => setTarget(e.target.value)}
          placeholder="e.g., https://staging.client-domain.com or 192.168.1.100" data-testid="pentest-target-input"
          className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
          style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--aurem-text, #ccc)', border: '1px solid rgba(255,255,255,0.08)' }} />
      </div>

      {/* Scan Type */}
      <div className="grid grid-cols-4 gap-2" data-testid="scan-type-selector">
        {SCAN_TYPES.map(s => (
          <button key={s.id} onClick={() => setScanType(s.id)} data-testid={`scan-${s.id}`}
            className="rounded-xl px-3 py-2 text-left transition-all"
            style={{
              background: scanType === s.id ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.02)',
              border: `1px solid ${scanType === s.id ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.06)'}`,
            }}>
            <p className="text-[10px] font-bold" style={{ color: scanType === s.id ? '#ef4444' : 'var(--aurem-text, #ccc)' }}>{s.label}</p>
            <p className="text-[8px]" style={{ color: '#666' }}>{s.desc}</p>
          </button>
        ))}
      </div>

      {/* Run Button */}
      <button onClick={runPentest} disabled={running || !target.trim()} data-testid="run-pentest-btn"
        className="w-full flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold transition-all hover:opacity-90 disabled:opacity-40"
        style={{ background: running ? 'rgba(128,128,128,0.2)' : 'rgba(239,68,68,0.9)', color: running ? '#888' : '#fff' }}>
        {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Shield className="w-3.5 h-3.5" />}
        {running ? 'Starting PentAGI...' : 'Launch Pentest'}
      </button>

      {error && <p className="text-xs font-bold text-center" style={{ color: '#ef4444' }} data-testid="pentest-error">{error}</p>}

      {/* Result */}
      {result && (
        <div className="rounded-xl p-4 space-y-2" data-testid="pentest-result"
          style={{ background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.15)' }}>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4" style={{ color: result.status === 'running' ? '#D4AF37' : '#22c55e' }} />
            <span className="text-xs font-bold" style={{ color: result.status === 'running' ? '#D4AF37' : '#22c55e' }}>
              {result.status === 'running' ? 'PENTEST RUNNING' : result.status?.toUpperCase()}
            </span>
          </div>
          <p className="text-[10px]" style={{ color: 'var(--aurem-text, #ccc)' }}>{result.message || `Target: ${result.target}`}</p>
          <div className="flex gap-3 text-[9px]" style={{ color: '#888' }}>
            <span>ID: {result.pentest_id}</span>
            {result.flow_id && <span>Flow: {result.flow_id}</span>}
          </div>
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Recent Pentests</p>
          {history.map((pt, i) => (
            <div key={i} className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid rgba(128,128,128,0.08)' }}>
              <div className="flex items-center gap-2">
                <Shield className="w-3 h-3" style={{ color: pt.status === 'completed' ? '#22c55e' : pt.status === 'running' ? '#D4AF37' : '#ef4444' }} />
                <span className="text-[10px]" style={{ color: 'var(--aurem-text, #ccc)' }}>{pt.target}</span>
                <span className="text-[8px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.05)', color: '#888' }}>{pt.scan_type}</span>
              </div>
              <span className="text-[9px]" style={{ color: '#666' }}>{pt.created_at ? new Date(pt.created_at).toLocaleDateString() : ''}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
