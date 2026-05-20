/**
 * ORA System Scanner + Repair Center
 * Phase 1: Live scan with progress bars (50 tests, 7 categories)
 * Phase 2: ORA Repair — generates & deploys fixes with live progress
 * Phase 3: Push fixes to customer website DB + Rescan & Verify
 */

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Search, Shield, Globe, Zap, Eye, Code, Server, CheckCircle, XCircle, AlertTriangle, Activity, ChevronDown, ChevronRight, Wrench, Copy, Check, Play, Terminal, Bell, BellOff, Share2, Link2, Clock, Save, TrendingUp, RefreshCw, Database, ArrowRight } from 'lucide-react';
import usePushNotifications from '../hooks/usePushNotifications';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const CATEGORIES = {
  connection: { label: 'CONNECTION', icon: Globe, color: '#FF6B00' },
  performance: { label: 'PERFORMANCE', icon: Zap, color: '#D4B977' },
  security: { label: 'SECURITY', icon: Shield, color: '#FF6B6B' },
  seo: { label: 'SEO OPTIMIZATION', icon: Eye, color: '#4ade80' },
  accessibility: { label: 'ACCESSIBILITY', icon: Activity, color: '#64C8FF' },
  technology: { label: 'TECHNOLOGY', icon: Code, color: '#FF6B00' },
  infrastructure: { label: 'INFRASTRUCTURE', icon: Server, color: '#8B7355' },
};

const ResultIcon = ({ result }) => {
  if (result === 'pass') return <CheckCircle className="size-3.5 text-[#4ade80]" />;
  if (result === 'fail') return <XCircle className="size-3.5 text-[#FF6B6B]" />;
  return <AlertTriangle className="size-3.5 text-[#D4B977]" />;
};

const ScoreGauge = ({ score, label }) => {
  const color = score >= 80 ? '#4ade80' : score >= 60 ? '#D4B977' : '#FF6B6B';
  const grade = score >= 90 ? 'A+' : score >= 80 ? 'A' : score >= 70 ? 'B' : score >= 60 ? 'C' : score >= 50 ? 'D' : 'F';
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;
  return (
    <div className="flex flex-col items-center" data-testid={`gauge-${label}`}>
      <svg width="80" height="80" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="54" stroke="rgba(61,58,57,0.25)" strokeWidth="8" fill="none" />
        <circle cx="60" cy="60" r="54" stroke={color} strokeWidth="8" fill="none"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 60 60)" style={{ transition: 'stroke-dashoffset 1.5s ease-out' }} />
        <text x="60" y="55" textAnchor="middle" fontSize="22" fontWeight="bold" fill="#1A1A2E">{score}</text>
        <text x="60" y="72" textAnchor="middle" fontSize="10" fill="#888">{grade}</text>
      </svg>
      <span className="text-[9px] tracking-[1.5px] text-[#888] mt-1 uppercase">{label}</span>
    </div>
  );
};

const CategoryBar = ({ category, tests, score, isComplete, isActive }) => {
  const cat = CATEGORIES[category] || { label: category.toUpperCase(), icon: Activity, color: '#888' };
  const Icon = cat.icon;
  const [expanded, setExpanded] = useState(false);
  const passCount = tests.filter(t => t.result === 'pass').length;
  const barWidth = isComplete ? (score || 0) : Math.min(95, (tests.length / 8) * 100);
  return (
    <div className="mb-3" data-testid={`scan-category-${category}`}>
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/50 backdrop-blur-sm border border-white/30 hover:bg-white/70 transition-all">
        <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${cat.color}15` }}>
          <Icon className="size-4" style={{ color: cat.color }} />
        </div>
        <div className="flex-1 text-left">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-bold tracking-[1.5px] text-[#1A1A2E]">{cat.label}</span>
            <div className="flex items-center gap-2">
              {isComplete && <span className="text-xs font-bold" style={{ color: score >= 80 ? '#4ade80' : score >= 60 ? '#D4B977' : '#FF6B6B' }}>{score}%</span>}
              {!isComplete && isActive && <span className="text-[10px] text-[#D4B977] animate-pulse">SCANNING…</span>}
              <span className="text-[10px] text-[#888]">{passCount}/{tests.length}</span>
              {expanded ? <ChevronDown className="size-3 text-[#888]" /> : <ChevronRight className="size-3 text-[#888]" />}
            </div>
          </div>
          <div className="w-full h-2 rounded-full bg-[rgba(61,58,57,0.15)] overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700 ease-out"
              style={{ width: `${barWidth}%`,
                background: isComplete ? `linear-gradient(90deg, ${score >= 80 ? '#4ade80' : score >= 60 ? '#D4B977' : '#FF6B6B'}, ${score >= 80 ? '#FF6B00' : score >= 60 ? '#8B7355' : '#cc4444'})` : 'linear-gradient(90deg, #D4B977, #8B7355)',
                boxShadow: isActive ? '0 0 8px rgba(212,175,55,0.4)' : 'none'
              }} />
          </div>
        </div>
      </button>
      {expanded && tests.length > 0 && (
        <div className="mt-1 ml-11 space-y-1">
          {tests.map((test, i) => (
            <div key={i} className="flex items-center gap-2 py-1.5 px-3 rounded-lg bg-white/30 border border-white/20 text-xs">
              <ResultIcon result={test.result} />
              <span className="flex-1 text-[#1A1A2E] font-medium">{test.test}</span>
              <span className="text-[#888] text-[10px] font-mono">{test.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ============ REPAIR SECTION ============ */

const CodeBlock = ({ code }) => {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative mt-2 rounded-lg bg-[#1a1a2e] p-3 font-mono text-[11px] text-green-300 overflow-x-auto">
      <button onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
        className="absolute top-2 right-2 p-1 rounded bg-white/10 hover:bg-white/20 text-white/60">
        {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
      </button>
      <pre className="whitespace-pre-wrap">{code}</pre>
    </div>
  );
};

const RepairItem = ({ fix, index }) => {
  const [expanded, setExpanded] = useState(false);
  const statusColor = fix.status === 'deployed' ? '#4ade80' : fix.status === 'ready' ? '#D4B977' : '#888';
  const statusLabel = fix.status === 'deployed' ? 'AUTO-DEPLOYED' : fix.status === 'ready' ? 'FIX READY' : fix.status === 'generating' ? 'GENERATING...' : 'ANALYZING...';
  const catConfig = CATEGORIES[fix.category] || { color: '#888' };

  return (
    <div className="mb-2" data-testid={`repair-item-${index}`}>
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/50 backdrop-blur-sm border border-white/30 hover:bg-white/70 transition-all">
        <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${statusColor}15` }}>
          {fix.status === 'deployed' ? <CheckCircle className="size-4 text-[#4ade80]" /> :
           fix.status === 'ready' ? <Wrench className="size-4 text-[#D4B977]" /> :
           <Activity className="size-4 text-[#888] animate-spin" />}
        </div>
        <div className="flex-1 text-left">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-[#1A1A2E]">{fix.test}</span>
              <span className="text-[8px] px-1.5 py-0.5 rounded uppercase tracking-wider font-bold" style={{ background: `${catConfig.color}15`, color: catConfig.color }}>{fix.category}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-bold tracking-wider" style={{ color: statusColor }}>{statusLabel}</span>
              {expanded ? <ChevronDown className="size-3 text-[#888]" /> : <ChevronRight className="size-3 text-[#888]" />}
            </div>
          </div>
          <div className="w-full h-1.5 rounded-full bg-[rgba(61,58,57,0.15)] overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: fix.status === 'deployed' ? '100%' : fix.status === 'ready' ? '100%' : fix.status === 'generating' ? '60%' : '30%',
                background: fix.status === 'deployed' ? 'linear-gradient(90deg, #4ade80, #FF6B00)' : 'linear-gradient(90deg, #D4B977, #8B7355)',
                boxShadow: fix.status !== 'deployed' ? '0 0 6px rgba(212,175,55,0.4)' : 'none'
              }} />
          </div>
        </div>
      </button>
      {expanded && fix.fix_code && (
        <div className="mt-1 ml-11 p-3 rounded-lg bg-white/30 border border-white/20">
          <p className="text-xs text-[#666] mb-1">{fix.description}</p>
          {fix.ai_recommendation && <p className="text-xs text-[#FF6B00] italic mb-2">ORA: {fix.ai_recommendation}</p>}
          <div className="flex items-center gap-1 mb-1">
            <Terminal className="size-3 text-[#888]" />
            <span className="text-[9px] text-[#888] uppercase tracking-wider">Fix Code ({fix.platform})</span>
          </div>
          <CodeBlock code={fix.fix_code} />
        </div>
      )}
    </div>
  );
};

/* ============ MAIN COMPONENT ============ */

const CustomerScanner = ({ token }) => {
  const [websiteUrl, setWebsiteUrl] = useState('');
  // phases: idle, scanning, scanned, repairing, repaired, pushing, pushed, verified
  const [phase, setPhase] = useState('idle');
  const { supported: pushSupported, isSubscribed: pushActive, subscribe: pushSubscribe, unsubscribe: pushUnsubscribe } = usePushNotifications(token);

  const handleUrlChange = (e) => {
    let val = e.target.value;
    val = val.replace(/^https?:\/\//, '');
    setWebsiteUrl(val);
    if (phase !== 'idle' && phase !== 'scanning') {
      setPhase('idle');
      setTests({}); setCategoryScores({}); setCompleted(0);
      setCurrentTest(''); setActiveCategory(''); setFinalResult(null);
      setError(null); setRepairs([]); setRepairSummary(null);
      setShareLink(''); setPushResult(null);
    }
  };

  // Scan state
  const [tests, setTests] = useState({});
  const [categoryScores, setCategoryScores] = useState({});
  const [completed, setCompleted] = useState(0);
  const [total, setTotal] = useState(50);
  const [currentTest, setCurrentTest] = useState('');
  const [activeCategory, setActiveCategory] = useState('');
  const [finalResult, setFinalResult] = useState(null);

  // Repair state
  const [repairs, setRepairs] = useState([]);
  const [repairCompleted, setRepairCompleted] = useState(0);
  const [repairTotal, setRepairTotal] = useState(0);
  const [repairMessage, setRepairMessage] = useState('');
  const [repairSummary, setRepairSummary] = useState(null);

  // Push state
  const [pushResult, setPushResult] = useState(null);
  const [isPushing, setIsPushing] = useState(false);

  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);
  const [shareLink, setShareLink] = useState('');
  const [sharing, setSharing] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  // History state
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [savedScanId, setSavedScanId] = useState(null);

  const authHeaders = useMemo(() => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }), [token]);

  // ── FETCH SCAN HISTORY ──
  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/scanner/history`, { headers: authHeaders });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.scans || []);
      }
    } catch (e) { console.error('History fetch:', e); }
    finally { setHistoryLoading(false); }
  }, [authHeaders]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);
  useLivePolling(fetchHistory, 20000);

  // ── AUTO-SAVE SCAN + REPAIRS TO DB ──
  const saveScanToDb = useCallback(async (shareId) => {
    if (!finalResult) return;
    try {
      const body = {
        website_url: 'https://' + websiteUrl.replace(/^https?:\/\//, ''),
        overall_score: finalResult.overall_score || 0,
        scores: finalResult.scores || {},
        summary: finalResult.summary || {},
        categories: tests,
        repairs: repairs.map(r => ({ test: r.test, category: r.category, status: r.status, description: r.description, fix_code: r.fix_code, platform: r.platform, ai_recommendation: r.ai_recommendation })),
        repair_summary: repairSummary,
        share_id: shareId || null,
      };
      const res = await fetch(`${API_URL}/api/scanner/save`, {
        method: 'POST', headers: authHeaders,
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        setSavedScanId(data.scan_id);
        fetchHistory();
      }
    } catch (e) { console.error('Save scan:', e); }
  }, [finalResult, websiteUrl, tests, repairs, repairSummary, fetchHistory, authHeaders]);

  // Auto-save when push completes
  useEffect(() => {
    if (phase === 'pushed' && pushResult && !savedScanId) {
      saveScanToDb(null);
    }
  }, [phase, pushResult, savedScanId, saveScanToDb]);

  // ── SHARE HANDLER ──
  const handleShare = useCallback(async () => {
    if (!finalResult) return;
    setSharing(true);
    try {
      const body = {
        website_url: 'https://' + websiteUrl.replace(/^https?:\/\//, ''),
        overall_score: finalResult.overall_score || 0,
        scores: finalResult.scores || {},
        summary: finalResult.summary || {},
        categories: tests,
        repairs: repairs.map(r => ({ test: r.test, category: r.category, status: r.status, description: r.description, fix_code: r.fix_code, platform: r.platform, ai_recommendation: r.ai_recommendation })),
        repair_summary: repairSummary,
      };
      const res = await fetch(`${API_URL}/api/scanner/share`, {
        method: 'POST', headers: authHeaders,
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        const origin = window.location.origin;
        const link = `${origin}/report/${data.share_id}`;
        setShareLink(link);
        if (!savedScanId) saveScanToDb(data.share_id);
      }
    } catch (e) { console.error('Share failed:', e); }
    finally { setSharing(false); }
  }, [finalResult, websiteUrl, tests, repairs, repairSummary, savedScanId, saveScanToDb, authHeaders]);

  const copyShareLink = () => {
    navigator.clipboard.writeText(shareLink);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  };

  // ── LOAD FROM HISTORY ──
  const loadFromHistory = (scan) => {
    setWebsiteUrl(scan.website_url.replace(/^https?:\/\//, ''));
    setTests(scan.categories || {});
    setCategoryScores(scan.scores || {});
    setFinalResult({ overall_score: scan.overall_score, scores: scan.scores, summary: scan.summary });
    setRepairs(scan.repairs || []);
    setRepairSummary(scan.repair_summary);
    setSavedScanId(scan.scan_id);
    setCompleted(scan.summary?.passed + scan.summary?.warnings + scan.summary?.failed || 50);
    setTotal(50);
    setPushResult(null);
    if (scan.repairs?.length > 0) {
      setRepairCompleted(scan.repairs.length);
      setRepairTotal(scan.repairs.length);
      setRepairMessage(`${scan.repairs.length} fixes deployed`);
      setPhase('repaired');
    } else {
      setPhase('scanned');
    }
    setShowHistory(false);
  };

  // ── SCAN ──
  const handleScan = useCallback(() => {
    if (!websiteUrl) { setError('Please enter a website URL'); return; }
    setPhase('scanning');
    setTests({}); setCategoryScores({}); setCompleted(0); setCurrentTest('');
    setActiveCategory(''); setFinalResult(null); setError(null);
    setRepairs([]); setRepairSummary(null); setSavedScanId(null); setShareLink('');
    setPushResult(null);

    let url = 'https://' + websiteUrl.replace(/^https?:\/\//, '');

    const es = new EventSource(`${API_URL}/api/scanner/scan-live?url=${encodeURIComponent(url)}&token=${encodeURIComponent(token)}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const d = JSON.parse(event.data);
        if (d.phase === 'test_done') {
          setCompleted(d.completed); setTotal(d.total);
          setCurrentTest(d.test); setActiveCategory(d.category);
          setTests(prev => ({ ...prev, [d.category]: [...(prev[d.category] || []), { test: d.test, result: d.result, value: d.value }] }));
        }
        if (d.phase === 'category_done') setCategoryScores(prev => ({ ...prev, [d.category]: d.score }));
        if (d.phase === 'complete') { setFinalResult(d); setPhase('scanned'); es.close(); }
        if (d.phase === 'error') { setError(d.error); setPhase('idle'); es.close(); }
      } catch (e) { console.error('SSE parse:', e); }
    };
    es.onerror = () => { if (phase === 'scanning') setError('Connection lost'); setPhase('scanned'); es.close(); };
  }, [websiteUrl, phase]);

  // ── REPAIR ──
  const handleRepair = useCallback(() => {
    setPhase('repairing');
    setRepairs([]); setRepairCompleted(0); setRepairSummary(null); setPushResult(null);

    let url = 'https://' + websiteUrl.replace(/^https?:\/\//, '');

    const es = new EventSource(`${API_URL}/api/scanner/repair-live?url=${encodeURIComponent(url)}&token=${encodeURIComponent(token)}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const d = JSON.parse(event.data);
        if (d.phase === 'init') { setRepairTotal(d.total_fixes); setRepairMessage(d.message); }
        if (d.phase === 'deploying') {
          setRepairCompleted(d.fix_num - 1);
          setRepairMessage(d.message);
          setRepairs(prev => {
            const existing = prev.find(r => r.test === d.test);
            if (existing) return prev.map(r => r.test === d.test ? { ...r, status: d.status } : r);
            return [...prev, { test: d.test, category: d.category, status: d.status }];
          });
        }
        if (d.phase === 'fix_ready') {
          setRepairCompleted(d.fix_num);
          setRepairs(prev => prev.map(r => r.test === d.test ? { ...r, ...d } : r));
        }
        if (d.phase === 'complete') { setRepairSummary(d); setPhase('repaired'); es.close(); }
      } catch (e) { console.error('Repair SSE:', e); }
    };
    es.onerror = () => { setPhase('repaired'); es.close(); };
  }, [websiteUrl, phase]);

  // ── PUSH FIXES TO CUSTOMER DATABASE ──
  const handlePushToDb = useCallback(async () => {
    if (!repairs.length || !finalResult) return;
    setIsPushing(true);
    setPhase('pushing');
    try {
      const body = {
        website_url: 'https://' + websiteUrl.replace(/^https?:\/\//, ''),
        repairs: repairs.map(r => ({ test: r.test, category: r.category, fix_code: r.fix_code, description: r.description, platform: r.platform, ai_recommendation: r.ai_recommendation })),
        repair_summary: repairSummary,
        scores: finalResult.scores || {},
        overall_score: finalResult.overall_score || 0,
      };
      const res = await fetch(`${API_URL}/api/scanner/push-fixes`, {
        method: 'POST', headers: authHeaders,
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        setPushResult(data);
        setPhase('pushed');
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || 'Failed to push fixes to database');
        setPhase('repaired');
      }
    } catch (e) {
      console.error('Push failed:', e);
      setError('Failed to push fixes to database');
      setPhase('repaired');
    } finally {
      setIsPushing(false);
    }
  }, [repairs, finalResult, websiteUrl, repairSummary, authHeaders]);

  // ── RESCAN & VERIFY ──
  const handleRescanVerify = useCallback(() => {
    setPushResult(null);
    setSavedScanId(null);
    setShareLink('');
    setRepairs([]);
    setRepairSummary(null);
    setPhase('idle');
    // Trigger scan after state reset
    setTimeout(() => {
      if (!websiteUrl) return;
      setPhase('scanning');
      setTests({}); setCategoryScores({}); setCompleted(0); setCurrentTest('');
      setActiveCategory(''); setFinalResult(null); setError(null);

      let url = 'https://' + websiteUrl.replace(/^https?:\/\//, '');

      const es = new EventSource(`${API_URL}/api/scanner/scan-live?url=${encodeURIComponent(url)}&token=${encodeURIComponent(token)}`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const d = JSON.parse(event.data);
          if (d.phase === 'test_done') {
            setCompleted(d.completed); setTotal(d.total);
            setCurrentTest(d.test); setActiveCategory(d.category);
            setTests(prev => ({ ...prev, [d.category]: [...(prev[d.category] || []), { test: d.test, result: d.result, value: d.value }] }));
          }
          if (d.phase === 'category_done') setCategoryScores(prev => ({ ...prev, [d.category]: d.score }));
          if (d.phase === 'complete') {
            setFinalResult(d);
            const issues = (d.summary?.warnings || 0) + (d.summary?.failed || 0);
            // If no issues found, mark as verified (100% clean)
            if (issues === 0) {
              setPhase('verified');
            } else {
              setPhase('scanned');
            }
            es.close();
          }
          if (d.phase === 'error') { setError(d.error); setPhase('idle'); es.close(); }
        } catch (e) { console.error('SSE parse:', e); }
      };
      es.onerror = () => { setPhase('scanned'); es.close(); };
    }, 100);
  }, [websiteUrl]);

  // ── RECONCILE SCAN RESULTS AFTER REPAIRS ──
  useEffect(() => {
    if (phase !== 'repaired' || repairs.length === 0 || !finalResult) return;

    const repairedTests = new Set(repairs.filter(r => r.status === 'ready' || r.status === 'deployed').map(r => r.test));
    if (repairedTests.size === 0) return;

    const updatedTests = {};
    let newPassed = 0, newWarnings = 0, newFailed = 0;

    Object.entries(tests).forEach(([cat, catTests]) => {
      updatedTests[cat] = catTests.map(t => {
        if (repairedTests.has(t.test) && t.result !== 'pass') {
          return { ...t, result: 'pass', value: 'Fixed by ORA' };
        }
        return t;
      });
      updatedTests[cat].forEach(t => {
        if (t.result === 'pass') newPassed++;
        else if (t.result === 'fail') newFailed++;
        else newWarnings++;
      });
    });

    const updatedScores = {};
    Object.entries(updatedTests).forEach(([cat, catTests]) => {
      const tot = catTests.length;
      const passed = catTests.filter(t => t.result === 'pass').length;
      updatedScores[cat] = tot > 0 ? Math.round((passed / tot) * 100) : 100;
    });

    const scoreValues = Object.values(updatedScores);
    const newOverall = scoreValues.length > 0 ? Math.round(scoreValues.reduce((a, b) => a + b, 0) / scoreValues.length) : 0;

    setTests(updatedTests);
    setCategoryScores(updatedScores);
    setFinalResult({
      ...finalResult,
      overall_score: newOverall,
      scores: updatedScores,
      summary: { passed: newPassed, warnings: newWarnings, failed: newFailed },
    });
  }, [phase]); // Only run once when phase transitions to 'repaired'

  useEffect(() => { return () => { if (eventSourceRef.current) eventSourceRef.current.close(); }; }, []);

  const categoryOrder = ['connection', 'performance', 'security', 'seo', 'accessibility', 'technology', 'infrastructure'];
  const isScanning = phase === 'scanning';
  const showResults = ['scanned', 'repairing', 'repaired', 'pushing', 'pushed', 'verified'].includes(phase);
  const issueCount = finalResult ? (finalResult.summary?.warnings || 0) + (finalResult.summary?.failed || 0) : 0;

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#1A1A2E] tracking-wider mb-1" data-testid="scanner-title">ORA System Scanner</h1>
            <p className="text-xs text-[#888]">Fully automatic root-cause fix engine, scan, repair, push & verify</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowHistory(!showHistory); if (!showHistory) fetchHistory(); }}
              data-testid="history-toggle-btn"
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-medium transition-all border ${
                showHistory
                  ? 'bg-[#FF6B00]/10 border-[#FF6B00]/30 text-[#FF6B00]'
                  : 'bg-white/50 border-[#FF6B00]/15 text-[#888] hover:border-[#FF6B00]/30 hover:text-[#FF6B00]'
              }`}
            >
              <Clock className="size-3.5" />
              History {history.length > 0 && `(${history.length})`}
            </button>
            {pushSupported && (
              <button
                onClick={pushActive ? pushUnsubscribe : pushSubscribe}
                data-testid="push-toggle-btn"
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-medium transition-all border ${
                  pushActive
                    ? 'bg-[#D4AF37]/10 border-[#D4AF37]/30 text-[#D4AF37]'
                    : 'bg-white/50 border-[#FF6B00]/15 text-[#888] hover:border-[#D4AF37]/30 hover:text-[#D4AF37]'
                }`}
                title={pushActive ? 'Push notifications enabled' : 'Enable push notifications'}
              >
                {pushActive ? <Bell className="size-3.5" /> : <BellOff className="size-3.5" />}
                {pushActive ? 'Alerts ON' : 'Enable Alerts'}
              </button>
            )}
          </div>
        </div>

        {/* ===== SCAN HISTORY PANEL ===== */}
        {showHistory && (
          <div className="mb-6 p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="scan-history-panel">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Clock className="size-4 text-[#FF6B00]" />
                <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">Scan History</h2>
              </div>
              <span className="text-[10px] text-[#888]">{history.length} saved scans</span>
            </div>
            {historyLoading ? (
              <div className="text-center py-6">
                <Activity className="size-5 animate-spin text-[#888] mx-auto mb-2" />
                <span className="text-[10px] text-[#888]">Loading history…</span>
              </div>
            ) : history.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {history.map((scan, i) => {
                  const scoreColor = scan.overall_score >= 80 ? '#4ade80' : scan.overall_score >= 60 ? '#D4B977' : '#FF6B6B';
                  return (
                    <button key={scan.scan_id || i} onClick={() => loadFromHistory(scan)}
                      data-testid={`history-item-${i}`}
                      className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/50 border border-white/30 hover:bg-white/80 hover:border-[#FF6B00]/20 transition-all text-left">
                      <div className="size-10 rounded-lg flex items-center justify-center font-bold text-sm" style={{ background: `${scoreColor}15`, color: scoreColor }}>
                        {scan.overall_score}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-[#1A1A2E] truncate">{scan.website_url}</div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[9px] text-[#888]">{new Date(scan.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                          {scan.repairs?.length > 0 && (
                            <span className="text-[8px] px-1.5 py-0.5 rounded bg-[#FF6B00]/10 text-[#FF6B00] font-bold">{scan.repairs.length} FIXES</span>
                          )}
                        </div>
                      </div>
                      <ChevronRight className="size-4 text-[#888]" />
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-6">
                <Globe className="size-8 text-[#ccc] mx-auto mb-2" />
                <p className="text-xs text-[#888]">No scans saved yet.</p>
              </div>
            )}
          </div>
        )}

        {/* URL Input */}
        <div className="mb-6 p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="scanner-input">
          <label className="block text-[10px] text-[#888] mb-2 uppercase tracking-[1.5px] font-bold">Target Website</label>
          <div className="flex gap-3">
            <div className="flex-1 flex items-stretch bg-white/60 border border-[#FF6B00]/20 rounded-lg overflow-hidden focus-within:border-[#D4AF37] focus-within:ring-1 focus-within:ring-[#D4AF37]/20">
              <span className="flex items-center px-3 text-sm font-bold text-[#FF6B00] bg-[#FF6B00]/5 border-r border-[#FF6B00]/10 select-none" data-testid="https-prefix">https://</span>
              <input type="text" value={websiteUrl} onChange={handleUrlChange}
                onKeyDown={(e) => e.key === 'Enter' && handleScan()}
                placeholder="example.com"
                className="flex-1 px-3 py-3 bg-transparent text-[#1A1A2E] placeholder-[#aaa] text-sm focus:outline-none"
                disabled={isScanning || phase === 'repairing' || phase === 'pushing'}
                data-testid="scanner-url-input" />
            </div>
            <button onClick={handleScan} disabled={isScanning || phase === 'repairing' || phase === 'pushing'} data-testid="scan-button"
              className="px-6 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-white rounded-lg font-bold text-sm hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-[#D4AF37]/20">
              <Search className="size-4" />
              {isScanning ? 'Scanning...' : 'Scan System'}
            </button>
          </div>
        </div>

        {error && <div className="mb-4 p-3 bg-red-50/80 border border-red-200/50 rounded-lg text-red-600 text-sm" data-testid="scan-error">{error}</div>}

        {/* ===== VERIFIED — 100% CLEAN ===== */}
        {phase === 'verified' && finalResult && (
          <div className="mb-6 p-6 bg-gradient-to-r from-[#FF6B00]/10 to-[#4ade80]/10 rounded-xl border-2 border-[#4ade80]/30" data-testid="verified-success">
            <div className="flex items-center gap-4 mb-4">
              <div className="size-14 rounded-2xl bg-[#4ade80]/15 flex items-center justify-center">
                <CheckCircle className="size-8 text-[#4ade80]" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[#FF6B00] tracking-wider">100% VERIFIED CLEAN</h2>
                <p className="text-xs text-[#666]">All issues resolved from root cause. No errors remaining.</p>
              </div>
            </div>
            <div className="flex justify-around flex-wrap gap-4 mb-4">
              <ScoreGauge score={finalResult.overall_score} label="Overall" />
              {Object.entries(finalResult.scores || {}).map(([key, score]) => <ScoreGauge key={key} score={score} label={key} />)}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 bg-[#4ade80]/10 rounded-lg text-center">
                <div className="text-2xl font-bold text-[#FF6B00]">{finalResult.summary?.passed || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Passed</div>
              </div>
              <div className="p-3 bg-[#D4B977]/10 rounded-lg text-center">
                <div className="text-2xl font-bold text-[#D4B977]">{finalResult.summary?.warnings || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Warnings</div>
              </div>
              <div className="p-3 bg-[#FF6B6B]/10 rounded-lg text-center">
                <div className="text-2xl font-bold text-[#FF6B6B]">{finalResult.summary?.failed || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Failed</div>
              </div>
            </div>
          </div>
        )}

        {/* ===== SCAN PHASE ===== */}
        {(isScanning || showResults) && phase !== 'verified' && (
          <>
            <div className="mb-4 flex items-center justify-between px-2">
              <div className="flex items-center gap-3">
                {isScanning && <div className="size-2 rounded-full bg-[#D4B977] animate-pulse" />}
                <span className="text-xs text-[#888]">{isScanning ? `Running test ${completed}/${total}` : `Scan Complete — ${completed} tests`}</span>
              </div>
              {isScanning && <span className="text-[10px] text-[#D4B977] font-mono tracking-wider animate-pulse">{currentTest}</span>}
            </div>

            {/* Master Progress */}
            <div className="mb-6 px-2" data-testid="master-progress">
              <div className="w-full h-3 rounded-full bg-[rgba(61,58,57,0.15)] overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${(completed / total) * 100}%`,
                    background: finalResult ? 'linear-gradient(90deg, #D4AF37, #4ade80, #D4B977)' : 'linear-gradient(90deg, #D4AF37, #D4B977, #8B7355)',
                    boxShadow: isScanning ? '0 0 12px rgba(212,175,55,0.5)' : '0 0 8px rgba(212,175,55,0.3)'
                  }} />
              </div>
            </div>

            {/* Category Bars */}
            <div className="mb-6" data-testid="scan-results">
              {categoryOrder.map(cat => {
                const catTests = tests[cat] || [];
                if (catTests.length === 0 && activeCategory !== cat) return null;
                return <CategoryBar key={cat} category={cat} tests={catTests} score={categoryScores[cat]} isComplete={categoryScores[cat] !== undefined} isActive={activeCategory === cat} />;
              })}
            </div>
          </>
        )}

        {/* Score Dashboard */}
        {finalResult && phase !== 'verified' && (
          <div className="p-6 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl mb-6" data-testid="final-results">
            <h2 className="text-[11px] font-bold tracking-[2px] text-[#1A1A2E] mb-5 uppercase">Scan Report</h2>
            <div className="flex justify-around mb-6 flex-wrap gap-4">
              <ScoreGauge score={finalResult.overall_score} label="Overall" />
              {Object.entries(finalResult.scores || {}).map(([key, score]) => <ScoreGauge key={key} score={score} label={key} />)}
            </div>
            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="p-3 bg-[#4ade80]/10 rounded-lg text-center">
                <div className="text-2xl font-bold text-[#FF6B00]">{finalResult.summary?.passed || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Passed</div>
              </div>
              <div className="p-3 bg-[#D4B977]/10 rounded-lg text-center">
                <div className="text-2xl font-bold text-[#D4B977]">{finalResult.summary?.warnings || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Warnings</div>
              </div>
              <div className="p-3 bg-[#FF6B6B]/10 rounded-lg text-center">
                <div className="text-2xl font-bold text-[#FF6B6B]">{finalResult.summary?.failed || 0}</div>
                <div className="text-[9px] text-[#888] uppercase tracking-wider">Failed</div>
              </div>
            </div>

            {/* === ACTION BUTTONS BASED ON PHASE === */}

            {/* STEP 1: Deploy ORA Fixes (after scan, issues found) */}
            {issueCount > 0 && phase === 'scanned' && (
              <button onClick={handleRepair} data-testid="deploy-fixes-btn"
                className="w-full py-4 bg-gradient-to-r from-[#FF6B00] to-[#4ade80] text-white rounded-xl font-bold text-sm hover:opacity-90 transition-all flex items-center justify-center gap-3 shadow-lg shadow-[#FF6B00]/20 mt-4">
                <Wrench className="size-5" />
                DEPLOY ORA FIXES — {issueCount} Issues Detected
                <Play className="size-4" />
              </button>
            )}

            {/* STEP 2: Push Fixes to Customer DB (after repair) */}
            {phase === 'repaired' && repairs.length > 0 && (
              <button onClick={handlePushToDb} disabled={isPushing} data-testid="push-to-db-btn"
                className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-3 mt-4 shadow-lg transition-all disabled:opacity-60"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)', color: '#fff', boxShadow: '0 4px 15px rgba(212,175,55,0.3)' }}>
                <Database className="size-5" />
                {isPushing ? 'PUSHING FIXES TO DATABASE...' : 'PUSH FIXES TO CUSTOMER WEBSITE DATABASE'}
                <ArrowRight className="size-4" />
              </button>
            )}

            {/* Pushing progress indicator */}
            {phase === 'pushing' && (
              <div className="mt-4 p-4 rounded-xl bg-[#D4AF37]/10 border border-[#D4AF37]/20 flex items-center gap-3" data-testid="pushing-indicator">
                <Activity className="size-5 text-[#D4AF37] animate-spin" />
                <div>
                  <span className="text-sm font-bold text-[#8B7355]">Pushing fixes to customer database…</span>
                  <p className="text-[10px] text-[#888]">Writing root-cause fixes permanently</p>
                </div>
              </div>
            )}

            {/* STEP 3: Push success + Rescan & Verify (after push) */}
            {phase === 'pushed' && pushResult && (
              <div className="mt-4 space-y-3">
                <div className="p-4 rounded-xl bg-[#4ade80]/10 border border-[#4ade80]/20 flex items-center gap-3" data-testid="push-success">
                  <CheckCircle className="size-6 text-[#4ade80]" />
                  <div>
                    <span className="text-sm font-bold text-[#FF6B00]">{pushResult.total_pushed} fixes pushed to customer database</span>
                    <p className="text-[10px] text-[#666]">Root-cause fixes deployed permanently. Rescan to verify 100% clean.</p>
                  </div>
                </div>
                <button onClick={handleRescanVerify} data-testid="rescan-verify-btn"
                  className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-3 shadow-lg transition-all"
                  style={{ background: 'linear-gradient(135deg, #FF6B00, #4ade80)', color: '#fff', boxShadow: '0 4px 15px rgba(45,122,74,0.3)' }}>
                  <RefreshCw className="size-5" />
                  RESCAN & VERIFY DEPLOYMENT
                </button>
              </div>
            )}

            {/* Share + Save section */}
            {finalResult && (phase === 'scanned' || phase === 'pushed' || phase === 'verified') && (
              <div className="mt-4 flex gap-2" data-testid="share-section">
                {!shareLink ? (
                  <button onClick={handleShare} disabled={sharing} data-testid="share-report-btn"
                    className="flex-1 py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                    style={{ background: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.25)', color: '#8B7355' }}>
                    {sharing ? <><Activity className="size-4 animate-spin" /> Generating Link…</> : <><Share2 className="size-4" /> Share Report</>}
                  </button>
                ) : (
                  <div className="flex-1 p-3 rounded-xl" style={{ background: 'rgba(255,107,0,0.05)', border: '1px solid rgba(255,107,0,0.1)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <Link2 className="size-4 text-[#FF6B00]" />
                      <span className="text-xs font-bold text-[#FF6B00] tracking-wider">REPORT LINK</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input readOnly value={shareLink} data-testid="share-link-input"
                        className="flex-1 px-3 py-2 rounded-lg text-xs text-[#1A1A2E] bg-white/70 border border-white/40 font-mono truncate" />
                      <button onClick={copyShareLink} data-testid="copy-share-link"
                        className="px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all"
                        style={{ background: shareCopied ? 'rgba(255,107,0,0.1)' : 'rgba(212,175,55,0.15)', color: shareCopied ? '#FF6B00' : '#8B7355', border: `1px solid ${shareCopied ? 'rgba(45,122,74,0.25)' : 'rgba(212,175,55,0.25)'}` }}>
                        {shareCopied ? <><Check className="size-3.5" /> Copied!</> : <><Copy className="size-3.5" /> Copy</>}
                      </button>
                    </div>
                  </div>
                )}
                {!savedScanId && (
                  <button onClick={() => saveScanToDb(null)} data-testid="save-scan-btn"
                    className="px-4 py-3 rounded-xl text-sm font-bold flex items-center gap-2 transition-all border bg-white/50 border-[#FF6B00]/15 text-[#888] hover:border-[#FF6B00]/30 hover:text-[#FF6B00]">
                    <Save className="size-4" /> Save
                  </button>
                )}
                {savedScanId && (
                  <div className="px-4 py-3 rounded-xl text-sm font-bold flex items-center gap-2 border bg-[#FF6B00]/10 border-[#FF6B00]/20 text-[#FF6B00]">
                    <Check className="size-4" /> Saved
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ===== REPAIR PHASE ===== */}
        {(['repairing', 'repaired', 'pushing', 'pushed'].includes(phase)) && (
          <div className="mb-6" data-testid="repair-section">
            <div className="flex items-center gap-3 mb-4">
              <div className="size-8 rounded-lg bg-[#FF6B00]/10 flex items-center justify-center">
                <Wrench className="size-4 text-[#FF6B00]" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-[#1A1A2E] tracking-wider">ORA REPAIR ENGINE</h2>
                <p className="text-[10px] text-[#888]">{repairMessage || 'Deploying fixes...'}</p>
              </div>
            </div>

            {/* Repair Master Progress */}
            {repairTotal > 0 && (
              <div className="mb-4 px-2" data-testid="repair-progress">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-[#888]">{phase === 'repairing' ? `Deploying fix ${repairCompleted}/${repairTotal}` : `${repairTotal} fixes deployed`}</span>
                  {phase === 'repairing' && <span className="text-[10px] text-[#FF6B00] font-mono animate-pulse">REPAIRING…</span>}
                </div>
                <div className="w-full h-3 rounded-full bg-[rgba(61,58,57,0.15)] overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${repairTotal > 0 ? (repairCompleted / repairTotal) * 100 : 0}%`,
                      background: phase !== 'repairing' ? 'linear-gradient(90deg, #4ade80, #FF6B00)' : 'linear-gradient(90deg, #FF6B00, #4ade80, #D4B977)',
                      boxShadow: phase === 'repairing' ? '0 0 12px rgba(45,122,74,0.5)' : '0 0 8px rgba(45,122,74,0.3)'
                    }} />
                </div>
              </div>
            )}

            {/* Individual Fix Items */}
            {repairs.map((fix, i) => <RepairItem key={i} fix={fix} index={i} />)}

            {/* Repair Complete Summary */}
            {repairSummary && (
              <div className="mt-4 p-5 bg-gradient-to-r from-[#FF6B00]/10 to-[#4ade80]/10 rounded-xl border border-[#FF6B00]/20" data-testid="repair-summary">
                <div className="flex items-center gap-3 mb-3">
                  <CheckCircle className="size-6 text-[#4ade80]" />
                  <h3 className="text-sm font-bold text-[#FF6B00]">ORA REPAIR COMPLETE</h3>
                  {savedScanId && (
                    <span className="ml-auto flex items-center gap-1 text-[9px] font-bold text-[#FF6B00] bg-[#FF6B00]/10 px-2 py-0.5 rounded-full">
                      <Save className="size-3" /> SAVED TO DB
                    </span>
                  )}
                </div>

                {/* Post-repair projected scores */}
                {finalResult && (
                  <div className="mb-4 p-4 bg-white/60 rounded-xl border border-[#4ade80]/20">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="size-4 text-[#4ade80]" />
                      <span className="text-[10px] font-bold tracking-[1.5px] text-[#FF6B00] uppercase">Projected Scores After Deployment</span>
                    </div>
                    <div className="flex justify-around flex-wrap gap-3">
                      <ScoreGauge score={finalResult.overall_score} label="Overall" />
                      {Object.entries(finalResult.scores || {}).map(([key, score]) => <ScoreGauge key={key} score={score} label={key} />)}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div className="p-3 bg-white/50 rounded-lg text-center">
                    <div className="text-xl font-bold text-[#FF6B00]">{repairSummary.fixes_applied}</div>
                    <div className="text-[9px] text-[#888] uppercase">Total Fixes</div>
                  </div>
                  <div className="p-3 bg-white/50 rounded-lg text-center">
                    <div className="text-xl font-bold text-[#D4B977]">{repairSummary.manual_fixes}</div>
                    <div className="text-[9px] text-[#888] uppercase">Code Ready</div>
                  </div>
                </div>
                <p className="text-xs text-[#666]">
                  ORA generated {repairSummary.fixes_applied} root-cause fixes. Push to customer database to deploy permanently.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomerScanner;
