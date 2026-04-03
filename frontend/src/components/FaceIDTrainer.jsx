/**
 * FaceID Training Interface
 * Captures user's face data for biometric authentication
 * Part 1 of biometric setup (followed by PIN setup)
 */

import React, { useState, useRef, useEffect } from 'react';
import { Camera, CheckCircle, AlertCircle, Loader, User } from 'lucide-react';
import * as faceapi from 'face-api.js';
import PINSetup from './PINSetup';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FaceIDTrainer = ({ email, onComplete }) => {
  const [loading, setLoading] = useState(true);
  const [capturing, setCapturing] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [showPinSetup, setShowPinSetup] = useState(false);
  const [error, setError] = useState(null);
  const [faceDetected, setFaceDetected] = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [status, setStatus] = useState('Initializing...');
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const faceDescriptorRef = useRef(null);

  useEffect(() => {
    loadModels();
    return () => {
      // Cleanup
      if (videoRef.current && videoRef.current.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks();
        tracks.forEach(track => track.stop());
      }
    };
  }, []);

  const loadModels = async () => {
    try {
      setLoading(true);
      setStatus('Loading face recognition models...');
      
      // Load face-api.js models from CDN
      const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model';
      
      console.log('[FaceID] Loading models from:', MODEL_URL);
      
      await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
      ]);
      
      setModelsLoaded(true);
      setLoading(false);
      setStatus('Models loaded. Ready to start camera.');
      console.log('[FaceID] All models loaded successfully');
    } catch (err) {
      console.error('[FaceID] Failed to load models:', err);
      setError(`Failed to load face recognition models: ${err.message}`);
      setLoading(false);
    }
  };

  const startCamera = async () => {
    try {
      setError(null); // Clear any previous errors
      setStatus('Starting camera...');
      
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { 
          width: 640, 
          height: 480,
          facingMode: 'user' // Use front camera on mobile
        }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        
        setCapturing(true);
        setStatus('Camera started. Detecting face...');
        console.log('[FaceID] Camera started, beginning face detection');
        
        // Wait for video to stabilize, then start detection
        setTimeout(() => {
          console.log('[FaceID] Starting detection loop');
          detectFace();
        }, 1000); // Increased to 1 second for better stability
      }
    } catch (err) {
      console.error('[FaceID] Camera error:', err);
      let errorMessage = 'Camera access denied. Please allow camera access.';
      
      if (err.name === 'NotFoundError') {
        errorMessage = 'No camera found on this device.';
      } else if (err.name === 'NotAllowedError') {
        errorMessage = 'Camera permission denied. Please enable camera in browser settings.';
      } else if (err.name === 'NotReadableError') {
        errorMessage = 'Camera is in use by another application.';
      }
      
      setError(errorMessage);
      setLoading(false);
      setStatus('');
    }
  };

  const detectFace = async () => {
    if (!videoRef.current || !modelsLoaded || !capturing) {
      console.log('[FaceID] Detection skipped:', { 
        hasVideo: !!videoRef.current, 
        modelsLoaded, 
        capturing 
      });
      return;
    }

    try {
      console.log('[FaceID] Running face detection...');
      
      const detection = await faceapi
        .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({
          inputSize: 224,
          scoreThreshold: 0.5
        }))
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (detection) {
        console.log('[FaceID] Face detected! Score:', detection.detection.score);
        setFaceDetected(true);
        setStatus('Face detected! Position steady...');
        
        // Draw detection on canvas
        if (canvasRef.current && videoRef.current) {
          const dims = faceapi.matchDimensions(canvasRef.current, videoRef.current, true);
          const resizedDetection = faceapi.resizeResults(detection, dims);
          
          const ctx = canvasRef.current.getContext('2d');
          ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
          
          // Flip context for mirrored drawing
          ctx.save();
          ctx.scale(-1, 1);
          ctx.translate(-canvasRef.current.width, 0);
          
          faceapi.draw.drawDetections(canvasRef.current, resizedDetection);
          faceapi.draw.drawFaceLandmarks(canvasRef.current, resizedDetection);
          
          ctx.restore();
        }
      } else {
        console.log('[FaceID] No face detected in frame');
        setFaceDetected(false);
        setStatus('Looking for face...');
      }
    } catch (err) {
      console.error('[FaceID] Detection error:', err);
      setStatus('Detection error - retrying...');
    }

    // Continue detection loop
    if (capturing && !captured) {
      setTimeout(() => detectFace(), 100);
    }
  };

  const captureFace = async () => {
    if (!videoRef.current || !modelsLoaded) return;

    setCapturing(false);

    try {
      // Capture multiple face descriptors for better accuracy
      const descriptors = [];
      
      for (let i = 0; i < 3; i++) {
        const detection = await faceapi
          .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
          .withFaceLandmarks()
          .withFaceDescriptor();

        if (detection) {
          descriptors.push(detection.descriptor);
        }
        
        // Small delay between captures
        await new Promise(resolve => setTimeout(resolve, 500));
      }

      if (descriptors.length === 0) {
        setError('No face detected. Please try again.');
        setCapturing(true);
        detectFace();
        return;
      }

      // Average the descriptors
      const avgDescriptor = new Float32Array(128);
      for (let i = 0; i < 128; i++) {
        let sum = 0;
        descriptors.forEach(desc => sum += desc[i]);
        avgDescriptor[i] = sum / descriptors.length;
      }

      faceDescriptorRef.current = Array.from(avgDescriptor);
      
      setCaptured(true);
      
      // Stop camera
      if (videoRef.current.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks();
        tracks.forEach(track => track.stop());
      }

      // Move to PIN setup after short delay
      setTimeout(() => {
        setShowPinSetup(true);
      }, 1500);

    } catch (err) {
      console.error('Face capture failed:', err);
      setError('Failed to capture face data');
      setCapturing(true);
      detectFace();
    }
  };

  const skipFaceID = () => {
    // User chose to skip biometric setup entirely
    console.log('[FaceID] User skipped biometric setup');
    
    // Stop camera if running
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach(track => track.stop());
    }
    
    // Mark as skipped in localStorage (no backend setup)
    localStorage.setItem('faceid_trained', 'skipped');
    
    // Proceed to dashboard
    if (onComplete) {
      onComplete();
    }
  };

  // If showing PIN setup, render that instead
  if (showPinSetup) {
    return (
      <PINSetup
        email={email}
        faceDescriptor={faceDescriptorRef.current}
        onComplete={onComplete}
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
        minHeight: 400,
        padding: 40
      }}>
        <Loader className="w-12 h-12 text-[#D4AF37] animate-spin mb-4" />
        <p style={{fontSize: 14, color: '#888'}}>Loading face recognition models...</p>
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
      <h2 style={{
        fontSize: 20,
        fontWeight: 600,
        color: '#F4F4F4',
        marginBottom: 8,
        textAlign: 'center'
      }}>
        Setup FaceID Authentication
      </h2>
      <p style={{
        fontSize: 13,
        color: '#888',
        marginBottom: 24,
        textAlign: 'center',
        maxWidth: 400
      }}>
        Position your face in the frame. We'll capture your biometric data for secure login.
      </p>

      {error && (
        <div style={{
          padding: 12,
          background: '#1A0A0A',
          border: '1px solid #3A1A1A',
          borderRadius: 8,
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <AlertCircle className="w-4 h-4 text-[#F44]" />
          <span style={{fontSize: 12, color: '#F88'}}>{error}</span>
        </div>
      )}

      {/* Video Feed */}
      <div style={{
        position: 'relative',
        width: 640,
        height: 480,
        background: '#000',
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 16
      }}>
        <video
          ref={videoRef}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: 'scaleX(-1)'  /* Fix: Mirror video to show natural view */
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
        {capturing && (
          <div style={{
            position: 'absolute',
            top: 16,
            left: 16,
            padding: '8px 12px',
            background: faceDetected ? '#0A2A0A' : '#2A0A0A',
            border: `1px solid ${faceDetected ? '#2A5A2A' : '#5A2A2A'}`,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            zIndex: 10
          }}>
            <div style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: faceDetected ? '#4A4' : '#F44',
              animation: 'pulse 2s infinite'
            }} />
            <span style={{
              fontSize: 11,
              color: faceDetected ? '#4A4' : '#F44',
              fontWeight: 600,
              textTransform: 'uppercase'
            }}>
              {status || (faceDetected ? 'Face Detected' : 'Looking for face...')}
            </span>
          </div>
        )}

        {/* Captured Overlay */}
        {captured && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'rgba(0, 150, 0, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <CheckCircle className="w-24 h-24 text-[#4A4]" />
          </div>
        )}
      </div>

      {/* Controls */}
      {!capturing && !captured && (
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={startCamera}
            disabled={!modelsLoaded}
            data-testid="start-camera-button"
            style={{
              padding: '12px 32px',
              background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
              border: 'none',
              borderRadius: 8,
              color: '#050505',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            <Camera className="w-5 h-5" />
            Start Camera
          </button>
          
          <button
            onClick={skipFaceID}
            data-testid="skip-faceid-button"
            style={{
              padding: '12px 32px',
              background: 'transparent',
              border: '1px solid #444',
              borderRadius: 8,
              color: '#888',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            Skip for now
          </button>
        </div>
      )}

      {capturing && !captured && (
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={captureFace}
            data-testid="manual-capture-button"
            style={{
              padding: '12px 32px',
              background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
              border: 'none',
              borderRadius: 8,
              color: '#050505',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            <CheckCircle className="w-5 h-5" />
            Capture Now
          </button>
          
          <button
            onClick={skipFaceID}
            data-testid="skip-faceid-button"
            style={{
              padding: '12px 32px',
              background: 'transparent',
              border: '1px solid #444',
              borderRadius: 8,
              color: '#888',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            Skip for now
          </button>
        </div>
      )}

      {captured && (
        <div style={{textAlign: 'center'}}>
          <p style={{fontSize: 14, color: '#4A4', marginBottom: 8}}>
            ✅ FaceID data captured successfully!
          </p>
          <p style={{fontSize: 12, color: '#888'}}>
            Redirecting to dashboard...
          </p>
        </div>
      )}

      <style jsx>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
      `}</style>
    </div>
  );
};

export default FaceIDTrainer;
