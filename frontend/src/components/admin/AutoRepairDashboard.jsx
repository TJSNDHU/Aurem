import React, { useState, useEffect, useCallback } from 'react';
import { 
  Wrench, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Clock,
  RefreshCw,
  Play,
  ThumbsUp,
  ThumbsDown,
  Activity,
  Zap,
  Shield,
  Bot
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

export default function AutoRepairDashboard() {
  const [history, setHistory] = useState([]);
  const [pending, setPending] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [processingApproval, setProcessingApproval] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      const [historyRes, pendingRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/auto-repair/history?limit=20`, { headers }),
        fetch(`${API_URL}/api/admin/auto-repair/pending`, { headers }),
        fetch(`${API_URL}/api/admin/auto-repair/stats`, { headers })
      ]);

      if (historyRes.ok) {
        const data = await historyRes.json();
        setHistory(data.repairs || []);
      }

      if (pendingRes.ok) {
        const data = await pendingRes.json();
        setPending(data.pending || []);
      }

      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data.stats);
      }
    } catch (error) {
      console.error('Failed to fetch auto-repair data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  const triggerRepair = async () => {
    setRunning(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/admin/auto-repair/run`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        await fetchData();
      }
    } catch (error) {
      console.error('Failed to trigger repair:', error);
    } finally {
      setRunning(false);
    }
  };

  const handleApproval = async (approvalId, action) => {
    setProcessingApproval(approvalId);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/admin/auto-repair/approve`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ approval_id: approvalId, action })
      });

      if (response.ok) {
        await fetchData();
      }
    } catch (error) {
      console.error('Failed to process approval:', error);
    } finally {
      setProcessingApproval(null);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (healthy) => {
    return healthy ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50';
  };

  return (
    <div className="p-6 space-y-6" data-testid="auto-repair-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Autonomous Repair</h1>
            <p className="text-sm text-gray-500">Self-healing system with AI diagnosis</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={triggerRepair}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            data-testid="trigger-repair-btn"
          >
            {running ? (
              <>
                <Activity className="w-4 h-4 animate-pulse" />
                Running...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Now
              </>
            )}
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl p-4 text-white">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-5 h-5" />
              <span className="font-medium">Success Rate</span>
            </div>
            <div className="text-3xl font-bold">{stats.success_rate || 100}%</div>
            <p className="text-white/70 text-sm">Issues fixed automatically</p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2 text-gray-500">
              <Wrench className="w-5 h-5" />
              <span className="font-medium">Auto-Fixed (24h)</span>
            </div>
            <div className="text-3xl font-bold text-gray-900">{stats.auto_fixed_24h || 0}</div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2 text-gray-500">
              <Activity className="w-5 h-5" />
              <span className="font-medium">Total Repairs (24h)</span>
            </div>
            <div className="text-3xl font-bold text-gray-900">{stats.total_repairs_24h || 0}</div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2 text-gray-500">
              <Clock className="w-5 h-5" />
              <span className="font-medium">Pending Approval</span>
            </div>
            <div className="text-3xl font-bold text-amber-600">{stats.pending_approvals || 0}</div>
          </div>
        </div>
      )}

      {/* Pending Approvals */}
      {pending.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <h2 className="text-lg font-semibold text-amber-800 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5" />
            Pending Approvals ({pending.length})
          </h2>
          <div className="space-y-3">
            {pending.map((item, idx) => (
              <div key={idx} className="bg-white rounded-lg p-4 border border-amber-200">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">
                      {item.fix?.description || 'Unknown issue'}
                    </div>
                    <div className="text-sm text-gray-500 mt-1">
                      {item.fix?.root_cause || 'Cause unknown'}
                    </div>
                    <div className="text-xs text-gray-400 mt-2 font-mono bg-gray-50 p-2 rounded">
                      {item.fix?.fix_command?.slice(0, 100) || 'No fix command'}
                    </div>
                    <div className="mt-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        item.fix?.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                        item.fix?.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {item.fix?.risk_level?.toUpperCase() || 'UNKNOWN'} RISK
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleApproval(item.approval_id, 'approve')}
                      disabled={processingApproval === item.approval_id}
                      className="flex items-center gap-1 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      <ThumbsUp className="w-4 h-4" />
                      Approve
                    </button>
                    <button
                      onClick={() => handleApproval(item.approval_id, 'reject')}
                      disabled={processingApproval === item.approval_id}
                      className="flex items-center gap-1 px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                    >
                      <ThumbsDown className="w-4 h-4" />
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Repair History */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Shield className="w-5 h-5" />
            Repair History
          </h2>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <Activity className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
          </div>
        ) : history.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No repairs recorded yet</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {history.map((repair, idx) => (
              <div key={idx} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {repair.system_healthy_after ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                    <div>
                      <div className="font-medium text-gray-900">
                        {repair.auto_fixed || 0} auto-fixed, {repair.ai_actions || 0} AI actions
                      </div>
                      <div className="text-sm text-gray-500 flex items-center gap-2">
                        <Clock className="w-3 h-3" />
                        {formatDate(repair.timestamp)}
                        <span className="mx-1">·</span>
                        {repair.errors_found || 0} errors found
                      </div>
                    </div>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(repair.system_healthy_after)}`}>
                    {repair.system_healthy_after ? 'HEALTHY' : 'DEGRADED'}
                  </span>
                </div>

                {/* Show fixes */}
                {repair.fixes && repair.fixes.length > 0 && (
                  <div className="mt-3 pl-8 space-y-1">
                    {repair.fixes.slice(0, 3).map((fix, fixIdx) => (
                      <div key={fixIdx} className="text-sm flex items-center gap-2">
                        {fix.auto_applied !== false ? (
                          <CheckCircle className="w-3 h-3 text-green-500" />
                        ) : (
                          <Clock className="w-3 h-3 text-amber-500" />
                        )}
                        <span className="text-gray-600">
                          {fix.fix_applied || fix.description || 'Unknown fix'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
