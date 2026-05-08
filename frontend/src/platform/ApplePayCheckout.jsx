/**
 * ApplePayCheckout — Iteration 202
 * =================================
 * Embedded Stripe Checkout (zero-redirect) with Apple Pay / Google Pay.
 *
 * Stripe auto-shows Apple Pay on Safari/iOS/macOS, Google Pay on Chrome+Android
 * when the user has a card on the device — no extra config required.
 *
 * Usage:
 *   <ApplePayCheckout plan="growth" onComplete={() => load()} />
 */
import React, { useEffect, useState, useCallback } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from '@stripe/react-stripe-js';
import { Apple, Loader2, X, Zap } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

let _stripePromise = null;
async function getStripe() {
  if (_stripePromise) return _stripePromise;
  const r = await fetch(`${API}/api/stripe-embed/publishable-key`);
  const { publishable_key } = await r.json();
  _stripePromise = loadStripe(publishable_key);
  return _stripePromise;
}

export default function ApplePayCheckout({ plan = 'starter', onComplete }) {
  const [open, setOpen] = useState(false);
  const [stripe, setStripe] = useState(null);
  const [clientSecret, setClientSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [annual, setAnnual] = useState(false);

  const openSheet = useCallback(async () => {
    setError('');
    setLoading(true);
    try {
      const s = await getStripe();
      setStripe(s);
      const tok = getPlatformToken();
      const r = await fetch(`${API}/api/stripe-embed/create-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ plan, annual, return_url: window.location.origin }),
      });
      const d = await r.json();
      if (!r.ok || !d.client_secret) throw new Error(d.detail || 'Could not open checkout');
      setClientSecret(d.client_secret);
      setOpen(true);
    } catch (e) {
      setError(e.message || 'Failed to open checkout');
    }
    setLoading(false);
  }, [plan, annual]);

  const close = () => { setOpen(false); setClientSecret(''); };

  const handleComplete = useCallback(() => {
    close();
    if (typeof onComplete === 'function') onComplete();
  }, [onComplete]);

  return (
    <div data-testid={`applepay-wrapper-${plan}`}>
      {/* Annual 20% off toggle */}
      <label
        data-testid={`applepay-annual-toggle-${plan}`}
        style={{
          display:'inline-flex',alignItems:'center',gap:8,fontSize:11,
          color: annual ? '#4ADE80' : '#8A8070',letterSpacing:'0.06em',
          textTransform:'uppercase',fontWeight:700,cursor:'pointer',marginBottom:8,
          padding:'6px 10px',borderRadius:20,
          border:`1px solid ${annual ? 'rgba(74,222,128,0.35)' : 'rgba(255,255,255,0.08)'}`,
          background: annual ? 'rgba(74,222,128,0.08)' : 'transparent',
        }}
      >
        <input
          type="checkbox"
          checked={annual}
          onChange={(e) => setAnnual(e.target.checked)}
          style={{accentColor:'#4ADE80'}}
          data-testid={`applepay-annual-checkbox-${plan}`}
        />
        Annual — 20% off
      </label>
      <br/>
      <button
        data-testid={`applepay-open-${plan}`}
        onClick={openSheet}
        disabled={loading}
        style={{
          display:'inline-flex',alignItems:'center',gap:8,padding:'12px 20px',
          background:'#000',color:'#FFF',border:'1px solid #FFF',borderRadius:10,
          fontSize:13,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
          cursor:'pointer',fontFamily:"'Jost',sans-serif",
        }}
      >
        {loading ? <Loader2 size={14} style={{animation:'spin 1s linear infinite'}}/> : <Apple size={16} fill="#FFF"/>}
        {loading ? 'Opening…' : `Pay with Apple Pay · ${plan.toUpperCase()}${annual ? ' · ANNUAL' : ''}`}
      </button>
      <p style={{fontSize:10.5,letterSpacing:'0.1em',color:'#8A8070',marginTop:6,display:'flex',alignItems:'center',gap:6}}>
        <Zap size={10} color="#4ADE80"/> One-tap · Google Pay &amp; card also supported · HST auto-applied · Zero redirects
      </p>

      {error && (
        <div data-testid={`applepay-error-${plan}`} style={{marginTop:10,padding:'8px 12px',background:'rgba(239,68,68,0.08)',border:'1px solid rgba(239,68,68,0.3)',borderRadius:8,color:'#EF4444',fontSize:12}}>
          {error}
        </div>
      )}

      {open && stripe && clientSecret && (
        <div
          data-testid={`applepay-sheet-${plan}`}
          onClick={close}
          style={{
            position:'fixed',inset:0,background:'rgba(0,0,0,0.82)',zIndex:999,
            display:'flex',alignItems:'center',justifyContent:'center',padding:20,
          }}
        >
          <div onClick={(e)=>e.stopPropagation()} style={{
            width:'100%',maxWidth:560,maxHeight:'92vh',overflowY:'auto',
            background:'#FFF',borderRadius:16,position:'relative',
          }}>
            <button
              data-testid={`applepay-close-${plan}`}
              onClick={close}
              style={{
                position:'absolute',top:12,right:12,zIndex:1,background:'rgba(0,0,0,0.06)',
                border:'none',borderRadius:20,width:32,height:32,display:'flex',
                alignItems:'center',justifyContent:'center',cursor:'pointer',
              }}
            >
              <X size={16}/>
            </button>
            <EmbeddedCheckoutProvider
              stripe={stripe}
              options={{ clientSecret, onComplete: handleComplete }}
            >
              <EmbeddedCheckout />
            </EmbeddedCheckoutProvider>
          </div>
        </div>
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
