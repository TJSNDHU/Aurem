/**
 * CustomerReferrals — Share BIN, track referrals, earn a free month
 */
import React, { useEffect, useState } from 'react';
import { Copy, Check, Gift, Share2 } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerReferrals({ ctx }) {
  const [data, setData] = useState({ referrals: [], count_successful: 0, rewards_earned: 0 });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const tok = getPlatformToken();
    fetch(`${API}/api/customer/referrals`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : { referrals: [], count_successful: 0, rewards_earned: 0 })
      .then(d => setData(d))
      .catch(() => {});
  }, []);

  const shareUrl = `${window.location.origin}/platform/signup?ref=${encodeURIComponent(ctx.bin)}`;
  const shareMsg = `Try AUREM — AI autopilot for small business. Use my referral to get started: ${shareUrl}`;

  const copy = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shareWA = () => {
    window.open(`https://wa.me/?text=${encodeURIComponent(shareMsg)}`, '_blank');
  };

  return (
    <div data-testid="customer-referrals">
      <h1 style={title}>Refer & Earn</h1>
      <p style={sub}>Share your BIN. Every friend who subscribes = 1 free month for you.</p>

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:16}}>
        <Stat testid="ref-shared" label="Referrals Sent" value={(data.referrals || []).length}/>
        <Stat testid="ref-successful" label="Successful" value={data.count_successful || 0}/>
        <Stat testid="ref-rewards" label="Free Months Earned" value={data.rewards_earned || 0}/>
      </div>

      <div style={card}>
        <h3 style={sectionH}><Gift size={14} style={{verticalAlign:'-2px',marginRight:8}}/>Your Referral Link</h3>
        <div style={{display:'flex',gap:8,marginTop:12,flexWrap:'wrap'}}>
          <input data-testid="ref-url" readOnly value={shareUrl} style={{flex:1,minWidth:240,padding:'10px 12px',background:'rgba(212,175,55,0.03)',border:'1px solid rgba(212,175,55,0.15)',borderRadius:8,color:'#E8E0D0',fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}/>
          <button data-testid="ref-copy" onClick={copy} style={primaryBtn}>
            {copied ? <Check size={13}/> : <Copy size={13}/>} {copied ? 'Copied' : 'Copy'}
          </button>
          <button data-testid="ref-share-wa" onClick={shareWA} style={{...primaryBtn, background:'linear-gradient(135deg,#25D366,#128C7E)'}}>
            <Share2 size={13}/> WhatsApp
          </button>
        </div>
        <p style={{fontSize:11,color:'#8A8070',marginTop:10}}>
          They can also enter your BIN <span style={{fontFamily:"'JetBrains Mono',monospace",color:'#D4AF37',fontWeight:700}}>{ctx.bin}</span> at signup.
        </p>
      </div>

      <div style={{...card, marginTop:16}}>
        <h3 style={sectionH}>Your Referrals</h3>
        {(data.referrals || []).length === 0 ? (
          <p style={{fontSize:12,color:'#8A8070',marginTop:10}}>No referrals yet. Share your link to get started!</p>
        ) : (
          <ul style={{margin:'12px 0 0',padding:0,listStyle:'none'}}>
            {data.referrals.map((r, i) => (
              <li key={i} data-testid={`ref-${i}`} style={{display:'flex',justifyContent:'space-between',padding:'9px 0',borderBottom:i<data.referrals.length-1?'1px solid rgba(255,255,255,0.04)':'none'}}>
                <span style={{fontSize:12,color:'#E8E0D0'}}>{r.email || r.masked_email}</span>
                <span style={{fontSize:11,color: r.status==='subscribed'?'#4ADE80':'#8A8070',fontWeight:600,textTransform:'uppercase',letterSpacing:'0.1em'}}>{r.status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Stat({ testid, label, value }) {
  return (
    <div data-testid={testid} style={card}>
      <div style={{fontSize:10,letterSpacing:'0.18em',color:'#8A8070',fontWeight:600,textTransform:'uppercase',marginBottom:8}}>{label}</div>
      <div style={{fontSize:24,fontWeight:800,color:'#FFF',fontFamily:"'Cinzel',serif"}}>{value}</div>
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
const sectionH = { fontFamily:"'Cinzel',serif", fontSize:14, fontWeight:700, color:'#D4AF37', letterSpacing:'0.1em', textTransform:'uppercase', margin:'0 0 4px' };
const primaryBtn = { display:'inline-flex',alignItems:'center',gap:6, padding:'10px 16px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:8, fontSize:11, fontWeight:700, letterSpacing:'0.08em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
