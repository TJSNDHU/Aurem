import React, { useState, useEffect, useCallback, useMemo } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Server, Key, DollarSign, Users, Activity,
  TrendingUp, AlertCircle, CheckCircle, XCircle,
  Database, Zap, BarChart3, Settings, Copy, Mail, RefreshCw, Check,
  Globe, Shield, Search, Eye, Wrench, ChevronDown, ChevronUp, ArrowLeft, ExternalLink
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/* ─── Inline Admin Business IDs Panel ─── */
function AdminBusinessIdsEmbed({ token }) {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState('');

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/api/admin/business-ids`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setTenants(d.tenants || []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  const copyBid = (bid) => { navigator.clipboard?.writeText(bid); setCopied(bid); setTimeout(() => setCopied(''), 2000); };
  const resend = async (email) => {
    await fetch(`${API_URL}/api/admin/business-id/resend/${email}`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
  };

  return (
    <Card>
      <CardHeader><CardTitle data-testid="business-ids-title">Business IDs ({tenants.length})</CardTitle></CardHeader>
      <CardContent>
        {loading ? <div className="text-center py-8 text-gray-500">Loading…</div> : (
          <div className="space-y-2">
            {tenants.map((t, i) => (
              <div key={t.business_id || i} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border">
                <div>
                  <div className="font-medium text-sm">{t.business_name || t.email}</div>
                  <div className="text-xs text-gray-500">{t.email}</div>
                </div>
                <div className="flex items-center gap-3">
                  <code className="text-sm font-bold text-orange-600">{t.business_id}</code>
                  <button onClick={() => copyBid(t.business_id)} className="p-1 hover:bg-gray-200 rounded" title="Copy">
                    {copied === t.business_id ? <Check size={14} className="text-green-500" /> : <Copy size={14} className="text-gray-400" />}
                  </button>
                  <button onClick={() => resend(t.email)} className="p-1 hover:bg-gray-200 rounded" title="Resend Welcome">
                    <Mail size={14} className="text-gray-400" />
                  </button>
                  <Badge variant={t.welcome_sent ? "default" : "secondary"}>{t.connected_devices} devices</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ─── Score Badge ─── */
function ScoreBadge({ score, size = 'md' }) {
  const color = score >= 80 ? 'bg-green-100 text-green-700 border-green-200'
    : score >= 60 ? 'bg-yellow-100 text-yellow-700 border-yellow-200'
    : 'bg-red-100 text-red-700 border-red-200';
  const sz = size === 'lg' ? 'text-2xl px-4 py-2' : 'text-sm px-2 py-0.5';
  return <span className={`font-bold rounded-md border ${color} ${sz}`} data-testid="score-badge">{score}</span>;
}

/* ─── Repair Status Badge ─── */
function RepairStatusBadge({ status }) {
  const map = {
    deployed: 'bg-green-100 text-green-700',
    ready: 'bg-blue-100 text-blue-700',
    pending_approval: 'bg-yellow-100 text-yellow-700',
    archived: 'bg-gray-100 text-gray-500',
  };
  return <span className={`text-xs font-medium px-2 py-0.5 rounded ${map[status] || 'bg-gray-100 text-gray-500'}`}>{status}</span>;
}

/* ─── Client Detail View ─── */
function ClientDetail({ profileId, token, onBack }) {
  const [client, setClient] = useState(null);
  const [scans, setScans] = useState([]);
  const [repairs, setRepairs] = useState([]);
  const [inlineRepairs, setInlineRepairs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedScan, setExpandedScan] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState('');

  const loadClientData = useCallback(async () => {
    if (!profileId || !token) return;
    const h = { 'Authorization': `Bearer ${token}` };
    try {
      const [detail, repairData] = await Promise.all([
        fetch(`${API_URL}/api/admin/mission-control/clients/${profileId}`, { headers: h }).then(r => r.json()),
        fetch(`${API_URL}/api/admin/mission-control/clients/${profileId}/repairs`, { headers: h }).then(r => r.json()),
      ]);
      setClient(detail.client);
      setScans(detail.scans || []);
      setRepairs(repairData.repairs || []);
      setInlineRepairs(repairData.inline_repairs || []);
    } catch (e) {
      console.error('Failed to load client:', e);
    }
  }, [profileId, token]);

  useEffect(() => {
    loadClientData().finally(() => setLoading(false));
  }, [loadClientData]);

  const triggerRescan = async () => {
    if (!token || scanning) return;
    setScanning(true);
    setScanProgress('Connecting to website...');
    const phases = ['Analyzing performance...', 'Checking security headers...', 'Scanning SEO...', 'Testing accessibility...', 'Generating report...'];
    let phase = 0;
    const interval = setInterval(() => {
      if (phase < phases.length) { setScanProgress(phases[phase]); phase++; }
    }, 2500);
    try {
      const res = await fetch(`${API_URL}/api/admin/mission-control/clients/${profileId}/rescan`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      clearInterval(interval);
      if (!res.ok) throw new Error(`Scan failed: ${res.status}`);
      const data = await res.json();
      setScanProgress(`Score: ${data.scan?.overall_score} — Done!`);
      // Refresh all client data
      await loadClientData();
      setTimeout(() => { setScanning(false); setScanProgress(''); }, 2000);
    } catch (e) {
      clearInterval(interval);
      console.error('Rescan failed:', e);
      setScanProgress('Scan failed. Try again.');
      setTimeout(() => { setScanning(false); setScanProgress(''); }, 3000);
    }
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading client details…</div>;
  if (!client) return <div className="text-center py-12 text-red-500">Client not found</div>;

  const allRepairs = [...repairs, ...inlineRepairs];
  const categoryGroups = {};
  allRepairs.forEach(r => {
    const cat = r.category || 'other';
    if (!categoryGroups[cat]) categoryGroups[cat] = [];
    categoryGroups[cat].push(r);
  });

  return (
    <div className="space-y-4" data-testid="client-detail-view">
      {/* Back button + Header + Rescan */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack} data-testid="client-detail-back">
          <ArrowLeft className="size-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h2 className="text-xl font-bold text-gray-900">{client.business_name}</h2>
          <div className="flex items-center gap-3 text-sm text-gray-500">
            {client.website_url && (
              <a href={client.website_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-blue-600 hover:underline">
                <Globe className="size-3" /> {client.website_url}
                <ExternalLink className="size-3" />
              </a>
            )}
            <span>{client.category} / {client.sub_category}</span>
            {client.plan && <Badge variant="outline">{client.plan}</Badge>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button
            onClick={triggerRescan}
            disabled={scanning}
            className={`${scanning ? 'bg-orange-500 hover:bg-orange-500' : 'bg-pink-600 hover:bg-pink-700'} text-white`}
            data-testid="rescan-button"
          >
            <RefreshCw className={`size-4 mr-2 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning...' : 'Rescan Now'}
          </Button>
          {scanning && scanProgress && (
            <span className="text-xs text-orange-600 font-medium animate-pulse" data-testid="scan-progress">{scanProgress}</span>
          )}
          {!scanning && scans.length > 0 && (
            <span className="text-xs text-gray-400">
              Last scanned: {(() => {
                const d = scans[0]?.created_at || scans[0]?.scan_date;
                if (!d) return 'N/A';
                const diff = Date.now() - new Date(d).getTime();
                if (diff < 60000) return 'just now';
                if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
                if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
                return new Date(d).toLocaleDateString();
              })()}
            </span>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xs text-gray-500 mb-1">Total Scans</div>
            <div className="text-2xl font-bold text-gray-900" data-testid="client-total-scans">{scans.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xs text-gray-500 mb-1">Total Repairs</div>
            <div className="text-2xl font-bold text-green-600" data-testid="client-total-repairs">{allRepairs.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xs text-gray-500 mb-1">Latest Score</div>
            {scans.length > 0 ? <ScoreBadge score={scans[0].overall_score} size="lg" /> : <span className="text-gray-400">--</span>}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xs text-gray-500 mb-1">Status</div>
            <Badge className={client.status === 'active' ? 'bg-green-500' : 'bg-gray-400'}>{client.status || 'unknown'}</Badge>
          </CardContent>
        </Card>
      </div>

      {/* Scan History */}
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Search className="size-4" /> Scan History</CardTitle></CardHeader>
        <CardContent>
          {scans.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No scans recorded</p>
          ) : (
            <div className="space-y-2">
              {scans.map((scan) => {
                const isExpanded = expandedScan === scan.scan_id;
                const scores = scan.scores || {};
                const summary = scan.summary || {};
                const inlineReps = (scan.repairs || []);
                const scanDate = scan.created_at || scan.scan_date || '';
                // Handle both scan_history format (passed/warnings/failed) and system_scans format (issues_found/critical)
                const summaryText = summary.passed != null
                  ? `${summary.passed || 0} passed, ${summary.warnings || 0} warnings, ${summary.failed || 0} failed`
                  : scan.open_issues != null
                    ? `${scan.open_issues} open${scan.fixed_issues ? `, ${scan.fixed_issues} fixed` : ''}${scan.confirmed_resolved ? `, ${scan.confirmed_resolved} resolved` : ''}${scan.critical_issues ? `, ${scan.critical_issues} critical` : ''}`
                    : `${scan.issues_found || 0} issues found${scan.critical_issues ? `, ${scan.critical_issues} critical` : ''}`;
                // Build category-like data from system_scans performance/security/seo/accessibility
                const categories = scan.categories || {};
                const hasCategoryTests = Object.keys(categories).length > 0;
                // For system_scans, build issue list from sub-objects
                const scanIssues = [];
                if (!hasCategoryTests) {
                  ['performance', 'security', 'seo', 'accessibility'].forEach(cat => {
                    const catData = scan[cat];
                    if (catData && catData.issues) {
                      catData.issues.forEach(issue => scanIssues.push({ ...issue, _cat: cat }));
                    }
                  });
                }
                const recommendations = scan.recommendations || [];
                return (
                  <div key={scan.scan_id} className="border rounded-lg overflow-hidden" data-testid={`scan-row-${scan.scan_id}`}>
                    <button
                      className="w-full flex items-center justify-between p-3 hover:bg-gray-50 text-left"
                      onClick={() => setExpandedScan(isExpanded ? null : scan.scan_id)}
                    >
                      <div className="flex items-center gap-3">
                        <ScoreBadge score={scan.overall_score} />
                        <div>
                          <div className="text-sm font-medium">{(scan.scan_id || '').slice(0, 20)}...</div>
                          <div className="text-xs text-gray-500">
                            {scanDate ? new Date(scanDate).toLocaleDateString() : 'N/A'} &middot; {summaryText}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {inlineReps.length > 0 && (
                          <Badge variant="outline" className="text-xs">
                            <Wrench className="size-3 mr-1" /> {inlineReps.length} repairs
                          </Badge>
                        )}
                        {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                      </div>
                    </button>
                    {isExpanded && (
                      <div className="border-t px-4 py-3 bg-gray-50 space-y-3">
                        {/* Score breakdown */}
                        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                          {Object.entries(scores).map(([key, val]) => (
                            <div key={key} className="text-center">
                              <div className="text-xs text-gray-500 capitalize">{key}</div>
                              <ScoreBadge score={typeof val === 'number' ? val : 0} />
                            </div>
                          ))}
                        </div>
                        {/* Category test results (scan_history format) */}
                        {hasCategoryTests && Object.entries(categories).map(([cat, tests]) => (
                          <div key={cat}>
                            <div className="text-xs font-semibold text-gray-600 uppercase mb-1">{cat}</div>
                            <div className="space-y-1">
                              {tests.map((t, i) => (
                                <div key={i} className="flex items-center justify-between text-xs px-2 py-1 rounded bg-white">
                                  <span className="text-gray-700">{t.test}</span>
                                  <div className="flex items-center gap-2">
                                    <span className="text-gray-500">{t.value}</span>
                                    {t.result === 'pass' && <CheckCircle className="size-3 text-green-500" />}
                                    {t.result === 'warning' && <AlertCircle className="size-3 text-yellow-500" />}
                                    {t.result === 'fail' && <XCircle className="size-3 text-red-500" />}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                        {/* Issues list (system_scans format) */}
                        {!hasCategoryTests && scanIssues.length > 0 && (() => {
                          const openIssues = scanIssues.filter(i => !i.is_fixed);
                          const fixedIssues = scanIssues.filter(i => i.is_fixed);
                          return (
                            <>
                              {openIssues.length > 0 && (
                                <div>
                                  <div className="text-xs font-semibold text-gray-600 uppercase mb-1">Open Issues ({openIssues.length})</div>
                                  <div className="space-y-1">
                                    {openIssues.map((issue, i) => (
                                      <div key={i} className="flex items-center justify-between text-xs px-2 py-1 rounded bg-white" data-testid={`open-issue-${i}`}>
                                        <div className="flex-1">
                                          <span className="font-medium text-gray-700">{issue.issue}</span>
                                          <span className="text-gray-400 ml-2 text-xs">{issue.details?.slice(0, 80)}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline" className="text-xs capitalize">{issue._cat}</Badge>
                                          {issue.severity === 'critical' && <XCircle className="size-3 text-red-500" />}
                                          {issue.severity === 'warning' && <AlertCircle className="size-3 text-yellow-500" />}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {fixedIssues.length > 0 && (
                                <div>
                                  <div className="text-xs font-semibold text-green-600 uppercase mb-1 flex items-center gap-1">
                                    <CheckCircle className="size-3" /> Already Fixed ({fixedIssues.length})
                                  </div>
                                  <div className="space-y-1 opacity-60">
                                    {fixedIssues.map((issue, i) => (
                                      <div key={i} className="flex items-center justify-between text-xs px-2 py-1 rounded bg-green-50 border border-green-100" data-testid={`fixed-issue-${i}`}>
                                        <div className="flex-1">
                                          <span className="font-medium text-green-700 line-through">{issue.issue}</span>
                                          {issue.fixed_note && <span className="text-green-500 ml-2 text-xs">{issue.fixed_note}</span>}
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline" className="text-xs capitalize border-green-200 text-green-600">{issue._cat}</Badge>
                                          <CheckCircle className="size-3 text-green-500" />
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {openIssues.length === 0 && fixedIssues.length > 0 && (
                                <div className="text-center py-2">
                                  <Badge className="bg-green-100 text-green-700 border-green-200" data-testid="all-fixed-badge">All issues fixed</Badge>
                                </div>
                              )}
                              {/* Confirmed Resolved — fixes that worked, issue gone from live site */}
                              {scan.resolved_details?.length > 0 && (
                                <div>
                                  <div className="text-xs font-semibold text-emerald-600 uppercase mb-1 flex items-center gap-1">
                                    <CheckCircle className="size-3" /> Confirmed Resolved ({scan.resolved_details.length})
                                  </div>
                                  <div className="space-y-1 opacity-50">
                                    {scan.resolved_details.map((item, i) => (
                                      <div key={i} className="flex items-center justify-between text-xs px-2 py-1 rounded bg-emerald-50 border border-emerald-100" data-testid={`resolved-issue-${i}`}>
                                        <div className="flex-1">
                                          <span className="font-medium text-emerald-700 line-through">{item.issue}</span>
                                          <span className="text-emerald-500 ml-2 text-xs">{item.fixed_note}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline" className="text-xs capitalize border-emerald-200 text-emerald-600">{item.category}</Badge>
                                          <CheckCircle className="size-3 text-emerald-500" />
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </>
                          );
                        })()}
                        {/* Recommendations (system_scans format) */}
                        {recommendations.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-gray-600 uppercase mb-1">Recommendations</div>
                            <div className="space-y-1">
                              {recommendations.map((rec, i) => (
                                <div key={i} className="text-xs px-2 py-1.5 rounded bg-white">
                                  <div className="flex items-center gap-2 mb-0.5">
                                    <Badge variant="outline" className={`text-xs ${rec.priority === 'high' ? 'border-red-300 text-red-600' : 'border-yellow-300 text-yellow-600'}`}>
                                      {rec.priority}
                                    </Badge>
                                    <span className="font-medium text-gray-700">{rec.title}</span>
                                  </div>
                                  {rec.solution && <div className="text-gray-500 ml-4">{rec.solution}</div>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {/* Inline repairs */}
                        {inlineReps.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-gray-600 uppercase mb-1">Repairs Ready</div>
                            {inlineReps.map((r, i) => (
                              <div key={i} className="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-white mb-1">
                                <div>
                                  <span className="font-medium text-gray-700">{r.test}</span>
                                  <span className="text-gray-400 ml-2">{r.description}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Badge variant="outline" className="text-xs">{r.category}</Badge>
                                  <RepairStatusBadge status={r.status} />
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Repairs Summary */}
      {Object.keys(categoryGroups).length > 0 && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Wrench className="size-4" /> All Repairs ({allRepairs.length})</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(categoryGroups).map(([cat, items]) => (
                <div key={cat}>
                  <div className="flex items-center gap-2 mb-2">
                    <Shield className="size-4 text-gray-400" />
                    <span className="text-sm font-semibold capitalize">{cat}</span>
                    <Badge variant="secondary" className="text-xs">{items.length}</Badge>
                  </div>
                  <div className="space-y-1 ml-6">
                    {items.map((r, i) => (
                      <div key={i} className="flex items-center justify-between text-sm px-2 py-1.5 rounded hover:bg-gray-50">
                        <span className="text-gray-700">{r.test || r.description}</span>
                        <RepairStatusBadge status={r.status} />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ─── Clients List View ─── */
function ClientsTab({ token }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedClient, setSelectedClient] = useState(null);

  const loadClients = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/admin/mission-control/clients`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setClients(data.clients || []);
    } catch (e) {
      console.error('Failed to load clients:', e);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadClients(); }, [loadClients]);

  if (selectedClient) {
    return <ClientDetail profileId={selectedClient} token={token} onBack={() => setSelectedClient(null)} />;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle data-testid="clients-tab-title">Client Profiles ({clients.length})</CardTitle>
          <Button variant="outline" size="sm" onClick={loadClients} disabled={loading}>
            <RefreshCw className={`size-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-center py-8 text-gray-500">Loading clients…</div>
        ) : clients.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No clients found</div>
        ) : (
          <div className="space-y-2">
            {clients.map((client) => (
              <button
                key={client.profile_id || client.business_name}
                className="w-full flex items-center justify-between p-4 rounded-lg border hover:border-pink-300 hover:bg-pink-50/50 transition-colors text-left"
                onClick={() => client.profile_id && setSelectedClient(client.profile_id)}
                data-testid={`client-row-${client.profile_id}`}
              >
                <div className="flex items-center gap-4">
                  <div className="size-10 rounded-full bg-gradient-to-br from-pink-400 to-orange-400 flex items-center justify-center text-white font-bold text-sm">
                    {(client.business_name || '?')[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="font-medium text-gray-900">{client.business_name}</div>
                    <div className="text-xs text-gray-500 flex items-center gap-2">
                      {client.website_url ? (
                        <span className="flex items-center gap-1"><Globe className="size-3" /> {client.website_url}</span>
                      ) : (
                        <span className="text-gray-400">No website</span>
                      )}
                      {client.email && <span>&middot; {client.email}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {client.latest_scan && (
                    <ScoreBadge score={client.latest_scan.overall_score} />
                  )}
                  <div className="text-right text-xs">
                    <div className="text-gray-600">{client.total_scans} scans</div>
                    <div className="text-green-600">{client.total_repairs} repairs</div>
                  </div>
                  {client.plan && <Badge variant="outline" className="text-xs">{client.plan}</Badge>}
                  <Badge className={client.status === 'active' ? 'bg-green-500 text-white' : 'bg-gray-400 text-white'}>
                    {client.status || 'N/A'}
                  </Badge>
                  {client.email && (
                    <a
                      href={`/admin/customer/${encodeURIComponent(client.email)}`}
                      data-testid={`client-360-link-${client.profile_id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="text-xs px-2 py-1 rounded border border-pink-300 text-pink-700 hover:bg-pink-50 flex items-center gap-1"
                      title="Open Customer 360°"
                    >
                      <ExternalLink className="size-3" /> 360°
                    </a>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


/**
 * AUREM Admin Mission Control
 */
const AdminMissionControl = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);

  const getToken = () => {
    try {
      const { getPlatformToken } = require('../utils/secureTokenStore');
      return getPlatformToken() || localStorage.getItem('admin_key') || '';
    } catch {
      return localStorage.getItem('admin_key') || '';
    }
  };

  // State
  const [dashboard, setDashboard] = useState(null);
  const [overview, setOverview] = useState(null);
  const [pixelHealth, setPixelHealth] = useState(null);
  const [sentinel, setSentinel] = useState(null);
  const [services, setServices] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);

  // Add API key form
  const [newKey, setNewKey] = useState({ service_id: '', api_key: '', notes: '', monthly_spend_limit: '' });

  // Fetch data with JWT auth
  const fetchWithAuth = async (endpoint) => {
    const token = getToken();
    const response = await fetch(`${API_URL}${endpoint}`, {
      headers: { 'Authorization': `Bearer ${token}`, 'X-Admin-Key': token }
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  };

  // Load dashboard + overview
  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const [dashData, overviewData, sentinelData, pixelData] = await Promise.all([
        fetchWithAuth('/api/admin/mission-control/dashboard').catch(() => null),
        fetchWithAuth('/api/admin/mission-control/overview').catch(() => null),
        fetchWithAuth('/api/admin/sentinel/overview').catch(() => null),
        fetchWithAuth('/api/admin/mission-control/pixel-health').catch(() => null),
      ]);
      if (dashData) setDashboard(dashData);
      if (overviewData) setOverview(overviewData);
      if (sentinelData) setSentinel(sentinelData);
      if (pixelData) setPixelHealth(pixelData);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadServices = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/services');
      if (data.format === 'TOON') {
        const lines = data.data.split('\n').slice(1);
        const parsed = lines.map(line => {
          const parts = line.trim().split(', ');
          return { id: parts[0], category: parts[1], provider: parts[2], cost: parts[3], status: parts[4], tiers: parts[5] };
        });
        setServices(parsed);
      }
    } catch (error) { console.error('Failed to load services:', error); }
    finally { setLoading(false); }
  }, []);

  const loadApiKeys = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/api-keys');
      if (data.format === 'TOON') {
        const lines = data.data.split('\n').slice(1);
        const parsed = lines.map(line => {
          const parts = line.trim().split(', ');
          return { service: parts[0], preview: parts[1], status: parts[2], calls: parts[3], spend: parts[4], lastUsed: parts[5] };
        });
        setApiKeys(parsed);
      }
    } catch (error) { console.error('Failed to load API keys:', error); }
    finally { setLoading(false); }
  }, []);

  const loadSubscriptions = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/subscriptions');
      if (data.format === 'TOON') {
        const lines = data.data.split('\n').slice(1);
        const parsed = lines.map(line => {
          const parts = line.trim().split(', ');
          return { id: parts[0], user: parts[1], tier: parts[2], status: parts[3], amount: parts[4], periodEnd: parts[5], usage: parts[6] };
        });
        setSubscriptions(parsed);
      }
    } catch (error) { console.error('Failed to load subscriptions:', error); }
    finally { setLoading(false); }
  }, []);

  const addApiKey = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/admin/mission-control/services/add-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getToken()}`, 'X-Admin-Key': getToken() },
        body: JSON.stringify(newKey)
      });
      if (!response.ok) throw new Error('Failed to add API key');
      setNewKey({ service_id: '', api_key: '', notes: '', monthly_spend_limit: '' });
      await loadApiKeys();
      await loadServices();
      alert('API key added successfully!');
    } catch (error) { console.error('Failed to add API key:', error); alert('Failed to add API key'); }
    finally { setLoading(false); }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-500';
      case 'no_keys': return 'bg-yellow-500';
      case 'paused': return 'bg-gray-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  useEffect(() => {
    if (!getToken()) return;
    switch (activeTab) {
      case 'dashboard': loadDashboard(); break;
      case 'services': loadServices(); break;
      case 'api-keys': loadApiKeys(); loadServices(); break;
      case 'subscriptions': loadSubscriptions(); break;
      default: break;
    }
  }, [activeTab, loadDashboard, loadSubscriptions, loadServices, loadApiKeys]);

  // iter 270 — keep the active tab's data auto-refreshing every 20s.
  // useMemo gives useLivePolling a STABLE fetcher reference per tab.
  const activeLoader = useMemo(() => {
    const map = {
      'dashboard': loadDashboard,
      'services': loadServices,
      'api-keys': loadServices,
      'subscriptions': loadSubscriptions,
    };
    return map[activeTab] || null;
  }, [activeTab, loadDashboard, loadServices, loadSubscriptions]);
  useLivePolling(activeLoader || (async () => {}), 20000);

  return (
    <div className="min-h-screen mission-control-bg p-4" data-testid="mission-control-root" style={{backgroundImage:"url('/assets/aurem-mission-bg.jpg')"}}>
      {/* Lighting shimmer overlay — futuristic sweep across entire dashboard */}
      <div aria-hidden="true" className="admin-shimmer" />
      <div className="max-w-7xl mx-auto space-y-6 relative" style={{zIndex:1}}>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="mission-control-title" style={{color:'#FFFFFF', textShadow:'0 2px 18px rgba(212,175,55,0.35)'}}>
              <Server className="size-8" style={{color:'#D4AF37'}} />
              AUREM Mission Control
            </h1>
            <p className="mt-1" style={{color:'rgba(232,224,208,0.75)', letterSpacing:'0.02em'}}>Manage clients, services, API keys & usage</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => window.location.href = '/dashboard'}
              className="flex items-center gap-2 border-orange-300 text-orange-600 hover:bg-orange-50"
              data-testid="go-ora-command-center"
            >
              <Zap className="size-4" /> ORA Command Center
            </Button>
            <Button variant="outline" onClick={() => {
              localStorage.removeItem('admin_key');
              localStorage.removeItem('platform_token');
              window.location.href = '/admin/login';
            }}>
              Logout
            </Button>
          </div>
        </div>

        {/* Tabs — horizontally scrollable on narrow screens, no crush */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div
            className="aurem-admin-tabs-scroll"
            style={{
              overflowX: 'auto',
              overflowY: 'hidden',
              WebkitOverflowScrolling: 'touch',
              scrollbarWidth: 'thin',
              scrollbarColor: 'rgba(212,175,55,0.45) transparent',
              marginBottom: 8,
            }}
          >
            <style>{`
              .aurem-admin-tabs-scroll::-webkit-scrollbar { height: 6px; }
              .aurem-admin-tabs-scroll::-webkit-scrollbar-track { background: transparent; }
              .aurem-admin-tabs-scroll::-webkit-scrollbar-thumb {
                background: rgba(212,175,55,0.45);
                border-radius: 999px;
              }
              .aurem-admin-tabs-scroll::-webkit-scrollbar-thumb:hover {
                background: rgba(212,175,55,0.7);
              }
            `}</style>
            <TabsList
              className="inline-flex w-auto min-w-full gap-1"
              data-testid="mission-control-tabs"
              style={{ flexWrap: 'nowrap' }}
            >
              <TabsTrigger value="dashboard" data-testid="tab-dashboard" className="whitespace-nowrap">
                <BarChart3 className="size-4 mr-1" /> Dashboard
              </TabsTrigger>
              <TabsTrigger value="clients" data-testid="tab-clients" className="whitespace-nowrap">
                <Globe className="size-4 mr-1" /> Clients
              </TabsTrigger>
              <TabsTrigger value="services" data-testid="tab-services" className="whitespace-nowrap">
                <Database className="size-4 mr-1" /> Services
              </TabsTrigger>
              <TabsTrigger value="api-keys" data-testid="tab-api-keys" className="whitespace-nowrap">
                <Key className="size-4 mr-1" /> API Keys
              </TabsTrigger>
              <TabsTrigger value="business-ids" data-testid="tab-biz-ids" className="whitespace-nowrap">
                <Key className="size-4 mr-1" /> Biz IDs
              </TabsTrigger>
              <TabsTrigger value="subscriptions" data-testid="tab-subscriptions" className="whitespace-nowrap">
                <Users className="size-4 mr-1" /> Subs
              </TabsTrigger>
              <TabsTrigger value="analytics" data-testid="tab-analytics" className="whitespace-nowrap">
                <Activity className="size-4 mr-1" /> Analytics
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-4" data-testid="dashboard-tab-content">
            {/* Real metrics from overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Active Clients</CardTitle>
                  <Users className="size-4 text-gray-400" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold" data-testid="metric-active-clients">{overview?.active_clients ?? '--'}</div>
                  <p className="text-xs text-gray-500 mt-1">{overview?.total_clients ?? 0} total profiles</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Total Scans</CardTitle>
                  <Search className="size-4 text-gray-400" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold" data-testid="metric-total-scans">{overview?.total_scans ?? '--'}</div>
                  <p className="text-xs text-gray-500 mt-1">Avg score: {overview?.avg_scan_score ?? '--'}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Repairs Applied</CardTitle>
                  <Wrench className="size-4 text-gray-400" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600" data-testid="metric-total-repairs">{overview?.total_repairs ?? '--'}</div>
                  <p className="text-xs text-green-600 mt-1">Auto-deployed fixes</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Platform Users</CardTitle>
                  <Users className="size-4 text-gray-400" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold" data-testid="metric-total-users">{overview?.total_users ?? '--'}</div>
                  <p className="text-xs text-gray-500 mt-1">Registered accounts</p>
                </CardContent>
              </Card>
              <Card
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => { window.location.href = '/admin/sentinel'; }}
                data-testid="sentinel-kpi-card"
              >
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Sentinel · Errors (1h / 24h)</CardTitle>
                  <Shield className={`size-4 ${(sentinel?.errors_1h ?? 0) > 0 ? 'text-red-500' : (sentinel?.errors_24h ?? 0) > 0 ? 'text-amber-500' : 'text-green-500'}`} />
                </CardHeader>
                <CardContent>
                  <div
                    className={`text-2xl font-bold ${(sentinel?.errors_1h ?? 0) > 0 ? 'text-red-600' : (sentinel?.errors_24h ?? 0) > 0 ? 'text-amber-600' : 'text-green-600'}`}
                    data-testid="metric-sentinel-errors"
                  >
                    {sentinel?.errors_1h ?? 0} / {sentinel?.errors_24h ?? 0}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {sentinel?.top_types?.[0] ? `Top: ${sentinel.top_types[0].type} (${sentinel.top_types[0].count})` : 'All clear'}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* iter 290 — Pixel Health Strip (P0) */}
            <Card data-testid="pixel-health-card" className="border-2 border-amber-200 bg-gradient-to-r from-amber-50 to-white">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Zap className="size-4 text-amber-600" /> Pixel Deployment Health
                  <span className="ml-auto text-xs font-normal text-gray-500">last updated {pixelHealth?.timestamp ? new Date(pixelHealth.timestamp).toLocaleTimeString() : '--'}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div data-testid="pixel-installed-24h">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Installed (24h)</div>
                    <div className="text-2xl font-bold text-emerald-600">{pixelHealth?.pixel_installed_24h ?? '--'}</div>
                  </div>
                  <div data-testid="pixel-installed-total">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Installed (all-time)</div>
                    <div className="text-2xl font-bold">{pixelHealth?.pixel_installed_all_time ?? '--'}</div>
                    <div className="text-xs text-gray-500">of {pixelHealth?.total_workspaces ?? 0} workspaces · {pixelHealth?.pixel_install_pct ?? 0}%</div>
                  </div>
                  <div data-testid="pixel-pending-patches">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Pending Patches</div>
                    <div className={`text-2xl font-bold ${(pixelHealth?.pending_patches ?? 0) > 0 ? 'text-amber-600' : 'text-gray-400'}`}>
                      {pixelHealth?.pending_patches ?? '--'}
                    </div>
                  </div>
                  <div data-testid="pixel-applied-patches">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Applied Patches</div>
                    <div className="text-2xl font-bold text-emerald-600">{pixelHealth?.applied_patches ?? '--'}</div>
                    <div className="text-xs text-red-500">{pixelHealth?.failed_patches ?? 0} failed</div>
                  </div>
                  <div data-testid="pixel-avg-install-time">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Avg Install Time</div>
                    <div className="text-2xl font-bold">
                      {pixelHealth?.avg_install_time_minutes != null ? `${pixelHealth.avg_install_time_minutes}m` : '--'}
                    </div>
                    <div className="text-xs text-gray-500">signup → verified</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Quick Actions */}
            <Card>
              <CardHeader><CardTitle>Quick Actions</CardTitle></CardHeader>
              <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Button onClick={() => setActiveTab('clients')} variant="outline" data-testid="quick-action-clients">
                  <Globe className="size-4 mr-2" /> View Clients
                </Button>
                <Button onClick={() => setActiveTab('api-keys')} variant="outline">
                  <Key className="size-4 mr-2" /> Add API Key
                </Button>
                <Button onClick={() => setActiveTab('services')} variant="outline">
                  <Database className="size-4 mr-2" /> View Services
                </Button>
                <Button onClick={() => setActiveTab('subscriptions')} variant="outline">
                  <Users className="size-4 mr-2" /> Subscriptions
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Clients Tab */}
          <TabsContent value="clients" data-testid="clients-tab-content">
            <ClientsTab token={getToken()} />
          </TabsContent>

          {/* Services Tab */}
          <TabsContent value="services">
            <Card>
              <CardHeader>
                <CardTitle>Service Registry</CardTitle>
                <p className="text-sm text-gray-600">All available third-party services</p>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">Loading…</div>
                ) : (
                  <div className="space-y-3">
                    {services.map((service, idx) => (
                      <div key={service.id || idx} className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50">
                        <div className="flex-1">
                          <div className="font-medium">{service.id}</div>
                          <div className="text-sm text-gray-600">{service.provider} &bull; {service.category} &bull; {service.cost}</div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge className={getStatusColor(service.status)}>{service.status}</Badge>
                          <span className="text-xs text-gray-500">{service.tiers}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* API Keys Tab */}
          <TabsContent value="api-keys" className="space-y-4">
            <Card>
              <CardHeader><CardTitle>Add API Key</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Service</label>
                    <select className="w-full mt-1 p-2 border rounded" value={newKey.service_id} onChange={(e) => setNewKey({ ...newKey, service_id: e.target.value })}>
                      <option value="">Select service…</option>
                      {services.map((s, idx) => <option key={s.id || idx} value={s.id}>{s.id}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">API Key</label>
                    <Input type="password" placeholder="sk-proj-..." value={newKey.api_key} onChange={(e) => setNewKey({ ...newKey, api_key: e.target.value })} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Monthly Spend Limit (optional)</label>
                    <Input type="number" placeholder="1000.00" value={newKey.monthly_spend_limit} onChange={(e) => setNewKey({ ...newKey, monthly_spend_limit: e.target.value })} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Notes (optional)</label>
                    <Input placeholder="Production key" value={newKey.notes} onChange={(e) => setNewKey({ ...newKey, notes: e.target.value })} />
                  </div>
                </div>
                <Button onClick={addApiKey} disabled={!newKey.service_id || !newKey.api_key || loading} className="w-full">
                  {loading ? 'Adding...' : 'Add API Key'}
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Existing API Keys</CardTitle></CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">Loading…</div>
                ) : apiKeys.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">No API keys added yet</div>
                ) : (
                  <div className="space-y-3">
                    {apiKeys.map((key, idx) => (
                      <div key={key.service || idx} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex-1">
                          <div className="font-medium">{key.service}</div>
                          <div className="text-sm text-gray-600 font-mono">{key.preview}</div>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-gray-600">{key.calls} calls</span>
                          <span className="font-medium">${key.spend}</span>
                          <Badge className={getStatusColor(key.status)}>{key.status}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Subscriptions Tab */}
          <TabsContent value="subscriptions">
            <Card>
              <CardHeader><CardTitle>All Subscriptions</CardTitle></CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">Loading…</div>
                ) : subscriptions.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">No active subscriptions</div>
                ) : (
                  <div className="space-y-3">
                    {subscriptions.map((sub, idx) => (
                      <div key={sub.id || idx} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex-1">
                          <div className="font-medium">{sub.user}</div>
                          <div className="text-sm text-gray-600">{sub.usage}</div>
                        </div>
                        <div className="flex items-center gap-4">
                          <Badge>{sub.tier}</Badge>
                          <span className="font-medium">${sub.amount}/mo</span>
                          <Badge className={getStatusColor(sub.status)}>{sub.status}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Analytics Tab */}
          <TabsContent value="analytics">
            <Card>
              <CardHeader><CardTitle>Usage Analytics</CardTitle></CardHeader>
              <CardContent>
                <div className="text-center py-8 text-gray-500">
                  Analytics dashboard coming soon…
                  <br />
                  <span className="text-sm">View metrics at: <code className="bg-gray-100 px-2 py-1 rounded">/metrics</code></span>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Business IDs Tab */}
          <TabsContent value="business-ids">
            <AdminBusinessIdsEmbed token={getToken()} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminMissionControl;
