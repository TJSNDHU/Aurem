/**
 * ReRoots AI Hybrid Voice Consultant
 * Primary: Voxtral TTS (Mistral AI Studio) - 90ms latency
 * Fallback: Web Speech API (offline/no-signal)
 * 
 * Features:
 * - Cloned brand voice via Voxtral
 * - Real-time streaming TTS
 * - Offline fallback with Web Speech
 * - Voice command recognition
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Loader2, Sparkles, Radio, Wifi, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

// Voice Configuration
const VOXTRAL_VOICE_ID = 'reroots-consultant'; // Custom cloned voice
const VOXTRAL_MODEL = 'voxtral-v1'; // Mistral AI TTS model

// Web Speech fallback voices
const FALLBACK_VOICES = {
  'en-CA': 'Google UK English Female',
  'en-US': 'Samantha',
  'en-GB': 'Daniel'
};

/**
 * HybridVoiceConsultant - AI Voice Advisor Component
 */
export function HybridVoiceConsultant({ 
  onSpeakStart, 
  onSpeakEnd, 
  onTranscript,
  apiUrl,
  voxtralApiKey 
}) {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [voxtralAvailable, setVoxtralAvailable] = useState(true);
  const [currentText, setCurrentText] = useState('');
  const [transcript, setTranscript] = useState('');
  const [visualizerLevel, setVisualizerLevel] = useState(0);

  const recognitionRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const speechSynthRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);

  // Monitor online status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Initialize Speech Recognition
  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-CA';

      recognitionRef.current.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        setTranscript(finalTranscript || interimTranscript);
        
        if (finalTranscript && onTranscript) {
          onTranscript(finalTranscript);
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error('[Voice] Recognition error:', event.error);
        setIsListening(false);
        
        if (event.error === 'no-speech') {
          toast.info('No speech detected. Try again.');
        } else if (event.error === 'not-allowed') {
          toast.error('Microphone access denied');
        }
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, [onTranscript]);

  // Initialize Audio Context for visualizer
  const initAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
    }
    return audioContextRef.current;
  }, []);

  // Voxtral TTS - Primary
  const speakWithVoxtral = useCallback(async (text) => {
    if (!voxtralApiKey || !isOnline) {
      return false;
    }

    try {
      const response = await fetch(`${apiUrl}/api/pwa/voice/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text,
          voice_id: VOXTRAL_VOICE_ID,
          model: VOXTRAL_MODEL,
          streaming: true
        })
      });

      if (!response.ok) {
        throw new Error('Voxtral TTS failed');
      }

      // Stream audio response
      const audioData = await response.arrayBuffer();
      const audioContext = initAudioContext();
      const audioBuffer = await audioContext.decodeAudioData(audioData);
      
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(analyserRef.current);
      analyserRef.current.connect(audioContext.destination);
      
      source.onended = () => {
        setIsSpeaking(false);
        setVisualizerLevel(0);
        if (onSpeakEnd) onSpeakEnd();
      };

      source.start();
      setIsSpeaking(true);
      if (onSpeakStart) onSpeakStart();
      
      // Animate visualizer
      const updateVisualizer = () => {
        if (!isSpeaking) return;
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setVisualizerLevel(average / 255);
        requestAnimationFrame(updateVisualizer);
      };
      updateVisualizer();

      return true;
    } catch (error) {
      console.error('[Voice] Voxtral TTS error:', error);
      setVoxtralAvailable(false);
      return false;
    }
  }, [apiUrl, voxtralApiKey, isOnline, initAudioContext, isSpeaking, onSpeakStart, onSpeakEnd]);

  // Web Speech API - Fallback
  const speakWithWebSpeech = useCallback((text) => {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window)) {
        resolve(false);
        return;
      }

      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-CA';
      utterance.rate = 0.95;
      utterance.pitch = 1.05;

      // Try to find a good voice
      const voices = window.speechSynthesis.getVoices();
      const preferredVoice = voices.find(v => 
        v.name.includes('Samantha') || 
        v.name.includes('Google') ||
        v.name.includes('Premium') ||
        v.lang.startsWith('en')
      );
      
      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      utterance.onstart = () => {
        setIsSpeaking(true);
        if (onSpeakStart) onSpeakStart();
        
        // Simple visualizer for Web Speech
        const visualizerInterval = setInterval(() => {
          if (!speechSynthRef.current?.speaking) {
            clearInterval(visualizerInterval);
            return;
          }
          setVisualizerLevel(0.3 + Math.random() * 0.4);
        }, 100);
      };

      utterance.onend = () => {
        setIsSpeaking(false);
        setVisualizerLevel(0);
        if (onSpeakEnd) onSpeakEnd();
        resolve(true);
      };

      utterance.onerror = (e) => {
        console.error('[Voice] Web Speech error:', e);
        setIsSpeaking(false);
        resolve(false);
      };

      speechSynthRef.current = window.speechSynthesis;
      window.speechSynthesis.speak(utterance);
    });
  }, [onSpeakStart, onSpeakEnd]);

  // Hybrid Speak - Tries Voxtral first, falls back to Web Speech
  const speak = useCallback(async (text) => {
    if (!text || isSpeaking) return;
    
    setIsLoading(true);
    setCurrentText(text);

    try {
      // Try Voxtral first (if online and available)
      if (isOnline && voxtralAvailable && voxtralApiKey) {
        const success = await speakWithVoxtral(text);
        if (success) {
          setIsLoading(false);
          return;
        }
      }

      // Fallback to Web Speech
      console.log('[Voice] Using Web Speech fallback');
      await speakWithWebSpeech(text);
    } finally {
      setIsLoading(false);
    }
  }, [isSpeaking, isOnline, voxtralAvailable, voxtralApiKey, speakWithVoxtral, speakWithWebSpeech]);

  // Stop speaking
  const stopSpeaking = useCallback(() => {
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    
    setIsSpeaking(false);
    setVisualizerLevel(0);
    if (onSpeakEnd) onSpeakEnd();
  }, [onSpeakEnd]);

  // Toggle listening
  const toggleListening = useCallback(() => {
    if (!recognitionRef.current) {
      toast.error('Speech recognition not supported');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setTranscript('');
      recognitionRef.current.start();
      setIsListening(true);
    }
  }, [isListening]);

  return (
    <div className="flex flex-col items-center">
      {/* Status Badge */}
      <div className="flex items-center gap-2 mb-4 text-xs">
        <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${
          isOnline ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
        }`}>
          {isOnline ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          <span>{isOnline ? 'Online' : 'Offline'}</span>
        </div>
        
        {isOnline && (
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${
            voxtralAvailable ? 'bg-amber-500/20 text-amber-400' : 'bg-white/10 text-white/40'
          }`}>
            <Radio className="w-3 h-3" />
            <span>{voxtralAvailable ? 'Voxtral' : 'Web Speech'}</span>
          </div>
        )}
      </div>

      {/* Voice Visualizer Orb */}
      <div className="relative w-48 h-48 mb-6">
        {/* Glow effect */}
        <div 
          className="absolute inset-0 rounded-full blur-3xl transition-all duration-150"
          style={{
            background: `radial-gradient(circle, rgba(245, 158, 11, ${0.2 + visualizerLevel * 0.4}) 0%, transparent 70%)`,
            transform: `scale(${1 + visualizerLevel * 0.3})`
          }}
        />
        
        {/* Outer ring */}
        <div 
          className="absolute inset-0 rounded-full border-2 border-amber-500/30 transition-all duration-150"
          style={{
            transform: `scale(${1 + visualizerLevel * 0.1})`
          }}
        />
        
        {/* Middle ring */}
        <div 
          className="absolute inset-4 rounded-full border border-amber-500/20 transition-all duration-150"
          style={{
            transform: `scale(${1 + visualizerLevel * 0.15})`
          }}
        />
        
        {/* Core orb */}
        <div 
          className="absolute inset-8 rounded-full bg-gradient-to-br from-amber-500/80 to-amber-600/80 flex items-center justify-center transition-all duration-150 shadow-lg shadow-amber-500/30"
          style={{
            transform: `scale(${1 + visualizerLevel * 0.2})`
          }}
        >
          {isLoading ? (
            <Loader2 className="w-12 h-12 text-white animate-spin" />
          ) : isSpeaking ? (
            <Volume2 className="w-12 h-12 text-white animate-pulse" />
          ) : isListening ? (
            <Mic className="w-12 h-12 text-white animate-pulse" />
          ) : (
            <Sparkles className="w-12 h-12 text-white" />
          )}
        </div>
      </div>

      {/* Current text being spoken */}
      {currentText && isSpeaking && (
        <div className="mb-4 px-4 py-2 bg-white/5 rounded-lg max-w-xs text-center">
          <p className="text-white/80 text-sm line-clamp-2">{currentText}</p>
        </div>
      )}

      {/* Transcript */}
      {transcript && isListening && (
        <div className="mb-4 px-4 py-2 bg-amber-500/10 rounded-lg max-w-xs text-center">
          <p className="text-amber-400 text-sm">{transcript}</p>
        </div>
      )}

      {/* Control Buttons */}
      <div className="flex items-center gap-4">
        {/* Mic Button */}
        <Button
          onClick={toggleListening}
          disabled={isSpeaking}
          className={`w-14 h-14 rounded-full transition-all ${
            isListening
              ? 'bg-red-500 hover:bg-red-600 animate-pulse'
              : 'bg-white/10 hover:bg-white/20'
          }`}
        >
          {isListening ? (
            <MicOff className="w-6 h-6 text-white" />
          ) : (
            <Mic className="w-6 h-6 text-white" />
          )}
        </Button>

        {/* Stop Button (when speaking) */}
        {isSpeaking && (
          <Button
            onClick={stopSpeaking}
            className="w-14 h-14 rounded-full bg-white/10 hover:bg-white/20"
          >
            <VolumeX className="w-6 h-6 text-white" />
          </Button>
        )}
      </div>

      {/* Instructions */}
      <p className="mt-4 text-white/40 text-xs text-center max-w-xs">
        {isListening 
          ? 'Listening... Speak clearly'
          : isSpeaking
            ? 'Playing audio...'
            : 'Tap the mic to ask your AI consultant'
        }
      </p>
    </div>
  );
}

/**
 * useVoiceConsultant - Hook for voice functionality
 */
export function useVoiceConsultant(apiUrl) {
  const [voxtralApiKey, setVoxtralApiKey] = useState(null);
  
  // Fetch Voxtral API key on mount
  useEffect(() => {
    const fetchKey = async () => {
      try {
        const response = await fetch(`${apiUrl}/api/pwa/voice/config`);
        if (response.ok) {
          const data = await response.json();
          setVoxtralApiKey(data.voxtral_key);
        }
      } catch (error) {
        console.log('[Voice] Config fetch failed, using Web Speech');
      }
    };
    
    if (apiUrl) {
      fetchKey();
    }
  }, [apiUrl]);

  return { voxtralApiKey };
}

export default HybridVoiceConsultant;
