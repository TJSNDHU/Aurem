/**
 * VoiceAgentStudio — Admin UI for AUREM Voice Agent (Retell-powered)
 * ====================================================================
 * Manages agent configs per customer. Retell integration status badge.
 * Shows platform-wide call stats + per-customer deep-dive.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Phone, Loader2, PhoneCall, Activity, Users, Play, Volume2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const card = {
  padding: 20, borderRadius: 14,
  background: 'rgba(15,18,28,0.55)',
  border: '1px solid rgba(212,175,55,0.14)',
  backdropFilter: 'blur(22px)',
  marginBottom: 16,
};

export default function VoiceAgentStudio({ token }) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dry Test state
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [testPlaying, setTestPlaying] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/voice-agent/overview`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setOverview(await res.json());
    } catch (e) {} finally { setLoading(false); }
  }, [token]);

  const loadVoices = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/voice-agent/retell/voices`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setVoices((d.voices || []).slice(0, 40));
        if (d.voices?.[0]?.voice_id) setSelectedVoice(d.voices[0].voice_id);
      }
    } catch (e) {}
  }, [token]);

  const playVoicePreview = () => {
    const v = voices.find(x => x.voice_id === selectedVoice);
    const url = v?.preview_audio_url || v?.sample_url;
    if (!url) return alert('No preview available for this voice');
    setTestPlaying(true);
    const audio = new Audio(url);
    audio.play().catch(() => setTestPlaying(false));
    audio.onended = () => setTestPlaying(false);
    audio.onerror = () => setTestPlaying(false);
  };

  useEffect(() => { load(); const iv = setInterval(load, 15000); return () => clearInterval(iv); }, [load]);
  useEffect(() => { if (overview?.retell_connected) loadVoices(); }, [overview?.retell_connected, loadVoices]);

  if (loading) return <div style={card}><Loader2 className="animate-spin" size={28} style={{ color: '#D4AF37', display: 'block', margin: '20px auto' }} /></div>;

  return (
    <div data-testid="voice-agent-studio">
      {/* Retell status banner */}
      <div style={{
        ...card,
        background: overview?.retell_connected
          ? 'linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(15,18,28,0.55) 100%)'
          : 'linear-gradient(135deg, rgba(239,68,68,0.08) 0%, rgba(15,18,28,0.55) 100%)',
        borderColor: overview?.retell_connected ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Phone size={22} style={{ color: overview?.retell_connected ? '#22c55e' : '#ef4444' }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#FFF', fontFamily: "'Cinzel',serif" }}>
              Retell AI: {overview?.retell_connected ? 'Connected' : 'Not Connected'}
            </div>
            <div style={{ fontSize: 11, color: '#8A8070', marginTop: 3 }}>
              {overview?.retell_connected
                ? 'AI inbound call handler is live. Agents provision automatically on customer subscribe.'
                : 'Add RETELL_API_KEY to backend/.env to enable AI voice agents. Customer UI + DB layer ready.'}
            </div>
          </div>
          {!overview?.retell_connected && (
            <a href="https://retellai.com" target="_blank" rel="noreferrer" style={{ padding: '8px 14px', borderRadius: 8, background: 'rgba(212,175,55,0.15)', color: '#D4AF37', fontSize: 11, fontWeight: 700, textDecoration: 'none', letterSpacing: '0.1em' }}>
              Sign up on Retell →
            </a>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        <StatCard icon={Users} label="Customers Configured" value={overview?.total_customers_configured ?? 0} />
        <StatCard icon={Activity} label="Agents Enabled" value={overview?.enabled_agents ?? 0} color="#22c55e" />
        <StatCard icon={PhoneCall} label="Calls (7 days)" value={overview?.calls_7d ?? 0} color="#fb923c" />
        <StatCard icon={Phone} label="Total Minutes" value={overview?.total_minutes_all_time ?? 0} color="#D4AF37" />
      </div>

      {/* Provider config */}
      <div style={card}>
        <h3 style={{ fontSize: 12, color: '#D4AF37', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 14px 0' }}>
          Voice Agent Stack
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
          <ProviderRow name="Retell AI" purpose="Primary agent orchestration + STT + LLM + TTS" status={overview?.retell_connected ? 'live' : 'pending'} cost="$0.07/min bundled" />
          <ProviderRow name="ElevenLabs" purpose="Premium voice synthesis (Rachel, Josh, Dom)" status="configured" cost="$0.08-0.24/min" />
          <ProviderRow name="Deepgram" purpose="Fallback STT for DIY mode" status="configured" cost="$0.0043/min" />
          <ProviderRow name="Twilio" purpose="Inbound SIP + phone number" status="configured" cost="$0.0085/min Canada" />
        </div>
      </div>

      <div style={{ ...card, padding: 14, fontSize: 11, color: '#8A8070', background: 'rgba(212,175,55,0.05)', border: '1px dashed rgba(212,175,55,0.2)' }}>
        💡 <strong style={{ color: '#D4AF37' }}>Service in catalog:</strong> "AUREM Voice Agent (AI Inbound)" · $149/mo · 400 min included · $0.35/min overage · 81% margin
      </div>

      {/* ═══ DRY TEST — VOICE PREVIEW ═══ */}
      {overview?.retell_connected && (
        <div style={card} data-testid="voice-agent-dry-test">
          <h3 style={{ fontSize: 12, color: '#D4AF37', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 14px 0' }}>
            Dry Test · Voice Preview
          </h3>
          <p style={{ fontSize: 11, color: '#8A8070', margin: '0 0 14px 0' }}>
            Pick any of the {voices.length} Retell voices to preview how your AI agent will sound on calls. Audio plays in-browser — no minutes charged.
          </p>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <select
              data-testid="voice-selector"
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              style={{
                flex: 1, minWidth: 240, padding: '10px 12px', borderRadius: 8,
                background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(212,175,55,0.2)',
                color: '#FDF9F9', fontSize: 12,
              }}
            >
              {voices.length === 0 && <option value="">Loading voices…</option>}
              {voices.map((v) => (
                <option key={v.voice_id} value={v.voice_id}>
                  {v.voice_name || v.voice_id} {v.provider ? `(${v.provider})` : ''} {v.gender ? ` · ${v.gender}` : ''}
                </option>
              ))}
            </select>
            <button
              data-testid="voice-test-play-btn"
              onClick={playVoicePreview}
              disabled={testPlaying || !selectedVoice}
              style={{
                padding: '10px 18px', borderRadius: 8, border: 'none', cursor: testPlaying ? 'wait' : 'pointer',
                background: testPlaying ? 'rgba(212,175,55,0.3)' : '#D4AF37',
                color: '#0D0D0D', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}
            >
              {testPlaying ? <Volume2 size={14} /> : <Play size={14} />}
              {testPlaying ? 'PLAYING...' : 'PLAY SAMPLE'}
            </button>
          </div>
          <div style={{ fontSize: 10, color: '#555', marginTop: 10, letterSpacing: '0.12em' }}>
            {voices.length} VOICES AVAILABLE · POWERED BY RETELL AI
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div style={{ padding: 14, borderRadius: 12, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(212,175,55,0.1)' }}>
      <Icon size={14} style={{ color: color || '#8A8070', marginBottom: 6 }} />
      <div style={{ fontSize: 9, color: '#8A8070', letterSpacing: '0.16em', textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: color || '#FFF', marginTop: 4, fontFamily: "'Cinzel',serif" }}>{value}</div>
    </div>
  );
}

function ProviderRow({ name, purpose, status, cost }) {
  const bg = status === 'live' ? 'rgba(34,197,94,0.08)' : status === 'configured' ? 'rgba(59,130,246,0.08)' : 'rgba(251,146,60,0.08)';
  const color = status === 'live' ? '#22c55e' : status === 'configured' ? '#3b82f6' : '#fb923c';
  return (
    <div style={{ padding: 12, borderRadius: 10, background: bg, border: `1px solid ${color}44` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 13, color: '#FFF', fontWeight: 700 }}>{name}</span>
        <span style={{ fontSize: 9, color, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}>{status}</span>
      </div>
      <div style={{ fontSize: 10, color: '#8A8070' }}>{purpose}</div>
      <div style={{ fontSize: 10, color: '#D4AF37', marginTop: 4, fontFamily: "'JetBrains Mono',monospace" }}>{cost}</div>
    </div>
  );
}
