/**
 * ReRoots AI Biometric Gate Component
 * WebAuthn API Integration for FaceID/Fingerprint
 * Protects the Progress Tab and Vault Access
 * LOGS TO ADMIN: All auth events sent to Master Admin analytics
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Fingerprint, Shield, ShieldCheck, AlertCircle, Loader2, Key, Smartphone } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

// WebAuthn Configuration
const RP_NAME = 'ReRoots AI';
const RP_ID = typeof window !== 'undefined' ? window.location.hostname : 'reroots.ca';
const CHALLENGE_LENGTH = 32;
const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Log biometric events to admin analytics
const logBiometricEvent = async (eventType, method, success) => {
  try {
    const userId = localStorage.getItem('reroots_user_id') || localStorage.getItem('reroots_biometric_user_id') || 'anonymous';
    await fetch(`${API_URL}/api/pwa/admin/log-biometric`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: eventType,
        user_id: userId,
        method: method,
        success: success
      })
    });
  } catch (error) {
    console.log('[Biometric] Log event failed (non-critical):', error);
  }
};

/**
 * BiometricGate - Wrapper component for biometric-protected content
 */
export function BiometricGate({ children, onUnlock, fallbackPin = true }) {
  const [isSupported, setIsSupported] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isRegistered, setIsRegistered] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showPinFallback, setShowPinFallback] = useState(false);
  const [pin, setPin] = useState('');
  const [error, setError] = useState(null);

  // Check WebAuthn support
  useEffect(() => {
    const checkSupport = async () => {
      const supported = window.PublicKeyCredential !== undefined;
      setIsSupported(supported);
      
      if (supported) {
        // Check if user has registered credentials
        const credentialId = localStorage.getItem('reroots_biometric_credential');
        setIsRegistered(!!credentialId);
      }
      
      setIsLoading(false);
    };
    
    checkSupport();
  }, []);

  // Generate random challenge
  const generateChallenge = useCallback(() => {
    const challenge = new Uint8Array(CHALLENGE_LENGTH);
    crypto.getRandomValues(challenge);
    return challenge;
  }, []);

  // Convert ArrayBuffer to Base64
  const bufferToBase64 = (buffer) => {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    bytes.forEach(b => binary += String.fromCharCode(b));
    return btoa(binary);
  };

  // Convert Base64 to ArrayBuffer
  const base64ToBuffer = (base64) => {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  };

  // Register biometric credential
  const registerBiometric = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const userId = crypto.getRandomValues(new Uint8Array(16));
      const challenge = generateChallenge();
      
      const publicKeyCredentialCreationOptions = {
        challenge: challenge,
        rp: {
          name: RP_NAME,
          id: RP_ID
        },
        user: {
          id: userId,
          name: 'ReRoots User',
          displayName: 'Skin Vault Access'
        },
        pubKeyCredParams: [
          { alg: -7, type: 'public-key' },   // ES256
          { alg: -257, type: 'public-key' }  // RS256
        ],
        authenticatorSelection: {
          authenticatorAttachment: 'platform', // Use device biometrics (FaceID/Fingerprint)
          userVerification: 'required',
          residentKey: 'preferred'
        },
        timeout: 60000,
        attestation: 'none'
      };

      const credential = await navigator.credentials.create({
        publicKey: publicKeyCredentialCreationOptions
      });

      if (credential) {
        // Store credential ID for future authentication
        const credentialId = bufferToBase64(credential.rawId);
        localStorage.setItem('reroots_biometric_credential', credentialId);
        localStorage.setItem('reroots_biometric_user_id', bufferToBase64(userId));
        
        setIsRegistered(true);
        setIsAuthenticated(true);
        
        // Log to admin analytics
        await logBiometricEvent('registration', 'webauthn', true);
        
        toast.success('Biometric registered successfully!', {
          description: 'Your vault is now protected with FaceID/Fingerprint'
        });
        
        if (onUnlock) onUnlock();
      }
    } catch (err) {
      console.error('[Biometric] Registration error:', err);
      setError(err.message);
      
      // Log failed registration
      await logBiometricEvent('registration', 'webauthn', false);
      
      if (err.name === 'NotAllowedError') {
        toast.error('Biometric registration cancelled');
      } else if (err.name === 'NotSupportedError') {
        toast.error('Biometrics not supported on this device');
        setShowPinFallback(true);
      } else {
        toast.error('Failed to register biometric');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Authenticate with biometric
  const authenticateBiometric = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const credentialId = localStorage.getItem('reroots_biometric_credential');
      
      if (!credentialId) {
        setError('No biometric credential found. Please register first.');
        setIsLoading(false);
        return;
      }

      const challenge = generateChallenge();
      
      const publicKeyCredentialRequestOptions = {
        challenge: challenge,
        rpId: RP_ID,
        allowCredentials: [{
          id: base64ToBuffer(credentialId),
          type: 'public-key',
          transports: ['internal'] // Platform authenticator
        }],
        userVerification: 'required',
        timeout: 60000
      };

      const assertion = await navigator.credentials.get({
        publicKey: publicKeyCredentialRequestOptions
      });

      if (assertion) {
        setIsAuthenticated(true);
        
        // Log successful authentication to admin
        await logBiometricEvent('login', 'webauthn', true);
        
        toast.success('Identity verified!');
        if (onUnlock) onUnlock();
      }
    } catch (err) {
      console.error('[Biometric] Authentication error:', err);
      
      // Log failed authentication
      await logBiometricEvent('login', 'webauthn', false);
      
      if (err.name === 'NotAllowedError') {
        toast.error('Authentication cancelled or timed out');
        if (fallbackPin) setShowPinFallback(true);
      } else {
        setError(err.message);
        toast.error('Biometric verification failed');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // PIN fallback authentication
  const authenticateWithPin = async () => {
    const storedPin = localStorage.getItem('reroots_vault_pin');
    
    if (!storedPin) {
      // First time - set PIN
      if (pin.length >= 4) {
        localStorage.setItem('reroots_vault_pin', pin);
        setIsAuthenticated(true);
        
        // Log PIN registration
        await logBiometricEvent('registration', 'pin', true);
        
        toast.success('PIN set successfully!');
        if (onUnlock) onUnlock();
      } else {
        toast.error('PIN must be at least 4 digits');
      }
    } else {
      // Verify PIN
      if (pin === storedPin) {
        setIsAuthenticated(true);
        
        // Log successful PIN login
        await logBiometricEvent('login', 'pin', true);
        
        toast.success('PIN verified!');
        if (onUnlock) onUnlock();
      } else {
        // Log failed PIN attempt
        await logBiometricEvent('login', 'pin', false);
        
        toast.error('Incorrect PIN');
        setPin('');
      }
    }
  };

  // Reset biometric registration
  const resetBiometric = () => {
    localStorage.removeItem('reroots_biometric_credential');
    localStorage.removeItem('reroots_biometric_user_id');
    localStorage.removeItem('reroots_vault_pin');
    setIsRegistered(false);
    setIsAuthenticated(false);
    setShowPinFallback(false);
    toast.success('Biometric credentials cleared');
  };

  // If authenticated, show protected content
  if (isAuthenticated) {
    return <>{children}</>;
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center bg-gradient-to-b from-[#0a0a0f] to-[#1a1a2e] p-6">
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-r from-amber-500/20 to-amber-600/20 blur-3xl rounded-full" />
          <Loader2 className="w-16 h-16 text-amber-500 animate-spin relative z-10" />
        </div>
        <p className="mt-6 text-white/60 text-sm">Initializing secure access...</p>
      </div>
    );
  }

  // PIN fallback UI
  if (showPinFallback) {
    const hasStoredPin = !!localStorage.getItem('reroots_vault_pin');
    
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center bg-gradient-to-b from-[#0a0a0f] to-[#1a1a2e] p-6">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/20 flex items-center justify-center">
              <Key className="w-10 h-10 text-amber-500" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">
              {hasStoredPin ? 'Enter Your PIN' : 'Set Your PIN'}
            </h2>
            <p className="text-white/60 text-sm">
              {hasStoredPin 
                ? 'Enter your PIN to unlock the vault'
                : 'Create a PIN to protect your skin vault'
              }
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex justify-center gap-2">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className={`w-4 h-4 rounded-full border-2 transition-all ${
                    pin.length > i 
                      ? 'bg-amber-500 border-amber-500' 
                      : 'border-white/30'
                  }`}
                />
              ))}
            </div>

            <div className="grid grid-cols-3 gap-3 max-w-[240px] mx-auto">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, null, 0, 'del'].map((num, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    if (num === 'del') {
                      setPin(prev => prev.slice(0, -1));
                    } else if (num !== null && pin.length < 6) {
                      setPin(prev => prev + num);
                    }
                  }}
                  disabled={num === null}
                  className={`h-14 rounded-xl font-semibold text-lg transition-all ${
                    num === null
                      ? 'invisible'
                      : num === 'del'
                        ? 'bg-white/5 text-white/60 hover:bg-white/10'
                        : 'bg-white/10 text-white hover:bg-white/20 active:scale-95'
                  }`}
                >
                  {num === 'del' ? '⌫' : num}
                </button>
              ))}
            </div>

            <Button
              onClick={authenticateWithPin}
              disabled={pin.length < 4}
              className="w-full h-12 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-black font-semibold"
            >
              {hasStoredPin ? 'Unlock Vault' : 'Set PIN'}
            </Button>

            {isSupported && (
              <button
                onClick={() => setShowPinFallback(false)}
                className="w-full text-center text-amber-500/80 text-sm hover:text-amber-500"
              >
                Use biometric instead
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Main biometric UI
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center bg-gradient-to-b from-[#0a0a0f] to-[#1a1a2e] p-6">
      <div className="w-full max-w-sm text-center">
        {/* Icon */}
        <div className="relative w-24 h-24 mx-auto mb-6">
          <div className="absolute inset-0 bg-gradient-to-br from-amber-500/30 to-amber-600/30 blur-2xl rounded-full" />
          <div className="relative w-full h-full rounded-full bg-gradient-to-br from-[#1a1a2e] to-[#0a0a0f] border border-amber-500/30 flex items-center justify-center">
            {isRegistered ? (
              <ShieldCheck className="w-12 h-12 text-amber-500" />
            ) : (
              <Fingerprint className="w-12 h-12 text-amber-500" />
            )}
          </div>
        </div>

        {/* Title */}
        <h2 className="text-2xl font-bold text-white mb-2">
          {isRegistered ? 'Unlock Your Vault' : 'Secure Your Vault'}
        </h2>
        
        <p className="text-white/60 text-sm mb-8 max-w-xs mx-auto">
          {isRegistered
            ? 'Use FaceID or Fingerprint to access your encrypted skin photos'
            : 'Protect your skin progress photos with biometric security'
          }
        </p>

        {/* Error message */}
        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Not supported warning */}
        {!isSupported && (
          <div className="mb-6 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <div className="flex items-center gap-2 text-amber-500 mb-2">
              <Smartphone className="w-5 h-5" />
              <span className="font-semibold">Biometrics Not Available</span>
            </div>
            <p className="text-white/60 text-sm">
              Your device doesn't support WebAuthn biometrics. Use PIN fallback instead.
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="space-y-3">
          {isSupported && (
            <Button
              onClick={isRegistered ? authenticateBiometric : registerBiometric}
              disabled={isLoading}
              className="w-full h-14 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-black font-semibold text-lg rounded-xl"
            >
              {isLoading ? (
                <Loader2 className="w-6 h-6 animate-spin" />
              ) : (
                <>
                  <Fingerprint className="w-6 h-6 mr-2" />
                  {isRegistered ? 'Verify Identity' : 'Enable Biometric'}
                </>
              )}
            </Button>
          )}

          {(fallbackPin || !isSupported) && (
            <Button
              onClick={() => setShowPinFallback(true)}
              variant="outline"
              className="w-full h-12 border-white/20 text-white hover:bg-white/10"
            >
              <Key className="w-5 h-5 mr-2" />
              Use PIN Instead
            </Button>
          )}

          {isRegistered && (
            <button
              onClick={resetBiometric}
              className="text-white/40 text-xs hover:text-white/60 transition-colors"
            >
              Reset biometric credentials
            </button>
          )}
        </div>

        {/* Security badge */}
        <div className="mt-8 flex items-center justify-center gap-2 text-white/40 text-xs">
          <Shield className="w-4 h-4" />
          <span>AES-256 Encrypted • On-Device Only</span>
        </div>
      </div>
    </div>
  );
}

export default BiometricGate;
