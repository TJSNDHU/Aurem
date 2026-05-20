/**
 * AUREM Voice-to-Voice (V2V) Interface
 * Full WebSocket engine with:
 *  - Server-side OpenAI TTS (high-quality audio)
 *  - Browser Web Speech API for STT (captures user voice)
 *  - Live Emotion Detection (ToneSync sentiment indicator)
 *  - Panic Button Manual Override (take control / resume AI)
 *  - Real-time transcript with vibe labels
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic, MicOff, Phone, PhoneOff, Volume2, VolumeX,
  Loader2, AlertCircle, ShieldAlert, ShieldCheck,
  Activity, Zap, Brain, HeartPulse, AlertTriangle
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

/* ═══ VIBE BADGE — Live Emotion Indicator ═══ */
const VIBE_CONFIG = {
  POSITIVE:  { color: '#4ADE80', bg: 'rgba(74,222,128,0.12)', border: 'rgba(74,222,128,0.3)', icon: Zap,         label: 'Positive' },
  NEUTRAL:   { color: '#94A3B8', bg: 'rgba(148,163,184,0.10)', border: 'rgba(148,163,184,0.25)', icon: Activity,    label: 'Neutral' },
  CONCERNED: { color: '#FBBF24', bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.3)',  icon: Brain,        label: 'Concerned' },
  PANIC:     { color: '#EF4444', bg: 'rgba(239,68,68,0.15)',  border: 'rgba(239,68,68,0.4)',   icon: HeartPulse,   label: 'PANIC' },
};

const VibeBadge = ({ vibe, emotion, score }) => {
  const cfg = VIBE_CONFIG[vibe] || VIBE_CONFIG.NEUTRAL;
  const Icon = cfg.icon;

  return (
    <div
      data-testid="vibe-badge"
      className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-500"
      style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}
    >
      <Icon className="size-3.5" />
      <span>{cfg.label}</span>
      {emotion && emotion !== 'neutral' && (
        <span className="opacity-70 ml-1">({emotion})</span>
      )}
      {typeof score === 'number' && (
        <span className="opacity-50 ml-1">{score.toFixed(1)}</span>
      )}
    </div>
  );
};

/* ═══ VOICE VISUALIZER ═══ */
const VoiceVisualizer = ({ isActive, isSpeaking, vibe }) => {
  const barCount = 16;
  const vibeColor = VIBE_CONFIG[vibe]?.color || '#D4A373';
  const baseColor = isSpeaking ? vibeColor : '#4ADE80';

  return (
    <div className="flex items-end justify-center gap-[3px] h-20" data-testid="voice-visualizer">
      {[...Array(barCount)].map((_, i) => {
        const h = isActive ? 15 + Math.random() * 85 : 12;
        return (
          <div
            key={i}
            className="w-[3px] rounded-full transition-all"
            style={{
              height: `${h}%`,
              background: isActive ? baseColor : '#222',
              opacity: isActive ? 0.5 + Math.random() * 0.5 : 0.3,
              transitionDuration: '120ms',
            }}
          />
        );
      })}
    </div>
  );
};

/* ═══ PANIC OVERRIDE PANEL ═══ */
const PanicOverridePanel = ({ panicEvent, onTakeControl, onResumeAI, isHumanControlling }) => {
  if (!panicEvent && !isHumanControlling) return null;

  return (
    <div
      data-testid="panic-override-panel"
      className="mx-4 mb-3 p-3 rounded-xl text-xs"
      style={{
        background: isHumanControlling ? 'rgba(74,222,128,0.08)' : 'rgba(239,68,68,0.10)',
        border: `1px solid ${isHumanControlling ? 'rgba(74,222,128,0.3)' : 'rgba(239,68,68,0.3)'}`,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isHumanControlling ? (
            <ShieldCheck className="size-4 text-green-400" />
          ) : (
            <AlertTriangle className="size-4 text-red-400 animate-pulse" />
          )}
          <span className={isHumanControlling ? 'text-green-300 font-semibold' : 'text-red-300 font-semibold'}>
            {isHumanControlling ? 'You are in control — AI paused' : 'Customer distress detected'}
          </span>
        </div>
        <div className="flex gap-2">
          {!isHumanControlling ? (
            <button
              data-testid="take-control-btn"
              onClick={onTakeControl}
              className="px-3 py-1 rounded-full text-xs font-bold transition-all"
              style={{ background: 'rgba(239,68,68,0.25)', color: '#FCA5A5', border: '1px solid rgba(239,68,68,0.4)', cursor: 'pointer' }}
            >
              TAKE CONTROL
            </button>
          ) : (
            <button
              data-testid="resume-ai-btn"
              onClick={onResumeAI}
              className="px-3 py-1 rounded-full text-xs font-bold transition-all"
              style={{ background: 'rgba(74,222,128,0.2)', color: '#86EFAC', border: '1px solid rgba(74,222,128,0.3)', cursor: 'pointer' }}
            >
              RESUME AI
            </button>
          )}
        </div>
      </div>
      {panicEvent?.keywords?.length > 0 && (
        <div className="mt-2 text-[10px] text-red-400/60">
          Triggers: {panicEvent.keywords.join(', ')}
        </div>
      )}
    </div>
  );
};

/* ═══ MAIN COMPONENT ═══ */
const AuremVoice = ({ token, onClose }) => {
  const [isCallActive, setIsCallActive] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeakerOn, setIsSpeakerOn] = useState(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [error, setError] = useState(null);
  const [callDuration, setCallDuration] = useState(0);
  const [callId, setCallId] = useState(null);

  // Emotion / Tone Sync state
  const [currentVibe, setCurrentVibe] = useState('NEUTRAL');
  const [currentEmotion, setCurrentEmotion] = useState('neutral');
  const [sentimentScore, setSentimentScore] = useState(0);

  // Panic Override state
  const [panicEvent, setPanicEvent] = useState(null);
  const [isHumanControlling, setIsHumanControlling] = useState(false);

  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const durationRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const transcriptEndRef = useRef(null);

  // Auto-scroll transcript
  useEffect(() => {
    if (transcriptEndRef.current) {
      transcriptEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  // Cleanup on unmount
  const endCall = useCallback(() => {
    // Close WebSocket
    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'end' }));
        }
        wsRef.current.close();
      } catch (e) { /* ignore */ }
      wsRef.current = null;
    }

    // Stop STT
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) { /* ignore */ }
      recognitionRef.current = null;
    }

    // Stop audio
    audioQueueRef.current = [];
    if (audioContextRef.current) {
      try { audioContextRef.current.close(); } catch (e) { /* ignore */ }
      audioContextRef.current = null;
    }

    // Stop timer
    if (durationRef.current) {
      clearInterval(durationRef.current);
      durationRef.current = null;
    }

    setIsCallActive(false);
    setIsListening(false);
    setIsSpeaking(false);
    isPlayingRef.current = false;
  }, []);

  useEffect(() => {
    return () => {
      endCall();
    };
  }, [endCall]);

  /* ─── AUDIO PLAYBACK (Server TTS) ─── */
  const initAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContextRef.current;
  };

  const playAudioChunk = useCallback(async (base64Audio) => {
    if (!isSpeakerOn) return;

    try {
      const ctx = initAudioContext();
      if (ctx.state === 'suspended') await ctx.resume();

      const raw = atob(base64Audio);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

      const audioBuffer = await ctx.decodeAudioData(bytes.buffer);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      source.onended = () => {
        setIsSpeaking(false);
        isPlayingRef.current = false;
        playNextInQueue();
      };

      setIsSpeaking(true);
      isPlayingRef.current = true;
      source.start(0);
    } catch (e) {
      console.error('[V2V] Audio playback error:', e);
      setIsSpeaking(false);
      isPlayingRef.current = false;
    }
  }, [isSpeakerOn]);

  const playNextInQueue = useCallback(() => {
    if (audioQueueRef.current.length > 0 && !isPlayingRef.current) {
      const next = audioQueueRef.current.shift();
      playAudioChunk(next);
    }
  }, [playAudioChunk]);

  const queueAudio = useCallback((base64Audio) => {
    if (isPlayingRef.current) {
      audioQueueRef.current.push(base64Audio);
    } else {
      playAudioChunk(base64Audio);
    }
  }, [playAudioChunk]);

  /* ─── WEBSOCKET CONNECTION ─── */
  const connectWebSocket = useCallback((wsUrl) => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[V2V] WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case 'response_text':
            setTranscript(prev => [...prev, {
              role: 'assistant', text: msg.text, timestamp: new Date().toISOString(), vibe: currentVibe
            }]);
            break;

          case 'audio_chunk':
            if (msg.data) queueAudio(msg.data);
            break;

          case 'transcript':
            if (msg.speaker === 'user') {
              setTranscript(prev => [...prev, {
                role: 'user', text: msg.text, timestamp: new Date().toISOString()
              }]);
            }
            break;

          case 'tone_sync':
            setCurrentVibe(msg.vibe || 'NEUTRAL');
            setCurrentEmotion(msg.emotion || 'neutral');
            setSentimentScore(msg.sentiment_score || 0);
            break;

          case 'panic_triggered':
            setPanicEvent({
              eventId: msg.event_id,
              emotion: msg.emotion,
              keywords: msg.keywords || [],
              action: msg.action,
              message: msg.message,
            });
            setCurrentVibe('PANIC');
            break;

          case 'response_start':
            setIsSpeaking(true);
            break;

          case 'response_end':
            setIsListening(true);
            break;

          case 'interrupted':
            audioQueueRef.current = [];
            setIsSpeaking(false);
            break;

          case 'error':
            console.error('[V2V] Server error:', msg.message);
            setError(msg.message || 'Voice error');
            break;

          case 'stt_empty':
            // STT returned no result — reset to listening
            setIsSpeaking(false);
            setIsListening(true);
            break;

          default:
            break;
        }
      } catch (e) {
        console.error('[V2V] Message parse error:', e);
      }
    };

    ws.onerror = (e) => {
      console.error('[V2V] WebSocket error:', e);
      setError('Voice connection error. Please try again.');
    };

    ws.onclose = () => {
      console.log('[V2V] WebSocket closed');
    };

    return ws;
  }, [queueAudio, currentVibe]);

  /* ─── BROWSER STT (Web Speech API) ─── */
  const startBrowserSTT = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError('Speech recognition not supported. Use Chrome or Edge.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-CA';
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      // Show interim results as live subtitle
      let interimText = '';
      let finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript.trim() + ' ';
        } else {
          interimText += result[0].transcript;
        }
      }

      // Update live subtitle for interim results
      if (interimText) {
        setTranscript(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'interim') {
            last.text = interimText;
          } else {
            updated.push({ role: 'interim', text: interimText });
          }
          return updated;
        });
      }

      if (finalText.trim() && wsRef.current?.readyState === WebSocket.OPEN) {
        setIsListening(false);
        // Remove interim entry and send final text
        setTranscript(prev => prev.filter(t => t.role !== 'interim'));
        wsRef.current.send(JSON.stringify({ type: 'text', text: finalText.trim(), source: 'voice' }));
      }
    };

    recognition.onerror = (event) => {
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        console.error('[STT] Error:', event.error);
      }
    };

    recognition.onend = () => {
      // Auto-restart if call is active and not muted
      if (wsRef.current?.readyState === WebSocket.OPEN && !isMuted) {
        try { recognition.start(); } catch (e) { /* already started */ }
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [isMuted]);

  /* ─── CALL LIFECYCLE ─── */
  const startCall = async () => {
    setIsConnecting(true);
    setError(null);
    setTranscript([]);
    setPanicEvent(null);
    setIsHumanControlling(false);
    setCurrentVibe('NEUTRAL');

    try {
      const response = await fetch(`${API_URL}/api/voice/web-call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setIsConnecting(false);
        return;
      }

      setCallId(data.call_id);

      // Build WebSocket URL from API_URL (backend returns internal K8s hostname)
      const origin = API_URL.replace('https://', 'wss://').replace('http://', 'ws://');
      const wsUrl = `${origin}/api/voice/stream?call_id=${data.call_id}&token=${data.session_token}`;

      connectWebSocket(wsUrl);
      startBrowserSTT();

      setIsCallActive(true);
      setIsConnecting(false);

      // Start duration timer
      setCallDuration(0);
      durationRef.current = setInterval(() => {
        setCallDuration(prev => prev + 1);
      }, 1000);

    } catch (err) {
      console.error('[V2V] Call start error:', err);
      setError('Failed to start voice call. Please try again.');
      setIsConnecting(false);
    }
  };

  const toggleMute = () => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);
    if (recognitionRef.current) {
      if (newMuted) {
        try { recognitionRef.current.stop(); } catch (e) { /* ignore */ }
      } else {
        try { recognitionRef.current.start(); } catch (e) { /* ignore */ }
      }
    }
  };

  const toggleSpeaker = () => {
    const newState = !isSpeakerOn;
    setIsSpeakerOn(newState);
    if (!newState) {
      audioQueueRef.current = [];
    }
  };

  const sendInterrupt = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
      audioQueueRef.current = [];
      setIsSpeaking(false);
    }
  };

  /* ─── PANIC OVERRIDE ACTIONS ─── */
  const handleTakeControl = async () => {
    if (!callId) return;
    try {
      const res = await fetch(`${API_URL}/api/panic/takeover/${callId}?tenant_id=aurem_platform`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setIsHumanControlling(true);
        // Pause STT
        if (recognitionRef.current) {
          try { recognitionRef.current.stop(); } catch (e) { /* ignore */ }
        }
      }
    } catch (e) {
      console.error('[Panic] Take control error:', e);
    }
  };

  const handleResumeAI = async () => {
    if (!callId) return;
    try {
      const res = await fetch(`${API_URL}/api/panic/resume/${callId}?tenant_id=aurem_platform`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setIsHumanControlling(false);
        setPanicEvent(null);
        setCurrentVibe('NEUTRAL');
        // Resume STT
        if (recognitionRef.current) {
          try { recognitionRef.current.start(); } catch (e) { /* ignore */ }
        }
      }
    } catch (e) {
      console.error('[Panic] Resume AI error:', e);
    }
  };

  const formatDuration = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  /* ─── RENDER ─── */
  return (
    <div data-testid="aurem-voice" className="flex flex-col h-full" style={{ background: '#0A0A0A', borderRadius: 16 }}>
      {/* Header */}
      <div className="flex items-center justify-between p-4" style={{ borderBottom: '1px solid rgba(212,163,115,0.08)' }}>
        <div className="flex items-center gap-3">
          <div
            className="size-10 rounded-full flex items-center justify-center"
            style={{ background: isCallActive ? 'rgba(74,222,128,0.12)' : 'rgba(212,163,115,0.08)' }}
          >
            <Phone className={`size-5 ${isCallActive ? 'text-green-400' : 'text-[#D4A373]'}`} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#E8E4DE]">AUREM V2V Engine</h3>
            <p className="text-xs text-[#9A9590]">
              {isCallActive ? `Live — ${formatDuration(callDuration)}` : 'WebSocket + Whisper + GPT-4o + TTS'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Live Vibe Badge */}
          {isCallActive && (
            <VibeBadge vibe={currentVibe} emotion={currentEmotion} score={sentimentScore} />
          )}
          {onClose && (
            <button onClick={onClose} data-testid="close-voice-btn"
              className="text-[#9A9590] hover:text-[#E8E4DE] ml-2 text-lg"
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
              &times;
            </button>
          )}
        </div>
      </div>

      {/* Panic Override Panel */}
      <PanicOverridePanel
        panicEvent={panicEvent}
        onTakeControl={handleTakeControl}
        onResumeAI={handleResumeAI}
        isHumanControlling={isHumanControlling}
      />

      {/* Visualization */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-4">
        <VoiceVisualizer isActive={isCallActive} isSpeaking={isSpeaking} vibe={currentVibe} />

        <p className="text-sm text-[#9A9590] mt-3" data-testid="voice-status">
          {isConnecting ? 'Connecting to AUREM V2V...' :
           isHumanControlling ? 'Manual Override Active — AI Paused' :
           isListening ? 'Listening...' :
           isSpeaking ? 'AUREM is speaking...' :
           isCallActive ? 'Processing...' :
           'Press Start to begin voice call'}
        </p>

        {error && (
          <div className="mt-3 p-2.5 rounded-lg flex items-center gap-2"
            style={{ background: 'rgba(220,38,38,0.10)', border: '1px solid rgba(220,38,38,0.25)' }}>
            <AlertCircle className="size-4 text-red-400 flex-shrink-0" />
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}
      </div>

      {/* Transcript */}
      {transcript.length > 0 && (
        <div
          data-testid="voice-transcript"
          className="max-h-36 overflow-y-auto px-4 pb-2 space-y-1"
          style={{ borderTop: '1px solid rgba(212,163,115,0.06)' }}
        >
          {transcript.map((msg, i) => (
            <div key={i} className={`flex items-start gap-2 text-xs py-0.5 ${msg.role === 'interim' ? 'opacity-50' : ''}`}>
              <span className={`font-bold flex-shrink-0 ${
                msg.role === 'user' ? 'text-[#68DA8D]' : 
                msg.role === 'interim' ? 'text-[#68DA8D]/50' : 'text-[#D4A373]'
              }`}>
                {msg.role === 'interim' ? 'You' : msg.role === 'user' ? 'You' : 'AUREM'}:
              </span>
              <span className={msg.role === 'interim' ? 'text-[#C0BAB2]/50 italic' : 'text-[#C0BAB2]'}>{msg.text}</span>
              {msg.vibe && msg.vibe !== 'NEUTRAL' && (
                <span
                  className="flex-shrink-0 text-[9px] px-1.5 py-0.5 rounded-full"
                  style={{ background: VIBE_CONFIG[msg.vibe]?.bg, color: VIBE_CONFIG[msg.vibe]?.color }}
                >
                  {msg.vibe}
                </span>
              )}
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-center gap-4 p-4" style={{ borderTop: '1px solid rgba(212,163,115,0.08)' }}>
        {!isCallActive ? (
          <button
            onClick={startCall}
            disabled={isConnecting}
            data-testid="start-call-btn"
            className="px-6 py-3 rounded-full font-bold text-sm flex items-center gap-2 transition-all disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #4CAF50, #2E7D32)', color: '#fff', border: 'none', cursor: isConnecting ? 'wait' : 'pointer' }}
          >
            {isConnecting ? (
              <><Loader2 className="size-4 animate-spin" /> Connecting…</>
            ) : (
              <><Phone className="size-4" /> Start V2V Call</>
            )}
          </button>
        ) : (
          <>
            <button onClick={toggleMute} data-testid="mute-btn"
              className="size-11 rounded-full flex items-center justify-center transition-all"
              style={{ background: isMuted ? 'rgba(220,38,38,0.15)' : 'rgba(255,255,255,0.05)', border: '1px solid rgba(212,163,115,0.12)', cursor: 'pointer' }}>
              {isMuted ? <MicOff className="size-4 text-red-400" /> : <Mic className="size-4 text-[#E8E4DE]" />}
            </button>

            {/* Barge-in / Interrupt */}
            {isSpeaking && (
              <button onClick={sendInterrupt} data-testid="interrupt-btn"
                className="size-11 rounded-full flex items-center justify-center transition-all animate-pulse"
                style={{ background: 'rgba(251,191,36,0.15)', border: '1px solid rgba(251,191,36,0.3)', cursor: 'pointer' }}
                title="Interrupt AI">
                <ShieldAlert className="size-4 text-amber-400" />
              </button>
            )}

            <button onClick={endCall} data-testid="end-call-btn"
              className="size-14 rounded-full flex items-center justify-center transition-all"
              style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', border: 'none', cursor: 'pointer' }}>
              <PhoneOff className="size-5 text-white" />
            </button>

            <button onClick={toggleSpeaker} data-testid="speaker-btn"
              className="size-11 rounded-full flex items-center justify-center transition-all"
              style={{ background: !isSpeakerOn ? 'rgba(220,38,38,0.15)' : 'rgba(255,255,255,0.05)', border: '1px solid rgba(212,163,115,0.12)', cursor: 'pointer' }}>
              {isSpeakerOn ? <Volume2 className="size-4 text-[#E8E4DE]" /> : <VolumeX className="size-4 text-red-400" />}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default AuremVoice;
