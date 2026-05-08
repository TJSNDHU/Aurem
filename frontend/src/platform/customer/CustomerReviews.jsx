/**
 * CustomerReviews — Google Reviews dashboard (pull + auto-request)
 */
import React, { useEffect, useState } from 'react';
import { Star, Send, RefreshCw, ExternalLink } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerReviews({ ctx }) {
  const [data, setData] = useState({ reviews: [], stats: {} });
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [msg, setMsg] = useState('');

  const load = () => {
    const tok = getPlatformToken();
    setLoading(true);
    fetch(`${API}/api/customer/reviews`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : { reviews: [], stats: {} })
      .then(d => setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const requestReviews = async () => {
    setSending(true); setMsg('');
    try {
      const tok = getPlatformToken();
      const res = await fetch(`${API}/api/customer/reviews/request-batch`, {
        method: 'POST', headers: { Authorization: `Bearer ${tok}` },
      });
      const d = await res.json();
      setMsg(d.message || 'Review requests queued.');
    } catch (e) { setMsg('Failed to queue requests'); }
    setSending(false);
  };

  const stars = data.stats.avg_rating || 0;

  return (
    <div data-testid="customer-reviews">
      <h1 style={title}>Google Reviews</h1>
      <p style={sub}>Reviews auto-pulled from Google. Send review requests to recent customers in one tap.</p>

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:20}}>
        <StatCard testid="review-avg" label="Avg Rating" value={stars ? stars.toFixed(1) : '—'} sub={stars ? '★★★★★'.slice(0, Math.round(stars)) : ''}/>
        <StatCard testid="review-total" label="Total Reviews" value={data.stats.total || 0} sub="On Google"/>
        <StatCard testid="review-requests-sent" label="Requests Sent" value={data.stats.requests_sent || 0} sub="This month"/>
        <StatCard testid="review-requests-received" label="New Reviews" value={data.stats.new_reviews || 0} sub="From requests"/>
      </div>

      <div style={card}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:14}}>
          <h3 style={sectionH}>Recent Reviews</h3>
          <button data-testid="review-refresh" onClick={load} style={iconBtn}><RefreshCw size={14}/></button>
        </div>
        {loading ? (
          <p style={{fontSize:12,color:'#8A8070'}}>Loading...</p>
        ) : (data.reviews || []).length === 0 ? (
          <p style={{fontSize:12,color:'#8A8070'}}>No reviews yet. Click below to send review requests to your latest customers.</p>
        ) : (
          <ul style={{margin:0,padding:0,listStyle:'none'}}>
            {data.reviews.slice(0,10).map((r, i) => (
              <li key={i} style={{padding:'12px 0',borderBottom:i<data.reviews.length-1?'1px solid rgba(255,255,255,0.04)':'none'}}>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:4}}>
                  <span style={{fontSize:13,fontWeight:600,color:'#E8E0D0'}}>{r.author || 'Anonymous'}</span>
                  <span style={{color:'#D4AF37',fontSize:12}}>{'★'.repeat(r.rating || 0)}</span>
                </div>
                <p style={{fontSize:12,color:'#A89E88',margin:0,lineHeight:1.5}}>{r.text || ''}</p>
                <div style={{fontSize:10,color:'#5A5468',marginTop:4}}>{r.date || ''}</div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div style={{...card, marginTop:16}}>
        <h3 style={sectionH}>Auto-request reviews</h3>
        <p style={{fontSize:12,color:'#8A8070',lineHeight:1.6,marginBottom:14}}>
          AUREM will send a polite WhatsApp message to your recent customers:
          <br/><span style={{fontStyle:'italic',color:'#A89E88'}}>"Thanks for visiting! If you enjoyed your experience, we'd love your review: [link]"</span>
        </p>
        <button data-testid="review-request-batch" onClick={requestReviews} disabled={sending} style={primaryBtn}>
          <Send size={13}/> {sending ? 'Queueing…' : 'Send Batch Requests'}
        </button>
        {msg && <div data-testid="review-batch-msg" style={{fontSize:12,color:'#4ADE80',marginTop:10}}>{msg}</div>}
      </div>
    </div>
  );
}

function StatCard({ testid, label, value, sub }) {
  return (
    <div data-testid={testid} style={card}>
      <div style={{fontSize:10,letterSpacing:'0.18em',color:'#8A8070',fontWeight:600,textTransform:'uppercase',marginBottom:8}}>{label}</div>
      <div style={{fontSize:24,fontWeight:800,color:'#FFF',fontFamily:"'Cinzel',serif"}}>{value}</div>
      {sub && <div style={{fontSize:11,color:'#D4AF37',marginTop:4}}>{sub}</div>}
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
const iconBtn = { padding:8, borderRadius:8, background:'transparent', border:'1px solid rgba(212,175,55,0.15)', color:'#8A8070', cursor:'pointer' };
const primaryBtn = { display:'inline-flex',alignItems:'center',gap:8, padding:'10px 18px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:9, fontSize:12, fontWeight:700, letterSpacing:'0.1em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
