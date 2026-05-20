/**
 * AUREM Video Marketing — Enterprise Tier Video Generation via Muapi
 * Product input → AURA prompt → Muapi video → caption + hashtags → schedule
 */
import React, { useState, useCallback, useEffect } from 'react';
import {
  Video, Play, Upload, Loader2, CheckCircle, Copy, Download,
  Lock, ArrowUpRight, Sparkles, Film, Instagram, Linkedin,
  Clock, Layers, ChevronDown
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const STYLES = [
  { id: 'product_demo', label: 'Product Demo', desc: 'Showcase features & quality' },
  { id: 'brand_story', label: 'Brand Story', desc: 'Narrative-driven brand video' },
  { id: 'social_ad', label: 'Social Ad', desc: 'Short-form conversion ad' },
  { id: 'tutorial', label: 'Tutorial', desc: 'How-to & educational' },
];

const PLATFORMS = [
  { id: 'instagram_reels', label: 'Instagram Reels', ar: '9:16', icon: Instagram },
  { id: 'tiktok', label: 'TikTok', ar: '9:16', icon: Film },
  { id: 'linkedin', label: 'LinkedIn', ar: '16:9', icon: Linkedin },
  { id: 'youtube_shorts', label: 'YouTube Shorts', ar: '9:16', icon: Play },
];

const UpgradePrompt = () => (
  <div className="rounded-2xl p-8 text-center space-y-4" data-testid="video-upgrade-prompt"
    style={{ background: 'linear-gradient(135deg, rgba(212,175,55,0.08), rgba(184,115,51,0.08))', border: '1px solid rgba(212,175,55,0.15)' }}>
    <Lock size={40} style={{ color: '#D4AF37', margin: '0 auto' }} />
    <h3 className="text-lg font-black" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>Video Generation, Growth & Enterprise</h3>
    <p className="text-sm max-w-md mx-auto" style={{ color: 'var(--aurem-text-secondary, #888)' }}>
      AI-powered video generation for product demos, brand stories, and social ads.
      Growth ($297/mo): 480p text-to-video, 10/month.
      Enterprise ($997/mo): Full HD + image-to-video + lip sync + extend.
    </p>
    <button className="px-6 py-2.5 rounded-xl text-xs font-bold inline-flex items-center gap-2" data-testid="upgrade-to-enterprise-btn"
      style={{ background: 'linear-gradient(135deg, #D4AF37, #B87333)', color: '#141216' }}>
      Upgrade Now <ArrowUpRight size={14} />
    </button>
  </div>
);

export default function VideoMarketing({ token }) {
  const [productName, setProductName] = useState('');
  const [productDesc, setProductDesc] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [style, setStyle] = useState('brand_story');
  const [platform, setPlatform] = useState('instagram_reels');
  const [duration, setDuration] = useState(5);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [videoCheck, setVideoCheck] = useState(null);
  const [copied, setCopied] = useState(false);
  const [usageData, setUsageData] = useState(null);

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const fetchUsage = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/content-engine/usage`, { headers });
      if (res.ok) {
        const d = await res.json();
        setVideoCheck(d.videos || {});
        setUsageData(d);
      }
    } catch (e) { console.error(e); }
  }, [token]);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/content-engine/video-history?limit=10`, { headers });
      if (res.ok) {
        const d = await res.json();
        setHistory(d.videos || []);
      }
    } catch (e) { console.error(e); }
  }, [token]);

  useEffect(() => { fetchUsage(); fetchHistory(); }, [fetchUsage, fetchHistory]);

  const handleGenerate = useCallback(async () => {
    if (!productName.trim()) return;
    setGenerating(true);
    setError('');
    setResult(null);
    const selectedPlatform = PLATFORMS.find(p => p.id === platform);
    try {
      const res = await fetch(`${API_URL}/api/content-engine/generate-video`, {
        method: 'POST', headers,
        body: JSON.stringify({
          product_name: productName,
          product_description: productDesc,
          image_url: imageUrl || null,
          style,
          platform,
          aspect_ratio: aspectRatio,
          duration,
        }),
      });
      if (res.status === 403) {
        setVideoCheck({ allowed: false, reason: 'upgrade_required' });
        setError('Enterprise plan required for video generation');
      } else if (res.ok) {
        const d = await res.json();
        setResult(d);
        fetchHistory();
        fetchUsage();
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || d.error || 'Video generation failed');
      }
    } catch (e) { setError(e.message); }
    setGenerating(false);
  }, [productName, productDesc, imageUrl, style, platform, token]);

  const copyCaption = () => {
    if (result?.caption) {
      navigator.clipboard.writeText(result.caption);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // If not Enterprise tier, show upgrade prompt
  if (videoCheck && !videoCheck.allowed && videoCheck.reason === 'upgrade_required') {
    return (
      <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="video-marketing">
        <div>
          <h2 className="text-lg font-black tracking-tight" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>Video Marketing</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-text-secondary, #888)' }}>AI-powered video generation for marketing campaigns</p>
        </div>
        <UpgradePrompt />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="video-marketing">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-black tracking-tight" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>Video Marketing</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-text-secondary, #888)' }}>
            AI-powered video generation, Product Demo / Brand Story / Social Ad / Tutorial
          </p>
        </div>
        {usageData?.videos && (
          <span className="text-[10px] font-bold px-3 py-1 rounded-full" data-testid="video-usage-badge"
            style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }}>
            {usageData.videos.used || 0} videos generated
          </span>
        )}
      </div>

      {/* Generator Card */}
      <div className="rounded-2xl p-6 space-y-5" data-testid="video-generator"
        style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}>

        {/* Product Name */}
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: '#888' }}>Product Name *</label>
          <input type="text" value={productName} onChange={e => setProductName(e.target.value)}
            placeholder="e.g., AURA Vitamin C Serum" data-testid="product-name-input"
            className="w-full px-4 py-2.5 rounded-xl text-sm outline-none transition-all focus:ring-1"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--aurem-text, #ccc)', border: '1px solid rgba(255,255,255,0.08)', '--tw-ring-color': '#D4AF37' }} />
        </div>

        {/* Product Description */}
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: '#888' }}>Product Description (optional)</label>
          <textarea value={productDesc} onChange={e => setProductDesc(e.target.value)} rows={2}
            placeholder="Brief description of the product features and target audience..." data-testid="product-desc-input"
            className="w-full px-4 py-2.5 rounded-xl text-sm outline-none resize-none transition-all focus:ring-1"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--aurem-text, #ccc)', border: '1px solid rgba(255,255,255,0.08)', '--tw-ring-color': '#D4AF37' }} />
        </div>

        {/* Image URL (optional) */}
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: '#888' }}>
            Product Image URL (optional, enables Image-to-Video)
          </label>
          <input type="url" value={imageUrl} onChange={e => setImageUrl(e.target.value)}
            placeholder="https://example.com/product.jpg" data-testid="image-url-input"
            className="w-full px-4 py-2.5 rounded-xl text-sm outline-none transition-all focus:ring-1"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--aurem-text, #ccc)', border: '1px solid rgba(255,255,255,0.08)', '--tw-ring-color': '#D4AF37' }} />
          {imageUrl && (
            <p className="text-[9px] mt-1 font-bold" style={{ color: '#D4AF37' }}>Multi-Reference mode, product image will guide video style</p>
          )}
        </div>

        {/* Style Selector */}
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider block mb-2" style={{ color: '#888' }}>Style</label>
          <div className="grid grid-cols-4 gap-2" data-testid="style-selector">
            {STYLES.map(s => (
              <button key={s.id} onClick={() => setStyle(s.id)} data-testid={`style-${s.id}`}
                className="rounded-xl px-3 py-2.5 text-left transition-all"
                style={{
                  background: style === s.id ? 'rgba(212,175,55,0.12)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${style === s.id ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.06)'}`,
                }}>
                <p className="text-[11px] font-bold" style={{ color: style === s.id ? '#D4AF37' : 'var(--aurem-text, #ccc)' }}>{s.label}</p>
                <p className="text-[9px] mt-0.5" style={{ color: '#666' }}>{s.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Platform Selector */}
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider block mb-2" style={{ color: '#888' }}>Platform</label>
          <div className="grid grid-cols-4 gap-2" data-testid="platform-selector">
            {PLATFORMS.map(p => {
              const Icon = p.icon;
              return (
                <button key={p.id} onClick={() => setPlatform(p.id)} data-testid={`platform-${p.id}`}
                  className="rounded-xl px-3 py-2.5 flex items-center gap-2 transition-all"
                  style={{
                    background: platform === p.id ? 'rgba(212,175,55,0.12)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${platform === p.id ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.06)'}`,
                  }}>
                  <Icon size={14} style={{ color: platform === p.id ? '#D4AF37' : '#888' }} />
                  <div>
                    <p className="text-[11px] font-bold" style={{ color: platform === p.id ? '#D4AF37' : 'var(--aurem-text, #ccc)' }}>{p.label}</p>
                    <p className="text-[9px]" style={{ color: '#666' }}>{p.ar}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Duration + Aspect Ratio */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider block mb-2" style={{ color: '#888' }}>Duration</label>
            <div className="flex gap-2" data-testid="duration-selector">
              {[5, 10, 15].map(d => (
                <button key={d} onClick={() => setDuration(d)} data-testid={`duration-${d}`}
                  className="flex-1 rounded-xl px-3 py-2 text-center transition-all"
                  style={{
                    background: duration === d ? 'rgba(212,175,55,0.12)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${duration === d ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.06)'}`,
                    color: duration === d ? '#D4AF37' : 'var(--aurem-text, #ccc)',
                  }}>
                  <p className="text-[11px] font-bold">{d}s</p>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider block mb-2" style={{ color: '#888' }}>Aspect Ratio</label>
            <div className="flex gap-2" data-testid="aspect-ratio-selector">
              {[{id: '16:9', label: '16:9 Landscape'}, {id: '9:16', label: '9:16 Portrait'}, {id: '1:1', label: '1:1 Square'}].map(ar => (
                <button key={ar.id} onClick={() => setAspectRatio(ar.id)} data-testid={`ar-${ar.id.replace(':','-')}`}
                  className="flex-1 rounded-xl px-2 py-2 text-center transition-all"
                  style={{
                    background: aspectRatio === ar.id ? 'rgba(212,175,55,0.12)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${aspectRatio === ar.id ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.06)'}`,
                    color: aspectRatio === ar.id ? '#D4AF37' : 'var(--aurem-text, #ccc)',
                  }}>
                  <p className="text-[10px] font-bold">{ar.label}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Generate Button */}
        <button onClick={handleGenerate} disabled={generating || !productName.trim()} data-testid="generate-video-btn"
          className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold transition-all hover:opacity-90 disabled:opacity-40"
          style={{ background: generating ? 'rgba(128,128,128,0.2)' : 'linear-gradient(135deg, #D4AF37, #B87333)', color: generating ? '#888' : '#141216' }}>
          {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          {generating ? 'Generating Video (1-3 min)...' : 'Generate Video'}
        </button>

        {error && (
          <p className="text-xs text-center font-bold" data-testid="video-error" style={{ color: '#ef4444' }}>{error}</p>
        )}
      </div>

      {/* Result Card */}
      {result && result.generated && (
        <div className="rounded-2xl p-6 space-y-4" data-testid="video-result"
          style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid rgba(34,197,94,0.15)' }}>
          <div className="flex items-center gap-2">
            <CheckCircle size={16} style={{ color: '#22c55e' }} />
            <h3 className="text-xs font-black tracking-wider" style={{ color: '#22c55e' }}>VIDEO GENERATED</h3>
            <span className="text-[9px] px-2 py-0.5 rounded-full font-bold"
              style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>
              {result.mode === 'i2v' ? 'Image-to-Video' : 'Text-to-Video'}
            </span>
          </div>

          {/* Video Preview */}
          {result.video_url && (
            <div className="rounded-xl overflow-hidden" style={{ background: '#000' }}>
              <video src={result.video_url} controls className="w-full max-h-[400px]" data-testid="video-preview" />
            </div>
          )}

          {/* Video Prompt */}
          <div className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.02)' }}>
            <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#888' }}>Video Prompt</p>
            <p className="text-xs" style={{ color: 'var(--aurem-text, #ccc)' }}>{result.video_prompt}</p>
          </div>

          {/* Caption + Hashtags */}
          {result.caption && (
            <div className="rounded-xl p-3 flex items-start justify-between" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <div className="flex-1">
                <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#888' }}>Caption + Hashtags</p>
                <p className="text-xs whitespace-pre-wrap" style={{ color: 'var(--aurem-text, #ccc)' }}>{result.caption}</p>
              </div>
              <button onClick={copyCaption} data-testid="copy-caption-btn"
                className="ml-3 p-2 rounded-lg hover:opacity-80"
                style={{ background: 'rgba(212,175,55,0.1)' }}>
                {copied ? <CheckCircle size={14} style={{ color: '#22c55e' }} /> : <Copy size={14} style={{ color: '#D4AF37' }} />}
              </button>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            {result.video_url && (
              <a href={result.video_url} target="_blank" rel="noreferrer" data-testid="download-video-btn"
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[10px] font-bold hover:opacity-80"
                style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.2)' }}>
                <Download size={12} /> Download Video
              </a>
            )}
          </div>
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="rounded-2xl p-5" data-testid="video-history"
          style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}>
          <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>VIDEO HISTORY</h3>
          <div className="space-y-2">
            {history.map((vid, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 px-3 rounded-xl"
                style={{ background: 'rgba(255,255,255,0.015)' }}>
                <div className="flex items-center gap-3">
                  <Video size={14} style={{ color: '#D4AF37' }} />
                  <div>
                    <p className="text-xs font-bold" style={{ color: 'var(--aurem-text, #ccc)' }}>{vid.product_name}</p>
                    <p className="text-[9px]" style={{ color: '#888' }}>
                      {vid.style?.replace(/_/g, ' ')} / {vid.platform?.replace(/_/g, ' ')} / {vid.mode === 'i2v' ? 'I2V' : 'T2V'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[9px]" style={{ color: '#666' }}>
                    {vid.created_at ? new Date(vid.created_at).toLocaleDateString() : ''}
                  </span>
                  {vid.video_url && (
                    <a href={vid.video_url} target="_blank" rel="noreferrer"
                      className="text-[9px] font-bold px-2 py-0.5 rounded-lg hover:opacity-80"
                      style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>
                      View
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
