/**
 * CustomerBilling — Stripe subscription + invoices + Apple Pay embedded
 */
import React, { useEffect, useState } from 'react';
import { CreditCard, ExternalLink, Loader2 } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';
import ApplePayCheckout from '../ApplePayCheckout';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerBilling({ ctx }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);

  useEffect(() => {
    const tok = getPlatformToken();
    fetch(`${API}/api/customer/billing`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => setData(d))
      .finally(() => setLoading(false));
  }, []);

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const tok = getPlatformToken();
      const res = await fetch(`${API}/api/customer/billing/portal`, { method:'POST', headers: { Authorization: `Bearer ${tok}` } });
      const d = await res.json();
      if (d.url) window.location.href = d.url;
    } catch {}
    setPortalLoading(false);
  };

  if (loading) return <div data-testid="billing-loading" style={{color:'#8A8070'}}>Loading billing…</div>;

  return (
    <div data-testid="customer-billing">
      <h1 style={title}>Billing</h1>
      <p style={sub}>Manage your plan, update payment method, and download invoices.</p>

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:12,marginBottom:16}}>
        <div data-testid="billing-plan" style={card}>
          <div style={label}>Current Plan</div>
          <div style={{fontSize:22,fontWeight:800,color:'#FFF',fontFamily:"'Cinzel',serif"}}>{data?.plan_name || ctx.plan || 'Trial'}</div>
          <div style={{fontSize:11,color:'#D4AF37',marginTop:4}}>{data?.status || 'Active'}</div>
        </div>
        <div data-testid="billing-next" style={card}>
          <div style={label}>Next Invoice</div>
          <div style={{fontSize:22,fontWeight:800,color:'#FFF',fontFamily:"'Cinzel',serif"}}>{data?.next_invoice_amount ? `$${data.next_invoice_amount}` : '—'}</div>
          <div style={{fontSize:11,color:'#8A8070',marginTop:4}}>{data?.next_invoice_date?.slice(0,10) || 'N/A'}</div>
        </div>
        <div data-testid="billing-method" style={card}>
          <div style={label}>Payment Method</div>
          <div style={{fontSize:15,fontWeight:600,color:'#E8E0D0',marginTop:6}}>{data?.payment_method?.last4 ? `•••• ${data.payment_method.last4}` : 'Not on file'}</div>
          <div style={{fontSize:11,color:'#8A8070',marginTop:4}}>{data?.payment_method?.brand || ''}</div>
        </div>
      </div>

      <div style={card}>
        <h3 style={sectionH}>Manage Subscription</h3>
        <p style={{fontSize:12,color:'#8A8070',lineHeight:1.6,marginBottom:14}}>
          Open the secure Stripe portal to update your card, view past invoices, or change your plan.
        </p>
        <button data-testid="billing-portal" onClick={openPortal} disabled={portalLoading} style={primaryBtn}>
          {portalLoading ? <Loader2 size={13} style={{animation:'spin 1s linear infinite'}}/> : <ExternalLink size={13}/>} Open Stripe Portal
        </button>
      </div>

      {/* Apple Pay one-tap — embedded, zero redirects */}
      <div style={{...card, marginTop:16}} data-testid="billing-applepay-block">
        <h3 style={sectionH}>One-tap Upgrade</h3>
        <p style={{fontSize:12,color:'#8A8070',lineHeight:1.6,marginTop:10,marginBottom:14}}>
          Upgrade or subscribe inline without leaving AUREM. Apple Pay shows automatically on Safari + iOS, Google Pay on Chrome + Android.
        </p>
        <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
          <ApplePayCheckout plan="starter" onComplete={() => window.location.reload()} />
          <ApplePayCheckout plan="growth" onComplete={() => window.location.reload()} />
          <ApplePayCheckout plan="enterprise" onComplete={() => window.location.reload()} />
        </div>
      </div>

      <div style={{...card, marginTop:16}}>
        <h3 style={sectionH}>Invoices</h3>
        {(data?.invoices || []).length === 0 ? (
          <p style={{fontSize:12,color:'#8A8070',marginTop:10}}>No invoices yet.</p>
        ) : (
          <ul style={{margin:'12px 0 0',padding:0,listStyle:'none'}}>
            {data.invoices.map((inv, i) => (
              <li key={i} data-testid={`invoice-${i}`} style={{display:'flex',alignItems:'center',gap:10,padding:'10px 0',borderBottom:i<data.invoices.length-1?'1px solid rgba(255,255,255,0.04)':'none'}}>
                <CreditCard size={14} color="#8A8070"/>
                <div style={{flex:1}}>
                  <div style={{fontSize:13,color:'#E8E0D0'}}>${inv.amount} — {inv.date?.slice(0,10)}</div>
                  <div style={{fontSize:11,color:'#8A8070'}}>{inv.status}</div>
                </div>
                {inv.url && <a href={inv.url} target="_blank" rel="noreferrer" style={{fontSize:11,color:'#D4AF37',textDecoration:'none'}}>View</a>}
              </li>
            ))}
          </ul>
        )}
      </div>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

const title = { fontFamily:"'Cinzel',serif", fontSize:26, fontWeight:700, color:'#FFF', letterSpacing:'0.03em', marginBottom:4 };
const sub = { fontSize:13, color:'#8A8070', marginBottom:20 };
const card = {
  borderRadius: 18,
  padding: 22,
  background: 'rgba(15,18,28,0.55)',
  backdropFilter: 'blur(22px) saturate(150%)',
  WebkitBackdropFilter: 'blur(22px) saturate(150%)',
  border: '1px solid rgba(212,175,55,0.14)',
  boxShadow: '0 16px 44px rgba(0,0,0,0.35), inset 0 1px 0 rgba(212,175,55,0.08)',
};
const sectionH = { fontFamily:"'Cinzel',serif", fontSize:14, fontWeight:700, color:'#D4AF37', letterSpacing:'0.1em', textTransform:'uppercase', margin:0 };
const label = { fontSize:10, letterSpacing:'0.18em', color:'#8A8070', fontWeight:600, textTransform:'uppercase', marginBottom:8 };
const primaryBtn = { display:'inline-flex',alignItems:'center',gap:8, padding:'10px 18px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:9, fontSize:12, fontWeight:700, letterSpacing:'0.1em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
