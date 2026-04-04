/**
 * Fast Biometric Login - WebAuthn Based
 * Replaces slow face-api.js FaceIDLogin
 * Zero ML dependencies - uses native device biometrics
 */

import React, { useState, useEffect } from 'react';
import { Fingerprint, ArrowLeft, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FastBiometricLogin = ({ onSuccess, onFallbackToPassword }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [email, setEmail] = useState('');

  useEffect(() => {
    // Get saved email
    const savedEmail = localStorage.getItem('biometric_email') || localStorage.getItem('faceid_email');
    if (savedEmail) {
      setEmail(savedEmail);
      // Auto-trigger biometric prompt
      setTimeout(() => handleBiometricLogin(savedEmail), 500);
    } else {
      // No saved email, fallback to password
      onFallbackToPassword();
    }
  }, []);

  const handleBiometricLogin = async (userEmail) => {
    setLoading(true);
    setError(null);

    try {
      // Start WebAuthn authentication
      const startRes = await fetch(`${API_URL}/api/biometric/webauthn/auth/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userEmail })
      });

      if (!startRes.ok) {
        throw new Error('Biometric not set up for this account');
      }

      const { options } = await startRes.json();

      // Decode challenge
      const publicKeyOptions = {
        ...options,
        challenge: Uint8Array.from(atob(options.challenge.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)),
        allowCredentials: options.allowCredentials?.map(cred => ({
          ...cred,
          id: Uint8Array.from(atob(cred.id.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
        })) || []
      };

      // Trigger native biometric prompt
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
          signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature)))
        }
      };

      // Complete authentication
      const finishRes = await fetch(`${API_URL}/api/biometric/webauthn/auth/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userEmail,
          credential: credentialResponse
        })
      });

      if (!finishRes.ok) {
        throw new Error('Authentication failed');
      }

      // Success - trigger login callback
      if (onSuccess) {
        onSuccess(userEmail);
      }

    } catch (err) {
      console.error('[FastBiometricLogin] Error:', err);
      
      if (err.name === 'NotAllowedError') {
        setError('Biometric authentication cancelled');
      } else if (err.message.includes('not set up')) {
        setError('Biometric login not enabled. Use password instead.');
      } else {
        setError('Biometric login failed. Try password instead.');
      }
      
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: 32,
      maxWidth: 400,
      margin: '0 auto'
    }}>
      <div style={{
        width: 80,
        height: 80,
        borderRadius: '50%',
        background: loading ? 
          'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)' : 
          '#1A1A1A',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 24,
        border: loading ? 'none' : '2px solid #333'
      }}>
        {loading ? (
          <div className="w-10 h-10 border-3 border-[#050505] border-t-transparent rounded-full animate-spin" />
        ) : (
          <Fingerprint className="w-10 h-10 text-[#D4AF37]" />
        )}
      </div>

      <h2 style={{
        fontSize: 22,
        fontWeight: 600,
        color: '#F4F4F4',
        marginBottom: 8,
        textAlign: 'center'
      }}>
        {loading ? 'Authenticating...' : 'Biometric Login'}
      </h2>

      <p style={{
        fontSize: 13,
        color: '#888',
        marginBottom: 24,
        textAlign: 'center'
      }}>
        {loading 
          ? 'Complete the biometric prompt on your device'
          : email ? `Logging in as ${email}` : 'Checking biometric setup...'
        }
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
          gap: 8,
          width: '100%'
        }}>
          <AlertCircle className="w-4 h-4 text-[#F44]" />
          <span style={{ fontSize: 12, color: '#F88' }}>{error}</span>
        </div>
      )}

      {!loading && (
        <button
          onClick={onFallbackToPassword}
          style={{
            width: '100%',
            padding: '12px 24px',
            background: 'transparent',
            border: '1px solid #333',
            borderRadius: 8,
            color: '#F4F4F4',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8
          }}
        >
          <ArrowLeft className="w-5 h-5" />
          Use Password Instead
        </button>
      )}
    </div>
  );
};

export default FastBiometricLogin;
