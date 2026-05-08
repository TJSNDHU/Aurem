/**
 * AUREM Welcome Card Modal
 * Shows on first login with Business ID, QR code, and setup instructions.
 * Auto-closes after 60 seconds.
 */
import React, { useState, useEffect , useCallback} from 'react';
import { X, Copy, Check, Mail, ChevronRight, Smartphone, Watch } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function WelcomeCard({ token, onDismiss }) {
  const [bizId, setBizId] = useState('');
  const [bizName, setBizName] = useState('');
  const [qrData, setQrData] = useState(null);
  const [copied, setCopied] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [visible, setVisible] = useState(false);

  const handleDismiss = useCallback(async () => {
    setVisible(false);
    try {
      await fetch(`${API}/api/business-id/dismiss-welcome`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
    } catch {}
    setTimeout(() => onDismiss?.(), 300);
  }, [token, onDismiss]);

  useEffect(() => {
    // Fade in
    setTimeout(() => setVisible(true), 50);
    // Auto close after 60s
    const timer = setTimeout(() => handleDismiss(), 60000);
    return () => clearTimeout(timer);
  }, [token, onDismiss]);

  useEffect(() => {
    if (!token) return;
    const h = { 'Authorization': `Bearer ${token}` };
    // Load business ID
    fetch(`${API}/api/business-id/mine`, { headers: h })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          setBizId(d.business_id || '');
          setBizName(d.business_name || '');
          // Load QR
          if (d.business_id) {
            fetch(`${API}/api/business-id/qr/${d.business_id}`, { headers: h })
              .then(r => r.ok ? r.json() : null)
              .then(q => { if (q) setQrData(q); })
              .catch(() => {});
          }
        }
      })
      .catch(() => {});
  }, [token]);

  const handleCopy = () => {
    if (bizId) {
      navigator.clipboard?.writeText(bizId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleResend = async () => {
    setResending(true);
    try {
      await fetch(`${API}/api/business-id/resend-welcome`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      setResent(true);
    } catch {}
    setResending(false);
  };

  return (
    <div
      data-testid="welcome-card-overlay"
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
        opacity: visible ? 1 : 0,
        transition: 'opacity 0.3s ease',
      }}
    >
      <div
        data-testid="welcome-card"
        style={{
          width: '100%', maxWidth: 480, maxHeight: '90vh', overflowY: 'auto',
          background: '#0A0A14',
          border: '1px solid rgba(201,168,76,0.25)',
          borderRadius: 20,
          boxShadow: '0 40px 120px rgba(0,0,0,0.9), 0 0 60px rgba(201,168,76,0.06)',
          transform: visible ? 'scale(1) translateY(0)' : 'scale(0.95) translateY(20px)',
          transition: 'transform 0.3s cubic-bezier(0.16,1,0.3,1)',
        }}
        className="ora-hide-scroll"
      >
        {/* Header */}
        <div style={{ padding: '24px 24px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontFamily: "'Cinzel',serif", fontSize: 18, fontWeight: 700, color: '#C9A84C', letterSpacing: '0.04em', marginBottom: 4 }}>
              Welcome to AUREM
            </div>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 13, color: '#9A9490' }}>
              {bizName ? `${bizName} is now live.` : 'Your system is live.'}
            </div>
          </div>
          <button data-testid="welcome-close" onClick={handleDismiss} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
            <X size={18} color="#6A6070" />
          </button>
        </div>

        {/* Business ID */}
        <div style={{ padding: '20px 24px' }}>
          <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 10 }}>YOUR BUSINESS ID</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div data-testid="welcome-bid" style={{
              flex: 1, padding: '14px 20px', borderRadius: 12,
              background: 'rgba(255,107,0,0.06)', border: '1px solid rgba(255,107,0,0.2)',
              fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 700,
              color: '#FF6B00', letterSpacing: '0.08em', textAlign: 'center',
            }}>
              {bizId || '---'}
            </div>
            <button data-testid="welcome-copy" onClick={handleCopy} style={{
              width: 44, height: 44, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(255,107,0,0.08)', border: '1px solid rgba(255,107,0,0.15)', cursor: 'pointer',
            }}>
              {copied ? <Check size={16} color="#4ADE80" /> : <Copy size={16} color="#FF6B00" />}
            </button>
          </div>
        </div>

        {/* QR Code */}
        <div style={{ padding: '0 24px 20px', textAlign: 'center' }}>
          <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 12, textAlign: 'left' }}>CONNECT YOUR PHONE</div>
          {qrData ? (
            <div style={{ padding: 16, borderRadius: 16, background: 'rgba(201,168,76,0.04)', border: '1px solid rgba(201,168,76,0.12)', display: 'inline-block' }}>
              <img data-testid="welcome-qr" src={`data:image/png;base64,${qrData.qr_base64}`} alt="Business QR" style={{ width: 200, height: 200, borderRadius: 8 }} />
            </div>
          ) : (
            <div style={{ padding: 40, borderRadius: 16, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
              <div style={{ width: 24, height: 24, border: '2px solid rgba(201,168,76,0.3)', borderTop: '2px solid #C9A84C', borderRadius: '50%', animation: 'oraSpin 1s linear infinite', margin: '0 auto' }} />
            </div>
          )}
          <p style={{ fontFamily: "'Jost',sans-serif", fontSize: 12, color: '#9A9490', marginTop: 12 }}>
            Point your phone camera at this code.<br />ORA opens pre-connected to {bizName || 'your business'}.
          </p>
        </div>

        {/* Watch Section */}
        <div style={{ padding: '0 24px 20px' }}>
          <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6A6070', marginBottom: 10 }}>SMARTWATCH</div>
          <div style={{ padding: 14, borderRadius: 12, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <p style={{ fontFamily: "'Jost',sans-serif", fontSize: 12, color: '#9A9490', margin: 0, lineHeight: 1.6 }}>
              Once ORA is on your phone, your watch gets alerts automatically.
            </p>
            <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Watch size={12} color="#C9A84C" />
                <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#8A8070' }}>Apple Watch: automatic</span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
              <Smartphone size={12} color="#C9A84C" />
              <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#8A8070' }}>Android Watch: enable in Wearable settings</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ padding: '0 24px 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button
            data-testid="welcome-resend"
            onClick={handleResend}
            disabled={resending || resent}
            style={{
              width: '100%', padding: '12px', borderRadius: 12,
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
              color: resent ? '#4ADE80' : '#9A9490', cursor: resent ? 'default' : 'pointer',
              fontFamily: "'Jost',sans-serif", fontSize: 12, fontWeight: 500,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
          >
            <Mail size={14} />
            {resent ? 'Sent!' : resending ? 'Sending...' : 'Resend to my email'}
          </button>
          <button
            data-testid="welcome-open-dashboard"
            onClick={handleDismiss}
            style={{
              width: '100%', padding: '14px', borderRadius: 12,
              background: '#FF6B00', border: 'none',
              color: '#FFF', cursor: 'pointer',
              fontFamily: "'Jost',sans-serif", fontSize: 14, fontWeight: 600,
              letterSpacing: '0.03em',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
          >
            Open Dashboard <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
