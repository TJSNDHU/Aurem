/**
 * SupportMode.jsx - Live Support Screen Sharing + Camera
 * Features:
 * - rrweb for in-app activity recording
 * - Screen Capture API for FULL screen sharing (getDisplayMedia)
 * - Picture-in-Picture for camera (floats when switching apps)
 * - Draggable panel
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import * as rrweb from 'rrweb';

const C = {
  void: "#060608",
  gold: "#c9a86e",
  goldDim: "rgba(201,168,110,0.6)",
  surface: "#0f0f11",
  text: "#f5f0e8",
  textDim: "rgba(245,240,232,0.5)",
  border: "rgba(201,168,110,0.15)",
  red: "#ef4444",
  green: "#22c55e",
  blue: "#3b82f6"
};

export default function SupportMode({ user, apiBase, onClose, initialSession }) {
  const [status, setStatus] = useState(initialSession ? 'active' : 'idle');
  const [session, setSession] = useState(initialSession || null);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [screenShareEnabled, setScreenShareEnabled] = useState(false);
  const [isPiP, setIsPiP] = useState(false);
  const [error, setError] = useState(null);
  
  // Drag state
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);
  
  // Refs
  const wsRef = useRef(null);
  const stopRecordRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const screenPeerConnectionRef = useRef(null);
  const localStreamRef = useRef(null);
  const screenStreamRef = useRef(null);
  const videoRef = useRef(null);
  const screenVideoRef = useRef(null);
  const eventsBufferRef = useRef([]);
  const flushIntervalRef = useRef(null);

  // Auto-connect if we have an initial session from invite
  useEffect(() => {
    if (initialSession && !wsRef.current) {
      connectWebSocket(initialSession);
    }
  }, [initialSession]);

  const connectWebSocket = (sess) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = apiBase.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${wsHost}/api/support/ws/user/${sess.session_id}`;
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[Support] WebSocket connected');
      startRecording();
      setStatus('active');
    };

    ws.onmessage = (event) => handleWSMessage(JSON.parse(event.data));
    ws.onerror = () => { setError('Connection error'); setStatus('error'); };
    ws.onclose = () => { if (status === 'active') stopSession(); };
  };

  // ============ DRAG HANDLERS ============
  const handleDragStart = useCallback((e) => {
    e.preventDefault();
    const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
    const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;
    dragStartRef.current = { x: clientX - position.x, y: clientY - position.y };
    setIsDragging(true);
  }, [position]);

  const handleDragMove = useCallback((e) => {
    if (!isDragging) return;
    const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
    const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;
    let newX = clientX - dragStartRef.current.x;
    let newY = clientY - dragStartRef.current.y;
    
    const panel = panelRef.current;
    if (panel) {
      const rect = panel.getBoundingClientRect();
      const maxX = window.innerWidth - rect.width - 16;
      const maxY = window.innerHeight - rect.height - 90;
      const minX = -(window.innerWidth - rect.width - 16);
      const minY = -(window.innerHeight - rect.height - 100);
      newX = Math.max(minX, Math.min(newX, maxX));
      newY = Math.max(minY, Math.min(newY, maxY));
    }
    setPosition({ x: newX, y: newY });
  }, [isDragging]);

  const handleDragEnd = useCallback(() => setIsDragging(false), []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleDragMove);
      window.addEventListener('mouseup', handleDragEnd);
      window.addEventListener('touchmove', handleDragMove);
      window.addEventListener('touchend', handleDragEnd);
    }
    return () => {
      window.removeEventListener('mousemove', handleDragMove);
      window.removeEventListener('mouseup', handleDragEnd);
      window.removeEventListener('touchmove', handleDragMove);
      window.removeEventListener('touchend', handleDragEnd);
    };
  }, [isDragging, handleDragMove, handleDragEnd]);

  // ============ SESSION MANAGEMENT ============
  const startSession = async () => {
    setStatus('connecting');
    setError(null);

    try {
      const res = await fetch(`${apiBase}/api/support/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.id || 'anonymous',
          user_name: user?.name || user?.email || 'Anonymous User'
        })
      });

      if (!res.ok) throw new Error('Failed to start session');
      const sessionData = await res.json();
      setSession(sessionData);

      // Use the shared WebSocket connection function
      connectWebSocket(sessionData);

    } catch (err) {
      console.error('[Support] Start error:', err);
      setError(err.message);
      setStatus('error');
    }
  };

  // Track watching admin to re-initiate WebRTC when needed
  const watchingAdminRef = useRef(null);

  const handleWSMessage = useCallback((data) => {
    switch (data.type) {
      case 'admin_watching':
        console.log('[Support] Admin watching:', data.admin_id);
        watchingAdminRef.current = data.admin_id;
        
        // Initiate WebRTC for any active streams
        if (localStreamRef.current) {
          console.log('[Support] Initiating WebRTC for camera');
          initiateWebRTC(data.admin_id, 'camera');
        }
        if (screenStreamRef.current) {
          console.log('[Support] Initiating WebRTC for screen');
          initiateWebRTC(data.admin_id, 'screen');
        }
        break;
      case 'webrtc_answer':
        console.log('[Support] Received WebRTC answer for:', data.stream_type);
        const pc = data.stream_type === 'screen' ? screenPeerConnectionRef.current : peerConnectionRef.current;
        if (pc) {
          pc.setRemoteDescription(new RTCSessionDescription(data.answer))
            .catch(err => console.error('[Support] Error setting remote description:', err));
        }
        break;
      case 'webrtc_ice':
        const targetPc = data.stream_type === 'screen' ? screenPeerConnectionRef.current : peerConnectionRef.current;
        if (targetPc && data.candidate) {
          targetPc.addIceCandidate(new RTCIceCandidate(data.candidate))
            .catch(err => console.error('[Support] Error adding ICE candidate:', err));
        }
        break;
      default:
        break;
    }
  }, []);

  // ============ RRWEB RECORDING (IN-APP) ============
  const startRecording = () => {
    console.log('[Support] Starting rrweb recording...');
    stopRecordRef.current = rrweb.record({
      emit: (event) => {
        eventsBufferRef.current.push(event);
      },
      sampling: { mousemove: 50, mouseInteraction: true, scroll: 150, input: 'last' },
      recordCanvas: false,
      collectFonts: false
    });

    flushIntervalRef.current = setInterval(() => {
      if (eventsBufferRef.current.length > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
        console.log('[Support] Sending rrweb events:', eventsBufferRef.current.length);
        wsRef.current.send(JSON.stringify({ type: 'rrweb_events', events: eventsBufferRef.current }));
        eventsBufferRef.current = [];
      }
    }, 500);

    // Capture console errors
    const originalError = console.error;
    console.error = (...args) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'console_error', error: args.map(String).join(' '), timestamp: Date.now() }));
      }
      originalError.apply(console, args);
    };
    
    console.log('[Support] rrweb recording started');
  };

  // ============ SCREEN CAPTURE API (FULL SCREEN) ============
  const enableScreenShare = async () => {
    try {
      console.log('[Support] Requesting screen share...');
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { 
          cursor: 'always', 
          displaySurface: 'monitor',
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      });
      
      console.log('[Support] Screen share stream obtained:', stream.id, 'tracks:', stream.getTracks().length);
      screenStreamRef.current = stream;
      if (screenVideoRef.current) screenVideoRef.current.srcObject = stream;
      
      // Handle user stopping via browser UI
      stream.getVideoTracks()[0].onended = () => {
        console.log('[Support] Screen share ended by user');
        disableScreenShare();
      };
      
      setScreenShareEnabled(true);
      console.log('[Support] Screen share enabled');
      
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'screen_share_started' }));
        console.log('[Support] Notified server of screen share start');
        
        // If admin is already watching, initiate WebRTC immediately
        if (watchingAdminRef.current) {
          console.log('[Support] Admin already watching:', watchingAdminRef.current, '- initiating WebRTC for screen share');
          setTimeout(() => {
            initiateWebRTC(watchingAdminRef.current, 'screen');
          }, 200); // Small delay to ensure stream is ready
        } else {
          console.log('[Support] No admin watching yet, will initiate WebRTC when admin connects');
        }
      }
    } catch (err) {
      console.error('[Support] Screen share error:', err);
      if (err.name !== 'NotAllowedError') setError('Screen share failed');
    }
  };

  const disableScreenShare = () => {
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach(track => track.stop());
      screenStreamRef.current = null;
    }
    if (screenPeerConnectionRef.current) {
      screenPeerConnectionRef.current.close();
      screenPeerConnectionRef.current = null;
    }
    setScreenShareEnabled(false);
  };

  // ============ CAMERA + PICTURE-IN-PICTURE ============
  const enableCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false
      });
      localStreamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraEnabled(true);
      
      // If admin is already watching, initiate WebRTC immediately
      if (watchingAdminRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
        console.log('[Support] Admin already watching, initiating WebRTC for camera');
        setTimeout(() => {
          initiateWebRTC(watchingAdminRef.current, 'camera');
        }, 100);
      }
    } catch (err) {
      console.error('[Support] Camera error:', err);
      setError('Camera access denied');
    }
  };

  const disableCamera = () => {
    if (document.pictureInPictureElement) document.exitPictureInPicture().catch(() => {});
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
      localStreamRef.current = null;
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    setCameraEnabled(false);
    setIsPiP(false);
  };

  const togglePiP = async () => {
    if (!videoRef.current) return;
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setIsPiP(false);
      } else if (document.pictureInPictureEnabled) {
        await videoRef.current.requestPictureInPicture();
        setIsPiP(true);
        videoRef.current.onleavepictureinpicture = () => setIsPiP(false);
      }
    } catch (err) {
      console.error('[Support] PiP error:', err);
    }
  };

  // ============ WEBRTC ============
  const initiateWebRTC = async (adminId, streamType = 'camera') => {
    try {
      const stream = streamType === 'screen' ? screenStreamRef.current : localStreamRef.current;
      
      if (!stream) {
        console.error('[Support] No stream available for:', streamType);
        return;
      }
      
      const tracks = stream.getTracks();
      console.log('[Support] Creating WebRTC peer connection for:', streamType, 'admin:', adminId, 'tracks:', tracks.length);
      tracks.forEach(t => console.log('[Support] Track:', t.kind, t.label, t.readyState));
      
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
        // Close existing connection
        if (screenPeerConnectionRef.current) {
          console.log('[Support] Closing existing screen peer connection');
          screenPeerConnectionRef.current.close();
        }
        screenPeerConnectionRef.current = pc;
      } else {
        if (peerConnectionRef.current) {
          console.log('[Support] Closing existing camera peer connection');
          peerConnectionRef.current.close();
        }
        peerConnectionRef.current = pc;
      }
      
      // Add tracks from stream
      stream.getTracks().forEach(track => {
        console.log('[Support] Adding track to peer connection:', track.kind, 'for:', streamType);
        pc.addTrack(track, stream);
      });

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          console.log('[Support] ICE candidate generated for:', streamType);
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ 
              type: 'webrtc_ice', 
              candidate: event.candidate, 
              target_admin: adminId, 
              stream_type: streamType 
            }));
          }
        } else {
          console.log('[Support] ICE gathering complete for:', streamType);
        }
      };
      
      pc.oniceconnectionstatechange = () => {
        console.log('[Support] ICE connection state for', streamType, ':', pc.iceConnectionState);
      };
      
      pc.onconnectionstatechange = () => {
        console.log('[Support] WebRTC connection state for', streamType, ':', pc.connectionState);
      };
      
      pc.onnegotiationneeded = () => {
        console.log('[Support] Negotiation needed for:', streamType);
      };

      const offer = await pc.createOffer();
      console.log('[Support] Created offer for:', streamType, 'SDP length:', offer.sdp?.length);
      
      await pc.setLocalDescription(offer);
      console.log('[Support] Set local description for:', streamType);

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ 
          type: 'webrtc_offer', 
          offer, 
          target_admin: adminId, 
          stream_type: streamType 
        }));
        console.log('[Support] Sent WebRTC offer for:', streamType, 'to admin:', adminId);
      } else {
        console.error('[Support] WebSocket not open, cannot send offer');
      }
    } catch (err) {
      console.error('[Support] WebRTC initiation error:', err);
    }
  };

  // ============ STOP SESSION ============
  const stopSession = async () => {
    if (stopRecordRef.current) { stopRecordRef.current(); stopRecordRef.current = null; }
    if (flushIntervalRef.current) { clearInterval(flushIntervalRef.current); flushIntervalRef.current = null; }
    disableCamera();
    disableScreenShare();
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    if (session) {
      try { await fetch(`${apiBase}/api/support/end/${session.session_id}`, { method: 'POST' }); } catch (e) {}
    }
    setSession(null);
    setStatus('idle');
    eventsBufferRef.current = [];
  };

  useEffect(() => { return () => { if (status === 'active') stopSession(); }; }, []);

  const pipSupported = typeof document !== 'undefined' && document.pictureInPictureEnabled;

  return (
    <div ref={panelRef} style={{
      position: 'fixed', bottom: 90, right: 16, width: 320,
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 16,
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 1000,
      transform: `translate(${position.x}px, ${position.y}px)`,
      transition: isDragging ? 'none' : 'transform 0.1s ease-out', userSelect: 'none'
    }}>
      {/* Header */}
      <div onMouseDown={handleDragStart} onTouchStart={handleDragStart} style={{ 
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 16px', borderBottom: `1px solid ${C.border}`,
        cursor: isDragging ? 'grabbing' : 'grab', borderRadius: '16px 16px 0 0',
        background: isDragging ? 'rgba(201,168,110,0.1)' : 'transparent'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginRight: 4 }}>
            {[0,1].map(i => <div key={i} style={{ display: 'flex', gap: 2 }}>
              {[0,1].map(j => <div key={j} style={{ width: 3, height: 3, borderRadius: '50%', background: C.textDim }}/>)}
            </div>)}
          </div>
          <div style={{ width: 10, height: 10, borderRadius: '50%',
            background: status === 'active' ? C.green : status === 'connecting' ? C.gold : C.textDim,
            animation: status === 'active' ? 'pulse 2s infinite' : 'none'
          }} />
          <span style={{ color: C.text, fontWeight: 600, fontSize: 14 }}>Live Support</span>
        </div>
        <button onClick={(e) => { e.stopPropagation(); onClose(); }} style={{
          background: 'none', border: 'none', color: C.textDim, cursor: 'pointer', fontSize: 18, padding: '0 4px'
        }}>×</button>
      </div>

      {/* Content */}
      <div style={{ padding: '16px 20px 20px' }}>
        {status === 'idle' && (
          <div>
            <p style={{ color: C.textDim, fontSize: 13, marginBottom: 16, lineHeight: 1.5 }}>
              Share your screen with our support team to get help faster. Your privacy is protected.
            </p>
            <button onClick={startSession} style={{
              width: '100%', padding: '12px 16px', background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
              color: C.void, border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer', fontSize: 14
            }}>Share with Support</button>
          </div>
        )}

        {status === 'connecting' && (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <div style={{ width: 40, height: 40, border: `3px solid ${C.border}`, borderTopColor: C.gold,
              borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
            <p style={{ color: C.textDim, fontSize: 13 }}>Connecting...</p>
          </div>
        )}

        {status === 'active' && (
          <div>
            {/* Status */}
            <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)',
              borderRadius: 8, padding: 10, marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.green }} />
                <span style={{ color: C.green, fontSize: 12 }}>Session Active</span>
              </div>
              <p style={{ color: C.textDim, fontSize: 10, margin: '4px 0 0 12px' }}>ID: {session?.session_id}</p>
            </div>

            {/* SCREEN SHARE - Full Screen Capture - PROMINENT */}
            <div style={{ marginBottom: 12 }}>
              {!screenShareEnabled ? (
                <div>
                  <button onClick={enableScreenShare} style={{
                    width: '100%', padding: '14px 16px', 
                    background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                    color: 'white', border: 'none', borderRadius: 10,
                    cursor: 'pointer', fontSize: 14, fontWeight: 600,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                    boxShadow: '0 4px 12px rgba(59,130,246,0.3)'
                  }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
                    </svg>
                    Share Your Screen
                  </button>
                  <p style={{ color: C.textDim, fontSize: 10, textAlign: 'center', marginTop: 6 }}>
                    Best for showing issues - support team sees exactly what you see
                  </p>
                </div>
              ) : (
                <div style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.4)', borderRadius: 10, padding: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ color: '#60a5fa', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#3b82f6', animation: 'pulse 2s infinite' }} />
                      Screen Sharing Active
                    </span>
                    <button onClick={disableScreenShare} style={{
                      background: 'rgba(239,68,68,0.2)', color: C.red, border: 'none', borderRadius: 6,
                      padding: '6px 12px', fontSize: 11, cursor: 'pointer', fontWeight: 500
                    }}>Stop Sharing</button>
                  </div>
                  <video ref={screenVideoRef} autoPlay muted playsInline style={{
                    width: '100%', borderRadius: 8, background: '#000', maxHeight: 140
                  }} />
                </div>
              )}
            </div>

            {/* CAMERA with PiP */}
            <div style={{ marginBottom: 12 }}>
              {!cameraEnabled ? (
                <button onClick={enableCamera} style={{
                  width: '100%', padding: '10px 14px', background: 'rgba(201,168,110,0.1)',
                  color: C.gold, border: `1px solid ${C.border}`, borderRadius: 8,
                  cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8
                }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/>
                  </svg>
                  Enable Camera
                </button>
              ) : (
                <div style={{ background: 'rgba(201,168,110,0.1)', border: `1px solid ${C.border}`, borderRadius: 8, padding: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ color: C.gold, fontSize: 11 }}>Camera</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {pipSupported && (
                        <button onClick={togglePiP} title="Picture-in-Picture - Float when switching apps" style={{
                          background: isPiP ? C.gold : 'rgba(201,168,110,0.2)', color: isPiP ? C.void : C.gold,
                          border: 'none', borderRadius: 4, padding: '4px 8px', fontSize: 10, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: 4
                        }}>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="2" y="2" width="20" height="20" rx="2"/><rect x="11" y="11" width="9" height="9" rx="1" fill="currentColor"/>
                          </svg>
                          {isPiP ? 'Exit PiP' : 'Float'}
                        </button>
                      )}
                      <button onClick={disableCamera} style={{
                        background: 'rgba(239,68,68,0.2)', color: C.red, border: 'none', borderRadius: 4,
                        padding: '4px 8px', fontSize: 10, cursor: 'pointer'
                      }}>Off</button>
                    </div>
                  </div>
                  <video ref={videoRef} autoPlay muted playsInline style={{
                    width: '100%', borderRadius: 6, background: C.void, maxHeight: 100
                  }} />
                  {isPiP && <p style={{ color: C.gold, fontSize: 10, textAlign: 'center', margin: '6px 0 0' }}>
                    ✓ Camera floating - visible when you switch apps
                  </p>}
                </div>
              )}
            </div>

            {/* End Session */}
            <button onClick={stopSession} style={{
              width: '100%', padding: '10px 16px', background: 'rgba(239,68,68,0.1)',
              color: C.red, border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8,
              cursor: 'pointer', fontSize: 13, fontWeight: 600
            }}>End Support Session</button>
          </div>
        )}

        {status === 'error' && (
          <div>
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 8, padding: 12, marginBottom: 16 }}>
              <p style={{ color: C.red, fontSize: 13, margin: 0 }}>{error || 'Connection failed'}</p>
            </div>
            <button onClick={startSession} style={{
              width: '100%', padding: '10px 16px', background: C.gold, color: C.void,
              border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600
            }}>Try Again</button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
