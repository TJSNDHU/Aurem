/* iter 282al-14 — ORA Video Session
 * iter 282al-19 — bug fixes:
 *   #1 Mirror-flip the video (selfie view)
 *   #2 Draggable popup (mouse + touch)
 *   #3 Audio auto-starts with video (handled by parent via onAudioStream)
 *
 * Floating webcam popup with face-api.js emotion detection (TFJS, runs
 * 100 % in-browser — no upload, no API key, no cost). Surfaces the
 * detected emotion to the parent via `onEmotionChange(emotion)` so ORA
 * can adapt tone in real-time.
 *
 * Privacy: video stream never leaves the browser. Only the emotion
 * label (one word) is forwarded to the chat handler.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";

const FACEAPI_CDN =
  "https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.13/dist/face-api.js";
// Tiny model weights mirror — ~700 KB total
const MODEL_BASE =
  "https://justadudewhohacks.github.io/face-api.js/models";

const EMOTION_EMOJI = {
  happy: "😊",
  sad: "😢",
  angry: "😠",
  fearful: "😨",
  disgusted: "🤢",
  surprised: "😮",
  neutral: "😐",
};

const POPUP_W = 320;
const POPUP_H = 320;

let _faceapiPromise = null;
function loadFaceApi() {
  if (window.faceapi) return Promise.resolve(window.faceapi);
  if (_faceapiPromise) return _faceapiPromise;
  _faceapiPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = FACEAPI_CDN;
    s.async = true;
    s.onload = () => resolve(window.faceapi);
    s.onerror = () => reject(new Error("face-api.js failed to load"));
    document.head.appendChild(s);
  });
  return _faceapiPromise;
}

let _modelsLoaded = false;
async function ensureModels(faceapi) {
  if (_modelsLoaded) return;
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_BASE),
    faceapi.nets.faceExpressionNet.loadFromUri(MODEL_BASE),
  ]);
  _modelsLoaded = true;
}

function defaultPosition() {
  // bottom-right corner with a 24px gutter from edges
  if (typeof window === "undefined") return { x: 0, y: 0 };
  return {
    x: Math.max(8, window.innerWidth - POPUP_W - 24),
    y: Math.max(8, window.innerHeight - POPUP_H - 96),
  };
}

export const VideoOraSession = ({ open, onClose, onEmotionChange, onAudioStream }) => {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const tickerRef = useRef(null);
  const [status, setStatus] = useState("Loading face detection…");
  const [emotion, setEmotion] = useState(null);
  const [confidence, setConfidence] = useState(0);

  // ── Bug #2 — Drag state ──────────────────────────────────────────
  const [pos, setPos] = useState(defaultPosition);
  const dragRef = useRef({ active: false, dx: 0, dy: 0 });

  const onPointerDown = useCallback((e) => {
    const point = e.touches ? e.touches[0] : e;
    dragRef.current = {
      active: true,
      dx: point.clientX - pos.x,
      dy: point.clientY - pos.y,
    };
    e.preventDefault();
  }, [pos.x, pos.y]);

  useEffect(() => {
    const move = (e) => {
      if (!dragRef.current.active) return;
      const point = e.touches ? e.touches[0] : e;
      const x = Math.max(
        8,
        Math.min(window.innerWidth - POPUP_W - 8, point.clientX - dragRef.current.dx),
      );
      const y = Math.max(
        8,
        Math.min(window.innerHeight - POPUP_H - 8, point.clientY - dragRef.current.dy),
      );
      setPos({ x, y });
    };
    const up = () => { dragRef.current.active = false; };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    window.addEventListener("touchmove", move, { passive: false });
    window.addEventListener("touchend", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("touchend", up);
    };
  }, []);

  const stop = useCallback(() => {
    if (tickerRef.current) {
      clearInterval(tickerRef.current);
      tickerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setEmotion(null);
    setConfidence(0);
    if (onAudioStream) onAudioStream(null); // signal parent to drop STT
  }, [onAudioStream]);

  const start = useCallback(async () => {
    try {
      setStatus("Loading face detection (one-time, ~700 KB)…");
      const faceapi = await loadFaceApi();
      await ensureModels(faceapi);

      // Bug #3 — request mic alongside camera so ORA hears AND sees.
      // Parent receives the audio track via `onAudioStream` and drives
      // the existing Web Speech API STT pipeline.
      setStatus("Requesting camera + mic…");
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: "user" },
          audio: true,
        });
      } catch (audioErr) {
        // Mic refused → fall back to video-only so emotion still works
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: "user" },
          audio: false,
        });
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      if (onAudioStream && stream.getAudioTracks().length > 0) {
        onAudioStream(stream);
      }
      setStatus("Looking…");

      // Emotion polling — every 1.5 s
      const opts = new faceapi.TinyFaceDetectorOptions({
        inputSize: 224,
        scoreThreshold: 0.5,
      });
      tickerRef.current = setInterval(async () => {
        if (!videoRef.current || videoRef.current.paused) return;
        try {
          const det = await faceapi
            .detectSingleFace(videoRef.current, opts)
            .withFaceExpressions();
          if (!det || !det.expressions) return;
          const exp = det.expressions;
          const sorted = Object.entries(exp).sort((a, b) => b[1] - a[1]);
          const [top, score] = sorted[0];
          if (score >= 0.45) {
            setEmotion(top);
            setConfidence(score);
            if (onEmotionChange) onEmotionChange(top, score);
            setStatus(`Detected · ${top}`);
          }
        } catch (e) {
          /* silent — keep ticking */
        }
      }, 1500);
    } catch (e) {
      setStatus(`Error: ${e.message}`);
      stop();
    }
  }, [onEmotionChange, onAudioStream, stop]);

  useEffect(() => {
    if (open) start();
    return stop;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div
      data-testid="video-ora-popup"
      style={{
        position: "fixed",
        left: pos.x,
        top: pos.y,
        width: POPUP_W,
        background: "#0d0d0d",
        border: "1px solid #C9A84C",
        borderRadius: 14,
        boxShadow: "0 16px 48px rgba(0,0,0,0.55)",
        zIndex: 2147483646,
        overflow: "hidden",
        fontFamily: "Jost, system-ui, sans-serif",
        userSelect: "none",
        touchAction: "none",
      }}
    >
      {/* drag-handle header */}
      <div
        onMouseDown={onPointerDown}
        onTouchStart={onPointerDown}
        data-testid="video-ora-drag-handle"
        style={{
          padding: "10px 14px",
          background:
            "linear-gradient(90deg, #FF6B00, #9b3a00)",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 13,
          fontWeight: 600,
          letterSpacing: "0.04em",
          cursor: "move",
        }}
      >
        <span>📹 Video with ORA</span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            stop();
            onClose && onClose();
          }}
          data-testid="video-ora-close"
          style={{
            background: "transparent",
            border: "none",
            color: "#fff",
            fontSize: 18,
            cursor: "pointer",
            lineHeight: 1,
          }}
          aria-label="Close video"
        >
          ×
        </button>
      </div>
      <div style={{ position: "relative", background: "#000" }}>
        <video
          ref={videoRef}
          width={320}
          height={240}
          autoPlay
          playsInline
          muted
          data-testid="video-ora-stream"
          style={{
            display: "block",
            width: "100%",
            height: 240,
            objectFit: "cover",
            transform: "scaleX(-1)", // Bug #1 — selfie/mirror view
          }}
        />
        {emotion && (
          <div
            data-testid="video-ora-emotion-chip"
            style={{
              position: "absolute",
              top: 8,
              left: 8,
              padding: "4px 10px",
              background: "rgba(0,0,0,0.72)",
              border: "1px solid rgba(201,168,76,0.55)",
              borderRadius: 999,
              color: "#FFD56B",
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: "0.04em",
            }}
          >
            {EMOTION_EMOJI[emotion] || "🙂"} {emotion}
            <span style={{ opacity: 0.7, marginLeft: 6, fontSize: 10 }}>
              {Math.round(confidence * 100)}%
            </span>
          </div>
        )}
      </div>
      <div
        style={{
          padding: "8px 12px",
          fontSize: 11,
          color: "#9a948a",
          textAlign: "center",
          letterSpacing: "0.03em",
          borderTop: "1px solid #1a1a1a",
        }}
        data-testid="video-ora-status"
      >
        {status} · drag header to move · video stays on this device
      </div>
    </div>
  );
};

export default VideoOraSession;
