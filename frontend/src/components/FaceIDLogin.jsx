/**
 * FaceID Login Gate
 * Biometric authentication using facial recognition
 * Fetches stored face descriptor from backend
 * Falls back to PIN entry if face verification fails
 */

import React, { useState, useRef, useEffect } from 'react';
import { Loader, AlertCircle, Unlock, Lock } from 'lucide-react';
import * as faceapi from 'face-api.js';
import PINEntry from './PINEntry';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FaceIDLogin = ({ email, onSuccess, onFallbackToPassword }) => {
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [showPinEntry, setShowPinEntry] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('Initializing...');
  const [attemptCount, setAttemptCount] = useState(0);
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const emailRef = useRef(email);

  useEffect(() => {
    initFaceID();
    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks();
        tracks.forEach(track => track.stop());
      }
    };
  }, []);

  const initFaceID = async () => {
    try {
      // Check if user has biometric enabled in backend
      const statusResponse = await fetch(`${API_URL}/api/biometric/status/${emailRef.current}`);
      
      if (!statusResponse.ok) {
        setError('Biometric not setup. Please use password login.');
        setLoading(false);
        return;
      }

      const statusData = await statusResponse.json();
      
      if (!statusData.biometric_enabled) {
        setError('Biometric not setup for this account');
        setLoading(false);
        return;
      }

      console.log('[FaceID Login] Biometric enabled - loading models...');

      // Load models
      setStatus('Loading face recognition models...');
      const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model';
      
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
      await faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL);
      await faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL);

      setStatus('Starting camera...');
      await startCamera();
      
      setLoading(false);
      setScanning(true);
      
    } catch (err) {
      console.error('FaceID init failed:', err);
      setError('Failed to initialize FaceID');
      setLoading(false);
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        
        setStatus('Camera ready. Scanning for face...');
        console.log('[FaceID Login] Camera started successfully');
        
        // Start authentication loop
        authenticateFace();
      }
    } catch (err) {
      console.error('Camera access denied:', err);
      setError('Camera access denied');
      setStatus('Camera error');
    }
  };

  const authenticateFace = async () => {
    if (!videoRef.current || !scanning) return;

    try {
      const detection = await faceapi
        .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (detection) {
        // Draw on canvas
        if (canvasRef.current) {
          const dims = faceapi.matchDimensions(canvasRef.current, videoRef.current, true);
          const resizedDetection = faceapi.resizeResults(detection, dims);
          
          const ctx = canvasRef.current.getContext('2d');
          ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
          
          // Flip context for mirrored drawing
          ctx.save();
          ctx.scale(-1, 1);
          ctx.translate(-canvasRef.current.width, 0);
          
          faceapi.draw.drawDetections(canvasRef.current, resizedDetection);
          
          ctx.restore();
        }

        // Send to backend for verification
        setStatus('Verifying face...');
        
        const response = await fetch(`${API_URL}/api/biometric/verify-face`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: emailRef.current,
            face_descriptor: Array.from(detection.descriptor)
          })
        });

        const data = await response.json();

        if (response.ok && data.success) {
          setStatus('Face recognized! Logging in...');
          setScanning(false);
          
          // Stop camera
          if (videoRef.current.srcObject) {
            const tracks = videoRef.current.srcObject.getTracks();
            tracks.forEach(track => track.stop());
          }

          // Success - trigger login
          setTimeout(() => {
            onSuccess(emailRef.current);
          }, 500);
          
          return;
        } else {
          // Face not recognized - increment attempt count
          const newCount = attemptCount + 1;
          setAttemptCount(newCount);
          
          setStatus(`${data.message} - Attempt ${newCount}/3`);
          
          // After 3 failed attempts, offer PIN fallback
          if (newCount >= 3) {
            setScanning(false);
            if (videoRef.current.srcObject) {
              const tracks = videoRef.current.srcObject.getTracks();
              tracks.forEach(track => track.stop());
            }
            setShowPinEntry(true);
            return;
          }
        }
      } else {
        setStatus('Looking for face...');
      }

    } catch (err) {
      console.error('Auth error:', err);
      setStatus('Verification error - retrying...');
    }

    // Continue scanning
    if (scanning) {
      setTimeout(() => authenticateFace(), 100);
    }
  };

  // Show PIN entry if face recognition failed 3 times
  if (showPinEntry) {
    return (
      <PINEntry
        email={emailRef.current}
        onSuccess={onSuccess}
        onBack={() => {
          setShowPinEntry(false);
          setAttemptCount(0);
          setScanning(false);
          setLoading(true);
          initFaceID();
        }}
      />
    );
  }

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 40
      }}>
        <Loader className="w-12 h-12 text-[#D4AF37] animate-spin mb-4" />
        <p style={{fontSize: 14, color: '#888'}}>{status}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 40
      }}>
        <AlertCircle className="w-12 h-12 text-[#F44] mb-4" />
        <p style={{fontSize: 14, color: '#F88', marginBottom: 16, textAlign: 'center'}}>
          {error}
        </p>
        <button
          onClick={onFallbackToPassword}
          data-testid="use-password-fallback-button"
          style={{
            padding: '10px 24px',
            background: '#1A1A1A',
            border: '1px solid #333',
            borderRadius: 8,
            color: '#F4F4F4',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Use Password Instead
        </button>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: 24
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 16
      }}>
        <Lock className="w-8 h-8 text-[#D4AF37]" />
        <div>
          <h2 style={{fontSize: 18, fontWeight: 600, color: '#F4F4F4'}}>
            FaceID Authentication
          </h2>
          <p style={{fontSize: 12, color: '#888'}}>
            Position your face in the camera
          </p>
        </div>
      </div>

      {/* Video Feed */}
      <div style={{
        position: 'relative',
        width: 480,
        height: 360,
        background: '#000',
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 16,
        border: '2px solid #1A1A1A'
      }}>
        <video
          ref={videoRef}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: 'scaleX(-1)'  /* Mirror for natural view */
          }}
        />
        <canvas
          ref={canvasRef}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            transform: 'scaleX(-1)'  /* Match video mirror */
          }}
        />

        {/* Status Overlay */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: 16,
          background: 'linear-gradient(to top, rgba(0,0,0,0.8), transparent)',
          textAlign: 'center'
        }}>
          <p style={{
            fontSize: 13,
            color: '#F4F4F4',
            fontWeight: 600
          }}>
            {status}
          </p>
        </div>

        {/* Scanning Animation */}
        {scanning && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 200,
            height: 200,
            border: '2px solid #D4AF37',
            borderRadius: '50%',
            animation: 'scan 2s infinite'
          }} />
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <button
          onClick={onFallbackToPassword}
          data-testid="use-password-button"
          style={{
            padding: '8px 16px',
            background: 'none',
            border: '1px solid #333',
            borderRadius: 8,
            color: '#888',
            fontSize: 12,
            cursor: 'pointer'
          }}
        >
          Use Password Instead
        </button>

        <button
          onClick={() => setShowPinEntry(true)}
          data-testid="use-pin-button"
          style={{
            padding: '8px 16px',
            background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 8,
            color: '#050505',
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Use PIN Instead
        </button>
      </div>

      <style jsx>{`
        @keyframes scan {
          0%, 100% {
            opacity: 1;
            transform: translate(-50%, -50%) scale(1);
          }
          50% {
            opacity: 0.5;
            transform: translate(-50%, -50%) scale(1.1);
          }
        }
      `}</style>
    </div>
  );
};

export default FaceIDLogin;
