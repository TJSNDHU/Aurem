/**
 * FaceID Authentication Wrapper
 * Portal/Wrapper Pattern - No JSX conflicts
 * 
 * Wraps the auth page with biometric capability
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Scan, Lock } from 'lucide-react';
import FaceIDLogin from './FaceIDLogin';
import FaceIDTrainer from './FaceIDTrainer';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FaceIDAuthWrapper = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState('checking'); // 'checking', 'faceid', 'password', 'training'
  const [faceIDAvailable, setFaceIDAvailable] = useState(false);

  useEffect(() => {
    // Check if FaceID is trained
    const trained = localStorage.getItem('faceid_trained') === 'true';
    const descriptor = localStorage.getItem('faceid_descriptor');
    
    if (trained && descriptor) {
      setFaceIDAvailable(true);
      setMode('faceid');
    } else {
      setMode('password');
    }
  }, []);

  const handleFaceIDSuccess = async (email) => {
    try {
      const response = await fetch(`${API_URL}/api/platform/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: email,
          password: 'Admin123' // In production: use FaceID token backend validation
        })
      });

      const data = await response.json();

      if (response.ok && data.token) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        navigate('/dashboard');
      } else {
        alert('Login failed after FaceID recognition');
        setMode('password');
      }
    } catch (err) {
      console.error('FaceID login error:', err);
      alert('Connection failed');
      setMode('password');
    }
  };

  const handlePasswordLogin = async (email, password) => {
    try {
      const response = await fetch(`${API_URL}/api/platform/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (response.ok && data.token) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        localStorage.setItem('faceid_email', email);
        
        // Offer FaceID training
        if (!faceIDAvailable) {
          const train = window.confirm('Setup FaceID for faster login next time?');
          if (train) {
            setMode('training');
            return;
          }
        }
        
        navigate('/dashboard');
      } else {
        throw new Error(data.detail || 'Invalid credentials');
      }
    } catch (err) {
      throw err;
    }
  };

  const handleTrainingComplete = () => {
    navigate('/dashboard');
  };

  if (mode === 'checking') {
    return (
      <div style={{
        minHeight: '100vh',
        background: '#050505',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{
          width: 64,
          height: 64,
          border: '3px solid #D4AF37',
          borderRadius: '50%',
          borderTopColor: 'transparent',
          animation: 'spin 1s linear infinite'
        }} />
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#050505',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 16
    }}>
      <div style={{ width: '100%', maxWidth: 640 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 64,
            height: 64,
            margin: '0 auto 16px',
            borderRadius: 16,
            background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Sparkles style={{ width: 32, height: 32, color: '#050505' }} />
          </div>
          <h1 style={{
            fontSize: 24,
            fontWeight: 300,
            color: '#F4F4F4',
            letterSpacing: 2,
            marginBottom: 4
          }}>
            AUREM
          </h1>
          <p style={{ fontSize: 12, color: '#666' }}>
            BUSINESS AI PLATFORM
          </p>
        </div>

        {/* FaceID Training Mode */}
        {mode === 'training' && (
          <div style={{
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 16,
            overflow: 'hidden'
          }}>
            <FaceIDTrainer onComplete={handleTrainingComplete} />
          </div>
        )}

        {/* FaceID Login Mode */}
        {mode === 'faceid' && (
          <div style={{
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 16,
            overflow: 'hidden'
          }}>
            <FaceIDLogin 
              onSuccess={handleFaceIDSuccess}
              onFallbackToPassword={() => setMode('password')}
            />
          </div>
        )}

        {/* Password Login Mode */}
        {mode === 'password' && (
          <PasswordLoginForm 
            onLogin={handlePasswordLogin}
            onSwitchToFaceID={() => setMode('faceid')}
            faceIDAvailable={faceIDAvailable}
          />
        )}

        {/* Footer */}
        <p style={{
          textAlign: 'center',
          fontSize: 11,
          color: '#555',
          marginTop: 24
        }}>
          Protected by enterprise-grade security
        </p>
      </div>
    </div>
  );
};

// Password Login Form Component
const PasswordLoginForm = ({ onLogin, onSwitchToFaceID, faceIDAvailable }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await onLogin(email, password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: '#0A0A0A',
      border: '1px solid #1A1A1A',
      borderRadius: 16,
      padding: 32
    }}>
      <h2 style={{
        fontSize: 20,
        fontWeight: 600,
        color: '#F4F4F4',
        marginBottom: 4
      }}>
        Sign In
      </h2>
      <p style={{
        fontSize: 13,
        color: '#666',
        marginBottom: 24
      }}>
        Access AUREM Command Center
      </p>

      {/* FaceID Option */}
      {faceIDAvailable && (
        <>
          <button
            type="button"
            onClick={onSwitchToFaceID}
            data-testid="faceid-login-button"
            style={{
              width: '100%',
              padding: 16,
              background: 'linear-gradient(135deg, #1A3A1A 0%, #1A1A3A 100%)',
              border: '1px solid #2A5A2A',
              borderRadius: 12,
              color: '#4A4',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              marginBottom: 16
            }}
          >
            <Scan style={{ width: 20, height: 20 }} />
            Sign in with FaceID
          </button>

          <div style={{
            position: 'relative',
            marginBottom: 16
          }}>
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center'
            }}>
              <div style={{
                width: '100%',
                borderTop: '1px solid #1A1A1A'
              }} />
            </div>
            <div style={{
              position: 'relative',
              display: 'flex',
              justifyContent: 'center'
            }}>
              <span style={{
                padding: '0 8px',
                background: '#0A0A0A',
                fontSize: 11,
                color: '#666'
              }}>
                or use password
              </span>
            </div>
          </div>
        </>
      )}

      {/* Error Message */}
      {error && (
        <div style={{
          padding: 12,
          background: 'rgba(255, 68, 68, 0.1)',
          border: '1px solid rgba(255, 68, 68, 0.3)',
          borderRadius: 8,
          color: '#F88',
          fontSize: 13,
          marginBottom: 16
        }}>
          {error}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{
            display: 'block',
            fontSize: 11,
            color: '#888',
            marginBottom: 6,
            textTransform: 'uppercase',
            letterSpacing: 1
          }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="operator@company.com"
            required
            data-testid="email-input"
            style={{
              width: '100%',
              padding: '12px 16px',
              background: '#050505',
              border: '1px solid #1A1A1A',
              borderRadius: 8,
              color: '#F4F4F4',
              fontSize: 14,
              outline: 'none'
            }}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{
            display: 'block',
            fontSize: 11,
            color: '#888',
            marginBottom: 6,
            textTransform: 'uppercase',
            letterSpacing: 1
          }}>
            Password
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              data-testid="password-input"
              style={{
                width: '100%',
                padding: '12px 16px',
                paddingRight: 48,
                background: '#050505',
                border: '1px solid #1A1A1A',
                borderRadius: 8,
                color: '#F4F4F4',
                fontSize: 14,
                outline: 'none'
              }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              style={{
                position: 'absolute',
                right: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: '#666',
                cursor: 'pointer',
                padding: 4
              }}
            >
              {showPassword ? '👁️' : '👁️‍🗨️'}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            width: '100%',
            padding: '14px 24px',
            background: loading ? '#333' : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 8,
            color: '#050505',
            fontSize: 14,
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8
          }}
        >
          {loading ? 'Authenticating...' : 'Access Command Center'}
          <Lock style={{ width: 16, height: 16 }} />
        </button>
      </form>
    </div>
  );
};

export default FaceIDAuthWrapper;
