import React, { useState, useEffect, useCallback } from 'react';
import { 
  Brain, Activity, AlertTriangle, CheckCircle, XCircle, Clock, 
  Shield, Zap, RefreshCw, Bell, Send, Eye, ChevronRight
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) 
  ? 'https://reroots.ca' 
  : process.env.REACT_APP_BACKEND_URL;

const OrchestratorDashboard = () => {
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [pending, setPending] = useState([]);
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('events');
  const [refreshing, setRefreshing] = useState(false);

  const token = localStorage.getItem('reroots_token');
  const headers = { 
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json'
  };

  const fetchData = useCallback(async () => {
    try {
      setRefreshing(true);
      
      const [statsRes, eventsRes, pendingRes, queueRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/orchestrator/stats`, { headers }),
        fetch(`${API_URL}/api/admin/orchestrator/events?limit=30`, { headers }),
        fetch(`${API_URL}/api/admin/orchestrator/pending`, { headers }),
        fetch(`${API_URL}/api/admin/orchestrator/queue`, { headers })
      ]);

      const [statsData, eventsData, pendingData, queueData] = await Promise.all([
        statsRes.json(),
        eventsRes.json(),
        pendingRes.json(),
        queueRes.json()
      ]);

      setStats(statsData);
      setEvents(eventsData.events || []);
      setPending(pendingData.approvals || []);
      setQueue(queueData.queue || []);
      setError(null);
    } catch (err) {
      setError('Failed to load orchestrator data');
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleApprove = async (eventId) => {
    try {
      await fetch(`${API_URL}/api/admin/orchestrator/approve/${eventId}`, {
        method: 'POST',
        headers
      });
      fetchData();
    } catch (err) {
      console.error('Approve failed:', err);
    }
  };

  const handleReject = async (eventId) => {
    try {
      await fetch(`${API_URL}/api/admin/orchestrator/reject/${eventId}`, {
        method: 'POST',
        headers
      });
      fetchData();
    } catch (err) {
      console.error('Reject failed:', err);
    }
  };

  const sendTestDigest = async () => {
    try {
      await fetch(`${API_URL}/api/admin/orchestrator/test-digest`, {
        method: 'POST',
        headers
      });
      alert('Daily digest sent to WhatsApp');
    } catch (err) {
      console.error('Digest failed:', err);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'restarted': 'bg-green-500',
      'auto_fixed': 'bg-green-500',
      'blocked': 'bg-red-500',
      'pending_approval': 'bg-yellow-500',
      'queued_for_digest': 'bg-blue-500',
      'logged': 'bg-gray-500',
      'approved_by_admin': 'bg-green-600',
      'rejected_by_admin': 'bg-red-600',
    };
    return colors[status] || 'bg-gray-400';
  };

  const getEventIcon = (type) => {
    const icons = {
      'crash': <Zap className="w-4 h-4 text-red-500" />,
      'bug': <AlertTriangle className="w-4 h-4 text-orange-500" />,
      'violation': <Shield className="w-4 h-4 text-red-500" />,
      'suggestion': <Bell className="w-4 h-4 text-blue-500" />,
      'security': <Shield className="w-4 h-4 text-purple-500" />,
      'business': <Activity className="w-4 h-4 text-green-500" />,
      'performance': <Clock className="w-4 h-4 text-yellow-500" />,
    };
    return icons[type] || <Activity className="w-4 h-4 text-gray-500" />;
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-pink-500" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 bg-[#1a1a1a] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl">
            <Brain className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Central Orchestrator</h1>
            <p className="text-gray-400 text-sm">One brain. One loop. One notification.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={sendTestDigest}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center gap-2 transition-colors"
          >
            <Send className="w-4 h-4" />
            Send Digest
          </button>
          <button
            onClick={fetchData}
            disabled={refreshing}
            className="px-4 py-2 bg-[#2a2a2a] hover:bg-[#333] text-white rounded-lg flex items-center gap-2 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div className="p-4 bg-[#2a2a2a] rounded-xl border border-[#333]">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <span className="text-gray-400 text-sm">Events (24h)</span>
          </div>
          <div className="text-2xl font-bold text-white">{stats?.events_24h || 0}</div>
        </div>
        
        <div className="p-4 bg-[#2a2a2a] rounded-xl border border-[#333]">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="text-gray-400 text-sm">Auto-handled</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{stats?.auto_handled || 0}</div>
        </div>
        
        <div className="p-4 bg-[#2a2a2a] rounded-xl border border-[#333]">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-5 h-5 text-red-400" />
            <span className="text-gray-400 text-sm">Crashes</span>
          </div>
          <div className="text-2xl font-bold text-red-400">{stats?.crashes || 0}</div>
        </div>
        
        <div className="p-4 bg-[#2a2a2a] rounded-xl border border-[#333]">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-5 h-5 text-orange-400" />
            <span className="text-gray-400 text-sm">Violations</span>
          </div>
          <div className="text-2xl font-bold text-orange-400">{stats?.violations || 0}</div>
        </div>
        
        <div className="p-4 bg-[#2a2a2a] rounded-xl border border-[#333]">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-5 h-5 text-yellow-400" />
            <span className="text-gray-400 text-sm">Pending</span>
          </div>
          <div className="text-2xl font-bold text-yellow-400">{stats?.pending_approvals || 0}</div>
        </div>
        
        <div className="p-4 bg-[#2a2a2a] rounded-xl border border-[#333]">
          <div className="flex items-center gap-2 mb-2">
            <Bell className="w-5 h-5 text-purple-400" />
            <span className="text-gray-400 text-sm">In Queue</span>
          </div>
          <div className="text-2xl font-bold text-purple-400">{stats?.queued_notifications || 0}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[#333] pb-2">
        {[
          { id: 'events', label: 'Event Feed', count: events.length },
          { id: 'pending', label: 'Pending Approvals', count: pending.length },
          { id: 'queue', label: 'Notification Queue', count: queue.length }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-t-lg flex items-center gap-2 transition-colors ${
              activeTab === tab.id 
                ? 'bg-[#2a2a2a] text-white border-b-2 border-pink-500' 
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                tab.id === 'pending' && tab.count > 0 ? 'bg-yellow-500 text-black' : 'bg-[#444] text-white'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-[#2a2a2a] rounded-xl border border-[#333] overflow-hidden">
        {activeTab === 'events' && (
          <div className="divide-y divide-[#333]">
            {events.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                No events in the last 24 hours
              </div>
            ) : (
              events.map((event, i) => (
                <div key={event.event_id || i} className="p-4 hover:bg-[#333] transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[#1a1a1a] rounded-lg">
                      {getEventIcon(event.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-white capitalize">{event.type}</span>
                        <span className={`px-2 py-0.5 rounded text-xs text-white ${getStatusColor(event.status)}`}>
                          {event.status?.replace(/_/g, ' ')}
                        </span>
                        <span className="text-gray-500 text-xs">from {event.source}</span>
                      </div>
                      <p className="text-gray-400 text-sm truncate">
                        {event.data?.error || event.data?.message || event.data?.title || JSON.stringify(event.data).slice(0, 100)}
                      </p>
                      <p className="text-gray-500 text-xs mt-1">
                        {formatTime(event.timestamp || event.created_at)}
                      </p>
                    </div>
                    {event.result && (
                      <div className="text-right">
                        {event.result.recovered !== undefined && (
                          <span className={event.result.recovered ? 'text-green-400' : 'text-red-400'}>
                            {event.result.recovered ? 'Recovered' : 'Still down'}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'pending' && (
          <div className="divide-y divide-[#333]">
            {pending.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-500" />
                No pending approvals - all caught up!
              </div>
            ) : (
              pending.map((approval, i) => (
                <div 
                  key={approval.event_id || i} 
                  className="p-5 m-3 rounded-xl"
                  style={{ border: '1px solid #C8A96A' }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-5 h-5 text-yellow-500" />
                    <span className="font-bold text-white text-lg">{approval.title}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      approval.risk === 'high' ? 'bg-red-500' : 
                      approval.risk === 'medium' ? 'bg-yellow-500 text-black' : 'bg-blue-500'
                    } text-white`}>
                      {approval.risk?.toUpperCase()} RISK
                    </span>
                  </div>
                  
                  <p className="text-gray-400 text-sm mb-3">{approval.description}</p>
                  
                  {approval.suggested_fix && (
                    <div className="text-xs text-gray-300 bg-[#1a1a1a] p-3 rounded-lg mb-4 font-mono">
                      {approval.suggested_fix?.substring(0, 200)}
                      {approval.suggested_fix?.length > 200 && '...'}
                    </div>
                  )}
                  
                  <p className="text-gray-600 text-xs mb-4">
                    ID: {approval.event_id?.slice(0, 8)} • {formatTime(approval.created_at)}
                  </p>
                  
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleApprove(approval.event_id)}
                      className="flex-1 py-3 rounded-lg font-semibold text-white flex items-center justify-center gap-2 transition-all hover:opacity-90"
                      style={{ background: '#2E7D32' }}
                    >
                      <CheckCircle className="w-5 h-5" />
                      APPROVE
                    </button>
                    <button
                      onClick={() => handleReject(approval.event_id)}
                      className="flex-1 py-3 rounded-lg font-semibold text-white flex items-center justify-center gap-2 transition-all hover:opacity-90"
                      style={{ background: '#C62828' }}
                    >
                      <XCircle className="w-5 h-5" />
                      REJECT
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'queue' && (
          <div className="divide-y divide-[#333]">
            {queue.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                <Bell className="w-12 h-12 mx-auto mb-3 text-gray-500" />
                Notification queue is empty
              </div>
            ) : (
              <>
                <div className="p-4 bg-[#1a1a1a] text-gray-400 text-sm">
                  These notifications will be included in the next daily digest at 8am ET
                </div>
                {queue.map((notif, i) => (
                  <div key={i} className="p-4 hover:bg-[#333] transition-colors">
                    <div className="flex items-start gap-3">
                      <Bell className="w-5 h-5 text-purple-400 mt-0.5" />
                      <div>
                        <p className="text-white font-medium">{notif.title}</p>
                        <p className="text-gray-400 text-sm">{notif.body}</p>
                        <p className="text-gray-500 text-xs mt-1">
                          {formatTime(notif.created_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Architecture Diagram */}
      <div className="p-6 bg-[#2a2a2a] rounded-xl border border-[#333]">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Eye className="w-5 h-5 text-pink-400" />
          Autonomous Loop Architecture
        </h3>
        <div className="text-gray-400 text-sm font-mono whitespace-pre overflow-x-auto">
{`                    REROOTS AI™ AUTONOMOUS SYSTEM
    
    ┌─────────────────────────────────────────────┐
    │              ORCHESTRATOR BRAIN              │
    │         (single entry point for all)         │
    └──────┬──────────┬──────────┬────────┬────────┘
           │          │          │        │
        CRASH       BUG      SUGGEST   VIOLATE
           │          │          │        │
        Auto-      Known     Classify   Block
        restart    fix DB    by risk    always
           │          │          │        │
        Test       Patch      Safe?    Notify
        health     file         │      Tj once
           │          │       Yes/No
        Report     Restart      │
        once       backend   Auto-apply
                              OR
                           APPROVE?
                              │
                         WhatsApp Tj
                         one message`}
        </div>
      </div>
    </div>
  );
};

export default OrchestratorDashboard;
