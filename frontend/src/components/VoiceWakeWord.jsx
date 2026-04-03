/**
 * AUREM Voice Wake-Word Interface
 * "Hi Aurem" - Conversational Command System
 * Premium UX Layer
 */

import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Volume2, Zap, Activity } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const VoiceWakeWord = ({ token, businessId = "ABC-001" }) => {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const [wakeWordActive, setWakeWordActive] = useState(false);
  
  const recognitionRef = useRef(null);
  const synthRef = useRef(null);

  useEffect(() => {
    // Initialize Web Speech API
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        const current = event.resultIndex;
        const transcriptText = event.results[current][0].transcript;
        
        setTranscript(transcriptText);

        // Check for wake word "Hi Ora"
        if (transcriptText.toLowerCase().includes('hi ora') || 
            transcriptText.toLowerCase().includes('hey ora')) {
          setWakeWordActive(true);
          
          // Process command after wake word
          const command = transcriptText.toLowerCase().replace(/hi ora|hey ora/gi, '').trim();
          if (command.length > 3) {
            processCommand(command);
          }
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'no-speech') {
          // Restart listening
          setTimeout(startListening, 1000);
        }
      };

      recognitionRef.current.onend = () => {
        if (listening) {
          // Auto-restart if still in listening mode
          recognitionRef.current.start();
        }
      };
    }

    // Initialize Speech Synthesis
    synthRef.current = window.speechSynthesis;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, [listening]);

  const startListening = () => {
    if (recognitionRef.current) {
      setListening(true);
      setWakeWordActive(false);
      recognitionRef.current.start();
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      setListening(false);
      recognitionRef.current.stop();
    }
  };

  const processCommand = async (command) => {
    try {
      const response = await fetch(`${API_URL}/api/voice/command`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          transcript: command,
          business_id: businessId
        })
      });

      const data = await response.json();
      setResponse(data);

      // Speak response
      if (data.response_text) {
        speak(data.response_text);
      }

      // Navigate UI if specified
      if (data.ui_navigation && window.location.pathname !== data.ui_navigation) {
        setTimeout(() => {
          // TODO: Integrate with React Router navigation
          console.log('Navigate to:', data.ui_navigation);
        }, 1000);
      }

      // Reset wake word after processing
      setTimeout(() => setWakeWordActive(false), 3000);

    } catch (error) {
      console.error('Command processing error:', error);
      speak("Sorry, I couldn't process that command.");
    }
  };

  const speak = (text) => {
    if (synthRef.current) {
      // Cancel any ongoing speech
      synthRef.current.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => setSpeaking(false);

      synthRef.current.speak(utterance);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      zIndex: 9999
    }}>
      {/* Main Voice Button */}
      <button
        onClick={listening ? stopListening : startListening}
        style={{
          width: 64,
          height: 64,
          borderRadius: '50%',
          background: listening 
            ? 'linear-gradient(135deg, #FF4444 0%, #CC0000 100%)'
            : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 20px rgba(212, 175, 55, 0.4)',
          transition: 'all 0.3s',
          position: 'relative'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.1)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1)';
        }}
      >
        {listening ? (
          <Mic className="w-8 h-8 text-white" />
        ) : (
          <MicOff className="w-8 h-8 text-[#050505]" />
        )}

        {/* Listening pulse */}
        {listening && (
          <div style={{
            position: 'absolute',
            width: '100%',
            height: '100%',
            borderRadius: '50%',
            background: 'rgba(255, 68, 68, 0.3)',
            animation: 'pulse 2s infinite'
          }} />
        )}

        {/* Wake word indicator */}
        {wakeWordActive && (
          <div style={{
            position: 'absolute',
            top: -4,
            right: -4,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: '#4CAF50',
            border: '2px solid #0A0A0A',
            animation: 'ping 1s infinite'
          }} />
        )}
      </button>

      {/* Status Panel */}
      {(listening || response) && (
        <div style={{
          position: 'absolute',
          bottom: 80,
          right: 0,
          width: 320,
          background: '#0A0A0A',
          border: '1px solid #1A1A1A',
          borderRadius: 12,
          padding: 16,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8)'
        }}>
          {/* Transcript */}
          {listening && (
            <div style={{marginBottom: 12}}>
              <div style={{
                fontSize: 11,
                color: '#888',
                textTransform: 'uppercase',
                marginBottom: 4,
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}>
                <Activity className="w-3 h-3" />
                Listening...
              </div>
              <div style={{
                fontSize: 14,
                color: wakeWordActive ? '#4CAF50' : '#F4F4F4',
                fontWeight: wakeWordActive ? 600 : 400
              }}>
                {transcript || 'Say "Hi Ora" to activate...'}
              </div>
            </div>
          )}

          {/* Response */}
          {response && (
            <div>
              <div style={{
                fontSize: 11,
                color: '#888',
                textTransform: 'uppercase',
                marginBottom: 4,
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}>
                {speaking ? (
                  <>
                    <Volume2 className="w-3 h-3 animate-pulse" />
                    Speaking...
                  </>
                ) : (
                  <>
                    <Zap className="w-3 h-3" />
                    Response
                  </>
                )}
              </div>
              <div style={{
                fontSize: 14,
                color: '#F4F4F4',
                lineHeight: 1.5
              }}>
                {response.response_text}
              </div>

              {/* Command indicator */}
              {response.command && (
                <div style={{
                  marginTop: 8,
                  padding: '4px 8px',
                  background: '#1A3A1A',
                  border: '1px solid #2A5A2A',
                  borderRadius: 6,
                  fontSize: 11,
                  color: '#4A4',
                  textTransform: 'uppercase'
                }}>
                  Command: {response.command}
                </div>
              )}
            </div>
          )}

          {/* Instructions */}
          {listening && !transcript && (
            <div style={{
              marginTop: 12,
              padding: 12,
              background: '#050505',
              borderRadius: 8,
              border: '1px solid #1A1A1A'
            }}>
              <div style={{fontSize: 11, color: '#888', marginBottom: 8}}>
                Try saying:
              </div>
              <div style={{fontSize: 12, color: '#666', lineHeight: 1.6}}>
                • "Hi Ora, what's the revenue today?"<br />
                • "Hi Ora, show me the leads"<br />
                • "Hi Ora, sync the system"<br />
                • "Hi Ora, recover those carts"
              </div>
            </div>
          )}
        </div>
      )}

      {/* CSS Animations */}
      <style jsx>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0.5;
            transform: scale(1.1);
          }
        }

        @keyframes ping {
          0% {
            transform: scale(1);
            opacity: 1;
          }
          75%, 100% {
            transform: scale(2);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
};

export default VoiceWakeWord;
;
