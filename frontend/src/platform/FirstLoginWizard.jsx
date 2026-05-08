/**
 * FirstLoginWizard — 4-step post-BIN-login onboarding
 * ====================================================
 * Triggered if must_set_password=true OR wizard_complete=false.
 * Steps:
 *   1. Set Password (required if must_set_password)
 *   2. Confirm Business Details (name, industry, city, phone)
 *   3. Preferences (tone, services, goals)
 *   4. Finish (tour intro)
 */

import React, { useState } from 'react';
import { Check, ChevronRight, Eye, EyeOff, Loader2, Gift, Activity, Zap } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

const TONE_OPTIONS = ['Professional', 'Friendly', 'Casual', 'Luxury', 'Energetic'];
const GOAL_OPTIONS = ['More Leads', 'More Reviews', 'More Calls', 'Brand Awareness', 'Retention'];

export default function FirstLoginWizard({ ctx, onComplete }) {
  const mustSetPw = !!ctx?.must_set_password;
  const [step, setStep] = useState(mustSetPw ? 1 : 2);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Step 1
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [showPw, setShowPw] = useState(false);

  // Step 2
  const [businessName, setBusinessName] = useState(ctx?.business_name || '');
  const [industry, setIndustry] = useState(ctx?.industry || '');
  const [city, setCity] = useState(ctx?.city || '');
  const [phone, setPhone] = useState(ctx?.phone || '');

  // Step 3
  const [tone, setTone] = useState('Professional');
  const [services, setServices] = useState('');
  const [goals, setGoals] = useState([]);

  const apiHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getPlatformToken()}`,
  });

  const submitStep1 = async () => {
    setError('');
    if (pw.length < 8) return setError('Password must be at least 8 characters');
    if (pw !== pw2) return setError('Passwords do not match');
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/bin-auth/first-login/set-password`, {
        method: 'POST', headers: apiHeaders(),
        body: JSON.stringify({ new_password: pw }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to set password');
      await saveWizardStep(1, {});
      setStep(2);
    } catch (e) { setError(e.message); }
    setSaving(false);
  };

  const submitStep2 = async () => {
    setError('');
    if (!businessName.trim()) return setError('Business name is required');
    setSaving(true);
    try {
      await saveWizardStep(2, {
        business_name: businessName.trim(),
        industry: industry.trim(),
        city: city.trim(),
        phone: phone.trim(),
      });
      setStep(3);
    } catch (e) { setError(e.message); }
    setSaving(false);
  };

  const submitStep3 = async () => {
    setSaving(true);
    try {
      await saveWizardStep(3, {
        tone,
        services: services.split(',').map(s => s.trim()).filter(Boolean),
        goals,
      });
      setStep(4);
    } catch (e) { setError(e.message); }
    setSaving(false);
  };

  const submitFinish = async () => {
    setSaving(true);
    try {
      await saveWizardStep(4, {});
      onComplete();
    } catch (e) { setError(e.message); }
    setSaving(false);
  };

  const saveWizardStep = async (stepNum, data) => {
    const res = await fetch(`${API}/api/bin-auth/first-login/wizard`, {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ step: stepNum, data }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || 'Failed to save');
    }
  };

  const toggleGoal = (g) => setGoals(prev => prev.includes(g) ? prev.filter(x=>x!==g) : [...prev, g]);

  return (
    <div data-testid="first-login-wizard" style={{
      position:'fixed',inset:0,zIndex:200,background:'rgba(5,5,7,0.96)',
      backdropFilter:'blur(12px)',display:'flex',alignItems:'center',justifyContent:'center',
      padding:20,fontFamily:"'Jost',sans-serif"
    }}>
      <div style={{
        width:'100%',maxWidth:520,background:'#0D0D17',border:'1px solid rgba(212,175,55,0.15)',
        borderRadius:20,padding:'32px 28px',boxShadow:'0 20px 80px rgba(0,0,0,0.6)',maxHeight:'92vh',overflowY:'auto'
      }}>
        {/* Progress */}
        <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:24}}>
          {[1,2,3,4].map(n => (
            <React.Fragment key={n}>
              <div data-testid={`wizard-step-indicator-${n}`} style={{
                width:28,height:28,borderRadius:'50%',border:`1.5px solid ${n<=step?'#D4AF37':'rgba(255,255,255,0.12)'}`,
                background:n<step?'#D4AF37':'transparent',color:n<step?'#0A0A00':(n===step?'#D4AF37':'#555'),
                display:'flex',alignItems:'center',justifyContent:'center',fontSize:12,fontWeight:700,flexShrink:0
              }}>
                {n<step ? <Check size={13}/> : n}
              </div>
              {n < 4 && <div style={{flex:1,height:1.5,background:n<step?'#D4AF37':'rgba(255,255,255,0.08)'}}/>}
            </React.Fragment>
          ))}
        </div>

        {/* Step 1: Password */}
        {step === 1 && (
          <div data-testid="wizard-step-1">
            <h2 style={{fontFamily:"'Cinzel',serif",fontSize:22,fontWeight:700,color:'#FFF',letterSpacing:'0.03em',marginBottom:8}}>Secure Your Account</h2>
            <p style={{fontSize:13,color:'#8A8070',lineHeight:1.5,marginBottom:20}}>Welcome! Let's replace your temporary password with one only you know.</p>
            <div style={{marginBottom:14}}>
              <label style={labelS}>New Password</label>
              <div style={{position:'relative'}}>
                <input data-testid="wizard-new-password" type={showPw?'text':'password'} value={pw} onChange={e=>setPw(e.target.value)} style={inputS} placeholder="At least 8 characters" />
                <button type="button" onClick={()=>setShowPw(!showPw)} style={eyeBtn}>{showPw ? <EyeOff size={15}/> : <Eye size={15}/>}</button>
              </div>
            </div>
            <div style={{marginBottom:14}}>
              <label style={labelS}>Confirm Password</label>
              <input data-testid="wizard-confirm-password" type={showPw?'text':'password'} value={pw2} onChange={e=>setPw2(e.target.value)} style={inputS} placeholder="Type it again" />
            </div>
            {error && <div data-testid="wizard-error" style={errorS}>{error}</div>}
            <button data-testid="wizard-next-1" onClick={submitStep1} disabled={saving} style={primaryBtn}>
              {saving ? <Loader2 size={14} style={{animation:'oraSpin 1s linear infinite'}}/> : 'Continue'} {!saving && <ChevronRight size={14}/>}
            </button>
          </div>
        )}

        {/* Step 2: Business Details */}
        {step === 2 && (
          <div data-testid="wizard-step-2">
            <h2 style={{fontFamily:"'Cinzel',serif",fontSize:22,fontWeight:700,color:'#FFF',letterSpacing:'0.03em',marginBottom:8}}>Confirm Your Business</h2>
            <p style={{fontSize:13,color:'#8A8070',lineHeight:1.5,marginBottom:20}}>A few details so ORA can personalize your experience.</p>
            <div style={{marginBottom:12}}>
              <label style={labelS}>Business Name *</label>
              <input data-testid="wizard-business-name" value={businessName} onChange={e=>setBusinessName(e.target.value)} style={inputS} placeholder="Your company" />
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:12}}>
              <div>
                <label style={labelS}>Industry</label>
                <input data-testid="wizard-industry" value={industry} onChange={e=>setIndustry(e.target.value)} style={inputS} placeholder="e.g., Auto Repair" />
              </div>
              <div>
                <label style={labelS}>City</label>
                <input data-testid="wizard-city" value={city} onChange={e=>setCity(e.target.value)} style={inputS} placeholder="e.g., Mississauga" />
              </div>
            </div>
            <div style={{marginBottom:14}}>
              <label style={labelS}>Phone (for WhatsApp/SMS)</label>
              <input data-testid="wizard-phone" value={phone} onChange={e=>setPhone(e.target.value)} style={inputS} placeholder="+1 416 555 1234" />
            </div>
            {error && <div style={errorS}>{error}</div>}
            <div style={{display:'flex',gap:10}}>
              {!mustSetPw && <button onClick={()=>setStep(1)} style={secondaryBtn}>Back</button>}
              <button data-testid="wizard-next-2" onClick={submitStep2} disabled={saving} style={{...primaryBtn,flex:1}}>
                {saving ? <Loader2 size={14} style={{animation:'oraSpin 1s linear infinite'}}/> : 'Continue'} {!saving && <ChevronRight size={14}/>}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Preferences */}
        {step === 3 && (
          <div data-testid="wizard-step-3">
            <h2 style={{fontFamily:"'Cinzel',serif",fontSize:22,fontWeight:700,color:'#FFF',letterSpacing:'0.03em',marginBottom:8}}>Tune Your AI</h2>
            <p style={{fontSize:13,color:'#8A8070',lineHeight:1.5,marginBottom:20}}>Help ORA write in the right voice and focus on what matters.</p>
            <div style={{marginBottom:14}}>
              <label style={labelS}>Communication Tone</label>
              <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
                {TONE_OPTIONS.map(t => (
                  <button key={t} data-testid={`wizard-tone-${t.toLowerCase()}`} onClick={()=>setTone(t)} style={chip(tone===t)}>{t}</button>
                ))}
              </div>
            </div>
            <div style={{marginBottom:14}}>
              <label style={labelS}>Services You Offer</label>
              <input data-testid="wizard-services" value={services} onChange={e=>setServices(e.target.value)} style={inputS} placeholder="e.g., Oil change, Brakes, Engine repair" />
              <div style={{fontSize:10,color:'#5A5468',marginTop:4}}>Separate with commas</div>
            </div>
            <div style={{marginBottom:14}}>
              <label style={labelS}>Goals (pick any)</label>
              <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
                {GOAL_OPTIONS.map(g => (
                  <button key={g} data-testid={`wizard-goal-${g.toLowerCase().replace(/\s+/g,'-')}`} onClick={()=>toggleGoal(g)} style={chip(goals.includes(g))}>{g}</button>
                ))}
              </div>
            </div>
            <div style={{display:'flex',gap:10}}>
              <button onClick={()=>setStep(2)} style={secondaryBtn}>Back</button>
              <button data-testid="wizard-next-3" onClick={submitStep3} disabled={saving} style={{...primaryBtn,flex:1}}>
                {saving ? <Loader2 size={14} style={{animation:'oraSpin 1s linear infinite'}}/> : 'Continue'} {!saving && <ChevronRight size={14}/>}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Done */}
        {step === 4 && (
          <div data-testid="wizard-step-4" style={{textAlign:'center'}}>
            <div style={{width:64,height:64,borderRadius:'50%',background:'rgba(212,175,55,0.12)',border:'1.5px solid #D4AF37',display:'flex',alignItems:'center',justifyContent:'center',margin:'0 auto 18px'}}>
              <Check size={28} color="#D4AF37"/>
            </div>
            <h2 style={{fontFamily:"'Cinzel',serif",fontSize:22,fontWeight:700,color:'#FFF',letterSpacing:'0.03em',marginBottom:8}}>You're All Set</h2>
            <p style={{fontSize:13,color:'#8A8070',lineHeight:1.6,marginBottom:18}}>
              Your BIN is <span style={{fontFamily:"'JetBrains Mono',monospace",color:'#D4AF37',fontWeight:700}}>{ctx.bin}</span>.
              <br/>Save it — you can log in with your BIN or email from any device.
            </p>

            {/* Power Trial banner */}
            <div data-testid="wizard-trial-banner" style={{background:'linear-gradient(135deg,rgba(34,197,94,0.08),rgba(212,175,55,0.05))',border:'1px solid rgba(34,197,94,0.25)',borderRadius:12,padding:14,marginBottom:16,textAlign:'left'}}>
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                <Zap size={14} color="#22c55e"/>
                <span style={{fontSize:10,letterSpacing:'0.18em',textTransform:'uppercase',color:'#22c55e',fontWeight:700}}>Power Trial · 7 Days FREE</span>
              </div>
              <div style={{fontSize:12,color:'#C9C9D1',lineHeight:1.6}}>
                Scanner · ORA 50 msgs · Friend Scanner (5/wk) · Pixel monitoring · 1 free Social Reel
              </div>
            </div>

            {/* What's Ready */}
            <div style={{background:'rgba(212,175,55,0.06)',border:'1px solid rgba(212,175,55,0.15)',borderRadius:10,padding:14,marginBottom:14,textAlign:'left'}}>
              <div style={{fontSize:10,letterSpacing:'0.2em',color:'#D4AF37',fontWeight:700,marginBottom:8,textTransform:'uppercase'}}>What's Ready</div>
              <ul style={{margin:0,paddingLeft:16,fontSize:12,color:'#A89E88',lineHeight:1.9}}>
                <li>Your sample website (edit anytime)</li>
                <li>Google Reviews dashboard</li>
                <li>ORA Chat personalized to your business</li>
                <li>Monthly reports sent via WhatsApp + Email</li>
              </ul>
            </div>

            {/* Next Steps — Hybrid Storefront CTAs */}
            <div data-testid="wizard-next-steps" style={{textAlign:'left',marginBottom:16}}>
              <div style={{fontSize:10,letterSpacing:'0.2em',color:'#D4AF37',fontWeight:700,marginBottom:10,textTransform:'uppercase'}}>
                Recommended Next Steps
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr',gap:8}}>
                <div data-testid="next-step-friend" style={nextStepCard}>
                  <Gift size={16} color="#D4AF37" style={{flexShrink:0}}/>
                  <div style={{flex:1}}>
                    <div style={{fontSize:12,fontWeight:700,color:'#FFF',marginBottom:2}}>Scan a Friend's Site</div>
                    <div style={{fontSize:10,color:'#8A8070'}}>Earn $20 credit per paid referral · 5 free scans in trial</div>
                  </div>
                </div>
                <div data-testid="next-step-pixel" style={nextStepCard}>
                  <Activity size={16} color="#D4AF37" style={{flexShrink:0}}/>
                  <div style={{flex:1}}>
                    <div style={{fontSize:12,fontWeight:700,color:'#FFF',marginBottom:2}}>Install the AUREM Pixel</div>
                    <div style={{fontSize:10,color:'#8A8070'}}>4 easy methods · Shopify, WordPress, Email-to-Dev, Manual</div>
                  </div>
                </div>
                <div data-testid="next-step-service" style={nextStepCard}>
                  <Zap size={16} color="#D4AF37" style={{flexShrink:0}}/>
                  <div style={{flex:1}}>
                    <div style={{fontSize:12,fontWeight:700,color:'#FFF',marginBottom:2}}>Unlock Add-on Services</div>
                    <div style={{fontSize:10,color:'#8A8070'}}>Pick 3+ → auto 15% bundle discount · From $19/mo</div>
                  </div>
                </div>
              </div>
            </div>

            <button data-testid="wizard-finish" onClick={submitFinish} disabled={saving} style={primaryBtn}>
              {saving ? <Loader2 size={14} style={{animation:'oraSpin 1s linear infinite'}}/> : 'Enter My Dashboard'}
            </button>
          </div>
        )}
      </div>
      <style>{`@keyframes oraSpin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

const labelS = { display:'block', fontSize:10, letterSpacing:'0.18em', textTransform:'uppercase', color:'#8A8070', fontWeight:600, marginBottom:6 };
const inputS = { width:'100%', padding:'12px 14px', background:'rgba(212,175,55,0.03)', border:'1px solid rgba(212,175,55,0.15)', borderRadius:9, color:'#E8E0D0', fontSize:14, fontFamily:"'Jost',sans-serif", outline:'none', boxSizing:'border-box' };
const eyeBtn = { position:'absolute', right:12, top:'50%', transform:'translateY(-50%)', background:'none', border:'none', color:'#8A8070', cursor:'pointer', padding:4 };
const errorS = { color:'#EF4444', fontSize:12, marginBottom:10, padding:'8px 12px', background:'rgba(239,68,68,0.08)', borderRadius:8 };
const primaryBtn = { width:'100%', display:'flex', alignItems:'center', justifyContent:'center', gap:8, padding:'12px 16px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:10, fontSize:13, fontWeight:700, letterSpacing:'0.1em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
const secondaryBtn = { padding:'12px 18px', background:'transparent', border:'1px solid rgba(212,175,55,0.2)', borderRadius:10, fontSize:12, color:'#8A8070', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
const chip = (active) => ({ padding:'8px 14px', borderRadius:20, border:`1px solid ${active?'#D4AF37':'rgba(212,175,55,0.15)'}`, background:active?'rgba(212,175,55,0.12)':'transparent', color:active?'#D4AF37':'#8A8070', fontSize:11.5, fontWeight:500, cursor:'pointer', fontFamily:"'Jost',sans-serif" });
const nextStepCard = { display:'flex', alignItems:'center', gap:10, padding:'10px 12px', background:'rgba(212,175,55,0.04)', border:'1px solid rgba(212,175,55,0.12)', borderRadius:10 };
