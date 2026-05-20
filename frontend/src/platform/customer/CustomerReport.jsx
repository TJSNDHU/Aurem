/**
 * CustomerReport — Monthly PDF report (auto-generated 1st of month)
 */
import React, { useEffect, useState } from 'react';
import { Download, Calendar, FileText, RefreshCw } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerReport({ ctx }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [msg, setMsg] = useState('');

  const load = () => {
    const tok = getPlatformToken();
    setLoading(true);
    fetch(`${API}/api/customer/reports`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : { reports: [] })
      .then(d => setReports(d.reports || []))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const generateNow = async () => {
    setGenerating(true); setMsg('');
    try {
      const tok = getPlatformToken();
      const res = await fetch(`${API}/api/customer/reports/generate`, { method:'POST', headers: { Authorization: `Bearer ${tok}` } });
      const d = await res.json();
      setMsg(d.message || 'Report queued. You\'ll get it on WhatsApp + Email.');
      setTimeout(load, 2000);
    } catch (e) { setMsg('Failed to queue report'); }
    setGenerating(false);
  };

  return (
    <div data-testid="customer-report">
      <h1 style={title}>Monthly Report</h1>
      <p style={sub}>Auto-generated on the 1st of each month. Sent via WhatsApp + Email.</p>

      <div style={card}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:14}}>
          <h3 style={sectionH}>Your Reports</h3>
          <div style={{display:'flex',gap:8}}>
            <button data-testid="report-generate" onClick={generateNow} disabled={generating} style={primaryBtn}>
              <RefreshCw size={13}/> {generating ? 'Generating…' : 'Generate Now'}
            </button>
          </div>
        </div>
        {msg && <div data-testid="report-msg" style={{fontSize:12,color:'#4ADE80',marginBottom:12}}>{msg}</div>}

        {loading ? (
          <p style={{fontSize:12,color:'#8A8070'}}>Loading reports…</p>
        ) : reports.length === 0 ? (
          <div style={{padding:'30px 20px',textAlign:'center'}}>
            <FileText size={36} color="#8A8070" style={{margin:'0 auto 12px',opacity:0.4}}/>
            <p style={{fontSize:13,color:'#8A8070'}}>No reports yet. Your first report arrives on the 1st of next month, or click "Generate Now" for a preview.</p>
          </div>
        ) : (
          <ul style={{margin:0,padding:0,listStyle:'none'}}>
            {reports.map((r, i) => (
              <li key={i} data-testid={`report-${r.month || i}`} style={{display:'flex',alignItems:'center',gap:12,padding:'12px 0',borderBottom:i<reports.length-1?'1px solid rgba(255,255,255,0.04)':'none'}}>
                <Calendar size={16} color="#D4AF37"/>
                <div style={{flex:1}}>
                  <div style={{fontSize:13,color:'#E8E0D0',fontWeight:600}}>{r.title || r.month || 'Report'}</div>
                  <div style={{fontSize:11,color:'#8A8070'}}>{r.generated_at?.slice(0,10) || ''}</div>
                </div>
                {r.url && (
                  <a data-testid={`report-download-${r.month || i}`} href={r.url} target="_blank" rel="noreferrer" style={{padding:'8px 14px',borderRadius:8,background:'rgba(212,175,55,0.08)',border:'1px solid rgba(212,175,55,0.2)',color:'#D4AF37',fontSize:11,textDecoration:'none',fontWeight:600,display:'inline-flex',alignItems:'center',gap:6}}>
                    <Download size={12}/> PDF
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
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
const primaryBtn = { display:'inline-flex',alignItems:'center',gap:8, padding:'8px 14px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:8, fontSize:11, fontWeight:700, letterSpacing:'0.08em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
