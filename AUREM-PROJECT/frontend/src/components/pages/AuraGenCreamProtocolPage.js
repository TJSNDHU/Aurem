import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { ChevronLeft, ShoppingBag, Share2, Link2, Check, Copy } from "lucide-react";
import { toast } from "sonner";

// AURA-GEN Accelerator Rich Cream 30-Day Solo Protocol
// ReRoots Aesthetics · Mandelic + Triple Peptide + HPR + Bakuchiol

const days = [
  {
    range: "Day 1–3", label: "SURFACE ACTIVATION", color: "#C9A84C",
    bg: "rgba(201,168,76,0.08)", border: "rgba(201,168,76,0.3)",
    issues: [
      { icon: "📐", problem: "Surface Roughness / Texture", rating: 72, mechanism: "Mandelic Acid begins dissolving corneocyte bonds immediately. Skin smoother to the touch by Day 2. LHA penetrates sebaceous follicle — pore-clearing starts Day 1." },
      { icon: "🔴", problem: "Active Redness / Reactivity", rating: 68, mechanism: "Dipotassium Glycyrrhizate calms inflammatory cascade within hours. Bisabolol reduces skin reactivity. Allantoin begins accelerating surface recovery." },
      { icon: "🏗️", problem: "Immediate Dryness / Tightness", rating: 80, mechanism: "Full emulsion system delivers Glycerin + Squalane + Shea immediately. Rich cream provides instant occlusion — moisture locked from first application. No tightness within 20 minutes." },
      { icon: "💊", problem: "Active / Inflamed Breakouts", rating: 60, mechanism: "Mandelic Acid is bacteriostatic against P. acnes from Day 1. Zinc PCA begins reducing sebaceous inflammation. Active lesions start calming within 48 hours." },
    ],
    summary: "Immediate smoothness, comfort and redness reduction. Cream sets the foundation — barrier, texture, and acne response all start Day 1."
  },
  {
    range: "Day 4–7", label: "BARRIER BUILD", color: "#87CEEB",
    bg: "rgba(135,206,235,0.08)", border: "rgba(135,206,235,0.3)",
    issues: [
      { icon: "🛡️", problem: "Compromised / Leaky Barrier", rating: 70, mechanism: "Cetearyl Alcohol + Cetyl Alcohol + Glyceryl Stearate = full intercellular lipid replacement. By Day 5 the lipid matrix is structurally reinforced. TEWL measurably reduced." },
      { icon: "🔬", problem: "Enlarged / Congested Pores", rating: 65, mechanism: "Mandelic + LHA combination has now completed first deep pore-clearing cycle. Zinc PCA regulating sebum production. Pores visibly tighter and cleaner by Day 6." },
      { icon: "💊", problem: "Cystic / Hormonal Breakouts", rating: 58, mechanism: "Zinc PCA specifically targets androgen-driven sebum excess. Succinic Acid creates antibacterial microenvironment. Results slower than surface acne — first response visible Day 5–7." },
      { icon: "🌑", problem: "Early Pigmentation / PIH", rating: 48, mechanism: "Mandelic Acid beginning first full AHA cell cycle. Niacinamide 5% blocking melanosome transfer. Hexylresorcinol directly inhibiting tyrosinase. Three pathways active." },
    ],
    summary: "Barrier framework rebuilt. Pores clearing. Acne responding. Brightening mechanisms all engaged."
  },
  {
    range: "Day 8–14", label: "COLLAGEN ONSET", color: "#A8D8A8",
    bg: "rgba(168,216,168,0.08)", border: "rgba(168,216,168,0.3)",
    issues: [
      { icon: "🏗️", problem: "Loss of Firmness / Sagging Skin", rating: 60, mechanism: "Matrixyl 3000 has signalled fibroblasts to begin collagen synthesis. Type I, III and IV collagen production measurably elevated. First firmness improvement felt — not yet visible — at Day 10–12." },
      { icon: "🧬", problem: "Expression Lines / Dynamic Wrinkles", rating: 58, mechanism: "SNAP-8 + Leuphasyl dual SNARE inhibition cumulative effect reaching threshold. Muscle micro-contractions relaxing. Forehead and periorbital lines softer by Day 12–14." },
      { icon: "🌟", problem: "Uneven Tone / Post-Resurfacing Clarity", rating: 65, mechanism: "First full AHA cycle complete. Mandelic + LHA have shed one full layer of melanin-heavy cells. Niacinamide + Hexylresorcinol blocking new pigment. Skin measurably more even." },
      { icon: "🛡️", problem: "Chronic Sensitivity / Reactive Skin", rating: 78, mechanism: "Full intercellular lipid matrix rebuilt. Skin no longer reactive to its previous triggers. Rosacea-prone and reactive skin types notice dramatically reduced reactivity at Week 2." },
    ],
    summary: "Collagen synthesis launched. Barrier fully sealed. First tone and line improvements measurable."
  },
  {
    range: "Day 15–21", label: "RETINOID PEAK", color: "#E8A0C0",
    bg: "rgba(232,160,192,0.08)", border: "rgba(232,160,192,0.3)",
    issues: [
      { icon: "🔄", problem: "Slow Cell Turnover / Thick Dead Skin", rating: 80, mechanism: "HPR + Bakuchiol dual retinoid system has now completed one full 28-day analogue of the retinoid cycle. Cell turnover dramatically accelerated. Skin texture completely transformed at Week 3." },
      { icon: "🏗️", problem: "Moderate Wrinkles / Deep Lines", rating: 68, mechanism: "New collagen scaffolding now visible under fine-to-moderate lines. HPR has upregulated collagen gene expression. Lines measurably shallower compared to Day 1 photography." },
      { icon: "🌑", problem: "Stubborn Dark Spots / Melasma", rating: 72, mechanism: "Two complete AHA cell cycles done. Melanin-heavy cells replaced twice. Hexylresorcinol + Niacinamide + Mandelic still suppressing pigment regeneration. Spots 40–60% lighter." },
      { icon: "⚡", problem: "Dull / Tired Skin Appearance", rating: 82, mechanism: "Adenosine cellular energy boost + GHK-Cu gene activation + Ferulic Acid antioxidant = skin that produces energy like younger tissue. Radiance and vitality fully visible." },
    ],
    summary: "Week 3 — retinoid cycle peak. Cell turnover transformed. Collagen building visibly. Spots dramatically lighter."
  },
  {
    range: "Day 22–30", label: "TRANSFORMATION", color: "#9B8EC4",
    bg: "rgba(155,142,196,0.08)", border: "rgba(155,142,196,0.3)",
    issues: [
      { icon: "🏆", problem: "Moderate–Deep Wrinkles", rating: 78, mechanism: "HPR + Bakuchiol + Matrixyl triple retinoid-peptide collagen stack at full cumulative effect. Wrinkle depth reduced by estimated 20–35% at Day 30 vs Day 1 baseline." },
      { icon: "🌈", problem: "Overall Complexion", rating: 85, mechanism: "Three full AHA cell cycles complete. Six brightening mechanisms active simultaneously. Complexion uniformly 1–2 shades brighter. All three pigment pathways continuously suppressed." },
      { icon: "🧱", problem: "Chronic Barrier Dysfunction / TEWL", rating: 90, mechanism: "Complete lipid bilayer reconstruction achieved. Skin now holds moisture independently. Patients who previously needed moisturiser every 4 hours now comfortable for 12+ hours." },
      { icon: "🔬", problem: "Acne / Oily Skin / Congestion", rating: 85, mechanism: "Mandelic + LHA + Succinic + Zinc PCA + Niacinamide = most comprehensive OTC anti-acne system in a single cream. Sebum, bacteria, congestion and inflammation all suppressed." },
    ],
    summary: "Day 30 full result. Barrier reconstructed, collagen building, complexion transformed, acne suppressed. This is the before/after photo moment."
  }
];

const ritual = {
  am: [
    { step: 1, action: "Gentle pH-balanced cleanser", time: "60 sec", note: "Mandelic Acid is pH-sensitive. Cleanse with a non-alkaline formula to preserve the acid mantle" },
    { step: 2, action: "Pea-size amount, warm between palms, press and smooth", time: "45 sec", note: "Warm cream before applying — activates the emulsifier for better skin contact and spread" },
    { step: 3, action: "SPF 30+ minimum — mandatory", time: "30 sec", note: "Mandelic AHA and HPR both increase UV sensitivity. SPF is not optional with this formula" },
  ],
  pm: [
    { step: 1, action: "Double cleanse — oil then water phase", time: "2 min", note: "Oil cleanser first removes SPF and sebum. Water cleanser after resets pH for cream actives" },
    { step: 2, action: "Slightly more than AM application", time: "45 sec", note: "HPR + Bakuchiol work hardest overnight. Apply more generously at PM — the retinoid cycle is nocturnal" },
    { step: 3, action: "Skip additional moisturiser", time: "—", note: "This cream is the final step. It is the moisturiser. No additional products needed on top." },
  ]
};

const concerns = [
  { name: "Acne / Sebum / Pore Control", rating: 5, day30: 85, ingredients: ["Mandelic 5%", "LHA", "Succinic Acid", "Zinc PCA", "Niacinamide"] },
  { name: "Hyperpigmentation / Dark Spots", rating: 5, day30: 85, ingredients: ["Mandelic 5%", "Niacinamide 5%", "Hexylresorcinol", "LHA"] },
  { name: "Anti-Aging / Wrinkles / Firmness", rating: 5, day30: 78, ingredients: ["Matrixyl 3000", "SNAP-8", "Leuphasyl", "HPR 2%", "Bakuchiol"] },
  { name: "Barrier Repair / Reconstruction", rating: 5, day30: 90, ingredients: ["Cetearyl Alcohol", "Glyceryl Stearate", "Squalane", "Shea Butter"] },
  { name: "Cell Regeneration / Renewal", rating: 5, day30: 80, ingredients: ["HPR 2%", "Bakuchiol", "GHK-Cu", "Adenosine"] },
  { name: "Soothing / Redness / Sensitivity", rating: 4, day30: 76, ingredients: ["DPK Glycyrrhizate", "Bisabolol", "Allantoin", "Shea Butter"] },
  { name: "Antioxidant / Environmental", rating: 4, day30: 78, ingredients: ["Ferulic Acid", "Bakuchiol", "GHK-Cu", "Bisabolol"] },
  { name: "Hydration / Moisture Retention", rating: 4, day30: 82, ingredients: ["Glycerin", "Squalane", "Shea Butter", "LMW HA"] },
];

function Stars({ count, color = "#C9A84C" }) {
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
      <div style={{ width: `${value}%`, height: "100%", borderRadius: 100, background: `linear-gradient(90deg, ${color}55, ${color})`, transition: "width 1s ease" }} />
    </div>
  );
}

export default function AuraGenCreamProtocolPage() {
  const navigate = useNavigate();
  const [activeDay, setActiveDay] = useState(0);
  const [activeTab, setActiveTab] = useState("timeline");
  const [copied, setCopied] = useState(false);
  const [showShareMenu, setShowShareMenu] = useState(false);
  
  // Set page title on mount
  useEffect(() => {
    document.title = "AURA-GEN Accelerator Cream 30-Day Protocol | ReRoots Skincare";
    
    // Update meta description
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', 'Complete 30-day protocol for AURA-GEN Accelerator Rich Cream. Day-by-day transformation guide with Mandelic 5%, Triple Peptide, HPR + Bakuchiol.');
    }
    
    return () => {
      // Reset to default on unmount
      document.title = "ReRoots | Premium PDRN Skincare";
    };
  }, []);
  
  const day = days[activeDay];
  const ACCENT = "#C9A84C";

  // Share URL
  const shareUrl = `${window.location.origin}/aura-gen-cream-protocol`;
  const shareTitle = "AURA-GEN Accelerator Cream 30-Day Protocol";
  const shareText = "The complete barrier-rebuilding, collagen-building, acne-clearing cream — Triple Peptide + HPR + Bakuchiol + Mandelic AHA in one step.";

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
      // WhatsApp: Opens WhatsApp with pre-filled message, user selects contact
      whatsapp: `https://api.whatsapp.com/send?text=${encodedFullMessage}`,
      // Twitter/X: Opens tweet composer with text and link
      twitter: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`,
      // Facebook: Opens share dialog
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}&quote=${encodedText}`,
      // Email: Opens default email client with subject and body
      email: `mailto:?subject=${encodedTitle}&body=${encodedFullMessage}`,
      // SMS: Opens SMS app (works best on mobile)
      sms: `sms:?&body=${encodedFullMessage}`,
    };
    window.open(urls[platform], '_blank');
    setShowShareMenu(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#080C08", color: "#F0EBE3", fontFamily: "'Georgia', serif", overflowX: "hidden", paddingTop: "70px" }}>
      {/* SEO Meta Tags */}
      <Helmet>
        <title>AURA-GEN Accelerator Cream 30-Day Protocol | ReRoots Skincare</title>
        <meta name="description" content="Complete 30-day protocol for AURA-GEN Accelerator Rich Cream. Day-by-day transformation guide with Mandelic 5%, Triple Peptide, HPR + Bakuchiol. See what changes to expect and when." />
        <meta name="keywords" content="AURA-GEN cream protocol, 30 day skincare routine, Mandelic acid cream, HPR retinoid, Bakuchiol cream, anti-aging protocol, acne treatment cream, barrier repair cream, ReRoots skincare" />
        <link rel="canonical" href="https://reroots.ca/aura-gen-cream-protocol" />
        
        {/* Open Graph */}
        <meta property="og:title" content="AURA-GEN Accelerator Cream 30-Day Protocol" />
        <meta property="og:description" content="The complete barrier-rebuilding, collagen-building, acne-clearing cream protocol. Triple Peptide + HPR + Bakuchiol + Mandelic AHA." />
        <meta property="og:url" content="https://reroots.ca/aura-gen-cream-protocol" />
        <meta property="og:type" content="article" />
        <meta property="og:image" content="https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/a4671ebm_1767158945864.jpg" />
        
        {/* Twitter */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="AURA-GEN Accelerator Cream 30-Day Protocol" />
        <meta name="twitter:description" content="Complete day-by-day transformation guide for AURA-GEN Accelerator Rich Cream." />
        
        {/* Schema.org Structured Data */}
        <script type="application/ld+json">{`
          {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": "AURA-GEN Accelerator Cream 30-Day Protocol",
            "description": "Complete 30-day protocol for AURA-GEN Accelerator Rich Cream with Mandelic, HPR, Bakuchiol, and Triple Peptide Complex",
            "totalTime": "P30D",
            "tool": [
              {"@type": "HowToTool", "name": "AURA-GEN Accelerator Rich Cream"},
              {"@type": "HowToTool", "name": "SPF 30+ Sunscreen"}
            ],
            "step": [
              {"@type": "HowToStep", "name": "Day 1-3: Surface Activation", "text": "Mandelic Acid begins dissolving corneocyte bonds. Skin smoother by Day 2."},
              {"@type": "HowToStep", "name": "Day 4-7: Barrier Build", "text": "Full intercellular lipid replacement. TEWL measurably reduced."},
              {"@type": "HowToStep", "name": "Day 8-14: Collagen Onset", "text": "Matrixyl 3000 signals fibroblasts. First firmness improvement at Day 10-12."},
              {"@type": "HowToStep", "name": "Day 15-21: Retinoid Peak", "text": "HPR + Bakuchiol complete first retinoid cycle. Cell turnover transformed."},
              {"@type": "HowToStep", "name": "Day 22-30: Transformation", "text": "Wrinkle depth reduced 20-35%. Complexion 1-2 shades brighter."}
            ],
            "supply": [
              {"@type": "HowToSupply", "name": "Mandelic Acid 5%"},
              {"@type": "HowToSupply", "name": "HPR (Hydroxypinacolone Retinoate) 2%"},
              {"@type": "HowToSupply", "name": "Bakuchiol"},
              {"@type": "HowToSupply", "name": "Matrixyl 3000"},
              {"@type": "HowToSupply", "name": "SNAP-8 + Leuphasyl"}
            ]
          }
        `}</script>
      </Helmet>
      
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Josefin+Sans:wght@200;300;400&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #C9A84C44; border-radius: 100px; }
        .btn { cursor: pointer; border: none; background: none; transition: all 0.25s; }
        .btn:hover { opacity: 0.75; }
        .card:hover { transform: translateX(3px); }
        .card { transition: transform 0.2s; }
        .daybtn:hover { transform: translateY(-2px); }
        .daybtn { transition: all 0.25s; border: none; cursor: pointer; }
      `}</style>

      {/* HEADER */}
      <div style={{ background: "linear-gradient(160deg, #0C100A 0%, #080C08 100%)", borderBottom: "1px solid rgba(201,168,76,0.12)", padding: "24px 24px 28px", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: -80, right: -80, width: 360, height: 360, background: "radial-gradient(circle, rgba(201,168,76,0.07) 0%, transparent 65%)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", bottom: -40, left: 180, width: 220, height: 220, background: "radial-gradient(circle, rgba(135,206,235,0.04) 0%, transparent 65%)", pointerEvents: "none" }} />

        {/* Top Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <button onClick={() => navigate(-1)} style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none", cursor: "pointer", color: "#F0EBE388", fontSize: 12 }}>
            <ChevronLeft size={16} /> Back to Shop
          </button>
          
          {/* Share Button */}
          <div style={{ position: "relative" }}>
            <button onClick={handleNativeShare} style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 100, background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.3)", cursor: "pointer", color: ACCENT }}>
              <Share2 size={14} />
              <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 2, textTransform: "uppercase" }}>Share</span>
            </button>
            
            {showShareMenu && (
              <div style={{ position: "absolute", top: "calc(100% + 8px)", right: 0, background: "#1a1a2e", borderRadius: 12, border: "1px solid rgba(201,168,76,0.2)", padding: "8px", minWidth: 180, zIndex: 100, boxShadow: "0 8px 32px rgba(0,0,0,0.4)" }}>
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

        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 6, color: "#C9A84C55", marginBottom: 10, textTransform: "uppercase" }}>
          ReRoots Aesthetics · Standalone Protocol
        </div>
        <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 36, fontWeight: 300, letterSpacing: 2, lineHeight: 1.05, marginBottom: 4 }}>
          AURA-GEN
          <span style={{ color: "#C9A84C", fontStyle: "italic" }}> Accelerator</span>
        </div>
        <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 16, fontWeight: 300, color: "#F0EBE355", letterSpacing: 3, marginBottom: 6 }}>
          Rich Cream
        </div>
        <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 4, color: "#F0EBE355", textTransform: "uppercase", marginBottom: 20 }}>
          Accelerator Complex · 30-Day Solo Protocol
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {["Mandelic 5%", "Triple Peptide", "HPR + Bakuchiol", "Zinc PCA", "Matrixyl 3000"].map(tag => (
            <span key={tag} style={{
              fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, textTransform: "uppercase",
              color: "#C9A84CAA", padding: "4px 12px", borderRadius: 100,
              background: "rgba(201,168,76,0.08)", border: "1px solid rgba(201,168,76,0.18)"
            }}>{tag}</span>
          ))}
          <span style={{
            fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, textTransform: "uppercase",
            color: "#4CAF50AA", padding: "4px 12px", borderRadius: 100,
            background: "rgba(76,175,80,0.08)", border: "1px solid rgba(76,175,80,0.18)"
          }}>✓ 8/8 Concerns Covered</span>
        </div>
      </div>

      {/* TABS */}
      <div style={{ display: "flex", padding: "0 24px", borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0A0E0A", overflowX: "auto" }}>
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
                        {i < activeDay && <span style={{ fontSize: 7, color: "#080C08" }}>✓</span>}
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
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: "#F0EBE333", textTransform: "uppercase" }}>Cream-Only Protocol · Twice Daily</div>
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
                      <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 3, color: `${s.color}77`, textTransform: "uppercase" }}>Accelerator Cream Protocol</div>
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
                            {step.step === 1 ? (s.key === "am" ? "Cleanse" : "Double Cleanse") : step.step === 2 ? "Accelerator Rich Cream" : s.key === "am" ? "SPF 30+" : "Final Step"}
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

            {/* Intro Protocol Warning */}
            <div style={{ marginTop: 20, padding: "14px 18px", borderRadius: 10, background: "rgba(201,168,76,0.07)", border: "1px solid rgba(201,168,76,0.2)" }}>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 3, color: "#C9A84CAA", textTransform: "uppercase", marginBottom: 6 }}>⚠ HPR Introduction Protocol — First 14 Days</div>
              <div style={{ fontFamily: "'Georgia', serif", fontSize: 11, color: "#F0EBE3AA", lineHeight: 1.65 }}>
                For new users: apply PM only for the first 14 days. HPR is a direct retinoic acid receptor agonist — more potent than encapsulated retinol. Start every other night for Week 1, then nightly from Week 2. From Day 15, move to full AM + PM protocol.
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#F0EBE322", textTransform: "uppercase", marginBottom: 12 }}>Key Cream Rules</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
                {[
                  { rule: "Warm Before Applying", detail: "Warm cream between palms for 5 seconds before application. Emulsifiers activate at skin temperature.", color: ACCENT },
                  { rule: "Press, Don't Drag", detail: "Pressing motion prevents disruption of the emulsifier membrane and avoids traction on sensitive skin.", color: "#87CEEB" },
                  { rule: "SPF is Mandatory", detail: "Mandelic AHA + HPR both sensitise skin to UV. Skipping SPF reverses brightening and causes new PIH.", color: "#F5C842" },
                  { rule: "HPR is Nocturnal", detail: "Apply more cream at PM than AM. Retinoid receptor activity is highest during overnight cell division.", color: "#E8A0C0" },
                  { rule: "No Separate Moisturiser", detail: "This cream is the final step. Adding another moisturiser dilutes actives and disrupts the emulsion.", color: "#A8D8A8" },
                  { rule: "Weeks 1–2: PM Only", detail: "First 14 days PM only. HPR is potent — purging phase is possible if introduced too fast.", color: "#9B8EC4" },
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
              <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 9, letterSpacing: 3, color: "#F0EBE333", textTransform: "uppercase" }}>Cream standalone · Day 30 resolution % per concern</div>
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
                      <span key={ing} style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 1, color: "#C9A84C77", padding: "2px 8px", borderRadius: 100, background: "rgba(201,168,76,0.07)", border: "1px solid rgba(201,168,76,0.12)", textTransform: "uppercase" }}>{ing}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Score Card */}
            <div style={{ marginTop: 20, padding: "20px 24px", borderRadius: 14, background: "linear-gradient(135deg, rgba(201,168,76,0.07), rgba(135,206,235,0.04))", border: "1px solid rgba(201,168,76,0.16)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
              <div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#C9A84C66", textTransform: "uppercase", marginBottom: 6 }}>Cream Standalone Score</div>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 40, fontWeight: 300, color: ACCENT, lineHeight: 1 }}>8 / 8</div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: "#F0EBE333", textTransform: "uppercase", marginTop: 4 }}>Concerns at 4–5 Stars</div>
                <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 2, color: "#87CEEB88", textTransform: "uppercase", marginTop: 6 }}>+ Add Serum for deeper bio-repair & faster delivery</div>
              </div>
              <div style={{ maxWidth: 340 }}>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 14, fontStyle: "italic", color: "#F0EBE3AA", lineHeight: 1.7, marginBottom: 10 }}>
                  "The Accelerator is the most complete standalone skin treatment in the AURA-GEN line. It covers all 8 concerns, drives collagen, clears acne, rebuilds the barrier and delivers a triple peptide anti-aging stack — all in one step."
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {["Triple Peptide", "Dual Retinoid", "5-AHA System", "Full Barrier Rebuild", "Acne Control"].map(tag => (
                    <span key={tag} style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 7, letterSpacing: 1, color: "#C9A84C88", textTransform: "uppercase", padding: "3px 8px", borderRadius: 100, background: "rgba(201,168,76,0.07)", border: "1px solid rgba(201,168,76,0.14)" }}>{tag}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* CTA */}
            <div style={{ marginTop: 24, textAlign: "center" }}>
              <button onClick={() => navigate('/products')} style={{ padding: "12px 28px", borderRadius: 100, background: "linear-gradient(135deg, #C9A84C, #D4AF37)", border: "none", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 10 }}>
                <ShoppingBag size={16} color="#080C08" />
                <span style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 10, letterSpacing: 3, color: "#080C08", textTransform: "uppercase" }}>Shop Accelerator Cream</span>
              </button>
            </div>
          </div>
        )}

        {/* Shareable Link Section */}
        <div style={{ marginTop: 28, padding: "18px 20px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(201,168,76,0.12)" }}>
          <div style={{ fontFamily: "'Josefin Sans', sans-serif", fontSize: 8, letterSpacing: 4, color: "#C9A84C66", textTransform: "uppercase", marginBottom: 10 }}>Share This Protocol</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 200, padding: "10px 14px", borderRadius: 8, background: "rgba(0,0,0,0.25)", border: "1px solid rgba(255,255,255,0.05)", display: "flex", alignItems: "center", gap: 10 }}>
              <Link2 size={14} color={ACCENT} />
              <span style={{ fontFamily: "monospace", fontSize: 11, color: "#F0EBE3AA", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{shareUrl}</span>
            </div>
            <button onClick={copyLink} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 8, background: copied ? "rgba(76,175,80,0.2)" : "rgba(201,168,76,0.12)", border: `1px solid ${copied ? "rgba(76,175,80,0.4)" : "rgba(201,168,76,0.25)"}`, cursor: "pointer" }}>
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
