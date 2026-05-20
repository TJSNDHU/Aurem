/**
 * Leads Dashboard
 * Shows captured leads with today's impact metrics
 * Phase A: Lead Capture System
 */

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import useAuthFetch from '../hooks/useAuthFetch';

const LeadsDashboard = () => {
  const { apiFetch } = useAuthFetch();
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  // Lead enrichment (moved from sidebar — now inline per-card + bulk select)
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [enrichingIds, setEnrichingIds] = useState(new Set());
  const [toastMsg, setToastMsg] = useState(null);

  // Adaptive ORA mode toggle (shadow / automation)
  const [oraMode, setOraMode] = useState('shadow');
  const [oraBuckets, setOraBuckets] = useState({});
  const [oraModeBusy, setOraModeBusy] = useState(false);

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  const ENRICH_SCORE_THRESHOLD = 70;  // only leads at or above this qualify for manual Enrich
  function leadScore(l) {
    return l?.score ?? l?.ora_score ?? l?.value_estimate ?? 0;
  }

  // Adaptive ORA bucket visuals (shadow mode P1 — colors only, no actions)
  function bucketColorBg(b) {
    return ({
      CLOSER_NOW: 'rgba(239,68,68,0.12)',
      INTENSIFY:  'rgba(245,158,11,0.12)',
      CONTINUE:   'rgba(74,222,128,0.10)',
      SLOW:       'rgba(156,163,175,0.10)',
      HALT:       'rgba(107,114,128,0.08)',
    })[b] || 'rgba(156,163,175,0.08)';
  }
  function bucketColorFg(b) {
    return ({
      CLOSER_NOW: '#ef4444',
      INTENSIFY:  '#f59e0b',
      CONTINUE:   '#16a34a',
      SLOW:       '#6b7280',
      HALT:       '#9ca3af',
    })[b] || '#6b7280';
  }
  function bucketEmoji(b) {
    return ({
      CLOSER_NOW: '🔥',
      INTENSIFY:  '⚡',
      CONTINUE:   '✓',
      SLOW:       '⏳',
      HALT:       '⏸',
    })[b] || '○';
  }

  function showToast(msg, type = "success") {
    setToastMsg({ msg, type });
    setTimeout(() => setToastMsg(null), 3200);
  }
  function toggleSelect(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  async function enrichLead(leadId) {
    if (!leadId || enrichingIds.has(leadId)) return;
    setEnrichingIds((p) => new Set(p).add(leadId));
    try {
      const r = await apiFetch(`/api/enrichment/enrich/${leadId}`, {
        method: "POST",
        body: JSON.stringify({ include_website: true, include_social: true, include_firmographics: true }),
      });
      const d = await r.json();
      if (r.ok) {
        showToast(`Enriched: ${d.lead_name || leadId.slice(0, 8)}`, "success");
        fetchLeads();
      } else {
        showToast(`Enrich failed: ${d.detail || r.status}`, "error");
      }
    } catch (e) { showToast(`Enrich error: ${e.message}`, "error"); }
    setEnrichingIds((p) => { const n = new Set(p); n.delete(leadId); return n; });
  }
  async function enrichSelected() {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    showToast(`Queuing ${ids.length} lead${ids.length !== 1 ? "s" : ""} for enrichment…`, "success");
    for (const id of ids) {
      await enrichLead(id);
    }
    setSelectedIds(new Set());
  }

  useEffect(() => {
    fetchLeads();
    fetchStats();
    fetchOraConfig();
    // Refresh every 30 seconds
    const interval = setInterval(() => {
      fetchLeads();
      fetchStats();
      fetchOraConfig();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchOraConfig = async () => {
    try {
      const r = await apiFetch('/api/conviction/config');
      if (!r.ok) return;
      const d = await r.json();
      setOraMode(d.mode || 'shadow');
      setOraBuckets(d.bucket_counts || {});
    } catch { /* silent */ }
  };

  const toggleOraMode = async () => {
    const next = oraMode === 'automation' ? 'shadow' : 'automation';
    const confirmMsg = next === 'automation'
      ? '⚠️ Enable Adaptive ORA AUTOMATION?\n\n• Hot leads (score ≥90) will auto-handoff to Closer agent and wake it immediately.\n• Cold leads (score <20) will auto-halt (stage=halted, status=do_not_contact).\n\nYou can flip back to Shadow Mode anytime.'
      : 'Switch back to SHADOW mode?\n\nScores will keep updating but no agents will auto-fire.';
    if (!window.confirm(confirmMsg)) return;
    setOraModeBusy(true);
    try {
      const r = await apiFetch('/api/conviction/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: next }),
      });
      const d = await r.json();
      if (r.ok && d.mode) {
        setOraMode(d.mode);
        showToast(`Adaptive ORA → ${d.mode.toUpperCase()}`, 'success');
      } else {
        showToast(`Mode switch failed: ${d.detail || 'unknown'}`, 'error');
      }
    } catch (e) {
      showToast(`Network error: ${e.message}`, 'error');
    }
    setOraModeBusy(false);
  };

  const fetchLeads = async () => {
    try {
      const response = await fetch(`${API_URL}/api/leads`);
      const data = await response.json();
      if (data.success) {
        setLeads(data.leads);
      }
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/leads/stats?period=today`);
      const data = await response.json();
      if (data.success) {
        setStats(data.stats);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const updateLeadStatus = async (leadId, newStatus) => {
    try {
      const response = await fetch(`${API_URL}/api/leads/${leadId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      
      if (response.ok) {
        // Refresh leads
        fetchLeads();
        fetchStats();
      }
    } catch (err) {
      console.error('Failed to update lead:', err);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      new: 'bg-blue-500',
      contacted: 'bg-yellow-500',
      converted: 'bg-green-500',
      lost: 'bg-gray-500'
    };
    return colors[status] || 'bg-gray-500';
  };

  const getIntentIcon = (intentType) => {
    const icons = {
      booking: '📅',
      purchase: '🛍️',
      inquiry: '💬'
    };
    return icons[intentType] || '💡';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full size-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading leads…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center text-red-600">
          <p>Error loading leads: {error}</p>
          <Button onClick={() => window.location.reload()} className="mt-4">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Leads Dashboard</h1>
            <p className="text-gray-600 mt-2">AI-captured leads from your conversations</p>
          </div>

          {/* Adaptive ORA mode toggle */}
          <div
            className={`rounded-xl border-2 p-4 min-w-[320px] transition-all ${
              oraMode === 'automation'
                ? 'bg-gradient-to-br from-amber-50 to-orange-50 border-amber-400'
                : 'bg-gradient-to-br from-slate-50 to-gray-50 border-gray-300'
            }`}
            data-testid="adaptive-ora-toggle-card"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{oraMode === 'automation' ? '🤖' : '👁'}</span>
                  <span className="text-xs font-bold tracking-[1.5px] uppercase text-gray-700">Adaptive ORA</span>
                  <span
                    className={`text-[10px] font-black px-2 py-0.5 rounded-full tracking-wider ${
                      oraMode === 'automation'
                        ? 'bg-amber-500 text-white'
                        : 'bg-gray-400 text-white'
                    }`}
                    data-testid="adaptive-ora-mode-badge"
                  >
                    {oraMode === 'automation' ? 'AUTO FIRING' : 'SHADOW'}
                  </span>
                </div>
                <p className="text-[11px] text-gray-600 mt-1 max-w-[220px]">
                  {oraMode === 'automation'
                    ? 'Hot leads auto-handoff to Closer, cold leads auto-halt.'
                    : 'Scores computed silently. No agent auto-fires.'}
                </p>
              </div>
              <button
                onClick={toggleOraMode}
                disabled={oraModeBusy}
                data-testid="adaptive-ora-toggle-btn"
                className={`relative inline-flex h-7 w-14 shrink-0 cursor-pointer rounded-full border-2 transition-colors duration-200 focus:outline-none ${
                  oraMode === 'automation'
                    ? 'bg-amber-500 border-amber-500'
                    : 'bg-gray-200 border-gray-300'
                } ${oraModeBusy ? 'opacity-50 cursor-wait' : ''}`}
                aria-label="Toggle Adaptive ORA automation"
              >
                <span
                  className={`pointer-events-none inline-block size-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ${
                    oraMode === 'automation' ? 'translate-x-7' : 'translate-x-0.5'
                  } mt-[1px]`}
                />
              </button>
            </div>
            {/* Bucket counts */}
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-200/60 flex-wrap">
              {[
                { key: 'CLOSER_NOW', label: '🔥 Hot',    color: 'text-red-600' },
                { key: 'INTENSIFY',  label: '⚡ Warm',   color: 'text-amber-600' },
                { key: 'CONTINUE',   label: '✓ Drip',   color: 'text-green-600' },
                { key: 'SLOW',       label: '⏳ Slow',   color: 'text-gray-500' },
                { key: 'HALT',       label: '○ Halted', color: 'text-gray-400' },
              ].map((b) => (
                <div key={b.key} className="flex items-center gap-1" data-testid={`bucket-count-${b.key}`}>
                  <span className={`text-[11px] font-semibold ${b.color}`}>{b.label}</span>
                  <span className="text-[11px] font-mono text-gray-700">{oraBuckets[b.key] || 0}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-blue-100 text-sm">Total Leads Today</p>
                    <h3 className="text-3xl font-bold mt-2">{stats.total_leads}</h3>
                  </div>
                  <div className="text-4xl opacity-50">💰</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-green-500 to-green-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-green-100 text-sm">Converted</p>
                    <h3 className="text-3xl font-bold mt-2">{stats.converted}</h3>
                  </div>
                  <div className="text-4xl opacity-50">✅</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-purple-100 text-sm">Estimated Value</p>
                    <h3 className="text-3xl font-bold mt-2">${stats.total_value.toFixed(0)}</h3>
                  </div>
                  <div className="text-4xl opacity-50">💵</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-orange-500 to-orange-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-orange-100 text-sm">Conversion Rate</p>
                    <h3 className="text-3xl font-bold mt-2">{stats.conversion_rate}%</h3>
                  </div>
                  <div className="text-4xl opacity-50">📈</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Leads List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Recent Leads</span>
              <Badge variant="outline">{leads.length} total</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Bulk actions — enrich selected */}
            {selectedIds.size > 0 && (
              <div
                className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-md px-4 py-2 mb-4"
                data-testid="leads-bulk-bar"
              >
                <span className="text-sm text-amber-900 font-medium">
                  {selectedIds.size} selected · only leads with score ≥ {ENRICH_SCORE_THRESHOLD} are eligible
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setSelectedIds(new Set())}
                  >Clear</Button>
                  <Button
                    size="sm"
                    className="bg-amber-600 hover:bg-amber-700 text-white"
                    onClick={enrichSelected}
                    data-testid="leads-bulk-enrich-btn"
                  >⬡ Enrich Selected ({selectedIds.size})</Button>
                </div>
              </div>
            )}
            {leads.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-6xl mb-4">🎯</div>
                <p className="text-lg">No leads captured yet</p>
                <p className="text-sm mt-2">Your AI will automatically capture leads from conversations</p>
              </div>
            ) : (
              <div className="space-y-4">
                {leads.map((lead) => {
                  const id = lead.lead_id;
                  const score = leadScore(lead);
                  const qualifies = score >= ENRICH_SCORE_THRESHOLD;
                  const isChecked = selectedIds.has(id);
                  const isEnriching = enrichingIds.has(id);
                  const isEnriched = !!(lead.enrichment_data || lead.enriched_at);
                  return (
                  <div
                    key={id}
                    className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 cursor-pointer" onClick={() => setSelectedLead(lead)}>
                        <div className="flex items-center gap-3 mb-2">
                          {qualifies && (
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => { e.stopPropagation(); toggleSelect(id); }}
                              onClick={(e) => e.stopPropagation()}
                              className="size-4 cursor-pointer"
                              data-testid={`lead-select-${id}`}
                              title="Select for bulk enrich"
                            />
                          )}
                          <span className="text-2xl">
                            {getIntentIcon(lead.interest?.intent_type)}
                          </span>
                          <div>
                            <h3 className="font-semibold text-lg">
                              {lead.customer?.name || 'Unknown'}
                            </h3>
                            <p className="text-sm text-gray-600">
                              {lead.interest?.intent_type || 'General inquiry'}
                            </p>
                          </div>
                          {/* Adaptive ORA conviction pill (shadow mode) */}
                          {typeof lead.conviction_score === 'number' && (
                            <span
                              data-testid={`conviction-pill-${id}`}
                              className="ml-auto flex flex-col items-end gap-0.5"
                              title={`Shadow mode · last signal: ${lead.last_signal || 'none'}`}
                            >
                              <span
                                className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
                                style={{
                                  background: bucketColorBg(lead.conviction_bucket),
                                  color: bucketColorFg(lead.conviction_bucket),
                                  border: `1px solid ${bucketColorFg(lead.conviction_bucket)}33`,
                                }}
                              >
                                {bucketEmoji(lead.conviction_bucket)} {lead.conviction_bucket || 'NEW'}
                              </span>
                              <span className="text-[10px] text-gray-500">
                                score {Math.round(lead.conviction_score)}
                              </span>
                            </span>
                          )}
                        </div>

                        <div className="grid grid-cols-2 gap-4 text-sm mt-3">
                          <div>
                            <span className="text-gray-500">Phone:</span>
                            <span className="ml-2 font-medium">
                              {lead.customer?.phone || 'Not provided'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-500">Email:</span>
                            <span className="ml-2 font-medium">
                              {lead.customer?.email || 'Not provided'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-500">Value:</span>
                            <span className="ml-2 font-medium text-green-600">
                              ${lead.value_estimate?.toFixed(2) || '0.00'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-500">Captured:</span>
                            <span className="ml-2 font-medium">
                              {new Date(lead.captured_at).toLocaleString()}
                            </span>
                          </div>
                        </div>

                        {lead.interest?.preferred_time && (
                          <div className="mt-2 text-sm">
                            <span className="text-gray-500">Preferred time:</span>
                            <span className="ml-2 font-medium">
                              {lead.interest.preferred_time}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="ml-4">
                        <Badge className={`${getStatusColor(lead.status)} text-white`}>
                          {lead.status}
                        </Badge>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 mt-4 pt-4 border-t">
                      {lead.status === 'new' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            updateLeadStatus(lead.lead_id, 'contacted');
                          }}
                        >
                          Mark Contacted
                        </Button>
                      )}
                      {(lead.status === 'new' || lead.status === 'contacted') && (
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={(e) => {
                            e.stopPropagation();
                            updateLeadStatus(lead.lead_id, 'converted');
                          }}
                        >
                          Mark Converted
                        </Button>
                      )}
                      {lead.customer?.phone && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(`tel:${lead.customer.phone}`);
                          }}
                        >
                          📞 Call
                        </Button>
                      )}
                      {lead.customer?.email && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(`mailto:${lead.customer.email}`);
                          }}
                        >
                          📧 Email
                        </Button>
                      )}
                      {/* Enrich button — only on qualifying leads (score >= 70) */}
                      {qualifies && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isEnriching}
                          onClick={(e) => { e.stopPropagation(); enrichLead(id); }}
                          data-testid={`lead-enrich-${id}`}
                          className="border-amber-500 text-amber-700 hover:bg-amber-50"
                        >
                          {isEnriching ? "⟳ Enriching…" : isEnriched ? "⬡ Re-enrich" : "⬡ Enrich"}
                        </Button>
                      )}
                    </div>
                  </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Toast */}
        {toastMsg && (
          <div
            data-testid="leads-toast"
            className={`fixed top-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm ${
              toastMsg.type === "error" ? "bg-red-600 text-white" : "bg-green-600 text-white"
            }`}
          >
            {toastMsg.msg}
          </div>
        )}

        {/* Lead Detail Modal */}
        {selectedLead && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
            onClick={() => setSelectedLead(null)}
          >
            <div
              className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between mb-4">
                <h2 className="text-2xl font-bold">Lead Details</h2>
                <button
                  onClick={() => setSelectedLead(null)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Customer Information</h3>
                  <div className="bg-gray-50 p-4 rounded">
                    <p><strong>Name:</strong> {selectedLead.customer?.name || 'Unknown'}</p>
                    <p><strong>Email:</strong> {selectedLead.customer?.email || 'Not provided'}</p>
                    <p><strong>Phone:</strong> {selectedLead.customer?.phone || 'Not provided'}</p>
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">Lead Information</h3>
                  <div className="bg-gray-50 p-4 rounded">
                    <p><strong>Intent:</strong> {selectedLead.interest?.intent_type || 'General'}</p>
                    <p><strong>Confidence:</strong> {(selectedLead.ai_confidence * 100).toFixed(0)}%</p>
                    <p><strong>Estimated Value:</strong> ${selectedLead.value_estimate?.toFixed(2)}</p>
                    <p><strong>Status:</strong> <Badge className={getStatusColor(selectedLead.status)}>{selectedLead.status}</Badge></p>
                  </div>
                </div>

                {selectedLead.transcript && selectedLead.transcript.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Conversation Transcript</h3>
                    <div className="bg-gray-50 p-4 rounded max-h-64 overflow-y-auto space-y-2">
                      {selectedLead.transcript.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`p-2 rounded ${
                            msg.role === 'user' ? 'bg-blue-100' : 'bg-gray-200'
                          }`}
                        >
                          <p className="text-xs text-gray-600 mb-1">
                            {msg.role === 'user' ? 'Customer' : 'AI'}
                          </p>
                          <p className="text-sm">{msg.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  className="flex-1"
                  onClick={() => {
                    if (selectedLead.customer?.phone) {
                      window.open(`tel:${selectedLead.customer.phone}`);
                    }
                  }}
                  disabled={!selectedLead.customer?.phone}
                >
                  📞 Call Customer
                </Button>
                <Button
                  className="flex-1"
                  variant="outline"
                  onClick={() => {
                    if (selectedLead.customer?.email) {
                      window.open(`mailto:${selectedLead.customer.email}`);
                    }
                  }}
                  disabled={!selectedLead.customer?.email}
                >
                  📧 Send Email
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LeadsDashboard;
