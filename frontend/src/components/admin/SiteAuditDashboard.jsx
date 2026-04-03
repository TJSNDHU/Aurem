import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  RefreshCw,
  Database,
  Server,
  Wifi,
  Clock,
  Zap,
  Shield,
  Globe,
  CloudLightning
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

export default function SiteAuditDashboard() {
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [checks, setChecks] = useState([]);
  const [error, setError] = useState(null);

  const fetchAudit = useCallback(async () => {
    try {
      setError(null);
      const token = localStorage.getItem('reroots_token') || localStorage.getItem('token');
      
      if (token) {
        // Fetch status endpoint
        const statusRes = await fetch(`${API_URL}/api/admin/audit/status`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setAuditData(statusData);
          
          // If we have last_audit with checks, use those
          if (statusData.last_audit?.checks) {
            setChecks(statusData.last_audit.checks);
          }
        }
        
        // Also try summary endpoint
        const summaryRes = await fetch(`${API_URL}/api/admin/audit/summary`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (summaryRes.ok) {
          const summaryData = await summaryRes.json();
          if (summaryData.checks && summaryData.checks.length > 0) {
            setChecks(summaryData.checks);
          }
        }
      }
    } catch (err) {
      console.error('Failed to fetch audit:', err);
      setError('Failed to load audit data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAudit();
    const interval = setInterval(fetchAudit, 30000);
    return () => clearInterval(interval);
  }, [fetchAudit]);

  const runAudit = async () => {
    setRunning(true);
    try {
      const token = localStorage.getItem('reroots_token') || localStorage.getItem('token');
      await fetch(`${API_URL}/api/admin/audit/run`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      // Wait a moment for audit to run
      await new Promise(r => setTimeout(r, 3000));
      await fetchAudit();
    } catch (error) {
      console.error('Failed to run audit:', error);
    } finally {
      setRunning(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'pass':
      case 'ok':
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'warn':
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-amber-500" />;
      case 'fail':
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Activity className="w-5 h-5 text-blue-500 animate-pulse" />;
    }
  };

  const getCheckIcon = (name) => {
    const iconMap = {
      'Database': <Database className="w-5 h-5 text-gray-400" />,
      'API Health': <Server className="w-5 h-5 text-gray-400" />,
      'AI Service': <Zap className="w-5 h-5 text-gray-400" />,
      'Stripe': <Wifi className="w-5 h-5 text-gray-400" />,
      'External APIs': <Globe className="w-5 h-5 text-gray-400" />,
      'Response Time': <Clock className="w-5 h-5 text-gray-400" />,
      'Security': <Shield className="w-5 h-5 text-gray-400" />,
    };
    return iconMap[name] || <CloudLightning className="w-5 h-5 text-gray-400" />;
  };

  const getStatusMessage = (check) => {
    if (check.status === 'pass') return 'Synchronized ✓';
    if (check.status === 'fail') return 'Connection failed';
    if (check.status === 'warn') return 'Degraded performance';
    return 'Synchronizing...';
  };

  // Default checks when no data
  const defaultChecks = [
    { name: 'Database', status: 'checking' },
    { name: 'API Health', status: 'checking' },
    { name: 'AI Service', status: 'checking' },
    { name: 'Stripe', status: 'checking' },
    { name: 'External APIs', status: 'checking' },
    { name: 'Security', status: 'checking' },
  ];

  const displayChecks = checks.length > 0 ? checks : defaultChecks;

  return (
    <div className="p-6 space-y-6" data-testid="site-audit-dashboard">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-8 h-8 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Site Audit</h1>
            <p className="text-sm text-gray-500">System health and service synchronization</p>
          </div>
        </div>
        <button
          onClick={runAudit}
          disabled={running}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${running ? 'animate-spin' : ''}`} />
          {running ? 'Running...' : 'Run Audit'}
        </button>
      </div>

      {/* Overall Status Banner */}
      {auditData?.last_audit?.overall_status && (
        <div className={`p-4 rounded-xl border ${
          auditData.last_audit.overall_status === 'healthy' 
            ? 'bg-green-50 border-green-200' 
            : 'bg-amber-50 border-amber-200'
        }`}>
          <div className="flex items-center gap-3">
            {auditData.last_audit.overall_status === 'healthy' 
              ? <CheckCircle className="w-6 h-6 text-green-500" />
              : <AlertTriangle className="w-6 h-6 text-amber-500" />
            }
            <div>
              <p className="font-semibold text-gray-900">
                System Status: {auditData.last_audit.overall_status === 'healthy' ? 'All Systems Synchronized' : 'Some Issues Detected'}
              </p>
              {auditData.last_audit.summary && (
                <p className="text-sm text-gray-600">
                  {auditData.last_audit.summary.passed || 0} passed, {auditData.last_audit.summary.warnings || 0} warnings, {auditData.last_audit.summary.failed || 0} failed
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200">
          <div className="flex items-center gap-3">
            <XCircle className="w-6 h-6 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Activity className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-2" />
            <p className="text-gray-500">Loading synchronization status...</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayChecks.map((check, index) => (
            <div key={index} className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
              <div className="flex items-center gap-3 mb-3">
                {getCheckIcon(check.name)}
                <span className="font-medium">{check.name}</span>
                {getStatusIcon(check.status)}
              </div>
              <p className="text-sm text-gray-600">
                {check.status === 'checking' ? 'Awaiting synchronization...' : getStatusMessage(check)}
              </p>
            </div>
          ))}
        </div>
      )}

      {auditData?.last_audit?.timestamp && (
        <p className="text-sm text-gray-500 text-center">
          Last synchronized: {new Date(auditData.last_audit.timestamp).toLocaleString()}
        </p>
      )}
      
      {auditData?.scheduler_active && (
        <p className="text-xs text-gray-400 text-center">
          Auto-sync scheduled: {auditData.next_run}
        </p>
      )}
    </div>
  );
}
