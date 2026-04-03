/**
 * VoiceButton Component - Voice Input/Output Controls
 * Drop-in component for voice-enabled features
 */

import React, { useState, useEffect } from 'react';
import { useVoiceInput, useVoiceOutput } from '../hooks/useVoice';
import { SUPPORTED_LANGUAGES } from '../services/voiceService';

// ═══════════════════════════════════════════════════════════════════════════════
// VOICE INPUT BUTTON
// ═══════════════════════════════════════════════════════════════════════════════

export const VoiceMicButton = ({ 
  onResult, 
  onListeningChange,
  language = 'en-US',
  size = 'md',
  className = '',
  showLanguageSelect = false,
  style = {}
}) => {
  const {
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    toggleListening,
    setLanguage,
    error
  } = useVoiceInput({ 
    language,
    onResult: (text) => {
      if (onResult) onResult(text);
    }
  });
  
  useEffect(() => {
    if (onListeningChange) {
      onListeningChange(isListening);
    }
  }, [isListening, onListeningChange]);
  
  useEffect(() => {
    setLanguage(language);
  }, [language, setLanguage]);
  
  if (!isSupported) {
    return null;
  }
  
  const sizeClasses = {
    sm: { button: 'w-8 h-8', icon: 'w-4 h-4' },
    md: { button: 'w-10 h-10', icon: 'w-5 h-5' },
    lg: { button: 'w-12 h-12', icon: 'w-6 h-6' }
  };
  
  const sizes = sizeClasses[size] || sizeClasses.md;
  
  return (
    <div className={`inline-flex items-center gap-2 ${className}`} style={style}>
      <button
        onClick={toggleListening}
        className={`${sizes.button} rounded-full flex items-center justify-center transition-all duration-200 ${
          isListening 
            ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-500/50' 
            : 'bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-800'
        }`}
        title={isListening ? 'Stop listening' : 'Start voice input'}
        type="button"
      >
        {isListening ? (
          // Stop icon
          <svg className={sizes.icon} fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
        ) : (
          // Mic icon
          <svg className={sizes.icon} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" 
            />
          </svg>
        )}
      </button>
      
      {isListening && interimTranscript && (
        <span className="text-sm text-gray-500 italic max-w-[200px] truncate">
          {interimTranscript}
        </span>
      )}
      
      {error && (
        <span className="text-xs text-red-500">{error}</span>
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// VOICE OUTPUT / SPEAKER BUTTON
// ═══════════════════════════════════════════════════════════════════════════════

export const VoiceSpeakerButton = ({
  text,
  language = 'en-US',
  autoPlay = false,
  size = 'md',
  className = '',
  onStart,
  onEnd,
  style = {}
}) => {
  const {
    isSpeaking,
    isSupported,
    speak,
    stop,
    setLanguage
  } = useVoiceOutput({ language });
  
  useEffect(() => {
    setLanguage(language);
  }, [language, setLanguage]);
  
  useEffect(() => {
    if (autoPlay && text && isSupported) {
      speak(text);
    }
  }, [autoPlay, text, isSupported, speak]);
  
  const handleClick = () => {
    if (isSpeaking) {
      stop();
      if (onEnd) onEnd();
    } else if (text) {
      speak(text);
      if (onStart) onStart();
    }
  };
  
  if (!isSupported) {
    return null;
  }
  
  const sizeClasses = {
    sm: { button: 'w-8 h-8', icon: 'w-4 h-4' },
    md: { button: 'w-10 h-10', icon: 'w-5 h-5' },
    lg: { button: 'w-12 h-12', icon: 'w-6 h-6' }
  };
  
  const sizes = sizeClasses[size] || sizeClasses.md;
  
  return (
    <button
      onClick={handleClick}
      disabled={!text}
      className={`${sizes.button} rounded-full flex items-center justify-center transition-all duration-200 ${
        isSpeaking
          ? 'bg-blue-500 text-white animate-pulse'
          : text
            ? 'bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-800'
            : 'bg-gray-50 text-gray-300 cursor-not-allowed'
      } ${className}`}
      title={isSpeaking ? 'Stop speaking' : 'Listen to this'}
      type="button"
      style={style}
    >
      {isSpeaking ? (
        // Stop icon
        <svg className={sizes.icon} fill="currentColor" viewBox="0 0 24 24">
          <rect x="6" y="6" width="12" height="12" rx="1" />
        </svg>
      ) : (
        // Speaker icon
        <svg className={sizes.icon} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
          />
        </svg>
      )}
    </button>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// LANGUAGE SELECTOR
// ═══════════════════════════════════════════════════════════════════════════════

export const LanguageSelector = ({
  value = 'en-US',
  onChange,
  compact = false,
  className = '',
  style = {}
}) => {
  return (
    <select
      value={value}
      onChange={(e) => onChange && onChange(e.target.value)}
      className={`rounded-lg border border-gray-200 bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
        compact ? 'px-2 py-1' : 'px-3 py-2'
      } ${className}`}
      style={style}
    >
      {SUPPORTED_LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {compact ? lang.flag : `${lang.flag} ${lang.name}`}
        </option>
      ))}
    </select>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// VOICE CHAT INPUT - Combined mic + text input
// ═══════════════════════════════════════════════════════════════════════════════

export const VoiceChatInput = ({
  value,
  onChange,
  onSend,
  placeholder = 'Type or speak...',
  language = 'en-US',
  showLanguageSelect = false,
  disabled = false,
  className = '',
  style = {}
}) => {
  const [inputValue, setInputValue] = useState(value || '');
  const [currentLang, setCurrentLang] = useState(language);
  
  const handleVoiceResult = (transcript) => {
    const newValue = inputValue ? `${inputValue} ${transcript}` : transcript;
    setInputValue(newValue);
    if (onChange) onChange(newValue);
  };
  
  const handleInputChange = (e) => {
    setInputValue(e.target.value);
    if (onChange) onChange(e.target.value);
  };
  
  const handleSend = () => {
    if (inputValue.trim() && onSend) {
      onSend(inputValue.trim());
      setInputValue('');
    }
  };
  
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  useEffect(() => {
    if (value !== undefined) {
      setInputValue(value);
    }
  }, [value]);
  
  return (
    <div className={`flex items-center gap-2 ${className}`} style={style}>
      {showLanguageSelect && (
        <LanguageSelector 
          value={currentLang}
          onChange={setCurrentLang}
          compact
        />
      )}
      
      <div className="flex-1 relative">
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full px-4 py-2 pr-12 rounded-full border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        />
        
        <div className="absolute right-1 top-1/2 -translate-y-1/2">
          <VoiceMicButton
            onResult={handleVoiceResult}
            language={currentLang}
            size="sm"
          />
        </div>
      </div>
      
      <button
        onClick={handleSend}
        disabled={!inputValue.trim() || disabled}
        className="w-10 h-10 rounded-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-200 text-white disabled:text-gray-400 flex items-center justify-center transition-colors"
        type="button"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
      </button>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// AI MESSAGE WITH SPEAKER - Message bubble with TTS
// ═══════════════════════════════════════════════════════════════════════════════

export const AIMessageWithSpeaker = ({
  message,
  language = 'en-US',
  autoPlay = false,
  className = '',
  style = {}
}) => {
  return (
    <div className={`flex items-start gap-2 ${className}`} style={style}>
      <div className="flex-1 bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 text-sm">
        {message}
      </div>
      <VoiceSpeakerButton
        text={message}
        language={language}
        autoPlay={autoPlay}
        size="sm"
      />
    </div>
  );
};


export default {
  VoiceMicButton,
  VoiceSpeakerButton,
  LanguageSelector,
  VoiceChatInput,
  AIMessageWithSpeaker
};
