/**
 * Fraud Prevention Dashboard - Admin Panel Component
 * Shows fraud statistics, recent checks, and blocked entities
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Shield, AlertTriangle, Ban, Eye, CheckCircle, XCircle, RefreshCw, Search } from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Colors
const C = {
  bg: '#FDF9F9',
  card: '#FFFFFF',
  primary: '#F8A5B8',
  text: '#2D2A2E',
  textMuted: '#6B6B6B',
  green: '#22c55e',
  red: '#ef4444',
  yellow: '#f59e0b',
  border: '#E8E8E8'
};

export default function FraudDashboard() {
  const [stats, setStats] = useState(null);
  const [recentChecks, setRecentChecks] = useState([]);
  const [highRisk, setHighRisk] = useState([]);
  const [blockedEntities, setBlockedEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [blockForm, setBlockForm] = useState({ type: 'email', value: '', reason: '' });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, checksRes, highRiskRes, blockedRes] = await Promise.all([
        fetch(`${API}/api/fraud/admin/stats`),
        fetch(`${API}/api/fraud/admin/recent-checks?limit=30`),
        fetch(`${API}/api/fraud/admin/high-risk?min_score=40`),
        fetch(`${API}/api/fraud/admin/blocked`)
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (checksRes.ok) {
        const data = await checksRes.json();
        setRecentChecks(data.checks || []);
      }
      if (highRiskRes.ok) {
        const data = await highRiskRes.json();
        setHighRisk(data.high_risk_entities || []);
      }
      if (blockedRes.ok) {
        const data = await blockedRes.json();
        setBlockedEntities(data.blocked_entities || []);
      }
    } catch (error) {
      console.error('Failed to fetch fraud data:', error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleBlock = async (e) => {
    e.preventDefault();
    if (!blockForm.value.trim()) return;

    try {
      const res = await fetch(`${API}/api/fraud/admin/block?entity_type=${blockForm.type}&value=${encodeURIComponent(blockForm.value)}&reason=${encodeURIComponent(blockForm.reason)}`, {
        method: 'POST'
      });

      if (res.ok) {
        setBlockForm({ type: 'email', value: '', reason: '' });
        fetchData();
      }
    } catch (error) {
      console.error('Block failed:', error);
    }
  };

  const handleUnblock = async (type, value) => {
    try {
      const res = await fetch(`${API}/api/fraud/admin/unblock?entity_type=${type}&value=${encodeURIComponent(value)}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Unblock failed:', error);
    }
  };

  const getRiskColor = (score) => {
    if (score >= 70) return C.red;
    if (score >= 40) return C.yellow;
    return C.green;
  };

  const getRecommendationBadge = (rec) => {
    const colors = {
      block: { bg: '#fef2f2', text: '#dc2626', icon: XCircle },
      review: { bg: '#fffbeb', text: '#d97706', icon: AlertTriangle },
      allow: { bg: '#f0fdf4', text: '#16a34a', icon: CheckCircle }
    };
    const style = colors[rec] || colors.allow;
    const Icon = style.icon;

    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 500,
        background: style.bg,
        color: style.text
      }}>
        <Icon size={12} />
        {rec?.toUpperCase()}
      </span>
    );
  };

  if (loading && !stats) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: C.textMuted }}>
        <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
        Loading fraud data...
      </div>
    );
  }

  return (
    <div style={{ padding: 20, background: C.bg, minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Shield size={28} color={C.primary} />
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 600, color: C.text, margin: 0 }}>Fraud Prevention</h1>
            <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>Monitor and block suspicious activity</p>
          </div>
        </div>
        <button
          onClick={fetchData}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
            cursor: 'pointer',
            fontSize: 13
          }}
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
          <StatCard title="Checks (24h)" value={stats.total_checks_24h} icon={Eye} color="#3b82f6" />
          <StatCard title="Checks (7d)" value={stats.total_checks_7d} icon={Search} color="#8b5cf6" />
          <StatCard title="Blocked (24h)" value={stats.blocked_24h} icon={Ban} color={C.red} />
          <StatCard title="Needs Review" value={stats.review_24h} icon={AlertTriangle} color={C.yellow} />
          <StatCard title="Blocked Entities" value={stats.blocked_entities} icon={Shield} color={C.primary} />
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, borderBottom: `1px solid ${C.border}`, paddingBottom: 12 }}>
        {['overview', 'high-risk', 'blocked', 'block-new'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 16px',
              background: activeTab === tab ? C.primary : 'transparent',
              color: activeTab === tab ? '#fff' : C.text,
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 500
            }}
          >
            {tab === 'overview' && 'Recent Checks'}
            {tab === 'high-risk' && `High Risk (${highRisk.length})`}
            {tab === 'blocked' && `Blocked (${blockedEntities.length})`}
            {tab === 'block-new' && 'Block New'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ background: C.card, borderRadius: 12, border: `1px solid ${C.border}`, overflow: 'hidden' }}>
        {activeTab === 'overview' && (
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f9fafb', position: 'sticky', top: 0 }}>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Type</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Value</th>
                  <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 500, color: C.textMuted }}>Risk Score</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Factors</th>
                  <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 500, color: C.textMuted }}>Action</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 500, color: C.textMuted }}>Time</th>
                </tr>
              </thead>
              <tbody>
                {recentChecks.map((check, i) => (
                  <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        padding: '2px 8px',
                        background: check.type === 'email' ? '#dbeafe' : '#fef3c7',
                        color: check.type === 'email' ? '#1d4ed8' : '#92400e',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 500
                      }}>
                        {check.type?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: 12 }}>
                      {check.value?.substring(0, 30)}{check.value?.length > 30 ? '...' : ''}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <span style={{
                        display: 'inline-block',
                        minWidth: 40,
                        padding: '4px 8px',
                        background: getRiskColor(check.risk_score),
                        color: '#fff',
                        borderRadius: 4,
                        fontSize: 12,
                        fontWeight: 600
                      }}>
                        {check.risk_score}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: 11, color: C.textMuted, maxWidth: 200 }}>
                      {(check.risk_factors || []).slice(0, 2).join(', ')}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      {getRecommendationBadge(check.recommendation)}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 11, color: C.textMuted }}>
                      {check.timestamp ? new Date(check.timestamp).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
                {recentChecks.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 40, textAlign: 'center', color: C.textMuted }}>
                      No recent fraud checks
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'high-risk' && (
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f9fafb', position: 'sticky', top: 0 }}>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Type</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Value</th>
                  <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 500, color: C.textMuted }}>Risk Score</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Risk Factors</th>
                  <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 500, color: C.textMuted }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {highRisk.map((item, i) => (
                  <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        padding: '2px 8px',
                        background: item.type === 'email' ? '#dbeafe' : '#fef3c7',
                        color: item.type === 'email' ? '#1d4ed8' : '#92400e',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 500
                      }}>
                        {item.type?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: 12 }}>
                      {item.value}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <span style={{
                        display: 'inline-block',
                        minWidth: 40,
                        padding: '4px 8px',
                        background: getRiskColor(item.risk_score),
                        color: '#fff',
                        borderRadius: 4,
                        fontSize: 12,
                        fontWeight: 600
                      }}>
                        {item.risk_score}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: 11, color: C.textMuted }}>
                      {(item.risk_factors || []).join(', ')}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <button
                        onClick={() => {
                          setBlockForm({ type: item.type, value: item.value, reason: 'High risk score' });
                          setActiveTab('block-new');
                        }}
                        style={{
                          padding: '4px 12px',
                          background: C.red,
                          color: '#fff',
                          border: 'none',
                          borderRadius: 4,
                          cursor: 'pointer',
                          fontSize: 11,
                          fontWeight: 500
                        }}
                      >
                        Block
                      </button>
                    </td>
                  </tr>
                ))}
                {highRisk.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: C.textMuted }}>
                      No high-risk entities found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'blocked' && (
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f9fafb', position: 'sticky', top: 0 }}>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Type</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Value</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 500, color: C.textMuted }}>Reason</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 500, color: C.textMuted }}>Blocked At</th>
                  <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 500, color: C.textMuted }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {blockedEntities.map((item, i) => (
                  <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        padding: '2px 8px',
                        background: '#fee2e2',
                        color: '#dc2626',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 500
                      }}>
                        {item.type?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: 12 }}>
                      {item.value}
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: 12, color: C.textMuted }}>
                      {item.reason || 'Manual block'}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 11, color: C.textMuted }}>
                      {item.blocked_at ? new Date(item.blocked_at).toLocaleString() : '-'}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <button
                        onClick={() => handleUnblock(item.type, item.value)}
                        style={{
                          padding: '4px 12px',
                          background: '#fff',
                          color: C.green,
                          border: `1px solid ${C.green}`,
                          borderRadius: 4,
                          cursor: 'pointer',
                          fontSize: 11,
                          fontWeight: 500
                        }}
                      >
                        Unblock
                      </button>
                    </td>
                  </tr>
                ))}
                {blockedEntities.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: C.textMuted }}>
                      No blocked entities
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'block-new' && (
          <div style={{ padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: C.text }}>Block an Entity</h3>
            <form onSubmit={handleBlock} style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 400 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: C.textMuted }}>
                  Entity Type
                </label>
                <select
                  value={blockForm.type}
                  onChange={(e) => setBlockForm({ ...blockForm, type: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    fontSize: 14
                  }}
                >
                  <option value="email">Email</option>
                  <option value="ip">IP Address</option>
                  <option value="device">Device Fingerprint</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: C.textMuted }}>
                  Value
                </label>
                <input
                  type="text"
                  value={blockForm.value}
                  onChange={(e) => setBlockForm({ ...blockForm, value: e.target.value })}
                  placeholder={blockForm.type === 'email' ? 'spam@example.com' : blockForm.type === 'ip' ? '192.168.1.1' : 'device-fingerprint-hash'}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    fontSize: 14
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: C.textMuted }}>
                  Reason (optional)
                </label>
                <input
                  type="text"
                  value={blockForm.reason}
                  onChange={(e) => setBlockForm({ ...blockForm, reason: e.target.value })}
                  placeholder="e.g., Multiple fraudulent orders"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    fontSize: 14
                  }}
                />
              </div>

              <button
                type="submit"
                style={{
                  padding: '12px 24px',
                  background: C.red,
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8
                }}
              >
                <Ban size={16} />
                Block Entity
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({ title, value, icon: Icon, color }) {
  return (
    <div style={{
      background: '#fff',
      borderRadius: 12,
      padding: 16,
      border: `1px solid ${C.border}`,
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }}>
      <div style={{
        width: 44,
        height: 44,
        borderRadius: 10,
        background: `${color}15`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <Icon size={22} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 600, color: C.text }}>{value || 0}</div>
        <div style={{ fontSize: 12, color: C.textMuted }}>{title}</div>
      </div>
    </div>
  );
}
