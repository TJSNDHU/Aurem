/**
 * Fast Biometric Setup - Optimized for Speed
 * Uses native WebAuthn (Face ID/Touch ID/Fingerprint) - No heavy ML models
 * Fallback to PIN only if biometrics unavailable
 * ~2 second setup vs 15+ seconds with face-api.js
 */

import React, { useState, useEffect } from 'react';
import { Fingerprint, Lock, Check, AlertCircle, Zap } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FastBiometricSetup = ({ email, onComplete, onSkip }) => {
  const [step, setStep] = useState('checking'); // 'checking', 'choice', 'webauthn', 'pin', 'complete'
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [biometricSupported, setBiometricSupported] = useState(false);
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [pinStep, setPinStep] = useState('enter'); // 'enter' or 'confirm'

  useEffect(() => {
    checkBiometricSupport();
  }, []);

  const checkBiometricSupport = async () => {
    try {
      // For mobile browsers, WebAuthn support is limited
      // Skip biometric check and go straight to PIN choice for better UX
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      
      if (isMobile) {
        // On mobile, offer PIN only (WebAuthn has compatibility issues)
        setBiometricSupported(false);
        setStep('choice');
        return;
      }
      
      // Check if WebAuthn is supported (desktop browsers)
      const supported = window.PublicKeyCredential !== undefined;
      
      if (supported) {
        // Check if platform authenticator (Face ID/Touch ID) is available
        const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
        setBiometricSupported(available);
      } else {
        setBiometricSupported(false);
      }
      
      setStep('choice');
    } catch (err) {
      console.error('[FastBiometric] Support check failed:', err);
      setBiometricSupported(false);
      setStep('choice');
    }
  };

  const setupWebAuthn = async () => {
    setLoading(true);
    setError(null);

    try {
      // Request registration options from backend
      const startRes = await fetch(`${API_URL}/api/biometric/webauthn/register/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: email,
          user_name: email,
          user_display_name: email.split('@')[0]
        })
      });

      if (!startRes.ok) {
        throw new Error('Failed to start biometric registration');
      }

      const { options } = await startRes.json();

      // Decode challenge and user ID
      const publicKeyOptions = {
        ...options,
        challenge: Uint8Array.from(atob(options.challenge.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)),
        user: {
          ...options.user,
          id: Uint8Array.from(atob(options.user.id.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))
        }
      };

      // Trigger native biometric prompt (Face ID/Touch ID/Fingerprint)
      const credential = await navigator.credentials.create({
        publicKey: publicKeyOptions
      });

      // Encode response
      const credentialResponse = {
        id: credential.id,
        rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
        type: credential.type,
        response: {
          clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
          attestationObject: btoa(String.fromCharCode(...new Uint8Array(credential.response.attestationObject)))
        }
      };

      // Complete registration
      const finishRes = await fetch(`${API_URL}/api/biometric/webauthn/register/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: email,
          credential: credentialResponse
        })
      });

      if (!finishRes.ok) {
        throw new Error('Failed to save biometric credential');
      }

      // Mark as enrolled
      localStorage.setItem('biometric_enabled', 'true');
      localStorage.setItem('biometric_email', email);
      localStorage.setItem('biometric_type', 'webauthn');

      setStep('complete');
      setTimeout(() => {
        if (onComplete) onComplete();
      }, 1500);

    } catch (err) {
      console.error('[FastBiometric] WebAuthn setup failed:', err);
      
      if (err.name === 'NotAllowedError') {
        setError('Biometric setup cancelled. You can set up a PIN instead.');
      } else {
        setError('Biometric setup failed. Please try PIN setup instead.');
      }
      
      setLoading(false);
    }
  };

  const handlePinInput = (value) => {
    const numericValue = value.replace(/\D/g, '').slice(0, 6);
    
    if (pinStep === 'enter') {
      setPin(numericValue);
    } else {
      setConfirmPin(numericValue);
    }
  };

  const handlePinContinue = () => {
    if (pin.length < 4) {
      setError('PIN must be at least 4 digits');
      return;
    }
    
    setError(null);
    setPinStep('confirm');
  };

  const handlePinFinish = async () => {
    if (pin !== confirmPin) {
      setError('PINs do not match');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Save PIN to backend (without face descriptor - PIN only)
      const response = await fetch(`${API_URL}/api/biometric/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          face_descriptor: Array(128).fill(0), // Dummy descriptor
          pin: confirmPin
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        localStorage.setItem('pin_enabled', 'true');
        localStorage.setItem('pin_email', email);
        
        setStep('complete');
        setTimeout(() => {
          if (onComplete) onComplete();
        }, 1500);
      } else {
        setError(data.message || 'Failed to save PIN');
        setLoading(false);
      }
    } catch (err) {
      console.error('[FastBiometric] PIN setup failed:', err);
      setError('Network error. Please try again.');
      setLoading(false);
    }
  };

  // Choice Screen
  if (step === 'choice') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 24,
        maxWidth: 400,
        margin: '0 auto'
      }}>
        <Zap className="w-12 h-12 text-[#D4AF37] mb-4" />
        
        <h2 style={{
          fontSize: 22,
          fontWeight: 600,
          color: '#F4F4F4',
          marginBottom: 8,
          textAlign: 'center'
        }}>
          Secure Your Account
        </h2>

        <p style={{
          fontSize: 13,
          color: '#888',
          marginBottom: 24,
          textAlign: 'center'
        }}>
          Choose your preferred login method
        </p>

        {/* Biometric Option (if supported) */}
        {biometricSupported && (
          <button
            onClick={() => setStep('webauthn')}
            style={{
              width: '100%',
              padding: 16,
              marginBottom: 12,
              background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
              border: 'none',
              borderRadius: 12,
              color: '#050505',
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 12
            }}
          >
            <Fingerprint className="w-6 h-6" />
            <div style={{ flex: 1, textAlign: 'left' }}>
              <div>Face ID / Touch ID</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>⚡ Instant login (recommended)</div>
            </div>
          </button>
        )}

        {/* PIN Option */}
        <button
          onClick={() => setStep('pin')}
          style={{
            width: '100%',
            padding: 16,
            marginBottom: 12,
            background: '#1A1A1A',
            border: '1px solid #333',
            borderRadius: 12,
            color: '#F4F4F4',
            fontSize: 15,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 12
          }}
        >
          <Lock className="w-6 h-6 text-[#D4AF37]" />
          <div style={{ flex: 1, textAlign: 'left' }}>
            <div>PIN Code</div>
            <div style={{ fontSize: 11, opacity: 0.5 }}>4-6 digit backup</div>
          </div>
        </button>

        {/* Skip Option */}
        {onSkip && (
          <button
            onClick={onSkip}
            style={{
              width: '100%',
              padding: 12,
              background: 'transparent',
              border: 'none',
              color: '#666',
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            Skip for now
          </button>
        )}
      </div>
    );
  }

  // WebAuthn Setup
  if (step === 'webauthn') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 24,
        maxWidth: 400,
        margin: '0 auto'
      }}>
        <div style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 24
        }}>
          <Fingerprint className="w-10 h-10 text-[#050505]" />
        </div>

        <h2 style={{
          fontSize: 22,
          fontWeight: 600,
          color: '#F4F4F4',
          marginBottom: 8,
          textAlign: 'center'
        }}>
          Setup Biometric Login
        </h2>

        <p style={{
          fontSize: 13,
          color: '#888',
          marginBottom: 32,
          textAlign: 'center'
        }}>
          Your device will prompt you to authenticate
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

        <button
          onClick={setupWebAuthn}
          disabled={loading}
          style={{
            width: '100%',
            padding: '14px 24px',
            background: loading ? '#333' : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 8,
            color: loading ? '#666' : '#050505',
            fontSize: 15,
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            marginBottom: 12
          }}
        >
          {loading ? (
            <>
              <div className="w-5 h-5 border-2 border-[#666] border-t-transparent rounded-full animate-spin" />
              Setting up...
            </>
          ) : (
            <>
              <Fingerprint className="w-5 h-5" />
              Enable Biometric Login
            </>
          )}
        </button>

        <button
          onClick={() => setStep('choice')}
          style={{
            width: '100%',
            padding: 12,
            background: 'transparent',
            border: 'none',
            color: '#666',
            fontSize: 13,
            cursor: 'pointer'
          }}
        >
          Back
        </button>
      </div>
    );
  }

  // PIN Setup
  if (step === 'pin') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 24,
        maxWidth: 400,
        margin: '0 auto'
      }}>
        <div style={{
          width: 64,
          height: 64,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 24
        }}>
          <Lock className="w-8 h-8 text-[#050505]" />
        </div>

        <h2 style={{
          fontSize: 22,
          fontWeight: 600,
          color: '#F4F4F4',
          marginBottom: 8,
          textAlign: 'center'
        }}>
          {pinStep === 'enter' ? 'Create Your PIN' : 'Confirm Your PIN'}
        </h2>

        <p style={{
          fontSize: 13,
          color: '#888',
          marginBottom: 32,
          textAlign: 'center'
        }}>
          {pinStep === 'enter' 
            ? 'Create a 4-6 digit PIN for quick login'
            : 'Re-enter your PIN to confirm'
          }
        </p>

        {/* PIN Display */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          {[0, 1, 2, 3, 4, 5].map((index) => {
            const currentValue = pinStep === 'enter' ? pin : confirmPin;
            const isFilled = index < currentValue.length;
            
            return (
              <div
                key={index}
                style={{
                  width: 48,
                  height: 56,
                  borderRadius: 8,
                  border: `2px solid ${isFilled ? '#D4AF37' : '#1A1A1A'}`,
                  background: isFilled ? 'rgba(212, 175, 55, 0.1)' : '#0A0A0A',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  fontWeight: 600,
                  color: '#F4F4F4'
                }}
              >
                {isFilled ? '•' : ''}
              </div>
            );
          })}
        </div>

        {/* Error */}
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

        {/* Hidden Input */}
        <input
          type="tel"
          inputMode="numeric"
          pattern="[0-9]*"
          value={pinStep === 'enter' ? pin : confirmPin}
          onChange={(e) => handlePinInput(e.target.value)}
          maxLength={6}
          autoFocus
          style={{
            position: 'absolute',
            opacity: 0,
            pointerEvents: 'none'
          }}
        />

        {/* Number Pad */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
          width: '100%',
          maxWidth: 280,
          marginBottom: 24
        }}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, '', 0, '⌫'].map((num, index) => {
            if (num === '') return <div key={index} />;
            
            const isBackspace = num === '⌫';
            const currentValue = pinStep === 'enter' ? pin : confirmPin;
            
            return (
              <button
                key={index}
                onClick={() => {
                  if (isBackspace) {
                    handlePinInput(currentValue.slice(0, -1));
                  } else {
                    handlePinInput(currentValue + num);
                  }
                }}
                style={{
                  padding: 16,
                  background: '#0A0A0A',
                  border: '1px solid #1A1A1A',
                  borderRadius: 12,
                  color: '#F4F4F4',
                  fontSize: 20,
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {num}
              </button>
            );
          })}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 12, width: '100%' }}>
          {pinStep === 'confirm' && (
            <button
              onClick={() => { setPinStep('enter'); setConfirmPin(''); setError(null); }}
              style={{
                flex: 1,
                padding: 12,
                background: 'transparent',
                border: '1px solid #333',
                borderRadius: 8,
                color: '#888',
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Back
            </button>
          )}
          
          <button
            onClick={pinStep === 'enter' ? handlePinContinue : handlePinFinish}
            disabled={loading || (pinStep === 'enter' ? pin.length < 4 : confirmPin.length < 4)}
            style={{
              flex: 1,
              padding: 12,
              background: (loading || (pinStep === 'enter' ? pin.length < 4 : confirmPin.length < 4))
                ? '#333'
                : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
              border: 'none',
              borderRadius: 8,
              color: (loading || (pinStep === 'enter' ? pin.length < 4 : confirmPin.length < 4)) ? '#666' : '#050505',
              fontSize: 14,
              fontWeight: 600,
              cursor: (loading || (pinStep === 'enter' ? pin.length < 4 : confirmPin.length < 4)) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8
            }}
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-[#666] border-t-transparent rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              <>
                {pinStep === 'enter' ? 'Continue' : (
                  <>
                    <Check className="w-5 h-5" />
                    Finish
                  </>
                )}
              </>
            )}
          </button>
        </div>

        <button
          onClick={() => setStep('choice')}
          style={{
            width: '100%',
            padding: 12,
            marginTop: 12,
            background: 'transparent',
            border: 'none',
            color: '#666',
            fontSize: 13,
            cursor: 'pointer'
          }}
        >
          Choose different method
        </button>
      </div>
    );
  }

  // Complete
  if (step === 'complete') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 24,
        maxWidth: 400,
        margin: '0 auto'
      }}>
        <div style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #22C55E 0%, #16A34A 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 24
        }}>
          <Check className="w-10 h-10 text-white" />
        </div>

        <h2 style={{
          fontSize: 22,
          fontWeight: 600,
          color: '#F4F4F4',
          marginBottom: 8,
          textAlign: 'center'
        }}>
          All Set!
        </h2>

        <p style={{
          fontSize: 13,
          color: '#888',
          textAlign: 'center'
        }}>
          Your account is secured and ready to use
        </p>
      </div>
    );
  }

  // Checking
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 48
    }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );
};

export default FastBiometricSetup;
