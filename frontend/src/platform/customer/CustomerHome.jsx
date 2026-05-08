/**
 * CustomerHome — Overview of key metrics (reviews, calls, visits)
 * Refactored iter 241: spatial-glass cards + stagger animations + lightning hover
 */
import React, { useEffect, useState } from 'react';
import { TrendingUp, Star, Phone, Eye, FileText, Gift, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getPlatformToken } from '../../utils/secureTokenStore';
import TrialBanner from '../TrialBanner';

const API = process.env.REACT_APP_BACKEND_URL || '';

function Stat({ icon:Icon, label, value, hint, testid, idx=0 }) {
  return (
    <motion.div
      data-testid={testid}
      initial={{ opacity: 0, y: 22, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.05 + idx * 0.06, type: 'spring', stiffness: 200, damping: 22 }}
      className="glass-card"
      style={{ padding: '22px 24px' }}
    >
      <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12}}>
        <div style={{width:34,height:34,borderRadius:10,background:'linear-gradient(135deg, rgba(249,115,22,0.22), rgba(201,162,39,0.1))',display:'flex',alignItems:'center',justifyContent:'center',boxShadow:'0 4px 14px rgba(249,115,22,0.18)'}}>
          <Icon size={16} color="#F97316" />
        </div>
        <span style={{fontSize:11,letterSpacing:'0.18em',color:'rgba(255,255,255,0.42)',fontWeight:600,textTransform:'uppercase'}}>{label}</span>
      </div>
      <div className="stat-number">{value}</div>
      {hint && <div className="stat-label">{hint}</div>}
    </motion.div>
  );
}

export default function CustomerHome({ ctx }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const tok = getPlatformToken();
    fetch(`${API}/api/client/activity`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : { events: [] })
      .then(d => setStats({ activity: d.events || [] }))
      .catch(() => setStats({ activity: [] }));
  }, []);

  const firstName = (ctx.full_name || '').split(' ')[0] || 'there';

  return (
    <div data-testid="customer-home">
      <motion.h1
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{fontFamily:"'Cinzel',serif",fontSize:34,fontWeight:600,color:'#FFF',letterSpacing:'0.02em',marginBottom:6,textShadow:'0 0 18px rgba(249,115,22,0.25)'}}
      >
        Hi {firstName}
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.08 }}
        style={{fontSize:13,color:'rgba(255,255,255,0.5)',marginBottom:24}}
      >
        Here's what AUREM did for <span style={{color:'#F97316',textShadow:'0 0 12px rgba(249,115,22,0.4)'}}>{ctx.business_name || ctx.bin}</span> recently.
      </motion.p>

      {/* Section 8 — Trial banner (auto-hides on paid / no-trial) */}
      <TrialBanner />

      {/* Smart Onboarding banner — visible until completed */}
      {ctx && ctx.role !== 'admin' && ctx.smart_onboarding_complete === false && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, type: 'spring', stiffness: 180, damping: 22 }}
        >
          <Link
            to="/my/onboarding"
            data-testid="smart-onboarding-banner"
            className="trial-banner"
            style={{
              display:'flex',alignItems:'center',gap:14,
              marginBottom:20,textDecoration:'none',color:'#FFF',
            }}
          >
            <Sparkles size={22} color="#F97316" className="lightning-pulse"/>
            <div style={{flex:1}}>
              <div style={{fontFamily:"'Cinzel',serif",fontSize:14,fontWeight:700,color:'#F97316',letterSpacing:'0.08em',textTransform:'uppercase'}}>Finish Smart Setup</div>
              <div style={{fontSize:12.5,color:'#E8E0D0',marginTop:3}}>Auto-detect your website platform, socials &amp; Google listing — one-click start.</div>
            </div>
            <span className="btn-aurem-primary" style={{fontSize:11,padding:'8px 14px'}}>Start</span>
          </Link>
        </motion.div>
      )}

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:14,marginBottom:24}}>
        <Stat testid="stat-reviews" idx={0} icon={Star} label="Reviews" value="—" hint="Auto-collected from Google" />
        <Stat testid="stat-calls" idx={1} icon={Phone} label="Calls" value="—" hint="Via ORA voice & inbound" />
        <Stat testid="stat-visits" idx={2} icon={Eye} label="Website Visits" value="—" hint="Last 30 days" />
        <Stat testid="stat-leads" idx={3} icon={TrendingUp} label="New Leads" value="—" hint="In pipeline" />
      </div>

      {/* Quick links */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, type: 'spring', stiffness: 180, damping: 22 }}
        className="glass-card"
        style={{padding:24,marginBottom:20}}
      >
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:14,fontWeight:700,color:'#F97316',letterSpacing:'0.1em',textTransform:'uppercase',marginBottom:14}}>Quick Actions</h3>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:10}}>
          <Link to="/my/website" data-testid="quick-edit-site" style={quickLink}>Edit my website</Link>
          <Link to="/my/reviews" data-testid="quick-reviews" style={quickLink}>Request reviews</Link>
          <Link to="/my/ora" data-testid="quick-ora" style={quickLink}>Ask ORA</Link>
          <Link to="/my/referrals" data-testid="quick-refer" style={quickLink}><Gift size={14} style={{marginRight:6,verticalAlign:'-2px'}}/>Refer & earn</Link>
          <Link to="/my/report" data-testid="quick-report" style={quickLink}><FileText size={14} style={{marginRight:6,verticalAlign:'-2px'}}/>Latest report</Link>
        </div>
      </motion.div>

      {/* Activity Feed */}
      <motion.div
        data-testid="activity-feed"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, type: 'spring', stiffness: 180, damping: 22 }}
        className="glass-card"
        style={{padding:24}}
      >
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:14,fontWeight:700,color:'#F97316',letterSpacing:'0.1em',textTransform:'uppercase',marginBottom:14}}>Recent Activity</h3>
        {stats?.activity?.length ? (
          <ul style={{margin:0,padding:0,listStyle:'none'}}>
            {stats.activity.slice(0,8).map((ev, i) => (
              <motion.li
                key={i}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.55 + i * 0.04 }}
                style={{padding:'10px 0',borderBottom:i<stats.activity.length-1?'1px solid rgba(255,255,255,0.04)':'none',display:'flex',justifyContent:'space-between',gap:12}}
              >
                <span style={{fontSize:13,color:'#E8E0D0'}}>{ev.description}</span>
                <span style={{fontSize:11,color:'#5A5468',flexShrink:0}}>{ev.timestamp?.slice(0,10)}</span>
              </motion.li>
            ))}
          </ul>
        ) : (
          <p style={{fontSize:12,color:'#8A8070'}}>No recent activity yet. Your agents are warming up.</p>
        )}
      </motion.div>
    </div>
  );
}

const quickLink = {
  padding:'14px 16px', borderRadius:10,
  background:'rgba(249,115,22,0.06)',
  border:'1px solid rgba(249,115,22,0.16)',
  color:'#E8E0D0', fontSize:13, textDecoration:'none', fontWeight:500,
  transition:'all 0.25s cubic-bezier(.25,.8,.25,1)',
};
