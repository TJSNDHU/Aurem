import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

/**
 * GoogleAuthButton — Emergent-managed Google OAuth (no Google Cloud setup needed).
 *
 * Flow:
 *  1. User clicks → redirect to `https://auth.emergentagent.com/?redirect=<dashboard>`
 *  2. User approves with Google → Emergent redirects back with `#session_id=xxx`
 *  3. `AppRouter` detects the fragment and renders `GoogleAuthCallback`,
 *     which POSTs the session_id to `/api/auth/google/callback` and stores the JWT.
 */
export const GoogleAuthButton = ({
  buttonText = 'Continue with Google',
  className = '',
  redirectPath = '/dashboard',
}) => {
  const [loading, setLoading] = useState(false);

  const handleClick = () => {
    setLoading(true);
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + redirectPath;
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      data-testid="google-auth-btn"
      className={`w-full flex items-center justify-center gap-3 py-5 sm:py-6 text-sm sm:text-base border-2 border-gray-200 hover:border-[#C9A86C] hover:bg-[#FDF9F9] transition-all rounded-full disabled:opacity-50 ${className}`}
    >
      {loading ? (
        <>
          <Loader2 className="size-4 animate-spin" />
          <span>Redirecting to Google…</span>
        </>
      ) : (
        <>
          <svg className="size-5" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          <span>{buttonText}</span>
        </>
      )}
    </button>
  );
};

// Legacy alias retained for any imports of `GoogleAuthButtonCustom`.
export const GoogleAuthButtonCustom = GoogleAuthButton;

export default GoogleAuthButton;
