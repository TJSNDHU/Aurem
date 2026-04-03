import React, { useState, useEffect } from 'react';
import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google';
import axios from 'axios';
import { toast } from 'sonner';
import { API } from '@/utils/api';
import { Loader2 } from 'lucide-react';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

/**
 * GoogleAuthButton - Handles Google OAuth using user's custom Google Cloud credentials
 * Uses @react-oauth/google library with the /auth/google/verify-token backend endpoint
 */
export const GoogleAuthButton = ({ 
  onSuccess, 
  onError, 
  isAdmin = false,
  buttonText = "Continue with Google",
  className = ""
}) => {
  const [clientId, setClientId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [configError, setConfigError] = useState(false);

  // Fetch Google Client ID from backend on mount
  useEffect(() => {
    const fetchGoogleConfig = async () => {
      try {
        const apiUrl = `${API}/auth/google/config`;
        console.log('[GoogleAuth] Fetching config from:', apiUrl);
        
        // Try fetch first as it's more reliable
        const response = await fetch(apiUrl, {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          },
          credentials: 'same-origin'
        });
        
        if (!response.ok) {
          console.error('[GoogleAuth] Response not ok:', response.status);
          setConfigError(true);
          return;
        }
        
        const data = await response.json();
        console.log('[GoogleAuth] Config response:', data);
        
        if (data?.client_id) {
          setClientId(data.client_id);
        } else {
          console.error('[GoogleAuth] No client_id in response:', data);
          setConfigError(true);
        }
      } catch (error) {
        console.error('[GoogleAuth] Failed to fetch Google config:', error.message);
        setConfigError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchGoogleConfig();
  }, []);

  const handleGoogleSuccess = async (credentialResponse) => {
    console.log('[GoogleAuth] Received credential from Google');
    setIsProcessing(true);

    try {
      const response = await axios.post(`${API}/auth/google/verify-token`, {
        credential: credentialResponse.credential,
        is_admin: isAdmin
      });

      const { token, user } = response.data;

      // Store auth data
      localStorage.setItem('reroots_token', token);
      localStorage.setItem('reroots_user', JSON.stringify(user));
      localStorage.setItem('reroots_returning_customer', 'true');

      console.log('[GoogleAuth] Login successful:', user.email);
      toast.success(`Welcome${user.first_name ? ', ' + user.first_name : ''}!`);

      if (onSuccess) {
        onSuccess(user, token);
      }
    } catch (error) {
      console.error('[GoogleAuth] Backend verification failed:', error);
      const errorMessage = error.response?.data?.detail || 'Google authentication failed';
      toast.error(errorMessage);
      
      if (onError) {
        onError(error);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleGoogleError = () => {
    console.error('[GoogleAuth] Google sign-in error');
    toast.error('Google sign-in was cancelled or failed');
    if (onError) {
      onError(new Error('Google sign-in failed'));
    }
  };

  // Show loading state while fetching config
  if (loading) {
    return (
      <div className={`flex items-center justify-center py-5 ${className}`}>
        <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
      </div>
    );
  }

  // Show disabled button if config failed - so users know Google auth exists but isn't available
  if (!clientId || configError) {
    return (
      <button 
        disabled 
        className={`w-full flex items-center justify-center gap-3 py-5 border-2 border-gray-200 rounded-full opacity-50 cursor-not-allowed ${className}`}
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        <span className="text-gray-400">Google Sign-in Unavailable</span>
      </button>
    );
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      {isProcessing ? (
        <div className={`flex items-center justify-center gap-2 py-5 border-2 border-gray-200 rounded-full ${className}`}>
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm text-gray-600">Verifying Google...</span>
        </div>
      ) : (
        <div className={`google-auth-button-wrapper ${className}`}>
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
            type="standard"
            theme="outline"
            size="large"
            text="continue_with"
            shape="pill"
            width="100%"
            logo_alignment="left"
          />
        </div>
      )}
    </GoogleOAuthProvider>
  );
};

/**
 * GoogleAuthButtonCustom - A fully custom styled Google button
 * Uses the credential flow but with custom UI
 */
export const GoogleAuthButtonCustom = ({ 
  onSuccess, 
  onError, 
  isAdmin = false,
  buttonText = "Sign in with Google",
  disabled = false,
  className = ""
}) => {
  const [clientId, setClientId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const fetchGoogleConfig = async () => {
      try {
        const apiUrl = `${API}/auth/google/config`;
        const response = await fetch(apiUrl, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
          credentials: 'same-origin'
        });
        if (response.ok) {
          const data = await response.json();
          if (data?.client_id) {
            setClientId(data.client_id);
          }
        }
      } catch (error) {
        console.error('[GoogleAuth] Failed to fetch Google config:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchGoogleConfig();
  }, []);

  const handleCredentialResponse = async (response) => {
    if (!response.credential) {
      toast.error('Google sign-in failed');
      return;
    }

    setIsProcessing(true);

    try {
      const backendResponse = await axios.post(`${API}/auth/google/verify-token`, {
        credential: response.credential,
        is_admin: isAdmin
      });

      const { token, user } = backendResponse.data;

      localStorage.setItem('reroots_token', token);
      localStorage.setItem('reroots_user', JSON.stringify(user));
      localStorage.setItem('reroots_returning_customer', 'true');

      toast.success(`Welcome${user.first_name ? ', ' + user.first_name : ''}!`);

      if (onSuccess) {
        onSuccess(user, token);
      }
    } catch (error) {
      console.error('[GoogleAuth] Verification failed:', error);
      const errorMessage = error.response?.data?.detail || 'Google authentication failed';
      toast.error(errorMessage);
      
      if (onError) {
        onError(error);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  if (loading) {
    return (
      <button 
        disabled 
        className={`w-full flex items-center justify-center gap-3 py-5 border-2 border-gray-200 rounded-full opacity-50 ${className}`}
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Loading...</span>
      </button>
    );
  }

  if (!clientId) {
    return null;
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <div id="google-signin-button" style={{ display: 'none' }} />
      <GoogleLogin
        onSuccess={handleCredentialResponse}
        onError={() => {
          toast.error('Google sign-in was cancelled or failed');
          if (onError) onError(new Error('Google sign-in failed'));
        }}
        useOneTap={false}
        auto_select={false}
        render={(renderProps) => (
          <button
            type="button"
            onClick={renderProps.onClick}
            disabled={disabled || isProcessing || renderProps.disabled}
            className={`w-full flex items-center justify-center gap-3 py-5 sm:py-6 text-sm sm:text-base border-2 border-gray-200 hover:border-[#C9A86C] hover:bg-[#FDF9F9] transition-all rounded-full disabled:opacity-50 ${className}`}
          >
            {isProcessing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Verifying Google...</span>
              </>
            ) : (
              <>
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                <span>{buttonText}</span>
              </>
            )}
          </button>
        )}
      />
    </GoogleOAuthProvider>
  );
};

export default GoogleAuthButton;
