/**
 * Device Fingerprint Hook - Free fingerprinting for fraud prevention
 * Generates a unique device identifier based on browser/device characteristics
 */

import { useEffect, useState, useCallback } from 'react';

// Generate a hash from string
const hashCode = (str) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16);
};

// Collect browser/device characteristics
const collectFingerprint = async () => {
  const components = [];
  
  // Screen info
  components.push(`screen:${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}`);
  components.push(`availScreen:${window.screen.availWidth}x${window.screen.availHeight}`);
  
  // Timezone
  components.push(`tz:${Intl.DateTimeFormat().resolvedOptions().timeZone}`);
  components.push(`tzOffset:${new Date().getTimezoneOffset()}`);
  
  // Language
  components.push(`lang:${navigator.language}`);
  components.push(`langs:${(navigator.languages || []).join(',')}`);
  
  // Platform
  components.push(`platform:${navigator.platform}`);
  components.push(`userAgent:${navigator.userAgent}`);
  
  // Hardware concurrency (CPU cores)
  components.push(`cores:${navigator.hardwareConcurrency || 'unknown'}`);
  
  // Device memory (if available)
  components.push(`memory:${navigator.deviceMemory || 'unknown'}`);
  
  // Touch support
  components.push(`touch:${('ontouchstart' in window) || (navigator.maxTouchPoints > 0)}`);
  
  // WebGL info
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      if (debugInfo) {
        components.push(`webglVendor:${gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL)}`);
        components.push(`webglRenderer:${gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)}`);
      }
    }
  } catch (e) {
    components.push('webgl:unavailable');
  }
  
  // Canvas fingerprint
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 200;
    canvas.height = 50;
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillStyle = '#f60';
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = '#069';
    ctx.fillText('Fingerprint', 2, 15);
    ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
    ctx.fillText('Canvas', 4, 17);
    components.push(`canvas:${hashCode(canvas.toDataURL())}`);
  } catch (e) {
    components.push('canvas:unavailable');
  }
  
  // Audio fingerprint (simplified)
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      const context = new AudioContext();
      components.push(`audioSampleRate:${context.sampleRate}`);
      context.close();
    }
  } catch (e) {
    components.push('audio:unavailable');
  }
  
  // Plugins (if available)
  const plugins = [];
  for (let i = 0; i < (navigator.plugins?.length || 0); i++) {
    plugins.push(navigator.plugins[i].name);
  }
  components.push(`plugins:${hashCode(plugins.join(','))}`);
  
  // Do Not Track
  components.push(`dnt:${navigator.doNotTrack || 'unknown'}`);
  
  // Cookie enabled
  components.push(`cookies:${navigator.cookieEnabled}`);
  
  // Local storage available
  try {
    localStorage.setItem('test', 'test');
    localStorage.removeItem('test');
    components.push('localStorage:true');
  } catch (e) {
    components.push('localStorage:false');
  }
  
  // Session storage available
  try {
    sessionStorage.setItem('test', 'test');
    sessionStorage.removeItem('test');
    components.push('sessionStorage:true');
  } catch (e) {
    components.push('sessionStorage:false');
  }
  
  // IndexedDB available
  components.push(`indexedDB:${!!window.indexedDB}`);
  
  // Create final fingerprint hash
  const fingerprintString = components.join('|');
  const fingerprint = hashCode(fingerprintString);
  
  return {
    fingerprint,
    components: {
      screen: `${window.screen.width}x${window.screen.height}`,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      language: navigator.language,
      platform: navigator.platform,
      userAgent: navigator.userAgent,
      cores: navigator.hardwareConcurrency || 'unknown',
      memory: navigator.deviceMemory || 'unknown',
      touch: ('ontouchstart' in window) || (navigator.maxTouchPoints > 0)
    }
  };
};

// Hook for device fingerprinting
export const useDeviceFingerprint = () => {
  const [fingerprint, setFingerprint] = useState(null);
  const [components, setComponents] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const getFingerprint = async () => {
      try {
        // Check if we already have a fingerprint stored
        const stored = localStorage.getItem('device_fp');
        if (stored) {
          const data = JSON.parse(stored);
          setFingerprint(data.fingerprint);
          setComponents(data.components);
          setLoading(false);
          return;
        }
        
        // Generate new fingerprint
        const result = await collectFingerprint();
        setFingerprint(result.fingerprint);
        setComponents(result.components);
        
        // Store for consistency
        localStorage.setItem('device_fp', JSON.stringify(result));
        setLoading(false);
      } catch (error) {
        console.error('Fingerprint error:', error);
        setFingerprint('error');
        setLoading(false);
      }
    };
    
    getFingerprint();
  }, []);
  
  return { fingerprint, components, loading };
};

// Fraud check utility functions
const API = process.env.REACT_APP_BACKEND_URL || '';

export const checkEmailFraud = async (email) => {
  try {
    const res = await fetch(`${API}/api/fraud/check-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    return await res.json();
  } catch (error) {
    console.error('Email fraud check error:', error);
    return { is_risky: false, risk_score: 0, recommendation: 'allow' };
  }
};

export const checkIPFraud = async () => {
  try {
    const res = await fetch(`${API}/api/fraud/check-ip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    return await res.json();
  } catch (error) {
    console.error('IP fraud check error:', error);
    return { is_risky: false, risk_score: 0, recommendation: 'allow' };
  }
};

export const registerDevice = async (fingerprint, userAgent, email = null) => {
  try {
    const res = await fetch(`${API}/api/fraud/register-device`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fingerprint,
        user_agent: userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        language: navigator.language,
        platform: navigator.platform,
        email
      })
    });
    return await res.json();
  } catch (error) {
    console.error('Device registration error:', error);
    return { status: 'error', is_risky: false };
  }
};

export const checkVelocity = async (email, deviceFingerprint = null, orderValue = 0) => {
  try {
    const res = await fetch(`${API}/api/fraud/velocity-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        ip: '', // Server will use request IP
        device_fingerprint: deviceFingerprint,
        order_value: orderValue
      })
    });
    return await res.json();
  } catch (error) {
    console.error('Velocity check error:', error);
    return { is_risky: false, risk_score: 0, recommendation: 'allow' };
  }
};

export const fullFraudCheck = async (email, deviceFingerprint = null, orderValue = 0) => {
  try {
    const params = new URLSearchParams({
      email,
      ...(deviceFingerprint && { device_fingerprint: deviceFingerprint }),
      ...(orderValue && { order_value: orderValue.toString() })
    });
    
    const res = await fetch(`${API}/api/fraud/full-check?${params}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    return await res.json();
  } catch (error) {
    console.error('Full fraud check error:', error);
    return { 
      combined_risk_score: 0, 
      recommendation: 'allow',
      risk_factors: ['Check failed - allowing by default']
    };
  }
};

export default useDeviceFingerprint;
