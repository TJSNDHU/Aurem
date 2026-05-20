/**
 * AUREM Acquisition Engine
 * Zero-cost customer acquisition with 5-tier channel system
 * Tier 1: Basic DIY (Forms + Click-to-Chat)
 * Tier 2: Advanced DIY (Apps Script + Meta WhatsApp Cloud API)
 * Tier 3: AUREM Extension (Coming Soon - browser automation)
 * Tier 4: Premium API (Locked upsell)
 * Tier 5: AI Voice Agent (Web Voice + Self-Hosted + Premium)
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import {
  Rocket, Users, Mail, MessageCircle, Plus, Play, Pause, Trash2,
  Copy, Check, RefreshCw, ArrowRight, ChevronRight, ChevronDown,
  Target, TrendingUp, Zap, Globe, ExternalLink, X,
  CheckCircle, AlertCircle, Clock, Send, Code, Star, Sparkles,
  Shield, Lock, Eye, Settings, BarChart3, Chrome,
  Instagram, Youtube, Linkedin, Twitter, Facebook, Smartphone,
  Mic, MicOff, Phone, PhoneOff, Volume2, VolumeX
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const EMAIL_TEMPLATES = [
  { id: 'welcome-luxe', name: 'Scientific Luxe Welcome', subject: 'Welcome to {{brand}} — Your Personalized Journey Begins', preview: 'Premium welcome email with WhatsApp CTA and personalized product recommendation', category: 'Welcome', tags: ['skincare', 'biotech', 'luxury'] },
  { id: 'offer-discount', name: 'Exclusive Offer', subject: '{{first_name}}, Your Exclusive {{discount}}% Awaits', preview: 'Urgency-driven offer with countdown and WhatsApp claim button', category: 'Offer', tags: ['discount', 'urgency', 'conversion'] },
  { id: 'followup-care', name: 'Consultative Follow-Up', subject: "We noticed you're interested in {{concern}} — Let's talk", preview: 'Smart follow-up based on form answers with booking link', category: 'Follow-Up', tags: ['consultative', 'personalized', 'booking'] },
  { id: 'reengagement', name: 'Re-Engagement', subject: "{{first_name}}, we miss you — here's something special", preview: 'Win-back email for leads that have not converted', category: 'Re-engage', tags: ['winback', 'retention'] }
];

const SOCIAL_CHANNELS = [
  { id: 'gmail', name: 'Gmail', icon: Mail, color: '#EA4335', desc: 'Read inbox, auto-reply, keyword monitor' },
  { id: 'whatsapp', name: 'WhatsApp', icon: MessageCircle, color: '#25D366', desc: 'Auto-reply DMs, broadcast, CRM sync' },
  { id: 'instagram', name: 'Instagram', icon: Instagram, color: '#E4405F', desc: 'DM replies, comment auto-responder' },
  { id: 'facebook', name: 'Facebook', icon: Facebook, color: '#1877F2', desc: 'Page inbox, post comment replies' },
  { id: 'youtube', name: 'YouTube', icon: Youtube, color: '#FF0000', desc: 'Video comment auto-engage, lead capture' },
  { id: 'linkedin', name: 'LinkedIn', icon: Linkedin, color: '#0A66C2', desc: 'InMail replies, post comment engage' },
  { id: 'x', name: 'X (Twitter)', icon: Twitter, color: '#999', desc: 'DM replies, mention auto-engage' },
];

// ═══════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════

function CopyButton({ text, label, variant = 'gold' }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); };
  const colors = variant === 'gold' ? 'text-[#D4AF37] bg-[#D4AF37]/10 hover:bg-[#D4AF37]/20' : 'text-[#888] bg-white/50 hover:bg-[#1A1A1A]';
  return (
    <button onClick={handleCopy} className={`flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium rounded-md transition-colors ${colors}`}>
      {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
      {copied ? 'Copied!' : label || 'Copy'}
    </button>
  );
}

function StepCard({ number, title, description, children, total = 4 }) {
  return (
    <div className="relative pl-10 pb-6">
      <div className="absolute left-0 top-0 size-7 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/30 flex items-center justify-center text-[11px] font-bold text-[#D4AF37]">{number}</div>
      {number < total && <div className="absolute left-[13px] top-8 w-[1px] h-[calc(100%-32px)] bg-[#1A1A1A]" />}
      <div>
        <h4 className="text-xs font-medium text-[#1A1A2E] mb-1">{title}</h4>
        <p className="text-[11px] text-[#888] mb-3 leading-relaxed">{description}</p>
        {children}
      </div>
    </div>
  );
}

function TierBadge({ tier, label, color }) {
  return (
    <span className="px-2 py-0.5 text-[9px] font-semibold rounded-full tracking-wider" style={{ backgroundColor: `${color}15`, color, border: `1px solid ${color}30` }}>
      TIER {tier} — {label}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════
// TIER 5: AI VOICE AGENT (CENTERPIECE)
// ═══════════════════════════════════════════════════════════════

function Tier5VoiceAgent({ token, config }) {
  const [expanded, setExpanded] = useState(true);
  const [subTier, setSubTier] = useState('5a');
  const [isCallActive, setIsCallActive] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [currentText, setCurrentText] = useState('');
  const [callDuration, setCallDuration] = useState(0);
  const [selfHostedScript, setSelfHostedScript] = useState('');
  const [loadingScript, setLoadingScript] = useState(false);

  const recognitionRef = useRef(null);
  const synthRef = useRef(window.speechSynthesis);
  const durationRef = useRef(null);
  const sessionIdRef = useRef(`voice-${Date.now()}`);
  const isCallActiveRef = useRef(false);
  const brandName = config?.brand_name || 'AUREM';

  const startCall = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      alert('Voice not supported in this browser. Please use Chrome.');
      return;
    }
    isCallActiveRef.current = true;
    setIsCallActive(true);
    setTranscript([]);
    setCallDuration(0);
    sessionIdRef.current = `voice-${Date.now()}`;
    durationRef.current = setInterval(() => setCallDuration(d => d + 1), 1000);

    const greeting = `Welcome to ${brandName}! I'm your AI consultant. How can I help you today?`;
    setTranscript([{ role: 'agent', text: greeting }]);
    speakText(greeting);
  };

  const endCall = () => {
    isCallActiveRef.current = false;
    setIsCallActive(false);
    setIsListening(false);
    setIsSpeaking(false);
    if (recognitionRef.current) recognitionRef.current.stop();
    if (synthRef.current) synthRef.current.cancel();
    if (durationRef.current) clearInterval(durationRef.current);
  };

  const speakText = (text) => {
    setIsSpeaking(true);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    const voices = synthRef.current.getVoices();
    const preferred = voices.find(v => v.name.includes('Google') && v.lang.startsWith('en')) || voices.find(v => v.lang.startsWith('en'));
    if (preferred) utterance.voice = preferred;
    utterance.onend = () => { setIsSpeaking(false); startListening(); };
    utterance.onerror = () => { setIsSpeaking(false); startListening(); };
    synthRef.current.speak(utterance);
  };

  const startListening = () => {
    if (!isCallActiveRef.current) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognitionRef.current = recognition;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => setIsListening(true);
    recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      setCurrentText(result[0].transcript);
      if (result.isFinal) {
        const userText = result[0].transcript;
        setCurrentText('');
        setTranscript(prev => [...prev, { role: 'user', text: userText }]);
        setIsListening(false);
        processUserSpeech(userText);
      }
    };
    recognition.onerror = () => { setIsListening(false); if (isCallActiveRef.current) setTimeout(startListening, 1000); };
    recognition.onend = () => setIsListening(false);
    recognition.start();
  };

  const processUserSpeech = async (text) => {
    try {
      const res = await fetch(`${API_URL}/api/acquisition/voice-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          message: text,
          history: transcript.slice(-6).map(t => ({ role: t.role === 'user' ? 'user' : 'assistant', content: t.text })),
          session_id: sessionIdRef.current
        })
      });
      const data = await res.json();
      const agentText = data.response || "I'd be happy to help you with that. Could you tell me more?";
      setTranscript(prev => [...prev, { role: 'agent', text: agentText }]);
      speakText(agentText);
    } catch {
      const fallback = "I'm here to help! Could you repeat that?";
      setTranscript(prev => [...prev, { role: 'agent', text: fallback }]);
      speakText(fallback);
    }
  };

  const loadSelfHostedScript = async () => {
    setLoadingScript(true);
    try {
      const res = await fetch(`${API_URL}/api/acquisition/generate-voice-script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({})
      });
      const data = await res.json();
      setSelfHostedScript(data.script || '');
    } catch (err) { console.error(err); }
    finally { setLoadingScript(false); }
  };

  const formatDuration = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  // Voice visualizer bars
  const VoiceBars = ({ active, color }) => (
    <div className="flex items-center gap-[2px] h-8">
      {[...Array(16)].map((_, i) => (
        <div key={i} className="w-[3px] rounded-full transition-all duration-100" style={{
          height: active ? `${12 + Math.random() * 88}%` : '15%',
          backgroundColor: active ? color : 'rgba(255,255,255,0.2)',
          animationDelay: `${i * 30}ms`
        }} />
      ))}
    </div>
  );

  return (
    <div className="bg-white/80 backdrop-blur-sm border-2 border-[#D4AF37]/40 rounded-xl overflow-hidden shadow-[0_0_40px_rgba(212,175,55,0.08)]" data-testid="tier-5-voice">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-5 text-left hover:bg-white/40 transition-colors">
        <div className="flex items-center gap-4">
          <div className="size-14 rounded-xl bg-gradient-to-br from-[#D4AF37]/20 to-[#D4AF37]/5 flex items-center justify-center relative border border-[#D4AF37]/30">
            <Phone className="size-7 text-[#D4AF37]" />
            <div className="absolute -top-1.5 -right-1.5 size-5 bg-[#4ade80] rounded-full flex items-center justify-center border-2 border-[#0A0A0A]">
              <Sparkles className="size-2.5 text-[#050505]" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-base font-semibold text-[#1A1A2E]">AI Voice Agent</h3>
              <TierBadge tier={5} label="LIVE NOW" color="#D4AF37" />
              <span className="px-2 py-0.5 text-[9px] font-bold text-[#4ade80] bg-[#4ade80]/10 rounded-full">$0</span>
              <span className="px-2 py-0.5 text-[9px] font-bold text-[#D4AF37] bg-[#D4AF37]/10 rounded-full animate-pulse">NEW</span>
            </div>
            <p className="text-[11px] text-[#888]">Real-time AI voice conversations, customers talk, AI responds instantly. Zero API fees.</p>
          </div>
        </div>
        {expanded ? <ChevronDown className="size-4 text-[#D4AF37]" /> : <ChevronRight className="size-4 text-[#D4AF37]" />}
      </button>

      {expanded && (
        <div className="border-t border-[#D4AF37]/20">
          {/* Sub-tier selector */}
          <div className="flex gap-1 p-3 bg-[#1A3026] border-b border-[#FF6B00]/20">
            {[
              { id: '5a', label: 'Web Voice Agent', icon: Mic, color: '#FF6B00', badge: 'FREE' },
              { id: '5b', label: 'Self-Hosted (Ollama)', icon: Code, color: '#3b82f6', badge: 'DIY' },
              { id: '5c', label: 'Premium (AUREM Voice)', icon: Phone, color: '#a855f7', badge: 'PRO' },
            ].map(t => (
              <button key={t.id} onClick={() => setSubTier(t.id)} data-testid={`voice-tier-${t.id}`} className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[11px] transition-all border ${subTier === t.id ? 'border-[#FF6B00]/40 bg-[#FF6B00]/15 text-white' : 'border-transparent text-white/50 hover:text-white/70'}`}>
                <t.icon className="size-3.5" style={{ color: t.color }} />
                {t.label}
                <span className="text-[8px] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: `${t.color}15`, color: t.color }}>{t.badge}</span>
              </button>
            ))}
          </div>

          {/* ═══ 5A: Web Voice Agent (CENTERPIECE) ═══ */}
          {subTier === '5a' && (
            <div className="p-5">
              {/* Architecture Diagram */}
              <div className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20 mb-5">
                <h4 className="text-[10px] text-[#555] tracking-wider mb-4">ZERO-COST VOICE PIPELINE</h4>
                <div className="flex items-center justify-between">
                  {[
                    { label: 'Customer Speaks', sub: 'Microphone', icon: Mic, color: '#4ade80', time: '' },
                    { label: 'Speech → Text', sub: 'Web Speech API', icon: Volume2, color: '#3b82f6', time: '<100ms' },
                    { label: 'AI Thinks', sub: 'GPT-4o (Emergent)', icon: Sparkles, color: '#D4AF37', time: '<200ms' },
                    { label: 'Text → Voice', sub: 'Web Speech API', icon: Phone, color: '#a855f7', time: '<100ms' },
                    { label: 'Customer Hears', sub: 'Speaker', icon: Volume2, color: '#4ade80', time: '' },
                  ].map((step, idx) => (
                    <React.Fragment key={idx}>
                      <div className="flex-1 text-center">
                        <div className="size-11 rounded-xl mx-auto mb-1.5 flex items-center justify-center" style={{ backgroundColor: `${step.color}10`, border: `1px solid ${step.color}25` }}>
                          <step.icon className="size-5" style={{ color: step.color }} />
                        </div>
                        <p className="text-[10px] font-medium text-[#1A1A2E]">{step.label}</p>
                        <p className="text-[8px] text-[#555]">{step.sub}</p>
                        {step.time && <p className="text-[8px] font-mono text-[#D4AF37] mt-0.5">{step.time}</p>}
                      </div>
                      {idx < 4 && <ArrowRight className="size-3.5 text-[#333] flex-shrink-0 mx-1" />}
                    </React.Fragment>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-[#FF6B00]/20 flex items-center justify-center gap-6">
                  <div className="text-center">
                    <span className="text-lg font-bold font-mono text-[#D4AF37]">&lt;400ms</span>
                    <p className="text-[8px] text-[#555]">Total Latency</p>
                  </div>
                  <div className="w-px h-8 bg-[#1A1A1A]" />
                  <div className="text-center">
                    <span className="text-lg font-bold font-mono text-[#4ade80]">$0.00</span>
                    <p className="text-[8px] text-[#555]">Per Minute</p>
                  </div>
                  <div className="w-px h-8 bg-[#1A1A1A]" />
                  <div className="text-center">
                    <span className="text-lg font-bold font-mono text-[#3b82f6]">24/7</span>
                    <p className="text-[8px] text-[#555]">Availability</p>
                  </div>
                </div>
              </div>

              {/* LIVE Voice Agent */}
              <div className="relative rounded-xl overflow-hidden border border-[#FF6B00]/30 bg-gradient-to-br from-[#1A3026] to-[#0D1A14]">
                {/* Call Header */}
                <div className="flex items-center justify-between p-4 border-b border-[#FF6B00]/20">
                  <div className="flex items-center gap-3">
                    <div className={`size-3 rounded-full ${isCallActive ? 'bg-[#4ade80] animate-pulse' : 'bg-white/30'}`} />
                    <span className="text-xs font-medium text-white">{isCallActive ? 'Call Active' : 'Ready to Call'}</span>
                    {isCallActive && <span className="text-[10px] font-mono text-[#FF6B00]">{formatDuration(callDuration)}</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-[9px] text-white/50">
                      {isListening && <span className="flex items-center gap-1 text-[#4ade80]"><Mic className="size-3" /> Listening</span>}
                      {isSpeaking && <span className="flex items-center gap-1 text-[#FF6B00]"><Volume2 className="size-3" /> Speaking</span>}
                    </div>
                    {isCallActive && (
                      <button onClick={endCall} data-testid="cancel-voice-call" className="size-7 rounded-full flex items-center justify-center bg-white/10 hover:bg-red-500/20 text-white/60 hover:text-red-400 transition-all" title="Cancel Call">
                        <X className="size-4" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Voice Visualization */}
                <div className="p-6 flex flex-col items-center">
                  <div className="size-28 rounded-full flex items-center justify-center mb-4 relative" style={{
                    background: isCallActive ? 'radial-gradient(circle, rgba(212,175,55,0.15) 0%, transparent 70%)' : 'radial-gradient(circle, rgba(85,85,85,0.1) 0%, transparent 70%)'
                  }}>
                    <div className={`size-20 rounded-full flex items-center justify-center transition-all ${isCallActive ? 'bg-[#FF6B00]/10 border-2 border-[#FF6B00]/40' : 'bg-white/10 border-2 border-white/20'}`}>
                      {isSpeaking ? <Volume2 className="size-8 text-[#FF6B00]" /> : isListening ? <Mic className="size-8 text-[#4ade80]" /> : <Phone className="size-8 text-white/65" />}
                    </div>
                    {isCallActive && (isSpeaking || isListening) && (
                      <div className="absolute inset-0 rounded-full border-2 animate-ping" style={{ borderColor: isSpeaking ? '#FF6B0040' : '#4ade8040' }} />
                    )}
                  </div>

                  <VoiceBars active={isCallActive && (isListening || isSpeaking)} color={isSpeaking ? '#FF6B00' : '#4ade80'} />

                  {currentText && <p className="text-xs text-white/60 italic mt-2 text-center max-w-md">"{currentText}"</p>}
                </div>

                {/* Transcript */}
                {transcript.length > 0 && (
                  <div className="mx-4 mb-4 max-h-48 overflow-y-auto rounded-lg bg-white/10 border border-white/10 p-3 space-y-2">
                    {transcript.map((msg, i) => (
                      <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                        {msg.role === 'agent' && <div className="size-6 rounded-full bg-[#FF6B00]/15 flex items-center justify-center flex-shrink-0"><Sparkles className="size-3 text-[#FF6B00]" /></div>}
                        <p className={`text-[11px] leading-relaxed max-w-[80%] px-3 py-2 rounded-xl ${msg.role === 'user' ? 'bg-white/15 text-white' : 'bg-[#FF6B00]/10 text-white/80 border border-[#FF6B00]/15'}`}>{msg.text}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Call Controls */}
                <div className="flex items-center justify-center gap-4 p-4 border-t border-white/10">
                  {!isCallActive ? (
                    <button onClick={startCall} data-testid="start-voice-call" className="flex items-center gap-2 px-8 py-3.5 bg-gradient-to-r from-[#FF6B00] to-[#B38659] rounded-full text-[#1A3026] text-sm font-semibold hover:opacity-90 transition-opacity shadow-[0_0_20px_rgba(212,163,115,0.3)]">
                      <Phone className="size-4" />
                      Talk to AI Agent
                    </button>
                  ) : (
                    <button onClick={endCall} data-testid="end-voice-call" className="flex items-center gap-2 px-8 py-3.5 bg-gradient-to-r from-[#ef4444] to-[#dc2626] rounded-full text-white text-sm font-semibold hover:opacity-90 transition-opacity">
                      <PhoneOff className="size-4" />
                      End Call
                    </button>
                  )}
                </div>
              </div>

              {/* Embed Instructions */}
              <div className="mt-4 p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20">
                <h4 className="text-[10px] text-[#555] tracking-wider mb-2">EMBED ON YOUR WEBSITE</h4>
                <p className="text-[10px] text-[#888] mb-3">Add a "Talk to AI" button to your website or Google Business Profile. Customers click it, your AI agent handles the conversation.</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] font-mono text-[#888] bg-white/80 backdrop-blur-sm p-2 rounded border border-[#FF6B00]/20 truncate">{'<button onclick="window.open(\'YOUR_AUREM_VOICE_URL\')">Talk to AI</button>'}</code>
                  <CopyButton text={'<button onclick="window.open(\'YOUR_AUREM_VOICE_URL\')">Talk to AI</button>'} label="Copy" />
                </div>
              </div>
            </div>
          )}

          {/* ═══ 5B: Self-Hosted Voice Guide ═══ */}
          {subTier === '5b' && (
            <div className="p-5">
              {/* Stack Comparison */}
              <div className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20 mb-5">
                <h4 className="text-[10px] text-[#555] tracking-wider mb-3">SELF-HOSTED vs PAID COMPARISON</h4>
                <div className="grid grid-cols-3 gap-px bg-[#1A1A1A] rounded-lg overflow-hidden text-[10px]">
                  <div className="bg-white/80 backdrop-blur-sm p-2.5 font-medium text-[#888]">Feature</div>
                  <div className="bg-white/80 backdrop-blur-sm p-2.5 text-center font-medium text-[#a855f7]">Paid (AUREM Voice/Retell)</div>
                  <div className="bg-white/80 backdrop-blur-sm p-2.5 text-center font-medium text-[#3b82f6]">Your DIY ($0)</div>
                  {[
                    ['Cost per Minute', '$0.15 - $0.20', '$0.00'],
                    ['Privacy', 'Cloud-hosted', '100% Local (Private)'],
                    ['Setup Time', '5 Minutes', '1-2 Hours (one-time)'],
                    ['Scalability', 'Unlimited', 'Limited by PC speed'],
                    ['Latency', '~500ms', '~290ms (faster!)'],
                  ].map(([feat, paid, diy], i) => (
                    <React.Fragment key={i}>
                      <div className="bg-[#080808] p-2.5 text-[#555]">{feat}</div>
                      <div className="bg-[#080808] p-2.5 text-center text-[#666]">{paid}</div>
                      <div className="bg-[#080808] p-2.5 text-center text-[#1A1A2E]">{diy}</div>
                    </React.Fragment>
                  ))}
                </div>
              </div>

              {/* Component Stack */}
              <div className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20 mb-5">
                <h4 className="text-[10px] text-[#555] tracking-wider mb-3">THE ZERO-DOLLAR DIY STACK</h4>
                <div className="space-y-2">
                  {[
                    { component: 'The Ears (STT)', tool: 'Whisper Turbo (Faster-Whisper)', why: 'Runs locally on your PC. No API cost per word.', time: '<100ms', color: '#4ade80' },
                    { component: 'The Brain (LLM)', tool: 'Ollama (Llama 3.2)', why: 'Runs on your hardware. No per-token fees.', time: '<150ms', color: '#D4AF37' },
                    { component: 'The Voice (TTS)', tool: 'Kokoro-82M', why: 'High-quality human voice that runs on basic CPU.', time: '<100ms', color: '#3b82f6' },
                    { component: 'The Glue', tool: 'Pipecat / LiveKit Agents', why: 'Open-source framework that joins the steps with zero buffering.', time: 'Real-time', color: '#a855f7' },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 bg-white/80 backdrop-blur-sm rounded-lg border border-[#FF6B00]/20">
                      <div className="size-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${item.color}10` }}>
                        <span className="text-[11px] font-bold" style={{ color: item.color }}>{item.time}</span>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-[#888]">{item.component}</span>
                          <ArrowRight className="size-3 text-[#333]" />
                          <span className="text-[11px] font-medium text-[#1A1A2E]">{item.tool}</span>
                        </div>
                        <p className="text-[9px] text-[#555]">{item.why}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 p-3 bg-[#D4AF37]/5 border border-[#D4AF37]/10 rounded-lg text-center">
                  <p className="text-sm font-bold font-mono text-[#D4AF37]">~290ms Total Latency</p>
                  <p className="text-[9px] text-[#888]">Faster than human response time (300-400ms)</p>
                </div>
              </div>

              {/* Hardware Requirements */}
              <div className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20 mb-5">
                <h4 className="text-[10px] text-[#555] tracking-wider mb-2">HARDWARE REQUIREMENTS</h4>
                <div className="flex gap-3">
                  <div className="flex-1 p-3 bg-white/80 backdrop-blur-sm rounded-lg">
                    <p className="text-[10px] font-medium text-[#1A1A2E]">Minimum</p>
                    <p className="text-[9px] text-[#555]">Laptop with 8GB RAM, any modern CPU</p>
                  </div>
                  <div className="flex-1 p-3 bg-white/80 backdrop-blur-sm rounded-lg border border-[#D4AF37]/20">
                    <p className="text-[10px] font-medium text-[#D4AF37]">Recommended</p>
                    <p className="text-[9px] text-[#555]">16GB RAM, or a $5/mo VPS for 24/7</p>
                  </div>
                </div>
              </div>

              {/* Generate Script Button */}
              <button onClick={loadSelfHostedScript} disabled={loadingScript} data-testid="generate-voice-script-btn" className="w-full px-4 py-3 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#3b82f6] to-[#1d4ed8] rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-2 mb-4">
                {loadingScript ? <><RefreshCw className="size-3.5 animate-spin" /> Generating…</> : <><Code className="size-3.5" /> Generate Pipecat Starter Code</>}
              </button>

              {selfHostedScript && (
                <div data-testid="voice-script-output">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] text-[#555] tracking-wider">PIPECAT VOICE AGENT CODE</span>
                    <CopyButton text={selfHostedScript} label="Copy Code" variant="gold" />
                  </div>
                  <pre className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20 text-[10px] text-[#555] font-mono overflow-x-auto max-h-80 whitespace-pre-wrap leading-relaxed">{selfHostedScript}</pre>
                  <div className="mt-3 p-3 bg-[#ef4444]/5 border border-[#ef4444]/10 rounded-lg">
                    <p className="text-[10px] text-[#ef4444] font-medium mb-1">Compliance Warning</p>
                    <ul className="text-[9px] text-[#888] space-y-0.5">
                      <li>- B2B Only: Only call business numbers (Google/LinkedIn)</li>
                      <li>- Warm Leads: Use for people who filled your lead form</li>
                      <li>- AI Disclosure: Identify as AI in first 10 seconds</li>
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══ 5C: Premium Voice (Locked) ═══ */}
          {subTier === '5c' && (
            <div className="p-5">
              <div className="grid grid-cols-3 gap-3 mb-5">
                {[
                  { name: 'AUREM Voice AI', desc: 'Production voice calls, DIY Engine', color: '#a855f7' },
                  { name: 'ElevenLabs', desc: 'Ultra-realistic voice cloning', color: '#E4405F' },
                  { name: 'Real Phone Lines', desc: 'Inbound + outbound via SIP', color: '#D4AF37' },
                ].map((api, i) => (
                  <div key={i} className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20 text-center relative">
                    <Lock className="size-3 text-[#a855f7] absolute top-2 right-2" />
                    <Phone className="size-6 mx-auto mb-2" style={{ color: api.color }} />
                    <p className="text-[11px] font-medium text-[#1A1A2E]">{api.name}</p>
                    <p className="text-[9px] text-[#555]">{api.desc}</p>
                  </div>
                ))}
              </div>
              <div className="p-4 bg-gradient-to-br from-[#a855f7]/5 to-transparent border border-[#a855f7]/20 rounded-xl text-center">
                <Lock className="size-6 text-[#a855f7] mx-auto mb-2" />
                <p className="text-xs font-medium text-[#1A1A2E] mb-1">Premium Voice, Enterprise Plan</p>
                <p className="text-[10px] text-[#888] mb-3">Real phone calls, voice cloning, SIP trunks, unlimited minutes</p>
                <button data-testid="upgrade-voice-btn" onClick={() => alert('Contact sales to upgrade your voice plan.')} className="px-6 py-2.5 text-xs font-semibold text-white bg-gradient-to-r from-[#a855f7] to-[#7c3aed] rounded-lg hover:opacity-90">
                  Upgrade to Enterprise
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// TIER 1: BASIC DIY
// ═══════════════════════════════════════════════════════════════

function Tier1Basic({ config, setupData, setSetupData, onSaveSetup, saving, isConfigured }) {
  const [expanded, setExpanded] = useState(false);
  const waLink = setupData.whatsapp_number ? `https://wa.me/${setupData.whatsapp_number}?text=${encodeURIComponent(setupData.brand_name ? `Hi ${setupData.brand_name}! I'd like to learn more` : "Hi! I'd like to learn more")}` : '';
  return (
    <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden" data-testid="tier-1-basic">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-5 text-left hover:bg-white/40 transition-colors">
        <div className="flex items-center gap-4">
          <div className="size-12 rounded-xl bg-[#4ade80]/10 flex items-center justify-center"><Zap className="size-6 text-[#4ade80]" /></div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-sm font-medium text-[#1A1A2E]">Basic DIY</h3>
              <TierBadge tier={1} label="5 MIN SETUP" color="#4ade80" />
              <span className="px-2 py-0.5 text-[9px] font-bold text-[#4ade80] bg-[#4ade80]/10 rounded-full">$0</span>
            </div>
            <p className="text-[11px] text-[#888]">Google Form + Google Sheet + WhatsApp Click-to-Chat link</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isConfigured && <span className="px-2 py-0.5 text-[9px] text-[#4ade80] bg-[#4ade80]/10 rounded-full flex items-center gap-1"><CheckCircle className="size-3" /> Active</span>}
          {expanded ? <ChevronDown className="size-4 text-[#555]" /> : <ChevronRight className="size-4 text-[#555]" />}
        </div>
      </button>
      {expanded && (
        <div className="px-5 pb-5 border-t border-[#FF6B00]/20 pt-5">
          <StepCard number={1} title="Create a Google Form" description="Build a lead capture form with fields: Name, Email, Phone, and concern/interest dropdown.">
            <div className="p-3 bg-white/60 rounded-lg border border-[#FF6B00]/20">
              <div className="flex flex-wrap gap-1.5 mb-2">
                {['Full Name', 'Email Address', 'WhatsApp Number', 'What are you looking for?'].map((f, i) => (
                  <span key={i} className="px-2 py-1 text-[10px] bg-white/50 text-[#1A1A2E] rounded border border-[#FF6B00]/15">{f}</span>
                ))}
              </div>
              <a href="https://forms.google.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-[10px] text-[#D4AF37] hover:underline"><ExternalLink className="size-3" /> Open Google Forms</a>
            </div>
          </StepCard>
          <StepCard number={2} title="Connect to Google Sheets" description="In Google Form, click Responses tab → Sheets icon. Creates a live spreadsheet.">
            <div className="p-3 bg-white/60 rounded-lg border border-[#FF6B00]/20"><p className="text-[10px] text-[#4ade80]">This happens automatically when you click the Sheets icon.</p></div>
          </StepCard>
          <StepCard number={3} title="Setup Brand & WhatsApp" description="Enter your details. AUREM generates your Click-to-Chat link.">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-[10px] text-[#888] mb-1 tracking-wider">BRAND NAME</label><input type="text" value={setupData.brand_name} onChange={e => setSetupData({...setupData, brand_name: e.target.value})} placeholder="Aura-Gen" data-testid="t1-brand-name" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" /></div>
                <div><label className="block text-[10px] text-[#888] mb-1 tracking-wider">TAGLINE</label><input type="text" value={setupData.brand_tagline} onChange={e => setSetupData({...setupData, brand_tagline: e.target.value})} placeholder="Scientific-Luxe Skincare" data-testid="t1-tagline" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-[10px] text-[#888] mb-1 tracking-wider">GMAIL</label><input type="email" value={setupData.gmail_email} onChange={e => setSetupData({...setupData, gmail_email: e.target.value})} placeholder="you@gmail.com" data-testid="t1-gmail" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" /></div>
                <div><label className="block text-[10px] text-[#888] mb-1 tracking-wider">WHATSAPP NUMBER</label><input type="tel" value={setupData.whatsapp_number} onChange={e => setSetupData({...setupData, whatsapp_number: e.target.value})} placeholder="15551234567" data-testid="t1-whatsapp" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50 font-mono" /></div>
              </div>
              <button onClick={onSaveSetup} disabled={!setupData.gmail_email || !setupData.whatsapp_number || saving} data-testid="t1-save-btn" className="w-full px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 disabled:opacity-50">
                {saving ? 'Saving...' : 'Save Configuration'}
              </button>
            </div>
          </StepCard>
          <StepCard number={4} title="Share Click-to-Chat Link" description="Copy and share on your website, social media, or email signature." total={4}>
            {waLink ? (
              <div className="p-3 bg-white/60 rounded-lg border border-[#FF6B00]/20">
                <div className="flex items-center justify-between mb-2"><span className="text-[10px] text-[#25D366] flex items-center gap-1"><MessageCircle className="size-3" /> WhatsApp Click-to-Chat</span><CopyButton text={waLink} label="Copy Link" /></div>
                <code className="block text-[10px] font-mono text-[#888] break-all">{waLink}</code>
              </div>
            ) : <p className="text-[10px] text-[#555] italic">Enter WhatsApp number above to generate link.</p>}
          </StepCard>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// TIER 3: EXTENSION + TIER 4: PREMIUM (compact)
// ═══════════════════════════════════════════════════════════════

function Tier3Extension({ token }) {
  const [expanded, setExpanded] = useState(false);
  const [activeSection, setActiveSection] = useState('download');
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState(null);
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLeads, setSelectedLeads] = useState(new Set());

  const fetchLeads = useCallback(async () => {
    setLoadingLeads(true);
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (searchQuery) params.set('search', searchQuery);
      const r = await fetch(`${API_URL}/api/extension/leads?${params}`, { headers: { 'Authorization': `Bearer ${token}` } });
      if (r.ok) { const d = await r.json(); setLeads(d.leads || []); }
    } catch {} finally { setLoadingLeads(false); }
  }, [token, searchQuery]);

  const fetchStats = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/extension/leads/stats`, { headers: { 'Authorization': `Bearer ${token}` } });
      if (r.ok) { const d = await r.json(); setStats(d.stats || null); }
    } catch {}
  }, [token]);

  useEffect(() => { if (expanded) { fetchLeads(); fetchStats(); } }, [expanded, fetchLeads, fetchStats]);

  const handleDownload = () => { window.open(`${API_URL}/api/extension/download`, '_blank'); };
  const handleExportCSV = () => { window.open(`${API_URL}/api/extension/leads/export`, '_blank'); };

  const handleDeleteLead = async (leadId) => {
    try {
      await fetch(`${API_URL}/api/extension/leads/${leadId}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
      fetchLeads(); fetchStats();
    } catch {}
  };

  const handleStatusChange = async (leadId, newStatus) => {
    try {
      await fetch(`${API_URL}/api/extension/leads/${leadId}/status`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ status: newStatus })
      });
      fetchLeads(); fetchStats();
    } catch {}
  };

  const sourceIcon = (source) => {
    if (source?.includes('linkedin')) return <Linkedin className="size-3 text-[#0A66C2]" />;
    if (source?.includes('facebook')) return <Facebook className="size-3 text-[#1877F2]" />;
    if (source?.includes('instagram')) return <Instagram className="size-3 text-[#E4405F]" />;
    if (source?.includes('twitter') || source?.includes('x_')) return <Twitter className="size-3 text-[#999]" />;
    return <Globe className="size-3 text-[#D4AF37]" />;
  };

  const statusColors = { new: '#D4AF37', contacted: '#3b82f6', converted: '#4ade80', lost: '#ef4444' };

  return (
    <div className="bg-white/80 backdrop-blur-sm border border-[#D4AF37]/20 rounded-xl overflow-hidden" data-testid="tier-3-extension">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-5 text-left hover:bg-white/40 transition-colors">
        <div className="flex items-center gap-4">
          <div className="size-12 rounded-xl bg-[#D4AF37]/10 flex items-center justify-center relative"><Chrome className="size-6 text-[#D4AF37]" /><div className="absolute -top-1 -right-1 size-4 bg-[#D4AF37] rounded-full flex items-center justify-center"><Sparkles className="size-2.5 text-[#050505]" /></div></div>
          <div>
            <div className="flex items-center gap-3 mb-1"><h3 className="text-sm font-medium text-[#1A1A2E]">AUREM Browser Extension</h3><TierBadge tier={3} label="ONE-CLICK" color="#D4AF37" /><span className="px-2 py-0.5 text-[9px] font-bold text-[#4ade80] bg-[#4ade80]/10 rounded-full">READY</span></div>
            <p className="text-[11px] text-[#888]">Scrape leads from LinkedIn, social media & any webpage, auto-sync to dashboard</p>
          </div>
        </div>
        {expanded ? <ChevronDown className="size-4 text-[#555]" /> : <ChevronRight className="size-4 text-[#555]" />}
      </button>

      {expanded && (
        <div className="border-t border-[#D4AF37]/10">
          {/* Section tabs */}
          <div className="flex gap-1 px-5 pt-4 pb-3">
            {[
              { id: 'download', label: 'Install', icon: Chrome },
              { id: 'leads', label: `Leads${stats ? ` (${stats.total})` : ''}`, icon: Users },
              { id: 'stats', label: 'Analytics', icon: BarChart3 },
            ].map(tab => (
              <button key={tab.id} onClick={() => setActiveSection(tab.id)} data-testid={`ext-tab-${tab.id}`}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[10px] font-medium transition-colors ${activeSection === tab.id ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/20' : 'text-[#666] hover:text-[#555]'}`}>
                <tab.icon className="size-3" />{tab.label}
              </button>
            ))}
          </div>

          {/* ── Install Section ── */}
          {activeSection === 'download' && (
            <div className="px-5 pb-5 space-y-4">
              <div className="p-4 bg-white/60 rounded-xl border border-[#FF6B00]/20">
                <h4 className="text-xs font-medium text-[#1A1A2E] mb-3">Quick Setup, 2 minutes</h4>
                <div className="space-y-3">
                  <StepCard number={1} title="Download Extension" description="Click below to download the AUREM Lead Scraper extension package (.zip)" total={3}>
                    <button onClick={handleDownload} data-testid="download-extension-btn" className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] text-xs font-semibold hover:opacity-90">
                      <Chrome className="size-3.5" /> Download Extension
                    </button>
                  </StepCard>
                  <StepCard number={2} title="Load in Chrome" description="Open chrome://extensions → Enable Developer Mode → Drag & drop the extracted folder" total={3} />
                  <StepCard number={3} title="Connect to AUREM" description="Click the extension icon → Settings → Paste your dashboard URL and auth token → Start scraping!" total={3} />
                </div>
              </div>

              {/* Supported platforms */}
              <div className="grid grid-cols-2 gap-2">
                {SOCIAL_CHANNELS.map(ch => (
                  <div key={ch.id} className="p-2.5 bg-white/60 rounded-lg border border-[#FF6B00]/20 flex items-center gap-2.5">
                    <div className="size-7 rounded-md flex items-center justify-center" style={{ backgroundColor: `${ch.color}12` }}><ch.icon className="size-3.5" style={{ color: ch.color }} /></div>
                    <div><p className="text-[10px] font-medium text-[#1A1A2E]">{ch.name}</p><p className="text-[9px] text-[#555] leading-tight">{ch.desc}</p></div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Leads Section ── */}
          {activeSection === 'leads' && (
            <div className="px-5 pb-5">
              {/* Search + actions bar */}
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1 relative">
                  <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchLeads()}
                    placeholder="Search leads by name, email, company..." data-testid="ext-leads-search"
                    className="w-full px-3 py-2 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50 pl-8" />
                  <Target className="absolute left-2.5 top-2.5 size-3.5 text-[#555]" />
                </div>
                <button onClick={fetchLeads} data-testid="ext-leads-refresh" className="p-2 rounded-lg bg-white/50 border border-[#FF6B00]/15 text-[#888] hover:text-[#1A1A2E]"><RefreshCw className={`size-3.5 ${loadingLeads ? 'animate-spin' : ''}`} /></button>
                <button onClick={handleExportCSV} data-testid="ext-leads-export" className="flex items-center gap-1.5 px-3 py-2 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-[10px] font-medium text-[#888] hover:text-[#1A1A2E]">
                  <ExternalLink className="size-3" /> CSV
                </button>
              </div>

              {/* Leads list */}
              {leads.length > 0 ? (
                <div className="bg-white/60 rounded-xl border border-[#FF6B00]/20 divide-y divide-[#111] max-h-[400px] overflow-auto">
                  {leads.map((lead) => (
                    <div key={lead.lead_id} className="flex items-center gap-3 px-4 py-3 hover:bg-white/80 backdrop-blur-sm group" data-testid={`ext-lead-${lead.lead_id}`}>
                      <div className="size-8 rounded-lg bg-[#D4AF37]/10 flex items-center justify-center text-[11px] font-bold text-[#D4AF37]">
                        {(lead.name || '?')[0].toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-[#1A1A2E] truncate">{lead.name}</span>
                          {sourceIcon(lead.source)}
                        </div>
                        {lead.title && <p className="text-[10px] text-[#888] truncate">{lead.title}</p>}
                        <div className="flex items-center gap-2 mt-0.5">
                          {lead.email && <span className="text-[9px] text-[#3b82f6]">{lead.email}</span>}
                          {lead.phone && <span className="text-[9px] text-[#4ade80]">{lead.phone}</span>}
                          {lead.company && <span className="text-[9px] text-[#a855f7]">{lead.company}</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <select value={lead.status || 'new'} onChange={e => handleStatusChange(lead.lead_id, e.target.value)}
                          className="px-1.5 py-0.5 bg-white/50 border border-[#FF6B00]/15 rounded text-[9px] text-[#1A1A2E] outline-none cursor-pointer"
                          data-testid={`ext-lead-status-${lead.lead_id}`}>
                          <option value="new">New</option>
                          <option value="contacted">Contacted</option>
                          <option value="converted">Converted</option>
                          <option value="lost">Lost</option>
                        </select>
                        <button onClick={() => handleDeleteLead(lead.lead_id)} className="p-1 rounded text-[#555] hover:text-[#ef4444]"><Trash2 className="size-3" /></button>
                      </div>
                      <span className="px-1.5 py-0.5 text-[8px] font-medium rounded" style={{ backgroundColor: `${statusColors[lead.status] || '#D4AF37'}12`, color: statusColors[lead.status] || '#D4AF37' }}>
                        {lead.status || 'new'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-10 bg-white/60 rounded-xl border border-[#FF6B00]/20 text-center">
                  <Chrome className="size-8 text-[#333] mx-auto mb-3" />
                  <p className="text-xs text-[#555] mb-1">No leads scraped yet</p>
                  <p className="text-[10px] text-[#444]">Install the extension and start scraping LinkedIn, social profiles & websites</p>
                </div>
              )}
            </div>
          )}

          {/* ── Stats Section ── */}
          {activeSection === 'stats' && (
            <div className="px-5 pb-5 space-y-3">
              {stats ? (
                <>
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      { label: 'Total', value: stats.total, color: '#D4AF37' },
                      { label: 'New', value: stats.new, color: '#f59e0b' },
                      { label: 'Contacted', value: stats.contacted, color: '#3b82f6' },
                      { label: 'Converted', value: stats.converted, color: '#4ade80' },
                    ].map(s => (
                      <div key={s.label} className="p-3 bg-white/60 rounded-xl border border-[#FF6B00]/20 text-center">
                        <div className="text-xl font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
                        <div className="text-[9px] text-[#555] mt-0.5">{s.label}</div>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-3 bg-white/60 rounded-xl border border-[#FF6B00]/20">
                      <div className="text-[10px] text-[#555] mb-2 tracking-wider">DATA QUALITY</div>
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-[#888]">With Email</span>
                          <span className="text-[10px] font-mono text-[#3b82f6]">{stats.with_email}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-[#888]">With Phone</span>
                          <span className="text-[10px] font-mono text-[#4ade80]">{stats.with_phone}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-[#888]">Email Rate</span>
                          <span className="text-[10px] font-mono text-[#D4AF37]">{stats.total > 0 ? Math.round(stats.with_email / stats.total * 100) : 0}%</span>
                        </div>
                      </div>
                    </div>
                    <div className="p-3 bg-white/60 rounded-xl border border-[#FF6B00]/20">
                      <div className="text-[10px] text-[#555] mb-2 tracking-wider">BY SOURCE</div>
                      <div className="space-y-1.5">
                        {Object.entries(stats.sources || {}).slice(0, 5).map(([src, count]) => (
                          <div key={src} className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              {sourceIcon(src)}
                              <span className="text-[10px] text-[#888]">{src.replace('_', ' ')}</span>
                            </div>
                            <span className="text-[10px] font-mono text-[#1A1A2E]">{count}</span>
                          </div>
                        ))}
                        {Object.keys(stats.sources || {}).length === 0 && <p className="text-[10px] text-[#444]">No data yet</p>}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="p-8 bg-white/60 rounded-xl border border-[#FF6B00]/20 text-center">
                  <BarChart3 className="size-8 text-[#333] mx-auto mb-2" />
                  <p className="text-xs text-[#555]">Analytics will appear as leads are scraped</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Tier4Premium() {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden opacity-80" data-testid="tier-4-premium">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-5 text-left hover:bg-white/40 transition-colors">
        <div className="flex items-center gap-4">
          <div className="size-12 rounded-xl bg-[#a855f7]/10 flex items-center justify-center"><Lock className="size-6 text-[#a855f7]" /></div>
          <div>
            <div className="flex items-center gap-3 mb-1"><h3 className="text-sm font-medium text-[#1A1A2E]">Premium API Integrations</h3><TierBadge tier={4} label="UNLIMITED" color="#a855f7" /></div>
            <p className="text-[11px] text-[#888]">Twilio, SendGrid, Meta Business API, no limits, no manual setup</p>
          </div>
        </div>
        {expanded ? <ChevronDown className="size-4 text-[#555]" /> : <ChevronRight className="size-4 text-[#555]" />}
      </button>
      {expanded && (
        <div className="p-5 border-t border-[#FF6B00]/20">
          <div className="p-4 bg-gradient-to-br from-[#a855f7]/5 to-transparent border border-[#a855f7]/20 rounded-xl text-center">
            <Lock className="size-6 text-[#a855f7] mx-auto mb-2" />
            <p className="text-xs font-medium text-[#1A1A2E] mb-1">Enterprise Plan</p>
            <p className="text-[10px] text-[#888] mb-3">Unlimited API calls, zero setup, priority support</p>
            <button data-testid="upgrade-premium-btn" onClick={() => alert('Contact sales to upgrade to premium.')} className="px-6 py-2.5 text-xs font-semibold text-white bg-gradient-to-r from-[#a855f7] to-[#7c3aed] rounded-lg hover:opacity-90">Upgrade</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function AcquisitionEngine({ token, user }) {
  const [campaigns, setCampaigns] = useState([]);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [showCreateCampaign, setShowCreateCampaign] = useState(false);
  const [setupData, setSetupData] = useState({ gmail_email: '', gmail_app_password: '', whatsapp_number: '', brand_name: '', brand_tagline: '' });
  const [campaignForm, setCampaignForm] = useState({ name: '', template_id: 'welcome-luxe', whatsapp_msg: '', discount: '10', auto_email: true, auto_whatsapp: true });
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState(null);
  const [funnelStats, setFunnelStats] = useState(null);
  const [copied, setCopied] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const h = { 'Authorization': `Bearer ${token}` };
      const [cR, lR, cfR, sR] = await Promise.all([
        fetch(`${API_URL}/api/acquisition/campaigns`, { headers: h }),
        fetch(`${API_URL}/api/acquisition/leads`, { headers: h }),
        fetch(`${API_URL}/api/acquisition/config`, { headers: h }),
        fetch(`${API_URL}/api/acquisition/funnel-stats`, { headers: h })
      ]);
      if (cR.ok) { const d = await cR.json(); setCampaigns(d.campaigns || []); }
      if (lR.ok) { const d = await lR.json(); setLeads(d.leads || []); }
      if (cfR.ok) { const d = await cfR.json(); setConfig(d.config || null); if (d.config) setSetupData(prev => ({ ...prev, ...d.config })); }
      if (sR.ok) { const d = await sR.json(); setFunnelStats(d); }
    } catch { setCampaigns([]); setLeads([]); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);
  // iter 271 — live refresh every 15s (pauses in background)
  useLivePolling(fetchData, 15000);

  const handleSaveSetup = async () => { setSaving(true); try { const r = await fetch(`${API_URL}/api/acquisition/config`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(setupData) }); if (r.ok) fetchData(); } catch {} finally { setSaving(false); } };
  const handleCreateCampaign = async () => { setSaving(true); try { const r = await fetch(`${API_URL}/api/acquisition/campaigns`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(campaignForm) }); if (r.ok) { setShowCreateCampaign(false); setCampaignForm({ name: '', template_id: 'welcome-luxe', whatsapp_msg: '', discount: '10', auto_email: true, auto_whatsapp: true }); fetchData(); } } catch {} finally { setSaving(false); } };
  const handleToggle = async (id, status) => { try { await fetch(`${API_URL}/api/acquisition/campaigns/${id}/toggle`, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ status: status === 'active' ? 'paused' : 'active' }) }); fetchData(); } catch {} };
  const handleDelete = async (id) => { try { await fetch(`${API_URL}/api/acquisition/campaigns/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } }); fetchData(); } catch {} };
  const copyText = (text, key) => { navigator.clipboard.writeText(text); setCopied(key); setTimeout(() => setCopied(null), 2000); };

  const funnel = funnelStats || { discovered: 0, captured: 0, nurtured: 0, converted: 0 };
  const isConfigured = config && config.gmail_email && config.whatsapp_number;

  if (loading) return (
    <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="acquisition-engine-loading">
      <div className="flex items-center gap-3 text-[#666]"><RefreshCw className="size-5 animate-spin" /><span className="text-sm">Loading Acquisition Engine…</span></div>
    </div>
  );

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="acquisition-engine">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">Acquisition Engine</h1>
            <p className="text-xs text-[#888]">Zero-cost customer acquisition across every channel, your accounts, our automation</p>
          </div>
          <button onClick={() => isConfigured ? setShowCreateCampaign(true) : setActiveTab('channels')} data-testid="create-campaign-btn" className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] text-xs font-semibold hover:opacity-90"><Plus className="size-3.5" /> New Campaign</button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/80 backdrop-blur-sm p-1 rounded-lg border border-[#FF6B00]/20 w-fit">
          {[
            { id: 'overview', label: 'Overview', icon: BarChart3 },
            { id: 'channels', label: 'Setup Channels', icon: Zap },
            { id: 'campaigns', label: 'Campaigns', icon: Rocket },
            { id: 'leads', label: 'Leads', icon: Users },
            { id: 'templates', label: 'Templates', icon: Mail },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} data-testid={`acq-tab-${tab.id}`} className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs transition-all ${activeTab === tab.id ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30' : 'text-[#666] hover:text-[#555]'}`}>
              <tab.icon className="size-3.5" />{tab.label}
            </button>
          ))}
        </div>

        {/* ═══ OVERVIEW ═══ */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
              <h3 className="text-[10px] text-[#555] tracking-wider mb-5">ACQUISITION FUNNEL</h3>
              <div className="flex items-center justify-between">
                {[
                  { stage: 'Discovered', value: funnel.discovered, icon: Globe, color: '#888' },
                  { stage: 'Captured', value: funnel.captured, icon: Target, color: '#D4AF37' },
                  { stage: 'Nurtured', value: funnel.nurtured, icon: Mail, color: '#3b82f6' },
                  { stage: 'Converted', value: funnel.converted, icon: CheckCircle, color: '#4ade80' }
                ].map((s, i) => (
                  <React.Fragment key={i}>
                    <div className="flex-1 text-center">
                      <div className="size-14 rounded-2xl mx-auto mb-2 flex items-center justify-center" style={{ backgroundColor: `${s.color}12` }}><s.icon className="size-6" style={{ color: s.color }} /></div>
                      <div className="text-2xl font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
                      <div className="text-[11px] font-medium text-[#1A1A2E] mt-0.5">{s.stage}</div>
                    </div>
                    {i < 3 && <div className="flex items-center px-2"><div className="w-10 h-[1px] bg-[#333]" /><ChevronRight className="size-4 text-[#333]" /></div>}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* 5-Tier Cards */}
            <div className="grid grid-cols-5 gap-3">
              {[
                { tier: 1, name: 'Basic DIY', status: isConfigured ? 'Active' : 'Setup', color: '#4ade80', icon: Zap, desc: 'Forms + Chat' },
                { tier: 2, name: 'Advanced', status: 'Available', color: '#3b82f6', icon: Code, desc: 'Nexus Connect' },
                { tier: 3, name: 'Extension', status: 'Ready', color: '#D4AF37', icon: Chrome, desc: 'Lead Scraper' },
                { tier: 4, name: 'Premium', status: 'Enterprise', color: '#a855f7', icon: Lock, desc: 'Unlimited' },
                { tier: 5, name: 'Voice Agent', status: 'LIVE', color: '#D4AF37', icon: Phone, desc: 'Talk to AI' },
              ].map(t => (
                <button key={t.tier} onClick={() => setActiveTab('channels')} className={`p-4 bg-white/80 backdrop-blur-sm rounded-xl text-left hover:border-[#D4AF37]/20 transition-colors group ${t.tier === 5 ? 'border-2 border-[#D4AF37]/30 shadow-[0_0_15px_rgba(212,175,55,0.05)]' : 'border border-[#FF6B00]/20'}`}>
                  <t.icon className="size-5 mb-2" style={{ color: t.color }} />
                  <p className="text-xs font-medium text-[#1A1A2E] mb-0.5">{t.name}</p>
                  <p className="text-[9px] text-[#555] mb-2">{t.desc}</p>
                  <span className="px-2 py-0.5 text-[9px] rounded-full" style={{ backgroundColor: `${t.color}12`, color: t.color }}>{t.status}</span>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl"><div className="text-2xl font-bold font-mono text-[#D4AF37]">{campaigns.length}</div><p className="text-[10px] text-[#555] mt-1">Total Campaigns</p></div>
              <div className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl"><div className="text-2xl font-bold font-mono text-[#3b82f6]">{leads.length}</div><p className="text-[10px] text-[#555] mt-1">Leads Captured</p></div>
              <div className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl"><div className="text-2xl font-bold font-mono text-[#4ade80]">$0</div><p className="text-[10px] text-[#555] mt-1">API Costs This Month</p></div>
            </div>
          </div>
        )}

        {/* ═══ CHANNELS (5 Tiers) ═══ */}
        {activeTab === 'channels' && (
          <div className="space-y-4">
            <Tier5VoiceAgent token={token} config={config} />
            <Tier1Basic config={config} setupData={setupData} setSetupData={setSetupData} onSaveSetup={handleSaveSetup} saving={saving} isConfigured={isConfigured} />
            <Tier3Extension token={token} />
            <Tier4Premium />
          </div>
        )}

        {/* ═══ CAMPAIGNS ═══ */}
        {activeTab === 'campaigns' && (
          campaigns.length > 0 ? (
            <div className="space-y-3">
              {campaigns.map(c => {
                const formUrl = `${API_URL}/api/acquisition/form/${c.id}`;
                const embedCode = `<iframe src="${formUrl}" width="100%" height="500" frameborder="0"></iframe>`;
                return (
                  <div key={c.id} data-testid={`campaign-${c.id}`} className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className={`size-10 rounded-lg flex items-center justify-center ${c.status === 'active' ? 'bg-[#4ade80]/10' : 'bg-[#555]/10'}`}><Rocket className={`size-5 ${c.status === 'active' ? 'text-[#4ade80]' : 'text-[#555]'}`} /></div>
                        <div><h3 className="text-sm font-medium text-[#1A1A2E]">{c.name}</h3><div className="flex items-center gap-2 mt-0.5">{c.auto_email && <span className="text-[9px] px-1.5 py-0.5 bg-[#3b82f6]/10 text-[#3b82f6] rounded">Email</span>}{c.auto_whatsapp && <span className="text-[9px] px-1.5 py-0.5 bg-[#25D366]/10 text-[#25D366] rounded">WhatsApp</span>}</div></div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${c.status === 'active' ? 'bg-[#4ade80]/10 text-[#4ade80]' : 'bg-[#555]/10 text-[#555]'}`}>{c.status === 'active' ? 'Live' : 'Paused'}</span>
                        <button onClick={() => handleToggle(c.id, c.status)} className="p-1.5 rounded-md text-[#888] hover:text-[#1A1A2E]">{c.status === 'active' ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}</button>
                        <button onClick={() => handleDelete(c.id)} className="p-1.5 rounded-md text-[#555] hover:text-[#ef4444]"><Trash2 className="size-3.5" /></button>
                      </div>
                    </div>
                    <div className="grid grid-cols-4 gap-3 mb-4">
                      {[{ l: 'Leads', v: c.lead_count||0, c: '#D4AF37' },{ l: 'Emails', v: c.emails_sent||0, c: '#3b82f6' },{ l: 'WA Clicks', v: c.wa_clicks||0, c: '#25D366' },{ l: 'Conv %', v: `${c.conversion_rate||0}%`, c: '#4ade80' }].map((s,i)=>(
                        <div key={i} className="p-3 bg-white/60 rounded-lg text-center"><div className="text-lg font-bold font-mono" style={{color:s.c}}>{s.v}</div><div className="text-[9px] text-[#555]">{s.l}</div></div>
                      ))}
                    </div>
                    <div className="p-3 bg-white/60 rounded-lg">
                      <div className="flex items-center justify-between mb-1.5"><span className="text-[10px] text-[#555]">FORM LINK</span>
                        <div className="flex gap-1">
                          <button onClick={() => copyText(formUrl,`u-${c.id}`)} className="flex items-center gap-1 px-2 py-1 text-[10px] text-[#D4AF37] bg-[#D4AF37]/10 rounded">{copied===`u-${c.id}` ? <Check className="size-3"/> : <Copy className="size-3"/>} URL</button>
                          <button onClick={() => copyText(embedCode,`e-${c.id}`)} className="flex items-center gap-1 px-2 py-1 text-[10px] text-[#888] bg-white/50 rounded">{copied===`e-${c.id}` ? <Check className="size-3"/> : <Code className="size-3"/>} Embed</button>
                        </div>
                      </div>
                      <code className="block text-[10px] font-mono text-[#888] truncate">{formUrl}</code>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-16 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl text-center">
              <Rocket className="size-10 text-[#333] mx-auto mb-4" /><h3 className="text-sm font-medium text-[#1A1A2E] mb-2">No campaigns yet</h3>
              <button onClick={() => isConfigured ? setShowCreateCampaign(true) : setActiveTab('channels')} className="px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90">{isConfigured ? 'Create Campaign' : 'Setup First'}</button>
            </div>
          )
        )}

        {/* ═══ LEADS ═══ */}
        {activeTab === 'leads' && (
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-[#FF6B00]/20"><h3 className="text-xs text-[#555] tracking-wider">CAPTURED LEADS ({leads.length})</h3></div>
            {leads.length > 0 ? (
              <div className="divide-y divide-[#141414]">
                {leads.map((l,i) => (
                  <div key={i} className="flex items-center justify-between px-4 py-3 hover:bg-white/40">
                    <div className="flex items-center gap-3"><div className="size-8 rounded-full bg-[#D4AF37]/10 flex items-center justify-center text-[10px] font-semibold text-[#D4AF37]">{(l.name||'L')[0].toUpperCase()}</div><div><p className="text-xs text-[#1A1A2E]">{l.name}</p><p className="text-[10px] text-[#888]">{l.email}</p></div></div>
                    <div className="flex items-center gap-3">{l.concern && <span className="px-2 py-0.5 text-[9px] bg-[#D4AF37]/10 text-[#D4AF37] rounded">{l.concern}</span>}<div className="flex gap-1">{l.email_sent && <Mail className="size-3 text-[#3b82f6]"/>}{l.wa_clicked && <MessageCircle className="size-3 text-[#25D366]"/>}</div></div>
                  </div>
                ))}
              </div>
            ) : <div className="p-10 text-center"><Users className="size-8 text-[#333] mx-auto mb-3"/><p className="text-sm text-[#555]">No leads yet</p></div>}
          </div>
        )}

        {/* ═══ TEMPLATES ═══ */}
        {activeTab === 'templates' && (
          <div className="grid grid-cols-2 gap-4">
            {EMAIL_TEMPLATES.map(t => (
              <div key={t.id} data-testid={`template-${t.id}`} className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
                <span className="text-[9px] px-2 py-0.5 rounded-full bg-[#D4AF37]/10 text-[#D4AF37]">{t.category}</span>
                <h3 className="text-sm font-medium text-[#1A1A2E] mt-2 mb-1">{t.name}</h3>
                <p className="text-[10px] text-[#D4AF37] font-mono mb-2">{t.subject}</p>
                <p className="text-[11px] text-[#888] mb-3">{t.preview}</p>
                <div className="flex flex-wrap gap-1">{t.tags.map((tag,i) => <span key={i} className="px-2 py-0.5 text-[9px] bg-white/50 text-[#666] rounded border border-[#FF6B00]/15">{tag}</span>)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Campaign Modal */}
      {showCreateCampaign && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-2xl w-full max-w-lg overflow-hidden max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-[#FF6B00]/20"><h3 className="text-sm font-medium text-[#1A1A2E]">New Campaign</h3><button onClick={() => setShowCreateCampaign(false)} className="text-[#555] hover:text-[#555]"><X className="size-5"/></button></div>
            <div className="flex-1 overflow-auto p-5 space-y-4">
              <div><label className="block text-[10px] text-[#888] mb-1.5 tracking-wider">CAMPAIGN NAME</label><input type="text" value={campaignForm.name} onChange={e => setCampaignForm({...campaignForm, name: e.target.value})} placeholder="Summer Launch" data-testid="campaign-name-input" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"/></div>
              <div><label className="block text-[10px] text-[#888] mb-1.5 tracking-wider">EMAIL TEMPLATE</label>
                <div className="space-y-2">{EMAIL_TEMPLATES.map(t => (<button key={t.id} onClick={() => setCampaignForm({...campaignForm, template_id: t.id})} className={`w-full text-left p-3 rounded-lg border transition-colors ${campaignForm.template_id === t.id ? 'bg-[#D4AF37]/10 border-[#D4AF37]/30' : 'bg-white/50 border-[#FF6B00]/15'}`}><p className="text-xs text-[#1A1A2E]">{t.name}</p><p className="text-[10px] text-[#888] mt-0.5">{t.subject}</p></button>))}</div>
              </div>
              <div><label className="block text-[10px] text-[#888] mb-1.5 tracking-wider">WHATSAPP MESSAGE</label><input type="text" value={campaignForm.whatsapp_msg} onChange={e => setCampaignForm({...campaignForm, whatsapp_msg: e.target.value})} placeholder="Hi! I'd like to claim my offer" data-testid="campaign-wa-msg" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"/></div>
            </div>
            <div className="flex gap-3 p-5 border-t border-[#FF6B00]/20">
              <button onClick={() => setShowCreateCampaign(false)} className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#FF6B00]/15 rounded-lg">Cancel</button>
              <button onClick={handleCreateCampaign} disabled={!campaignForm.name || saving} data-testid="launch-campaign-btn" className="flex-1 px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg disabled:opacity-50">{saving ? 'Creating...' : 'Launch'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
