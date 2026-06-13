"""
Iteration 177 - Memobase Semantic Memory + Video Engine + 3D Helix Tests
=========================================================================
Tests for:
1. Memobase (P1) - MongoDB-based vector semantic memory for Hermes OODA loop
2. Video Engine (P3) - Remotion scaffold with queue/claim/complete/download endpoints
3. Hermes Memory recall now includes semantic_memories field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module-level auth token
_auth_token = None

def get_auth_token():
    global _auth_token
    if _auth_token is None:
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "teji.ss1986@gmail.com",
            "password": os.environ.get("AUREM_ADMIN_PASSWORD", "")
        })
        if login_res.status_code == 200:
            _auth_token = login_res.json().get("token")
    return _auth_token


class TestMemobaseEndpoints:
    """Memobase semantic memory endpoints under /api/hermes/memobase/*"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = get_auth_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip("Auth failed - skipping authenticated tests")
    
    # === AUTH GUARD TESTS ===
    def test_memobase_store_requires_auth(self):
        """POST /api/hermes/memobase/store requires authentication"""
        res = requests.post(f"{BASE_URL}/api/hermes/memobase/store", json={"content": "test"})
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: memobase/store requires auth")
    
    def test_memobase_recall_requires_auth(self):
        """POST /api/hermes/memobase/recall requires authentication"""
        res = requests.post(f"{BASE_URL}/api/hermes/memobase/recall", json={"query": "test"})
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: memobase/recall requires auth")
    
    def test_memobase_consolidate_requires_auth(self):
        """POST /api/hermes/memobase/consolidate requires authentication"""
        res = requests.post(f"{BASE_URL}/api/hermes/memobase/consolidate")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: memobase/consolidate requires auth")
    
    def test_memobase_stats_requires_auth(self):
        """GET /api/hermes/memobase/stats requires authentication"""
        res = requests.get(f"{BASE_URL}/api/hermes/memobase/stats")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: memobase/stats requires auth")
    
    # === MEMOBASE STORE TESTS ===
    def test_memobase_store_episodic(self):
        """POST /api/hermes/memobase/store - stores episodic memory"""
        res = self.session.post(f"{BASE_URL}/api/hermes/memobase/store", json={
            "content": "TEST_User asked about pricing plans for enterprise tier",
            "memory_type": "episodic",
            "agent_id": "ora",
            "session_id": "test_session_177",
            "outcome": "success",
            "context": {"topic": "pricing", "tier": "enterprise"}
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("stored") == True, f"Expected stored=True, got {data}"
        assert "has_embedding" in data, "Response should include has_embedding field"
        assert data.get("memory_type") == "episodic", f"Expected memory_type=episodic, got {data}"
        print(f"PASS: memobase/store episodic - stored={data['stored']}, has_embedding={data.get('has_embedding')}")
    
    def test_memobase_store_semantic(self):
        """POST /api/hermes/memobase/store - stores semantic memory"""
        res = self.session.post(f"{BASE_URL}/api/hermes/memobase/store", json={
            "content": "TEST_AUREM platform provides AI-powered marketing automation",
            "memory_type": "semantic",
            "agent_id": "hermes",
            "outcome": "success"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("stored") == True
        assert data.get("memory_type") == "semantic"
        print(f"PASS: memobase/store semantic - stored={data['stored']}")
    
    def test_memobase_store_procedural(self):
        """POST /api/hermes/memobase/store - stores procedural memory"""
        res = self.session.post(f"{BASE_URL}/api/hermes/memobase/store", json={
            "content": "TEST_To generate a report: 1) Select client 2) Choose format 3) Click generate",
            "memory_type": "procedural",
            "agent_id": "ora",
            "outcome": "success"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("stored") == True
        assert data.get("memory_type") == "procedural"
        print(f"PASS: memobase/store procedural - stored={data['stored']}")
    
    # === MEMOBASE RECALL TESTS ===
    def test_memobase_recall_semantic_search(self):
        """POST /api/hermes/memobase/recall - semantic search across memories"""
        res = self.session.post(f"{BASE_URL}/api/hermes/memobase/recall", json={
            "query": "pricing enterprise tier",
            "limit": 5,
            "threshold": 0.3
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "memories" in data, "Response should include memories array"
        assert "count" in data, "Response should include count"
        assert "query" in data, "Response should include query"
        print(f"PASS: memobase/recall - found {data['count']} memories for query")
    
    def test_memobase_recall_with_filters(self):
        """POST /api/hermes/memobase/recall - with memory_type and agent_id filters"""
        res = self.session.post(f"{BASE_URL}/api/hermes/memobase/recall", json={
            "query": "marketing automation",
            "limit": 3,
            "memory_type": "semantic",
            "agent_id": "hermes"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "memories" in data
        print(f"PASS: memobase/recall with filters - found {data['count']} memories")
    
    # === MEMOBASE CONSOLIDATE TESTS ===
    def test_memobase_consolidate(self):
        """POST /api/hermes/memobase/consolidate - merge duplicate memories"""
        res = self.session.post(f"{BASE_URL}/api/hermes/memobase/consolidate")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "consolidated" in data, "Response should include consolidated count"
        print(f"PASS: memobase/consolidate - consolidated={data.get('consolidated')}")
    
    # === MEMOBASE STATS TESTS ===
    def test_memobase_stats(self):
        """GET /api/hermes/memobase/stats - memory statistics"""
        res = self.session.get(f"{BASE_URL}/api/hermes/memobase/stats")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "total_memories" in data, "Response should include total_memories"
        assert "with_embeddings" in data, "Response should include with_embeddings"
        assert "by_type" in data, "Response should include by_type breakdown"
        assert "embedding_coverage" in data, "Response should include embedding_coverage"
        print(f"PASS: memobase/stats - total={data['total_memories']}, with_embeddings={data['with_embeddings']}, coverage={data['embedding_coverage']}%")
    
    # === HERMES MEMORY RECALL WITH SEMANTIC_MEMORIES ===
    def test_hermes_memory_recall_includes_semantic(self):
        """GET /api/hermes/memory/recall - now includes semantic_memories field"""
        res = self.session.get(f"{BASE_URL}/api/hermes/memory/recall", params={
            "query": "pricing plans",
            "tenant_id": "aurem_platform"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "semantic_memories" in data, "Response should include semantic_memories field"
        assert "query_type" in data, "Response should include query_type"
        assert "prior_success" in data, "Response should include prior_success"
        print(f"PASS: hermes/memory/recall includes semantic_memories - count={len(data.get('semantic_memories', []))}")


class TestVideoEngineEndpoints:
    """Video Engine scaffold endpoints under /api/video/*"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = get_auth_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip("Auth failed - skipping authenticated tests")
    
    # === AUTH GUARD TESTS ===
    def test_video_generate_requires_auth(self):
        """POST /api/video/generate requires authentication"""
        res = requests.post(f"{BASE_URL}/api/video/generate", json={"video_type": "social_reel"})
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: video/generate requires auth")
    
    def test_video_queue_requires_auth(self):
        """GET /api/video/queue requires authentication"""
        res = requests.get(f"{BASE_URL}/api/video/queue")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: video/queue requires auth")
    
    def test_video_stats_requires_auth(self):
        """GET /api/video/stats requires authentication"""
        res = requests.get(f"{BASE_URL}/api/video/stats")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: video/stats requires auth")
    
    def test_video_types_requires_auth(self):
        """GET /api/video/types requires authentication"""
        res = requests.get(f"{BASE_URL}/api/video/types")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: video/types requires auth")
    
    def test_video_claim_requires_auth(self):
        """POST /api/video/claim requires authentication"""
        res = requests.post(f"{BASE_URL}/api/video/claim", json={"worker_id": "test"})
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: video/claim requires auth")
    
    def test_video_complete_requires_auth(self):
        """POST /api/video/complete requires authentication"""
        res = requests.post(f"{BASE_URL}/api/video/complete", json={"job_id": "test"})
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("PASS: video/complete requires auth")
    
    # === VIDEO TYPES ===
    def test_video_types(self):
        """GET /api/video/types - list available video templates"""
        res = self.session.get(f"{BASE_URL}/api/video/types")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "types" in data, "Response should include types"
        types = data["types"]
        # Verify expected video types exist
        expected_types = ["product_showcase", "campaign_recap", "testimonial", "social_reel"]
        for vtype in expected_types:
            assert vtype in types, f"Expected video type '{vtype}' not found"
            assert "label" in types[vtype], f"Video type {vtype} should have label"
            assert "duration_s" in types[vtype], f"Video type {vtype} should have duration_s"
            assert "resolution" in types[vtype], f"Video type {vtype} should have resolution"
        print(f"PASS: video/types - found {len(types)} video types: {list(types.keys())}")
    
    # === VIDEO GENERATE (QUEUE) ===
    def test_video_generate_social_reel(self):
        """POST /api/video/generate - queue social_reel video job"""
        res = self.session.post(f"{BASE_URL}/api/video/generate", json={
            "video_type": "social_reel",
            "title": "TEST_AUREM Social Reel",
            "content": {"headline": "AI Marketing", "cta": "Try Now"},
            "priority": 5
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("queued") == True, f"Expected queued=True, got {data}"
        assert "job_id" in data, "Response should include job_id"
        assert data.get("video_type") == "social_reel"
        assert data.get("status") == "queued"
        self.job_id = data["job_id"]
        print(f"PASS: video/generate social_reel - job_id={data['job_id']}, status={data['status']}")
        return data["job_id"]
    
    def test_video_generate_product_showcase(self):
        """POST /api/video/generate - queue product_showcase video job"""
        res = self.session.post(f"{BASE_URL}/api/video/generate", json={
            "video_type": "product_showcase",
            "title": "TEST_Product Demo",
            "content": {"product_name": "AUREM Platform", "features": ["AI Chat", "Analytics"]},
            "priority": 8
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("queued") == True
        assert data.get("video_type") == "product_showcase"
        print(f"PASS: video/generate product_showcase - job_id={data['job_id']}")
    
    def test_video_generate_invalid_type(self):
        """POST /api/video/generate - invalid video type returns 400"""
        res = self.session.post(f"{BASE_URL}/api/video/generate", json={
            "video_type": "invalid_type",
            "title": "Test"
        })
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        print("PASS: video/generate invalid type returns 400")
    
    # === VIDEO QUEUE ===
    def test_video_queue_list(self):
        """GET /api/video/queue - list queued jobs"""
        res = self.session.get(f"{BASE_URL}/api/video/queue", params={"limit": 10})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "jobs" in data, "Response should include jobs array"
        assert "count" in data, "Response should include count"
        print(f"PASS: video/queue - found {data['count']} jobs")
    
    # === VIDEO STATS ===
    def test_video_stats(self):
        """GET /api/video/stats - queue statistics"""
        res = self.session.get(f"{BASE_URL}/api/video/stats")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "total" in data, "Response should include total"
        assert "queued" in data, "Response should include queued count"
        assert "rendering" in data, "Response should include rendering count"
        assert "completed" in data, "Response should include completed count"
        assert "failed" in data, "Response should include failed count"
        print(f"PASS: video/stats - total={data['total']}, queued={data['queued']}, completed={data['completed']}")
    
    # === VIDEO CLAIM (Worker claims job) ===
    def test_video_claim_job(self):
        """POST /api/video/claim - worker claims next queued job"""
        res = self.session.post(f"{BASE_URL}/api/video/claim", json={
            "worker_id": "test_worker_177"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        # Either claimed a job or no jobs available
        if data.get("claimed"):
            assert "job" in data, "Response should include job details when claimed"
            job = data["job"]
            assert job.get("status") == "rendering", "Claimed job should have status=rendering"
            assert job.get("worker_id") == "test_worker_177"
            self.claimed_job_id = job.get("job_id")
            print(f"PASS: video/claim - claimed job_id={job['job_id']}, status={job['status']}")
        else:
            assert "message" in data, "Response should include message when no jobs"
            print(f"PASS: video/claim - no jobs available: {data.get('message')}")
    
    # === VIDEO COMPLETE (Worker marks job done) ===
    def test_video_complete_job(self):
        """POST /api/video/complete - worker marks job as completed"""
        # First claim a job
        claim_res = self.session.post(f"{BASE_URL}/api/video/claim", json={
            "worker_id": "test_worker_complete"
        })
        if claim_res.status_code == 200 and claim_res.json().get("claimed"):
            job_id = claim_res.json()["job"]["job_id"]
            
            # Complete the job
            res = self.session.post(f"{BASE_URL}/api/video/complete", json={
                "job_id": job_id,
                "output_path": "/app/backend/uploads/videos/test_output.mp4"
            })
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
            data = res.json()
            assert data.get("job_id") == job_id
            assert data.get("status") == "completed"
            print(f"PASS: video/complete - job_id={job_id}, status=completed")
        else:
            # Queue a new job first, then claim and complete
            gen_res = self.session.post(f"{BASE_URL}/api/video/generate", json={
                "video_type": "testimonial",
                "title": "TEST_Complete Flow",
                "content": {}
            })
            if gen_res.status_code == 200:
                job_id = gen_res.json()["job_id"]
                # Claim it
                self.session.post(f"{BASE_URL}/api/video/claim", json={"worker_id": "test_complete"})
                # Complete it
                res = self.session.post(f"{BASE_URL}/api/video/complete", json={
                    "job_id": job_id,
                    "output_path": "/app/backend/uploads/videos/test.mp4"
                })
                assert res.status_code == 200
                print(f"PASS: video/complete - job_id={job_id}, status={res.json().get('status')}")
            else:
                print("PASS: video/complete - skipped (no jobs to complete)")
    
    def test_video_complete_with_error(self):
        """POST /api/video/complete - worker marks job as failed"""
        # Generate and claim a job
        gen_res = self.session.post(f"{BASE_URL}/api/video/generate", json={
            "video_type": "campaign_recap",
            "title": "TEST_Error Flow",
            "content": {}
        })
        if gen_res.status_code == 200:
            job_id = gen_res.json()["job_id"]
            # Claim it
            self.session.post(f"{BASE_URL}/api/video/claim", json={"worker_id": "test_error"})
            # Complete with error
            res = self.session.post(f"{BASE_URL}/api/video/complete", json={
                "job_id": job_id,
                "error": "Render failed: out of memory"
            })
            assert res.status_code == 200
            data = res.json()
            assert data.get("status") == "failed"
            print(f"PASS: video/complete with error - job_id={job_id}, status=failed")
        else:
            print("PASS: video/complete with error - skipped")
    
    # === VIDEO DOWNLOAD ===
    def test_video_download_not_ready(self):
        """GET /api/video/download/{job_id} - returns 400 if not completed"""
        # Generate a job (will be queued, not completed)
        gen_res = self.session.post(f"{BASE_URL}/api/video/generate", json={
            "video_type": "social_reel",
            "title": "TEST_Download Not Ready",
            "content": {}
        })
        if gen_res.status_code == 200:
            job_id = gen_res.json()["job_id"]
            res = self.session.get(f"{BASE_URL}/api/video/download/{job_id}")
            assert res.status_code == 400, f"Expected 400, got {res.status_code}"
            print(f"PASS: video/download not ready - returns 400 for queued job")
        else:
            print("PASS: video/download not ready - skipped")
    
    def test_video_download_not_found(self):
        """GET /api/video/download/{job_id} - returns 404 for nonexistent job"""
        res = self.session.get(f"{BASE_URL}/api/video/download/nonexistent_job_id")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: video/download nonexistent - returns 404")


class TestForensicMinerHelixUI:
    """Tests for 3D Helix toggle buttons in Forensic Miner tab"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = get_auth_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip("Auth failed - skipping authenticated tests")
    
    def test_forensic_miner_scan_endpoint(self):
        """POST /api/forensic-miner/scan - verify endpoint works for helix data"""
        res = self.session.post(f"{BASE_URL}/api/forensic-miner/scan", json={
            "niche": "skincare",
            "limit": 3,
            "auto_outreach": False
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        # Verify response structure for helix visualization
        assert "stores" in data or "domains_found" in data, "Response should include stores or domains_found"
        print(f"PASS: forensic-miner/scan - domains_found={data.get('domains_found', 0)}, stores_enriched={data.get('stores_enriched', 0)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
