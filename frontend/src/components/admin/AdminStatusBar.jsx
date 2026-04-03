import React, { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, CheckCircle, AlertTriangle, Activity, Clock, Users, Smartphone, ShoppingCart, Wifi, WifiOff } from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) 
  ? 'https://reroots.ca' 
  : process.env.REACT_APP_BACKEND_URL;

const WS_URL = API_URL.replace('https://', 'wss://').replace('http://', 'ws://');

/**
 * AdminStatusBar - Live status bar showing system health at top of admin panel
 * Now includes: Live Activity Ticker, WebSocket connection status, and PWA user count
 */
const AdminStatusBar = () => {
  const [status, setStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);
  
  // Live Sync state
  const [liveStats, setLiveStats] = useState({ total_users: 0, pwa_users: 0 });
  const [wsConnected, setWsConnected] = useState(false);
  const [recentActivity, setRecentActivity] = useState([]);
  
  const wsRef = useRef(null);
  const activityTimeoutRef = useRef(null);

  const token = localStorage.getItem('reroots_token') || localStorage.getItem('token');
  const headers = { 
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  };

  // Initialize WebSocket for Admin
  useEffect(() => {
    const connectWebSocket = () => {
      const clientId = `admin_${Date.now()}`;
      const wsUrl = `${WS_URL}/api/live/ws/${clientId}?type=admin`;
      
      try {
        wsRef.current = new WebSocket(wsUrl);
        
        wsRef.current.onopen = () => {
          console.log('[AdminStatusBar] WebSocket connected');
          setWsConnected(true);
        };
        
        wsRef.current.onmessage = (event) => {
          const data = JSON.parse(event.data);
          
          if (data.type === 'connected' && data.stats) {
            setLiveStats({
              total_users: data.stats.total_users || 0,
              pwa_users: data.stats.pwa_users || 0
            });
          }
          
          if (data.type === 'user_connected' || data.type === 'user_disconnected') {
            setLiveStats(prev => ({
              ...prev,
              total_users: data.total_users || prev.total_users
            }));
          }
          
          if (data.type === 'live_activity') {
            // Add to activity ticker
            const activity = data.activity;
            setRecentActivity(prev => {
              const newActivity = {
                id: Date.now(),
                type: activity.activity_type || activity.type || 'unknown',
                user: activity.user_id?.slice(0, 8) || 'Anonymous',
                source: activity.client_type || 'web',
                time: new Date().toLocaleTimeString()
              };
              return [newActivity, ...prev.slice(0, 4)]; // Keep last 5
            });
            
            // Clear activity after 30 seconds
            if (activityTimeoutRef.current) {
              clearTimeout(activityTimeoutRef.current);
            }
            activityTimeoutRef.current = setTimeout(() => {
              setRecentActivity(prev => prev.slice(0, 2));
            }, 30000);
          }
        };
        
        wsRef.current.onclose = () => {
          console.log('[AdminStatusBar] WebSocket disconnected');
          setWsConnected(false);
          // Reconnect after 5 seconds
          setTimeout(connectWebSocket, 5000);
        };
        
        wsRef.current.onerror = () => {
          setWsConnected(false);
        };
        
      } catch (error) {
        console.error('[AdminStatusBar] WebSocket error:', error);
        setWsConnected(false);
      }
    };
    
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (activityTimeoutRef.current) {
        clearTimeout(activityTimeoutRef.current);
      }
    };
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const [healRes, orchestratorRes, liveRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/auto-heal/status`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/orchestrator/pending`, { headers }).catch(() => null),
        fetch(`${API_URL}/api/live/stats`, { headers }).catch(() => null)
      ]);
      
      if (healRes?.ok) {
        const data = await healRes.json();
        setStatus(data);
      }
      
      if (orchestratorRes?.ok) {
        const data = await orchestratorRes.json();
        setPendingCount(data.count || 0);
      }
      
      if (liveRes?.ok) {
        const data = await liveRes.json();
        setLiveStats({
          total_users: (data.website_connections || 0) + (data.pwa_connections || 0),
          pwa_users: data.pwa_connections || 0
        });
      }
    } catch (err) {
      console.error('Status bar load error:', err);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 60000); // Refresh every 60s
    return () => clearInterval(interval);
  }, [loadStatus]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      // Run all health checks simultaneously
      await Promise.all([
        fetch(`${API_URL}/api/admin/auto-heal/run`, { method: 'POST', headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/audit/run`, { method: 'POST', headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/auto-repair/run`, { method: 'POST', headers }).catch(() => null),
        fetch(`${API_URL}/api/admin/orchestrator/sync`, { method: 'POST', headers }).catch(() => null),
      ]);
      setLastSync(new Date().toLocaleTimeString());
      // Reload status after sync
      await loadStatus();
    } catch (err) {
      console.error('Sync error:', err);
    } finally {
      setSyncing(false);
    }
  };

  const allHealthy = status?.overall_status === 'healthy' || status?.system_healthy;
  const schedulerCount = status?.scheduler_jobs || status?.scheduler_count || 0;

  // Activity icon based on type
  const getActivityIcon = (type) => {
    if (type?.includes('cart') || type?.includes('checkout')) return <ShoppingCart className="w-3 h-3" />;
    if (type?.includes('quiz') || type?.includes('profile')) return <Activity className="w-3 h-3" />;
    return <Users className="w-3 h-3" />;
  };

  return (
    <div 
      className="flex items-center justify-between px-4 py-2 text-xs border-b transition-colors"
      style={{
        background: allHealthy ? '#E8F5E9' : '#FFF3E0',
        borderColor: allHealthy ? '#A5D6A7' : '#FFCC80'
      }}
    >
      <div className="flex items-center gap-4">
        {/* WebSocket Connection Status */}
        <div className="flex items-center gap-1">
          {wsConnected ? (
            <Wifi className="w-3 h-3 text-green-600" />
          ) : (
            <WifiOff className="w-3 h-3 text-red-500" />
          )}
          <span className={wsConnected ? 'text-green-700' : 'text-red-600'}>
            {wsConnected ? 'Live' : 'Offline'}
          </span>
        </div>

        {/* Live Users Count */}
        <div className="flex items-center gap-1 text-gray-600">
          <Users className="w-3 h-3" />
          <span>{liveStats.total_users} users</span>
          {liveStats.pwa_users > 0 && (
            <span className="flex items-center gap-0.5 ml-1 text-amber-600">
              <Smartphone className="w-3 h-3" />
              {liveStats.pwa_users} PWA
            </span>
          )}
        </div>

        {/* System Status */}
        <div className="flex items-center gap-2">
          {allHealthy ? (
            <CheckCircle className="w-4 h-4 text-green-600" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-orange-600" />
          )}
          <span style={{ color: allHealthy ? '#2E7D32' : '#E65100', fontWeight: 600 }}>
            {allHealthy ? 'Healthy' : 'Issues'}
          </span>
        </div>

        {/* Scheduler Status */}
        <div className="flex items-center gap-1 text-gray-600">
          <Activity className="w-3 h-3" />
          <span>{schedulerCount} jobs</span>
        </div>

        {/* Pending Approvals */}
        {pendingCount > 0 && (
          <div className="flex items-center gap-1">
            <span className="px-2 py-0.5 bg-amber-500 text-white rounded-full text-xs font-semibold">
              {pendingCount} pending
            </span>
          </div>
        )}

        {/* Live Activity Ticker */}
        {recentActivity.length > 0 && (
          <div className="flex items-center gap-2 border-l pl-3 ml-2 border-gray-300">
            <span className="text-gray-500">Live:</span>
            <div className="flex items-center gap-2 overflow-hidden max-w-xs">
              {recentActivity.slice(0, 2).map(activity => (
                <div 
                  key={activity.id}
                  className="flex items-center gap-1 px-2 py-0.5 bg-blue-100 rounded text-blue-700 animate-pulse"
                >
                  {getActivityIcon(activity.type)}
                  <span className="truncate max-w-[80px]">
                    {activity.type?.replace(/_/g, ' ')}
                  </span>
                  <span className="text-blue-400">
                    ({activity.source === 'pwa' ? '📱' : '🌐'})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Last Sync */}
        {lastSync && (
          <div className="flex items-center gap-1 text-gray-500">
            <Clock className="w-3 h-3" />
            <span>{lastSync}</span>
          </div>
        )}
      </div>

      {/* Sync Button */}
      <button
        onClick={handleSync}
        disabled={syncing}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium text-white transition-all hover:opacity-90 disabled:opacity-50"
        style={{ background: '#C8A96A' }}
      >
        <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
        {syncing ? 'Syncing...' : 'Sync'}
      </button>
    </div>
  );
};

export default AdminStatusBar;
