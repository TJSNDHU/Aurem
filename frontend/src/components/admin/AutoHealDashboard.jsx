/**
 * AutoHealDashboard.jsx
 * Admin dashboard widget for monitoring the self-healing system
 * Shows health check status, recent actions, and manual trigger
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, 
  Server, 
  Globe, 
  Database, 
  Clock, 
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Zap,
  Calendar,
  Loader2,
  Play,
  History
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Health check configurations
const HEALTH_CHECKS = [
  { 
    key: 'backend', 
    name: 'Backend API', 
    icon: Server, 
    description: 'FastAPI health endpoint',
    canAutoFix: true
  },
  { 
    key: 'frontend', 
    name: 'Frontend', 
    icon: Globe, 
    description: 'React app serving',
    canAutoFix: true
  },
  { 
    key: 'redis', 
    name: 'Redis Cache', 
    icon: Zap, 
    description: 'Redis Cloud connection',
    canAutoFix: false
  },
  { 
    key: 'mongodb', 
    name: 'MongoDB', 
    icon: Database, 
    description: 'Database connection',
    canAutoFix: false
  },
  { 
    key: 'schedulers', 
    name: 'Schedulers', 
    icon: Clock, 
    description: 'Background tasks',
    canAutoFix: true
  }
];

// Status indicator component
const StatusIndicator = ({ status, size = 'md' }) => {
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4'
  };
  
  const statusColors = {
    healthy: 'bg-green-500',
    fixed: 'bg-yellow-500',
    alerted: 'bg-orange-500',
    failed: 'bg-red-500',
    skipped: 'bg-gray-400',
    error: 'bg-red-500',
    unknown: 'bg-gray-300'
  };
  
  return (
    <div className={`${sizeClasses[size]} rounded-full ${statusColors[status] || statusColors.unknown} ${status === 'healthy' ? 'animate-pulse' : ''}`} />
  );
};

// Health check card component
const HealthCheckCard = ({ check, result }) => {
  const Icon = check.icon;
  const status = result?.status || 'unknown';
  const isHealthy = status === 'healthy' || status === 'skipped';
  
  return (
    <div 
      className={`p-4 rounded-xl border transition-all ${
        isHealthy 
          ? 'bg-green-50/50 border-green-200' 
          : 'bg-red-50/50 border-red-200'
      }`}
      data-testid={`health-check-${check.key}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isHealthy ? 'bg-green-100' : 'bg-red-100'}`}>
            <Icon className={`h-5 w-5 ${isHealthy ? 'text-green-600' : 'text-red-600'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-medium text-gray-900">{check.name}</h4>
              {check.canAutoFix && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  Auto-fix
                </Badge>
              )}
            </div>
            <p className="text-xs text-gray-500">{check.description}</p>
          </div>
        </div>
        <StatusIndicator status={status} size="lg" />
      </div>
      
      {result?.issue && (
        <div className="mt-3 p-2 bg-white/80 rounded-lg border border-red-100">
          <p className="text-xs text-red-600 font-medium">{result.issue}</p>
          {result.action_taken && (
            <p className="text-xs text-gray-500 mt-1">Action: {result.action_taken}</p>
          )}
        </div>
      )}
      
      {result?.running_schedulers !== undefined && (
        <div className="mt-2 text-xs text-gray-500">
          {result.running_schedulers} schedulers running
        </div>
      )}
    </div>
  );
};

// Action log entry component
const ActionLogEntry = ({ log }) => {
  const isResolved = log.resolved;
  
  return (
    <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
      <div className={`p-1.5 rounded-full ${isResolved ? 'bg-green-100' : 'bg-red-100'}`}>
        {isResolved ? (
          <CheckCircle className="h-4 w-4 text-green-600" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-red-600" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-gray-900 capitalize">
            {log.check_name?.replace(/_/g, ' ')}
          </span>
          <Badge 
            variant={isResolved ? 'default' : 'destructive'} 
            className="text-[10px] px-1.5"
          >
            {isResolved ? 'Resolved' : 'Unresolved'}
          </Badge>
        </div>
        <p className="text-xs text-gray-600 mt-0.5 truncate">{log.issue_found}</p>
        <p className="text-xs text-gray-400 mt-1">
          {new Date(log.timestamp).toLocaleString()}
        </p>
      </div>
    </div>
  );
};

export default function AutoHealDashboard() {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState(null);
  const [nextRun, setNextRun] = useState(600); // 10 minutes in seconds
  
  // Fetch status and logs
  const fetchData = useCallback(async () => {
    const token = localStorage.getItem('reroots_token');
    if (!token) return;
    
    try {
      const [statusRes, logsRes] = await Promise.all([
        fetch(`${API}/api/admin/auto-heal/status`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`${API}/api/admin/auto-heal/logs?limit=10`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      
      if (statusRes.ok) {
        const data = await statusRes.json();
        setStatus(data);
      }
      
      if (logsRes.ok) {
        const data = await logsRes.json();
        setLogs(data.logs || []);
      }
    } catch (error) {
      console.error('Failed to fetch auto-heal data:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  // Initial fetch
  useEffect(() => {
    fetchData();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);
  
  // Countdown timer for next run
  useEffect(() => {
    const timer = setInterval(() => {
      setNextRun(prev => {
        if (prev <= 1) {
          fetchData(); // Refresh when timer hits 0
          return 600; // Reset to 10 minutes
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(timer);
  }, [fetchData]);
  
  // Manual run handler
  const handleRunNow = async () => {
    const token = localStorage.getItem('reroots_token');
    if (!token) {
      toast.error('Authentication required');
      return;
    }
    
    setRunning(true);
    try {
      const res = await fetch(`${API}/api/admin/auto-heal/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        const data = await res.json();
        setLastRun(data.results);
        setNextRun(600); // Reset countdown
        
        const allHealthy = data.results?.summary?.all_healthy;
        if (allHealthy) {
          toast.success('All health checks passed!');
        } else {
          const actionsCount = data.results?.summary?.actions_taken_count || 0;
          toast.warning(`Health checks complete. ${actionsCount} action(s) taken.`);
        }
        
        // Refresh logs
        fetchData();
      } else {
        toast.error('Failed to run health checks');
      }
    } catch (error) {
      toast.error('Error running health checks');
    } finally {
      setRunning(false);
    }
  };
  
  // Format countdown
  const formatCountdown = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }
  
  // Get results from last run or status
  const checkResults = lastRun?.checks || {};
  
  return (
    <div className="space-y-6" data-testid="auto-heal-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600">
            <Activity className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Auto-Heal Monitor</h2>
            <p className="text-sm text-gray-500">Self-healing system status</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Next run countdown */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
            <Clock className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-mono text-gray-600">
              Next: {formatCountdown(nextRun)}
            </span>
          </div>
          
          {/* Run now button */}
          <Button
            onClick={handleRunNow}
            disabled={running}
            className="bg-emerald-600 hover:bg-emerald-700"
            data-testid="run-health-checks-btn"
          >
            {running ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run Now
              </>
            )}
          </Button>
        </div>
      </div>
      
      {/* Status summary */}
      {lastRun?.summary && (
        <div className={`p-4 rounded-xl border ${
          lastRun.summary.all_healthy 
            ? 'bg-green-50 border-green-200' 
            : 'bg-yellow-50 border-yellow-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {lastRun.summary.all_healthy ? (
                <CheckCircle className="h-5 w-5 text-green-600" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
              )}
              <span className={`font-medium ${
                lastRun.summary.all_healthy ? 'text-green-700' : 'text-yellow-700'
              }`}>
                {lastRun.summary.all_healthy 
                  ? 'All systems operational' 
                  : `${lastRun.summary.actions_taken_count} issue(s) detected`}
              </span>
            </div>
            <span className="text-xs text-gray-500">
              Last check: {new Date(lastRun.timestamp).toLocaleTimeString()}
              {' · '}
              {lastRun.summary.duration_ms}ms
            </span>
          </div>
        </div>
      )}
      
      {/* Health checks grid */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
          <Server className="h-4 w-4" />
          Health Checks
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {HEALTH_CHECKS.map(check => (
            <HealthCheckCard 
              key={check.key} 
              check={check} 
              result={checkResults[check.key]}
            />
          ))}
        </div>
      </div>
      
      {/* Recent actions log */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
          <History className="h-4 w-4" />
          Recent Actions
          {logs.length > 0 && (
            <Badge variant="secondary" className="text-xs">
              {logs.length}
            </Badge>
          )}
        </h3>
        
        {logs.length === 0 ? (
          <div className="p-8 text-center bg-gray-50 rounded-xl border border-dashed border-gray-200">
            <CheckCircle className="h-10 w-10 text-green-400 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No recent actions</p>
            <p className="text-xs text-gray-400 mt-1">
              The system is running smoothly with no auto-heal actions needed
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {logs.map((log, idx) => (
              <ActionLogEntry key={idx} log={log} />
            ))}
          </div>
        )}
      </div>
      
      {/* Info footer */}
      <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
        <div className="flex items-start gap-3">
          <RefreshCw className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-blue-800">Automatic Monitoring</p>
            <p className="text-xs text-blue-600 mt-1">
              Health checks run automatically every 10 minutes. Failed services are auto-restarted 
              when possible. External services (Redis, MongoDB) trigger WhatsApp alerts to admin.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
