import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Lock, CheckCircle, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (res.ok) {
        setSuccess(true);
        toast.success('Password reset successfully!');
      } else {
        toast.error(data.detail || 'Failed to reset password');
      }
    } catch (err) {
      toast.error('Network error. Please try again.');
    }
    setLoading(false);
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--aurem-bg, #050505)' }}>
        <div className="text-center" data-testid="reset-invalid">
          <AlertCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
          <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>Invalid Reset Link</h1>
          <p className="text-sm mb-6" style={{ color: 'var(--aurem-body-secondary, #888)' }}>This password reset link is invalid or has expired.</p>
          <Link to="/forgot-password" className="text-sm font-medium" style={{ color: 'var(--aurem-accent, #F97316)' }}>
            Request a new reset link
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--aurem-bg, #050505)' }}>
      <div className="w-full max-w-md px-6">
        <Link to="/login" className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity" style={{ color: 'var(--aurem-accent, #F97316)' }} data-testid="reset-back-link">
          <ArrowLeft className="w-4 h-4" /> Back to Login
        </Link>

        {success ? (
          <div className="text-center" data-testid="reset-success">
            <CheckCircle className="w-16 h-16 mx-auto mb-4" style={{ color: '#FF6B00' }} />
            <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--aurem-heading, #F4F4F4)' }}>Password Reset!</h1>
            <p className="text-sm mb-6" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Your password has been reset successfully. You can now log in with your new password.</p>
            <Link to="/login" className="inline-block px-8 py-3 rounded-xl text-sm font-bold" style={{ background: 'linear-gradient(135deg, #F97316, #EA580C)', color: '#050505' }} data-testid="reset-login-link">
              Go to Login
            </Link>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-2">
              <Lock className="w-6 h-6" style={{ color: 'var(--aurem-accent, #F97316)' }} />
              <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading, #F4F4F4)' }} data-testid="reset-title">New Password</h1>
            </div>
            <p className="text-sm mb-8" style={{ color: 'var(--aurem-body-secondary, #888)' }}>
              Enter your new password below.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--aurem-body-secondary, #888)' }}>New Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 6 characters"
                  required
                  minLength={6}
                  data-testid="reset-password-input"
                  className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(212,175,55,0.15)', color: 'var(--aurem-heading, #F4F4F4)' }}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat password"
                  required
                  minLength={6}
                  data-testid="reset-confirm-input"
                  className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(212,175,55,0.15)', color: 'var(--aurem-heading, #F4F4F4)' }}
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                data-testid="reset-submit-btn"
                className="w-full py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #F97316, #EA580C)', color: '#050505' }}
              >
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
