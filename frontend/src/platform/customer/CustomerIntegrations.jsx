/**
 * CustomerIntegrations — /my/integrations
 * ================================================
 * One-stop shop for the four iter-322 features:
 *   1. Shopify 1-click connect
 *   2. Widget install snippet (copy embed code)
 *   3. Pixel status (installed 🟢 / not installed 🔴)
 *   4. Booking widget preview
 */
import React, { useState, useEffect, useCallback } from 'react';
import { ShoppingBag, Code2, Activity, CalendarCheck, Copy, RefreshCw, ExternalLink } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

const card = {
  borderRadius: 18,
  padding: 22,
  background: 'rgba(15,18,28,0.55)',
  backdropFilter: 'blur(22px) saturate(150%)',
  WebkitBackdropFilter: 'blur(22px) saturate(150%)',
  border: '1px solid rgba(212,175,55,0.14)',
  boxShadow: '0 16px 44px rgba(0,0,0,0.35), inset 0 1px 0 rgba(212,175,55,0.08)',
};
const sectionH = { fontFamily:"'Cinzel',serif", fontSize:14, fontWeight:700, color:'#D4AF37', letterSpacing:'0.1em', textTransform:'uppercase', margin:'0 0 12px', display:'flex', alignItems:'center', gap:8 };
const subtle   = { fontSize: 12, color: '#8A8070' };
const tagBtn   = (color='#D4AF37') => ({
  display:'inline-flex', alignItems:'center', gap:6, padding:'8px 14px',
  borderRadius:9, background:`${color}15`, border:`1px solid ${color}55`,
  color, fontSize:11, fontWeight:700, letterSpacing:'0.08em',
  textTransform:'uppercase', cursor:'pointer', textDecoration:'none',
});

const title = { fontFamily:"'Cinzel',serif", fontSize:26, fontWeight:700, color:'#FFF', letterSpacing:'0.03em', marginBottom:4 };
const sub   = { fontSize:13, color:'#8A8070', marginBottom:20 };


export default function CustomerIntegrations({ ctx }) {
  return (
    <div data-testid="customer-integrations">
      <h1 style={title}>Integrations</h1>
      <p style={sub}>Connect AUREM to your store, website and tracking pixel, all in one place.</p>

      <div style={{display:'grid', gridTemplateColumns:'1fr', gap:16}}>
        <ShopifyCard />
        <WidgetInstallCard />
        <PixelStatusCard />
        <BookingPreviewCard ctx={ctx} />
      </div>
    </div>
  );
}


// ───────────────────────────── 1. Shopify ─────────────────────────────
function ShopifyCard() {
  const tok = getPlatformToken();
  const [status, setStatus] = useState(null);
  const [shop, setShop] = useState('');
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/shopify/auth/status`, { headers:{ Authorization:`Bearer ${tok}` }})
      .then(r => r.ok ? r.json() : null)
      .then(setStatus)
      .catch(()=>{})
      .finally(()=>setLoading(false));
  }, [tok]);
  useEffect(()=>{ refresh(); }, [refresh]);

  const connected = !!(status?.connected || status?.shop);

  return (
    <div style={card} data-testid="integrations-shopify">
      <h3 style={sectionH}><ShoppingBag size={14}/> Shopify</h3>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:12, flexWrap:'wrap'}}>
        <div style={{flex:1, minWidth:240}}>
          <div style={{fontSize:13, color:'#E8E0D0', fontWeight:600}}>
            {loading ? 'Checking…' : connected ? `Connected — ${status?.shop || status?.shop_domain}` : 'Not connected'}
          </div>
          <div style={{...subtle, marginTop:4}}>
            Sync products, orders and customers into ORA in one click.
          </div>
        </div>
        {!connected ? (
          <div style={{display:'flex', gap:8, alignItems:'center', flexWrap:'wrap'}}>
            <input
              data-testid="shopify-shop-input"
              value={shop}
              onChange={e=>setShop(e.target.value)}
              placeholder="yourstore.myshopify.com"
              style={{padding:'10px 12px', minWidth:220, background:'rgba(0,0,0,0.3)',
                      border:'1px solid rgba(212,175,55,0.15)', borderRadius:8,
                      color:'#E8E0D0', fontSize:12}}
            />
            <a data-testid="shopify-connect-btn"
               href={shop ? `${API}/api/shopify/auth?shop=${encodeURIComponent(shop)}&token=${encodeURIComponent(tok)}` : '#'}
               onClick={e => { if (!shop) { e.preventDefault(); alert('Enter your Shopify store domain first.'); } }}
               style={{...tagBtn('#95BF47'), color:'#0E0E0F', background:'#95BF47'}}>
              Connect <ExternalLink size={12}/>
            </a>
          </div>
        ) : (
          <a data-testid="shopify-manage-btn"
             href="/my/website" style={tagBtn('#95BF47')}>Manage</a>
        )}
      </div>
    </div>
  );
}


// ───────────────────────────── 2. Widget Install ─────────────────────────────
function WidgetInstallCard() {
  const tok = getPlatformToken();
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    fetch(`${API}/api/customer/api-key`, { headers:{ Authorization:`Bearer ${tok}` }})
      .then(r => r.ok ? r.json() : null)
      .then(setInfo)
      .catch(()=>{});
  }, [tok]);
  useEffect(load, [load]);

  const widgetSnippet = info?.key
    ? `<script src="${window.location.origin}/widget.js" data-api-key="${info.key}"></script>`
    : info?.snippet
    || `<script src="${window.location.origin}/widget.js" data-api-key="sk_aurem_live_xxxxx"></script>`;

  const copy = () => {
    navigator.clipboard.writeText(widgetSnippet);
    setCopied(true);
    setTimeout(()=>setCopied(false), 1800);
  };

  return (
    <div style={card} data-testid="integrations-widget">
      <h3 style={sectionH}><Code2 size={14}/> Website Widget</h3>
      <p style={{...subtle, marginBottom:10}}>
        Paste this snippet before <code style={{color:'#D4AF37'}}>&lt;/body&gt;</code> on your site. The widget
        auto-detects your theme, opens an ORA chat and lets visitors book appointments.
      </p>
      <div data-testid="widget-snippet"
        style={{padding:14, borderRadius:10, background:'rgba(0,0,0,0.4)',
                border:'1px solid rgba(255,255,255,0.06)',
                fontFamily:"'JetBrains Mono',monospace", fontSize:11.5,
                color:'#8A8070', lineHeight:1.5, wordBreak:'break-all'}}>
        {widgetSnippet}
      </div>
      <div style={{display:'flex', gap:8, marginTop:10}}>
        <button data-testid="widget-copy-btn" onClick={copy} style={tagBtn('#D4AF37')}>
          <Copy size={12}/> {copied ? 'Copied ✓' : 'Copy embed code'}
        </button>
        <a data-testid="widget-preview-btn"
           href="/widget.js" target="_blank" rel="noreferrer" style={tagBtn('#64C8FF')}>
          View source <ExternalLink size={12}/>
        </a>
      </div>
    </div>
  );
}


// ───────────────────────────── 3. Pixel Status ─────────────────────────────
function PixelStatusCard() {
  const tok = getPlatformToken();
  const [pixel, setPixel] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/customer/pixel/status`, { headers:{ Authorization:`Bearer ${tok}` }})
      .then(r => r.ok ? r.json() : { status:'not_installed' })
      .then(setPixel)
      .catch(()=>setPixel({status:'not_installed'}))
      .finally(()=>setLoading(false));
  }, [tok]);
  useEffect(()=>{ refresh(); }, [refresh]);

  const installed = pixel?.status === 'installed' || pixel?.connected || (pixel?.events_total > 0);
  const dot = installed ? '#4ADE80' : '#EF4444';

  return (
    <div style={card} data-testid="integrations-pixel">
      <h3 style={sectionH}><Activity size={14}/> Pixel Tracking</h3>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:12, flexWrap:'wrap'}}>
        <div style={{display:'flex', alignItems:'center', gap:10}}>
          <span style={{width:10, height:10, borderRadius:'50%', background:dot, boxShadow:`0 0 10px ${dot}88`}} />
          <div>
            <div style={{fontSize:13, color:'#E8E0D0', fontWeight:600}} data-testid="pixel-status-label">
              {loading ? 'Checking…' : installed ? '🟢 Installed & active' : '🔴 Not installed'}
            </div>
            <div style={{...subtle, marginTop:3}}>
              {installed
                ? `Events captured: ${pixel?.events_total || 0}. Last ping: ${pixel?.last_used ? new Date(pixel.last_used).toLocaleString() : '—'}`
                : 'Paste the pixel snippet from Settings → API Key & Pixel Install to track visitors.'}
            </div>
          </div>
        </div>
        <div style={{display:'flex', gap:8}}>
          <button data-testid="pixel-refresh-btn" onClick={refresh} style={tagBtn('#D4AF37')}>
            <RefreshCw size={12}/> Refresh
          </button>
          <a data-testid="pixel-install-link" href="/my/settings#pixel-install" style={tagBtn('#64C8FF')}>
            Install guide
          </a>
        </div>
      </div>
    </div>
  );
}


// ───────────────────────────── 4. Booking Preview ─────────────────────────────
function BookingPreviewCard({ ctx }) {
  return (
    <div style={card} data-testid="integrations-booking">
      <h3 style={sectionH}><CalendarCheck size={14}/> Booking Widget</h3>
      <p style={{...subtle, marginBottom:10}}>
        Visitors can book straight from your site through the ORA chat widget. Slots are stored in the same{' '}
        <code style={{color:'#D4AF37'}}>bookings</code> collection used by your customer dashboard.
      </p>
      <ol style={{...subtle, marginLeft:18, lineHeight:1.7}}>
        <li>Drop the website widget snippet (above) onto your site.</li>
        <li>Visitor clicks the floating ORA bubble → <strong style={{color:'#D4AF37'}}>📅 Book</strong>.</li>
        <li>They pick a service, date, slot → AUREM confirms instantly.</li>
        <li>Customise services in Settings → Booking.</li>
      </ol>
      <div style={{display:'flex', gap:8, marginTop:12}}>
        <a data-testid="booking-settings-link" href="/my/settings#booking" style={tagBtn('#D4AF37')}>
          Configure services
        </a>
        <a data-testid="booking-test-link" href="/" target="_blank" rel="noreferrer" style={tagBtn('#64C8FF')}>
          Test on aurem.live <ExternalLink size={12}/>
        </a>
      </div>
    </div>
  );
}
