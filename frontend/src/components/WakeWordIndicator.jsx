/**
 * AUREM — WakeWordIndicator (Phase 3)
 * iter 322v · 2026-02-06
 *
 * Background-only "Hey ORA" listener. Renders ONLY a 3px gold pulse dot
 * (no panels, no waveform). On wake-phrase detection it calls
 * `onActivate()` so the parent can route to its voice-session UI.
 *
 * Defensive design:
 *   - Browsers without SpeechRecognition → renders nothing, never crashes
 *   - Mic permission denied → silently degrades, dot disappears
 *   - Auto-pause via `paused` prop while a voice session is active
 *   - Recognition is restarted on `end` so the listener stays alive
 *
 * No paid integrations required. Pure browser SpeechRecognition.
 */
import React, { useEffect, useRef, useState } from "react";

// "hey ora", "hi ora", "ok ora", "yo ora", plus "ora listen", "orah"
const WAKE_PATTERN = /\b((hey|hi|ok|yo)\s+(ora|aura|aurem|orah)|ora\s+listen)\b/i;

const STYLE_CSS = `
.aurem-wake-dot{
  position:relative; width:3px; height:3px; border-radius:50%;
  background:#D4A646;
  box-shadow:0 0 8px rgba(212,166,70,0.85), 0 0 14px rgba(212,166,70,0.45);
  animation:aurem-wake-pulse 2.4s ease-in-out infinite;
  display:inline-block;
}
.aurem-wake-dot.muted{
  background:rgba(212,166,70,0.20);
  box-shadow:none; animation:none;
}
.aurem-wake-dot::after{
  content:""; position:absolute; inset:-6px; border-radius:50%;
  border:1px solid rgba(212,166,70,0.35);
  animation:aurem-wake-ring 2.4s ease-out infinite;
}
.aurem-wake-dot.muted::after{display:none;}
@keyframes aurem-wake-pulse{
  0%,100%{transform:scale(1); opacity:1;}
  50%{transform:scale(0.7); opacity:0.55;}
}
@keyframes aurem-wake-ring{
  0%{transform:scale(0.6); opacity:0.9;}
  100%{transform:scale(2.4); opacity:0;}
}
`;

export default function WakeWordIndicator({ onActivate, paused = false }) {
  const [supported] = useState(() =>
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition)
  );
  const [active, setActive] = useState(false);
  const recognitionRef = useRef(null);
  const stoppedByUserRef = useRef(false);

  useEffect(() => {
    if (!supported) return;
    if (paused) {
      // External code (e.g. an open voice session) wants us silent.
      stoppedByUserRef.current = true;
      try { recognitionRef.current?.stop(); } catch (_e) { /* noop */ }
      setActive(false);
      return;
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-CA";
    recognitionRef.current = recognition;
    stoppedByUserRef.current = false;

    recognition.onstart = () => setActive(true);
    recognition.onend = () => {
      setActive(false);
      // Auto-restart unless the parent paused us (e.g. session active)
      if (!stoppedByUserRef.current) {
        try { recognition.start(); } catch (_e) { /* already running */ }
      }
    };
    recognition.onerror = (e) => {
      // mic-denied / no-speech / aborted — let onend restart logic decide
      setActive(false);
      if (e?.error === "not-allowed" || e?.error === "service-not-allowed") {
        // Permanent denial — stop trying
        stoppedByUserRef.current = true;
      }
    };
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((r) => r[0]?.transcript || "")
        .join(" ")
        .toLowerCase();
      if (WAKE_PATTERN.test(transcript)) {
        // Pause ourselves; parent decides when to re-enable us
        stoppedByUserRef.current = true;
        try { recognition.stop(); } catch (_e) { /* noop */ }
        if (typeof onActivate === "function") onActivate();
      }
    };

    try {
      recognition.start();
    } catch (_e) {
      // already-started edge case — ignore
    }

    return () => {
      stoppedByUserRef.current = true;
      try { recognition.stop(); } catch (_e) { /* noop */ }
      recognitionRef.current = null;
    };
  }, [supported, paused, onActivate]);

  if (!supported) return null;
  return (
    <span title={active ? "Listening for 'Hey ORA'" : "Wake word inactive"}>
      <style dangerouslySetInnerHTML={{ __html: STYLE_CSS }} />
      <span
        className={`aurem-wake-dot${active ? "" : " muted"}`}
        data-testid="aurem-wake-dot"
        aria-label={active ? "Wake word listening" : "Wake word muted"}
      />
    </span>
  );
}
