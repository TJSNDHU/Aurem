/**
 * AUREM Voice Interface
 * Real voice-to-voice conversation using Vapi
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, MicOff, Phone, PhoneOff, Volume2, VolumeX, Loader2, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Voice visualization component
const VoiceVisualizer = ({ isActive, isSpeaking }) => {
  const bars = 12;
  
  return (
    <div className="flex items-center justify-center gap-1 h-16">
      {[...Array(bars)].map((_, i) => (
        <div
          key={i}
          className={`w-1 rounded-full transition-all duration-150 ${
            isActive 
              ? isSpeaking 
                ? 'bg-[#D4AF37]' 
                : 'bg-[#4A4]'
              : 'bg-[#333]'
          }`}
          style={{
            height: isActive 
              ? `${Math.random() * 100}%` 
              : '20%',
            animationDelay: `${i * 50}ms`
          }}
        />
      ))}
    </div>
  );
};

const AuremVoice = ({ token, onClose }) => {
  const [isCallActive, setIsCallActive] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeakerOn, setIsSpeakerOn] = useState(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [error, setError] = useState(null);
  const [voiceConfig, setVoiceConfig] = useState(null);
  const [callDuration, setCallDuration] = useState(0);
  
  const vapiRef = useRef(null);
  const durationRef = useRef(null);

  // Fetch voice configuration
  useEffect(() => {
    fetchVoiceConfig();
    return () => {
      if (durationRef.current) clearInterval(durationRef.current);
      endCall();
    };
  }, []);

  const fetchVoiceConfig = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/voice/config`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setVoiceConfig(data);
      
      if (!data.available) {
        setError('Voice service requires Vapi API key configuration');
      }
    } catch (err) {
      setError('Failed to load voice configuration');
    }
  };

  const startCall = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      // Get call configuration from backend
      const response = await fetch(`${API_URL}/api/aurem/voice/web-call`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setIsConnecting(false);
        return;
      }

      // Initialize Vapi if SDK is loaded
      if (window.Vapi && data.vapi_key) {
        const vapi = new window.Vapi(data.vapi_key);
        vapiRef.current = vapi;

        // Set up event handlers
        vapi.on('call-start', () => {
          setIsCallActive(true);
          setIsConnecting(false);
          startDurationTimer();
        });

        vapi.on('call-end', () => {
          setIsCallActive(false);
          stopDurationTimer();
        });

        vapi.on('speech-start', () => {
          setIsSpeaking(true);
          setIsListening(false);
        });

        vapi.on('speech-end', () => {
          setIsSpeaking(false);
        });

        vapi.on('user-speech-start', () => {
          setIsListening(true);
          setIsSpeaking(false);
        });

        vapi.on('user-speech-end', () => {
          setIsListening(false);
        });

        vapi.on('message', (message) => {
          if (message.type === 'transcript') {
            setTranscript(prev => [...prev, {
              role: message.role,
              text: message.transcript,
              timestamp: new Date().toISOString()
            }]);
          }
        });

        vapi.on('error', (error) => {
          console.error('Vapi error:', error);
          setError('Voice connection error');
          setIsCallActive(false);
          setIsConnecting(false);
        });

        // Start the call with assistant config
        await vapi.start(data.assistant_config);

      } else {
        // Fallback: Use browser speech recognition + synthesis
        startBrowserVoice();
      }

    } catch (err) {
      console.error('Call start error:', err);
      setError('Failed to start voice call');
      setIsConnecting(false);
    }
  };

  const startBrowserVoice = () => {
    // Fallback using Web Speech API
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setError('Voice not supported in this browser');
      setIsConnecting(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsCallActive(true);
      setIsConnecting(false);
      setIsListening(true);
      startDurationTimer();
    };

    recognition.onresult = async (event) => {
      const last = event.results.length - 1;
      const transcript = event.results[last][0].transcript;
      
      if (event.results[last].isFinal) {
        setTranscript(prev => [...prev, { role: 'user', text: transcript }]);
        
        // Send to AUREM AI and get response
        try {
          const response = await fetch(`${API_URL}/api/aurem/chat`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: transcript })
          });
          
          const data = await response.json();
          
          if (data.response) {
            setTranscript(prev => [...prev, { role: 'assistant', text: data.response }]);
            
            // Speak the response
            if (isSpeakerOn && 'speechSynthesis' in window) {
              setIsSpeaking(true);
              const utterance = new SpeechSynthesisUtterance(data.response);
              utterance.rate = 1;
              utterance.pitch = 1;
              utterance.onend = () => setIsSpeaking(false);
              window.speechSynthesis.speak(utterance);
            }
          }
        } catch (err) {
          console.error('Chat error:', err);
        }
      }
    };

    recognition.onerror = (event) => {
      if (event.error !== 'no-speech') {
        setError(`Speech recognition error: ${event.error}`);
      }
    };

    recognition.onend = () => {
      if (isCallActive) {
        recognition.start(); // Restart for continuous listening
      }
    };

    vapiRef.current = recognition;
    recognition.start();
  };

  const endCall = async () => {
    try {
      if (vapiRef.current) {
        if (vapiRef.current.stop) {
          vapiRef.current.stop();
        } else if (vapiRef.current.abort) {
          vapiRef.current.abort();
        }
        vapiRef.current = null;
      }
      
      window.speechSynthesis?.cancel();
      
      setIsCallActive(false);
      setIsSpeaking(false);
      setIsListening(false);
      stopDurationTimer();
      
    } catch (err) {
      console.error('End call error:', err);
    }
  };

  const toggleMute = () => {
    setIsMuted(!isMuted);
    // Implement actual mute logic based on Vapi or Web Speech API
  };

  const toggleSpeaker = () => {
    setIsSpeakerOn(!isSpeakerOn);
    if (!isSpeakerOn) {
      window.speechSynthesis?.cancel();
    }
  };

  const startDurationTimer = () => {
    durationRef.current = setInterval(() => {
      setCallDuration(prev => prev + 1);
    }, 1000);
  };

  const stopDurationTimer = () => {
    if (durationRef.current) {
      clearInterval(durationRef.current);
      durationRef.current = null;
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#050505]/95 backdrop-blur-lg flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-[#0A0A0A] border border-[#1A1A1A] rounded-2xl overflow-hidden">
        {/* Header */}
        <div className="p-6 text-center border-b border-[#1A1A1A]">
          <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center mb-4">
            {isConnecting ? (
              <Loader2 className="w-10 h-10 text-[#050505] animate-spin" />
            ) : isCallActive ? (
              <div className="relative">
                <Phone className="w-10 h-10 text-[#050505]" />
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-[#4A4] rounded-full animate-pulse" />
              </div>
            ) : (
              <Mic className="w-10 h-10 text-[#050505]" />
            )}
          </div>
          <h2 className="text-xl font-medium text-[#F4F4F4]">
            {isConnecting ? 'Connecting...' : isCallActive ? 'AUREM Voice' : 'Voice Mode'}
          </h2>
          {isCallActive && (
            <p className="text-sm text-[#D4AF37] mt-1">{formatDuration(callDuration)}</p>
          )}
          <p className="text-sm text-[#666] mt-2">
            {isCallActive 
              ? isSpeaking 
                ? 'AUREM is speaking...' 
                : isListening 
                  ? 'Listening...' 
                  : 'Speak to AUREM'
              : 'Start a voice conversation'
            }
          </p>
        </div>

        {/* Visualizer */}
        <div className="p-6 bg-[#050505]">
          <VoiceVisualizer isActive={isCallActive} isSpeaking={isSpeaking} />
        </div>

        {/* Error */}
        {error && (
          <div className="mx-6 mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="mx-6 mb-4 max-h-40 overflow-y-auto space-y-2">
            {transcript.slice(-4).map((item, idx) => (
              <div 
                key={idx} 
                className={`text-xs p-2 rounded ${
                  item.role === 'user' 
                    ? 'bg-[#1A1A1A] text-[#AAA]' 
                    : 'bg-[#D4AF37]/10 text-[#D4AF37]'
                }`}
              >
                <span className="font-medium">{item.role === 'user' ? 'You' : 'AUREM'}:</span> {item.text}
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
        <div className="p-6 border-t border-[#1A1A1A]">
          <div className="flex items-center justify-center gap-4">
            {isCallActive && (
              <>
                <button
                  onClick={toggleMute}
                  className={`p-4 rounded-full border transition-all ${
                    isMuted 
                      ? 'bg-red-500/20 border-red-500/50 text-red-400' 
                      : 'border-[#333] text-[#888] hover:text-[#F4F4F4]'
                  }`}
                >
                  {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
                </button>
                
                <button
                  onClick={toggleSpeaker}
                  className={`p-4 rounded-full border transition-all ${
                    !isSpeakerOn 
                      ? 'bg-red-500/20 border-red-500/50 text-red-400' 
                      : 'border-[#333] text-[#888] hover:text-[#F4F4F4]'
                  }`}
                >
                  {isSpeakerOn ? <Volume2 className="w-6 h-6" /> : <VolumeX className="w-6 h-6" />}
                </button>
              </>
            )}
            
            <button
              onClick={isCallActive ? endCall : startCall}
              disabled={isConnecting}
              className={`p-5 rounded-full transition-all ${
                isCallActive 
                  ? 'bg-red-500 hover:bg-red-600' 
                  : 'bg-gradient-to-br from-[#D4AF37] to-[#8B7355] hover:opacity-90'
              } disabled:opacity-50`}
            >
              {isConnecting ? (
                <Loader2 className="w-8 h-8 text-[#050505] animate-spin" />
              ) : isCallActive ? (
                <PhoneOff className="w-8 h-8 text-white" />
              ) : (
                <Phone className="w-8 h-8 text-[#050505]" />
              )}
            </button>
          </div>
        </div>

        {/* Close button */}
        <div className="p-4 border-t border-[#1A1A1A]">
          <button
            onClick={onClose}
            className="w-full py-2 text-sm text-[#666] hover:text-[#AAA] transition-colors"
          >
            {isCallActive ? 'Hide (call continues)' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AuremVoice;
