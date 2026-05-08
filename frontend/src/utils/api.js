// API URL configuration - works on all domains
// Supports: localhost, preview.emergentagent.com, and custom domains (reroots.ca)
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // For localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    
    // For custom domains (reroots.ca, etc.) - ALWAYS use same origin
    // This ensures API calls go to the correct backend regardless of env var
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    
    // For preview/staging environments, use env var if available
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    
    // Fallback to same origin
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

export const BACKEND_URL = getBackendUrl();
export const API = `${BACKEND_URL}/api`;

// Phone country code helper - auto-detect and format phone numbers
export const COUNTRY_CODES = {
  'CA': { code: '+1', name: 'Canada', flag: '🇨🇦' },
  'US': { code: '+1', name: 'USA', flag: '🇺🇸' },
  'GB': { code: '+44', name: 'UK', flag: '🇬🇧' },
  'IN': { code: '+91', name: 'India', flag: '🇮🇳' },
  'AU': { code: '+61', name: 'Australia', flag: '🇦🇺' },
  'DE': { code: '+49', name: 'Germany', flag: '🇩🇪' },
  'FR': { code: '+33', name: 'France', flag: '🇫🇷' },
  'CN': { code: '+86', name: 'China', flag: '🇨🇳' },
  'JP': { code: '+81', name: 'Japan', flag: '🇯🇵' },
  'MX': { code: '+52', name: 'Mexico', flag: '🇲🇽' },
  'BR': { code: '+55', name: 'Brazil', flag: '🇧🇷' },
  'AE': { code: '+971', name: 'UAE', flag: '🇦🇪' },
  'SA': { code: '+966', name: 'Saudi Arabia', flag: '🇸🇦' },
  'PK': { code: '+92', name: 'Pakistan', flag: '🇵🇰' },
};

// Session ID management for cart persistence
export const getSessionId = () => {
  let sessionId = localStorage.getItem("reroots_session_id");
  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("reroots_session_id", sessionId);
  }
  return sessionId;
};

export const formatPhoneWithCountryCode = (phone, countryCode = 'CA') => {
  if (!phone) return '';
  // Remove all non-digits
  const digits = phone.replace(/\D/g, '');
  // If already has country code (starts with +), return as is
  if (phone.startsWith('+')) return phone;
  // If number is 10 digits (North American format), add country code
  const country = COUNTRY_CODES[countryCode] || COUNTRY_CODES['CA'];
  if (digits.length === 10) {
    return `${country.code}${digits}`;
  }
  // If number is 11 digits starting with 1 (like 1XXXXXXXXXX), format with +
  if (digits.length === 11 && digits.startsWith('1')) {
    return `+${digits}`;
  }
  // Otherwise return with country code prefix
  return `${country.code}${digits}`;
};
