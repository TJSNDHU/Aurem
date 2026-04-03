/**
 * React Hooks for Voice Services
 * useVoiceInput - Speech recognition hook
 * useVoiceOutput - Text-to-speech hook
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { getVoiceRecognition, getTextToSpeech, SUPPORTED_LANGUAGES } from '../services/voiceService';

// ═══════════════════════════════════════════════════════════════════════════════
// useVoiceInput - Speech Recognition Hook
// ═══════════════════════════════════════════════════════════════════════════════

export const useVoiceInput = (options = {}) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState(null);
  const [isSupported, setIsSupported] = useState(false);
  const [language, setLanguageState] = useState(options.language || 'en-US');
  
  const recognitionRef = useRef(null);
  const onResultCallback = useRef(options.onResult);
  
  // Update callback ref
  useEffect(() => {
    onResultCallback.current = options.onResult;
  }, [options.onResult]);
  
  // Initialize
  useEffect(() => {
    const recognition = getVoiceRecognition();
    recognitionRef.current = recognition;
    setIsSupported(recognition.isSupported());
    
    if (recognition.isSupported()) {
      recognition.setLanguage(language);
      
      recognition.onResult = (result) => {
        if (result.isFinal) {
          setTranscript(result.transcript);
          setInterimTranscript('');
          if (onResultCallback.current) {
            onResultCallback.current(result.transcript, result);
          }
        } else {
          setInterimTranscript(result.transcript);
        }
      };
      
      recognition.onError = (err) => {
        setError(err);
        setIsListening(false);
      };
      
      recognition.onStart = () => {
        setIsListening(true);
        setError(null);
      };
      
      recognition.onEnd = () => {
        setIsListening(false);
      };
    }
    
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);
  
  // Update language
  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.setLanguage(language);
    }
  }, [language]);
  
  const startListening = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
    setError(null);
    if (recognitionRef.current) {
      recognitionRef.current.start();
    }
  }, []);
  
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);
  
  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);
  
  const setLanguage = useCallback((langCode) => {
    setLanguageState(langCode);
  }, []);
  
  const clearTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
  }, []);
  
  return {
    isListening,
    transcript,
    interimTranscript,
    error,
    isSupported,
    language,
    startListening,
    stopListening,
    toggleListening,
    setLanguage,
    clearTranscript,
    languages: SUPPORTED_LANGUAGES
  };
};


// ═══════════════════════════════════════════════════════════════════════════════
// useVoiceOutput - Text-to-Speech Hook
// ═══════════════════════════════════════════════════════════════════════════════

export const useVoiceOutput = (options = {}) => {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState([]);
  const [currentVoice, setCurrentVoice] = useState(null);
  const [language, setLanguageState] = useState(options.language || 'en-US');
  const [isSupported, setIsSupported] = useState(false);
  const [error, setError] = useState(null);
  
  const ttsRef = useRef(null);
  
  // Initialize
  useEffect(() => {
    const tts = getTextToSpeech();
    ttsRef.current = tts;
    setIsSupported(tts.isSupported());
    
    if (tts.isSupported()) {
      // Load voices (may be async)
      const loadVoices = () => {
        const availableVoices = tts.getVoices();
        setVoices(availableVoices);
        if (tts.voice) {
          setCurrentVoice(tts.voice.name);
        }
      };
      
      loadVoices();
      
      // Voices may load asynchronously
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = loadVoices;
      }
      
      tts.onStart = () => {
        setIsSpeaking(true);
        setIsPaused(false);
      };
      
      tts.onEnd = () => {
        setIsSpeaking(false);
        setIsPaused(false);
      };
      
      tts.onError = (err) => {
        setError(err);
        setIsSpeaking(false);
      };
    }
    
    return () => {
      if (ttsRef.current) {
        ttsRef.current.stop();
      }
    };
  }, []);
  
  // Update language
  useEffect(() => {
    if (ttsRef.current) {
      ttsRef.current.setLanguage(language);
    }
  }, [language]);
  
  const speak = useCallback((text, speakOptions = {}) => {
    setError(null);
    if (ttsRef.current) {
      return ttsRef.current.speak(text, {
        language,
        ...speakOptions
      });
    }
    return false;
  }, [language]);
  
  const stop = useCallback(() => {
    if (ttsRef.current) {
      ttsRef.current.stop();
    }
  }, []);
  
  const pause = useCallback(() => {
    if (ttsRef.current) {
      ttsRef.current.pause();
      setIsPaused(true);
    }
  }, []);
  
  const resume = useCallback(() => {
    if (ttsRef.current) {
      ttsRef.current.resume();
      setIsPaused(false);
    }
  }, []);
  
  const setLanguage = useCallback((langCode) => {
    setLanguageState(langCode);
  }, []);
  
  const setVoice = useCallback((voiceName) => {
    if (ttsRef.current) {
      ttsRef.current.setVoice(voiceName);
      setCurrentVoice(voiceName);
    }
  }, []);
  
  const setRate = useCallback((rate) => {
    if (ttsRef.current) {
      ttsRef.current.setRate(rate);
    }
  }, []);
  
  const getVoicesForLanguage = useCallback((langCode) => {
    if (ttsRef.current) {
      return ttsRef.current.getVoicesForLanguage(langCode);
    }
    return [];
  }, []);
  
  return {
    isSpeaking,
    isPaused,
    voices,
    currentVoice,
    language,
    isSupported,
    error,
    speak,
    stop,
    pause,
    resume,
    setLanguage,
    setVoice,
    setRate,
    getVoicesForLanguage,
    languages: SUPPORTED_LANGUAGES
  };
};


// ═══════════════════════════════════════════════════════════════════════════════
// useVoiceChat - Combined hook for voice-enabled chat
// ═══════════════════════════════════════════════════════════════════════════════

export const useVoiceChat = (options = {}) => {
  const { onSendMessage, autoSpeak = true } = options;
  
  const voice = useVoiceInput({
    language: options.language,
    onResult: (transcript) => {
      if (onSendMessage && transcript.trim()) {
        onSendMessage(transcript);
      }
    }
  });
  
  const speaker = useVoiceOutput({
    language: options.language
  });
  
  // Speak AI response
  const speakResponse = useCallback((text) => {
    if (autoSpeak && speaker.isSupported) {
      speaker.speak(text);
    }
  }, [autoSpeak, speaker]);
  
  // Set language for both
  const setLanguage = useCallback((langCode) => {
    voice.setLanguage(langCode);
    speaker.setLanguage(langCode);
  }, [voice, speaker]);
  
  return {
    // Voice input
    isListening: voice.isListening,
    transcript: voice.transcript,
    interimTranscript: voice.interimTranscript,
    startListening: voice.startListening,
    stopListening: voice.stopListening,
    toggleListening: voice.toggleListening,
    voiceInputSupported: voice.isSupported,
    
    // Voice output
    isSpeaking: speaker.isSpeaking,
    speak: speaker.speak,
    speakResponse,
    stopSpeaking: speaker.stop,
    voiceOutputSupported: speaker.isSupported,
    
    // Shared
    language: voice.language,
    setLanguage,
    languages: SUPPORTED_LANGUAGES,
    
    // Errors
    inputError: voice.error,
    outputError: speaker.error
  };
};

export default {
  useVoiceInput,
  useVoiceOutput,
  useVoiceChat
};
