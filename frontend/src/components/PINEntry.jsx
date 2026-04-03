/**
 * PIN Entry Component
 * Fallback authentication when face recognition fails
 */

import React, { useState } from 'react';
import { Lock, AlertCircle, ArrowLeft } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PINEntry = ({ email, onSuccess, onBack }) => {
  const [pin, setPin] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handlePinInput = (value) => {
    const numericValue = value.replace(/\D/g, '').slice(0, 6);
    setPin(numericValue);
    setError(null);

    // Auto-submit when 4-6 digits entered
    if (numericValue.length >= 4 && numericValue.length <= 6) {
      verifyPin(numericValue);
    }
  };

  const verifyPin = async (pinValue) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/biometric/verify-pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          pin: pinValue
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        console.log('[PIN Entry] PIN verified successfully');
        if (onSuccess) {
          onSuccess(email);
        }
      } else {
        setError(data.message || 'Incorrect PIN');
        setPin('');
        setLoading(false);
      }
    } catch (err) {
      console.error('[PIN Entry] Error:', err);
      setError('Network error. Please try again.');
      setPin('');
      setLoading(false);
    }
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
      {/* Back Button */}
      {onBack && (
        <button
          onClick={onBack}
          style={{
            alignSelf: 'flex-start',
            padding: '8px',
            background: 'transparent',
            border: 'none',
            color: '#888',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            marginBottom: 16
          }}
        >
          <ArrowLeft className="w-4 h-4" />
          <span style={{ fontSize: 13 }}>Back to Face Recognition</span>
        </button>
      )}

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
        Enter Your PIN
      </h2>

      <p style={{
        fontSize: 13,
        color: '#888',
        marginBottom: 32,
        textAlign: 'center',
        maxWidth: 320
      }}>
        Face recognition unavailable. Enter your backup PIN to continue.
      </p>

      {/* PIN Display */}
      <div style={{
        display: 'flex',
        gap: 12,
        marginBottom: 24
      }}>
        {[0, 1, 2, 3, 4, 5].map((index) => {
          const isFilled = index < pin.length;
          
          return (
            <div
              key={index}
              style={{
                width: 48,
                height: 56,
                borderRadius: 8,
                border: `2px solid ${error ? '#F44' : (isFilled ? '#D4AF37' : '#1A1A1A')}`,
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

      {/* Loading Indicator */}
      {loading && (
        <div style={{
          padding: 12,
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: '#D4AF37'
        }}>
          <div className="w-4 h-4 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
          <span style={{fontSize: 12}}>Verifying...</span>
        </div>
      )}

      {/* Hidden Input for Mobile Keyboard */}
      <input
        type="tel"
        inputMode="numeric"
        pattern="[0-9]*"
        value={pin}
        onChange={(e) => handlePinInput(e.target.value)}
        maxLength={6}
        autoFocus
        disabled={loading}
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
        maxWidth: 280
      }}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, '', 0, '⌫'].map((num, index) => {
          if (num === '') return <div key={index} />;
          
          const isBackspace = num === '⌫';
          
          return (
            <button
              key={index}
              onClick={() => {
                if (loading) return;
                
                if (isBackspace) {
                  handlePinInput(pin.slice(0, -1));
                } else {
                  handlePinInput(pin + num);
                }
              }}
              disabled={loading}
              style={{
                padding: '16px',
                background: isBackspace ? '#1A1A1A' : '#0A0A0A',
                border: '1px solid #1A1A1A',
                borderRadius: 12,
                color: isBackspace ? '#D4AF37' : '#F4F4F4',
                fontSize: 20,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s',
                opacity: loading ? 0.5 : 1
              }}
              onMouseOver={(e) => !loading && (e.currentTarget.style.background = '#1A1A1A')}
              onMouseOut={(e) => !loading && (e.currentTarget.style.background = isBackspace ? '#1A1A1A' : '#0A0A0A')}
            >
              {num}
            </button>
          );
        })}
      </div>

      <p style={{
        fontSize: 11,
        color: '#555',
        marginTop: 24,
        textAlign: 'center'
      }}>
        Forgot your PIN? Contact support or<br />use password login.
      </p>
    </div>
  );
};

export default PINEntry;
