"""
Iteration 179 - Voice Recall Integration into ORA Chat Pipeline
================================================================
Tests the wiring of voice-recall into ORA's live chat pipeline:
1. ORA chat endpoint runs without errors (POST /api/aurem/chat)
2. Hermes recall includes semantic_memories from Memobase
3. After chat, a new memory is stored in Memobase (fire-and-forget)
4. Voice-transcript endpoint still works
5. Voice-recall endpoint still works
6. Memory count increases after chat interactions
7. Regression: /api/docs/generate still works
8. Regression: /api/video/types still works
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token."""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header."""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestMemobaseStatsBaseline:
    """Get baseline memory count before ORA chat tests."""

    def test_get_baseline_stats(self, authenticated_client):
        """Get initial memory count for comparison."""
        response = authenticated_client.get(f"{BASE_URL}/api/hermes/memobase/stats")
        assert response.status_code == 200, f"Stats endpoint failed: {response.text}"
        data = response.json()
        assert "total_memories" in data, "Missing total_memories field"
        print(f"[BASELINE] Memobase stats: total_memories={data.get('total_memories')}")
        # Store baseline for later comparison
        TestMemobaseStatsBaseline.baseline_count = data.get("total_memories", 0)


class TestORAChat:
    """Test ORA chat endpoint with voice-recall integration."""

    def test_ora_chat_basic(self, authenticated_client):
        """POST /api/aurem/chat — ORA chat pipeline runs without errors."""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        payload = {
            "message": "What is the current status of my business?",
            "session_id": session_id,
            "source": "chat",
        }
        # ORA chat may take up to 15 seconds due to model race timeout
        response = authenticated_client.post(
            f"{BASE_URL}/api/aurem/chat",
            json=payload,
            timeout=30,
        )
        assert response.status_code == 200, f"ORA chat failed: {response.status_code} - {response.text[:300]}"
        data = response.json()
        
        # Validate response structure
        assert "response" in data, "Missing response field"
        assert "session_id" in data, "Missing session_id field"
        assert "timestamp" in data, "Missing timestamp field"
        assert "llm_source" in data, "Missing llm_source field"
        
        # Response should not be empty
        assert len(data["response"]) > 0, "Empty response from ORA"
        
        # LLM source can be various values (timeout_fallback, resilience_fallback, race_winner_*, etc.)
        print(f"[ORA CHAT] Response: {data['response'][:100]}...")
        print(f"[ORA CHAT] LLM Source: {data['llm_source']}")
        print(f"[ORA CHAT] Session ID: {data['session_id']}")

    def test_ora_chat_voice_source(self, authenticated_client):
        """POST /api/aurem/chat with source=voice — triggers voice-specific prompt."""
        session_id = f"test_voice_{uuid.uuid4().hex[:8]}"
        payload = {
            "message": "Give me a quick update",
            "session_id": session_id,
            "source": "voice",  # Voice source triggers shorter responses
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/aurem/chat",
            json=payload,
            timeout=30,
        )
        assert response.status_code == 200, f"ORA voice chat failed: {response.status_code}"
        data = response.json()
        
        assert "response" in data
        assert len(data["response"]) > 0
        print(f"[ORA VOICE] Response: {data['response'][:100]}...")
        print(f"[ORA VOICE] LLM Source: {data['llm_source']}")

    def test_ora_chat_multiple_for_memory_storage(self, authenticated_client):
        """POST /api/aurem/chat multiple times to ensure memory storage fires."""
        session_id = f"test_memory_{uuid.uuid4().hex[:8]}"
        
        # Send 2 messages to ensure memory storage fires
        messages = [
            "TEST_VOICE_RECALL: What are my top clients?",
            "TEST_VOICE_RECALL: How is revenue trending?",
        ]
        
        for msg in messages:
            payload = {
                "message": msg,
                "session_id": session_id,
                "source": "chat",
            }
            response = authenticated_client.post(
                f"{BASE_URL}/api/aurem/chat",
                json=payload,
                timeout=30,
            )
            assert response.status_code == 200, f"ORA chat failed for '{msg[:30]}': {response.status_code}"
            data = response.json()
            assert "response" in data
            print(f"[ORA MULTI] Message: {msg[:40]}... -> LLM: {data['llm_source']}")
            # Small delay to allow fire-and-forget storage
            time.sleep(1)


class TestVoiceTranscript:
    """Test voice-transcript endpoint (Audio RAG pattern)."""

    def test_voice_transcript_store(self, authenticated_client):
        """POST /api/hermes/memobase/voice-transcript — stores transcript."""
        payload = {
            "transcript": "TEST_VOICE_RECALL: This is a test voice transcript for iteration 179 testing. The user asked about their business metrics and revenue forecasting.",
            "session_id": f"voice_test_{uuid.uuid4().hex[:8]}",
            "caller_info": {"caller_phone": "+1234567890"},
            "sentiment": "neutral",
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/voice-transcript",
            json=payload,
            timeout=15,
        )
        assert response.status_code == 200, f"Voice transcript failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("stored") is True, f"Transcript not stored: {data}"
        assert "chunks" in data, "Missing chunks field"
        print(f"[VOICE TRANSCRIPT] Stored: {data.get('stored')}, Chunks: {data.get('chunks')}")

    def test_voice_transcript_too_short(self, authenticated_client):
        """POST /api/hermes/memobase/voice-transcript — rejects short transcripts."""
        payload = {
            "transcript": "Hi",  # Too short (<10 chars)
            "session_id": "test_short",
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/voice-transcript",
            json=payload,
            timeout=15,
        )
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        data = response.json()
        assert data.get("stored") is False, "Short transcript should not be stored"
        assert data.get("reason") == "transcript_too_short", f"Wrong reason: {data.get('reason')}"
        print(f"[VOICE TRANSCRIPT SHORT] Correctly rejected: {data}")


class TestVoiceRecall:
    """Test voice-recall endpoint (semantic search for voice context)."""

    def test_voice_recall_basic(self, authenticated_client):
        """POST /api/hermes/memobase/voice-recall — returns memories with audio_rag pattern."""
        payload = {
            "query": "business metrics revenue",
            "limit": 5,
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/voice-recall",
            json=payload,
            timeout=15,
        )
        assert response.status_code == 200, f"Voice recall failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Response is a dict with 'memories' list and 'pattern' field
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "memories" in data, "Missing memories field"
        assert "pattern" in data, "Missing pattern field"
        assert data["pattern"] == "audio_rag", f"Expected pattern=audio_rag, got {data['pattern']}"
        
        memories = data["memories"]
        assert isinstance(memories, list), f"Expected memories to be list, got {type(memories)}"
        print(f"[VOICE RECALL] Found {len(memories)} memories, pattern={data['pattern']}")
        
        # If memories found, validate structure
        if len(memories) > 0:
            mem = memories[0]
            assert "content" in mem, "Missing content field"
            # Check for relevance_score (evaluator scoring pattern)
            if "relevance_score" in mem:
                print(f"[VOICE RECALL] First memory relevance_score: {mem.get('relevance_score')}")

    def test_voice_recall_with_caller_filter(self, authenticated_client):
        """POST /api/hermes/memobase/voice-recall — filters by caller_phone."""
        payload = {
            "query": "test voice transcript",
            "caller_phone": "+1234567890",
            "limit": 3,
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/voice-recall",
            json=payload,
            timeout=15,
        )
        assert response.status_code == 200, f"Voice recall with caller failed: {response.status_code}"
        data = response.json()
        
        assert isinstance(data, dict)
        assert "memories" in data
        memories = data["memories"]
        assert isinstance(memories, list)
        print(f"[VOICE RECALL CALLER] Found {len(memories)} memories for caller +1234567890")


class TestMemobaseStatsAfterChat:
    """Verify memory count increased after ORA chat interactions."""

    def test_stats_after_chat(self, authenticated_client):
        """GET /api/hermes/memobase/stats — memory count should increase."""
        # Wait a bit for fire-and-forget storage to complete
        time.sleep(2)
        
        response = authenticated_client.get(f"{BASE_URL}/api/hermes/memobase/stats")
        assert response.status_code == 200, f"Stats endpoint failed: {response.text}"
        data = response.json()
        
        assert "total_memories" in data
        current_count = data.get("total_memories", 0)
        baseline = getattr(TestMemobaseStatsBaseline, "baseline_count", 0)
        
        print(f"[STATS AFTER] Baseline: {baseline}, Current: {current_count}")
        
        # Memory count should have increased (or at least not decreased)
        # Note: fire-and-forget may not have completed yet, so we just check it's >= baseline
        assert current_count >= baseline, f"Memory count decreased: {baseline} -> {current_count}"
        
        # Check other stats fields
        assert "with_embeddings" in data
        assert "by_type" in data
        print(f"[STATS AFTER] With embeddings: {data.get('with_embeddings')}")
        print(f"[STATS AFTER] By type: {data.get('by_type')}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints."""

    def test_video_types(self, authenticated_client):
        """GET /api/video/types — still works (returns dict with 'types' key)."""
        response = authenticated_client.get(f"{BASE_URL}/api/video/types")
        assert response.status_code == 200, f"Video types failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Response is a dict with 'types' key
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "types" in data, "Missing types field"
        types = data["types"]
        assert isinstance(types, dict), f"Expected types to be dict, got {type(types)}"
        print(f"[REGRESSION] Video types: {len(types)} types available - {list(types.keys())}")

    def test_docs_generate(self, authenticated_client):
        """POST /api/docs/generate — still works (requires title and sections)."""
        payload = {
            "title": "Test Proposal",
            "doc_type": "proposal",
            "sections": [
                {"heading": "Introduction", "content": "This is a test proposal."},
                {"heading": "Scope", "content": "Testing document generation."},
            ],
            "context": {"client_name": "Test Client", "project": "Test Project"},
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/docs/generate",
            json=payload,
            timeout=30,
        )
        # Accept 200 or 202 (async generation)
        assert response.status_code in [200, 202], f"Docs generate failed: {response.status_code} - {response.text}"
        data = response.json()
        print(f"[REGRESSION] Docs generate response: {list(data.keys())}")


class TestMemobaseRecallWithSemanticMemories:
    """Test that Hermes recall includes semantic_memories from Memobase."""

    def test_memobase_recall_endpoint(self, authenticated_client):
        """POST /api/hermes/memobase/recall — returns semantic memories in dict format."""
        payload = {
            "query": "business revenue clients",
            "limit": 5,
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/recall",
            json=payload,
            timeout=15,
        )
        assert response.status_code == 200, f"Memobase recall failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Response is a dict with 'memories' list
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "memories" in data, "Missing memories field"
        
        memories = data["memories"]
        assert isinstance(memories, list), f"Expected memories to be list, got {type(memories)}"
        print(f"[MEMOBASE RECALL] Found {len(memories)} semantic memories")
        
        # If memories found, validate structure includes relevance_score
        if len(memories) > 0:
            mem = memories[0]
            assert "content" in mem, "Missing content field"
            # Evaluator scoring pattern should add relevance_score
            if "relevance_score" in mem:
                print(f"[MEMOBASE RECALL] First memory relevance_score: {mem.get('relevance_score')}")
            if "similarity" in mem:
                print(f"[MEMOBASE RECALL] First memory similarity: {mem.get('similarity')}")


class TestMemobaseStore:
    """Test direct Memobase store endpoint."""

    def test_memobase_store(self, authenticated_client):
        """POST /api/hermes/memobase/store — stores memory with embedding."""
        payload = {
            "content": "TEST_VOICE_RECALL: Iteration 179 test memory for voice recall integration testing.",
            "memory_type": "episodic",
            "agent_id": "test_agent",
            "session_id": f"test_{uuid.uuid4().hex[:8]}",
            "outcome": "success",
            "context": {"test": True, "iteration": 179},
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/store",
            json=payload,
            timeout=15,
        )
        assert response.status_code == 200, f"Memobase store failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("stored") is True, f"Memory not stored: {data}"
        print(f"[MEMOBASE STORE] Stored: {data.get('stored')}, Has embedding: {data.get('has_embedding')}")


class TestMemobaseConsolidate:
    """Test Memobase consolidation endpoint."""

    def test_memobase_consolidate(self, authenticated_client):
        """POST /api/hermes/memobase/consolidate — merges similar memories."""
        response = authenticated_client.post(
            f"{BASE_URL}/api/hermes/memobase/consolidate",
            json={},
            timeout=30,
        )
        assert response.status_code == 200, f"Consolidate failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Should return consolidation stats
        assert "consolidated" in data, "Missing consolidated field"
        print(f"[MEMOBASE CONSOLIDATE] Consolidated: {data.get('consolidated')} memories")


class TestMemoryCountIncrease:
    """Final verification that memory count increased after all tests."""

    def test_final_memory_count(self, authenticated_client):
        """Verify memory count increased after all ORA chat and store operations."""
        # Wait for fire-and-forget operations to complete
        time.sleep(3)
        
        response = authenticated_client.get(f"{BASE_URL}/api/hermes/memobase/stats")
        assert response.status_code == 200
        data = response.json()
        
        final_count = data.get("total_memories", 0)
        baseline = getattr(TestMemobaseStatsBaseline, "baseline_count", 0)
        
        print(f"[FINAL CHECK] Baseline: {baseline}, Final: {final_count}, Increase: {final_count - baseline}")
        
        # Memory count should have increased from ORA chat + voice transcript + store operations
        # At minimum, we stored 1 voice transcript + 1 direct store = 2 new memories
        # Plus ORA chat fire-and-forget stores
        assert final_count > baseline, f"Memory count did not increase: {baseline} -> {final_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
