/**
 * useVoice — browser-native Speech Recognition (STT) + Speech Synthesis (TTS).
 *
 * Zero API keys, zero backend cost. Uses the Web Speech API supported in
 * all evergreen browsers (Chrome, Edge, Safari).
 *
 * Usage:
 *   const { isListening, transcript, startListening, stopListening,
 *           isSpeaking, speak, stopSpeaking, supported } = useVoice();
 *
 *   startListening('en-IN')      → starts mic, calls onResult when done
 *   speak("Hello there", 'en')   → speaks the text out loud
 */
import { useCallback, useEffect, useRef, useState } from "react";

function _getRecognition() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export default function useVoice({ onResult } = {}) {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState("");
  const recogRef = useRef(null);

  const SR = _getRecognition();
  const supportedSTT = !!SR;
  const supportedTTS =
    typeof window !== "undefined" && "speechSynthesis" in window;

  const startListening = useCallback(
    (lang = "en-IN") => {
      if (!SR) {
        setError("Speech recognition not supported in this browser");
        return;
      }
      setError("");
      setTranscript("");
      const r = new SR();
      r.lang = lang;
      r.interimResults = true;
      r.continuous = false;
      r.onresult = (e) => {
        const text = Array.from(e.results)
          .map((res) => res[0].transcript)
          .join("");
        setTranscript(text);
        if (e.results[e.results.length - 1].isFinal) {
          if (onResult) onResult(text);
        }
      };
      r.onerror = (e) => {
        setError(e.error || "recognition error");
        setIsListening(false);
      };
      r.onend = () => setIsListening(false);
      r.start();
      recogRef.current = r;
      setIsListening(true);
    },
    [SR, onResult]
  );

  const stopListening = useCallback(() => {
    if (recogRef.current) {
      try {
        recogRef.current.stop();
      } catch (e) {
        // ignore
      }
    }
    setIsListening(false);
  }, []);

  const speak = useCallback(
    (text, { lang = "en-IN", rate = 1.0, pitch = 1.0 } = {}) => {
      if (!supportedTTS || !text) return;
      try {
        window.speechSynthesis.cancel(); // stop anything in flight
        const u = new SpeechSynthesisUtterance(String(text));
        u.lang = lang;
        u.rate = rate;
        u.pitch = pitch;
        u.onstart = () => setIsSpeaking(true);
        u.onend = () => setIsSpeaking(false);
        u.onerror = () => setIsSpeaking(false);
        window.speechSynthesis.speak(u);
      } catch (e) {
        setIsSpeaking(false);
      }
    },
    [supportedTTS]
  );

  const stopSpeaking = useCallback(() => {
    if (!supportedTTS) return;
    try {
      window.speechSynthesis.cancel();
    } catch (e) {
      // ignore
    }
    setIsSpeaking(false);
  }, [supportedTTS]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recogRef.current) {
        try { recogRef.current.stop(); } catch (e) { /* noop */ }
      }
      if (supportedTTS) {
        try { window.speechSynthesis.cancel(); } catch (e) { /* noop */ }
      }
    };
  }, [supportedTTS]);

  return {
    isListening,
    isSpeaking,
    transcript,
    error,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    supported: supportedSTT && supportedTTS,
    supportedSTT,
    supportedTTS,
  };
}
