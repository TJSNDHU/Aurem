/**
 * ZImageStudio.jsx - Professional AI Image Generation Studio
 * Z-Image-Turbo (6B params) - #1 Open Source Model
 * 
 * Features:
 * - DSLR-quality output (up to 2048x2048)
 * - Nano-pixel accuracy controls
 * - Quality presets (Draft → Maximum)
 * - Batch generation
 * - Professional negative prompts
 */

import React, { useState, useRef, useEffect } from 'react';

const C = {
  void: "#060608",
  void2: "#0a0a0d",
  gold: "#c9a86e",
  goldBright: "#e8d5a3",
  goldDim: "rgba(201,168,110,0.4)",
  surface: "#0f0f11",
  surface2: "#151518",
  surface3: "#1a1a1e",
  text: "#f5f0e8",
  textDim: "rgba(245,240,232,0.5)",
  border: "rgba(201,168,110,0.15)",
  borderBright: "rgba(201,168,110,0.3)",
  green: "#22c55e",
  red: "#ef4444",
  blue: "#3b82f6",
  purple: "#a855f7"
};

// Quality Presets matching backend
const QUALITY_PRESETS = {
  draft: { steps: 8, cfg: 5.5, label: "Draft", desc: "Fast preview (~5s)", color: C.textDim },
  standard: { steps: 12, cfg: 6.5, label: "Standard", desc: "Balanced (~10s)", color: C.blue },
  high: { steps: 18, cfg: 7.0, label: "High", desc: "Detailed (~20s)", color: C.green },
  ultra: { steps: 22, cfg: 7.5, label: "Ultra", desc: "DSLR Quality (~30s)", color: C.gold },
  maximum: { steps: 30, cfg: 8.0, label: "Maximum", desc: "Nano-Pixel (~45s)", color: C.purple }
};

// Resolution presets for different use cases
const RESOLUTION_PRESETS = [
  { label: "1:1 Square", width: 1024, height: 1024, icon: "⬜", use: "Social, Profile" },
  { label: "1:1 HD", width: 1536, height: 1536, icon: "🔳", use: "Print, Large" },
  { label: "1:1 Ultra", width: 2048, height: 2048, icon: "⬛", use: "Maximum Detail" },
  { label: "4:3 Standard", width: 1024, height: 768, icon: "🖼", use: "Photo, Display" },
  { label: "4:3 HD", width: 1536, height: 1152, icon: "📷", use: "High-Res Photo" },
  { label: "16:9 Wide", width: 1024, height: 576, icon: "🎬", use: "Banner, Video" },
  { label: "16:9 HD", width: 1920, height: 1080, icon: "📺", use: "Full HD Banner" },
  { label: "9:16 Portrait", width: 576, height: 1024, icon: "📱", use: "Mobile, Stories" },
  { label: "9:16 HD", width: 1080, height: 1920, icon: "📲", use: "HD Stories" },
  { label: "3:4 Portrait", width: 768, height: 1024, icon: "🎨", use: "Portrait Photo" },
  { label: "2:3 Poster", width: 1024, height: 1536, icon: "🖼️", use: "Poster, Print" }
];

// Professional prompt templates
const PROMPT_TEMPLATES = [
  { 
    category: "Product Photography",
    prompts: [
      { label: "Luxury Product", prompt: "Luxury product photography, marble surface, soft studio lighting, minimalist composition, premium feel, commercial quality" },
      { label: "Cosmetics", prompt: "High-end cosmetic product shot, clean white background, soft shadows, beauty photography, magazine quality" },
      { label: "Tech Product", prompt: "Sleek technology product, dramatic lighting, dark background, reflective surface, Apple-style photography" }
    ]
  },
  {
    category: "Portrait & People",
    prompts: [
      { label: "Professional Headshot", prompt: "Professional corporate headshot, neutral background, soft natural lighting, confident expression, LinkedIn quality" },
      { label: "Fashion Portrait", prompt: "High fashion portrait photography, dramatic lighting, editorial style, Vogue magazine quality" },
      { label: "Lifestyle", prompt: "Authentic lifestyle photography, natural light, candid moment, warm tones, genuine emotion" }
    ]
  },
  {
    category: "Landscape & Nature",
    prompts: [
      { label: "Golden Hour", prompt: "Breathtaking landscape at golden hour, dramatic sky, perfect composition, National Geographic quality" },
      { label: "Minimalist Nature", prompt: "Minimalist nature photography, single subject, negative space, zen aesthetic, peaceful atmosphere" },
      { label: "Dramatic Weather", prompt: "Dramatic stormy landscape, moody atmosphere, powerful clouds, cinematic lighting, award-winning photography" }
    ]
  },
  {
    category: "Architecture & Interior",
    prompts: [
      { label: "Modern Architecture", prompt: "Modern architectural photography, clean lines, geometric shapes, professional real estate quality" },
      { label: "Luxury Interior", prompt: "Luxury interior design photography, natural light, warm ambiance, Architectural Digest quality" },
      { label: "Urban Night", prompt: "Urban cityscape at night, neon lights, long exposure, cyberpunk aesthetic, cinematic" }
    ]
  }
];

// DSLR enhancement text
const DSLR_ENHANCEMENT = ", professional photography, 8k uhd, high resolution, sharp focus, detailed, masterpiece, best quality, photorealistic";
const DSLR_NEGATIVE = "blurry, low resolution, pixelated, jpeg artifacts, noise, grainy, oversaturated, undersaturated, overexposed, underexposed, bad anatomy, deformed, ugly, duplicate, watermark, signature, text overlay, cropped, out of frame, worst quality, low quality";

export default function ZImageStudio({ apiBase }) {
  // Generation state
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [selectedResolution, setSelectedResolution] = useState(RESOLUTION_PRESETS[0]);
  const [qualityPreset, setQualityPreset] = useState("ultra");
  const [seed, setSeed] = useState(-1);
  const [enhancePrompt, setEnhancePrompt] = useState(true);
  const [useDSLRNegative, setUseDSLRNegative] = useState(true);
  
  // Advanced controls
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customSteps, setCustomSteps] = useState(22);
  const [customCFG, setCustomCFG] = useState(7.5);
  
  // UI state
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [showTemplates, setShowTemplates] = useState(false);
  
  // Refs
  const imageRef = useRef(null);
  const promptRef = useRef(null);

  // Generate image
  const generateImage = async () => {
    if (!prompt.trim()) {
      setError("Please enter a prompt describing your image");
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      const preset = QUALITY_PRESETS[qualityPreset];
      
      const response = await fetch(`${apiBase}/api/z-image/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          negative_prompt: negativePrompt.trim(),
          width: selectedResolution.width,
          height: selectedResolution.height,
          steps: showAdvanced ? customSteps : preset.steps,
          cfg_scale: showAdvanced ? customCFG : preset.cfg,
          seed: seed,
          quality_preset: qualityPreset,
          enhance_prompt: enhancePrompt,
          use_dslr_negative: useDSLRNegative
        })
      });

      const data = await response.json();

      if (data.success) {
        const imageUrl = data.image_url || data.image_base64;
        const newResult = {
          url: imageUrl,
          seed: data.seed_used,
          time: data.generation_time,
          prompt: prompt,
          resolution: data.resolution,
          quality: qualityPreset
        };
        
        setResult(newResult);
        
        // Add to history
        setHistory(prev => [newResult, ...prev].slice(0, 20));
      } else {
        setError(data.error || "Generation failed - please try again");
      }
    } catch (err) {
      setError("Connection failed - the model may be starting up. Please wait 30 seconds and try again.");
      console.error(err);
    } finally {
      setIsGenerating(false);
    }
  };

  // Apply template
  const applyTemplate = (template) => {
    setPrompt(template.prompt);
    setShowTemplates(false);
    promptRef.current?.focus();
  };

  // Download image
  const downloadImage = async () => {
    if (!result?.url) return;
    
    try {
      const response = await fetch(result.url);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `z-image-${selectedResolution.width}x${selectedResolution.height}-${Date.now()}.png`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      // Fallback
      window.open(result.url, '_blank');
    }
  };

  // Copy seed
  const copySeed = () => {
    if (result?.seed) {
      navigator.clipboard.writeText(String(result.seed));
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: `linear-gradient(180deg, ${C.void} 0%, ${C.void2} 100%)`,
      color: C.text
    }}>
      {/* Header */}
      <div style={{ 
        padding: '20px 24px',
        borderBottom: `1px solid ${C.border}`,
        background: C.void,
        position: 'sticky',
        top: 0,
        zIndex: 100
      }}>
        <div style={{ maxWidth: 1600, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ 
              fontSize: 24, 
              fontWeight: 700, 
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 12
            }}>
              <span style={{
                background: `linear-gradient(135deg, ${C.gold}, ${C.goldBright})`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>
                Z-Image Studio
              </span>
              <span style={{ 
                fontSize: 10, 
                padding: '4px 8px', 
                background: 'rgba(168,85,247,0.2)',
                color: C.purple,
                borderRadius: 4,
                fontWeight: 600
              }}>
                TURBO 6B
              </span>
            </h1>
            <p style={{ color: C.textDim, fontSize: 12, margin: '4px 0 0' }}>
              #1 Open Source Model • DSLR Quality • Up to 2048×2048
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              style={{
                padding: '8px 16px',
                background: showTemplates ? 'rgba(201,168,110,0.15)' : C.surface2,
                border: `1px solid ${showTemplates ? C.gold : C.border}`,
                borderRadius: 8,
                color: showTemplates ? C.gold : C.textDim,
                fontSize: 12,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
              </svg>
              Templates
            </button>
          </div>
        </div>
      </div>

      <div style={{ padding: 24, maxWidth: 1600, margin: '0 auto' }}>
        {/* Templates Panel */}
        {showTemplates && (
          <div style={{
            background: C.surface,
            borderRadius: 16,
            padding: 20,
            marginBottom: 24,
            border: `1px solid ${C.border}`
          }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              {PROMPT_TEMPLATES.map((cat, i) => (
                <button
                  key={i}
                  onClick={() => setActiveCategory(activeCategory === i ? null : i)}
                  style={{
                    padding: '8px 16px',
                    background: activeCategory === i ? 'rgba(201,168,110,0.15)' : C.surface2,
                    border: `1px solid ${activeCategory === i ? C.gold : C.border}`,
                    borderRadius: 8,
                    color: activeCategory === i ? C.gold : C.textDim,
                    fontSize: 12,
                    cursor: 'pointer'
                  }}
                >
                  {cat.category}
                </button>
              ))}
            </div>
            
            {activeCategory !== null && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {PROMPT_TEMPLATES[activeCategory].prompts.map((t, i) => (
                  <button
                    key={i}
                    onClick={() => applyTemplate(t)}
                    style={{
                      padding: 12,
                      background: C.surface2,
                      border: `1px solid ${C.border}`,
                      borderRadius: 10,
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = C.gold;
                      e.currentTarget.style.background = 'rgba(201,168,110,0.05)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = C.border;
                      e.currentTarget.style.background = C.surface2;
                    }}
                  >
                    <div style={{ color: C.gold, fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{t.label}</div>
                    <div style={{ color: C.textDim, fontSize: 11, lineHeight: 1.4 }}>{t.prompt.substring(0, 100)}...</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: 24 }}>
          {/* Left Column - Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Prompt Input */}
            <div style={{ 
              background: C.surface, 
              borderRadius: 16, 
              padding: 20,
              border: `1px solid ${C.border}`
            }}>
              <label style={{ color: C.textDim, fontSize: 11, marginBottom: 8, display: 'block', textTransform: 'uppercase', letterSpacing: 1 }}>
                Describe Your Image
              </label>
              <textarea
                ref={promptRef}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="A majestic snow-capped mountain at golden hour, dramatic clouds, crystal clear lake reflection, professional landscape photography..."
                style={{
                  width: '100%',
                  minHeight: 120,
                  padding: 16,
                  background: C.surface2,
                  border: `1px solid ${C.border}`,
                  borderRadius: 12,
                  color: C.text,
                  fontSize: 14,
                  lineHeight: 1.6,
                  resize: 'vertical',
                  outline: 'none',
                  fontFamily: 'inherit'
                }}
                onFocus={(e) => e.target.style.borderColor = C.gold}
                onBlur={(e) => e.target.style.borderColor = C.border}
              />
              
              {/* Enhancement toggles */}
              <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
                <label style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 8, 
                  cursor: 'pointer',
                  color: enhancePrompt ? C.gold : C.textDim,
                  fontSize: 12
                }}>
                  <input
                    type="checkbox"
                    checked={enhancePrompt}
                    onChange={(e) => setEnhancePrompt(e.target.checked)}
                    style={{ accentColor: C.gold }}
                  />
                  Auto-enhance for DSLR quality
                </label>
                <label style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 8, 
                  cursor: 'pointer',
                  color: useDSLRNegative ? C.gold : C.textDim,
                  fontSize: 12
                }}>
                  <input
                    type="checkbox"
                    checked={useDSLRNegative}
                    onChange={(e) => setUseDSLRNegative(e.target.checked)}
                    style={{ accentColor: C.gold }}
                  />
                  Professional negative prompts
                </label>
              </div>
            </div>

            {/* Quality Preset */}
            <div style={{ 
              background: C.surface, 
              borderRadius: 16, 
              padding: 20,
              border: `1px solid ${C.border}`
            }}>
              <label style={{ color: C.textDim, fontSize: 11, marginBottom: 12, display: 'block', textTransform: 'uppercase', letterSpacing: 1 }}>
                Quality Preset
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
                {Object.entries(QUALITY_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    onClick={() => setQualityPreset(key)}
                    style={{
                      padding: '12px 8px',
                      background: qualityPreset === key ? `${preset.color}15` : C.surface2,
                      border: `1px solid ${qualityPreset === key ? preset.color : C.border}`,
                      borderRadius: 10,
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    <div style={{ color: qualityPreset === key ? preset.color : C.text, fontSize: 12, fontWeight: 600 }}>
                      {preset.label}
                    </div>
                    <div style={{ color: C.textDim, fontSize: 9, marginTop: 4 }}>
                      {preset.steps} steps
                    </div>
                  </button>
                ))}
              </div>
              <div style={{ 
                marginTop: 12, 
                padding: 10, 
                background: C.surface2, 
                borderRadius: 8,
                fontSize: 11,
                color: C.textDim,
                display: 'flex',
                justifyContent: 'space-between'
              }}>
                <span>{QUALITY_PRESETS[qualityPreset].desc}</span>
                <span>CFG: {QUALITY_PRESETS[qualityPreset].cfg}</span>
              </div>
            </div>

            {/* Resolution */}
            <div style={{ 
              background: C.surface, 
              borderRadius: 16, 
              padding: 20,
              border: `1px solid ${C.border}`
            }}>
              <label style={{ color: C.textDim, fontSize: 11, marginBottom: 12, display: 'block', textTransform: 'uppercase', letterSpacing: 1 }}>
                Resolution
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                {RESOLUTION_PRESETS.slice(0, 9).map((res, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedResolution(res)}
                    style={{
                      padding: '10px 8px',
                      background: selectedResolution === res ? 'rgba(201,168,110,0.1)' : C.surface2,
                      border: `1px solid ${selectedResolution === res ? C.gold : C.border}`,
                      borderRadius: 8,
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      marginBottom: 4
                    }}>
                      <span style={{ fontSize: 14 }}>{res.icon}</span>
                      <span style={{ 
                        fontSize: 9, 
                        color: selectedResolution === res ? C.gold : C.textDim,
                        fontFamily: 'monospace'
                      }}>
                        {res.width}×{res.height}
                      </span>
                    </div>
                    <div style={{ color: selectedResolution === res ? C.gold : C.text, fontSize: 11, fontWeight: 500 }}>
                      {res.label}
                    </div>
                    <div style={{ color: C.textDim, fontSize: 9 }}>{res.use}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Advanced Controls */}
            <div style={{ 
              background: C.surface, 
              borderRadius: 16, 
              padding: 16,
              border: `1px solid ${C.border}`
            }}>
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                style={{
                  width: '100%',
                  background: 'none',
                  border: 'none',
                  color: C.textDim,
                  fontSize: 12,
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <span>Advanced Controls</span>
                <span style={{ transform: showAdvanced ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▼</span>
              </button>
              
              {showAdvanced && (
                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {/* Custom Steps */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <label style={{ color: C.textDim, fontSize: 11 }}>Inference Steps</label>
                      <span style={{ color: C.gold, fontSize: 12, fontWeight: 600 }}>{customSteps}</span>
                    </div>
                    <input
                      type="range"
                      min="4"
                      max="50"
                      value={customSteps}
                      onChange={(e) => setCustomSteps(parseInt(e.target.value))}
                      style={{ width: '100%', accentColor: C.gold }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: C.textDim }}>
                      <span>Fast</span>
                      <span>Maximum Detail</span>
                    </div>
                  </div>
                  
                  {/* CFG Scale */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <label style={{ color: C.textDim, fontSize: 11 }}>CFG Scale (Prompt Adherence)</label>
                      <span style={{ color: C.gold, fontSize: 12, fontWeight: 600 }}>{customCFG}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="20"
                      step="0.5"
                      value={customCFG}
                      onChange={(e) => setCustomCFG(parseFloat(e.target.value))}
                      style={{ width: '100%', accentColor: C.gold }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: C.textDim }}>
                      <span>Creative</span>
                      <span>Strict</span>
                    </div>
                  </div>
                  
                  {/* Seed */}
                  <div>
                    <label style={{ color: C.textDim, fontSize: 11, marginBottom: 8, display: 'block' }}>
                      Seed (for reproducibility)
                    </label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        type="number"
                        value={seed}
                        onChange={(e) => setSeed(parseInt(e.target.value) || -1)}
                        placeholder="-1 for random"
                        style={{
                          flex: 1,
                          padding: '10px 12px',
                          background: C.surface2,
                          border: `1px solid ${C.border}`,
                          borderRadius: 8,
                          color: C.text,
                          fontSize: 13,
                          outline: 'none'
                        }}
                      />
                      <button
                        onClick={() => setSeed(-1)}
                        style={{
                          padding: '10px 16px',
                          background: C.surface2,
                          border: `1px solid ${C.border}`,
                          borderRadius: 8,
                          color: C.textDim,
                          fontSize: 11,
                          cursor: 'pointer'
                        }}
                      >
                        Random
                      </button>
                    </div>
                  </div>
                  
                  {/* Negative Prompt */}
                  <div>
                    <label style={{ color: C.textDim, fontSize: 11, marginBottom: 8, display: 'block' }}>
                      Custom Negative Prompt (optional)
                    </label>
                    <textarea
                      value={negativePrompt}
                      onChange={(e) => setNegativePrompt(e.target.value)}
                      placeholder="Things to avoid in the image..."
                      style={{
                        width: '100%',
                        minHeight: 60,
                        padding: 12,
                        background: C.surface2,
                        border: `1px solid ${C.border}`,
                        borderRadius: 8,
                        color: C.text,
                        fontSize: 12,
                        resize: 'vertical',
                        outline: 'none',
                        fontFamily: 'inherit'
                      }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Generate Button */}
            <button
              onClick={generateImage}
              disabled={isGenerating || !prompt.trim()}
              style={{
                width: '100%',
                padding: '18px 24px',
                background: isGenerating 
                  ? C.surface2 
                  : `linear-gradient(135deg, ${C.gold}, #b8956a)`,
                border: 'none',
                borderRadius: 14,
                color: isGenerating ? C.textDim : C.void,
                fontSize: 16,
                fontWeight: 700,
                cursor: isGenerating ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
                boxShadow: isGenerating ? 'none' : '0 4px 20px rgba(201,168,110,0.3)'
              }}
            >
              {isGenerating ? (
                <>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%',
                    border: `2px solid ${C.gold}`,
                    borderTopColor: 'transparent',
                    animation: 'spin 1s linear infinite'
                  }} />
                  Generating {QUALITY_PRESETS[qualityPreset].label} Quality...
                </>
              ) : (
                <>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                  </svg>
                  Generate Image
                </>
              )}
            </button>

            {/* Error */}
            {error && (
              <div style={{
                padding: 14,
                background: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 12,
                color: C.red,
                fontSize: 13
              }}>
                {error}
              </div>
            )}
          </div>

          {/* Right Column - Result */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Generated Image */}
            <div style={{ 
              background: C.surface, 
              borderRadius: 16, 
              padding: 16,
              border: `1px solid ${C.border}`,
              flex: 1
            }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: 12 
              }}>
                <span style={{ color: C.textDim, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
                  Generated Image
                </span>
                {result && (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={copySeed}
                      title="Copy seed for reproducibility"
                      style={{
                        padding: '6px 10px',
                        background: C.surface2,
                        border: `1px solid ${C.border}`,
                        borderRadius: 6,
                        color: C.textDim,
                        fontSize: 10,
                        cursor: 'pointer'
                      }}
                    >
                      Seed: {result.seed}
                    </button>
                    <button
                      onClick={downloadImage}
                      style={{
                        padding: '6px 12px',
                        background: 'rgba(34,197,94,0.1)',
                        border: '1px solid rgba(34,197,94,0.3)',
                        borderRadius: 6,
                        color: C.green,
                        fontSize: 10,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                      </svg>
                      Download
                    </button>
                  </div>
                )}
              </div>

              <div style={{
                aspectRatio: `${selectedResolution.width}/${selectedResolution.height}`,
                background: C.void,
                borderRadius: 12,
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                border: `1px solid ${C.border}`
              }}>
                {result?.url ? (
                  <img
                    ref={imageRef}
                    src={result.url}
                    alt="Generated"
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain'
                    }}
                  />
                ) : (
                  <div style={{ textAlign: 'center', color: C.textDim, padding: 40 }}>
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ opacity: 0.2, marginBottom: 16 }}>
                      <rect x="3" y="3" width="18" height="18" rx="2"/>
                      <circle cx="8.5" cy="8.5" r="1.5"/>
                      <polyline points="21 15 16 10 5 21"/>
                    </svg>
                    <p style={{ fontSize: 14, marginBottom: 4 }}>Your masterpiece awaits</p>
                    <p style={{ fontSize: 11, opacity: 0.6 }}>{selectedResolution.width} × {selectedResolution.height}</p>
                  </div>
                )}

                {isGenerating && (
                  <div style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'rgba(6,6,8,0.95)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backdropFilter: 'blur(4px)'
                  }}>
                    <div style={{
                      width: 60, height: 60, borderRadius: '50%',
                      border: `3px solid ${C.gold}`,
                      borderTopColor: 'transparent',
                      animation: 'spin 1s linear infinite',
                      marginBottom: 20
                    }} />
                    <p style={{ color: C.gold, fontSize: 15, fontWeight: 600 }}>Creating DSLR-Quality Image...</p>
                    <p style={{ color: C.textDim, fontSize: 12, marginTop: 8 }}>
                      {QUALITY_PRESETS[qualityPreset].desc}
                    </p>
                    <div style={{ 
                      marginTop: 16, 
                      padding: '8px 16px', 
                      background: 'rgba(201,168,110,0.1)',
                      borderRadius: 8,
                      fontSize: 11,
                      color: C.gold
                    }}>
                      {selectedResolution.width} × {selectedResolution.height} • {showAdvanced ? customSteps : QUALITY_PRESETS[qualityPreset].steps} steps
                    </div>
                  </div>
                )}
              </div>

              {result && (
                <div style={{ 
                  marginTop: 12, 
                  padding: 12, 
                  background: C.surface2, 
                  borderRadius: 10,
                  fontSize: 11 
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: C.textDim }}>
                    <span>Resolution: {result.resolution}</span>
                    <span>Quality: {QUALITY_PRESETS[result.quality]?.label}</span>
                    <span>Time: {result.time?.toFixed(1)}s</span>
                  </div>
                </div>
              )}
            </div>

            {/* History */}
            {history.length > 0 && (
              <div style={{ 
                background: C.surface, 
                borderRadius: 16, 
                padding: 16,
                border: `1px solid ${C.border}`
              }}>
                <span style={{ color: C.textDim, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12, display: 'block' }}>
                  Recent ({history.length})
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                  {history.slice(0, 8).map((item, i) => (
                    <div
                      key={i}
                      onClick={() => setResult(item)}
                      style={{
                        aspectRatio: '1',
                        borderRadius: 8,
                        overflow: 'hidden',
                        cursor: 'pointer',
                        border: `1px solid ${result === item ? C.gold : C.border}`,
                        transition: 'all 0.2s',
                        opacity: result === item ? 1 : 0.7
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseLeave={(e) => e.currentTarget.style.opacity = result === item ? '1' : '0.7'}
                    >
                      <img
                        src={item.url}
                        alt=""
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        input[type="range"] {
          -webkit-appearance: none;
          height: 6px;
          background: ${C.surface2};
          border-radius: 3px;
        }
        input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 16px;
          height: 16px;
          background: ${C.gold};
          border-radius: 50%;
          cursor: pointer;
        }
      `}</style>
    </div>
  );
}
