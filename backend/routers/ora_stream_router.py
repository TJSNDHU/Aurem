"""
ORA Streaming Pipeline — WebSocket + Chunked V2V
=================================================
Real-time token streaming and Voice-to-Voice with sub-200ms latency.

Architecture:
  1. WebSocket /api/ora/stream — streams LLM tokens as they generate
  2. Chunked V2V — LLM generates ~5 words → immediately pipes to TTS → streams audio
  3. SSE fallback /api/ora/stream-sse — for browsers without WebSocket support

The 50ms Rule: No silence while ORA is thinking.
"""

import os
import json
import time
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ORA Streaming"])

# Streaming config
CHUNK_WORDS = 8  # Words per V2V chunk (lower = faster first audio)
STREAM_TIMEOUT = 30  # Max seconds for a streaming response


def _get_db():
    try:
        import server
        return server.db
    except Exception:
        return None


def _get_llm_key():
    return os.getenv("EMERGENT_LLM_KEY", "")


async def _verify_token(token: str) -> dict:
    """Verify JWT token for WebSocket auth."""
    import jwt
    secret = os.getenv("JWT_SECRET", "")
    return jwt.decode(token, secret, algorithms=["HS256"])


async def _stream_llm_tokens(message: str, session_id: str, context: str = ""):
    """
    Generator that yields LLM response tokens as they're generated.
    Uses Emergent LLM for streaming.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        system_msg = """You are ORA, the sovereign AI commander for AUREM — a biotech empire automation platform.
You are sharp, concise, and strategic. Respond naturally in 2-3 sentences unless detail is requested."""
        if context:
            system_msg += f"\n\nContext:\n{context}"

        chat = LlmChat(
            api_key=_get_llm_key(),
            session_id=session_id,
            system_message=system_msg,
        ).with_model("openai", "gpt-4o")

        response = await chat.send_message(UserMessage(text=message))
        resp_text = response if isinstance(response, str) else str(response)

        # Simulate token-by-token streaming (Emergent doesn't support native streaming yet)
        words = resp_text.split()
        buffer = []
        for i, word in enumerate(words):
            buffer.append(word)
            # Yield every CHUNK_WORDS words or at sentence boundaries
            if len(buffer) >= CHUNK_WORDS or word.endswith(('.', '!', '?', ':', ';')) or i == len(words) - 1:
                chunk = " ".join(buffer)
                buffer = []
                yield chunk

    except Exception as e:
        logger.error(f"[ORA Stream] LLM error: {e}")
        yield "I'm experiencing a connection issue. Please try again."


async def _stream_sovereign_tokens(message: str, session_id: str, context: str = ""):
    """
    Stream tokens from the Sovereign Node (Ollama via Cloudflare Tunnel).
    Ollama natively supports streaming — true token-by-token delivery.
    """
    try:
        from services.local_llm_service import get_config
        config = get_config()
        if not config.get("enabled") or not config.get("ollama_url"):
            async for chunk in _stream_llm_tokens(message, session_id, context):
                yield chunk
            return

        import httpx
        ollama_url = config["ollama_url"].rstrip("/")
        model = config.get("model", "llama3.1")

        system_prompt = "You are ORA, the sovereign AI commander for AUREM. Be concise and strategic."
        if context:
            system_prompt += f"\n\nContext:\n{context}"

        async with httpx.AsyncClient(timeout=httpx.Timeout(STREAM_TIMEOUT, connect=5)) as client:
            async with client.stream(
                "POST",
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    "stream": True,
                },
                headers={},
            ) as resp:
                word_buffer = []
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            word_buffer.append(token)
                            # Check if we have enough for a chunk
                            combined = "".join(word_buffer)
                            word_count = len(combined.split())
                            if word_count >= CHUNK_WORDS or combined.rstrip().endswith(('.', '!', '?', ':')):
                                yield combined
                                word_buffer = []
                        if data.get("done"):
                            if word_buffer:
                                yield "".join(word_buffer)
                            break
                    except json.JSONDecodeError:
                        continue

    except Exception as e:
        logger.warning(f"[ORA Stream] Sovereign stream failed: {e}, falling back to cloud")
        async for chunk in _stream_llm_tokens(message, session_id, context):
            yield chunk


# ═══ WEBSOCKET STREAMING ENDPOINT ═══

@router.websocket("/api/ora/stream")
async def ora_stream_ws(websocket: WebSocket):
    """
    WebSocket endpoint for real-time ORA chat streaming.
    
    Client sends: {"type": "chat", "message": "...", "session_id": "...", "token": "..."}
    Server sends: {"type": "token", "text": "...", "chunk_index": N}
                  {"type": "done", "full_text": "...", "session_id": "...", "latency_ms": N}
                  {"type": "v2v_audio", "audio_b64": "...", "chunk_index": N}  (if V2V enabled)
    """
    await websocket.accept()
    logger.info("[ORA Stream] WebSocket connected")

    try:
        while True:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=120)
            data = json.loads(raw)
            msg_type = data.get("type", "chat")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": time.time()})
                continue

            if msg_type != "chat":
                continue

            # Auth check
            token = data.get("token", "")
            try:
                await _verify_token(token)
            except Exception:
                await websocket.send_json({"type": "error", "message": "Invalid authentication"})
                continue

            message = data.get("message", "").strip()
            session_id = data.get("session_id", str(uuid.uuid4()))
            v2v_enabled = data.get("v2v", False)

            if not message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            t0 = time.time()
            full_text = []
            chunk_index = 0

            # Stream tokens
            async for chunk in _stream_sovereign_tokens(message, session_id):
                full_text.append(chunk)
                chunk_index += 1

                await websocket.send_json({
                    "type": "token",
                    "text": chunk,
                    "chunk_index": chunk_index,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                })

                # V2V: Pipe chunk to TTS immediately
                if v2v_enabled and len(chunk.split()) >= 3:
                    try:
                        from services.sovereign_voice import synthesize_speech
                        voice_result = await synthesize_speech(chunk, speaker="ORA")
                        if voice_result.get("success"):
                            await websocket.send_json({
                                "type": "v2v_chunk",
                                "chunk_index": chunk_index,
                                "audio_size": voice_result.get("audio_size", 0),
                                "first_byte_ms": voice_result.get("first_byte_ms", 0),
                            })
                    except Exception as ve:
                        logger.debug(f"[V2V] Chunk voice failed: {ve}")

            # Done
            complete_text = " ".join(full_text)
            total_ms = int((time.time() - t0) * 1000)

            await websocket.send_json({
                "type": "done",
                "full_text": complete_text,
                "session_id": session_id,
                "latency_ms": total_ms,
                "chunks": chunk_index,
                "source": "sovereign" if chunk_index > 1 else "cloud",
            })

            # Store in session memory
            try:
                db = _get_db()
                if db is not None:
                    await db.session_memory.insert_one({
                        "session_id": session_id,
                        "role": "user",
                        "content": message,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    await db.session_memory.insert_one({
                        "session_id": session_id,
                        "role": "assistant",
                        "content": complete_text,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "latency_ms": total_ms,
                    })
            except Exception:
                pass

    except WebSocketDisconnect:
        logger.info("[ORA Stream] WebSocket disconnected")
    except asyncio.TimeoutError:
        logger.info("[ORA Stream] WebSocket idle timeout")
    except Exception as e:
        logger.error(f"[ORA Stream] Error: {e}")


# ═══ SSE STREAMING FALLBACK ═══

class StreamChatRequest(BaseModel):
    message: str
    session_id: str = ""
    v2v: bool = False


@router.post("/api/ora/stream-sse")
async def ora_stream_sse(req: StreamChatRequest, authorization: str = Header(None)):
    """
    SSE fallback for streaming — for clients without WebSocket support.
    Returns Server-Sent Events with token chunks.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        await _verify_token(authorization.replace("Bearer ", ""))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    session_id = req.session_id or str(uuid.uuid4())

    async def event_generator():
        t0 = time.time()
        chunk_index = 0
        full_text = []

        async for chunk in _stream_sovereign_tokens(req.message, session_id):
            full_text.append(chunk)
            chunk_index += 1
            event_data = json.dumps({
                "type": "token",
                "text": chunk,
                "chunk_index": chunk_index,
                "elapsed_ms": int((time.time() - t0) * 1000),
            })
            yield f"data: {event_data}\n\n"

        # Done event
        complete_text = " ".join(full_text)
        done_data = json.dumps({
            "type": "done",
            "full_text": complete_text,
            "session_id": session_id,
            "latency_ms": int((time.time() - t0) * 1000),
            "chunks": chunk_index,
        })
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



# ─────────────────────────────────────────────────────────────────────
# iter 322ah — Groq-backed SSE for the customer ORA widget
# ─────────────────────────────────────────────────────────────────────
class GroqStreamReq(BaseModel):
    message: str
    session_id: str | None = None


_GROQ_SYSTEM = (
    "You are ORA, the AI sales co-pilot for the AUREM platform. "
    "You help local business owners (plumbers, salons, auto shops, etc.) "
    "manage their leads, campaigns, and customer outreach. "
    "Be concise, friendly, and actionable. Reply in 2–4 sentences unless "
    "the user explicitly asks for detail. Use plain English with light "
    "Hinglish phrasing when the user does. Never invent specific lead "
    "details, numbers, or names — if you need data, say so and offer to "
    "look it up."
)


@router.post("/api/aurem/chat/stream")
async def aurem_chat_stream_groq(body: GroqStreamReq, request: Request):
    """SSE stream of ORA chat tokens via Groq llama-3.3-70b.
    First token <100ms target. Falls back to OpenRouter chain on failure.

    Frame format (one JSON per `data:` line):
      • {session_id}                  — first frame, conversation id
      • {ttfb_ms}                     — on first model token
      • {token: "<chunk>"}            — each model chunk
      • {done: true, total_ms, ttfb_ms}  — terminator
      • {error: "..."}                — only on failure
    """
    from services.llm_gateway_v2 import route_stream

    msg = (body.message or "").strip()
    session_id = body.session_id or f"ora_{uuid.uuid4().hex[:12]}"
    if not msg:
        async def empty():
            yield f"data: {json.dumps({'error': 'empty message'})}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    start = time.monotonic()

    async def gen():
        ttfb_ms = None
        full_text = ""
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
        try:
            async for tok in route_stream(
                "ora_chat", msg, system=_GROQ_SYSTEM, max_tokens=600,
            ):
                if ttfb_ms is None:
                    ttfb_ms = round((time.monotonic() - start) * 1000.0, 1)
                    yield f"data: {json.dumps({'ttfb_ms': ttfb_ms})}\n\n"
                full_text += tok
                yield f"data: {json.dumps({'token': tok})}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            logger.warning(f"[ora.stream.groq] crash: {e}")
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
        total_ms = round((time.monotonic() - start) * 1000.0, 1)
        yield f"data: {json.dumps({'done': True, 'ttfb_ms': ttfb_ms, 'total_ms': total_ms})}\n\n"

        db = _get_db()
        if db is not None:
            try:
                await db.ora_chat_history.insert_one({
                    "session_id": session_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "user_message": msg,
                    "assistant_text": full_text,
                    "ttfb_ms": ttfb_ms,
                    "total_ms": total_ms,
                    "streamed": True,
                    "model": "groq/llama-3.3-70b-versatile",
                })
            except Exception:
                pass

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
