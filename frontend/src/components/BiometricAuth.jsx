/**
 * Biometric Authentication Components
 * Face Recognition, Voice Recognition, Fingerprint/WebAuthn
 * For ReRoots AI commercial system access control
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════════════════════
// WEBAUTHN (FINGERPRINT / FACE ID / WINDOWS HELLO)
// ═══════════════════════════════════════════════════════════════════════════════

export const useWebAuthn = () => {
  const [isSupported, setIsSupported] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Check WebAuthn support
    setIsSupported(
      window.PublicKeyCredential !== undefined &&
      typeof window.PublicKeyCredential === 'function'
    );
  }, []);

  const register = useCallback(async (userId, userName, displayName) => {
    if (!isSupported) {
      setError('WebAuthn not supported in this browser');
      return { success: false, error: 'Not supported' };
    }

    setIsLoading(true);
    setError(null);

    try {
      // Start registration
      const startRes = await fetch(`${API_URL}/api/biometric/webauthn/register/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          user_name: userName,
          user_display_name: displayName || userName
        })
      });

      if (!startRes.ok) throw new Error('Failed to start registration');
      const { options, challenge } = await startRes.json();

      // Decode challenge and user ID for WebAuthn
      const publicKeyOptions = {
        ...options,
        challenge: Uint8Array.from(atob(options.challenge.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)),
        user: {
          ...options.user,
          id: Uint8Array.from(atob(options.user.id.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
        },
        excludeCredentials: options.excludeCredentials?.map(cred => ({
          ...cred,
          id: Uint8Array.from(atob(cred.id.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
        })) || []
      };

      // Create credential
      const credential = await navigator.credentials.create({
        publicKey: publicKeyOptions
      });

      // Encode response for sending to server
      const credentialResponse = {
        id: credential.id,
        rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
        type: credential.type,
        response: {
          clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
          attestationObject: btoa(String.fromCharCode(...new Uint8Array(credential.response.attestationObject))),
          transports: credential.response.getTransports?.() || ['internal']
        }
      };

      // Finish registration
      const finishRes = await fetch(`${API_URL}/api/biometric/webauthn/register/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          credential: credentialResponse,
          challenge
        })
      });

      if (!finishRes.ok) throw new Error('Failed to finish registration');
      const result = await finishRes.json();

      setIsLoading(false);
      return { success: true, ...result };

    } catch (err) {
      setError(err.message);
      setIsLoading(false);
      return { success: false, error: err.message };
    }
  }, [isSupported]);

  const authenticate = useCallback(async (userId) => {
    if (!isSupported) {
      setError('WebAuthn not supported');
      return { success: false, error: 'Not supported' };
    }

    setIsLoading(true);
    setError(null);

    try {
      // Start authentication
      const startRes = await fetch(`${API_URL}/api/biometric/webauthn/auth/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });

      if (!startRes.ok) {
        const errData = await startRes.json();
        throw new Error(errData.detail || 'Failed to start authentication');
      }
      const { options, challenge } = await startRes.json();

      // Decode challenge and credentials
      const publicKeyOptions = {
        ...options,
        challenge: Uint8Array.from(atob(options.challenge.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)),
        allowCredentials: options.allowCredentials?.map(cred => ({
          ...cred,
          id: Uint8Array.from(atob(cred.id.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
        })) || []
      };

      // Get credential
      const credential = await navigator.credentials.get({
        publicKey: publicKeyOptions
      });

      // Encode response
      const credentialResponse = {
        id: credential.id,
        rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
        type: credential.type,
        response: {
          clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
          authenticatorData: btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData))),
          signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature))),
          userHandle: credential.response.userHandle 
            ? btoa(String.fromCharCode(...new Uint8Array(credential.response.userHandle)))
            : null
        }
      };

      // Finish authentication
      const finishRes = await fetch(`${API_URL}/api/biometric/webauthn/auth/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          credential: credentialResponse,
          challenge
        })
      });

      if (!finishRes.ok) throw new Error('Authentication failed');
      const result = await finishRes.json();

      setIsLoading(false);
      return { success: true, ...result };

    } catch (err) {
      setError(err.message);
      setIsLoading(false);
      return { success: false, error: err.message };
    }
  }, [isSupported]);

  return {
    isSupported,
    isLoading,
    error,
    register,
    authenticate
  };
};


// ═══════════════════════════════════════════════════════════════════════════════
// FACE RECOGNITION COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export const FaceRecognition = ({
  userId,
  mode = 'verify', // 'enroll' or 'verify'
  onSuccess,
  onError,
  onClose,
  requiredSamples = 5
}) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [faceApiLoaded, setFaceApiLoaded] = useState(false);
  const [samples, setSamples] = useState([]);
  const [status, setStatus] = useState('Initializing camera...');
  const [faceDetected, setFaceDetected] = useState(false);
  const streamRef = useRef(null);
  const faceapiRef = useRef(null);

  // Load face-api.js dynamically
  useEffect(() => {
    const loadFaceApi = async () => {
      if (window.faceapi) {
        faceapiRef.current = window.faceapi;
        setFaceApiLoaded(true);
        return;
      }

      try {
        // Load face-api.js from CDN
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js';
        script.async = true;
        
        script.onload = async () => {
          faceapiRef.current = window.faceapi;
          
          // Load models from CDN
          const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model';
          await Promise.all([
            faceapiRef.current.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
            faceapiRef.current.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
            faceapiRef.current.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
          ]);
          
          setFaceApiLoaded(true);
          setStatus('Camera ready');
        };
        
        document.body.appendChild(script);
      } catch (err) {
        setStatus('Failed to load face detection');
        onError?.('Failed to load face detection library');
      }
    };

    loadFaceApi();
  }, [onError]);

  // Start camera
  useEffect(() => {
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: 640, height: 480 }
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          streamRef.current = stream;
        }
        setIsLoading(false);
      } catch (err) {
        setStatus('Camera access denied');
        onError?.('Camera access denied');
      }
    };

    if (faceApiLoaded) {
      startCamera();
    }

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [faceApiLoaded, onError]);

  // Face detection loop
  useEffect(() => {
    if (!faceApiLoaded || isLoading || !videoRef.current) return;

    const faceapi = faceapiRef.current;
    let animationId;

    const detectFace = async () => {
      if (!videoRef.current || !canvasRef.current) return;

      const detections = await faceapi
        .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

      const canvas = canvasRef.current;
      const displaySize = { width: videoRef.current.videoWidth, height: videoRef.current.videoHeight };
      faceapi.matchDimensions(canvas, displaySize);

      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (detections) {
        setFaceDetected(true);
        
        // Draw face box
        const resizedDetections = faceapi.resizeResults(detections, displaySize);
        faceapi.draw.drawDetections(canvas, resizedDetections);
        
        if (mode === 'enroll') {
          setStatus(`Face detected! Samples: ${samples.length}/${requiredSamples}`);
        } else {
          setStatus('Face detected! Click Verify');
        }
      } else {
        setFaceDetected(false);
        setStatus('Position your face in the camera');
      }

      animationId = requestAnimationFrame(detectFace);
    };

    videoRef.current.onloadedmetadata = () => {
      detectFace();
    };

    return () => {
      if (animationId) cancelAnimationFrame(animationId);
    };
  }, [faceApiLoaded, isLoading, mode, samples.length, requiredSamples]);

  // Capture face sample
  const captureSample = async () => {
    if (!faceDetected || !videoRef.current) return;

    const faceapi = faceapiRef.current;
    const detections = await faceapi
      .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (detections) {
      const descriptor = Array.from(detections.descriptor);
      setSamples(prev => [...prev, descriptor]);
      
      if (samples.length + 1 >= requiredSamples) {
        // Auto-enroll when enough samples
        await enrollFace([...samples, descriptor]);
      }
    }
  };

  // Enroll face
  const enrollFace = async (descriptors) => {
    setStatus('Enrolling face...');
    try {
      const res = await fetch(`${API_URL}/api/biometric/face/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          face_descriptors: descriptors
        })
      });

      if (!res.ok) throw new Error('Enrollment failed');
      const data = await res.json();
      
      setStatus('Face enrolled successfully!');
      onSuccess?.(data);
    } catch (err) {
      setStatus('Enrollment failed');
      onError?.(err.message);
    }
  };

  // Verify face
  const verifyFace = async () => {
    if (!faceDetected || !videoRef.current) return;

    setStatus('Verifying...');
    const faceapi = faceapiRef.current;
    
    const detections = await faceapi
      .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!detections) {
      setStatus('No face detected');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/biometric/face/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          face_descriptor: Array.from(detections.descriptor)
        })
      });

      const data = await res.json();
      
      if (data.matched) {
        setStatus(`Verified! Confidence: ${(data.confidence * 100).toFixed(1)}%`);
        onSuccess?.(data);
      } else {
        setStatus('Face not recognized');
        onError?.('Face not recognized');
      }
    } catch (err) {
      setStatus('Verification failed');
      onError?.(err.message);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-md w-full overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">
              {mode === 'enroll' ? '🔐 Enroll Face' : '🔓 Face Verification'}
            </h3>
            <button onClick={onClose} className="text-white/80 hover:text-white">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Camera view */}
        <div className="relative aspect-[4/3] bg-gray-900">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
          />
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full"
          />
          
          {/* Face guide overlay */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className={`w-48 h-60 border-4 rounded-full transition-colors ${
              faceDetected ? 'border-green-500' : 'border-white/50'
            }`} />
          </div>

          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <div className="animate-spin w-10 h-10 border-4 border-white border-t-transparent rounded-full" />
            </div>
          )}
        </div>

        {/* Status and actions */}
        <div className="p-4 space-y-4">
          <p className={`text-center font-medium ${faceDetected ? 'text-green-600' : 'text-gray-600'}`}>
            {status}
          </p>

          {mode === 'enroll' && (
            <div className="flex gap-2">
              <div className="flex-1 bg-gray-100 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-full rounded-full transition-all"
                  style={{ width: `${(samples.length / requiredSamples) * 100}%` }}
                />
              </div>
              <span className="text-sm text-gray-500">{samples.length}/{requiredSamples}</span>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            
            {mode === 'enroll' ? (
              <button
                onClick={captureSample}
                disabled={!faceDetected || samples.length >= requiredSamples}
                className="flex-1 py-3 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Capture ({samples.length}/{requiredSamples})
              </button>
            ) : (
              <button
                onClick={verifyFace}
                disabled={!faceDetected}
                className="flex-1 py-3 rounded-xl bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
              >
                Verify Face
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// VOICE RECOGNITION COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export const VoiceRecognition = ({
  userId,
  mode = 'verify', // 'enroll' or 'verify'
  passphrase = "My voice is my password",
  onSuccess,
  onError,
  onClose,
  requiredSamples = 3
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [samples, setSamples] = useState([]);
  const [status, setStatus] = useState('Click to start recording');
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const chunksRef = useRef([]);

  // Start recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Set up audio analysis
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);
      analyserRef.current.fftSize = 256;
      
      // Set up recording
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };
      
      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        processRecording(blob);
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorderRef.current.start();
      setIsRecording(true);
      setStatus(`Say: "${passphrase}"`);
      
      // Update audio level
      const updateLevel = () => {
        if (!analyserRef.current || !isRecording) return;
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setAudioLevel(avg / 255);
        requestAnimationFrame(updateLevel);
      };
      updateLevel();
      
      // Auto-stop after 5 seconds
      setTimeout(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
          stopRecording();
        }
      }, 5000);
      
    } catch (err) {
      setStatus('Microphone access denied');
      onError?.('Microphone access denied');
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // Process recording
  const processRecording = async (blob) => {
    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64 = reader.result.split(',')[1];
      
      if (mode === 'enroll') {
        const newSamples = [...samples, base64];
        setSamples(newSamples);
        
        if (newSamples.length >= requiredSamples) {
          await enrollVoice(newSamples);
        } else {
          setStatus(`Sample ${newSamples.length}/${requiredSamples} recorded. Record again.`);
        }
      } else {
        await verifyVoice(base64);
      }
    };
    reader.readAsDataURL(blob);
  };

  // Enroll voice
  const enrollVoice = async (voiceSamples) => {
    setStatus('Enrolling voice...');
    try {
      const res = await fetch(`${API_URL}/api/biometric/voice/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          voice_samples: voiceSamples,
          passphrase: passphrase
        })
      });

      if (!res.ok) throw new Error('Enrollment failed');
      const data = await res.json();
      
      setStatus('Voice enrolled successfully!');
      onSuccess?.(data);
    } catch (err) {
      setStatus('Enrollment failed');
      onError?.(err.message);
    }
  };

  // Verify voice
  const verifyVoice = async (voiceSample) => {
    setStatus('Verifying voice...');
    try {
      const res = await fetch(`${API_URL}/api/biometric/voice/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          voice_sample: voiceSample,
          passphrase: passphrase
        })
      });

      const data = await res.json();
      
      if (data.matched) {
        setStatus(`Verified! Confidence: ${(data.confidence * 100).toFixed(1)}%`);
        onSuccess?.(data);
      } else {
        setStatus('Voice not recognized');
        onError?.('Voice not recognized');
      }
    } catch (err) {
      setStatus('Verification failed');
      onError?.(err.message);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-md w-full overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-pink-600 text-white p-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">
              {mode === 'enroll' ? '🎤 Enroll Voice' : '🔊 Voice Verification'}
            </h3>
            <button onClick={onClose} className="text-white/80 hover:text-white">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Voice visualizer */}
        <div className="p-8 flex flex-col items-center">
          {/* Mic button */}
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`w-32 h-32 rounded-full flex items-center justify-center transition-all ${
              isRecording 
                ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
                : 'bg-purple-600 hover:bg-purple-700'
            }`}
            style={{
              boxShadow: isRecording ? `0 0 ${audioLevel * 100}px ${audioLevel * 50}px rgba(239, 68, 68, 0.3)` : 'none'
            }}
          >
            <svg className="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isRecording ? (
                <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                />
              )}
            </svg>
          </button>

          {/* Passphrase display */}
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-500">Say this phrase:</p>
            <p className="text-lg font-medium text-gray-800 mt-1">"{passphrase}"</p>
          </div>

          {/* Status */}
          <p className={`mt-4 text-center font-medium ${
            status.includes('successfully') ? 'text-green-600' : 
            status.includes('failed') || status.includes('denied') ? 'text-red-600' : 
            'text-gray-600'
          }`}>
            {status}
          </p>

          {/* Progress for enrollment */}
          {mode === 'enroll' && (
            <div className="w-full mt-4 flex gap-2">
              <div className="flex-1 bg-gray-100 rounded-full h-2">
                <div 
                  className="bg-purple-600 h-full rounded-full transition-all"
                  style={{ width: `${(samples.length / requiredSamples) * 100}%` }}
                />
              </div>
              <span className="text-sm text-gray-500">{samples.length}/{requiredSamples}</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// BIOMETRIC SETTINGS PANEL
// ═══════════════════════════════════════════════════════════════════════════════

export const BiometricSettings = ({ userId, onStatusChange }) => {
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showFaceEnroll, setShowFaceEnroll] = useState(false);
  const [showVoiceEnroll, setShowVoiceEnroll] = useState(false);
  const webauthn = useWebAuthn();

  // Fetch status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/biometric/status/${userId}`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          onStatusChange?.(data);
        }
      } catch (err) {
        console.error('Failed to fetch biometric status:', err);
      }
      setIsLoading(false);
    };

    if (userId) fetchStatus();
  }, [userId, onStatusChange]);

  // Handle WebAuthn registration
  const handleWebAuthnRegister = async () => {
    const result = await webauthn.register(userId, userId, 'ReRoots User');
    if (result.success) {
      setStatus(prev => ({
        ...prev,
        webauthn: { enrolled: true, credential_count: (prev?.webauthn?.credential_count || 0) + 1 }
      }));
    }
  };

  if (isLoading) {
    return <div className="p-4 text-center text-gray-500">Loading...</div>;
  }

  return (
    <div className="space-y-4">
      {/* WebAuthn / Device Biometrics */}
      <div className="p-4 rounded-xl border border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4"
                />
              </svg>
            </div>
            <div>
              <p className="font-medium">Fingerprint / Face ID</p>
              <p className="text-sm text-gray-500">Device biometrics</p>
            </div>
          </div>
          
          {status?.webauthn?.enrolled ? (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
              {status.webauthn.credential_count} device(s)
            </span>
          ) : webauthn.isSupported ? (
            <button
              onClick={handleWebAuthnRegister}
              disabled={webauthn.isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {webauthn.isLoading ? 'Setting up...' : 'Set Up'}
            </button>
          ) : (
            <span className="text-sm text-gray-400">Not supported</span>
          )}
        </div>
      </div>

      {/* Face Recognition */}
      <div className="p-4 rounded-xl border border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <div>
              <p className="font-medium">Face Recognition</p>
              <p className="text-sm text-gray-500">Camera-based verification</p>
            </div>
          </div>
          
          {status?.face?.enrolled ? (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
              Enrolled
            </span>
          ) : (
            <button
              onClick={() => setShowFaceEnroll(true)}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700"
            >
              Set Up
            </button>
          )}
        </div>
      </div>

      {/* Voice Recognition */}
      <div className="p-4 rounded-xl border border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-pink-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-pink-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                />
              </svg>
            </div>
            <div>
              <p className="font-medium">Voice Recognition</p>
              <p className="text-sm text-gray-500">Voice-based verification</p>
            </div>
          </div>
          
          {status?.voice?.enrolled ? (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
              Enrolled
            </span>
          ) : (
            <button
              onClick={() => setShowVoiceEnroll(true)}
              className="px-4 py-2 bg-pink-600 text-white rounded-lg text-sm hover:bg-pink-700"
            >
              Set Up
            </button>
          )}
        </div>
      </div>

      {/* Modals */}
      {showFaceEnroll && (
        <FaceRecognition
          userId={userId}
          mode="enroll"
          onSuccess={() => {
            setShowFaceEnroll(false);
            setStatus(prev => ({ ...prev, face: { enrolled: true } }));
          }}
          onError={(err) => console.error(err)}
          onClose={() => setShowFaceEnroll(false)}
        />
      )}

      {showVoiceEnroll && (
        <VoiceRecognition
          userId={userId}
          mode="enroll"
          onSuccess={() => {
            setShowVoiceEnroll(false);
            setStatus(prev => ({ ...prev, voice: { enrolled: true } }));
          }}
          onError={(err) => console.error(err)}
          onClose={() => setShowVoiceEnroll(false)}
        />
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// BIOMETRIC LOCK SCREEN
// ═══════════════════════════════════════════════════════════════════════════════

export const BiometricLockScreen = ({
  userId,
  onUnlock,
  onCancel,
  title = "Unlock ReRoots AI",
  allowedMethods = ['webauthn', 'face', 'voice']
}) => {
  const [selectedMethod, setSelectedMethod] = useState(null);
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const webauthn = useWebAuthn();

  // Fetch enrolled methods
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/biometric/status/${userId}`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          
          // Auto-select first available method
          if (data.webauthn?.enrolled && allowedMethods.includes('webauthn')) {
            setSelectedMethod('webauthn');
          } else if (data.face?.enrolled && allowedMethods.includes('face')) {
            setSelectedMethod('face');
          } else if (data.voice?.enrolled && allowedMethods.includes('voice')) {
            setSelectedMethod('voice');
          }
        }
      } catch (err) {
        console.error(err);
      }
      setIsLoading(false);
    };

    fetchStatus();
  }, [userId, allowedMethods]);

  // Handle WebAuthn authentication
  const handleWebAuthn = async () => {
    const result = await webauthn.authenticate(userId);
    if (result.success) {
      onUnlock?.(result);
    }
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50">
        <div className="animate-spin w-12 h-12 border-4 border-white border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center z-50 p-4">
      <div className="max-w-sm w-full text-center">
        {/* Lock icon */}
        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-white/10 flex items-center justify-center">
          <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>

        <h2 className="text-2xl font-bold text-white mb-2">{title}</h2>
        <p className="text-gray-400 mb-8">Verify your identity to continue</p>

        {/* Method buttons */}
        <div className="space-y-3">
          {status?.webauthn?.enrolled && allowedMethods.includes('webauthn') && (
            <button
              onClick={handleWebAuthn}
              disabled={webauthn.isLoading}
              className="w-full py-4 px-6 rounded-xl bg-white/10 hover:bg-white/20 text-white flex items-center justify-center gap-3 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4"
                />
              </svg>
              {webauthn.isLoading ? 'Verifying...' : 'Use Fingerprint / Face ID'}
            </button>
          )}

          {status?.face?.enrolled && allowedMethods.includes('face') && (
            <button
              onClick={() => setSelectedMethod('face')}
              className="w-full py-4 px-6 rounded-xl bg-white/10 hover:bg-white/20 text-white flex items-center justify-center gap-3 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              Use Face Recognition
            </button>
          )}

          {status?.voice?.enrolled && allowedMethods.includes('voice') && (
            <button
              onClick={() => setSelectedMethod('voice')}
              className="w-full py-4 px-6 rounded-xl bg-white/10 hover:bg-white/20 text-white flex items-center justify-center gap-3 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                />
              </svg>
              Use Voice Recognition
            </button>
          )}
        </div>

        {/* Cancel */}
        {onCancel && (
          <button
            onClick={onCancel}
            className="mt-6 text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
        )}

        {/* Error display */}
        {webauthn.error && (
          <p className="mt-4 text-red-400 text-sm">{webauthn.error}</p>
        )}
      </div>

      {/* Face/Voice modals */}
      {selectedMethod === 'face' && (
        <FaceRecognition
          userId={userId}
          mode="verify"
          onSuccess={(data) => {
            setSelectedMethod(null);
            onUnlock?.(data);
          }}
          onError={() => setSelectedMethod(null)}
          onClose={() => setSelectedMethod(null)}
        />
      )}

      {selectedMethod === 'voice' && (
        <VoiceRecognition
          userId={userId}
          mode="verify"
          onSuccess={(data) => {
            setSelectedMethod(null);
            onUnlock?.(data);
          }}
          onError={() => setSelectedMethod(null)}
          onClose={() => setSelectedMethod(null)}
        />
      )}
    </div>
  );
};


export default {
  useWebAuthn,
  FaceRecognition,
  VoiceRecognition,
  BiometricSettings,
  BiometricLockScreen
};
