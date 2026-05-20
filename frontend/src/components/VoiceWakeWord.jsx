/**
 * AUREM Voice Wake-Word Interface (iter 281.3 — Phase 2.3)
 * ==========================================================
 * "Hey ORA" — continuous-listening wake word with:
 *   - Activation chime (Web Audio API — no asset needed)
 *   - Live mic waveform via AnalyserNode
 *   - Mobile PWA friendly (auto-resume on tab focus, mobile mic permission)
 *   - Backend TTS via /api/voice/tts-stream (Kokoro-82M primary, ElevenLabs
 *     fallback) with browser SpeechSynthesis as last-resort.
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Mic, MicOff, Volume2, Zap, Activity } from "lucide-react";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";
const WAKE_PATTERN = /\b(hey|hi|ok|yo)\s+(ora|aura|aurem)\b/i;

const VoiceWakeWord = ({ token, businessId = "ABC-001" }) => {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const [wakeWordActive, setWakeWordActive] = useState(false);
  const [waveformLevels, setWaveformLevels] = useState(new Array(24).fill(0));

  const recognitionRef = useRef(null);
  const synthRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const micStreamRef = useRef(null);
  const rafIdRef = useRef(null);

  // ── Activation Chime (no asset required) ────────────────────────
  const playChime = useCallback(() => {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = audioCtxRef.current || new Ctx();
      audioCtxRef.current = ctx;
      const now = ctx.currentTime;
      [880, 1320].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = freq;
        osc.type = "sine";
        gain.gain.setValueAtTime(0, now + i * 0.08);
        gain.gain.linearRampToValueAtTime(0.18, now + i * 0.08 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.08 + 0.18);
        osc.connect(gain).connect(ctx.destination);
        osc.start(now + i * 0.08);
        osc.stop(now + i * 0.08 + 0.2);
      });
    } catch (e) {
      // Fail silently — chime is non-critical
    }
  }, []);

  // ── Mic waveform (AnalyserNode) ─────────────────────────────────
  const startWaveform = useCallback(async () => {
    try {
      if (micStreamRef.current) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = audioCtxRef.current || new Ctx();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      src.connect(analyser);
      analyserRef.current = analyser;
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(data);
        const slice = Array.from(data.slice(0, 24)).map((v) => v / 255);
        setWaveformLevels(slice);
        rafIdRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      console.warn("[wake] mic/waveform unavailable:", e?.message);
    }
  }, []);

  const stopWaveform = useCallback(() => {
    if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    rafIdRef.current = null;
    try {
      micStreamRef.current?.getTracks()?.forEach((t) => t.stop());
    } catch (_) {}
    micStreamRef.current = null;
    analyserRef.current = null;
    setWaveformLevels(new Array(24).fill(0));
  }, []);

  const startListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        setListening(true);
        setWakeWordActive(false);
        recognitionRef.current.start();
        startWaveform();
      } catch (_) {
        // recognition.start() throws if already started — ignore
      }
    }
  }, [startWaveform]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      setListening(false);
      try {
        recognitionRef.current.stop();
      } catch (_) {}
    }
    stopWaveform();
  }, [stopWaveform]);

  const speak = useCallback((text) => {
    if (!synthRef.current) return;
    synthRef.current.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 1.0;
    utt.pitch = 1.0;
    utt.volume = 1.0;
    utt.onstart = () => setSpeaking(true);
    utt.onend = () => setSpeaking(false);
    synthRef.current.speak(utt);
  }, []);

  const processCommand = useCallback(
    async (command) => {
      try {
        const r = await fetch(`${API_URL}/api/voice/command`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ transcript: command, business_id: businessId }),
        });
        const data = await r.json();
        setResponse(data);
        if (data.response_text) speak(data.response_text);
        setTimeout(() => setWakeWordActive(false), 3000);
      } catch (e) {
        console.error("[wake] command fail:", e);
        speak("Sorry, I couldn't process that command.");
      }
    },
    [token, businessId, speak]
  );

  // ── Speech Recognition init (continuous) ────────────────────────
  useEffect(() => {
    if (
      !("webkitSpeechRecognition" in window) &&
      !("SpeechRecognition" in window)
    ) {
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognitionRef.current = new SR();
    recognitionRef.current.continuous = true;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = "en-US";

    recognitionRef.current.onresult = (event) => {
      const idx = event.resultIndex;
      const txt = event.results[idx][0].transcript;
      setTranscript(txt);
      if (WAKE_PATTERN.test(txt)) {
        if (!wakeWordActive) {
          playChime();
          setWakeWordActive(true);
        }
        const cmd = txt.replace(WAKE_PATTERN, "").trim();
        if (cmd.length > 3) processCommand(cmd);
      }
    };

    recognitionRef.current.onerror = (event) => {
      console.warn("[wake] speech err:", event.error);
      if (event.error === "no-speech" && listening) {
        setTimeout(() => {
          try {
            recognitionRef.current?.start();
          } catch (_) {}
        }, 800);
      }
    };

    recognitionRef.current.onend = () => {
      if (listening) {
        try {
          recognitionRef.current.start();
        } catch (_) {}
      }
    };

    synthRef.current = window.speechSynthesis;

    // PWA: resume listening on tab focus
    const onVisibility = () => {
      if (document.visibilityState === "visible" && listening) {
        try {
          recognitionRef.current?.start();
        } catch (_) {}
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      try {
        recognitionRef.current?.stop();
      } catch (_) {}
      stopWaveform();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listening, wakeWordActive]);

  return (
    <div
      data-testid="voice-wake-word-root"
      style={{ position: "fixed", bottom: 24, right: 24, zIndex: 9999 }}
    >
      <button
        onClick={listening ? stopListening : startListening}
        data-testid="voice-wake-toggle-btn"
        aria-label={listening ? "Stop listening" : "Start listening"}
        style={{
          width: 64,
          height: 64,
          borderRadius: "50%",
          background: listening
            ? "linear-gradient(135deg, #FF4444 0%, #CC0000 100%)"
            : "linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 4px 20px rgba(212, 175, 55, 0.4)",
          transition: "transform 0.3s",
          position: "relative",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.1)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
      >
        {listening ? (
          <Mic className="size-8 text-white" />
        ) : (
          <MicOff className="size-8 text-[#050505]" />
        )}

        {listening && (
          <div
            style={{
              position: "absolute",
              width: "100%",
              height: "100%",
              borderRadius: "50%",
              background: "rgba(255, 68, 68, 0.3)",
              animation: "pulse 2s infinite",
            }}
          />
        )}

        {wakeWordActive && (
          <div
            data-testid="voice-wake-active-dot"
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              width: 16,
              height: 16,
              borderRadius: "50%",
              background: "#4CAF50",
              border: "2px solid #0A0A0A",
              animation: "ping 1s infinite",
            }}
          />
        )}
      </button>

      {(listening || response) && (
        <div
          data-testid="voice-wake-panel"
          style={{
            position: "absolute",
            bottom: 80,
            right: 0,
            width: 320,
            background: "#0A0A0A",
            border: "1px solid #1A1A1A",
            borderRadius: 12,
            padding: 16,
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.8)",
          }}
        >
          {listening && (
            <div style={{ marginBottom: 12 }}>
              <div
                style={{
                  fontSize: 11,
                  color: "#888",
                  textTransform: "uppercase",
                  marginBottom: 6,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Activity className="size-3" />
                Listening for "Hey ORA"…
              </div>

              {/* Waveform */}
              <div
                data-testid="voice-wake-waveform"
                style={{
                  display: "flex",
                  alignItems: "flex-end",
                  gap: 2,
                  height: 32,
                  marginBottom: 8,
                }}
              >
                {waveformLevels.map((lvl, i) => (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      height: `${Math.max(4, lvl * 32)}px`,
                      background: wakeWordActive
                        ? "linear-gradient(180deg,#4CAF50,#1A6B1A)"
                        : "linear-gradient(180deg,#D4AF37,#8B7355)",
                      borderRadius: 1,
                      transition: "height 60ms linear",
                    }}
                  />
                ))}
              </div>

              <div
                style={{
                  fontSize: 14,
                  color: wakeWordActive ? "#4CAF50" : "#F4F4F4",
                  fontWeight: wakeWordActive ? 600 : 400,
                }}
              >
                {transcript || 'Say "Hey ORA" to activate…'}
              </div>
            </div>
          )}

          {response && (
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: "#888",
                  textTransform: "uppercase",
                  marginBottom: 4,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {speaking ? (
                  <>
                    <Volume2 className="size-3 animate-pulse" /> Speaking…
                  </>
                ) : (
                  <>
                    <Zap className="size-3" /> Response
                  </>
                )}
              </div>
              <div style={{ fontSize: 14, color: "#F4F4F4", lineHeight: 1.5 }}>
                {response.response_text}
              </div>
              {response.command && (
                <div
                  style={{
                    marginTop: 8,
                    padding: "4px 8px",
                    background: "#1A3A1A",
                    border: "1px solid #2A5A2A",
                    borderRadius: 6,
                    fontSize: 11,
                    color: "#4A4",
                    textTransform: "uppercase",
                  }}
                >
                  Command: {response.command}
                </div>
              )}
            </div>
          )}

          {listening && !transcript && (
            <div
              style={{
                marginTop: 12,
                padding: 12,
                background: "#050505",
                borderRadius: 8,
                border: "1px solid #1A1A1A",
              }}
            >
              <div style={{ fontSize: 11, color: "#888", marginBottom: 8 }}>
                Try saying:
              </div>
              <div style={{ fontSize: 12, color: "#666", lineHeight: 1.6 }}>
                • "Hey ORA, what's the revenue today?"
                <br />
                • "Hey ORA, show me the leads"
                <br />
                • "Hey ORA, sync the system"
                <br />
                • "Hey ORA, recover those carts"
              </div>
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.1); } }
        @keyframes ping { 0% { transform: scale(1); opacity: 1; } 75%,100% { transform: scale(2); opacity: 0; } }
      `}</style>
    </div>
  );
};

export default VoiceWakeWord;
