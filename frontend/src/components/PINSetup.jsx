/**
 * PIN Setup Component
 * Part of biometric onboarding flow
 * Sets up 4-6 digit PIN as backup authentication
 */

import React, { useState } from 'react';
import { Lock, Check, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PINSetup = ({ email, faceDescriptor, onComplete }) => {
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState('enter'); // 'enter' or 'confirm'

  const handlePinInput = (value) => {
    // Only allow digits, max 6
    const numericValue = value.replace(/\D/g, '').slice(0, 6);
    
    if (step === 'enter') {
      setPin(numericValue);
    } else {
      setConfirmPin(numericValue);
    }
  };

  const handleContinue = () => {
    if (pin.length < 4) {
      setError('PIN must be at least 4 digits');
      return;
    }
    
    setError(null);
    setStep('confirm');
  };

  const handleFinish = async () => {
    if (pin !== confirmPin) {
      setError('PINs do not match');
      return;
    }

    if (confirmPin.length < 4 || confirmPin.length > 6) {
      setError('PIN must be 4-6 digits');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Send biometric data + PIN to backend
      const response = await fetch(`${API_URL}/api/biometric/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          face_descriptor: faceDescriptor,
          pin: confirmPin
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        console.log('[PIN Setup] Biometric data saved to backend');
        
        // Also store locally as cache
        localStorage.setItem('faceid_descriptor', JSON.stringify(faceDescriptor));
        localStorage.setItem('faceid_trained', 'true');
        localStorage.setItem('faceid_email', email);
        
        if (onComplete) {
          onComplete();
        }
      } else {
        setError(data.message || 'Failed to save biometric data');
        setLoading(false);
      }
    } catch (err) {
      console.error('[PIN Setup] Error:', err);
      setError('Network error. Please try again.');
      setLoading(false);
    }
  };

  const handleBack = () => {
    setStep('enter');
    setConfirmPin('');
    setError(null);
  };

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
        {step === 'enter' ? 'Create Your PIN' : 'Confirm Your PIN'}
      </h2>

      <p style={{
        fontSize: 13,
        color: '#888',
        marginBottom: 32,
        textAlign: 'center',
        maxWidth: 320
      }}>
        {step === 'enter' 
          ? 'Create a 4-6 digit PIN as backup for face recognition'
          : 'Re-enter your PIN to confirm'
        }
      </p>

      {/* PIN Display */}
      <div style={{
        display: 'flex',
        gap: 12,
        marginBottom: 24
      }}>
        {[0, 1, 2, 3, 4, 5].map((index) => {
          const currentValue = step === 'enter' ? pin : confirmPin;
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
                color: '#F4F4F4',
                transition: 'all 0.2s'
              }}
            >
              {isFilled ? '•' : ''}
            </div>
          );
        })}
      </div>

      {/* Error Message */}
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
          <span style={{fontSize: 12, color: '#F88'}}>{error}</span>
        </div>
      )}

      {/* Hidden Input for Mobile Keyboard */}
      <input
        type="tel"
        inputMode="numeric"
        pattern="[0-9]*"
        value={step === 'enter' ? pin : confirmPin}
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
          const currentValue = step === 'enter' ? pin : confirmPin;
          
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
                padding: '16px',
                background: isBackspace ? '#1A1A1A' : '#0A0A0A',
                border: '1px solid #1A1A1A',
                borderRadius: 12,
                color: isBackspace ? '#D4AF37' : '#F4F4F4',
                fontSize: 20,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseOver={(e) => e.currentTarget.style.background = '#1A1A1A'}
              onMouseOut={(e) => e.currentTarget.style.background = isBackspace ? '#1A1A1A' : '#0A0A0A'}
            >
              {num}
            </button>
          );
        })}
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 12, width: '100%' }}>
        {step === 'confirm' && (
          <button
            onClick={handleBack}
            style={{
              flex: 1,
              padding: '12px 24px',
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
          onClick={step === 'enter' ? handleContinue : handleFinish}
          disabled={loading || (step === 'enter' ? pin.length < 4 : confirmPin.length < 4)}
          style={{
            flex: 1,
            padding: '12px 24px',
            background: (loading || (step === 'enter' ? pin.length < 4 : confirmPin.length < 4))
              ? '#333'
              : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 8,
            color: (loading || (step === 'enter' ? pin.length < 4 : confirmPin.length < 4)) ? '#666' : '#050505',
            fontSize: 14,
            fontWeight: 600,
            cursor: (loading || (step === 'enter' ? pin.length < 4 : confirmPin.length < 4)) ? 'not-allowed' : 'pointer',
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
              {step === 'enter' ? 'Continue' : (
                <>
                  <Check className="w-5 h-5" />
                  Finish Setup
                </>
              )}
            </>
          )}
        </button>
      </div>

      <p style={{
        fontSize: 11,
        color: '#555',
        marginTop: 24,
        textAlign: 'center'
      }}>
        Your PIN is encrypted and stored securely.<br />
        Use it to login when face recognition is unavailable.
      </p>
    </div>
  );
};

export default PINSetup;
