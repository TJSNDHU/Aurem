/**
 * CustomerEditPortal — /edit?token=...&site=...
 * Mobile-first DIY editor for AWB-built customer sites.
 * Magic-link verify → 4 h session → save changes → AWB re-render → R2 push.
 */
import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, Save, Eye, Check, AlertTriangle, Image as ImageIcon, Mail } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const GOLD = '#C9A227';

const GROUPS = [
  { key: 'business', label: 'Business', fields: [
    { name: 'business_name', label: 'Business Name', type: 'text' },
    { name: 'tagline', label: 'Tagline / Hero Headline', type: 'text' },
    { name: 'about', label: 'About Section', type: 'textarea', rows: 5 },
  ]},
  { key: 'contact', label: 'Contact', fields: [
    { name: 'phone', label: 'Phone', type: 'tel' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'address', label: 'Address', type: 'text' },
    { name: 'hours', label: 'Hours of Operation', type: 'textarea', rows: 3 },
    { name: 'google_maps_address', label: 'Google Maps Address', type: 'text' },
  ]},
  { key: 'colors', label: 'Colors', fields: [
    { name: 'colors.primary',    label: 'Primary Color',    type: 'color' },
    { name: 'colors.background', label: 'Background Color', type: 'color' },
  ]},
  { key: 'social', label: 'Social Links', fields: [
    { name: 'social.instagram', label: 'Instagram URL', type: 'url' },
    { name: 'social.facebook',  label: 'Facebook URL',  type: 'url' },
    { name: 'social.tiktok',    label: 'TikTok URL',    type: 'url' },
    { name: 'social.youtube',   label: 'YouTube URL',   type: 'url' },
    { name: 'social.linkedin',  label: 'LinkedIn URL',  type: 'url' },
    { name: 'social.x',         label: 'X / Twitter URL', type: 'url' },
  ]},
];

const getNested = (obj, path) => {
  const parts = path.split('.');
  let cur = obj;
  for (const p of parts) { if (!cur) return ''; cur = cur[p]; }
  return cur || '';
};
const setNested = (obj, path, value) => {
  const parts = path.split('.');
  const out = { ...obj };
  let cur = out;
  for (let i = 0; i < parts.length - 1; i++) {
    cur[parts[i]] = { ...(cur[parts[i]] || {}) };
    cur = cur[parts[i]];
  }
  cur[parts[parts.length - 1]] = value;
  return out;
};

export default function CustomerEditPortal() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const siteParam = params.get('site') || '';

  const [phase, setPhase] = useState(token ? 'verifying' : 'request');
  const [session, setSession] = useState(null);  // {session_token, site, expires_at}
  const [content, setContent] = useState({});
  const [services, setServices] = useState([]);
  const [activeGroup, setActiveGroup] = useState('business');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [error, setError] = useState('');
  const [requestEmail, setRequestEmail] = useState('');
  const [requestSlug, setRequestSlug] = useState(siteParam);
  const [requestSent, setRequestSent] = useState(false);
  const fileRef = useRef(null);
  const [uploadingKind, setUploadingKind] = useState(null);
  const [npsScore, setNpsScore] = useState(null);
  const [npsSubmitting, setNpsSubmitting] = useState(false);
  const [npsSubmitted, setNpsSubmitted] = useState(false);
  const [npsVisible, setNpsVisible] = useState(false);

  // Verify token (StrictMode-safe via sessionStorage cache)
  useEffect(() => {
    if (!token) return;
    const cacheKey = `aurem_edit_session_${token}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      try {
        const d = JSON.parse(cached);
        setSession(d);
        setContent(d.site?.custom_content || {});
        setServices(d.site?.custom_content?.services || []);
        setPhase('editing');
        return;
      } catch { /* fallthrough to network */ }
    }
    (async () => {
      try {
        const r = await fetch(`${API}/api/edit/verify?token=${encodeURIComponent(token)}`);
        if (!r.ok) throw new Error((await r.json()).detail || 'invalid token');
        const d = await r.json();
        sessionStorage.setItem(cacheKey, JSON.stringify(d));
        setSession(d);
        setContent(d.site?.custom_content || {});
        setServices(d.site?.custom_content?.services || []);
        setPhase('editing');
      } catch (e) {
        setError(e.message);
        setPhase('expired');
      }
    })();
  }, [token]);

  const setField = (path, value) => setContent(c => setNested(c, path, value));

  const save = async () => {
    if (!session) return;
    setSaving(true); setError(''); setSaveMsg('');
    try {
      const changes = { ...content, services };
      const r = await fetch(`${API}/api/edit/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: session.session_token, changes }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error(d.detail || d.error || 'save failed');
      setSaveMsg(`Saved ${d.fields_updated.length} field(s). Site live in ~30s.`);
      setTimeout(() => setSaveMsg(''), 6000);
      // Show NPS once per session after first successful save
      if (!localStorage.getItem(`aurem_nps_shown_${session?.site_id}`)) {
        setNpsVisible(true);
        localStorage.setItem(`aurem_nps_shown_${session?.site_id}`, '1');
      }
    } catch (e) {
      setError(e.message);
    }
    setSaving(false);
  };

  const submitNps = async (score) => {
    if (!session || npsSubmitting) return;
    setNpsScore(score); setNpsSubmitting(true);
    try {
      const r = await fetch(`${API}/api/edit/nps`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: session.session_token, score,
                                source: 'edit_portal_save' }),
      });
      const d = await r.json();
      if (r.ok && d.ok) {
        setNpsSubmitted(true);
        setTimeout(() => setNpsVisible(false), 2500);
      }
    } catch { /* silent */ }
    setNpsSubmitting(false);
  };

  const uploadImage = async (kind, file) => {
    if (!file || !session) return;
    if (file.size > 5 * 1024 * 1024) { setError('Image must be < 5 MB'); return; }
    setUploadingKind(kind); setError('');
    try {
      const fd = new FormData();
      fd.append('token', session.session_token);
      fd.append('kind', kind);
      fd.append('file', file);
      const r = await fetch(`${API}/api/edit/upload-image`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error(d.detail || 'upload failed');
      setSaveMsg(`${kind} image uploaded`);
      setTimeout(() => setSaveMsg(''), 4000);
    } catch (e) { setError(e.message); }
    setUploadingKind(null);
  };

  const requestAccess = async () => {
    setError(''); setRequestSent(false);
    try {
      const r = await fetch(`${API}/api/edit/request-access`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_email: requestEmail, site_slug: requestSlug }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'request failed');
      setRequestSent(true);
    } catch (e) { setError(e.message); }
  };

  const renderField = (f) => {
    const val = getNested(content, f.name);
    if (f.type === 'textarea') {
      return <textarea data-testid={`edit-field-${f.name}`}
        value={val} onChange={e => setField(f.name, e.target.value)}
        rows={f.rows || 3} style={inputStyle} />;
    }
    if (f.type === 'color') {
      return (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="color" data-testid={`edit-field-${f.name}`}
            value={val || '#C9A227'} onChange={e => setField(f.name, e.target.value)}
            style={{ width: 56, height: 40, border: 'none', borderRadius: 6,
                     background: 'transparent', cursor: 'pointer' }} />
          <input type="text" value={val || ''}
            onChange={e => setField(f.name, e.target.value)}
            placeholder="#hex" style={{ ...inputStyle, flex: 1 }} />
        </div>
      );
    }
    return <input type={f.type || 'text'} data-testid={`edit-field-${f.name}`}
      value={val} onChange={e => setField(f.name, e.target.value)}
      style={inputStyle} />;
  };

  // Request phase (no token)
  if (phase === 'request') {
    return (
      <div style={pageStyle}>
        <div style={{ maxWidth: 480, margin: '60px auto', padding: 30,
                      background: '#13110D', borderRadius: 12,
                      border: '1px solid rgba(201,162,39,0.3)' }}>
          <Mail style={{ width: 32, height: 32, color: GOLD, marginBottom: 12 }} />
          <h1 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 28,
                       margin: '0 0 6px' }}>Edit Your AUREM Site</h1>
          <p style={{ color: '#8A8279', fontSize: 13, marginBottom: 22 }}>
            Enter your business email and site slug. We'll send a magic link that
            unlocks the editor for 24 h.
          </p>
          <label style={labelStyle}>BUSINESS EMAIL</label>
          <input data-testid="edit-request-email" type="email"
            value={requestEmail} onChange={e => setRequestEmail(e.target.value)}
            placeholder="you@yourbusiness.com" style={inputStyle} />
          <label style={{ ...labelStyle, marginTop: 14 }}>SITE SLUG OR ID</label>
          <input data-testid="edit-request-slug" type="text"
            value={requestSlug} onChange={e => setRequestSlug(e.target.value)}
            placeholder="spadina-auto" style={inputStyle} />
          <button data-testid="edit-request-submit" onClick={requestAccess}
            disabled={!requestEmail || !requestSlug}
            style={{ ...primaryBtn, width: '100%', marginTop: 20,
                     opacity: (!requestEmail || !requestSlug) ? 0.5 : 1 }}>
            Send Magic Link
          </button>
          {requestSent && (
            <div data-testid="edit-request-sent"
              style={{ marginTop: 14, padding: 12, borderRadius: 6,
                       background: 'rgba(34,197,94,0.1)',
                       border: '1px solid rgba(34,197,94,0.4)',
                       color: '#22C55E', fontSize: 13 }}>
              <Check style={{ width: 14, height: 14, display: 'inline',
                              verticalAlign: 'middle', marginRight: 6 }} />
              Check your email for the edit link.
            </div>
          )}
          {error && <ErrorBox text={error} />}
        </div>
      </div>
    );
  }

  if (phase === 'verifying') {
    return <div style={{ ...pageStyle, display: 'grid', placeItems: 'center' }}>
      <Loader2 className="animate-spin" style={{ width: 40, height: 40, color: GOLD }} />
    </div>;
  }

  if (phase === 'expired') {
    return (
      <div style={pageStyle}>
        <div style={{ maxWidth: 480, margin: '80px auto', padding: 30,
                      textAlign: 'center' }}>
          <AlertTriangle style={{ width: 48, height: 48, color: '#EF4444',
                                  margin: '0 auto 18px' }} />
          <h1 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 26 }}>
            Link Expired
          </h1>
          <p style={{ color: '#8A8279', marginBottom: 22 }}>
            {error || 'This edit link is no longer valid.'} Request a fresh one.
          </p>
          <button onClick={() => { window.location.search = ''; }}
            style={primaryBtn} data-testid="edit-request-again">
            Request New Link
          </button>
        </div>
      </div>
    );
  }

  // Editing phase
  const site = session?.site || {};
  // iter 322p — robust preview URL resolver (was double-prefixing absolute
  // preview_url's into `https://aurem.livehttps://aurem.live/...`).
  // Order: explicit live_url (absolute) → public_url (relative, prefix API)
  // → preview_url (could be absolute or relative — only prefix if relative).
  const previewUrl = (() => {
    if (site.live_url) return site.live_url;
    if (site.public_url) return `${API}${site.public_url}`;
    const p = site.preview_url || '';
    if (!p) return null;
    return /^https?:\/\//i.test(p) ? p : `${API}${p}`;
  })();
  return (
    <div style={pageStyle} data-testid="edit-portal-page">
      <header style={headerStyle}>
        <div>
          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 22 }}>
            {site.business_name || 'Your Site'}
          </div>
          <div style={{ fontSize: 10, color: '#8A8279', letterSpacing: 1.4,
                        fontFamily: "'DM Mono',monospace" }}>
            EDIT PORTAL · session ends {(session?.expires_at || '').slice(11, 16)} UTC
          </div>
        </div>
        {previewUrl && (
          <a href={previewUrl} target="_blank" rel="noreferrer"
            data-testid="edit-preview-link"
            style={{ ...secondaryBtn, textDecoration: 'none',
                     display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Eye style={{ width: 13, height: 13 }} /> PREVIEW
          </a>
        )}
      </header>

      <div style={{ maxWidth: 760, margin: '0 auto', padding: '20px 16px 100px' }}>
        {/* Group switcher */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap',
                      marginBottom: 18, overflowX: 'auto' }}>
          {GROUPS.map(g => (
            <button key={g.key} data-testid={`edit-group-${g.key}`}
              onClick={() => setActiveGroup(g.key)}
              style={{ ...chipStyle,
                background: activeGroup === g.key ? GOLD : 'transparent',
                color: activeGroup === g.key ? '#0A0A0A' : '#C9A227',
              }}>{g.label}</button>
          ))}
          <button data-testid="edit-group-services"
            onClick={() => setActiveGroup('services')}
            style={{ ...chipStyle,
              background: activeGroup === 'services' ? GOLD : 'transparent',
              color: activeGroup === 'services' ? '#0A0A0A' : '#C9A227' }}>
            Services
          </button>
          <button data-testid="edit-group-images"
            onClick={() => setActiveGroup('images')}
            style={{ ...chipStyle,
              background: activeGroup === 'images' ? GOLD : 'transparent',
              color: activeGroup === 'images' ? '#0A0A0A' : '#C9A227' }}>
            Images
          </button>
        </div>

        {/* Active group fields */}
        {GROUPS.filter(g => g.key === activeGroup).map(g => (
          <div key={g.key}>
            {g.fields.map(f => (
              <div key={f.name} style={{ marginBottom: 14 }}>
                <label style={labelStyle}>{f.label.toUpperCase()}</label>
                {renderField(f)}
              </div>
            ))}
          </div>
        ))}

        {activeGroup === 'services' && (
          <div data-testid="edit-services-list">
            {services.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <input value={typeof s === 'string' ? s : s.name || ''}
                  onChange={e => { const ns = [...services];
                    ns[i] = e.target.value; setServices(ns); }}
                  style={{ ...inputStyle, flex: 1 }}
                  data-testid={`edit-service-${i}`} />
                <button onClick={() => setServices(services.filter((_, j) => j !== i))}
                  style={{ ...secondaryBtn, color: '#EF4444',
                           border: '1px solid rgba(239,68,68,0.3)' }}>×</button>
              </div>
            ))}
            <button data-testid="edit-service-add"
              onClick={() => setServices([...services, ''])}
              style={{ ...secondaryBtn, marginTop: 8 }}>+ Add Service</button>
          </div>
        )}

        {activeGroup === 'images' && (
          <div>
            {[
              { kind: 'hero', label: 'Hero Image' },
              { kind: 'logo', label: 'Logo' },
            ].map(({ kind, label }) => (
              <div key={kind} style={{ marginBottom: 18 }}>
                <label style={labelStyle}>{label.toUpperCase()}</label>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="file" accept="image/*"
                    data-testid={`edit-upload-${kind}`}
                    onChange={e => uploadImage(kind, e.target.files?.[0])}
                    style={{ flex: 1, padding: 8, fontSize: 12 }} />
                  {uploadingKind === kind &&
                    <Loader2 className="animate-spin"
                      style={{ width: 16, height: 16, color: GOLD }} />}
                  {(content.images || {})[`${kind}_url`] &&
                    <ImageIcon style={{ width: 18, height: 18, color: '#22C55E' }} />}
                </div>
                <div style={{ fontSize: 10, color: '#7A7468', marginTop: 4 }}>
                  Max 5 MB · auto-compressed
                </div>
              </div>
            ))}
          </div>
        )}

        {error && <ErrorBox text={error} />}
      </div>

      {/* 2-tap NPS — appears once after first successful save */}
      {npsVisible && (
        <div data-testid="nps-widget" style={npsCardStyle}>
          {!npsSubmitted ? (
            <>
              <div style={{ fontSize: 13, color: '#F2EDE4',
                            marginBottom: 10, fontWeight: 600 }}>
                How did we do?
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
                {[
                  { s: 1, e: '😞' },
                  { s: 2, e: '😐' },
                  { s: 3, e: '🙂' },
                  { s: 4, e: '😊' },
                  { s: 5, e: '🤩' },
                ].map(({ s, e }) => (
                  <button key={s} data-testid={`nps-score-${s}`}
                    onClick={() => submitNps(s)}
                    disabled={npsSubmitting}
                    style={{
                      flex: 1, padding: '12px 6px', fontSize: 22,
                      background: npsScore === s
                        ? 'rgba(201,162,39,0.25)' : 'rgba(255,255,255,0.04)',
                      border: `1px solid ${npsScore === s
                        ? GOLD : 'rgba(201,162,39,0.25)'}`,
                      borderRadius: 6, cursor: 'pointer',
                      transition: 'all 120ms',
                    }}>
                    {e}
                    <div style={{ fontSize: 10, color: '#8A8279',
                                  marginTop: 4, fontFamily: "'DM Mono',monospace" }}>{s}</div>
                  </button>
                ))}
              </div>
              <button data-testid="nps-skip"
                onClick={() => setNpsVisible(false)}
                style={{ marginTop: 10, background: 'transparent',
                         border: 'none', color: '#7A7468', fontSize: 11,
                         cursor: 'pointer', letterSpacing: 1.2,
                         fontFamily: "'DM Mono',monospace" }}>
                SKIP
              </button>
            </>
          ) : (
            <div data-testid="nps-thanks" style={{ fontSize: 13, color: '#22C55E' }}>
              <Check style={{ width: 14, height: 14, display: 'inline',
                              verticalAlign: 'middle', marginRight: 6 }} />
              Thanks for the feedback!
            </div>
          )}
        </div>
      )}

      {/* Sticky save bar */}
      <div style={saveBarStyle}>
        <div style={{ flex: 1, fontSize: 12, color: saveMsg ? '#22C55E' : '#8A8279' }}>
          {saveMsg || (site.last_edited
            ? `Last saved ${new Date(site.last_edited).toLocaleTimeString()}`
            : 'No changes saved yet')}
        </div>
        <button data-testid="edit-save-btn" onClick={save} disabled={saving}
          style={{ ...primaryBtn, display: 'flex', alignItems: 'center', gap: 6,
                   opacity: saving ? 0.5 : 1 }}>
          {saving ? <Loader2 className="animate-spin"
                       style={{ width: 14, height: 14 }} />
                  : <Save style={{ width: 14, height: 14 }} />}
          {saving ? 'SAVING…' : 'SAVE CHANGES'}
        </button>
      </div>
    </div>
  );
}

// ─── Styles ────────────────────────────────────────────────────────────────
const pageStyle = {
  minHeight: '100vh', background: '#0A0A0B', color: '#F2EDE4',
  fontFamily: "'DM Sans',system-ui,sans-serif",
};
const headerStyle = {
  position: 'sticky', top: 0, padding: '14px 20px', zIndex: 5,
  background: '#0A0A0B', borderBottom: '1px solid rgba(201,162,39,0.18)',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
};
const inputStyle = {
  width: '100%', padding: '10px 12px', fontSize: 13,
  background: 'rgba(255,255,255,0.04)', color: '#F2EDE4',
  border: '1px solid rgba(201,162,39,0.25)', borderRadius: 6,
  outline: 'none', fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box',
};
const labelStyle = {
  display: 'block', fontSize: 10, color: '#8A8279', letterSpacing: 1.2,
  fontFamily: "'DM Mono',monospace", marginBottom: 6,
};
const primaryBtn = {
  padding: '10px 22px', borderRadius: 6, fontSize: 11, fontWeight: 800,
  letterSpacing: 1.5, background: GOLD, color: '#0A0A0A',
  border: 'none', cursor: 'pointer', fontFamily: 'inherit',
};
const secondaryBtn = {
  padding: '6px 12px', borderRadius: 4, fontSize: 10, fontWeight: 600,
  letterSpacing: 1.4, background: 'transparent', color: '#C9A227',
  border: '1px solid rgba(201,162,39,0.3)', cursor: 'pointer', fontFamily: 'inherit',
};
const chipStyle = {
  padding: '6px 14px', borderRadius: 16, fontSize: 11, fontWeight: 600,
  border: `1px solid ${GOLD}40`, cursor: 'pointer', fontFamily: 'inherit',
  whiteSpace: 'nowrap',
};
const saveBarStyle = {
  position: 'fixed', bottom: 0, left: 0, right: 0, padding: '12px 20px',
  background: '#13110D', borderTop: '1px solid rgba(201,162,39,0.3)',
  display: 'flex', alignItems: 'center', gap: 12, zIndex: 10,
};
const npsCardStyle = {
  margin: '20px auto 80px', maxWidth: 480, padding: 18,
  background: 'linear-gradient(180deg,#13110D,#0F0D09)',
  borderRadius: 10, border: '1px solid rgba(201,162,39,0.3)',
  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
};

const ErrorBox = ({ text }) => (
  <div data-testid="edit-error"
    style={{ marginTop: 12, padding: 10, borderRadius: 6,
             background: 'rgba(239,68,68,0.08)',
             border: '1px solid rgba(239,68,68,0.4)', color: '#EF4444',
             fontSize: 12 }}>
    <AlertTriangle style={{ width: 13, height: 13, display: 'inline',
                            verticalAlign: 'middle', marginRight: 6 }} />
    {text}
  </div>
);
