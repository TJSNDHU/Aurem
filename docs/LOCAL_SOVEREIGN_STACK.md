# AUREM Local Sovereign Stack — Setup Guide
## For Tj's Lenovo Legion (Intel Ultra 9)

This document describes how to run AUREM's AI stack locally for **$0 forever** operational cost.

---

## 1. Kokoro-82M TTS (Voice)

**Replaces**: ElevenLabs ($11+/mo)  
**Quality**: Better than Web Speech API, near-ElevenLabs quality  
**Cost**: $0 forever  
**License**: Apache 2.0  

### Install
```bash
pip install kokoro-onnx
# No GPU required for 82M model — runs on CPU
```

### Usage
```python
from kokoro_onnx import Kokoro

kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
samples, sample_rate = kokoro.create(
    "Welcome to AUREM, your AI business command center.",
    voice="af_heart",  # or af_sarah, am_adam
    speed=1.0
)
# Save: soundfile.write("output.wav", samples, sample_rate)
```

### Endpoint
- Run as local API: `localhost:8880/tts`
- When ready: Replace Web Speech API fallback in `v2v_stream_engine.py`

### Voice Options
- `af_heart` — Warm female (Scientific-Luxe tone)
- `af_sarah` — Professional female
- `am_adam` — Professional male
- `bf_emma` — British female

---

## 2. SearXNG Search Engine

**Replaces**: Perplexity Sonar Pro ($20+/mo)  
**Aggregates**: Google + Bing + DuckDuckGo + Reddit + YouTube simultaneously  
**Cost**: $0 forever  

### Install
```bash
docker pull searxng/searxng
docker run -d --name searxng \
  -p 8888:8080 \
  -e SEARXNG_SECRET="aurem-sovereign-key" \
  searxng/searxng
```

### Usage
```python
import httpx

async def searxng_search(query: str) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8888/search", params={
            "q": query, "format": "json", "engines": "google,bing,duckduckgo"
        })
        return resp.json().get("results", [])
```

### Endpoint
- `localhost:8888/search?q=your+query&format=json`
- When ready: Replace ScoutSearch primary tier in `scout_search.py`

---

## 3. Ollama Local LLM

**Replaces**: OpenRouter free tier models  
**Models**: llama3, mistral, deepseek-r1, qwen2.5  
**Cost**: $0 forever  

### Install
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama3.3           # 70B, general purpose
ollama pull deepseek-r1:14b    # Reasoning
ollama pull qwen2.5:32b        # Coding + analysis
ollama pull mistral:7b         # Fast fallback
```

### Usage
```python
import httpx

async def ollama_chat(prompt: str, model: str = "llama3.3") -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post("http://localhost:11434/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        })
        return resp.json()["message"]["content"]
```

### Endpoint
- `localhost:11434/api/chat`
- When ready: Replace OpenRouter free models as primary in `openrouter_client.py`

---

## Wire Order (When Legion is Ready)

```
Priority Chain:
1. Local Ollama         → Primary brain (fastest, most private)
2. Free OpenRouter      → Cloud fallback (if local is down)
3. Paid OpenRouter      → Emergency only (almost never)
4. Emergent LLM Key     → Ultimate fallback (should never reach)

TTS Chain:
1. Local Kokoro-82M     → Primary voice
2. OpenAI TTS           → Cloud fallback
3. Web Speech API       → Browser fallback

Search Chain:
1. Local SearXNG        → Primary search (aggregated)
2. DuckDuckGo           → Cloud fallback (free)
3. SmartSearch (Google)  → Quota-limited fallback
4. OpenRouter free      → Knowledge-based answer
```

---

## Cost Comparison

| Service | Before (Cloud) | After (Local) |
|---------|---------------|---------------|
| LLM Brain | $20-50/mo (GPT-4o) | $0 (Ollama) |
| Voice TTS | $11-22/mo (ElevenLabs) | $0 (Kokoro) |
| Web Search | $20/mo (Perplexity) | $0 (SearXNG) |
| **Total** | **$50-90/mo** | **$0/mo** |

**Electricity cost**: ~$5-10/mo for running Legion 24/7  
**Net savings**: $40-80/mo

---

## Sentinel Integration

When local services are running, update Sentinel Observer to check:
- `localhost:11434` — Ollama health
- `localhost:8880` — Kokoro health  
- `localhost:8888` — SearXNG health

If any local service fails, Sentinel auto-falls back to cloud equivalents.
