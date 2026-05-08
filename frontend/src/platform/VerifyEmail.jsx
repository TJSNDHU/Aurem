import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState('verifying'); // 'verifying' | 'success' | 'error'
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid verification link.');
      return;
    }

    const verify = async () => {
      try {
        const res = await fetch(`${API_URL}/api/auth/verify-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        const data = await res.json();
        if (res.ok) {
          setStatus('success');
          setMessage(data.message || 'Email verified successfully!');
        } else {
          setStatus('error');
          setMessage(data.detail || 'Verification failed.');
        }
      } catch {
        setStatus('error');
        setMessage('Network error. Please try again.');
      }
    };

    verify();
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--aurem-bg, #050505)' }}>
      <div className="text-center max-w-md px-6" data-testid="verify-email-page">
        {status === 'verifying' && (
          <>
            <Loader2 className="w-16 h-16 mx-auto mb-4 animate-spin" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
            <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>Verifying Email...</h1>
            <p className="text-sm" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Please wait while we verify your email address.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle className="w-16 h-16 mx-auto mb-4" style={{ color: '#FF6B00' }} />
            <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }} data-testid="verify-success-title">Email Verified!</h1>
            <p className="text-sm mb-6" style={{ color: 'var(--aurem-body-secondary, #888)' }}>{message}</p>
            <Link to="/login" className="inline-block px-8 py-3 rounded-xl text-sm font-bold" style={{ background: 'linear-gradient(135deg, #D4AF37, #B8962E)', color: '#050505' }}>
              Go to Login
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <AlertCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
            <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }} data-testid="verify-error-title">Verification Failed</h1>
            <p className="text-sm mb-6" style={{ color: 'var(--aurem-body-secondary, #888)' }}>{message}</p>
            <Link to="/login" className="text-sm font-medium" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
              Return to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
