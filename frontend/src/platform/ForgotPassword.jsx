import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Mail, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setSent(true);
        toast.success('Reset link sent! Check your email.');
      } else {
        const data = await res.json();
        toast.error(data.detail || 'Something went wrong');
      }
    } catch (err) {
      toast.error('Network error. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--aurem-bg, #050505)' }}>
      <div className="w-full max-w-md px-6">
        <Link to="/login" className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity" style={{ color: 'var(--aurem-accent, #D4AF37)' }} data-testid="forgot-back-link">
          <ArrowLeft className="size-4" /> Back to Login
        </Link>

        {sent ? (
          <div className="text-center" data-testid="forgot-success">
            <CheckCircle className="size-16 mx-auto mb-4" style={{ color: '#FF6B00' }} />
            <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>Check Your Email</h1>
            <p className="text-sm mb-6" style={{ color: 'var(--aurem-body-secondary, #888)' }}>
              If an account exists for <strong style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>{email}</strong>, we've sent password reset instructions.
            </p>
            <Link to="/login" className="text-sm font-medium" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
              Return to Login
            </Link>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-2">
              <Mail className="size-6" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
              <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading, #F4F4F4)' }} data-testid="forgot-title">Reset Password</h1>
            </div>
            <p className="text-sm mb-8" style={{ color: 'var(--aurem-body-secondary, #888)' }}>
              Enter your email and we'll send you a link to reset your password.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  data-testid="forgot-email-input"
                  className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(212,175,55,0.15)',
                    color: 'var(--aurem-heading, #F4F4F4)',
                  }}
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                data-testid="forgot-submit-btn"
                className="w-full py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                style={{
                  background: 'linear-gradient(135deg, #D4AF37, #B8962E)',
                  color: '#050505',
                }}
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
