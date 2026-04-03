/**
 * VoiceCallsDashboard - Voice AI Call History & Analytics
 * ═══════════════════════════════════════════════════════════════════
 * Admin dashboard for viewing voice call history and transcripts.
 * © 2025 Reroots Aesthetics Inc. All rights reserved.
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect } from 'react';
import { 
  Phone, 
  Clock, 
  Calendar, 
  ChevronRight, 
  X, 
  User, 
  Bot,
  PhoneCall,
  PhoneOff,
  AlertCircle,
  TrendingUp,
  Loader2
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

export default function VoiceCallsDashboard() {
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedCall, setSelectedCall] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Load calls and stats in parallel
      const [callsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/voice/calls?limit=50`),
        fetch(`${API_URL}/api/voice/stats?days=7`)
      ]);

      if (callsRes.ok) {
        const callsData = await callsRes.json();
        setCalls(callsData.calls || []);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData.stats || null);
      }
    } catch (err) {
      console.error('Failed to load voice data:', err);
      setError('Failed to load call data');
    } finally {
      setIsLoading(false);
    }
  };

  const loadCallDetails = async (sessionId) => {
    try {
      const response = await fetch(`${API_URL}/api/voice/calls/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setSelectedCall(data.call);
      }
    } catch (err) {
      console.error('Failed to load call details:', err);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getOutcomeColor = (outcome) => {
    switch (outcome) {
      case 'completed': return 'text-green-400 bg-green-400/10';
      case 'abandoned': return 'text-yellow-400 bg-yellow-400/10';
      case 'error': return 'text-red-400 bg-red-400/10';
      default: return 'text-gray-400 bg-gray-400/10';
    }
  };

  const getOutcomeIcon = (outcome) => {
    switch (outcome) {
      case 'completed': return PhoneOff;
      case 'abandoned': return AlertCircle;
      default: return Phone;
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0a0a0c]">
        <Loader2 className="w-8 h-8 animate-spin text-[#C8A96A]" />
      </div>
    );
  }

  return (
    <div className="h-full flex bg-[#0a0a0c]" data-testid="voice-calls-dashboard">
      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#C8A96A]/20 flex items-center justify-center">
                <PhoneCall className="w-5 h-5 text-[#C8A96A]" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Voice Calls</h2>
                <p className="text-sm text-gray-400">Reroots AI Voice conversation history</p>
              </div>
            </div>
            <button
              onClick={loadData}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Stats Row */}
        {stats && (
          <div className="px-6 py-4 border-b border-gray-800">
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
                  <Phone className="w-3 h-3" />
                  Total Calls (7d)
                </div>
                <div className="text-2xl font-bold text-white">{stats.total_calls}</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
                  <Clock className="w-3 h-3" />
                  Avg Duration
                </div>
                <div className="text-2xl font-bold text-white">
                  {formatDuration(stats.avg_duration_seconds)}
                </div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
                  <PhoneOff className="w-3 h-3 text-green-400" />
                  Completed
                </div>
                <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
                  <AlertCircle className="w-3 h-3 text-yellow-400" />
                  Abandoned
                </div>
                <div className="text-2xl font-bold text-yellow-400">{stats.abandoned}</div>
              </div>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="px-6 py-4">
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
              {error}
            </div>
          </div>
        )}

        {/* Calls Table */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {calls.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Phone className="w-12 h-12 text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-400 mb-2">No voice calls yet</h3>
              <p className="text-sm text-gray-500">
                Voice calls will appear here when customers use Reroots AI Voice
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase tracking-wider">
                  <th className="pb-3 font-medium">Phone</th>
                  <th className="pb-3 font-medium">Date</th>
                  <th className="pb-3 font-medium">Duration</th>
                  <th className="pb-3 font-medium">Outcome</th>
                  <th className="pb-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {calls.map((call) => {
                  const OutcomeIcon = getOutcomeIcon(call.outcome);
                  return (
                    <tr
                      key={call.session_id}
                      className="hover:bg-gray-800/50 cursor-pointer transition-colors"
                      onClick={() => loadCallDetails(call.session_id)}
                    >
                      <td className="py-4">
                        <div className="flex items-center gap-2">
                          <Phone className="w-4 h-4 text-gray-500" />
                          <span className="text-white font-mono">{call.phone_number}</span>
                        </div>
                      </td>
                      <td className="py-4">
                        <span className="text-gray-400 text-sm">{formatDate(call.start_time)}</span>
                      </td>
                      <td className="py-4">
                        <span className="text-white">{formatDuration(call.duration_seconds)}</span>
                      </td>
                      <td className="py-4">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getOutcomeColor(call.outcome)}`}>
                          <OutcomeIcon className="w-3 h-3" />
                          {call.outcome || 'unknown'}
                        </span>
                      </td>
                      <td className="py-4 text-right">
                        <ChevronRight className="w-4 h-4 text-gray-500" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Transcript Panel */}
      {selectedCall && (
        <div className="w-96 border-l border-gray-800 flex flex-col">
          <div className="px-4 py-4 border-b border-gray-800 flex items-center justify-between">
            <h3 className="font-medium text-white">Call Transcript</h3>
            <button
              onClick={() => setSelectedCall(null)}
              className="p-1 hover:bg-gray-800 rounded transition-colors"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          <div className="px-4 py-3 border-b border-gray-800 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Phone:</span>
              <span className="text-white font-mono">{selectedCall.phone_number}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Duration:</span>
              <span className="text-white">{formatDuration(selectedCall.duration_seconds)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Date:</span>
              <span className="text-white">{formatDate(selectedCall.start_time)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Outcome:</span>
              <span className={`px-2 py-0.5 rounded-full text-xs ${getOutcomeColor(selectedCall.outcome)}`}>
                {selectedCall.outcome}
              </span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {(!selectedCall.transcript || selectedCall.transcript.length === 0) ? (
              <p className="text-sm text-gray-500 text-center py-8">
                No transcript available
              </p>
            ) : (
              selectedCall.transcript.map((entry, index) => (
                <div
                  key={index}
                  className={`flex gap-3 ${entry.speaker === 'agent' ? '' : 'flex-row-reverse'}`}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                    entry.speaker === 'agent' 
                      ? 'bg-[#C8A96A]/20' 
                      : 'bg-gray-700'
                  }`}>
                    {entry.speaker === 'agent' 
                      ? <Bot className="w-4 h-4 text-[#C8A96A]" />
                      : <User className="w-4 h-4 text-gray-400" />
                    }
                  </div>
                  <div className={`flex-1 p-3 rounded-lg text-sm ${
                    entry.speaker === 'agent'
                      ? 'bg-gray-800 text-white'
                      : 'bg-[#C8A96A]/10 text-[#C8A96A]'
                  }`}>
                    <p>{entry.text}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {entry.timestamp ? formatDate(entry.timestamp) : ''}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
