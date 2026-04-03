import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { ChevronLeft, ShoppingBag, Share2, Link2, Check, Copy } from "lucide-react";
import { toast } from "sonner";

// AURA-GEN Serum 30-Day Solo Protocol
// ReRoots Aesthetics · TXA + PDRN + Argireline 17% Active Recovery Complex

const days = [
  {
    range: "Day 1–3", label: "FIRST CONTACT", color: "#E8A0C0",
    bg: "rgba(232,160,192,0.08)", border: "rgba(232,160,192,0.3)",
    issues: [
      { icon: "💧", problem: "Dehydration / Tightness", rating: 85, mechanism: "Methyl Gluceth-20 binds water instantly. Panthenol penetrates to dermis within hours. LMW HA floods intercellular space. Skin plump and comfortable from first application." },
      { icon: "✨", problem: "Dull / Flat Skin Tone", rating: 75, mechanism: "PDRN activates A2A adenosine receptors — triggers cellular energy surge within 48hrs. Skin takes on an immediate luminosity that customers notice before Day 3." },
      { icon: "🔴", problem: "Surface Redness / Reactive Skin", rating: 70, mechanism: "TXA anti-inflammatory action begins immediately. Allantoin calms keratinocyte reactivity. Niacinamide starts suppressing inflammatory cytokine release." },
      { icon: "🌊", problem: "Surface Dehydration Lines", rating: 72, mechanism: "PGA forms a moisture-retaining film on the surface. Combined with LMW HA underneath, fine dehydration lines visibly fill within 48–72 hours." },
    ],
    summary: "Immediate comfort, luminosity and hydration. Skin feels and looks different from application number one."
  },
  {
    range: "Day 4–7", label: "ACTIVE LOADING", color: "#C9A84C",
    bg: "rgba(201,168,76,0.08)", border: "rgba(201,168,76,0.3)",
    issues: [
      { icon: "🌑", problem: "Early Hyperpigmentation", rating: 50, mechanism: "TXA 5% has now built up sufficient concentration to block the plasmin–plasminogen pathway. Niacinamide inhibiting melanosome transfer. NAG inhibiting tyrosinase. Three mechanisms active simultaneously." },
      { icon: "🧬", problem: "Fine Expression Lines", rating: 45, mechanism: "Argireline 10% — cumulative SNARE complex inhibition reaching visible threshold. Micro-contractions in forehead and eye area begin relaxing. First subtle smoothing visible by Day 6–7." },
      { icon: "⚡", problem: "Fatigue / Stressed Skin Appearance", rating: 78, mechanism: "PDRN + Adenosine ATP boost fully loaded. Cellular energy production reset. Skin appears rested, bouncy and recovered even after poor sleep." },
      { icon: "🔬", problem: "Congested / Dull Complexion", rating: 68, mechanism: "DMI penetration system now pushing actives at maximum depth. Ginseng Berry antioxidants clearing oxidative backlog. Complexion brightness visibly improving day by day." },
    ],
    summary: "The active complex is fully loaded. Brightening mechanisms all online. Fine lines beginning to respond."
  },
  {
    range: "Day 8–14", label: "CELLULAR RENEWAL", color: "#A8D8A8",
    bg: "rgba(168,216,168,0.08)", border: "rgba(168,216,168,0.3)",
    issues: [
      { icon: "🌟", problem: "Uneven Skin Tone / Patches", rating: 60, mechanism: "First full epidermal cell cycle now complete. Pigmented cells shed, fresh cells replacing them. TXA + NAG + Niacinamide working all three melanin pathways. Visible tone improvement by Day 10–12." },
      { icon: "🧬", problem: "Moderate Fine Lines", rating: 65, mechanism: "Argireline 10% cumulative effect now clearly visible. Forehead, crow's feet and perioral lines measurably smoother. Maximum effect builds over 4–6 weeks but Week 2 is the first real milestone." },
      { icon: "💎", problem: "Loss of Radiance / Glass Skin", rating: 80, mechanism: "PDRN bio-repair + Ginseng antioxidant + full hydration stack = Glass Skin effect fully active. Skin reflects light differently. Customers notice without being told." },
      { icon: "🛡️", problem: "Post-Inflammatory Redness", rating: 72, mechanism: "TXA anti-inflammatory + Ceramide NP barrier support + SOD enzyme — reactive redness from breakouts, friction and UV exposure measurably reduced." },
    ],
    summary: "Week 2 is the first transformation milestone. Tone evening, fine lines smoothing, glass skin effect visible."
  },
  {
    range: "Day 15–21", label: "BIO-REPAIR PEAK", color: "#87CEEB",
    bg: "rgba(135,206,235,0.08)", border: "rgba(135,206,235,0.3)",
    issues: [
      { icon: "🧬", problem: "DNA-Level Skin Damage", rating: 75, mechanism: "PDRN 2% has now completed two full cycles of DNA fragment delivery. Tissue regeneration at A2A receptor level measurable. Skin recovering from UV, pollution and oxidative history." },
      { icon: "🌑", problem: "Stubborn Pigmentation / Dark Spots", rating: 68, mechanism: "Two full cell cycles complete. Melanin-heavy surface cells replaced twice over. Spots 30–40% lighter. TXA preventing new pigment formation simultaneously." },
      { icon: "🔄", problem: "Post-Acne Marks (PIH)", rating: 72, mechanism: "TXA prevents new PIH formation. NAG + Niacinamide clear existing marks via dual melanin pathway. PIH typically responds 2–3x faster than solar lentigo." },
      { icon: "⚡", problem: "Cellular Energy Deficit / Aging Skin", rating: 80, mechanism: "Adenosine + PDRN + Ginseng have reset the cellular metabolic baseline. Skin producing energy like younger tissue. Elasticity and bounce measurably improved." },
    ],
    summary: "Week 3 — PDRN at peak bio-repair activity. DNA damage being addressed at cellular level. Skin fundamentally different."
  },
  {
    range: "Day 22–30", label: "FULL EXPRESSION", color: "#9B8EC4",
    bg: "rgba(155,142,196,0.08)", border: "rgba(155,142,196,0.3)",
    issues: [
      { icon: "🏆", problem: "Expression Lines / Dynamic Wrinkles", rating: 78, mechanism: "Argireline 10% at maximum cumulative effect. 30 days of continuous SNARE inhibition has relaxed habitual muscle micro-contractions. Lines visibly smoother — especially forehead and eye area." },
      { icon: "🌈", problem: "Overall Complexion / Brightness", rating: 88, mechanism: "Three full cell cycles complete. Vast majority of surface melanin cleared. Complexion uniformly 1–2 shades brighter. TXA continuing to suppress new pigment formation going forward." },
      { icon: "🌿", problem: "Environmental / Oxidative Damage", rating: 82, mechanism: "SOD enzyme + Ginseng + Tocopheryl have been neutralising free radicals every day. Cumulative antioxidant protection now measurable in skin clarity and resilience." },
      { icon: "💎", problem: "Lack of Skin Vitality / Volume", rating: 85, mechanism: "PDRN bio-regeneration + Ceramide NP barrier + full hydration system = skin that looks alive, plump and structurally healthy. This is the before/after photo result." },
    ],
    summary: "Day 30 full result. Brightening, bio-repair, fine line reduction and vitality — all peak simultaneously."
  }
];

const ritual = {
  am: [
    { step: 1, action: "Gentle cleanser", time: "60 sec", note: "Never skip — actives absorb 40% better on clean skin" },
    { step: 2, action: "3–4 drops, press into damp skin", time: "60 sec", note: "Damp skin amplifies DMI penetration. Do not rub — press and hold 5 seconds" },
    { step: 3, action: "SPF 30+ minimum", time: "30 sec", note: "Non-negotiable. TXA brightening reverses within days without SPF protection" },
  ],
  pm: [
    { step: 1, action: "Double cleanse — oil then water", time: "2 min", note: "Remove every trace of SPF, pollution and sebum before actives" },
    { step: 2, action: "4–5 drops — slightly more than AM", time: "60 sec", note: "Night is peak PDRN and Argireline activity. Increase dose at PM for maximum repair" },
    { step: 3, action: "Optional: light moisturiser on top", time: "20 sec", note: "If skin is very dry, a ceramide moisturizer over serum increases barrier benefit" },
  ]
};

const concerns = [
  { name: "Hyperpigmentation / Dark Spots", rating: 5, day30: 88, ingredients: ["TXA 5%", "Niacinamide 4%", "NAG 2%", "Cyanocobalamin"] },
  { name: "Fine Lines / Expression Lines", rating: 5, day30: 78, ingredients: ["Argireline 10%", "Adenosine", "PDRN"] },
  { name: "Hydration / Plumping", rating: 4, day30: 85, ingredients: ["Methyl Gluceth-20", "LMW HA", "PGA", "Panthenol"] },
  { name: "Skin Vitality / Radiance", rating: 5, day30: 87, ingredients: ["PDRN 2%", "Ginseng Berry", "SOD", "Adenosine"] },
  { name: "Bio-Repair / DNA Repair", rating: 5, day30: 80, ingredients: ["PDRN 2%", "Ceramide NP", "SOD Liposomal"] },
  { name: "Redness / Inflammation", rating: 4, day30: 75, ingredients: ["TXA 5%", "Allantoin", "Niacinamide"] },
  { name: "Antioxidant Protection", rating: 4, day30: 80, ingredients: ["Ginseng Berry", "SOD", "Tocopheryl", "Propyl Gallate"] },
  { name: "Barrier Support", rating: 3, day30: 65, ingredients: ["Ceramide NP", "Panthenol"] },
];

function Stars({ count, color = "#E8A0C0" }) {
  return (
    <span style={{ display: "inline-flex", gap: 2 }}>
      {[1,2,3,4,5].map(i => (
        <span key={i} style={{ fontSize: 12, color: i <= count ? color : "rgba(255,255,255,0.1)" }}>★</span>
      ))}
    </span>
  );
}

function Bar({ value, color }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 100, height: 4, overflow: "hidden", flex: 1 }}>
      <div style={{ width: `${value}%`, height: "100%", borderRadius: 100, background: `linear-gradient(90deg, ${color}66, ${color})`, transition: "width 1s ease" }} />
    </div>
  );
}

export default function AuraGenSerumProtocolPage() {
  const navigate = useNavigate();
  const [activeDay, setActiveDay] = useState(0);
  const [activeTab, setActiveTab] = useState("timeline");
  const [copied, setCopied] = useState(false);
  const [showShareMenu, setShowShareMenu] = useState(false);
  
  // Set page title on mount
  useEffect(() => {
    document.title = "AURA-GEN Serum 30-Day Protocol | ReRoots PDRN Skincare";
    
    // Update meta description
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', 'Complete 30-day protocol for AURA-GEN Serum with 17% Active Recovery Complex. Day-by-day guide with PDRN, Tranexamic Acid, and Argireline.');
    }
    
    return () => {
      document.title = "ReRoots | Premium PDRN Skincare";
    };
  }, []);
  
  const day = days[activeDay];
  const ACCENT = "#E8A0C0";

  // Share URL
  const shareUrl = `${window.location.origin}/aura-gen-serum-protocol`;
  const shareTitle = "AURA-GEN Serum 30-Day Protocol";
  const shareText = "17% Active Recovery Complex — TXA + PDRN + Argireline. The complete brightening, anti-aging, and bio-repair serum protocol.";

  // Copy link to clipboard
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Link copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      const textArea = document.createElement("textarea");
      textArea.value = shareUrl;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setCopied(true);
      toast.success("Link copied!");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Native share (mobile)
  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: shareTitle, text: shareText, url: shareUrl });
      } catch (err) {
        if (err.name !== 'AbortError') copyLink();
      }
    } else {
      setShowShareMenu(!showShareMenu);
    }
  };

  // Share to specific platform
  const shareTo = (platform) => {
    const encodedUrl = encodeURIComponent(shareUrl);
    const encodedText = encodeURIComponent(shareText);
    const encodedTitle = encodeURIComponent(shareTitle);
    const fullMessage = `${shareText}\n\n${shareUrl}`;
    const encodedFullMessage = encodeURIComponent(fullMessage);
    
    const urls = {
      whatsapp: `https://api.whatsapp.com/send?text=${encodedFullMessage}`,
      twitter: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}&quote=${encodedText}`,
      email: `mailto:?subject=${encodedTitle}&body=${encodedFullMessage}`,
      sms: `sms:?&body=${encodedFullMessage}`,
    };
    window.open(urls[platform], '_blank');
    setShowShareMenu(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#080812", color: "#F0EBE3", fontFamily: "'Georgia', serif", overflowX: "hidden", paddingTop: "70px" }}>
      {/* SEO Meta Tags */}
      <Helmet>
        <title>AURA-GEN Serum 30-Day Protocol | ReRoots PDRN Skincare</title>
        <meta name="description" content="Complete 30-day protocol for AURA-GEN Serum with 17% Active Recovery Complex. Day-by-day guide with PDRN, Tranexamic Acid, and Argireline. See visible results timeline." />
        <meta name="keywords" content="AURA-GEN serum protocol, 30 day skincare routine, PDRN serum, Tranexamic Acid TXA, Argireline anti-aging, salmon DNA skincare, brightening serum, ReRoots Canada" />
        <link rel="canonical" href="https://reroots.ca/aura-gen-serum-protocol" />
        
        {/* Open Graph */}
        <meta property="og:title" content="AURA-GEN Serum 30-Day Protocol" />
        <meta property="og:description" content="17% Active Recovery Complex — TXA + PDRN + Argireline. The complete brightening, anti-aging, and bio-repair serum protocol." />
        <meta property="og:url" content="https://reroots.ca/aura-gen-serum-protocol" />
        <meta property="og:type" content="article" />
        <meta property="og:image" content="https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/a4671ebm_1767158945864.jpg" />
        
        {/* Twitter */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="AURA-GEN Serum 30-Day Protocol" />
        <meta name="twitter:description" content="Complete day-by-day transformation guide for AURA-GEN 17% Active Recovery Serum." />
        
        {/* Schema.org Structured Data */}
        <script type="application/ld+json">{`
          {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": "AURA-GEN Serum 30-Day Protocol",
            "description": "Complete 30-day protocol for AURA-GEN Serum with PDRN, Tranexamic Acid, and Argireline 17% Active Recovery Complex",
            "totalTime": "P30D",
            "tool": [
              {"@type": "HowToTool", "name": "AURA-GEN Serum"},
              {"@type": "HowToTool", "name": "SPF 30+ Sunscreen"}
            ],
            "step": [
              {"@type": "HowToStep", "name": "Day 1-3: First Contact", "text": "PDRN activates A2A receptors. Immediate hydration and luminosity."},
              {"@type": "HowToStep", "name": "Day 4-7: Signal Cascade", "text": "PDRN-triggered DNA repair visible. TXA reducing new melanin."},
              {"@type": "HowToStep", "name": "Day 8-14: Deep Repair", "text": "Collagen synthesis activated. Fine lines softening."},
              {"@type": "HowToStep", "name": "Day 15-21: Visible Change", "text": "Pigmentation measurably lighter. Expression lines relaxed."},
              {"@type": "HowToStep", "name": "Day 22-30: Transformation", "text": "Full bio-repair cycle complete. Skin transformed."}
            ],
            "supply": [
              {"@type": "HowToSupply", "name": "PDRN 2% (Salmon DNA)"},
              {"@type": "HowToSupply", "name": "Tranexamic Acid 5%"},
              {"@type": "HowToSupply", "name": "Argireline 10%"},
              {"@type": "HowToSupply", "name": "Niacinamide 5%"}
            ]
          }
        `}</script>
      </Helmet>
      
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Josefin+Sans:wght@200;300;400&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #E8A0C044; border-radius: 100px; }
        .btn { cursor: pointer; border: none; background: none; transition: all 0.25s; }
        .btn:hover { opacity: 0.75; }
        .card:hover { transform: translateX(3px); }
        .card { transition: transform 0.2s; }
        .daybtn:hover { transform: translateY(-2px); }
        .daybtn { transition: all 0.25s; border: none; cursor: pointer; }
      `}</style>

      {/* HEADER */}
      <div style={{ background: "linear-gradient(160deg, #110818 0%, #080812 100%)", borderBottom: "1px solid rgba(232,160,192,0.12)", padding: "24px 24px 28px", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: -80, right: -80, width: 360, height: 360, background: "radial-gradient(circle, rgba(232,160,192,0.07) 0%, transparent 65%)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", bottom: -40, left: 200, width: 200, height: 200, background: "radial-gradient(circle, rgba(155,142,196,0.05) 0%, transparent 65%)", pointerEvents: "none" }} />

        {/* Top Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <button onClick={() => navigate(-1)} style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none", cursor: "pointer", color: "#F0EBE388", fontSize: 12 }}>
            <ChevronLeft size={16} /> Back to Shop
          </button>
          
          {/* Share Button */}
          <div style={{ position: "relative" }}>
            <button onClick={handleNativeShare} style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 100, background: "rgba(232,160,192,0.1)", border: "1px solid rgba(232,160,192,0.3)", cursor: "pointer", color: ACCENT }}>
              <Share2 size={14} />
              <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, textTransform: "uppercase" }}>Share</span>
            </button>
            
            {showShareMenu && (
              <div style={{ position: "absolute", top: "calc(100% + 8px)", right: 0, background: "#1a1a2e", borderRadius: 12, border: "1px solid rgba(232,160,192,0.2)", padding: "8px", minWidth: 180, zIndex: 100, boxShadow: "0 8px 32px rgba(0,0,0,0.4)" }}>
                <button onClick={copyLink} style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "10px 12px", borderRadius: 8, border: "none", background: copied ? "rgba(76,175,80,0.15)" : "transparent", cursor: "pointer", color: copied ? "#4CAF50" : "#F0EBE3" }}>
                  {copied ? <Check size={16} /> : <Link2 size={16} />}
                  <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 1 }}>{copied ? "Copied!" : "Copy Link"}</span>
                </button>
                <div style={{ height: 1, background: "rgba(255,255,255,0.06)", margin: "4px 0" }} />
                {[
                  { id: "whatsapp", label: "WhatsApp", icon: "💬" },
                  { id: "sms", label: "Text Message", icon: "📱" },
                  { id: "email", label: "Email", icon: "📧" },
                  { id: "twitter", label: "Twitter/X", icon: "𝕏" },
                  { id: "facebook", label: "Facebook", icon: "📘" },
                ].map(opt => (
                  <button key={opt.id} onClick={() => shareTo(opt.id)} style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "10px 12px", borderRadius: 8, border: "none", background: "transparent", cursor: "pointer", color: "#F0EBE3" }}>
                    <span style={{ fontSize: 14 }}>{opt.icon}</span>
                    <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 1 }}>{opt.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 6, color: "#E8A0C066", marginBottom: 10, textTransform: "uppercase" }}>
          ReRoots Aesthetics · Standalone Protocol
        </div>
        <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 36, fontWeight: 300, letterSpacing: 2, lineHeight: 1.05, marginBottom: 6 }}>
          AURA-GEN
          <span style={{ color: "#E8A0C0", fontStyle: "italic" }}> Serum</span>
        </div>
        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 4, color: "#F0EBE366", textTransform: "uppercase", marginBottom: 20 }}>
          Bio-Regenerator · 30-Day Solo Protocol
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {["TXA 5%", "Argireline 10%", "PDRN 2%", "DMI Delivery", "17% Active Core"].map(tag => (
            <span key={tag} style={{
              fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, textTransform: "uppercase",
              color: "#E8A0C0AA", padding: "4px 12px", borderRadius: 100,
              background: "rgba(232,160,192,0.08)", border: "1px solid rgba(232,160,192,0.18)"
            }}>{tag}</span>
          ))}
          <span style={{
            fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, textTransform: "uppercase",
            color: "#4CAF50AA", padding: "4px 12px", borderRadius: 100,
            background: "rgba(76,175,80,0.08)", border: "1px solid rgba(76,175,80,0.18)"
          }}>✓ 7/8 Concerns Covered</span>
        </div>
      </div>

      {/* TABS */}
      <div style={{ display: "flex", padding: "0 24px", borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0A0A14", overflowX: "auto" }}>
        {[{ id: "timeline", label: "30-Day Timeline" }, { id: "ritual", label: "Application Ritual" }, { id: "matrix", label: "Resolving Matrix" }].map(t => (
          <button key={t.id} className="btn" onClick={() => setActiveTab(t.id)} style={{
            padding: "14px 20px", fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, textTransform: "uppercase",
            color: activeTab === t.id ? ACCENT : "#F0EBE333",
            borderBottom: activeTab === t.id ? `2px solid ${ACCENT}` : "2px solid transparent", marginBottom: -1, whiteSpace: "nowrap"
          }}>{t.label}</button>
        ))}
      </div>

      <div style={{ padding: "24px", maxWidth: 1080 }}>

        {/* TIMELINE */}
        {activeTab === "timeline" && (
          <div>
            <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
              {days.map((d, i) => (
                <button key={i} className="daybtn" onClick={() => setActiveDay(i)} style={{
                  padding: "10px 16px", borderRadius: 100,
                  border: `1px solid ${activeDay === i ? d.color : "rgba(255,255,255,0.07)"}`,
                  background: activeDay === i ? `${d.color}14` : "rgba(255,255,255,0.02)"
                }}>
                  <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 3, color: activeDay === i ? d.color : "#F0EBE344", textTransform: "uppercase", marginBottom: 2 }}>{d.range}</div>
                  <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 2, color: activeDay === i ? `${d.color}99` : "#F0EBE322", textTransform: "uppercase" }}>{d.label}</div>
                </button>
              ))}
            </div>

            {/* Phase Banner */}
            <div style={{ padding: "16px 20px", borderRadius: 12, border: `1px solid ${day.color}33`, background: day.bg, marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: `${day.color}88`, textTransform: "uppercase", marginBottom: 4 }}>Phase {activeDay + 1} · {day.range}</div>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 300, color: day.color, letterSpacing: 2 }}>{day.label}</div>
              </div>
              <div style={{ padding: "10px 16px", borderRadius: 8, background: "rgba(0,0,0,0.25)", border: `1px solid ${day.color}1A`, maxWidth: 320 }}>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 3, color: `${day.color}66`, textTransform: "uppercase", marginBottom: 4 }}>Summary</div>
                <div style={{ fontFamily: "'Georgia', serif", fontSize: 11, color: "#F0EBE3BB", lineHeight: 1.6 }}>{day.summary}</div>
              </div>
            </div>

            {/* Issue Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
              {day.issues.map((issue, i) => (
                <div key={i} className="card" style={{ padding: "16px 20px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: `1px solid ${day.border}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 18 }}>{issue.icon}</span>
                      <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 14, color: "#F0EBE3" }}>{issue.problem}</div>
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 16, fontWeight: 300, color: day.color }}>{issue.rating}%</div>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 2, color: "#F0EBE322", textTransform: "uppercase" }}>Resolved</div>
                    </div>
                  </div>
                  <div style={{ marginBottom: 10 }}><Bar value={issue.rating} color={day.color} /></div>
                  <div style={{ fontFamily: "'Georgia', serif", fontSize: 10, color: "#F0EBE366", lineHeight: 1.65 }}>{issue.mechanism}</div>
                </div>
              ))}
            </div>

            {/* Track */}
            <div style={{ marginTop: 28, paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#F0EBE322", textTransform: "uppercase", marginBottom: 12 }}>30-Day Progress Track</div>
              <div style={{ position: "relative" }}>
                <div style={{ position: "absolute", top: 9, left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.05)" }} />
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  {days.map((d, i) => (
                    <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, cursor: "pointer" }} onClick={() => setActiveDay(i)}>
                      <div style={{
                        width: 16, height: 16, borderRadius: "50%", zIndex: 1,
                        background: i <= activeDay ? d.color : "rgba(255,255,255,0.05)",
                        border: `2px solid ${i === activeDay ? d.color : "transparent"}`,
                        boxShadow: i === activeDay ? `0 0 10px ${d.color}55` : "none",
                        display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.3s"
                      }}>
                        {i < activeDay && <span style={{ fontSize: 7, color: "#080812" }}>✓</span>}
                      </div>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 1, color: i === activeDay ? d.color : "#F0EBE322", textTransform: "uppercase", textAlign: "center" }}>{d.range}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* RITUAL */}
        {activeTab === "ritual" && (
          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 26, fontWeight: 300, letterSpacing: 2, marginBottom: 4 }}>Application Ritual</div>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: "#F0EBE333", textTransform: "uppercase" }}>Serum-Only Protocol · Twice Daily</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
              {[
                { key: "am", label: "Morning", icon: "☀️", color: "#F5C842", steps: ritual.am },
                { key: "pm", label: "Evening", icon: "🌙", color: "#9B8EC4", steps: ritual.pm },
              ].map(s => (
                <div key={s.key} style={{ borderRadius: 14, border: `1px solid ${s.color}1A`, background: `linear-gradient(160deg, ${s.color}07, rgba(0,0,0,0.01))`, overflow: "hidden" }}>
                  <div style={{ padding: "16px 20px", borderBottom: `1px solid ${s.color}12`, display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 20 }}>{s.icon}</span>
                    <div>
                      <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 18, color: s.color }}>{s.label}</div>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 3, color: `${s.color}77`, textTransform: "uppercase" }}>AURA-GEN Serum Protocol</div>
                    </div>
                  </div>
                  {s.steps.map((step, i) => (
                    <div key={i} style={{ padding: "14px 20px", borderBottom: i < s.steps.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none", display: "flex", gap: 12 }}>
                      <div style={{ width: 24, height: 24, borderRadius: "50%", flexShrink: 0, background: `${s.color}14`, border: `1px solid ${s.color}2A`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Cormorant Garamond', serif", fontSize: 12, color: s.color }}>
                        {step.step}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, color: s.color, textTransform: "uppercase" }}>
                            {step.step === 2 ? "AURA-GEN Serum" : step.step === 1 ? (s.key === "am" ? "Cleanse" : "Double Cleanse") : s.key === "am" ? "SPF 30+" : "Moisturiser (optional)"}
                          </div>
                          <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 1, color: "#F0EBE322", background: "rgba(255,255,255,0.02)", padding: "2px 7px", borderRadius: 100, textTransform: "uppercase" }}>{step.time}</span>
                        </div>
                        <div style={{ fontFamily: "'Georgia', serif", fontSize: 11, color: "#F0EBE3BB", lineHeight: 1.5, marginBottom: 4 }}>{step.action}</div>
                        <div style={{ fontFamily: "'Georgia', serif", fontSize: 10, color: "#F0EBE344", fontStyle: "italic", lineHeight: 1.5, paddingLeft: 8, borderLeft: `2px solid ${s.color}2A` }}>{step.note}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {/* Serum Tips */}
            <div style={{ marginTop: 24 }}>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#F0EBE322", textTransform: "uppercase", marginBottom: 12 }}>Key Serum Rules</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
                {[
                  { rule: "Always Press, Never Rub", detail: "Rubbing disrupts the Argireline film and disturbs the ceramide liposome structure.", color: ACCENT },
                  { rule: "Damp Skin = Better Delivery", detail: "DMI penetration amplified 30–40% on slightly damp vs. completely dry skin.", color: "#C9A84C" },
                  { rule: "SPF is Part of the Formula", detail: "TXA brightening reverses in UV without SPF. Think of SPF as step 3 of the serum.", color: "#F5C842" },
                  { rule: "PM Dose = Larger", detail: "PDRN and Argireline work harder during sleep. 4–5 drops PM vs 3 AM.", color: "#9B8EC4" },
                  { rule: "No AHA Same Session", detail: "If using with a toner-AHA, apply serum first, allow full absorption, then AHA on alternate nights.", color: "#87CEEB" },
                  { rule: "Consistency Over Intensity", detail: "Daily moderate use outperforms sporadic heavy use. PDRN is cumulative.", color: "#A8D8A8" },
                ].map((r, i) => (
                  <div key={i} style={{ padding: "12px 14px", borderRadius: 10, background: `${r.color}07`, border: `1px solid ${r.color}1A` }}>
                    <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: r.color, textTransform: "uppercase", marginBottom: 4 }}>{r.rule}</div>
                    <div style={{ fontFamily: "'Georgia', serif", fontSize: 10, color: "#F0EBE366", lineHeight: 1.55 }}>{r.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* MATRIX */}
        {activeTab === "matrix" && (
          <div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 26, fontWeight: 300, letterSpacing: 2, marginBottom: 4 }}>Resolving Power Matrix</div>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: "#F0EBE333", textTransform: "uppercase" }}>Serum standalone · Day 30 resolution % per concern</div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {concerns.map((c, i) => (
                <div key={i} style={{ padding: "16px 20px", borderRadius: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                    <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 15, color: "#F0EBE3" }}>{c.name}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 16, fontWeight: 300, color: ACCENT }}>{c.day30}%</div>
                      <Stars count={c.rating} color={ACCENT} />
                    </div>
                  </div>
                  <div style={{ marginBottom: 10 }}><Bar value={c.day30} color={ACCENT} /></div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {c.ingredients.map(ing => (
                      <span key={ing} style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 1, color: "#E8A0C077", padding: "2px 8px", borderRadius: 100, background: "rgba(232,160,192,0.07)", border: "1px solid rgba(232,160,192,0.12)", textTransform: "uppercase" }}>{ing}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Score Card */}
            <div style={{ marginTop: 20, padding: "20px 24px", borderRadius: 14, background: "linear-gradient(135deg, rgba(232,160,192,0.07), rgba(155,142,196,0.04))", border: "1px solid rgba(232,160,192,0.16)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
              <div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#E8A0C066", textTransform: "uppercase", marginBottom: 6 }}>Serum Standalone Score</div>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 40, fontWeight: 300, color: ACCENT, lineHeight: 1 }}>7 / 8</div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: "#F0EBE333", textTransform: "uppercase", marginTop: 4 }}>Concerns at 4–5 Stars</div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: "#FF6B6B88", textTransform: "uppercase", marginTop: 6 }}>⚠ Barrier Repair: 3★ — Add Cream for 5★</div>
              </div>
              <div style={{ maxWidth: 340 }}>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 14, fontStyle: "italic", color: "#F0EBE3AA", lineHeight: 1.7, marginBottom: 10 }}>
                  "The serum delivers 17% of the most powerful actives in skincare. Standalone it is a complete brightening, anti-aging, and bio-repair treatment."
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {["10% Argireline", "5% TXA", "2% PDRN", "DMI Penetration", "Triple Brightening"].map(tag => (
                    <span key={tag} style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 1, color: "#E8A0C088", textTransform: "uppercase", padding: "3px 8px", borderRadius: 100, background: "rgba(232,160,192,0.07)", border: "1px solid rgba(232,160,192,0.14)" }}>{tag}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* CTA */}
            <div style={{ marginTop: 24, textAlign: "center" }}>
              <button onClick={() => navigate('/products')} style={{ padding: "12px 28px", borderRadius: 100, background: "linear-gradient(135deg, #E8A0C0, #D88AAF)", border: "none", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 10 }}>
                <ShoppingBag size={16} color="#080812" />
                <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 3, color: "#080812", textTransform: "uppercase" }}>Shop AURA-GEN Serum</span>
              </button>
            </div>
          </div>
        )}

        {/* Shareable Link Section */}
        <div style={{ marginTop: 28, padding: "18px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(232,160,192,0.12)" }}>
          <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#E8A0C066", textTransform: "uppercase", marginBottom: 10 }}>Share This Protocol</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 200, padding: "10px 14px", borderRadius: 8, background: "rgba(0,0,0,0.25)", border: "1px solid rgba(255,255,255,0.05)", display: "flex", alignItems: "center", gap: 10 }}>
              <Link2 size={14} color={ACCENT} />
              <span style={{ fontFamily: "monospace", fontSize: 11, color: "#F0EBE3AA", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{shareUrl}</span>
            </div>
            <button onClick={copyLink} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 8, background: copied ? "rgba(76,175,80,0.2)" : "rgba(232,160,192,0.12)", border: `1px solid ${copied ? "rgba(76,175,80,0.4)" : "rgba(232,160,192,0.25)"}`, cursor: "pointer" }}>
              {copied ? <Check size={14} color="#4CAF50" /> : <Copy size={14} color={ACCENT} />}
              <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, textTransform: "uppercase", color: copied ? "#4CAF50" : ACCENT }}>{copied ? "Copied!" : "Copy"}</span>
            </button>
            <div style={{ display: "flex", gap: 6 }}>
              {[{ id: "whatsapp", icon: "💬" }, { id: "sms", icon: "📱" }, { id: "email", icon: "📧" }].map(opt => (
                <button key={opt.id} onClick={() => shareTo(opt.id)} style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>{opt.icon}</button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
