import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, 
  AlertTriangle, 
  Shield, 
  Clock, 
  RefreshCw, 
  Server,
  Zap,
  CheckCircle,
  XCircle,
  AlertCircle,
  TrendingUp,
  Ban,
  Trash2
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const CrashDashboard = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      setRefreshing(true);
      const response = await fetch(`${API_URL}/api/admin/crash-dashboard/status`);
      if (!response.ok) throw new Error('Failed to fetch status');
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const resetCircuitBreaker = async () => {
    try {
      const response = await fetch(`${API_URL}/api/admin/crash-dashboard/circuit-breaker/reset`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to reset');
      fetchStatus();
    } catch (err) {
      alert('Failed to reset circuit breaker: ' + err.message);
    }
  };

  const clearOldCrashes = async () => {
    if (!window.confirm('Clear crash logs older than 7 days?')) return;
    try {
      const response = await fetch(`${API_URL}/api/admin/crash-dashboard/crashes/clear?days=7`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error('Failed to clear');
      const data = await response.json();
      alert(`Cleared ${data.deleted} old crash logs`);
      fetchStatus();
    } catch (err) {
      alert('Failed to clear crashes: ' + err.message);
    }
  };

  const getHealthColor = (score) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 50) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getHealthBg = (score) => {
    if (score >= 80) return 'bg-green-500/10 border-green-500/20';
    if (score >= 50) return 'bg-yellow-500/10 border-yellow-500/20';
    return 'bg-red-500/10 border-red-500/20';
  };

  const getCircuitBreakerStatus = (state) => {
    switch (state) {
      case 'CLOSED':
        return { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-500/10', label: 'Healthy' };
      case 'HALF_OPEN':
        return { icon: AlertCircle, color: 'text-yellow-500', bg: 'bg-yellow-500/10', label: 'Recovering' };
      case 'OPEN':
        return { icon: XCircle, color: 'text-red-500', bg: 'bg-red-500/10', label: 'Tripped' };
      default:
        return { icon: AlertCircle, color: 'text-gray-500', bg: 'bg-gray-500/10', label: 'Unknown' };
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
          <AlertTriangle className="inline-block mr-2" size={20} />
          Error loading dashboard: {error}
        </div>
      </div>
    );
  }

  const cbStatus = getCircuitBreakerStatus(status?.circuit_breaker?.state);
  const CbIcon = cbStatus.icon;

  return (
    <div className="p-6 space-y-6 bg-[#1a1a2e] min-h-screen text-white">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="text-amber-500" />
            Crash Dashboard
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            System health monitoring and crash protection
          </p>
        </div>
        <button
          onClick={fetchStatus}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-amber-600/20 hover:bg-amber-600/30 
                     text-amber-500 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Health Score Card */}
      <div className={`rounded-xl p-6 border ${getHealthBg(status?.health_score)}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-400 text-sm">System Health Score</p>
            <p className={`text-5xl font-bold ${getHealthColor(status?.health_score)}`}>
              {status?.health_score || 0}%
            </p>
          </div>
          <div className="text-right">
            <p className="text-gray-400 text-sm">Last Updated</p>
            <p className="text-gray-300">
              {status?.timestamp ? new Date(status.timestamp).toLocaleTimeString() : 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Circuit Breaker */}
        <div className={`rounded-xl p-4 border ${cbStatus.bg} border-${cbStatus.color.replace('text-', '')}/20`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Circuit Breaker</span>
            <CbIcon size={20} className={cbStatus.color} />
          </div>
          <p className={`text-xl font-bold ${cbStatus.color}`}>
            {status?.circuit_breaker?.state || 'Unknown'}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            {status?.circuit_breaker?.failures || 0} failures / {status?.circuit_breaker?.failure_threshold || 5} threshold
          </p>
        </div>

        {/* Crashes 24h */}
        <div className="rounded-xl p-4 border bg-red-500/10 border-red-500/20">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Crashes (24h)</span>
            <AlertTriangle size={20} className="text-red-500" />
          </div>
          <p className="text-xl font-bold text-red-400">
            {status?.crashes?.count_24h || 0}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Unhandled exceptions
          </p>
        </div>

        {/* Rate Limit Violations */}
        <div className="rounded-xl p-4 border bg-orange-500/10 border-orange-500/20">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Rate Violations (24h)</span>
            <Ban size={20} className="text-orange-500" />
          </div>
          <p className="text-xl font-bold text-orange-400">
            {status?.rate_limits?.violations_24h || 0}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Blocked requests
          </p>
        </div>

        {/* Auto-Heal Actions */}
        <div className="rounded-xl p-4 border bg-blue-500/10 border-blue-500/20">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Auto-Heal (24h)</span>
            <Zap size={20} className="text-blue-500" />
          </div>
          <p className="text-xl font-bold text-blue-400">
            {status?.auto_heal?.unresolved_24h || 0}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Unresolved issues
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-700">
        <div className="flex gap-4">
          {['overview', 'crashes', 'rate-limits', 'auto-heal'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-amber-500 text-amber-500'
                  : 'border-transparent text-gray-400 hover:text-gray-300'
              }`}
            >
              {tab.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="space-y-4">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Circuit Breaker Details */}
            <div className="bg-[#252542] rounded-xl p-4 border border-gray-700">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Server size={18} className="text-amber-500" />
                  Circuit Breaker Status
                </h3>
                {status?.circuit_breaker?.state === 'OPEN' && (
                  <button
                    onClick={resetCircuitBreaker}
                    className="text-xs px-3 py-1 bg-amber-600 hover:bg-amber-700 rounded-lg"
                  >
                    Reset
                  </button>
                )}
              </div>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">State</span>
                  <span className={cbStatus.color}>{status?.circuit_breaker?.state}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Failures</span>
                  <span>{status?.circuit_breaker?.failures || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Threshold</span>
                  <span>{status?.circuit_breaker?.failure_threshold || 5}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Recovery Timeout</span>
                  <span>{status?.circuit_breaker?.recovery_timeout_seconds || 60}s</span>
                </div>
                {status?.circuit_breaker?.last_failure_ago_seconds && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Last Failure</span>
                    <span>{status.circuit_breaker.last_failure_ago_seconds}s ago</span>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="bg-[#252542] rounded-xl p-4 border border-gray-700">
              <h3 className="font-semibold flex items-center gap-2 mb-4">
                <TrendingUp size={18} className="text-amber-500" />
                Quick Actions
              </h3>
              <div className="space-y-3">
                <button
                  onClick={clearOldCrashes}
                  className="w-full flex items-center justify-between p-3 bg-red-500/10 hover:bg-red-500/20 
                             rounded-lg text-red-400 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <Trash2 size={16} />
                    Clear Old Crash Logs
                  </span>
                  <span className="text-xs text-gray-500">7+ days</span>
                </button>
                <button
                  onClick={resetCircuitBreaker}
                  className="w-full flex items-center justify-between p-3 bg-amber-500/10 hover:bg-amber-500/20 
                             rounded-lg text-amber-400 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <RefreshCw size={16} />
                    Reset Circuit Breaker
                  </span>
                  <span className="text-xs text-gray-500">Force CLOSED</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'crashes' && (
          <div className="bg-[#252542] rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h3 className="font-semibold">Recent Crashes</h3>
              <span className="text-sm text-gray-400">
                {status?.crashes?.count_24h || 0} in last 24h
              </span>
            </div>
            <div className="divide-y divide-gray-700 max-h-[400px] overflow-y-auto">
              {status?.crashes?.recent?.length > 0 ? (
                status.crashes.recent.map((crash, i) => (
                  <div key={i} className="p-4 hover:bg-white/5">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-red-400">{crash.type}</p>
                        <p className="text-sm text-gray-400 mt-1">{crash.error}</p>
                        <p className="text-xs text-gray-500 mt-1">{crash.url}</p>
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(crash.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <CheckCircle className="mx-auto mb-2 text-green-500" size={32} />
                  No crashes in the last 24 hours
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'rate-limits' && (
          <div className="bg-[#252542] rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h3 className="font-semibold">Rate Limit Violations</h3>
              <span className="text-sm text-gray-400">
                {status?.rate_limits?.violations_24h || 0} in last 24h
              </span>
            </div>
            <div className="divide-y divide-gray-700 max-h-[400px] overflow-y-auto">
              {status?.rate_limits?.recent?.length > 0 ? (
                status.rate_limits.recent.map((violation, i) => (
                  <div key={i} className="p-4 hover:bg-white/5">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-orange-400">
                          {violation.activity_type?.replace(/_/g, ' ').toUpperCase()}
                        </p>
                        <p className="text-sm text-gray-400 mt-1">
                          IP: {violation.ip_hash}
                        </p>
                        {violation.details && (
                          <p className="text-xs text-gray-500 mt-1">
                            {JSON.stringify(violation.details)}
                          </p>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(violation.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <Shield className="mx-auto mb-2 text-green-500" size={32} />
                  No rate limit violations in the last 24 hours
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'auto-heal' && (
          <div className="bg-[#252542] rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h3 className="font-semibold">Auto-Heal Actions</h3>
              <span className="text-sm text-gray-400">
                Runs every 5 minutes
              </span>
            </div>
            <div className="divide-y divide-gray-700 max-h-[400px] overflow-y-auto">
              {status?.auto_heal?.recent?.length > 0 ? (
                status.auto_heal.recent.map((log, i) => (
                  <div key={i} className="p-4 hover:bg-white/5">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium flex items-center gap-2">
                          {log.resolved ? (
                            <CheckCircle size={16} className="text-green-500" />
                          ) : (
                            <AlertCircle size={16} className="text-yellow-500" />
                          )}
                          {log.check_name}
                        </p>
                        <p className="text-sm text-gray-400 mt-1">{log.issue_found}</p>
                        <p className="text-xs text-gray-500 mt-1">{log.action_taken}</p>
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <Activity className="mx-auto mb-2 text-green-500" size={32} />
                  All systems healthy - no auto-heal actions needed
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="text-center text-xs text-gray-500 pt-4 border-t border-gray-700">
        Auto-refresh: 30 seconds | Auto-heal interval: 5 minutes | Circuit breaker threshold: 5 failures
      </div>
    </div>
  );
};

export default CrashDashboard;
