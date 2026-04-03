import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import axios from 'axios';
import { Bot, X, Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

// Lazy-loaded motion components wrapper
const MotionDiv = React.lazy(() => import('framer-motion').then(mod => ({ default: mod.motion.div })));

const VoiceAIChat = ({ onClose }) => {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle"); // idle, listening, processing, speaking
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef(null);
  const synthRef = useRef(window.speechSynthesis);
  const messagesEndRef = useRef(null);

  // System prompt for AI
  const systemPrompt = `You are Alex, a friendly and helpful AI customer support agent for ReRoots, a premium biotech skincare e-commerce store based in Canada. Your role is to:
- Answer questions about ReRoots products (PDRN serums, skincare, etc.)
- Help with order status inquiries
- Explain return and refund policies
- Provide skincare advice
- Be warm, professional, and concise
- Keep responses under 2-3 sentences for voice conversations
- If you don't know something, offer to connect them with email support at support@reroots.ca`;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const speak = (text) => {
    if (!synthRef.current) return;
    
    synthRef.current.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    // Try to find a nice voice
    const voices = synthRef.current.getVoices();
    const preferredVoice = voices.find(v => 
      v.name.includes('Samantha') || 
      v.name.includes('Google') || 
      v.name.includes('Female') ||
      v.lang.startsWith('en')
    );
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => {
      setIsSpeaking(true);
      setStatus("speaking");
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      setStatus("idle");
    };

    synthRef.current.speak(utterance);
  };

  const handleUserMessage = async (userText) => {
    if (!userText.trim()) return;

    const userMsg = { role: "user", content: userText, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setTranscript("");
    setStatus("processing");

    try {
      // Use existing chat API endpoint
      const response = await axios.post(`${API}/api/chat/voice`, {
        message: userText,
        system_prompt: systemPrompt,
        conversation_history: messages.slice(-6).map(m => ({
          role: m.role,
          content: m.content
        }))
      });

      const aiResponse = response.data.response;
      const aiMsg = { role: "assistant", content: aiResponse, id: Date.now() + 1 };
      setMessages(prev => [...prev, aiMsg]);
      speak(aiResponse);
    } catch (error) {
      console.error("AI response error:", error);
      const errorMsg = "I'm having trouble connecting. Please try again or email us at support@reroots.ca";
      setMessages(prev => [...prev, { role: "assistant", content: errorMsg, id: Date.now() + 1 }]);
      speak(errorMsg);
    }
  };

  // Initialize speech recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        const current = event.resultIndex;
        const result = event.results[current];
        const transcriptText = result[0].transcript;
        setTranscript(transcriptText);
        
        if (result.isFinal) {
          handleUserMessage(transcriptText);
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        setStatus("idle");
        setIsListening(false);
        if (event.error === 'not-allowed') {
          toast.error("Microphone access denied. Please enable microphone permissions.");
        }
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
        if (status === "listening") {
          setStatus("idle");
        }
      };
    }

    // Add initial greeting
    const greeting = "Hi! I'm Alex, your ReRoots AI assistant. How can I help you today?";
    setMessages([{ role: "assistant", content: greeting, id: Date.now() }]);
    speak(greeting);

    const currentRecognition = recognitionRef.current;
    const currentSynth = synthRef.current;
    
    return () => {
      if (currentRecognition) {
        currentRecognition.stop();
      }
      currentSynth.cancel();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startListening = () => {
    if (!recognitionRef.current) {
      toast.error("Speech recognition not supported in your browser. Try Chrome.");
      return;
    }
    
    synthRef.current.cancel(); // Stop any ongoing speech
    setTranscript("");
    setStatus("listening");
    setIsListening(true);
    
    try {
      recognitionRef.current.start();
    } catch (e) {
      console.error("Recognition start error:", e);
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setIsListening(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <React.Suspense fallback={<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center">Loading...</div>}>
        <MotionDiv
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-[#F8A5B8] to-[#E991A5] p-4 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-bold">AI Voice Support</h3>
                  <p className="text-xs text-white/80">Speak naturally, I&apos;ll respond</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 hover:bg-white/20 rounded-full transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="h-64 overflow-y-auto p-4 bg-gray-50">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`mb-3 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                    msg.role === "user"
                      ? "bg-[#F8A5B8] text-white rounded-br-md"
                      : "bg-white shadow-sm border rounded-bl-md"
                  }`}
                >
                  <p className="text-sm">{msg.content}</p>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Status & Controls */}
          <div className="p-4 border-t bg-white">
            {/* Live Transcript */}
            {transcript && (
              <div className="mb-3 p-2 bg-gray-100 rounded-lg">
                <p className="text-sm text-gray-600 italic">&ldquo;{transcript}&rdquo;</p>
              </div>
            )}

            {/* Status Indicator */}
            <div className="flex items-center justify-center mb-4">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${
                status === "listening" ? "bg-red-100 text-red-600" :
                status === "processing" ? "bg-yellow-100 text-yellow-600" :
                status === "speaking" ? "bg-green-100 text-green-600" :
                "bg-gray-100 text-gray-600"
              }`}>
                {status === "listening" && (
                  <>
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                      <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse delay-75"></span>
                      <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse delay-150"></span>
                    </div>
                    <span className="text-sm font-medium">Listening...</span>
                  </>
                )}
                {status === "processing" && (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm font-medium">Thinking...</span>
                  </>
                )}
                {status === "speaking" && (
                  <>
                    <div className="flex gap-1 items-end">
                      <span className="w-1 h-3 bg-green-500 rounded-full animate-pulse"></span>
                      <span className="w-1 h-4 bg-green-500 rounded-full animate-pulse delay-75"></span>
                      <span className="w-1 h-2 bg-green-500 rounded-full animate-pulse delay-150"></span>
                    </div>
                    <span className="text-sm font-medium">Speaking...</span>
                  </>
                )}
                {status === "idle" && (
                  <span className="text-sm">Tap microphone to speak</span>
                )}
              </div>
            </div>

            {/* Microphone Button */}
            <div className="flex justify-center">
              <button
                onClick={isListening ? stopListening : startListening}
                disabled={status === "processing" || status === "speaking"}
                className={`w-16 h-16 rounded-full flex items-center justify-center transition-all transform hover:scale-105 ${
                  isListening 
                    ? "bg-red-500 animate-pulse" 
                    : status === "processing" || status === "speaking"
                    ? "bg-gray-300 cursor-not-allowed"
                    : "bg-[#F8A5B8] hover:bg-[#E991A5]"
                }`}
              >
                {isListening ? (
                  <div className="w-6 h-6 bg-white rounded-sm"></div>
                ) : (
                  <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 1.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-4.07z"/>
                  </svg>
                )}
              </button>
            </div>

            <p className="text-center text-xs text-gray-500 mt-3">
              {isListening ? "Click to stop" : "Click to speak"}
            </p>
          </div>
        </MotionDiv>
      </React.Suspense>
    </div>
  );
};

export default VoiceAIChat;
