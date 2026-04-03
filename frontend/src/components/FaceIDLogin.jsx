/**
 * FaceID Login Gate
 * Biometric authentication using facial recognition
 */

import React, { useState, useRef, useEffect } from 'react';
import { Loader, AlertCircle, Unlock, Lock } from 'lucide-react';
import * as faceapi from 'face-api.js';

const FaceIDLogin = ({ onSuccess, onFallbackToPassword }) => {
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('Initializing...');
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const storedDescriptorRef = useRef(null);

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
      // Check if FaceID is trained
      const trained = localStorage.getItem('faceid_trained');
      if (!trained) {
        setError('FaceID not setup. Please use password login to setup.');
        setLoading(false);
        return;
      }

      // Load stored descriptor
      const descriptorData = localStorage.getItem('faceid_descriptor');
      if (!descriptorData) {
        setError('FaceID data not found');
        setLoading(false);
        return;
      }

      storedDescriptorRef.current = new Float32Array(JSON.parse(descriptorData));

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
        
        // Start authentication loop
        authenticateFace();
      }
    } catch (err) {
      console.error('Camera access denied:', err);
      setError('Camera access denied');
    }
  };

  const authenticateFace = async () => {
    if (!videoRef.current || !scanning) return;

    try {
      const detection = await faceapi
        .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (detection && storedDescriptorRef.current) {
        // Draw on canvas
        if (canvasRef.current) {
          const dims = faceapi.matchDimensions(canvasRef.current, videoRef.current, true);
          const resizedDetection = faceapi.resizeResults(detection, dims);
          
          const ctx = canvasRef.current.getContext('2d');
          ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
          faceapi.draw.drawDetections(canvasRef.current, resizedDetection);
        }

        // Compare with stored descriptor
        const distance = faceapi.euclideanDistance(
          detection.descriptor,
          storedDescriptorRef.current
        );

        // Threshold: 0.6 is standard for face-api.js
        if (distance < 0.6) {
          setStatus('Face recognized! Logging in...');
          setScanning(false);
          
          // Stop camera
          if (videoRef.current.srcObject) {
            const tracks = videoRef.current.srcObject.getTracks();
            tracks.forEach(track => track.stop());
          }

          // Success - auto-login
          setTimeout(() => {
            // In production, this would trigger a backend auth call
            // For now, simulate login with stored credentials
            const email = localStorage.getItem('faceid_email') || 'teji.ss1986@gmail.com';
            onSuccess(email);
          }, 500);
          
          return;
        } else {
          setStatus(`Scanning... (confidence: ${Math.round((1 - distance) * 100)}%)`);
        }
      } else {
        setStatus('Looking for face...');
      }

    } catch (err) {
      console.error('Auth error:', err);
    }

    // Continue scanning
    if (scanning) {
      setTimeout(() => authenticateFace(), 100);
    }
  };

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
            objectFit: 'cover'
          }}
        />
        <canvas
          ref={canvasRef}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%'
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

      <button
        onClick={onFallbackToPassword}
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
