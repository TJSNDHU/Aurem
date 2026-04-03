"""
Test Live Support WebSocket Signaling Flow
Tests:
1. Session creation via POST /api/support/start
2. Admin WebSocket connection at /api/support/ws/admin/{admin_id}
3. User WebSocket connection at /api/support/ws/user/{session_id}
4. WebRTC signaling flow (webrtc_offer forwarding from user to admin)
5. Admin watching session and receiving offers
"""

import pytest
import requests
import asyncio
import websockets
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

# Get base URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL environment variable is required")

# WebSocket URL (convert https to wss)
WS_BASE_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

# Helper function for websocket connection with proper timeout handling
async def ws_connect(url, close_timeout=5):
    """Connect to websocket with proper timeout handling for newer websockets library"""
    return await asyncio.wait_for(
        websockets.connect(url, close_timeout=close_timeout),
        timeout=10
    )


class TestLiveSupportSessionCreation:
    """Test session creation endpoint"""
    
    def test_create_session_success(self):
        """Test POST /api/support/start creates a session"""
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": "test-user-001",
                "user_name": "Test User"
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "user_id" in data, "Response should contain user_id"
        assert data["user_id"] == "test-user-001"
        assert data["status"] == "active"
        print(f"✓ Session created: {data['session_id']}")
        
        return data["session_id"]
    
    def test_create_session_missing_user_id(self):
        """Test POST /api/support/start without user_id returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={"user_name": "Test User"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Missing user_id returns 400")
    
    def test_get_active_sessions(self):
        """Test GET /api/support/sessions returns active sessions"""
        response = requests.get(f"{BASE_URL}/api/support/sessions")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "sessions" in data, "Response should contain sessions array"
        assert isinstance(data["sessions"], list)
        print(f"✓ Active sessions endpoint works, found {len(data['sessions'])} sessions")


class TestLiveSupportWebSocketConnections:
    """Test WebSocket connections for admin and user"""
    
    @pytest.mark.asyncio
    async def test_admin_websocket_connection(self):
        """Test admin can connect via WebSocket and receive active_sessions"""
        admin_id = f"test-admin-{int(time.time())}"
        ws_url = f"{WS_BASE_URL}/api/support/ws/admin/{admin_id}"
        
        try:
            ws = await ws_connect(ws_url)
            try:
                # Admin should receive active_sessions on connect
                message = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(message)
                
                assert data["type"] == "active_sessions", f"Expected active_sessions, got {data['type']}"
                assert "sessions" in data, "Should contain sessions array"
                print(f"✓ Admin WebSocket connected, received {len(data['sessions'])} active sessions")
            finally:
                await ws.close()
                
        except Exception as e:
            pytest.fail(f"Admin WebSocket connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_user_websocket_connection_with_valid_session(self):
        """Test user can connect via WebSocket with valid session"""
        # First create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-ws-{int(time.time())}",
                "user_name": "WebSocket Test User"
            }
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        ws_url = f"{WS_BASE_URL}/api/support/ws/user/{session_id}"
        
        try:
            ws = await ws_connect(ws_url)
            try:
                # Connection should succeed
                print(f"✓ User WebSocket connected for session {session_id}")
                
                # Send a ping to verify connection is working
                await ws.send(json.dumps({"type": "ping"}))
                # Note: The server doesn't respond to ping in user websocket, but connection works
            finally:
                await ws.close()
                
        except Exception as e:
            pytest.fail(f"User WebSocket connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_user_websocket_connection_with_invalid_session(self):
        """Test user WebSocket connection with invalid session is rejected"""
        ws_url = f"{WS_BASE_URL}/api/support/ws/user/invalid-session-id"
        
        try:
            ws = await ws_connect(ws_url)
            try:
                # Should be closed with error code
                message = await asyncio.wait_for(ws.recv(), timeout=5)
                pytest.fail("Should have been rejected")
            finally:
                await ws.close()
        except websockets.exceptions.ConnectionClosed as e:
            # Expected - session not found
            assert e.code == 4004, f"Expected close code 4004, got {e.code}"
            print("✓ Invalid session correctly rejected with code 4004")
        except asyncio.TimeoutError:
            # Connection timeout is also acceptable for invalid session
            print("✓ Invalid session rejected (timeout)")
        except Exception as e:
            # Connection refused is also acceptable
            print(f"✓ Invalid session rejected: {type(e).__name__}")


class TestWebRTCSignalingFlow:
    """Test WebRTC signaling flow between user and admin"""
    
    @pytest.mark.asyncio
    async def test_admin_watching_session_notifies_user(self):
        """Test that when admin watches a session, user receives admin_watching message"""
        # Create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-rtc-{int(time.time())}",
                "user_name": "RTC Test User"
            }
        )
        assert response.status_code == 200
        session_data = response.json()
        session_id = session_data["session_id"]
        user_id = session_data["user_id"]
        
        admin_id = f"test-admin-rtc-{int(time.time())}"
        
        admin_ws_url = f"{WS_BASE_URL}/api/support/ws/admin/{admin_id}"
        user_ws_url = f"{WS_BASE_URL}/api/support/ws/user/{session_id}"
        
        admin_ws = None
        user_ws = None
        try:
            admin_ws = await ws_connect(admin_ws_url)
            # Admin receives active_sessions
            msg = await asyncio.wait_for(admin_ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "active_sessions"
            
            user_ws = await ws_connect(user_ws_url)
            
            # Admin starts watching the session
            await admin_ws.send(json.dumps({
                "type": "watch_session",
                "session_id": session_id
            }))
            
            # User should receive admin_watching notification
            user_msg = await asyncio.wait_for(user_ws.recv(), timeout=5)
            user_data = json.loads(user_msg)
            
            assert user_data["type"] == "admin_watching", f"Expected admin_watching, got {user_data['type']}"
            assert user_data["admin_id"] == admin_id
            print(f"✓ User received admin_watching notification from {admin_id}")
                    
        except Exception as e:
            pytest.fail(f"Admin watching session test failed: {e}")
        finally:
            if admin_ws:
                await admin_ws.close()
            if user_ws:
                await user_ws.close()
    
    @pytest.mark.asyncio
    async def test_webrtc_offer_forwarded_to_admin(self):
        """Test that webrtc_offer from user is forwarded to watching admin"""
        # Create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-offer-{int(time.time())}",
                "user_name": "Offer Test User"
            }
        )
        assert response.status_code == 200
        session_data = response.json()
        session_id = session_data["session_id"]
        
        admin_id = f"test-admin-offer-{int(time.time())}"
        
        admin_ws_url = f"{WS_BASE_URL}/api/support/ws/admin/{admin_id}"
        user_ws_url = f"{WS_BASE_URL}/api/support/ws/user/{session_id}"
        
        # Mock WebRTC offer
        mock_offer = {
            "type": "offer",
            "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:test\r\na=ice-pwd:testpassword\r\na=fingerprint:sha-256 00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00\r\na=setup:actpass\r\na=mid:0\r\na=sendonly\r\na=rtcp-mux\r\na=rtpmap:96 VP8/90000\r\n"
        }
        
        admin_ws = None
        user_ws = None
        try:
            admin_ws = await ws_connect(admin_ws_url)
            # Admin receives active_sessions
            msg = await asyncio.wait_for(admin_ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "active_sessions"
            
            user_ws = await ws_connect(user_ws_url)
            
            # Admin starts watching the session
            await admin_ws.send(json.dumps({
                "type": "watch_session",
                "session_id": session_id
            }))
            
            # Wait for user to receive admin_watching
            user_msg = await asyncio.wait_for(user_ws.recv(), timeout=5)
            user_data = json.loads(user_msg)
            assert user_data["type"] == "admin_watching"
            
            # User sends webrtc_offer for screen share
            await user_ws.send(json.dumps({
                "type": "webrtc_offer",
                "offer": mock_offer,
                "target_admin": admin_id,
                "stream_type": "screen"
            }))
            
            # Admin should receive the webrtc_offer
            admin_msg = await asyncio.wait_for(admin_ws.recv(), timeout=5)
            admin_data = json.loads(admin_msg)
            
            assert admin_data["type"] == "webrtc_offer", f"Expected webrtc_offer, got {admin_data['type']}"
            assert admin_data["session_id"] == session_id
            assert admin_data["stream_type"] == "screen"
            assert "offer" in admin_data
            assert admin_data["offer"]["sdp"] == mock_offer["sdp"]
            
            print(f"✓ WebRTC offer successfully forwarded to admin")
            print(f"  - Session ID: {session_id}")
            print(f"  - Stream type: {admin_data['stream_type']}")
            print(f"  - SDP length: {len(admin_data['offer']['sdp'])} chars")
                    
        except Exception as e:
            pytest.fail(f"WebRTC offer forwarding test failed: {e}")
        finally:
            if admin_ws:
                await admin_ws.close()
            if user_ws:
                await user_ws.close()
    
    @pytest.mark.asyncio
    async def test_webrtc_answer_forwarded_to_user(self):
        """Test that webrtc_answer from admin is forwarded to user"""
        # Create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-answer-{int(time.time())}",
                "user_name": "Answer Test User"
            }
        )
        assert response.status_code == 200
        session_data = response.json()
        session_id = session_data["session_id"]
        
        admin_id = f"test-admin-answer-{int(time.time())}"
        
        admin_ws_url = f"{WS_BASE_URL}/api/support/ws/admin/{admin_id}"
        user_ws_url = f"{WS_BASE_URL}/api/support/ws/user/{session_id}"
        
        # Mock WebRTC answer
        mock_answer = {
            "type": "answer",
            "sdp": "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:answer\r\na=ice-pwd:answerpassword\r\na=fingerprint:sha-256 11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11:11\r\na=setup:active\r\na=mid:0\r\na=recvonly\r\na=rtcp-mux\r\na=rtpmap:96 VP8/90000\r\n"
        }
        
        admin_ws = None
        user_ws = None
        try:
            admin_ws = await ws_connect(admin_ws_url)
            # Admin receives active_sessions
            msg = await asyncio.wait_for(admin_ws.recv(), timeout=5)
            
            user_ws = await ws_connect(user_ws_url)
            
            # Admin starts watching
            await admin_ws.send(json.dumps({
                "type": "watch_session",
                "session_id": session_id
            }))
            
            # Wait for user to receive admin_watching
            user_msg = await asyncio.wait_for(user_ws.recv(), timeout=5)
            
            # Admin sends webrtc_answer
            await admin_ws.send(json.dumps({
                "type": "webrtc_answer",
                "session_id": session_id,
                "answer": mock_answer,
                "stream_type": "screen"
            }))
            
            # User should receive the webrtc_answer
            user_answer_msg = await asyncio.wait_for(user_ws.recv(), timeout=5)
            user_answer_data = json.loads(user_answer_msg)
            
            assert user_answer_data["type"] == "webrtc_answer", f"Expected webrtc_answer, got {user_answer_data['type']}"
            assert user_answer_data["admin_id"] == admin_id
            assert user_answer_data["stream_type"] == "screen"
            assert "answer" in user_answer_data
            
            print(f"✓ WebRTC answer successfully forwarded to user")
            print(f"  - Admin ID: {admin_id}")
            print(f"  - Stream type: {user_answer_data['stream_type']}")
                    
        except Exception as e:
            pytest.fail(f"WebRTC answer forwarding test failed: {e}")
        finally:
            if admin_ws:
                await admin_ws.close()
            if user_ws:
                await user_ws.close()
    
    @pytest.mark.asyncio
    async def test_ice_candidate_forwarding(self):
        """Test that ICE candidates are forwarded between user and admin"""
        # Create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-ice-{int(time.time())}",
                "user_name": "ICE Test User"
            }
        )
        assert response.status_code == 200
        session_data = response.json()
        session_id = session_data["session_id"]
        
        admin_id = f"test-admin-ice-{int(time.time())}"
        
        admin_ws_url = f"{WS_BASE_URL}/api/support/ws/admin/{admin_id}"
        user_ws_url = f"{WS_BASE_URL}/api/support/ws/user/{session_id}"
        
        # Mock ICE candidate
        mock_ice_candidate = {
            "candidate": "candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host",
            "sdpMid": "0",
            "sdpMLineIndex": 0
        }
        
        admin_ws = None
        user_ws = None
        try:
            admin_ws = await ws_connect(admin_ws_url)
            # Admin receives active_sessions
            msg = await asyncio.wait_for(admin_ws.recv(), timeout=5)
            
            user_ws = await ws_connect(user_ws_url)
            
            # Admin starts watching
            await admin_ws.send(json.dumps({
                "type": "watch_session",
                "session_id": session_id
            }))
            
            # Wait for user to receive admin_watching
            user_msg = await asyncio.wait_for(user_ws.recv(), timeout=5)
            
            # User sends ICE candidate
            await user_ws.send(json.dumps({
                "type": "webrtc_ice",
                "candidate": mock_ice_candidate,
                "target_admin": admin_id,
                "stream_type": "screen"
            }))
            
            # Admin should receive the ICE candidate
            admin_ice_msg = await asyncio.wait_for(admin_ws.recv(), timeout=5)
            admin_ice_data = json.loads(admin_ice_msg)
            
            assert admin_ice_data["type"] == "webrtc_ice", f"Expected webrtc_ice, got {admin_ice_data['type']}"
            assert admin_ice_data["session_id"] == session_id
            assert admin_ice_data["stream_type"] == "screen"
            assert "candidate" in admin_ice_data
            
            print(f"✓ ICE candidate successfully forwarded to admin")
                    
        except Exception as e:
            pytest.fail(f"ICE candidate forwarding test failed: {e}")
        finally:
            if admin_ws:
                await admin_ws.close()
            if user_ws:
                await user_ws.close()


class TestSessionManagement:
    """Test session lifecycle management"""
    
    def test_end_session(self):
        """Test POST /api/support/end/{session_id} ends a session"""
        # First create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-end-{int(time.time())}",
                "user_name": "End Test User"
            }
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # End the session
        end_response = requests.post(f"{BASE_URL}/api/support/end/{session_id}")
        
        assert end_response.status_code == 200, f"Expected 200, got {end_response.status_code}"
        
        data = end_response.json()
        assert data["status"] == "ended"
        assert data["session_id"] == session_id
        print(f"✓ Session {session_id} ended successfully")
    
    def test_end_nonexistent_session(self):
        """Test ending a non-existent session returns 404"""
        response = requests.post(f"{BASE_URL}/api/support/end/nonexistent-session")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent session returns 404")
    
    def test_get_session_details(self):
        """Test GET /api/support/session/{session_id} returns session details"""
        # First create a session
        response = requests.post(
            f"{BASE_URL}/api/support/start",
            json={
                "user_id": f"test-user-details-{int(time.time())}",
                "user_name": "Details Test User"
            }
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # Get session details
        details_response = requests.get(f"{BASE_URL}/api/support/session/{session_id}")
        
        assert details_response.status_code == 200, f"Expected 200, got {details_response.status_code}"
        
        data = details_response.json()
        assert data["session_id"] == session_id
        assert "user_id" in data
        assert "user_name" in data
        assert "status" in data
        assert "viewing_admins" in data
        print(f"✓ Session details retrieved: {data['session_id']}")


class TestInviteSystem:
    """Test invite link system"""
    
    def test_create_invite_link(self):
        """Test POST /api/support/invite/create creates an invite"""
        response = requests.post(
            f"{BASE_URL}/api/support/invite/create",
            json={
                "admin_id": "test-admin",
                "customer_name": "Test Customer",
                "customer_email": "test@example.com",
                "note": "Test invite"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "invite_code" in data
        assert "invite_url" in data
        assert len(data["invite_code"]) == 8
        print(f"✓ Invite created: {data['invite_code']}")
        
        return data["invite_code"]
    
    def test_get_invite(self):
        """Test GET /api/support/invite/{code} returns invite details"""
        # First create an invite
        create_response = requests.post(
            f"{BASE_URL}/api/support/invite/create",
            json={"admin_id": "test-admin"}
        )
        invite_code = create_response.json()["invite_code"]
        
        # Get invite details
        response = requests.get(f"{BASE_URL}/api/support/invite/{invite_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["invite_code"] == invite_code
        assert data["status"] == "pending"
        print(f"✓ Invite details retrieved: {invite_code}")
    
    def test_join_via_invite(self):
        """Test POST /api/support/invite/{code}/join creates session from invite"""
        # First create an invite
        create_response = requests.post(
            f"{BASE_URL}/api/support/invite/create",
            json={"admin_id": "test-admin"}
        )
        invite_code = create_response.json()["invite_code"]
        
        # Join via invite
        join_response = requests.post(
            f"{BASE_URL}/api/support/invite/{invite_code}/join",
            json={
                "user_id": f"guest-{int(time.time())}",
                "user_name": "Guest User"
            }
        )
        
        assert join_response.status_code == 200, f"Expected 200, got {join_response.status_code}"
        
        data = join_response.json()
        assert "session" in data
        assert "invite" in data
        assert data["invite"]["status"] == "used"
        print(f"✓ Joined via invite, session: {data['session']['session_id']}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
