/**
 * ORA AI Interface - JARVIS Style
 * Futuristic 3D particle visualization with voice control
 * Inspired by AI Ad Lab design
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, Volume2, VolumeX, Send, Sparkles } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const ORAJarvis = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const canvasRef = useRef(null);
  const particlesRef = useRef([]);
  const animationRef = useRef(null);
  const recognitionRef = useRef(null);
  const synthRef = useRef(null);

  // Particle system for 3D visualization
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    canvas.width = 600;
    canvas.height = 600;

    // Create particles
    const particleCount = 150;
    const particles = [];

    for (let i = 0; i < particleCount; i++) {
      const angle = (Math.PI * 2 * i) / particleCount;
      const radius = 150 + Math.random() * 80;
      particles.push({
        x: 300 + Math.cos(angle) * radius,
        y: 300 + Math.sin(angle) * radius,
        z: (Math.random() - 0.5) * 200,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        vz: (Math.random() - 0.5) * 0.5,
        originalX: 300 + Math.cos(angle) * radius,
        originalY: 300 + Math.sin(angle) * radius,
        connections: []
      });
    }

    particlesRef.current = particles;

    // Animation loop
    const animate = () => {
      ctx.fillStyle = 'rgba(10, 15, 35, 0.1)';
      ctx.fillRect(0, 0, 600, 600);

      particles.forEach((p, i) => {
        // Gentle floating motion
        p.x += p.vx;
        p.y += p.vy;
        p.z += p.vz;

        // Return to original position gently
        p.vx += (p.originalX - p.x) * 0.001;
        p.vy += (p.originalY - p.y) * 0.001;

        // Bounce off edges
        if (p.x < 50 || p.x > 550) p.vx *= -0.8;
        if (p.y < 50 || p.y > 550) p.vy *= -0.8;

        // Draw particle
        const scale = 1 + p.z / 500;
        const opacity = isThinking ? 1 : 0.6;
        const size = 2 * scale;

        ctx.fillStyle = isThinking 
          ? `rgba(100, 200, 255, ${opacity})`
          : `rgba(212, 175, 55, ${opacity})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
        ctx.fill();

        // Draw connections to nearby particles
        particles.forEach((p2, j) => {
          if (i >= j) return;
          const dx = p2.x - p.x;
          const dy = p2.y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 80) {
            ctx.strokeStyle = isThinking
              ? `rgba(100, 200, 255, ${(1 - dist / 80) * 0.3})`
              : `rgba(212, 175, 55, ${(1 - dist / 80) * 0.2})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        });
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isThinking]);

  // Voice recognition
  const startRecording = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Voice input not supported in this browser. Please use Chrome.');
      return;
    }

    if (isRecording) {
      recognitionRef.current?.stop();
      return;
    }

    recognitionRef.current = new SpeechRecognition();
    recognitionRef.current.continuous = false;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = 'en-US';

    recognitionRef.current.onstart = () => setIsRecording(true);
    recognitionRef.current.onresult = (e) => {
      const transcript = Array.from(e.results)
        .map(r => r[0].transcript)
        .join('');
      setInput(transcript);
    };
    recognitionRef.current.onend = () => setIsRecording(false);
    recognitionRef.current.onerror = () => setIsRecording(false);

    recognitionRef.current.start();
  };

  // Text-to-speech
  const speak = (text) => {
    if (!voiceEnabled) return;

    synthRef.current = window.speechSynthesis;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9;
    utterance.pitch = 1;
    utterance.volume = 1;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);

    synthRef.current.speak(utterance);
  };

  const stopSpeaking = () => {
    synthRef.current?.cancel();
    setIsSpeaking(false);
  };

  // Send message
  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsThinking(true);

    // Simulate AI response
    await new Promise(r => setTimeout(r, 1500 + Math.random() * 1000));

    const response = getAIResponse(input);
    const aiMessage = {
      role: 'assistant',
      content: response,
      timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    };

    setIsThinking(false);
    setMessages(prev => [...prev, aiMessage]);

    // Speak response
    speak(response);
  };

  const getAIResponse = (query) => {
    const responses = {
      automation: "I can help you automate your entire business workflow. AUREM's multi-agent system handles customer communication, sales qualification, inventory management, and analytics—all running 24/7 without human intervention.",
      analytics: "Our real-time analytics engine tracks revenue velocity, customer lifetime value, conversion funnels, and growth opportunities. You receive actionable insights delivered every morning with prioritized recommendations.",
      customer: "AUREM captures, nurtures, and converts customers through intelligent WhatsApp sequences, personalized email flows, and automated purchase triggers. Every interaction is optimized for maximum conversion.",
      default: "I'm ORA, your business intelligence AI. I can help you with automation strategy, customer engagement, revenue analytics, and operational efficiency. What would you like to explore?"
    };

    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes('automat')) return responses.automation;
    if (lowerQuery.includes('analytic') || lowerQuery.includes('data')) return responses.analytics;
    if (lowerQuery.includes('customer') || lowerQuery.includes('lead')) return responses.customer;
    return responses.default;
  };

  return (
    <div style={{
      height: '100vh',
      background: 'linear-gradient(180deg, #0A0F23 0%, #050A1A 100%)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 40px',
        borderBottom: '1px solid rgba(100, 150, 255, 0.1)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Sparkles className="w-8 h-8 text-[#64C8FF]" />
          <div>
            <div style={{ 
              fontSize: 24, 
              fontWeight: 300, 
              letterSpacing: '0.3em', 
              color: '#64C8FF',
              textShadow: '0 0 20px rgba(100, 200, 255, 0.5)'
            }}>
              ORA
            </div>
            <div style={{ 
              fontSize: 10, 
              letterSpacing: '0.2em', 
              color: 'rgba(212, 175, 55, 0.6)',
              marginTop: 2
            }}>
              BUSINESS INTELLIGENCE AI
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {/* Voice Toggle */}
          <button
            onClick={() => {
              setVoiceEnabled(!voiceEnabled);
              if (voiceEnabled) stopSpeaking();
            }}
            style={{
              padding: '10px 20px',
              background: voiceEnabled 
                ? 'linear-gradient(135deg, #64C8FF 0%, #3B82F6 100%)'
                : 'rgba(100, 200, 255, 0.1)',
              border: `1px solid ${voiceEnabled ? '#64C8FF' : 'rgba(100, 200, 255, 0.3)'}`,
              borderRadius: 8,
              color: voiceEnabled ? '#0A0F23' : '#64C8FF',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              letterSpacing: '0.1em',
              transition: 'all 0.3s',
              boxShadow: voiceEnabled ? '0 0 20px rgba(100, 200, 255, 0.3)' : 'none'
            }}
          >
            {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            {voiceEnabled ? 'VOICE ON' : 'VOICE OFF'}
          </button>

          {isSpeaking && (
            <button
              onClick={stopSpeaking}
              style={{
                padding: '8px 16px',
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                borderRadius: 6,
                color: '#ef4444',
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              STOP
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div style={{
        flex: 1,
        display: 'flex',
        overflow: 'hidden'
      }}>
        {/* Left: Visualization */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative'
        }}>
          <canvas
            ref={canvasRef}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              filter: isThinking ? 'brightness(1.2)' : 'brightness(0.9)'
            }}
          />

          {isThinking && (
            <div style={{
              position: 'absolute',
              bottom: 60,
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '12px 24px',
              background: 'rgba(100, 200, 255, 0.1)',
              border: '1px solid rgba(100, 200, 255, 0.3)',
              borderRadius: 8,
              color: '#64C8FF',
              fontSize: 14,
              letterSpacing: '0.15em',
              animation: 'pulse 1.5s infinite'
            }}>
              ● THINKING...
            </div>
          )}

          {messages.length === 0 && !isThinking && (
            <div style={{
              position: 'absolute',
              textAlign: 'center',
              color: 'rgba(212, 175, 55, 0.6)',
              fontSize: 14,
              letterSpacing: '0.1em',
              lineHeight: 1.8
            }}>
              <div style={{ fontSize: 18, marginBottom: 12, color: '#64C8FF' }}>
                READY FOR COMMANDS
              </div>
              <div style={{ fontSize: 11 }}>
                Click the microphone or type to begin
              </div>
            </div>
          )}
        </div>

        {/* Right: Chat History (if any messages) */}
        {messages.length > 0 && (
          <div style={{
            width: 400,
            borderLeft: '1px solid rgba(100, 150, 255, 0.1)',
            display: 'flex',
            flexDirection: 'column',
            background: 'rgba(10, 15, 35, 0.5)'
          }}>
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: 16
            }}>
              {messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%'
                  }}
                >
                  <div style={{
                    padding: '12px 16px',
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, rgba(212, 175, 55, 0.2), rgba(212, 175, 55, 0.1))'
                      : 'linear-gradient(135deg, rgba(100, 200, 255, 0.15), rgba(100, 200, 255, 0.05))',
                    border: `1px solid ${msg.role === 'user' 
                      ? 'rgba(212, 175, 55, 0.3)'
                      : 'rgba(100, 200, 255, 0.2)'}`,
                    borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                    color: '#F4F4F4',
                    fontSize: 13,
                    lineHeight: 1.6
                  }}>
                    {msg.content}
                  </div>
                  <div style={{
                    fontSize: 9,
                    color: 'rgba(255, 255, 255, 0.3)',
                    marginTop: 4,
                    textAlign: msg.role === 'user' ? 'right' : 'left',
                    letterSpacing: '0.05em'
                  }}>
                    {msg.timestamp} · {msg.role === 'user' ? 'YOU' : 'ORA'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input Bar */}
      <div style={{
        padding: '20px 40px',
        borderTop: '1px solid rgba(100, 150, 255, 0.1)',
        background: 'rgba(10, 15, 35, 0.8)',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          padding: '12px 20px',
          background: 'rgba(100, 200, 255, 0.05)',
          border: '1px solid rgba(100, 200, 255, 0.2)',
          borderRadius: 12
        }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder={isRecording ? "🎤 Listening..." : "Ask ORA anything..."}
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: '#F4F4F4',
              fontSize: 14,
              letterSpacing: '0.02em'
            }}
          />

          {/* Microphone */}
          <button
            onClick={startRecording}
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: isRecording
                ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
                : 'linear-gradient(135deg, rgba(100, 200, 255, 0.2), rgba(100, 200, 255, 0.1))',
              border: `2px solid ${isRecording ? '#ef4444' : 'rgba(100, 200, 255, 0.4)'}`,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.3s',
              boxShadow: isRecording ? '0 0 25px rgba(239, 68, 68, 0.5)' : '0 0 15px rgba(100, 200, 255, 0.2)'
            }}
          >
            <Mic className={`w-5 h-5 ${isRecording ? 'text-white' : 'text-[#64C8FF]'}`} />
          </button>

          {/* Send */}
          <button
            onClick={sendMessage}
            disabled={!input.trim()}
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: input.trim()
                ? 'linear-gradient(135deg, #64C8FF 0%, #3B82F6 100%)'
                : 'rgba(100, 200, 255, 0.1)',
              border: '1px solid rgba(100, 200, 255, 0.3)',
              cursor: input.trim() ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.3s',
              opacity: input.trim() ? 1 : 0.5
            }}
          >
            <Send className={`w-5 h-5 ${input.trim() ? 'text-[#0A0F23]' : 'text-[#64C8FF]'}`} />
          </button>
        </div>

        <div style={{
          fontSize: 10,
          color: 'rgba(100, 200, 255, 0.4)',
          textAlign: 'center',
          marginTop: 12,
          letterSpacing: '0.1em'
        }}>
          PRESS ENTER TO SEND • CLICK MIC TO SPEAK • TOGGLE VOICE FOR RESPONSES
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
};

export default ORAJarvis;
