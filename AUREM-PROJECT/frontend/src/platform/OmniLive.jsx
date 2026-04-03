/**
 * OmniLive Dashboard - Phase 8.5
 * "The Command Center" - Real-time visualization of the Omni-Bridge
 * 
 * Features:
 * - Real-time WebSocket feed of OmniDimension activity
 * - Business ID filtering (ReRoots vs TJ Auto)
 * - Cost-savings ticker with ROI calculations
 * - Live call/lead status updates
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  MessageSquare,
  Building2,
  TrendingUp,
  DollarSign,
  Clock,
  Activity,
  Filter,
  RefreshCw,
  Zap,
  Users,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  Radio,
  Globe,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ChevronDown,
  BarChart3,
  Wallet,
  Timer
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Cost constants
const OMNIDIM_COST_PER_MIN = 0.07;
const HUMAN_COST_PER_CALL = 15.00;
const AVG_CALL_DURATION_MIN = 2.5; // Average call duration in minutes

// Business configurations
const BUSINESSES = [
  { id: 'all', name: 'All Businesses', icon: Globe, color: 'violet' },
  { id: 'reroots', name: 'ReRoots Skincare', icon: Sparkles, color: 'pink' },
  { id: 'tj_auto', name: 'TJ Auto Clinic', icon: Building2, color: 'blue' },
  { id: 'polaris', name: 'Polaris Built', icon: Zap, color: 'amber' }
];

const OmniLive = () => {
  // State
  const [activities, setActivities] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState('all');
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [stats, setStats] = useState({
    totalCalls: 0,
    totalLeads: 0,
    totalDuration: 0,
    avgSentiment: 0,
    costSaved: 0
  });
  const [showBusinessDropdown, setShowBusinessDropdown] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // Refs
  const activityListRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const wsRef = useRef(null);

  // Fetch activity data
  const fetchActivity = useCallback(async () => {
    try {
      const businessParam = selectedBusiness !== 'all' ? `?business_id=${selectedBusiness}` : '';
      const response = await fetch(`${API_URL}/api/brain/omnidim-activity${businessParam}`);
      
      if (response.ok) {
        const data = await response.json();
        
        // Combine calls and leads
        const allActivity = [
          ...(data.calls?.items || []).map(c => ({ ...c, activityType: 'call' })),
          ...(data.leads?.items || []).map(l => ({ ...l, activityType: 'lead' }))
        ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        setActivities(allActivity);
        
        // Calculate stats
        const calls = data.calls?.items || [];
        const leads = data.leads?.items || [];
        const totalDuration = calls.reduce((sum, c) => sum + (c.duration || 0), 0);
        const avgSentiment = calls.length > 0 
          ? calls.reduce((sum, c) => sum + (c.sentiment_score || 0), 0) / calls.length 
          : 0;
        
        // Cost savings calculation
        const totalCalls = calls.length;
        const humanCost = totalCalls * HUMAN_COST_PER_CALL;
        const omnidimCost = (totalDuration / 60) * OMNIDIM_COST_PER_MIN;
        const costSaved = humanCost - omnidimCost;
        
        setStats({
          totalCalls: calls.length,
          totalLeads: leads.length,
          totalDuration,
          avgSentiment,
          costSaved: Math.max(0, costSaved)
        });
        
        setLastUpdate(new Date());
        setIsConnected(true);
      }
    } catch (error) {
      console.error('Failed to fetch activity:', error);
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  }, [selectedBusiness]);

  // Fetch businesses
  const fetchBusinesses = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/omnidim/businesses`);
      if (response.ok) {
        const data = await response.json();
        setBusinesses(data.businesses || []);
      }
    } catch (error) {
      console.error('Failed to fetch businesses:', error);
    }
  }, []);

  // Setup polling for real-time updates
  useEffect(() => {
    fetchActivity();
    fetchBusinesses();
    
    // Poll every 5 seconds for updates
    pollIntervalRef.current = setInterval(fetchActivity, 5000);
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [fetchActivity, fetchBusinesses]);

  // Refetch when business filter changes
  useEffect(() => {
    setIsLoading(true);
    fetchActivity();
  }, [selectedBusiness, fetchActivity]);

  // Format duration
  const formatDuration = (seconds) => {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Format currency
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  // Get sentiment color
  const getSentimentColor = (sentiment) => {
    if (sentiment === 'positive' || sentiment > 0.3) return 'text-emerald-400';
    if (sentiment === 'negative' || sentiment < -0.3) return 'text-red-400';
    return 'text-amber-400';
  };

  // Get sentiment icon
  const getSentimentIcon = (sentiment) => {
    if (sentiment === 'positive' || sentiment > 0.3) return <ArrowUpRight className="w-4 h-4" />;
    if (sentiment === 'negative' || sentiment < -0.3) return <ArrowDownRight className="w-4 h-4" />;
    return <Activity className="w-4 h-4" />;
  };

  // Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'in_progress': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'new': return 'bg-violet-500/20 text-violet-400 border-violet-500/30';
      default: return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
    }
  };

  // Get business color
  const getBusinessColor = (businessId) => {
    const colors = {
      reroots: 'from-pink-500/20 to-pink-600/10 border-pink-500/30',
      tj_auto: 'from-blue-500/20 to-blue-600/10 border-blue-500/30',
      polaris: 'from-amber-500/20 to-amber-600/10 border-amber-500/30',
      finance: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30'
    };
    return colors[businessId] || 'from-zinc-500/20 to-zinc-600/10 border-zinc-500/30';
  };

  // Get selected business info
  const getSelectedBusinessInfo = () => {
    return BUSINESSES.find(b => b.id === selectedBusiness) || BUSINESSES[0];
  };

  // Render activity item
  const renderActivityItem = (activity, index) => {
    const isCall = activity.activityType === 'call';
    const timestamp = new Date(activity.created_at).toLocaleTimeString();
    
    return (
      <div
        key={activity.call_id || activity.id || index}
        className={`p-4 rounded-xl border bg-gradient-to-br ${getBusinessColor(activity.business_id)} 
          backdrop-blur-sm animate-fadeIn hover:scale-[1.01] transition-all duration-300`}
        style={{ animationDelay: `${index * 50}ms` }}
      >
        <div className="flex items-start justify-between gap-3">
          {/* Icon & Type */}
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isCall ? 'bg-violet-500/20' : 'bg-pink-500/20'}`}>
              {isCall ? (
                activity.status === 'completed' ? (
                  <PhoneOutgoing className="w-5 h-5 text-violet-400" />
                ) : (
                  <PhoneIncoming className="w-5 h-5 text-violet-400" />
                )
              ) : (
                <MessageSquare className="w-5 h-5 text-pink-400" />
              )}
            </div>
            
            <div className="flex-1 min-w-0">
              {/* Title */}
              <div className="flex items-center gap-2">
                <span className="font-medium text-white truncate">
                  {isCall ? (
                    activity.customer_phone_masked || 'Voice Call'
                  ) : (
                    activity.customer_name || 'Social Lead'
                  )}
                </span>
                <span className={`px-2 py-0.5 text-xs rounded-full border ${getStatusColor(activity.status)}`}>
                  {activity.status || 'new'}
                </span>
              </div>
              
              {/* Summary/Message */}
              <p className="text-sm text-zinc-400 mt-1 line-clamp-2">
                {activity.summary || activity.message || 'No details available'}
              </p>
              
              {/* Meta row */}
              <div className="flex items-center gap-4 mt-2 text-xs text-zinc-500">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timestamp}
                </span>
                
                {isCall && activity.duration && (
                  <span className="flex items-center gap-1">
                    <Timer className="w-3 h-3" />
                    {formatDuration(activity.duration)}
                  </span>
                )}
                
                {activity.sentiment && (
                  <span className={`flex items-center gap-1 ${getSentimentColor(activity.sentiment)}`}>
                    {getSentimentIcon(activity.sentiment)}
                    {typeof activity.sentiment === 'string' ? activity.sentiment : `${(activity.sentiment_score * 100).toFixed(0)}%`}
                  </span>
                )}
                
                {activity.business_id && (
                  <span className="flex items-center gap-1 text-zinc-400">
                    <Building2 className="w-3 h-3" />
                    {activity.business_id}
                  </span>
                )}
              </div>
            </div>
          </div>
          
          {/* Right side - Agent info */}
          {activity.agent_name && (
            <div className="text-right text-xs text-zinc-500">
              <span className="text-zinc-400">{activity.agent_name}</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-gradient-to-br from-violet-500/20 to-pink-500/20 rounded-2xl border border-violet-500/30">
              <Radio className="w-8 h-8 text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
                Omni-Live Command Center
              </h1>
              <p className="text-zinc-500 text-sm">Real-time Omni-Bridge Activity Monitor</p>
            </div>
          </div>
          
          {/* Connection Status */}
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm
              ${isConnected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}
            >
              <span className={`w-2 h-2 rounded-full animate-pulse 
                ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} 
              />
              {isConnected ? 'Live' : 'Disconnected'}
            </div>
            
            <button
              onClick={fetchActivity}
              className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-5 h-5 text-zinc-400 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          {/* Total Calls */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-violet-500/10 to-violet-600/5 border border-violet-500/20">
            <div className="flex items-center gap-2 text-violet-400 mb-2">
              <Phone className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Total Calls</span>
            </div>
            <div className="text-3xl font-bold text-white">{stats.totalCalls}</div>
          </div>
          
          {/* Total Leads */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-pink-500/10 to-pink-600/5 border border-pink-500/20">
            <div className="flex items-center gap-2 text-pink-400 mb-2">
              <Users className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Social Leads</span>
            </div>
            <div className="text-3xl font-bold text-white">{stats.totalLeads}</div>
          </div>
          
          {/* Total Duration */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/20">
            <div className="flex items-center gap-2 text-blue-400 mb-2">
              <Timer className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Talk Time</span>
            </div>
            <div className="text-3xl font-bold text-white">{formatDuration(stats.totalDuration)}</div>
          </div>
          
          {/* Avg Sentiment */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/20">
            <div className="flex items-center gap-2 text-emerald-400 mb-2">
              <TrendingUp className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Sentiment</span>
            </div>
            <div className={`text-3xl font-bold ${getSentimentColor(stats.avgSentiment)}`}>
              {stats.avgSentiment > 0 ? '+' : ''}{(stats.avgSentiment * 100).toFixed(0)}%
            </div>
          </div>
          
          {/* Cost Saved - The "Juice" */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-amber-500/10 to-amber-600/5 border border-amber-500/20 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-20 h-20 bg-amber-500/10 rounded-full blur-2xl" />
            <div className="flex items-center gap-2 text-amber-400 mb-2 relative">
              <Wallet className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Total Saved</span>
            </div>
            <div className="text-3xl font-bold text-amber-400 relative">
              {formatCurrency(stats.costSaved)}
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              vs ${HUMAN_COST_PER_CALL}/call human
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Activity Feed - Takes 2 columns */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter Bar */}
            <div className="flex items-center justify-between p-4 rounded-2xl bg-zinc-900/50 border border-zinc-800">
              <div className="flex items-center gap-3">
                <Filter className="w-5 h-5 text-zinc-500" />
                <span className="text-sm text-zinc-400">Filter by Business:</span>
                
                {/* Business Dropdown */}
                <div className="relative">
                  <button
                    onClick={() => setShowBusinessDropdown(!showBusinessDropdown)}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 
                      border border-zinc-700 transition-colors"
                  >
                    {React.createElement(getSelectedBusinessInfo().icon, { 
                      className: `w-4 h-4 text-${getSelectedBusinessInfo().color}-400` 
                    })}
                    <span className="text-white">{getSelectedBusinessInfo().name}</span>
                    <ChevronDown className={`w-4 h-4 text-zinc-400 transition-transform 
                      ${showBusinessDropdown ? 'rotate-180' : ''}`} 
                    />
                  </button>
                  
                  {showBusinessDropdown && (
                    <div className="absolute top-full left-0 mt-2 w-56 py-2 rounded-xl bg-zinc-800 
                      border border-zinc-700 shadow-xl z-50 animate-fadeIn"
                    >
                      {BUSINESSES.map(business => (
                        <button
                          key={business.id}
                          onClick={() => {
                            setSelectedBusiness(business.id);
                            setShowBusinessDropdown(false);
                          }}
                          className={`w-full flex items-center gap-3 px-4 py-2 hover:bg-zinc-700 
                            transition-colors ${selectedBusiness === business.id ? 'bg-zinc-700' : ''}`}
                        >
                          {React.createElement(business.icon, { 
                            className: `w-4 h-4 text-${business.color}-400` 
                          })}
                          <span className="text-white">{business.name}</span>
                          {selectedBusiness === business.id && (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 ml-auto" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              
              {lastUpdate && (
                <span className="text-xs text-zinc-500">
                  Last updated: {lastUpdate.toLocaleTimeString()}
                </span>
              )}
            </div>
            
            {/* Activity List */}
            <div 
              ref={activityListRef}
              className="space-y-3 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar"
            >
              {isLoading && activities.length === 0 ? (
                <div className="flex items-center justify-center p-12">
                  <RefreshCw className="w-8 h-8 text-violet-400 animate-spin" />
                </div>
              ) : activities.length === 0 ? (
                <div className="text-center p-12 rounded-2xl bg-zinc-900/50 border border-zinc-800">
                  <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-zinc-400 mb-2">No Activity Yet</h3>
                  <p className="text-sm text-zinc-500">
                    Post-call webhooks and social leads will appear here in real-time
                  </p>
                </div>
              ) : (
                activities.map((activity, index) => renderActivityItem(activity, index))
              )}
            </div>
          </div>
          
          {/* Right Sidebar - Stats & Info */}
          <div className="space-y-4">
            {/* Cost Savings Breakdown */}
            <div className="p-6 rounded-2xl bg-gradient-to-br from-amber-500/10 to-orange-600/5 border border-amber-500/20">
              <h3 className="flex items-center gap-2 text-lg font-semibold text-amber-400 mb-4">
                <DollarSign className="w-5 h-5" />
                Cost Savings Breakdown
              </h3>
              
              <div className="space-y-4">
                {/* Human Cost */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Human Agent Cost</span>
                  <span className="text-red-400 font-mono">
                    ${(stats.totalCalls * HUMAN_COST_PER_CALL).toFixed(2)}
                  </span>
                </div>
                
                {/* OmniDim Cost */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">OmniDim Cost</span>
                  <span className="text-emerald-400 font-mono">
                    ${((stats.totalDuration / 60) * OMNIDIM_COST_PER_MIN).toFixed(2)}
                  </span>
                </div>
                
                <div className="h-px bg-zinc-700" />
                
                {/* Net Savings */}
                <div className="flex items-center justify-between">
                  <span className="text-white font-semibold">Net Savings</span>
                  <span className="text-2xl font-bold text-amber-400">
                    {formatCurrency(stats.costSaved)}
                  </span>
                </div>
                
                {/* Savings Percentage */}
                <div className="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-amber-300">Reduction vs Human</span>
                    <span className="text-lg font-bold text-amber-400">97%</span>
                  </div>
                  <div className="w-full h-2 bg-zinc-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full transition-all duration-1000"
                      style={{ width: '97%' }}
                    />
                  </div>
                </div>
                
                {/* Cost Formula */}
                <div className="mt-4 p-3 rounded-xl bg-zinc-800/50 border border-zinc-700">
                  <p className="text-xs text-zinc-500">
                    <span className="text-amber-400">${OMNIDIM_COST_PER_MIN}/min</span> OmniDim vs{' '}
                    <span className="text-red-400">${HUMAN_COST_PER_CALL}/call</span> Human Agent
                  </p>
                </div>
              </div>
            </div>
            
            {/* Business Registry */}
            <div className="p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800">
              <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
                <Building2 className="w-5 h-5 text-violet-400" />
                Traffic Controller
              </h3>
              
              <div className="space-y-3">
                {businesses.length === 0 ? (
                  <p className="text-sm text-zinc-500">Loading businesses...</p>
                ) : (
                  businesses.map(business => (
                    <div 
                      key={business.business_id}
                      className={`p-3 rounded-xl border transition-all cursor-pointer
                        ${selectedBusiness === business.business_id 
                          ? 'bg-violet-500/10 border-violet-500/30' 
                          : 'bg-zinc-800/50 border-zinc-700 hover:bg-zinc-800'}`}
                      onClick={() => setSelectedBusiness(business.business_id)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-white">{business.name}</div>
                          <div className="text-xs text-zinc-500">{business.primary_agent}</div>
                        </div>
                        <div className={`px-2 py-1 rounded-lg text-xs
                          ${business.vertical === 'skincare' ? 'bg-pink-500/20 text-pink-400' :
                            business.vertical === 'automotive' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-zinc-500/20 text-zinc-400'}`}
                        >
                          {business.vertical}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
            
            {/* Quick Actions */}
            <div className="p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800">
              <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
                <Zap className="w-5 h-5 text-amber-400" />
                Quick Actions
              </h3>
              
              <div className="space-y-2">
                <button 
                  onClick={() => window.location.href = '/platform/voice'}
                  className="w-full flex items-center gap-3 p-3 rounded-xl bg-violet-500/10 
                    border border-violet-500/20 hover:bg-violet-500/20 transition-colors"
                >
                  <Phone className="w-5 h-5 text-violet-400" />
                  <span className="text-white">Voice Command Center</span>
                </button>
                
                <button 
                  onClick={() => window.location.href = '/platform/inbox'}
                  className="w-full flex items-center gap-3 p-3 rounded-xl bg-pink-500/10 
                    border border-pink-500/20 hover:bg-pink-500/20 transition-colors"
                >
                  <MessageSquare className="w-5 h-5 text-pink-400" />
                  <span className="text-white">Unified Inbox</span>
                </button>
                
                <button 
                  onClick={() => window.location.href = '/platform/brain'}
                  className="w-full flex items-center gap-3 p-3 rounded-xl bg-emerald-500/10 
                    border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                >
                  <BarChart3 className="w-5 h-5 text-emerald-400" />
                  <span className="text-white">Brain Debugger</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Custom styles */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out forwards;
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(39, 39, 42, 0.5);
          border-radius: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(113, 113, 122, 0.5);
          border-radius: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(113, 113, 122, 0.8);
        }
      `}</style>
    </div>
  );
};

export default OmniLive;
