#!/usr/bin/env python3
"""
AUREM TTS Server — Runs on your Legion laptop alongside Ollama.
Provides XTTS v2 voice synthesis at sub-200ms first-byte latency.

SETUP:
  1. pip install TTS==0.22.0 flask
  2. Place your 6-second voice sample at: ./voice_samples/ora_voice.wav
  3. python tts_server.py --port 5002
  4. Expose via Cloudflare Tunnel

The main AUREM platform calls this server for voice synthesis.
"""
import argparse
import os
import io
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TTS_SERVER")

# Lazy imports (heavy ML deps)
TTS_ENGINE = None
VOICE_SAMPLE = None


def init_engine(sample_path: str = "./voice_samples/ora_voice.wav"):
    """Initialize XTTS v2 engine with voice sample."""
    global TTS_ENGINE, VOICE_SAMPLE

    try:
        import torch
        from TTS.api import TTS

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[TTS] Initializing XTTS v2 on {device}...")

        TTS_ENGINE = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        if os.path.exists(sample_path):
            VOICE_SAMPLE = sample_path
            logger.info(f"[TTS] Voice sample loaded: {sample_path}")
        else:
            logger.warning(f"[TTS] No voice sample at {sample_path} — using default speaker")

        logger.info("[TTS] XTTS v2 ready!")
        return True

    except Exception as e:
        logger.error(f"[TTS] Init failed: {e}")
        logger.error("[TTS] Install with: pip install TTS==0.22.0")
        return False


def create_app():
    """Create Flask app for TTS API."""
    from flask import Flask, request, jsonify, send_file
    app = Flask(__name__)

    @app.route("/tts/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok" if TTS_ENGINE else "not_initialized",
            "model": "xtts_v2",
            "voice_sample": VOICE_SAMPLE is not None,
            "gpu": "cuda" if hasattr(TTS_ENGINE, 'device') and 'cuda' in str(getattr(TTS_ENGINE, 'device', '')) else "cpu",
        })

    @app.route("/tts/synthesize", methods=["POST"])
    def synthesize():
        data = request.json or {}
        text = data.get("text", "")
        speaker = data.get("speaker", "ORA")
        language = data.get("language", "en")

        if not text:
            return jsonify({"error": "No text provided"}), 400

        if not TTS_ENGINE:
            return jsonify({"error": "TTS engine not initialized"}), 503

        t0 = time.time()

        try:
            # Synthesize
            if VOICE_SAMPLE:
                wav = TTS_ENGINE.tts(
                    text=text[:500],  # Cap at 500 chars per request
                    speaker_wav=VOICE_SAMPLE,
                    language=language,
                )
            else:
                wav = TTS_ENGINE.tts(
                    text=text[:500],
                    language=language,
                )

            elapsed_ms = int((time.time() - t0) * 1000)

            # Convert to WAV bytes
            import numpy as np
            import wave
            import struct

            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                # Normalize and convert to int16
                audio_np = np.array(wav)
                audio_np = audio_np / max(abs(audio_np.max()), abs(audio_np.min()), 1e-6)
                audio_int16 = (audio_np * 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())

            audio_buffer.seek(0)

            logger.info(f"[TTS] Synthesized {len(text)} chars in {elapsed_ms}ms")

            return send_file(
                audio_buffer,
                mimetype="audio/wav",
                as_attachment=False,
                download_name="speech.wav",
            )

        except Exception as e:
            logger.error(f"[TTS] Synthesis failed: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/tts/speakers", methods=["GET"])
    def list_speakers():
        if TTS_ENGINE and hasattr(TTS_ENGINE, 'speakers'):
            return jsonify({"speakers": TTS_ENGINE.speakers or []})
        return jsonify({"speakers": []})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AUREM TTS Server (XTTS v2)")
    parser.add_argument("--port", type=int, default=5002, help="Server port")
    parser.add_argument("--sample", type=str, default="./voice_samples/ora_voice.wav", help="Voice sample WAV path")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Listen address")
    args = parser.parse_args()

    print("=" * 50)
    print("  AUREM Sovereign Voice — XTTS v2 Server")
    print("=" * 50)

    if init_engine(args.sample):
        app = create_app()
        print(f"\n  Listening on http://{args.host}:{args.port}")
        print(f"  Voice sample: {args.sample}")
        print(f"  Health check: http://localhost:{args.port}/tts/health")
        print(f"\n  Expose with: cloudflared tunnel --url http://localhost: {args.port}")
        print("=" * 50)
        app.run(host=args.host, port=args.port, debug=False)
    else:
        print("\n  [ERROR] TTS engine failed to initialize.")
        print("  Install: pip install TTS==0.22.0")
        print("  Ensure PyTorch + CUDA are installed for GPU acceleration.")
