/**
 * AI Voice Sales Co-Pilot
 * VoltAgent Dark Theme — Auto-calls, voice training, call history
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Phone, PhoneCall, Mic, MicOff, Clock, CheckCircle,
  TrendingUp, Users, Zap, AlertCircle, Sparkles, Volume2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const VoiceSalesAgent = ({ token }) => {
  const [activeTab, setActiveTab] = useState('auto-calls');
  const [recentScans, setRecentScans] = useState([]);
  const [callHistory, setCallHistory] = useState([]);
  const [voiceProfiles, setVoiceProfiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchRecentScans = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/scanner/scans`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRecentScans(data.scans || []);
      }
    } catch (err) {
      console.error('Failed to fetch scans:', err);
    }
  }, [token]);

  const fetchVoiceProfiles = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/voice/profiles`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVoiceProfiles(data.profiles || []);
      }
    } catch (err) {
      console.error('Failed to fetch voice profiles:', err);
    }
  }, [token]);

  const fetchCallHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/voice/call-history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setCallHistory(data.calls || []);
      }
    } catch (err) {
      console.error('Failed to fetch call history:', err);
    }
  }, [token]);

  useEffect(() => {
    fetchRecentScans();
    fetchVoiceProfiles();
    fetchCallHistory();
  }, [fetchRecentScans, fetchVoiceProfiles, fetchCallHistory]);

  const startAutoCall = async (scan) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/voice/start-sales-call`, {
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

      if (res.ok) {
        const data = await res.json();
        alert(`Call initiated! Call ID: ${data.call_id}`);
        fetchCallHistory();
      } else {
        const error = await res.json();
        alert(`Failed to start call: ${error.detail}`);
      }
    } catch (err) {
      console.error('Auto-call failed:', err);
      alert('Failed to initiate call');
    } finally {
      setLoading(false);
    }
  };

  const tabStyle = (isActive) => ({
    padding: '8px 16px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.2s',
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    background: isActive ? 'linear-gradient(135deg, #FF6B00, #CC5500)' : 'rgba(255,255,255,0.04)',
    color: isActive ? '#fff' : 'rgba(255,255,255,0.5)',
    borderBottom: isActive ? 'none' : '1px solid rgba(255,107,0,0.1)',
  });

  const cardStyle = {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,107,0,0.12)',
    borderRadius: 12,
    padding: 24,
  };

  return (
    <div data-testid="voice-sales-agent" className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-light tracking-wider mb-2" style={{ color: 'var(--aurem-heading, #E8E6E3)', fontFamily: 'var(--aurem-font-heading, Cinzel, serif)' }}>
            AI Voice Sales Co-Pilot
          </h1>
          <p className="text-sm" style={{ color: 'var(--aurem-body-secondary, rgba(255,255,255,0.45))' }}>
            Automated sales calls powered by AI. Train voices, trigger calls, view history.
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-6 flex gap-2">
          <button onClick={() => setActiveTab('auto-calls')} style={tabStyle(activeTab === 'auto-calls')} data-testid="tab-auto-calls">
            <PhoneCall className="size-4" /> Auto Calls
          </button>
          <button onClick={() => setActiveTab('voice-training')} style={tabStyle(activeTab === 'voice-training')} data-testid="tab-voice-training">
            <Mic className="size-4" /> Voice Training
          </button>
          <button onClick={() => setActiveTab('call-history')} style={tabStyle(activeTab === 'call-history')} data-testid="tab-call-history">
            <Clock className="size-4" /> Call History
          </button>
        </div>

        {/* Auto Calls Tab */}
        {activeTab === 'auto-calls' && (
          <div className="space-y-6">
            <div style={{ ...cardStyle, background: 'rgba(255,107,0,0.06)', borderColor: 'rgba(255,107,0,0.2)' }} className="flex items-start gap-3">
              <Sparkles className="size-5 mt-0.5" style={{ color: '#FF6B00' }} />
              <div>
                <p className="text-sm font-medium mb-1" style={{ color: '#FF6B00' }}>How Auto-Calls Work</p>
                <p className="text-xs" style={{ color: 'rgba(255,107,0,0.65)' }}>
                  Select a scan below. AI will call the customer, present the findings, answer questions, and schedule a follow-up meeting. Powered by GPT-4o + ElevenLabs voice synthesis.
                </p>
              </div>
            </div>

            <div style={cardStyle}>
              <h2 className="text-base font-medium mb-4" style={{ color: 'var(--aurem-heading, #E8E6E3)', fontFamily: 'var(--aurem-font-heading, Cinzel, serif)' }}>
                Select Customer to Call
              </h2>

              {recentScans.length === 0 ? (
                <div className="text-center py-12">
                  <Phone className="size-12 mx-auto mb-4" style={{ color: 'rgba(255,255,255,0.55)' }} />
                  <p className="text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>No scans available. Scan a customer website first.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentScans.slice(0, 5).map((scan) => (
                    <div
                      key={scan.scan_id}
                      data-testid={`scan-card-${scan.scan_id}`}
                      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,107,0,0.1)', borderRadius: 10, padding: 16, transition: 'border-color 0.2s' }}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <h3 className="text-sm font-medium mb-1" style={{ color: 'var(--aurem-heading, #E8E6E3)' }}>{scan.website_url}</h3>
                          <div className="flex gap-2 text-xs" style={{ color: 'rgba(255,255,255,0.65)' }}>
                            <span>{new Date(scan.scan_date).toLocaleDateString()}</span>
                            <span>&middot;</span>
                            <span>{scan.issues_found} issues found</span>
                            {scan.enrichment?.manual_data?.phone && (
                              <>
                                <span>&middot;</span>
                                <span style={{ color: '#4ade80' }}>Phone: {scan.enrichment.manual_data.phone}</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="text-2xl font-bold" style={{ color: scan.overall_score >= 80 ? '#4ade80' : scan.overall_score >= 60 ? '#facc15' : '#ef4444' }}>
                          {scan.overall_score}
                        </div>
                      </div>

                      <button
                        onClick={() => startAutoCall(scan)}
                        disabled={loading || !scan.enrichment?.manual_data?.phone}
                        data-testid={`start-call-${scan.scan_id}`}
                        className="w-full flex items-center justify-center gap-2 disabled:opacity-40"
                        style={{
                          padding: '10px 16px',
                          background: scan.enrichment?.manual_data?.phone ? 'linear-gradient(135deg, #FF6B00, #CC5500)' : 'rgba(255,255,255,0.06)',
                          color: scan.enrichment?.manual_data?.phone ? '#fff' : 'rgba(255,255,255,0.35)',
                          borderRadius: 8,
                          fontSize: 13,
                          fontWeight: 500,
                          border: 'none',
                          cursor: scan.enrichment?.manual_data?.phone ? 'pointer' : 'not-allowed',
                          transition: 'opacity 0.2s',
                        }}
                      >
                        <PhoneCall className="size-4" />
                        {!scan.enrichment?.manual_data?.phone 
                          ? 'No Phone Number' 
                          : loading 
                            ? 'Initiating Call...' 
                            : 'Start AI Call'
                        }
                      </button>

                      {!scan.enrichment?.manual_data?.phone && (
                        <p className="mt-2 text-xs text-center" style={{ color: 'rgba(255,107,0,0.5)' }}>
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
            <div style={{ ...cardStyle, background: 'rgba(168,85,247,0.06)', borderColor: 'rgba(168,85,247,0.2)' }} className="flex items-start gap-3">
              <Mic className="size-5 mt-0.5" style={{ color: '#a855f7' }} />
              <div>
                <p className="text-sm font-medium mb-1" style={{ color: '#a855f7' }}>Voice Profile Training</p>
                <p className="text-xs" style={{ color: 'rgba(168,85,247,0.6)' }}>
                  Train AI to recognize your team members' voices. AI can distinguish who's speaking during meetings and provide personalized coaching.
                </p>
              </div>
            </div>

            <div style={cardStyle}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-medium" style={{ color: 'var(--aurem-heading, #E8E6E3)', fontFamily: 'var(--aurem-font-heading, Cinzel, serif)' }}>
                  Trained Voice Profiles
                </h2>
                <button
                  onClick={() => alert('Voice training requires a connected voice integration. Configure in Settings > Integrations.')}
                  data-testid="train-new-voice-btn"
                  style={{
                    padding: '8px 16px',
                    background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
                    color: '#fff',
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 500,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  + Train New Voice
                </button>
              </div>

              {voiceProfiles.length === 0 ? (
                <div className="text-center py-12">
                  <Mic className="size-12 mx-auto mb-4" style={{ color: 'rgba(255,255,255,0.55)' }} />
                  <p className="text-sm mb-2" style={{ color: 'rgba(255,255,255,0.65)' }}>No voice profiles trained yet</p>
                  <p className="text-xs" style={{ color: 'rgba(255,255,255,0.6)' }}>Train voices to enable advanced features</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {voiceProfiles.map((profile) => (
                    <div key={profile.profile_id} className="flex items-center justify-between" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,107,0,0.1)', borderRadius: 10, padding: 16 }}>
                      <div className="flex items-center gap-4">
                        <div className="size-12 rounded-full flex items-center justify-center text-white font-bold" style={{ background: 'linear-gradient(135deg, #a855f7, #ec4899)' }}>
                          {profile.team_member_name.charAt(0)}
                        </div>
                        <div>
                          <h3 className="text-sm font-medium" style={{ color: 'var(--aurem-heading, #E8E6E3)' }}>{profile.team_member_name}</h3>
                          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.65)' }}>
                            Trained: {new Date(profile.trained_at).toLocaleDateString()} &middot; {profile.sample_count} samples
                          </p>
                        </div>
                      </div>
                      <div style={{ padding: '4px 12px', background: 'rgba(74,222,128,0.12)', color: '#4ade80', borderRadius: 20, fontSize: 11, fontWeight: 500, border: '1px solid rgba(74,222,128,0.2)' }}>
                        Active
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
          <div style={cardStyle}>
            <h2 className="text-base font-medium mb-4" style={{ color: 'var(--aurem-heading, #E8E6E3)', fontFamily: 'var(--aurem-font-heading, Cinzel, serif)' }}>
              Recent Calls
            </h2>

            {callHistory.length === 0 ? (
              <div className="text-center py-12">
                <Clock className="size-12 mx-auto mb-4" style={{ color: 'rgba(255,255,255,0.55)' }} />
                <p className="text-sm mb-2" style={{ color: 'rgba(255,255,255,0.65)' }}>No call history yet</p>
                <p className="text-xs" style={{ color: 'rgba(255,255,255,0.6)' }}>Start your first AI call to see history here</p>
              </div>
            ) : (
              <div className="space-y-3">
                {callHistory.map((call) => (
                  <div key={call.call_id} data-testid={`call-row-${call.call_id}`} className="flex items-center justify-between" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,107,0,0.1)', borderRadius: 10, padding: 16 }}>
                    <div className="flex items-center gap-3">
                      <div className="size-10 rounded-full flex items-center justify-center" style={{
                        background: call.status === 'completed' ? 'rgba(74,222,128,0.12)' : call.status === 'active' ? 'rgba(255,107,0,0.12)' : 'rgba(255,255,255,0.06)',
                      }}>
                        {call.status === 'completed' ? <CheckCircle className="size-5" style={{ color: '#4ade80' }} /> :
                         call.status === 'active' ? <PhoneCall className="size-5" style={{ color: '#FF6B00' }} /> :
                         <AlertCircle className="size-5" style={{ color: 'rgba(255,255,255,0.6)' }} />}
                      </div>
                      <div>
                        <p className="text-sm font-medium" style={{ color: 'var(--aurem-heading, #E8E6E3)' }}>
                          {call.customer_phone || call.customer_email || 'Unknown Customer'}
                        </p>
                        <p className="text-xs" style={{ color: 'rgba(255,255,255,0.65)' }}>
                          {call.started_at ? new Date(call.started_at).toLocaleString() : 'N/A'} &middot; {call.call_type || 'auto'}
                        </p>
                      </div>
                    </div>
                    <div style={{
                      padding: '4px 12px',
                      borderRadius: 20,
                      fontSize: 11,
                      fontWeight: 500,
                      background: call.status === 'completed' ? 'rgba(74,222,128,0.12)' : call.status === 'active' ? 'rgba(255,107,0,0.12)' : 'rgba(255,255,255,0.06)',
                      color: call.status === 'completed' ? '#4ade80' : call.status === 'active' ? '#FF6B00' : 'rgba(255,255,255,0.4)',
                      border: `1px solid ${call.status === 'completed' ? 'rgba(74,222,128,0.2)' : call.status === 'active' ? 'rgba(255,107,0,0.2)' : 'rgba(255,255,255,0.1)'}`,
                    }}>
                      {call.status || 'pending'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default VoiceSalesAgent;
