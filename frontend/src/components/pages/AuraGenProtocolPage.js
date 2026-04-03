import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { ChevronLeft, ShoppingBag, Share2, Link2, Check, Copy } from "lucide-react";
import { toast } from "sonner";

// AURA-GEN Dual System 30-Day Protocol
// ReRoots Aesthetics Clinical Protocol

const days = [
  {
    range: "Day 1–3",
    label: "ACTIVATION",
    color: "#C9A84C",
    bg: "rgba(201,168,76,0.08)",
    border: "rgba(201,168,76,0.3)",
    issues: [
      { icon: "💧", problem: "Dehydration / Tightness", product: "Serum", mechanism: "Methyl Gluceth-20 + Panthenol + LMW HA flood hydration reservoirs within hours of first application", rating: 85 },
      { icon: "🔴", problem: "Surface Redness / Irritation", product: "Both", mechanism: "TXA anti-inflammatory + Dipotassium Glycyrrhizate + Allantoin immediately calm inflammatory cytokines", rating: 70 },
      { icon: "✨", problem: "Dull, Flat Skin Tone", product: "Serum", mechanism: "PDRN activates A2A receptors within 48hrs — cellular energy surge gives immediate luminosity boost", rating: 75 },
      { icon: "📐", problem: "Surface Roughness", product: "Cream", mechanism: "Mandelic Acid begins dissolving dead cell bonds — skin texture visibly smoother by Day 2", rating: 65 },
    ],
    summary: "Skin feels immediately different. Hydration, smoothness, and calm redness are noticeable within 72 hours."
  },
  {
    range: "Day 4–7",
    label: "SURFACE RESET",
    color: "#E8A0C0",
    bg: "rgba(232,160,192,0.08)",
    border: "rgba(232,160,192,0.3)",
    issues: [
      { icon: "🌑", problem: "Dark Spots / Hyperpigmentation", product: "Both", mechanism: "TXA 5% blocks plasmin pathway. Niacinamide blocks melanosome transfer. Hexylresorcinol kills tyrosinase. Three mechanisms now active simultaneously", rating: 55 },
      { icon: "🔬", problem: "Enlarged Pores", product: "Cream", mechanism: "Zinc PCA + Mandelic + LHA clear sebaceous debris — first visible pore refinement by Day 5–6", rating: 60 },
      { icon: "💊", problem: "Active Breakouts / Acne", product: "Cream", mechanism: "Mandelic Acid kills P. acnes. Succinic Acid regulates sebum. LHA dissolves plugs from inside follicle. Active pustules begin resolving", rating: 70 },
      { icon: "🌊", problem: "Surface Dehydration Lines", product: "Serum", mechanism: "PGA film + LMW HA create a continuous moisture reservoir. Fine dehydration lines visibly plumped", rating: 80 },
    ],
    summary: "First real visible changes. Breakouts calming, pores tightening, fine dehydration lines filling in."
  },
  {
    range: "Day 8–14",
    label: "CELLULAR SHIFT",
    color: "#A8D8A8",
    bg: "rgba(168,216,168,0.08)",
    border: "rgba(168,216,168,0.3)",
    issues: [
      { icon: "🧬", problem: "Fine Lines / Expression Lines", product: "Both", mechanism: "Argireline 10% (Serum) + SNAP-8 + Leuphasyl (Cream) = triple SNARE-blocking stack. Neuro-muscular relaxation cumulative from Day 1 but visible at Week 2", rating: 65 },
      { icon: "🌟", problem: "Uneven Skin Tone / Patchy Pigment", product: "Both", mechanism: "Full AHA cell cycle now active. Mandelic + LHA have completed first full skin renewal cycle. Fresh cells replace pigmented ones", rating: 60 },
      { icon: "🛡️", problem: "Sensitized / Compromised Barrier", product: "Cream", mechanism: "Fatty alcohol + Glyceryl Stearate system has rebuilt intercellular lipid matrix. Skin no longer reactive to previous triggers", rating: 75 },
      { icon: "⚡", problem: "Fatigue / Stressed Skin", product: "Serum", mechanism: "PDRN + Adenosine + GHK-Cu have reset cellular energy production. Skin looks rested, bouncy, more alive", rating: 80 },
    ],
    summary: "Week 2 is the transformation week. Barrier rebuilt, tone evening, expression lines visibly reduced."
  },
  {
    range: "Day 15–21",
    label: "DEEP REPAIR",
    color: "#87CEEB",
    bg: "rgba(135,206,235,0.08)",
    border: "rgba(135,206,235,0.3)",
    issues: [
      { icon: "🏗️", problem: "Loss of Firmness / Elasticity", product: "Cream", mechanism: "Matrixyl 3000 has now completed one collagen synthesis cycle. Fibroblasts producing new Type I, III, IV collagen. Skin measurably firmer", rating: 65 },
      { icon: "🌑", problem: "Stubborn Dark Spots", product: "Both", mechanism: "Two full cell turnover cycles complete. Melanin-heavy cells at surface replaced. Spots 30–50% lighter at Week 3", rating: 70 },
      { icon: "🔄", problem: "Post-Acne Marks (PIH)", product: "Both", mechanism: "TXA anti-inflammatory prevents new PIH. Mandelic + niacinamide clear existing marks. Combination works faster than either alone", rating: 75 },
      { icon: "💎", problem: "Lack of Radiance / Glass Skin", product: "Both", mechanism: "Serum's DMI delivery + Cream's squalane seal = actives working at full depth. Ginseng antioxidant + cellular renewal = visible inner glow", rating: 85 },
    ],
    summary: "Week 3 is the firmness and radiance milestone. Collagen building, spots fading, skin looks structurally different."
  },
  {
    range: "Day 22–30",
    label: "TRANSFORMATION",
    color: "#9B8EC4",
    bg: "rgba(155,142,196,0.08)",
    border: "rgba(155,142,196,0.3)",
    issues: [
      { icon: "🏆", problem: "Moderate Wrinkles / Deep Lines", product: "Both", mechanism: "HPR + Bakuchiol have completed first full retinoid cycle. New collagen visible under deep lines. Wrinkle depth measurably reduced", rating: 75 },
      { icon: "🌈", problem: "Overall Skin Tone", product: "Both", mechanism: "Three full cell cycles complete. Majority of surface melanin cleared. Complexion uniformly brighter by 1–2 shades", rating: 85 },
      { icon: "🧱", problem: "Chronic Barrier Dysfunction", product: "Cream", mechanism: "Full lipid bilayer rebuilt. TEWL reduced. Skin holds moisture independently — less reliant on products to feel comfortable", rating: 90 },
      { icon: "⏳", problem: "Premature Aging / Environmental Damage", product: "Both", mechanism: "Ferulic + SOD + Ginseng antioxidant system has been actively neutralizing free radicals every day. Cumulative protection now measurable", rating: 80 },
    ],
    summary: "Day 30 is the full system result. Comprehensive transformation across all 8 skin concerns — this is the before/after photo moment."
  }
];

const ritual = {
  am: [
    { step: 1, product: "AURA-GEN Serum", action: "3–4 drops, press gently into clean damp skin", time: "60 sec", note: "DMI drives actives deep before cream occludes" },
    { step: 2, product: "Accelerator Rich Cream", action: "Pea-size amount, warm between fingers, press and smooth", time: "30 sec", note: "Seals serum actives in, provides SPF-ready base" },
    { step: 3, product: "SPF 30+", action: "Mandatory — TXA and HPR increase photosensitivity", time: "30 sec", note: "Without SPF, brightening results reverse" },
  ],
  pm: [
    { step: 1, product: "Double Cleanse", action: "Oil cleanser → gentle water cleanser", time: "2 min", note: "Removes SPF and environmental load — critical before actives" },
    { step: 2, product: "AURA-GEN Serum", action: "4–5 drops on slightly damp skin — use more at night", time: "60 sec", note: "Night is peak cell renewal — serum works hardest PM" },
    { step: 3, product: "Accelerator Rich Cream", action: "Generous application — slightly more than AM", time: "30 sec", note: "HPR + Bakuchiol are most active overnight. Seal deep." },
  ]
};

const concerns = [
  { name: "Hyperpigmentation", serum: 5, cream: 5, system: 5 },
  { name: "Anti-Aging / Wrinkles", serum: 5, cream: 5, system: 5 },
  { name: "Barrier Repair", serum: 3, cream: 5, system: 5 },
  { name: "Acne / Sebum Control", serum: 2, cream: 5, system: 5 },
  { name: "Hydration", serum: 4, cream: 4, system: 5 },
  { name: "Cell Regeneration", serum: 5, cream: 5, system: 5 },
  { name: "Soothing / Redness", serum: 4, cream: 4, system: 5 },
  { name: "Antioxidant Protection", serum: 4, cream: 4, system: 5 },
];

function Stars({ count, color = "#C9A84C" }) {
  return (
    <span style={{ display: "inline-flex", gap: 2 }}>
      {[1,2,3,4,5].map(i => (
        <span key={i} style={{ fontSize: 12, color: i <= count ? color : "rgba(255,255,255,0.15)" }}>★</span>
      ))}
    </span>
  );
}

function ProgressBar({ value, color }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.06)", borderRadius: 100, height: 4, overflow: "hidden", flex: 1 }}>
      <div style={{
        width: `${value}%`, height: "100%", borderRadius: 100,
        background: `linear-gradient(90deg, ${color}88, ${color})`,
        transition: "width 1s ease"
      }} />
    </div>
  );
}

export default function AuraGenProtocolPage() {
  const navigate = useNavigate();
  const [activeDay, setActiveDay] = useState(0);
  const [activeTab, setActiveTab] = useState("timeline");
  const [copied, setCopied] = useState(false);
  const [showShareMenu, setShowShareMenu] = useState(false);

  // Set page title on mount
  useEffect(() => {
    document.title = "AURA-GEN 30-Day Combo Protocol | Serum + Cream | ReRoots";
    
    // Update meta description
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', 'Complete 30-day protocol for AURA-GEN Serum + Accelerator Cream combo. Maximum results skincare routine with PDRN, TXA, Argireline, and Triple Peptide.');
    }
    
    return () => {
      document.title = "ReRoots | Premium PDRN Skincare";
    };
  }, []);

  const day = days[activeDay];
  
  // Share URL
  const shareUrl = `${window.location.origin}/aura-gen-protocol`;
  const shareTitle = "AURA-GEN 30-Day Transformation Protocol";
  const shareText = "Check out this clinical skincare protocol from ReRoots — addresses all 8 major skin concerns in 30 days.";

  // Copy link to clipboard
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Link copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback for older browsers
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
        await navigator.share({
          title: shareTitle,
          text: shareText,
          url: shareUrl,
        });
      } catch (err) {
        if (err.name !== 'AbortError') {
          copyLink(); // Fallback to copy
        }
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
    <div style={{
      minHeight: "100vh",
      background: "#080810",
      color: "#F0EBE3",
      fontFamily: "'Georgia', 'Times New Roman', serif",
      padding: "0",
      paddingTop: "70px", // Account for fixed navbar
      overflowX: "hidden"
    }}>
      {/* SEO Meta Tags */}
      <Helmet>
        <title>AURA-GEN 30-Day Combo Protocol | Serum + Cream | ReRoots</title>
        <meta name="description" content="Complete 30-day protocol for AURA-GEN Serum + Accelerator Cream combo. Day-by-day transformation guide with PDRN, TXA, Argireline, Mandelic, and Triple Peptide. Maximum results skincare routine." />
        <meta name="keywords" content="AURA-GEN protocol, 30 day skincare routine, PDRN serum cream combo, Tranexamic Acid, Argireline, Mandelic acid, anti-aging protocol, ReRoots skincare Canada" />
        <link rel="canonical" href="https://reroots.ca/aura-gen-protocol" />
        
        {/* Open Graph */}
        <meta property="og:title" content="AURA-GEN 30-Day Combo Protocol - Serum + Cream" />
        <meta property="og:description" content="The complete dual-system protocol for maximum skin transformation. PDRN Serum + Accelerator Cream working in synergy." />
        <meta property="og:url" content="https://reroots.ca/aura-gen-protocol" />
        <meta property="og:type" content="article" />
        <meta property="og:image" content="https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/a4671ebm_1767158945864.jpg" />
        
        {/* Twitter */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="AURA-GEN 30-Day Combo Protocol" />
        <meta name="twitter:description" content="Complete day-by-day transformation guide for AURA-GEN Serum + Accelerator Cream combo." />
        
        {/* Schema.org Structured Data */}
        <script type="application/ld+json">{`
          {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": "AURA-GEN 30-Day Combo Protocol",
            "description": "Complete 30-day protocol combining AURA-GEN Serum and Accelerator Cream for maximum skin transformation",
            "totalTime": "P30D",
            "tool": [
              {"@type": "HowToTool", "name": "AURA-GEN Serum"},
              {"@type": "HowToTool", "name": "AURA-GEN Accelerator Cream"},
              {"@type": "HowToTool", "name": "SPF 30+ Sunscreen"}
            ],
            "step": [
              {"@type": "HowToStep", "name": "Day 1-3: Activation", "text": "Serum floods hydration. Cream begins texture improvement. Both calm inflammation."},
              {"@type": "HowToStep", "name": "Day 4-7: Foundation", "text": "PDRN DNA repair visible. Barrier rebuilding. Pores clearing."},
              {"@type": "HowToStep", "name": "Day 8-14: Synergy Phase", "text": "Dual-system synergy peaks. Collagen synthesis from both products."},
              {"@type": "HowToStep", "name": "Day 15-21: Deep Results", "text": "Visible transformation. Lines softening. Spots fading."},
              {"@type": "HowToStep", "name": "Day 22-30: Full Transformation", "text": "Complete skin renewal. Before/after photo moment."}
            ],
            "supply": [
              {"@type": "HowToSupply", "name": "PDRN 2% (Salmon DNA)"},
              {"@type": "HowToSupply", "name": "Tranexamic Acid 5%"},
              {"@type": "HowToSupply", "name": "Argireline 10%"},
              {"@type": "HowToSupply", "name": "Mandelic Acid 5%"},
              {"@type": "HowToSupply", "name": "HPR + Bakuchiol"},
              {"@type": "HowToSupply", "name": "Matrixyl 3000"}
            ]
          }
        `}</script>
      </Helmet>
      
      {/* Styles */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Josefin+Sans:wght@200;300;400&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: #0a0a14; } ::-webkit-scrollbar-thumb { background: #C9A84C44; border-radius: 100px; }
        .tab-btn { cursor: pointer; transition: all 0.3s; border: none; background: none; }
        .tab-btn:hover { opacity: 0.8; }
        .day-btn { cursor: pointer; transition: all 0.3s; border: none; }
        .day-btn:hover { transform: translateY(-2px); }
        .issue-card { transition: all 0.3s; }
        .issue-card:hover { transform: translateX(4px); }
      `}</style>

      {/* HEADER */}
      <div style={{
        background: "linear-gradient(180deg, #0D0D1E 0%, #080810 100%)",
        borderBottom: "1px solid rgba(201,168,76,0.15)",
        padding: "24px 24px 24px",
        position: "relative",
        overflow: "hidden"
      }}>
        {/* Top Bar - Back & Share */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <button 
            onClick={() => navigate(-1)}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              background: "none", border: "none", cursor: "pointer",
              color: "#F0EBE388", fontSize: 12
            }}
          >
            <ChevronLeft size={16} /> Back to Shop
          </button>
          
          {/* Share Button */}
          <div style={{ position: "relative" }}>
            <button
              onClick={handleNativeShare}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 14px", borderRadius: 100,
                background: "rgba(201,168,76,0.1)",
                border: "1px solid rgba(201,168,76,0.3)",
                cursor: "pointer", color: "#C9A84C"
              }}
            >
              <Share2 size={14} />
              <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, textTransform: "uppercase" }}>Share</span>
            </button>
            
            {/* Share Menu Dropdown */}
            {showShareMenu && (
              <div style={{
                position: "absolute", top: "calc(100% + 8px)", right: 0,
                background: "#1a1a2e", borderRadius: 12,
                border: "1px solid rgba(201,168,76,0.2)",
                padding: "8px", minWidth: 180, zIndex: 100,
                boxShadow: "0 8px 32px rgba(0,0,0,0.4)"
              }}>
                {/* Copy Link */}
                <button
                  onClick={copyLink}
                  style={{
                    display: "flex", alignItems: "center", gap: 10, width: "100%",
                    padding: "10px 12px", borderRadius: 8, border: "none",
                    background: copied ? "rgba(76,175,80,0.15)" : "transparent",
                    cursor: "pointer", color: copied ? "#4CAF50" : "#F0EBE3",
                    transition: "all 0.2s"
                  }}
                >
                  {copied ? <Check size={16} /> : <Link2 size={16} />}
                  <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 1 }}>
                    {copied ? "Copied!" : "Copy Link"}
                  </span>
                </button>
                
                <div style={{ height: 1, background: "rgba(255,255,255,0.06)", margin: "4px 0" }} />
                
                {/* Share Options */}
                {[
                  { id: "whatsapp", label: "WhatsApp", icon: "💬" },
                  { id: "sms", label: "Text Message", icon: "📱" },
                  { id: "email", label: "Email", icon: "📧" },
                  { id: "twitter", label: "Twitter/X", icon: "𝕏" },
                  { id: "facebook", label: "Facebook", icon: "📘" },
                ].map(opt => (
                  <button
                    key={opt.id}
                    onClick={() => shareTo(opt.id)}
                    style={{
                      display: "flex", alignItems: "center", gap: 10, width: "100%",
                      padding: "10px 12px", borderRadius: 8, border: "none",
                      background: "transparent", cursor: "pointer", color: "#F0EBE3",
                      transition: "all 0.2s"
                    }}
                    onMouseEnter={(e) => e.target.style.background = "rgba(201,168,76,0.1)"}
                    onMouseLeave={(e) => e.target.style.background = "transparent"}
                  >
                    <span style={{ fontSize: 14 }}>{opt.icon}</span>
                    <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 1 }}>
                      {opt.label}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div style={{
          position: "absolute", top: -60, right: -60, width: 300, height: 300,
          background: "radial-gradient(circle, rgba(201,168,76,0.08) 0%, transparent 70%)",
          pointerEvents: "none"
        }} />
        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 6, color: "#C9A84C88", marginBottom: 8, textTransform: "uppercase" }}>
          ReRoots Aesthetics · Clinical Protocol
        </div>
        <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 32, fontWeight: 300, letterSpacing: 2, lineHeight: 1.1, marginBottom: 6 }}>
          AURA-GEN
          <span style={{ color: "#C9A84C", fontStyle: "italic" }}> Dual System</span>
        </div>
        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 11, letterSpacing: 4, color: "#F0EBE388", textTransform: "uppercase" }}>
          30-Day Transformation Protocol · Combination Strategy
        </div>

        {/* Product Pills */}
        <div style={{ display: "flex", gap: 12, marginTop: 20, flexWrap: "wrap" }}>
          {[
            { name: "Serum", sub: "Bio-Regenerator", color: "#E8A0C0" },
            { name: "Accelerator", sub: "Rich Cream", color: "#C9A84C" },
          ].map(p => (
            <div key={p.name} style={{
              padding: "8px 16px", borderRadius: 100,
              border: `1px solid ${p.color}44`,
              background: `${p.color}10`,
              display: "flex", alignItems: "center", gap: 8
            }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: p.color }} />
              <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 3, color: p.color, textTransform: "uppercase" }}>
                {p.name}
              </span>
              <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 1, color: "#F0EBE355" }}>
                {p.sub}
              </span>
            </div>
          ))}
          <div style={{
            padding: "8px 16px", borderRadius: 100,
            border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(255,255,255,0.03)",
            display: "flex", alignItems: "center", gap: 8
          }}>
            <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 3, color: "#4CAF50", textTransform: "uppercase" }}>
              ✓ All 8 Concerns
            </span>
            <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, color: "#F0EBE355" }}>5★ System Rating</span>
          </div>
        </div>
      </div>

      {/* TABS */}
      <div style={{
        display: "flex", gap: 0,
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        padding: "0 24px",
        background: "#0A0A16",
        overflowX: "auto"
      }}>
        {[
          { id: "timeline", label: "30-Day Timeline" },
          { id: "ritual", label: "AM / PM Ritual" },
          { id: "matrix", label: "Resolving Matrix" },
        ].map(t => (
          <button
            key={t.id}
            className="tab-btn"
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: "14px 20px",
              fontFamily: "'Josefin Sans', sans-serif",
              fontSize: 10, letterSpacing: 3,
              textTransform: "uppercase",
              color: activeTab === t.id ? "#C9A84C" : "#F0EBE344",
              borderBottom: activeTab === t.id ? "2px solid #C9A84C" : "2px solid transparent",
              marginBottom: -1,
              whiteSpace: "nowrap"
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding: "24px", maxWidth: 1100 }}>

        {/* ── TIMELINE TAB ── */}
        {activeTab === "timeline" && (
          <div>
            {/* Day Selector */}
            <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
              {days.map((d, i) => (
                <button
                  key={i}
                  className="day-btn"
                  onClick={() => setActiveDay(i)}
                  style={{
                    padding: "10px 16px",
                    borderRadius: 100,
                    border: `1px solid ${activeDay === i ? d.color : "rgba(255,255,255,0.08)"}`,
                    background: activeDay === i ? `${d.color}18` : "rgba(255,255,255,0.02)",
                    cursor: "pointer"
                  }}
                >
                  <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: activeDay === i ? d.color : "#F0EBE355", textTransform: "uppercase", marginBottom: 2 }}>
                    {d.range}
                  </div>
                  <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: activeDay === i ? `${d.color}AA` : "#F0EBE322", textTransform: "uppercase" }}>
                    {d.label}
                  </div>
                </button>
              ))}
            </div>

            {/* Phase Header */}
            <div style={{
              padding: "16px 20px",
              borderRadius: 12,
              border: `1px solid ${day.color}44`,
              background: day.bg,
              marginBottom: 20
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 4, color: `${day.color}99`, textTransform: "uppercase", marginBottom: 4 }}>
                    Phase {activeDay + 1} · {day.range}
                  </div>
                  <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 24, fontWeight: 300, color: day.color, letterSpacing: 2 }}>
                    {day.label}
                  </div>
                </div>
                <div style={{
                  padding: "10px 16px",
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.3)",
                  border: `1px solid ${day.color}22`,
                  maxWidth: 320
                }}>
                  <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: `${day.color}77`, textTransform: "uppercase", marginBottom: 4 }}>
                    Phase Summary
                  </div>
                  <div style={{ fontFamily: "'Georgia', serif", fontSize: 12, color: "#F0EBE3CC", lineHeight: 1.5 }}>
                    {day.summary}
                  </div>
                </div>
              </div>
            </div>

            {/* Issues Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
              {day.issues.map((issue, i) => (
                <div key={i} className="issue-card" style={{
                  padding: "16px 20px",
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.025)",
                  border: `1px solid ${day.border}`,
                }}>
                  {/* Header */}
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 20 }}>{issue.icon}</span>
                      <div>
                        <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 15, fontWeight: 400, color: "#F0EBE3", marginBottom: 2 }}>
                          {issue.problem}
                        </div>
                        <div style={{
                          display: "inline-block",
                          padding: "2px 8px", borderRadius: 100,
                          background: issue.product === "Both" ? "rgba(201,168,76,0.12)" : issue.product === "Serum" ? "rgba(232,160,192,0.12)" : "rgba(100,200,100,0.12)",
                          border: `1px solid ${issue.product === "Both" ? "rgba(201,168,76,0.25)" : issue.product === "Serum" ? "rgba(232,160,192,0.25)" : "rgba(100,200,100,0.25)"}`,
                        }}>
                          <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, textTransform: "uppercase",
                            color: issue.product === "Both" ? "#C9A84C" : issue.product === "Serum" ? "#E8A0C0" : "#90EE90"
                          }}>
                            {issue.product === "Both" ? "Serum + Cream" : issue.product === "Serum" ? "Serum" : "Cream"}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 18, fontWeight: 300, color: day.color }}>
                        {issue.rating}%
                      </div>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: "#F0EBE333", textTransform: "uppercase" }}>
                        Resolved
                      </div>
                    </div>
                  </div>

                  {/* Progress */}
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                    <ProgressBar value={issue.rating} color={day.color} />
                  </div>

                  {/* Mechanism */}
                  <div style={{ fontFamily: "'Georgia', serif", fontSize: 11, color: "#F0EBE377", lineHeight: 1.6 }}>
                    {issue.mechanism}
                  </div>
                </div>
              ))}
            </div>

            {/* Timeline Track */}
            <div style={{ marginTop: 28, padding: "20px 0" }}>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 4, color: "#F0EBE333", textTransform: "uppercase", marginBottom: 12 }}>
                Full 30-Day Resolution Track
              </div>
              <div style={{ position: "relative", paddingBottom: 8 }}>
                <div style={{ position: "absolute", top: 10, left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.06)" }} />
                <div style={{ display: "flex", justifyContent: "space-between", position: "relative" }}>
                  {days.map((d, i) => (
                    <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, cursor: "pointer" }}
                      onClick={() => setActiveDay(i)}>
                      <div style={{
                        width: 18, height: 18, borderRadius: "50%",
                        background: i <= activeDay ? d.color : "rgba(255,255,255,0.06)",
                        border: `2px solid ${i === activeDay ? d.color : "transparent"}`,
                        boxShadow: i === activeDay ? `0 0 12px ${d.color}66` : "none",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        transition: "all 0.3s", zIndex: 1
                      }}>
                        {i < activeDay && <span style={{ fontSize: 8, color: "#080810" }}>✓</span>}
                      </div>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 1, color: i === activeDay ? d.color : "#F0EBE333", textTransform: "uppercase", textAlign: "center" }}>
                        {d.range}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── RITUAL TAB ── */}
        {activeTab === "ritual" && (
          <div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 26, fontWeight: 300, letterSpacing: 2, color: "#F0EBE3", marginBottom: 4 }}>
                The Daily Ritual
              </div>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 3, color: "#F0EBE344", textTransform: "uppercase" }}>
                Application order is non-negotiable — sequence drives results
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20, marginTop: 24 }}>
              {[
                { key: "am", label: "Morning", sub: "AM Protocol", icon: "☀️", color: "#F5C842", steps: ritual.am },
                { key: "pm", label: "Evening", sub: "PM Protocol", icon: "🌙", color: "#9B8EC4", steps: ritual.pm },
              ].map(session => (
                <div key={session.key} style={{
                  borderRadius: 16,
                  border: `1px solid ${session.color}22`,
                  background: `linear-gradient(160deg, ${session.color}08, rgba(255,255,255,0.01))`,
                  overflow: "hidden"
                }}>
                  {/* Session Header */}
                  <div style={{
                    padding: "16px 20px",
                    borderBottom: `1px solid ${session.color}15`,
                    display: "flex", alignItems: "center", gap: 10
                  }}>
                    <span style={{ fontSize: 22 }}>{session.icon}</span>
                    <div>
                      <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 20, fontWeight: 300, color: session.color }}>
                        {session.label}
                      </div>
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: `${session.color}88`, textTransform: "uppercase" }}>
                        {session.sub}
                      </div>
                    </div>
                  </div>

                  {/* Steps */}
                  <div style={{ padding: "0" }}>
                    {session.steps.map((step, i) => (
                      <div key={i} style={{
                        padding: "14px 20px",
                        borderBottom: i < session.steps.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                        display: "flex", gap: 12, alignItems: "flex-start"
                      }}>
                        {/* Step Number */}
                        <div style={{
                          width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
                          background: `${session.color}18`,
                          border: `1px solid ${session.color}33`,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontFamily: "'Cormorant Garamond', serif", fontSize: 13, color: session.color
                        }}>
                          {step.step}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                            <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 2, color: session.color, textTransform: "uppercase" }}>
                              {step.product}
                            </div>
                            <div style={{
                              fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 1,
                              color: "#F0EBE333", background: "rgba(255,255,255,0.03)",
                              padding: "2px 8px", borderRadius: 100, textTransform: "uppercase"
                            }}>
                              {step.time}
                            </div>
                          </div>
                          <div style={{ fontFamily: "'Georgia', serif", fontSize: 12, color: "#F0EBE3CC", marginBottom: 6, lineHeight: 1.5 }}>
                            {step.action}
                          </div>
                          <div style={{
                            fontFamily: "'Georgia', serif", fontSize: 11, color: "#F0EBE355",
                            fontStyle: "italic", lineHeight: 1.5,
                            paddingLeft: 10, borderLeft: `2px solid ${session.color}33`
                          }}>
                            {step.note}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Critical Rules */}
            <div style={{ marginTop: 28 }}>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 4, color: "#F0EBE333", textTransform: "uppercase", marginBottom: 12 }}>
                Protocol Rules — Non-Negotiable
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
                {[
                  { rule: "Serum Always First", detail: "DMI in serum opens channels. Cream actives penetrate deeper.", color: "#E8A0C0" },
                  { rule: "Wait 60 Seconds", detail: "Allow serum to begin absorbing before applying cream.", color: "#C9A84C" },
                  { rule: "SPF Every Morning", detail: "TXA, HPR and Mandelic increase UV sensitivity.", color: "#F5C842" },
                  { rule: "Weeks 1–2: PM Only", detail: "For first-time HPR users, introduce cream PM only first.", color: "#9B8EC4" },
                  { rule: "No Vitamin C Same Time", detail: "TXA and Vitamin C compete. Use on alternate days.", color: "#87CEEB" },
                  { rule: "Patch Test First", detail: "Inner forearm, wait 24hrs before full face.", color: "#A8D8A8" },
                ].map((r, i) => (
                  <div key={i} style={{
                    padding: "14px 16px",
                    borderRadius: 10,
                    background: `${r.color}08`,
                    border: `1px solid ${r.color}22`
                  }}>
                    <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, color: r.color, textTransform: "uppercase", marginBottom: 4 }}>
                      {r.rule}
                    </div>
                    <div style={{ fontFamily: "'Georgia', serif", fontSize: 11, color: "#F0EBE377", lineHeight: 1.5 }}>
                      {r.detail}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── MATRIX TAB ── */}
        {activeTab === "matrix" && (
          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 26, fontWeight: 300, letterSpacing: 2, color: "#F0EBE3", marginBottom: 4 }}>
                Resolving Power Matrix
              </div>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 3, color: "#F0EBE344", textTransform: "uppercase" }}>
                Individual vs. combined system rating across all 8 concerns
              </div>
            </div>

            {/* Legend */}
            <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
              {[
                { label: "Serum Alone", color: "#E8A0C0" },
                { label: "Cream Alone", color: "#C9A84C" },
                { label: "Combined System", color: "#4CAF50" },
              ].map(l => (
                <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 20, height: 3, borderRadius: 100, background: l.color }} />
                  <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, color: "#F0EBE377", textTransform: "uppercase" }}>
                    {l.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Concern Rows */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {concerns.map((c, i) => (
                <div key={i} style={{
                  padding: "16px 20px",
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(255,255,255,0.06)"
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                    <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 16, fontWeight: 400 }}>
                      {c.name}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Stars count={c.system} color="#4CAF50" />
                      <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: "#4CAF50AA", textTransform: "uppercase" }}>
                        Combined
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {[
                      { label: "Serum", stars: c.serum, color: "#E8A0C0" },
                      { label: "Cream", stars: c.cream, color: "#C9A84C" },
                      { label: "System", stars: c.system, color: "#4CAF50" },
                    ].map(row => (
                      <div key={row.label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: `${row.color}AA`, textTransform: "uppercase", width: 50, flexShrink: 0 }}>
                          {row.label}
                        </div>
                        <ProgressBar value={row.stars * 20} color={row.color} />
                        <Stars count={row.stars} color={row.color} />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* System Score */}
            <div style={{
              marginTop: 24,
              padding: "24px",
              borderRadius: 16,
              background: "linear-gradient(135deg, rgba(201,168,76,0.08), rgba(76,175,80,0.05))",
              border: "1px solid rgba(201,168,76,0.2)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
              flexWrap: "wrap", gap: 16
            }}>
              <div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 4, color: "#C9A84C88", textTransform: "uppercase", marginBottom: 6 }}>
                  Combined System Score
                </div>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 42, fontWeight: 300, color: "#C9A84C", lineHeight: 1 }}>
                  8 / 8
                </div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 2, color: "#F0EBE344", textTransform: "uppercase", marginTop: 4 }}>
                  Concerns at 5 Stars
                </div>
              </div>
              <div style={{ maxWidth: 360 }}>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 15, fontStyle: "italic", color: "#F0EBE3BB", lineHeight: 1.6, marginBottom: 10 }}>
                  "The serum delivers. The cream seals. Together, they address every major skin concern at clinical grade — no gaps remain."
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {["17% Active Core", "Triple Peptide", "Dual Retinoid", "5-Mechanism Brightening", "Full Barrier Repair"].map(tag => (
                    <span key={tag} style={{
                      fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 1,
                      color: "#C9A84CAA", textTransform: "uppercase",
                      padding: "3px 8px", borderRadius: 100,
                      background: "rgba(201,168,76,0.08)",
                      border: "1px solid rgba(201,168,76,0.15)"
                    }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* CTA */}
            <div style={{ marginTop: 28, textAlign: "center" }}>
              <button
                onClick={() => navigate('/products')}
                style={{
                  padding: "14px 32px",
                  borderRadius: 100,
                  background: "linear-gradient(135deg, #C9A84C, #D4AF37)",
                  border: "none",
                  cursor: "pointer",
                  display: "inline-flex", alignItems: "center", gap: 10
                }}
              >
                <ShoppingBag size={18} color="#080810" />
                <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 11, letterSpacing: 3, color: "#080810", textTransform: "uppercase" }}>
                  Shop AURA-GEN Combo
                </span>
              </button>
            </div>
          </div>
        )}

        {/* Shareable Link Section - Always visible */}
        <div style={{
          marginTop: 32,
          padding: "20px 24px",
          borderRadius: 16,
          background: "rgba(255,255,255,0.02)",
          border: "1px solid rgba(201,168,76,0.15)"
        }}>
          <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 4, color: "#C9A84C88", textTransform: "uppercase", marginBottom: 10 }}>
            Share This Protocol
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            {/* URL Display */}
            <div style={{
              flex: 1, minWidth: 200,
              padding: "12px 16px",
              borderRadius: 8,
              background: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(255,255,255,0.06)",
              display: "flex", alignItems: "center", gap: 10
            }}>
              <Link2 size={14} color="#C9A84C" />
              <span style={{ 
                fontFamily: "monospace", fontSize: 12, color: "#F0EBE3AA",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
              }}>
                {shareUrl}
              </span>
            </div>
            
            {/* Copy Button */}
            <button
              onClick={copyLink}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "12px 20px", borderRadius: 8,
                background: copied ? "rgba(76,175,80,0.2)" : "rgba(201,168,76,0.15)",
                border: `1px solid ${copied ? "rgba(76,175,80,0.4)" : "rgba(201,168,76,0.3)"}`,
                cursor: "pointer",
                transition: "all 0.2s"
              }}
            >
              {copied ? <Check size={16} color="#4CAF50" /> : <Copy size={16} color="#C9A84C" />}
              <span style={{ 
                fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 2, 
                textTransform: "uppercase", color: copied ? "#4CAF50" : "#C9A84C" 
              }}>
                {copied ? "Copied!" : "Copy Link"}
              </span>
            </button>
            
            {/* Quick Share Buttons */}
            <div style={{ display: "flex", gap: 6 }}>
              {[
                { id: "whatsapp", icon: "💬", label: "WhatsApp" },
                { id: "sms", icon: "📱", label: "SMS" },
                { id: "email", icon: "📧", label: "Email" },
              ].map(opt => (
                <button
                  key={opt.id}
                  onClick={() => shareTo(opt.id)}
                  title={opt.label}
                  style={{
                    width: 40, height: 40,
                    borderRadius: 8,
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    cursor: "pointer",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 16,
                    transition: "all 0.2s"
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = "rgba(201,168,76,0.15)";
                    e.target.style.borderColor = "rgba(201,168,76,0.3)";
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = "rgba(255,255,255,0.03)";
                    e.target.style.borderColor = "rgba(255,255,255,0.08)";
                  }}
                >
                  {opt.icon}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
