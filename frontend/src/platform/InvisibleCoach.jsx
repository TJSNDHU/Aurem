/**
 * Invisible AI Sales Coach
 * AI listens during in-person meetings and whispers suggestions
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  Mic, MicOff, Volume2, VolumeX, Play, Pause, Square,
  AlertCircle, CheckCircle, Lightbulb, TrendingUp, DollarSign,
  Clock, Eye, EyeOff, Zap, FileText, Download
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const InvisibleCoach = ({ token }) => {
  const [isActive, setIsActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [recentScans, setRecentScans] = useState([]);
  const [selectedScan, setSelectedScan] = useState(null);
  const [coachSession, setCoachSession] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [transcript, setTranscript] = useState([]);
  const [wsConnection, setWsConnection] = useState(null);

  useEffect(() => {
    fetchRecentScans();
  }, []);

  useEffect(() => {
    // Cleanup WebSocket on unmount
    return () => {
      if (wsConnection) {
        wsConnection.close();
      }
    };
  }, [wsConnection]);

  const fetchRecentScans = async () => {
    try {
      const response = await fetch(`${API_URL}/api/scanner/scans`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setRecentScans(data.scans || []);
      }
    } catch (err) {
      console.error('Failed to fetch scans:', err);
    }
  };

  const startCoachSession = async (scan) => {
    try {
      const response = await fetch(`${API_URL}/api/coach/start-invisible`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          scan_id: scan.scan_id,
          meeting_type: 'in_person',
          silent_mode: true
        })
      });

      if (response.ok) {
        const data = await response.json();
        setCoachSession(data);
        setSelectedScan(scan);
        setIsActive(true);
        
        // Connect to WebSocket for real-time suggestions
        connectWebSocket(data.coach_id);
      }
    } catch (err) {
      console.error('Failed to start coach session:', err);
    }
  };

  const connectWebSocket = (coachId) => {
    const wsUrl = `${API_URL.replace('http', 'ws')}/ws/coach/${coachId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('Coach WebSocket connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'suggestion') {
        setSuggestions(prev => [data.suggestion, ...prev].slice(0, 5));
      } else if (data.type === 'transcript') {
        setTranscript(prev => [...prev, data]);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('Coach WebSocket disconnected');
    };

    setWsConnection(ws);
  };

  const stopCoachSession = () => {
    if (wsConnection) {
      wsConnection.close();
    }
    setIsActive(false);
    setCoachSession(null);
    setSuggestions([]);
    setTranscript([]);
  };

  const sendSpeech = (speaker, text) => {
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      wsConnection.send(JSON.stringify({
        type: 'speech',
        speaker: speaker,
        text: text
      }));
    }
  };

  const getSuggestionIcon = (type) => {
    switch (type) {
      case 'pricing': return DollarSign;
      case 'objection_handler': return AlertCircle;
      case 'technical_answer': return Zap;
      case 'talking_point': return Lightbulb;
      default: return CheckCircle;
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'urgent': return 'border-red-500/50 bg-red-500/10';
      case 'high': return 'border-yellow-500/50 bg-yellow-500/10';
      case 'medium': return 'border-blue-500/50 bg-blue-500/10';
      default: return 'border-gray-500/50 bg-gray-500/10';
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#050505] p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-light text-[#F4F4F4] tracking-wider mb-2 flex items-center gap-2">
            <EyeOff className="w-6 h-6 text-[#D4AF37]" />
            Invisible AI Sales Coach
          </h1>
          <p className="text-sm text-[#666]">
            AI listens silently during meetings and whispers suggestions to your earpiece. Customer never knows.
          </p>
        </div>

        {!isActive ? (
          // Setup Screen
          <div className="space-y-6">
            {/* Info Card */}
            <div className="p-6 bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-lg">
              <div className="flex items-start gap-4 mb-4">
                <Eye className="w-6 h-6 text-purple-400 mt-1" />
                <div>
                  <h2 className="text-lg font-medium text-purple-400 mb-2">How Invisible Coach Works</h2>
                  <ul className="space-y-2 text-sm text-purple-400/80">
                    <li>• AI listens to your in-person meeting through your device microphone</li>
                    <li>• Analyzes customer questions, objections, and concerns in real-time</li>
                    <li>• Whispers instant suggestions to your wireless earpiece</li>
                    <li>• Customer never knows you have AI assistance</li>
                    <li>• Full transcript and coaching report after the meeting</li>
                  </ul>
                </div>
              </div>

              <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-400 mt-0.5" />
                <p className="text-xs text-yellow-400">
                  <strong>Privacy Note:</strong> Always inform participants if recording is enabled. Use silent suggestions mode for privacy.
                </p>
              </div>
            </div>

            {/* Select Scan */}
            <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
              <h2 className="text-lg font-medium text-[#F4F4F4] mb-4">Select Customer Scan for Context</h2>

              {recentScans.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 text-[#333] mx-auto mb-4" />
                  <p className="text-sm text-[#666]">No scans available. Scan the customer's website first to provide AI with context.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {recentScans.slice(0, 4).map((scan) => (
                    <div
                      key={scan.scan_id}
                      onClick={() => startCoachSession(scan)}
                      className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg cursor-pointer hover:border-[#D4AF37]/30 transition-all"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <h3 className="text-sm font-medium text-[#F4F4F4] mb-1">{scan.website_url}</h3>
                          <p className="text-xs text-[#666]">{new Date(scan.scan_date).toLocaleDateString()}</p>
                        </div>
                        <div className="text-2xl font-bold text-[#D4AF37]">
                          {scan.overall_score}
                        </div>
                      </div>
                      <div className="flex gap-2 text-xs mb-3">
                        <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded">
                          {scan.critical_issues} Critical
                        </span>
                        <span className="px-2 py-1 bg-yellow-500/10 text-yellow-400 rounded">
                          {scan.issues_found} Total
                        </span>
                      </div>
                      <button className="w-full px-3 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg text-sm font-medium hover:opacity-90 transition-all flex items-center justify-center gap-2">
                        <Play className="w-4 h-4" />
                        Start Coach
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          // Active Coaching Screen
          <div className="space-y-6">
            {/* Control Panel */}
            <div className="p-6 bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/40 rounded-lg">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                  <div>
                    <h2 className="text-lg font-medium text-[#F4F4F4]">Coaching Active</h2>
                    <p className="text-xs text-[#888]">{selectedScan?.website_url}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIsMuted(!isMuted)}
                    className={`p-2 rounded-lg ${isMuted ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}
                  >
                    {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  </button>
                  <button
                    onClick={stopCoachSession}
                    className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/30 transition-all flex items-center gap-2"
                  >
                    <Square className="w-4 h-4" />
                    Stop Coach
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
                  <Clock className="w-5 h-5 text-[#888] mx-auto mb-1" />
                  <div className="text-xs text-[#666]">Duration</div>
                  <div className="text-sm font-medium text-[#F4F4F4]">--:--</div>
                </div>
                <div className="p-3 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
                  <Lightbulb className="w-5 h-5 text-yellow-400 mx-auto mb-1" />
                  <div className="text-xs text-[#666]">Suggestions</div>
                  <div className="text-sm font-medium text-[#F4F4F4]">{suggestions.length}</div>
                </div>
                <div className="p-3 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
                  <Volume2 className="w-5 h-5 text-green-400 mx-auto mb-1" />
                  <div className="text-xs text-[#666]">Status</div>
                  <div className="text-sm font-medium text-green-400">Listening</div>
                </div>
              </div>
            </div>

            {/* Live Suggestions */}
            <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
              <h2 className="text-lg font-medium text-[#F4F4F4] mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-yellow-400" />
                Live Suggestions
              </h2>

              {suggestions.length === 0 ? (
                <div className="text-center py-12">
                  <Lightbulb className="w-12 h-12 text-[#333] mx-auto mb-4" />
                  <p className="text-sm text-[#666]">Listening for customer questions...</p>
                  <p className="text-xs text-[#555] mt-2">AI will suggest responses as the conversation progresses</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {suggestions.map((suggestion, idx) => {
                    const Icon = getSuggestionIcon(suggestion.type);
                    return (
                      <div
                        key={idx}
                        className={`p-4 border rounded-lg ${getPriorityColor(suggestion.priority)}`}
                      >
                        <div className="flex items-start gap-3">
                          <Icon className="w-5 h-5 mt-1" />
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-xs font-medium uppercase tracking-wider">
                                {suggestion.type.replace('_', ' ')}
                              </span>
                              {suggestion.priority === 'urgent' && (
                                <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs font-medium">
                                  URGENT
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-[#F4F4F4] whitespace-pre-line">{suggestion.suggestion}</p>
                            <div className="mt-2 text-xs text-[#666]">
                              Confidence: {(suggestion.confidence * 100).toFixed(0)}%
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Demo Test Inputs */}
            <div className="p-4 bg-[#0A0A0A] border border-[#252525] rounded-lg">
              <p className="text-xs text-[#666] mb-3">Test the coach (simulation):</p>
              <div className="flex gap-2">
                <button
                  onClick={() => sendSpeech('customer', 'How much does this cost?')}
                  className="px-3 py-2 bg-[#1A1A1A] text-[#888] rounded text-xs hover:text-[#F4F4F4] transition-all"
                >
                  Test: Price Question
                </button>
                <button
                  onClick={() => sendSpeech('customer', 'What is the ROI on this?')}
                  className="px-3 py-2 bg-[#1A1A1A] text-[#888] rounded text-xs hover:text-[#F4F4F4] transition-all"
                >
                  Test: ROI Question
                </button>
                <button
                  onClick={() => sendSpeech('customer', 'This seems too expensive for us')}
                  className="px-3 py-2 bg-[#1A1A1A] text-[#888] rounded text-xs hover:text-[#F4F4F4] transition-all"
                >
                  Test: Objection
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InvisibleCoach;
