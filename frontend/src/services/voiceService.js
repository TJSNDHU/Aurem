/**
 * Voice Service - Speech Recognition & Text-to-Speech
 * Uses FREE Web Speech API (browser native)
 * Supports 100+ languages automatically
 */

// ═══════════════════════════════════════════════════════════════════════════════
// SPEECH RECOGNITION (Voice Input)
// ═══════════════════════════════════════════════════════════════════════════════

class VoiceRecognitionService {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.language = 'en-US';
    this.onResult = null;
    this.onError = null;
    this.onStart = null;
    this.onEnd = null;
    
    this.initialize();
  }
  
  initialize() {
    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      console.warn('[Voice] Speech Recognition not supported in this browser');
      return false;
    }
    
    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.maxAlternatives = 1;
    this.recognition.lang = this.language;
    
    // Event handlers
    this.recognition.onresult = (event) => {
      const last = event.results.length - 1;
      const transcript = event.results[last][0].transcript;
      const isFinal = event.results[last].isFinal;
      const confidence = event.results[last][0].confidence;
      
      if (this.onResult) {
        this.onResult({
          transcript,
          isFinal,
          confidence,
          language: this.language
        });
      }
    };
    
    this.recognition.onerror = (event) => {
      console.error('[Voice] Recognition error:', event.error);
      this.isListening = false;
      if (this.onError) {
        this.onError(event.error);
      }
    };
    
    this.recognition.onstart = () => {
      this.isListening = true;
      if (this.onStart) this.onStart();
    };
    
    this.recognition.onend = () => {
      this.isListening = false;
      if (this.onEnd) this.onEnd();
    };
    
    return true;
  }
  
  setLanguage(langCode) {
    this.language = langCode;
    if (this.recognition) {
      this.recognition.lang = langCode;
    }
  }
  
  start() {
    if (!this.recognition) {
      console.error('[Voice] Recognition not initialized');
      return false;
    }
    
    if (this.isListening) {
      this.stop();
    }
    
    try {
      this.recognition.start();
      return true;
    } catch (e) {
      console.error('[Voice] Start error:', e);
      return false;
    }
  }
  
  stop() {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
    }
  }
  
  isSupported() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
// TEXT-TO-SPEECH (Voice Output)
// ═══════════════════════════════════════════════════════════════════════════════

class TextToSpeechService {
  constructor() {
    this.synth = window.speechSynthesis;
    this.voice = null;
    this.voices = [];
    this.language = 'en-US';
    this.rate = 1.0;
    this.pitch = 1.0;
    this.volume = 1.0;
    this.isSpeaking = false;
    this.onStart = null;
    this.onEnd = null;
    this.onError = null;
    
    this.loadVoices();
  }
  
  loadVoices() {
    // Voices load asynchronously
    const loadVoiceList = () => {
      this.voices = this.synth.getVoices();
      // Try to find a good default voice
      this.voice = this.voices.find(v => v.lang.startsWith('en') && v.name.includes('Google')) 
                || this.voices.find(v => v.lang.startsWith('en'))
                || this.voices[0];
    };
    
    loadVoiceList();
    
    if (this.synth.onvoiceschanged !== undefined) {
      this.synth.onvoiceschanged = loadVoiceList;
    }
  }
  
  getVoices() {
    return this.voices;
  }
  
  getVoicesForLanguage(langCode) {
    const prefix = langCode.split('-')[0];
    return this.voices.filter(v => v.lang.startsWith(prefix));
  }
  
  setLanguage(langCode) {
    this.language = langCode;
    // Find best voice for this language
    const langVoices = this.getVoicesForLanguage(langCode);
    if (langVoices.length > 0) {
      // Prefer Google voices, then female, then first available
      this.voice = langVoices.find(v => v.name.includes('Google'))
                || langVoices.find(v => v.name.includes('Female'))
                || langVoices[0];
    }
  }
  
  setVoice(voiceName) {
    const voice = this.voices.find(v => v.name === voiceName);
    if (voice) {
      this.voice = voice;
    }
  }
  
  setRate(rate) {
    this.rate = Math.max(0.5, Math.min(2, rate));
  }
  
  setPitch(pitch) {
    this.pitch = Math.max(0, Math.min(2, pitch));
  }
  
  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume));
  }
  
  speak(text, options = {}) {
    if (!this.synth) {
      console.error('[Voice] Speech synthesis not supported');
      return false;
    }
    
    // Cancel any ongoing speech
    this.stop();
    
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Apply settings
    utterance.voice = options.voice || this.voice;
    utterance.lang = options.language || this.language;
    utterance.rate = options.rate || this.rate;
    utterance.pitch = options.pitch || this.pitch;
    utterance.volume = options.volume || this.volume;
    
    // Event handlers
    utterance.onstart = () => {
      this.isSpeaking = true;
      if (this.onStart) this.onStart();
    };
    
    utterance.onend = () => {
      this.isSpeaking = false;
      if (this.onEnd) this.onEnd();
    };
    
    utterance.onerror = (event) => {
      this.isSpeaking = false;
      console.error('[Voice] Speech error:', event.error);
      if (this.onError) this.onError(event.error);
    };
    
    this.synth.speak(utterance);
    return true;
  }
  
  stop() {
    if (this.synth) {
      this.synth.cancel();
      this.isSpeaking = false;
    }
  }
  
  pause() {
    if (this.synth) {
      this.synth.pause();
    }
  }
  
  resume() {
    if (this.synth) {
      this.synth.resume();
    }
  }
  
  isSupported() {
    return 'speechSynthesis' in window;
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
// SUPPORTED LANGUAGES
// ═══════════════════════════════════════════════════════════════════════════════

const SUPPORTED_LANGUAGES = [
  { code: 'en-US', name: 'English (US)', flag: '🇺🇸' },
  { code: 'en-GB', name: 'English (UK)', flag: '🇬🇧' },
  { code: 'en-CA', name: 'English (Canada)', flag: '🇨🇦' },
  { code: 'fr-FR', name: 'French', flag: '🇫🇷' },
  { code: 'fr-CA', name: 'French (Canada)', flag: '🇨🇦' },
  { code: 'es-ES', name: 'Spanish', flag: '🇪🇸' },
  { code: 'de-DE', name: 'German', flag: '🇩🇪' },
  { code: 'it-IT', name: 'Italian', flag: '🇮🇹' },
  { code: 'pt-BR', name: 'Portuguese (Brazil)', flag: '🇧🇷' },
  { code: 'zh-CN', name: 'Chinese (Mandarin)', flag: '🇨🇳' },
  { code: 'ja-JP', name: 'Japanese', flag: '🇯🇵' },
  { code: 'ko-KR', name: 'Korean', flag: '🇰🇷' },
  { code: 'hi-IN', name: 'Hindi', flag: '🇮🇳' },
  { code: 'ar-SA', name: 'Arabic', flag: '🇸🇦' },
  { code: 'ru-RU', name: 'Russian', flag: '🇷🇺' },
  { code: 'nl-NL', name: 'Dutch', flag: '🇳🇱' },
  { code: 'sv-SE', name: 'Swedish', flag: '🇸🇪' },
  { code: 'pl-PL', name: 'Polish', flag: '🇵🇱' },
  { code: 'tr-TR', name: 'Turkish', flag: '🇹🇷' },
  { code: 'vi-VN', name: 'Vietnamese', flag: '🇻🇳' },
];


// ═══════════════════════════════════════════════════════════════════════════════
// SINGLETON INSTANCES
// ═══════════════════════════════════════════════════════════════════════════════

let recognitionInstance = null;
let ttsInstance = null;

export const getVoiceRecognition = () => {
  if (!recognitionInstance) {
    recognitionInstance = new VoiceRecognitionService();
  }
  return recognitionInstance;
};

export const getTextToSpeech = () => {
  if (!ttsInstance) {
    ttsInstance = new TextToSpeechService();
  }
  return ttsInstance;
};

export { 
  VoiceRecognitionService, 
  TextToSpeechService, 
  SUPPORTED_LANGUAGES 
};

export default {
  getVoiceRecognition,
  getTextToSpeech,
  SUPPORTED_LANGUAGES
};
