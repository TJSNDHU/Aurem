import React, { useState, useEffect, useCallback } from 'react';
import { 
  Send, 
  Users, 
  Clock, 
  CheckCircle,
  XCircle,
  RefreshCw,
  Calendar,
  MessageSquare,
  Mail,
  Bell,
  TrendingUp,
  Filter
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

export default function ProactiveOutreachDashboard() {
  const [campaigns, setCampaigns] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };

      const [campaignsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/outreach/campaigns`, { headers }),
        fetch(`${API_URL}/api/outreach/stats`, { headers })
      ]);

      if (campaignsRes.ok) {
        const data = await campaignsRes.json();
        setCampaigns(data.campaigns || []);
      }

      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch outreach data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getStatusBadge = (status) => {
    const styles = {
      active: 'bg-green-100 text-green-700',
      paused: 'bg-amber-100 text-amber-700',
      completed: 'bg-blue-100 text-blue-700',
      draft: 'bg-gray-100 text-gray-700'
    };
    return styles[status] || styles.draft;
  };

  const getChannelIcon = (channel) => {
    switch (channel) {
      case 'email': return <Mail className="w-4 h-4" />;
      case 'sms': return <MessageSquare className="w-4 h-4" />;
      case 'push': return <Bell className="w-4 h-4" />;
      default: return <Send className="w-4 h-4" />;
    }
  };

  return (
    <div className="p-6 space-y-6" data-testid="proactive-outreach-dashboard">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Send className="w-8 h-8 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Proactive Outreach</h1>
            <p className="text-sm text-gray-500">Automated customer engagement campaigns</p>
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500">Total Sent</div>
            <div className="text-2xl font-bold text-gray-900">{stats.total_sent || 0}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500">Open Rate</div>
            <div className="text-2xl font-bold text-green-600">{stats.open_rate || 0}%</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500">Click Rate</div>
            <div className="text-2xl font-bold text-blue-600">{stats.click_rate || 0}%</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500">Conversions</div>
            <div className="text-2xl font-bold text-indigo-600">{stats.conversions || 0}</div>
          </div>
        </div>
      )}

      {/* Campaigns */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Campaigns</h2>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="completed">Completed</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
          </div>
        ) : campaigns.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Send className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No campaigns found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {campaigns
              .filter(c => filter === 'all' || c.status === filter)
              .map((campaign, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {getChannelIcon(campaign.channel)}
                      <div>
                        <div className="font-medium text-gray-900">{campaign.name}</div>
                        <div className="text-sm text-gray-500 flex items-center gap-2">
                          <Users className="w-3 h-3" />
                          {campaign.audience_size || 0} recipients
                          <span className="mx-1">·</span>
                          <Calendar className="w-3 h-3" />
                          {campaign.scheduled || 'Not scheduled'}
                        </div>
                      </div>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadge(campaign.status)}`}>
                      {campaign.status}
                    </span>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
