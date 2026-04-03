/**
 * AdminLiveSupport.jsx - Admin view for live support sessions
 * Shows callback requests, screen share sessions
 * Flow: AI Chat -> Callback -> Admin Request Screen Share
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';

// Dynamically import rrweb-player to avoid blocking admin panel load
let rrwebPlayer = null;
const loadRrwebPlayer = async () => {
  if (!rrwebPlayer) {
    try {
      const module = await import('rrweb-player');
      rrwebPlayer = module.default;
      await import('rrweb-player/dist/style.css');
    } catch (e) {
      console.error('Failed to load rrweb-player:', e);
    }
  }
  return rrwebPlayer;
};

// Colors
const C = {
  void: "#060608",
  gold: "#c9a86e",
  goldDim: "rgba(201,168,110,0.6)",
  surface: "#0f0f11",
  surface2: "#151518",
  text: "#f5f0e8",
  textDim: "rgba(245,240,232,0.5)",
  border: "rgba(201,168,110,0.15)",
  red: "#ef4444",
  green: "#22c55e",
  blue: "#3b82f6",
  orange: "#f97316"
};

export default function AdminLiveSupport({ adminId, apiBase }) {
  const [activeTab, setActiveTab] = useState('callbacks');  // 'callbacks' | 'sessions'
  const [callbacks, setCallbacks] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedCallback, setSelectedCallback] = useState(null);
  const [consoleErrors, setConsoleErrors] = useState([]);
  const [connected, setConnected] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteForm, setInviteForm] = useState({ customer_name: '', customer_email: '', note: '' });
  const [generatedInvite, setGeneratedInvite] = useState(null);
  const [copySuccess, setCopySuccess] = useState(false);
  
  const wsRef = useRef(null);
  const playerRef = useRef(null);
  const playerContainerRef = useRef(null);
  const eventsRef = useRef([]);
  const peerConnectionRef = useRef(null);  // For camera
  const screenPeerConnectionRef = useRef(null);  // For screen share
  const remoteVideoRef = useRef(null);  // Camera video
  const remoteScreenRef = useRef(null);  // Screen share video
  const selectedSessionRef = useRef(null); // Track selected session for WebSocket handler
  const sessionsRef = useRef([]); // Track sessions for WebSocket handler
  const [hasScreenVideo, setHasScreenVideo] = useState(false);  // WebRTC screen stream active

  // Create invite link
  const createInviteLink = async () => {
    try {
      const res = await fetch(`${apiBase}/api/support/invite/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: adminId,
          ...inviteForm
        })
      });
      const data = await res.json();
      const fullUrl = `${window.location.origin}/app?support=${data.invite_code}`;
      setGeneratedInvite({ ...data, full_url: fullUrl });
    } catch (e) {
      console.error('Failed to create invite:', e);
    }
  };

  const copyInviteLink = () => {
    if (generatedInvite?.full_url) {
      navigator.clipboard.writeText(generatedInvite.full_url);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

  const resetInviteModal = () => {
    setShowInviteModal(false);
    setGeneratedInvite(null);
    setInviteForm({ customer_name: '', customer_email: '', note: '' });
  };

  // Connect to admin WebSocket
  useEffect(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = apiBase.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${wsHost}/api/support/ws/admin/${adminId}`;
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[Admin] WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWSMessage(data);
    };

    ws.onerror = (e) => {
      console.error('[Admin] WebSocket error:', e);
      setConnected(false);
    };

    ws.onclose = () => {
      console.log('[Admin] WebSocket closed');
      setConnected(false);
    };

    // Fetch initial callbacks
    fetchCallbacks();
    // Refresh callbacks every 10 seconds
    const interval = setInterval(fetchCallbacks, 10000);

    return () => {
      if (ws) ws.close();
      clearInterval(interval);
    };
  }, [adminId, apiBase]);

  // Fetch callback requests
  const fetchCallbacks = async () => {
    try {
      const res = await fetch(`${apiBase}/api/support/callbacks`);
      const data = await res.json();
      setCallbacks(data.callbacks || []);
    } catch (e) {
      console.error('[Admin] Failed to fetch callbacks:', e);
    }
  };

  // Accept a callback
  const acceptCallback = async (callback) => {
    try {
      const res = await fetch(`${apiBase}/api/support/callback/${callback.callback_id}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: adminId,
          admin_name: 'Support Team'
        })
      });
      const data = await res.json();
      if (data.status === 'accepted') {
        setSelectedCallback(callback);
        fetchCallbacks();
      }
    } catch (e) {
      console.error('[Admin] Failed to accept callback:', e);
    }
  };

  // Request screen share from user
  const requestScreenShare = async (userId, userName) => {
    try {
      const res = await fetch(`${apiBase}/api/support/screen-share/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: adminId,
          admin_name: 'Support Team',
          user_id: userId,
          message: `Our support team would like to view your screen to help diagnose your issue, ${userName.split(' ')[0]}.`
        })
      });
      const data = await res.json();
      if (data.status === 'sent') {
        alert('Screen share request sent to customer. Waiting for them to accept...');
      }
    } catch (e) {
      console.error('[Admin] Failed to request screen share:', e);
      alert('Failed to send screen share request. Customer may not be online.');
    }
  };

  // Handle WebSocket messages
  const handleWSMessage = useCallback((data) => {
    const currentSession = selectedSessionRef.current;
    
    switch (data.type) {
      case 'active_sessions':
        setSessions(data.sessions || []);
        sessionsRef.current = data.sessions || [];
        break;

      case 'new_session':
        setSessions(prev => {
          const updated = [...prev, data.session];
          sessionsRef.current = updated;
          return updated;
        });
        break;

      case 'session_ended':
        setSessions(prev => {
          const updated = prev.filter(s => s.session_id !== data.session_id);
          sessionsRef.current = updated;
          return updated;
        });
        if (currentSession?.session_id === data.session_id) {
          setSelectedSession(null);
          selectedSessionRef.current = null;
          eventsRef.current = [];
        }
        break;

      case 'rrweb_events':
        if (currentSession && data.session_id === currentSession.session_id) {
          eventsRef.current = [...eventsRef.current, ...data.events];
          console.log('[Admin] Received rrweb events:', data.events.length, 'Total:', eventsRef.current.length);
          updatePlayer();
        }
        break;

      case 'webrtc_offer':
        console.log('[Admin] Received webrtc_offer, session:', data.session_id, 'streamType:', data.stream_type, 'current session:', currentSession?.session_id);
        if (currentSession && data.session_id === currentSession.session_id) {
          handleWebRTCOffer(data.offer, data.session_id, data.stream_type || 'camera');
        } else if (!currentSession) {
          // No session selected - try to find and auto-select the matching session
          console.log('[Admin] No session selected, checking sessions:', sessionsRef.current.length);
          const matchingSession = sessionsRef.current.find(s => s.session_id === data.session_id);
          if (matchingSession) {
            console.log('[Admin] Auto-selecting session and handling offer:', data.session_id);
            setSelectedSession(matchingSession);
            selectedSessionRef.current = matchingSession;
            handleWebRTCOffer(data.offer, data.session_id, data.stream_type || 'camera');
          } else {
            console.log('[Admin] Ignoring webrtc_offer - no matching session found in:', sessionsRef.current.map(s => s.session_id));
          }
        } else {
          console.log('[Admin] Ignoring webrtc_offer - session mismatch:', data.session_id, '!=', currentSession.session_id);
        }
        break;

      case 'webrtc_ice':
        // Route to correct peer connection based on stream type
        console.log('[Admin] Received webrtc_ice, session:', data.session_id, 'streamType:', data.stream_type, 'current session:', currentSession?.session_id);
        if (currentSession && data.session_id === currentSession.session_id) {
          const targetPc = data.stream_type === 'screen' 
            ? screenPeerConnectionRef.current 
            : peerConnectionRef.current;
          if (targetPc && data.candidate) {
            console.log('[Admin] Adding ICE candidate for:', data.stream_type);
            targetPc.addIceCandidate(new RTCIceCandidate(data.candidate))
              .then(() => console.log('[Admin] ICE candidate added successfully'))
              .catch(e => console.error('[Admin] Error adding ICE candidate:', e));
          } else {
            console.log('[Admin] No peer connection for ICE candidate, streamType:', data.stream_type, 'pcExists:', !!targetPc);
          }
        }
        break;

      case 'console_error':
        if (currentSession && data.session_id === currentSession.session_id) {
          setConsoleErrors(prev => [...prev, {
            error: data.error,
            timestamp: data.timestamp,
            ai_diagnosis: data.ai_diagnosis || null
          }].slice(-50)); // Keep last 50 errors
        }
        break;

      case 'new_callback':
        // New callback request - refresh the list
        fetchCallbacks();
        break;

      case 'screen_share_declined':
        alert(`Customer declined the screen share request.`);
        break;

      default:
        console.log('[Admin] Unknown message:', data);
    }
  }, []); // No dependencies - use refs for session tracking

  // Update or create rrweb player
  const updatePlayer = async () => {
    if (!playerContainerRef.current || eventsRef.current.length < 2) {
      console.log('[Admin] Not enough events to create player:', eventsRef.current.length);
      return;
    }

    console.log('[Admin] Updating player with', eventsRef.current.length, 'events');

    // For live mode, we need to use replayer with live updates
    try {
      const RrwebPlayer = await loadRrwebPlayer();
      if (!RrwebPlayer) {
        console.error('[Admin] rrweb-player not loaded');
        return;
      }
      
      // Destroy existing player only if we're creating a new one
      if (playerRef.current) {
        try {
          // Try to add events to existing player in live mode
          if (playerRef.current.addEvent) {
            const newEvents = eventsRef.current.slice(-10); // Add last 10 events
            newEvents.forEach(e => playerRef.current.addEvent(e));
            return;
          }
          playerRef.current.pause();
          playerRef.current = null;
          playerContainerRef.current.innerHTML = '';
        } catch (e) {
          console.log('[Admin] Error updating existing player:', e);
        }
      }
      
      playerRef.current = new RrwebPlayer({
        target: playerContainerRef.current,
        props: {
          events: eventsRef.current,
          width: 800,
          height: 450,
          autoPlay: true,
          showController: false,
          speed: 1,
          skipInactive: true,
          liveMode: true,
          insertStyleRules: [
            '.replayer-wrapper { background: #0f0f11 !important; }'
          ]
        }
      });
      
      console.log('[Admin] Player created successfully');
    } catch (e) {
      console.error('[Admin] Player error:', e);
    }
  };

  // Handle WebRTC offer from user (camera or screen)
  const handleWebRTCOffer = async (offer, sessionId, streamType = 'camera') => {
    console.log('[Admin] Handling WebRTC offer for:', streamType, 'session:', sessionId);
    console.log('[Admin] Offer SDP length:', offer?.sdp?.length);
    
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' },
        { urls: 'stun:stun3.l.google.com:19302' },
        { urls: 'stun:stun4.l.google.com:19302' }
      ]
    });
    
    if (streamType === 'screen') {
      // Close existing connection if any
      if (screenPeerConnectionRef.current) {
        console.log('[Admin] Closing existing screen peer connection');
        screenPeerConnectionRef.current.close();
      }
      screenPeerConnectionRef.current = pc;
    } else {
      if (peerConnectionRef.current) {
        console.log('[Admin] Closing existing camera peer connection');
        peerConnectionRef.current.close();
      }
      peerConnectionRef.current = pc;
    }

    // Handle incoming video track
    pc.ontrack = (event) => {
      console.log('[Admin] Received video track for:', streamType, 'streams:', event.streams.length, 'tracks:', event.track?.kind);
      
      if (streamType === 'screen') {
        if (remoteScreenRef.current) {
          console.log('[Admin] Setting screen video srcObject, stream:', event.streams[0]?.id);
          const stream = event.streams[0] || new MediaStream([event.track]);
          remoteScreenRef.current.srcObject = stream;
          setHasScreenVideo(true);
          
          // Force play after a small delay
          setTimeout(() => {
            if (remoteScreenRef.current) {
              remoteScreenRef.current.play()
                .then(() => console.log('[Admin] Screen video playing successfully'))
                .catch(e => console.log('[Admin] Screen video play error:', e));
            }
          }, 100);
        }
      } else {
        if (remoteVideoRef.current) {
          console.log('[Admin] Setting camera video srcObject');
          const stream = event.streams[0] || new MediaStream([event.track]);
          remoteVideoRef.current.srcObject = stream;
          remoteVideoRef.current.play().catch(e => console.log('[Admin] Camera video play error:', e));
        }
      }
    };
    
    pc.oniceconnectionstatechange = () => {
      console.log('[Admin] ICE connection state for', streamType, ':', pc.iceConnectionState);
    };
    
    pc.onconnectionstatechange = () => {
      console.log('[Admin] WebRTC connection state:', pc.connectionState, 'for:', streamType);
      if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
        console.log('[Admin] WebRTC disconnected/failed for:', streamType);
        if (streamType === 'screen') {
          setHasScreenVideo(false);
        }
      } else if (pc.connectionState === 'connected') {
        console.log('[Admin] WebRTC connected successfully for:', streamType);
      }
    };

    // Handle ICE candidates
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('[Admin] ICE candidate generated for:', streamType);
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'webrtc_ice',
            session_id: sessionId,
            candidate: event.candidate,
            stream_type: streamType
          }));
        }
      } else {
        console.log('[Admin] ICE gathering complete for:', streamType);
      }
    };

    try {
      // Set remote description and create answer
      console.log('[Admin] Setting remote description for:', streamType);
      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      console.log('[Admin] Remote description set, creating answer for:', streamType);
      
      const answer = await pc.createAnswer();
      console.log('[Admin] Answer created for:', streamType, 'SDP length:', answer.sdp?.length);
      
      await pc.setLocalDescription(answer);
      console.log('[Admin] Local description set for:', streamType);

      // Send answer to user
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'webrtc_answer',
          session_id: sessionId,
          answer: answer,
          stream_type: streamType
        }));
        console.log('[Admin] WebRTC answer sent for:', streamType);
      }
    } catch (err) {
      console.error('[Admin] WebRTC offer handling error:', err);
    }
  };

  // Watch a session
  const watchSession = (session) => {
    // Stop watching previous session
    if (selectedSession) {
      wsRef.current?.send(JSON.stringify({
        type: 'stop_watching',
        session_id: selectedSession.session_id
      }));
    }

    // Clean up
    eventsRef.current = [];
    setConsoleErrors([]);
    if (playerRef.current) {
      playerRef.current = null;
      if (playerContainerRef.current) {
        playerContainerRef.current.innerHTML = '';
      }
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    if (screenPeerConnectionRef.current) {
      screenPeerConnectionRef.current.close();
      screenPeerConnectionRef.current = null;
    }
    setHasScreenVideo(false);

    setSelectedSession(session);
    selectedSessionRef.current = session; // Update ref for WebSocket handler
    console.log('[Admin] Now watching session:', session.session_id);

    // Start watching new session
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'watch_session',
        session_id: session.session_id
      }));
    }
  };

  // Stop watching
  const stopWatching = () => {
    if (selectedSession && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'stop_watching',
        session_id: selectedSession.session_id
      }));
    }
    setSelectedSession(null);
    selectedSessionRef.current = null; // Clear ref
    eventsRef.current = [];
    setConsoleErrors([]);
    setHasScreenVideo(false);
    if (playerRef.current) {
      playerRef.current = null;
      if (playerContainerRef.current) {
        playerContainerRef.current.innerHTML = '';
      }
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    if (screenPeerConnectionRef.current) {
      screenPeerConnectionRef.current.close();
      screenPeerConnectionRef.current = null;
    }
  };

  return (
    <div style={{ padding: 24, minHeight: '100vh', background: C.void }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-start',
        marginBottom: 24,
        flexWrap: 'wrap',
        gap: 12
      }}>
        <div>
          <h1 style={{ color: C.text, fontSize: 20, fontWeight: 600, margin: 0 }}>
            Live Support Sessions
          </h1>
          <p style={{ color: C.textDim, fontSize: 12, margin: '4px 0 0 0' }}>
            View user screens in real-time
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Share Link Button */}
          <button
            onClick={() => setShowInviteModal(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
              color: C.void, border: 'none', borderRadius: 6,
              cursor: 'pointer', fontWeight: 600, fontSize: 12
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
              <polyline points="16 6 12 2 8 6"/>
              <line x1="12" y1="2" x2="12" y2="15"/>
            </svg>
            Share Link
          </button>
          
          {/* Connection Status */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 6,
            padding: '6px 12px',
            background: connected ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
            borderRadius: 6,
            fontSize: 12
          }}>
            <div style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: connected ? C.green : C.red
            }} />
            <span style={{ color: connected ? C.green : C.red }}>
              {connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {/* Left Panel - Callbacks & Sessions */}
        <div style={{ 
          width: '100%',
          maxWidth: 300,
          minWidth: 250,
          flexShrink: 0,
          background: C.surface,
          borderRadius: 12,
          padding: 12,
          border: `1px solid ${C.border}`
        }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button
              onClick={() => setActiveTab('callbacks')}
              style={{
                flex: 1, padding: '10px 12px', borderRadius: 8,
                background: activeTab === 'callbacks' ? `linear-gradient(135deg, ${C.gold}, #b8956a)` : C.surface2,
                color: activeTab === 'callbacks' ? C.void : C.textDim,
                border: activeTab === 'callbacks' ? 'none' : `1px solid ${C.border}`,
                cursor: 'pointer', fontSize: 13, fontWeight: 600
              }}
            >
              Callbacks ({callbacks.length})
            </button>
            <button
              onClick={() => setActiveTab('sessions')}
              style={{
                flex: 1, padding: '10px 12px', borderRadius: 8,
                background: activeTab === 'sessions' ? `linear-gradient(135deg, ${C.gold}, #b8956a)` : C.surface2,
                color: activeTab === 'sessions' ? C.void : C.textDim,
                border: activeTab === 'sessions' ? 'none' : `1px solid ${C.border}`,
                cursor: 'pointer', fontSize: 13, fontWeight: 600
              }}
            >
              Sessions ({sessions.length})
            </button>
          </div>

          {/* Callbacks Tab */}
          {activeTab === 'callbacks' && (
            <>
              {callbacks.length === 0 ? (
                <div style={{ color: C.textDim, fontSize: 13, textAlign: 'center', padding: 40 }}>
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginBottom: 12, opacity: 0.5 }}>
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72"/>
                  </svg>
                  <p>No pending callbacks</p>
                  <p style={{ fontSize: 11, marginTop: 8 }}>When customers request a callback through AI chat, they'll appear here.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {callbacks.map(cb => (
                    <div
                      key={cb.callback_id}
                      style={{
                        padding: 12,
                        background: selectedCallback?.callback_id === cb.callback_id 
                          ? 'rgba(201,168,110,0.1)' 
                          : C.surface2,
                        border: `1px solid ${selectedCallback?.callback_id === cb.callback_id 
                          ? C.gold 
                          : C.border}`,
                        borderRadius: 8
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <span style={{ color: C.text, fontSize: 14, fontWeight: 500 }}>
                          {cb.user_name}
                        </span>
                        <span style={{ 
                          fontSize: 10, 
                          padding: '2px 8px', 
                          background: 'rgba(249,115,22,0.2)',
                          color: C.orange,
                          borderRadius: 4
                        }}>
                          PENDING
                        </span>
                      </div>
                      
                      {cb.phone && (
                        <div style={{ color: C.textDim, fontSize: 12, marginBottom: 4 }}>
                          📞 {cb.phone}
                        </div>
                      )}
                      
                      {cb.note && (
                        <div style={{ 
                          color: C.textDim, fontSize: 12, marginBottom: 8,
                          padding: 8, background: C.void, borderRadius: 6,
                          borderLeft: `2px solid ${C.gold}`
                        }}>
                          "{cb.note}"
                        </div>
                      )}
                      
                      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                        <button
                          onClick={() => acceptCallback(cb)}
                          style={{
                            flex: 1, padding: '8px 12px',
                            background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
                            color: C.void, border: 'none', borderRadius: 6,
                            fontSize: 12, fontWeight: 600, cursor: 'pointer'
                          }}
                        >
                          Accept
                        </button>
                        <button
                          onClick={() => requestScreenShare(cb.user_id, cb.user_name)}
                          style={{
                            flex: 1, padding: '8px 12px',
                            background: C.blue, color: 'white',
                            border: 'none', borderRadius: 6,
                            fontSize: 12, fontWeight: 600, cursor: 'pointer'
                          }}
                        >
                          Request Screen
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Sessions Tab */}
          {activeTab === 'sessions' && (
            <>
              <h2 style={{ color: C.text, fontSize: 14, fontWeight: 600, margin: '0 0 12px 0' }}>
                Active Screen Sessions
              </h2>

          {sessions.length === 0 ? (
            <p style={{ color: C.textDim, fontSize: 13, textAlign: 'center', padding: 20 }}>
              No active sessions
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {sessions.map(session => (
                <div
                  key={session.session_id}
                  onClick={() => watchSession(session)}
                  style={{
                    padding: 12,
                    background: selectedSession?.session_id === session.session_id 
                      ? 'rgba(201,168,110,0.1)' 
                      : C.surface2,
                    border: `1px solid ${selectedSession?.session_id === session.session_id 
                      ? C.gold 
                      : C.border}`,
                    borderRadius: 8,
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: 4
                  }}>
                    <span style={{ color: C.text, fontSize: 14, fontWeight: 500 }}>
                      {session.user_name}
                    </span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {session.has_screen && (
                        <span style={{ 
                          fontSize: 10, 
                          padding: '2px 6px', 
                          background: 'rgba(34,197,94,0.2)',
                          color: C.green,
                          borderRadius: 4
                        }}>
                          SCREEN
                        </span>
                      )}
                      {session.has_camera && (
                        <span style={{ 
                          fontSize: 10, 
                          padding: '2px 6px', 
                          background: 'rgba(201,168,110,0.2)',
                          color: C.gold,
                          borderRadius: 4
                        }}>
                          CAM
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center' 
                  }}>
                    <span style={{ color: C.textDim, fontSize: 11 }}>
                      ID: {session.session_id}
                    </span>
                    <span style={{ color: C.textDim, fontSize: 11 }}>
                      {new Date(session.started_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
            </>
          )}
        </div>

        {/* Main View Area */}
        <div style={{ flex: 1, minWidth: 300 }}>
          {!selectedSession ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 300,
              padding: 40,
              background: C.surface,
              borderRadius: 12,
              border: `1px solid ${C.border}`
            }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={C.textDim} strokeWidth="1.5">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
              <p style={{ color: C.textDim, fontSize: 13, marginTop: 12, textAlign: 'center' }}>
                Select a session to start viewing
              </p>
            </div>
          ) : (
            <div>
              {/* Session Header */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
                flexWrap: 'wrap',
                gap: 8
              }}>
                <div>
                  <h2 style={{ color: C.text, fontSize: 16, fontWeight: 600, margin: 0 }}>
                    {selectedSession.user_name}
                  </h2>
                  <span style={{ color: C.textDim, fontSize: 11 }}>
                    Session: {selectedSession.session_id}
                  </span>
                </div>
                <button
                  onClick={stopWatching}
                  style={{
                    padding: '6px 12px',
                    background: 'rgba(239,68,68,0.1)',
                    color: C.red,
                    border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontSize: 12
                  }}
                >
                  Stop Viewing
                </button>
              </div>

              {/* Split View: Screen + Camera */}
              <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
                {/* Screen Replay */}
                <div style={{
                  flex: '2 1 400px',
                  minWidth: 280,
                  background: C.surface,
                  borderRadius: 10,
                  overflow: 'hidden',
                  border: `1px solid ${C.border}`
                }}>
                  <div style={{ 
                    padding: '6px 10px', 
                    borderBottom: `1px solid ${C.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: hasScreenVideo ? C.blue : C.green,
                        animation: 'pulse 2s infinite'
                      }} />
                      <span style={{ color: C.text, fontSize: 11, fontWeight: 500 }}>
                        Screen
                      </span>
                    </div>
                    {hasScreenVideo && (
                      <span style={{ 
                        fontSize: 9, 
                        padding: '2px 6px', 
                        background: 'rgba(59,130,246,0.2)',
                        color: C.blue,
                        borderRadius: 4
                      }}>
                        LIVE VIDEO
                      </span>
                    )}
                  </div>
                  <div 
                    ref={playerContainerRef} 
                    style={{ 
                      width: '100%', 
                      minHeight: 250,
                      aspectRatio: '16/9',
                      background: '#000',
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                  >
                    {/* WebRTC Screen Video - shows when user shares full screen */}
                    <video
                      ref={remoteScreenRef}
                      autoPlay
                      playsInline
                      muted
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                        position: 'absolute',
                        inset: 0,
                        zIndex: 10,
                        background: '#000',
                        opacity: hasScreenVideo ? 1 : 0,
                        transition: 'opacity 0.3s ease'
                      }}
                    />
                    
                    {/* Waiting state - shows when no screen data */}
                    {!hasScreenVideo && (
                      <div style={{
                        position: 'absolute',
                        inset: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: C.textDim,
                        fontSize: 13,
                        zIndex: 5
                      }}>
                        <div style={{
                          width: 40, height: 40, borderRadius: '50%',
                          border: `2px solid ${C.gold}`,
                          borderTopColor: 'transparent',
                          animation: 'spin 1s linear infinite',
                          marginBottom: 12
                        }} />
                        <span>Waiting for screen data...</span>
                        <span style={{ fontSize: 11, marginTop: 4, opacity: 0.6 }}>
                          Ask user to click "Share Your Screen"
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Camera Feed */}
                <div style={{
                  flex: '1 1 180px',
                  minWidth: 150,
                  maxWidth: 250,
                  background: C.surface,
                  borderRadius: 10,
                  overflow: 'hidden',
                  border: `1px solid ${C.border}`
                }}>
                  <div style={{ 
                    padding: '6px 10px', 
                    borderBottom: `1px solid ${C.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6
                  }}>
                    <div style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: selectedSession.has_camera ? C.green : C.textDim
                    }} />
                    <span style={{ color: C.text, fontSize: 11, fontWeight: 500 }}>
                      Camera
                    </span>
                  </div>
                  <div style={{ 
                    aspectRatio: '4/3',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: '#000',
                    position: 'relative'
                  }}>
                    <video
                      ref={remoteVideoRef}
                      autoPlay
                      playsInline
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                    {!selectedSession.has_camera && (
                      <div style={{
                        position: 'absolute',
                        color: C.textDim,
                        fontSize: 11,
                        textAlign: 'center'
                      }}>
                        Camera not enabled
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Console Errors */}
              <div style={{
                background: C.surface,
                borderRadius: 10,
                border: `1px solid ${C.border}`,
                overflow: 'hidden'
              }}>
                <div style={{ 
                  padding: '6px 10px', 
                  borderBottom: `1px solid ${C.border}`,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span style={{ color: C.text, fontSize: 11, fontWeight: 500 }}>
                    Console Errors
                  </span>
                  <span style={{ 
                    color: consoleErrors.length > 0 ? C.red : C.textDim, 
                    fontSize: 10 
                  }}>
                    {consoleErrors.length} errors
                  </span>
                </div>
                <div style={{ 
                  maxHeight: 150, 
                  overflowY: 'auto',
                  padding: consoleErrors.length > 0 ? 0 : 12
                }}>
                  {consoleErrors.length === 0 ? (
                    <p style={{ color: C.textDim, fontSize: 11, textAlign: 'center', margin: 0 }}>
                      No errors captured
                    </p>
                  ) : (
                    consoleErrors.map((err, i) => (
                      <div
                        key={i}
                        style={{
                          padding: '10px 12px',
                          borderBottom: `1px solid ${C.border}`,
                        }}
                      >
                        {/* Error header */}
                        <div style={{ fontFamily: 'monospace', fontSize: 11, marginBottom: err.ai_diagnosis ? 8 : 0 }}>
                          <span style={{ color: C.red }}>
                            [{new Date(err.timestamp).toLocaleTimeString()}]
                          </span>
                          <span style={{ color: C.text, marginLeft: 8 }}>
                            {err.error}
                          </span>
                        </div>
                        
                        {/* AI Diagnosis */}
                        {err.ai_diagnosis && (
                          <div style={{
                            background: 'rgba(59,130,246,0.1)',
                            border: '1px solid rgba(59,130,246,0.2)',
                            borderRadius: 6,
                            padding: '8px 10px',
                            marginTop: 6
                          }}>
                            <div style={{ 
                              display: 'flex', 
                              alignItems: 'center', 
                              gap: 6, 
                              marginBottom: 4,
                              color: '#3b82f6',
                              fontSize: 10,
                              fontWeight: 600
                            }}>
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/>
                                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                                <line x1="12" y1="17" x2="12.01" y2="17"/>
                              </svg>
                              AI DIAGNOSIS
                            </div>
                            <div style={{ 
                              color: C.text, 
                              fontSize: 12, 
                              lineHeight: 1.5,
                              whiteSpace: 'pre-wrap'
                            }}>
                              {err.ai_diagnosis}
                            </div>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Invite Link Modal */}
      {showInviteModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000
        }}>
          <div style={{
            width: 420, background: C.surface, borderRadius: 16, padding: 24,
            border: `1px solid ${C.border}`
          }}>
            {!generatedInvite ? (
              <>
                <h2 style={{ color: C.text, fontSize: 18, fontWeight: 600, margin: '0 0 8px' }}>
                  Create Support Link
                </h2>
                <p style={{ color: C.textDim, fontSize: 13, margin: '0 0 20px' }}>
                  Generate a link to share with a customer for instant support access.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div>
                    <label style={{ color: C.textDim, fontSize: 11, display: 'block', marginBottom: 4 }}>
                      Customer Name (optional)
                    </label>
                    <input
                      type="text"
                      value={inviteForm.customer_name}
                      onChange={(e) => setInviteForm({ ...inviteForm, customer_name: e.target.value })}
                      placeholder="e.g. John Smith"
                      style={{
                        width: '100%', padding: '10px 12px', background: C.surface2,
                        border: `1px solid ${C.border}`, borderRadius: 8, color: C.text,
                        fontSize: 14, outline: 'none'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ color: C.textDim, fontSize: 11, display: 'block', marginBottom: 4 }}>
                      Customer Email (optional)
                    </label>
                    <input
                      type="email"
                      value={inviteForm.customer_email}
                      onChange={(e) => setInviteForm({ ...inviteForm, customer_email: e.target.value })}
                      placeholder="e.g. john@example.com"
                      style={{
                        width: '100%', padding: '10px 12px', background: C.surface2,
                        border: `1px solid ${C.border}`, borderRadius: 8, color: C.text,
                        fontSize: 14, outline: 'none'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ color: C.textDim, fontSize: 11, display: 'block', marginBottom: 4 }}>
                      Internal Note (optional)
                    </label>
                    <input
                      type="text"
                      value={inviteForm.note}
                      onChange={(e) => setInviteForm({ ...inviteForm, note: e.target.value })}
                      placeholder="e.g. Issue with checkout"
                      style={{
                        width: '100%', padding: '10px 12px', background: C.surface2,
                        border: `1px solid ${C.border}`, borderRadius: 8, color: C.text,
                        fontSize: 14, outline: 'none'
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
                  <button
                    onClick={resetInviteModal}
                    style={{
                      flex: 1, padding: '10px 16px', background: 'transparent',
                      color: C.textDim, border: `1px solid ${C.border}`, borderRadius: 8,
                      cursor: 'pointer', fontSize: 13
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={createInviteLink}
                    style={{
                      flex: 1, padding: '10px 16px',
                      background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
                      color: C.void, border: 'none', borderRadius: 8,
                      cursor: 'pointer', fontSize: 13, fontWeight: 600
                    }}
                  >
                    Generate Link
                  </button>
                </div>
              </>
            ) : (
              <>
                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                  <div style={{
                    width: 50, height: 50, borderRadius: '50%', margin: '0 auto 12px',
                    background: 'rgba(34,197,94,0.2)', display: 'flex',
                    alignItems: 'center', justifyContent: 'center'
                  }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={C.green} strokeWidth="2">
                      <path d="M20 6L9 17l-5-5"/>
                    </svg>
                  </div>
                  <h2 style={{ color: C.text, fontSize: 18, fontWeight: 600, margin: '0 0 4px' }}>
                    Link Created!
                  </h2>
                  <p style={{ color: C.textDim, fontSize: 13, margin: 0 }}>
                    Share this link with your customer
                  </p>
                </div>

                <div style={{
                  background: C.surface2, border: `1px solid ${C.border}`,
                  borderRadius: 8, padding: 12, marginBottom: 16
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ color: C.textDim, fontSize: 11 }}>INVITE CODE</span>
                    <span style={{ color: C.gold, fontSize: 16, fontWeight: 700, letterSpacing: 2 }}>
                      {generatedInvite.invite_code}
                    </span>
                  </div>
                  <div style={{
                    background: C.void, borderRadius: 6, padding: '10px 12px',
                    fontFamily: 'monospace', fontSize: 12, color: C.text,
                    wordBreak: 'break-all'
                  }}>
                    {generatedInvite.full_url}
                  </div>
                </div>

                <button
                  onClick={copyInviteLink}
                  style={{
                    width: '100%', padding: '12px 16px',
                    background: copySuccess ? C.green : `linear-gradient(135deg, ${C.gold}, #b8956a)`,
                    color: copySuccess ? '#fff' : C.void, border: 'none', borderRadius: 8,
                    cursor: 'pointer', fontSize: 14, fontWeight: 600,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    transition: 'background 0.2s'
                  }}
                >
                  {copySuccess ? (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 6L9 17l-5-5"/>
                      </svg>
                      Copied!
                    </>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                      </svg>
                      Copy Link
                    </>
                  )}
                </button>

                <button
                  onClick={resetInviteModal}
                  style={{
                    width: '100%', padding: '10px 16px', marginTop: 10,
                    background: 'transparent', color: C.textDim,
                    border: `1px solid ${C.border}`, borderRadius: 8,
                    cursor: 'pointer', fontSize: 13
                  }}
                >
                  Done
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* CSS animations */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
