/**
 * AI Voice Sales Co-Pilot
 * Auto-calls customers after scan, voice training, call history
 */

import React, { useState, useEffect } from 'react';
import { 
  Phone, PhoneCall, Mic, MicOff, Play, Pause, Download,
  Clock, CheckCircle, XCircle, TrendingUp, Users, Zap,
  AlertCircle, Sparkles, Volume2, FileAudio
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const VoiceSalesAgent = ({ token }) => {
  const [activeTab, setActiveTab] = useState('auto-calls'); // auto-calls, voice-training, call-history
  const [recentScans, setRecentScans] = useState([]);
  const [callHistory, setCallHistory] = useState([]);
  const [voiceProfiles, setVoiceProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedScan, setSelectedScan] = useState(null);

  useEffect(() => {
    fetchRecentScans();
    fetchVoiceProfiles();
  }, []);

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

  const fetchVoiceProfiles = async () => {
    try {
      const response = await fetch(`${API_URL}/api/voice/profiles`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setVoiceProfiles(data.profiles || []);
      }
    } catch (err) {
      console.error('Failed to fetch voice profiles:', err);
    }
  };

  const startAutoCall = async (scan) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/voice/start-sales-call`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          scan_id: scan.scan_id,
          customer_email: scan.enrichment?.manual_data?.email || null,
          customer_phone: scan.enrichment?.manual_data?.phone || null
        })
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Call initiated! Call ID: ${data.call_id}\n\nThe AI will call the customer within 5 minutes.`);
        setSelectedScan(null);
      } else {
        const error = await response.json();
        alert(`Failed to start call: ${error.detail}`);
      }
    } catch (err) {
      console.error('Auto-call failed:', err);
      alert('Failed to initiate call');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#050505] p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-light text-[#F4F4F4] tracking-wider mb-2">AI Voice Sales Co-Pilot</h1>
          <p className="text-sm text-[#666]">
            Automated sales calls powered by AI. Train voices, trigger calls, view history.
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-6 flex gap-2">
          <button
            onClick={() => setActiveTab('auto-calls')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'auto-calls'
                ? 'bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505]'
                : 'bg-[#0A0A0A] border border-[#1A1A1A] text-[#888] hover:text-[#F4F4F4]'
            }`}
          >
            <PhoneCall className="w-4 h-4 inline mr-2" />
            Auto Calls
          </button>
          <button
            onClick={() => setActiveTab('voice-training')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'voice-training'
                ? 'bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505]'
                : 'bg-[#0A0A0A] border border-[#1A1A1A] text-[#888] hover:text-[#F4F4F4]'
            }`}
          >
            <Mic className="w-4 h-4 inline mr-2" />
            Voice Training
          </button>
          <button
            onClick={() => setActiveTab('call-history')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'call-history'
                ? 'bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505]'
                : 'bg-[#0A0A0A] border border-[#1A1A1A] text-[#888] hover:text-[#F4F4F4]'
            }`}
          >
            <Clock className="w-4 h-4 inline mr-2" />
            Call History
          </button>
        </div>

        {/* Auto Calls Tab */}
        {activeTab === 'auto-calls' && (
          <div className="space-y-6">
            {/* Info Card */}
            <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-blue-400 mt-0.5" />
              <div>
                <p className="text-sm text-blue-400 font-medium mb-1">How Auto-Calls Work</p>
                <p className="text-xs text-blue-400/70">
                  Select a scan below. AI will call the customer, present the findings, answer questions, and schedule a follow-up meeting. 
                  All powered by GPT-5 + ElevenLabs voice synthesis.
                </p>
              </div>
            </div>

            {/* Recent Scans */}
            <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
              <h2 className="text-lg font-medium text-[#F4F4F4] mb-4">Select Customer to Call</h2>

              {recentScans.length === 0 ? (
                <div className="text-center py-12">
                  <Phone className="w-12 h-12 text-[#333] mx-auto mb-4" />
                  <p className="text-sm text-[#666]">No scans available. Scan a customer website first.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentScans.slice(0, 5).map((scan) => (
                    <div
                      key={scan.scan_id}
                      className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg hover:border-[#D4AF37]/30 transition-all"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <h3 className="text-sm font-medium text-[#F4F4F4] mb-1">{scan.website_url}</h3>
                          <div className="flex gap-2 text-xs text-[#888]">
                            <span>{new Date(scan.scan_date).toLocaleDateString()}</span>
                            <span>•</span>
                            <span>{scan.issues_found} issues found</span>
                            {scan.enrichment?.manual_data?.phone && (
                              <>
                                <span>•</span>
                                <span className="text-green-400">Phone: {scan.enrichment.manual_data.phone}</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className={`text-2xl font-bold ${
                          scan.overall_score >= 80 ? 'text-green-400' : 
                          scan.overall_score >= 60 ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {scan.overall_score}
                        </div>
                      </div>

                      <button
                        onClick={() => startAutoCall(scan)}
                        disabled={loading || !scan.enrichment?.manual_data?.phone}
                        className="w-full px-4 py-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg text-sm font-medium hover:opacity-90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        <PhoneCall className="w-4 h-4" />
                        {!scan.enrichment?.manual_data?.phone 
                          ? 'No Phone Number' 
                          : loading 
                            ? 'Initiating Call...' 
                            : 'Start AI Call'
                        }
                      </button>

                      {!scan.enrichment?.manual_data?.phone && (
                        <p className="mt-2 text-xs text-yellow-400 text-center">
                          Add phone number in Customer Scanner to enable calls
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Voice Training Tab */}
        {activeTab === 'voice-training' && (
          <div className="space-y-6">
            {/* Info */}
            <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg flex items-start gap-3">
              <Mic className="w-5 h-5 text-purple-400 mt-0.5" />
              <div>
                <p className="text-sm text-purple-400 font-medium mb-1">Voice Profile Training</p>
                <p className="text-xs text-purple-400/70">
                  Train AI to recognize your team members' voices. AI can distinguish who's speaking during meetings and provide personalized coaching.
                </p>
              </div>
            </div>

            {/* Voice Profiles */}
            <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-[#F4F4F4]">Trained Voice Profiles</h2>
                <button className="px-4 py-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg text-sm font-medium hover:opacity-90 transition-all">
                  + Train New Voice
                </button>
              </div>

              {voiceProfiles.length === 0 ? (
                <div className="text-center py-12">
                  <Mic className="w-12 h-12 text-[#333] mx-auto mb-4" />
                  <p className="text-sm text-[#666] mb-2">No voice profiles trained yet</p>
                  <p className="text-xs text-[#555]">Train voices to enable advanced features</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {voiceProfiles.map((profile) => (
                    <div key={profile.profile_id} className="p-4 bg-[#050505] border border-[#1A1A1A] rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold">
                          {profile.team_member_name.charAt(0)}
                        </div>
                        <div>
                          <h3 className="text-sm font-medium text-[#F4F4F4]">{profile.team_member_name}</h3>
                          <p className="text-xs text-[#888]">
                            Trained: {new Date(profile.trained_at).toLocaleDateString()} • {profile.sample_count} samples
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-xs font-medium border border-green-500/30">
                          Active
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Call History Tab */}
        {activeTab === 'call-history' && (
          <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <h2 className="text-lg font-medium text-[#F4F4F4] mb-4">Recent Calls</h2>

            <div className="text-center py-12">
              <Clock className="w-12 h-12 text-[#333] mx-auto mb-4" />
              <p className="text-sm text-[#666] mb-2">No call history yet</p>
              <p className="text-xs text-[#555]">Start your first AI call to see history here</p>
            </div>

            {/* Future: Call history will show:
              - Call duration
              - Customer sentiment
              - Objections raised
              - Meeting scheduled?
              - Recording link
            */}
          </div>
        )}
      </div>
    </div>
  );
};

export default VoiceSalesAgent;
