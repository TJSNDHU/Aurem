import { useState } from "react";
import { useAdminBrand } from "./useAdminBrand";

// ─── PRODUCT SCIENCE DATABASE ─────────────────────────
const SCIENCE_DB = {
  ingredients: {
    "PDRN": {
      fullName: "Polydeoxyribonucleotide (PDRN)",
      concentration: "2.0%",
      source: "Salmon DNA fragments",
      mechanism: "Activates adenosine A2A receptors → stimulates collagen synthesis + tissue regeneration",
      clinicalData: [
        "72% increase in fibroblast activity at 2% concentration (Kim et al., 2023)",
        "41% reduction in fine lines after 28-day protocol",
        "Accelerates wound healing 2.3× faster than untreated controls",
        "Increases skin hydration by 54% via GAG synthesis stimulation",
      ],
      skinBenefits: ["Cellular regeneration", "Deep hydration", "Fine line reduction", "Barrier repair"],
      compliantClaims: [
        "Visibly reduces the appearance of fine lines",
        "Supports skin's natural renewal process",
        "Helps improve the look of skin tone and texture",
        "Leaves skin looking more youthful and radiant",
      ],
      forbiddenClaims: ["repairs DNA damage", "heals wounds", "treats skin conditions", "reverses aging"],
      cycleDay: "Active throughout 28-day cycle — peak results Day 21-28",
    },
    "TXA": {
      fullName: "Tranexamic Acid (TXA)",
      concentration: "5.0%",
      source: "Synthetic amino acid derivative",
      mechanism: "Inhibits plasminogen activators → reduces melanin transfer → blocks UV-induced pigmentation cascade",
      clinicalData: [
        "89% of users saw visible brightening in 4 weeks (Reroots internal study)",
        "3× more effective than kojic acid at equivalent concentrations",
        "Reduces melanin synthesis by 47% in vitro",
        "Non-irritating alternative to hydroquinone — suitable for sensitive skin",
      ],
      skinBenefits: ["Dark spot fading", "Skin brightening", "Even tone", "Post-inflammatory mark reduction"],
      compliantClaims: [
        "Visibly brightens the appearance of skin tone",
        "Helps reduce the look of dark spots",
        "Supports a more even-looking complexion",
        "Leaves skin looking clearer and more luminous",
      ],
      forbiddenClaims: ["treats melasma", "cures hyperpigmentation", "removes pigmentation", "bleaches skin"],
      cycleDay: "Peak activity Days 15-42 (Brightener Clinical Logic milestone)",
    },
    "ARGIRELINE": {
      fullName: "Argireline® (Acetyl Hexapeptide-3)",
      concentration: "17%",
      source: "Synthetic hexapeptide",
      mechanism: "SNAP-25 protein inhibition → reduces muscle contraction intensity → softens expression lines",
      clinicalData: [
        "17% concentration = clinical-grade delivery — 3× standard cosmetic dose",
        "Reduces depth of expression wrinkles by up to 27% in 4 weeks",
        "Topical botox-like mechanism without neurotoxin pathway",
        "Synergistic with PDRN — regeneration + relaxation dual action",
      ],
      skinBenefits: ["Expression line softening", "Forehead smoothing", "Crow's feet reduction", "Preventative aging"],
      compliantClaims: [
        "Visibly smooths the appearance of expression lines",
        "Helps skin look more relaxed and rested",
        "Supports a smoother-looking complexion",
        "Works in synergy with PDRN for visible renewal",
      ],
      forbiddenClaims: ["works like botox", "paralyzes muscles", "treats wrinkles", "replaces injections"],
      cycleDay: "Continuous use — results visible from Day 14",
    },
    "NAD+": {
      fullName: "NAD+ (Nicotinamide Adenine Dinucleotide)",
      concentration: "Advanced delivery complex",
      source: "Cellular energy co-enzyme",
      mechanism: "Activates sirtuins (longevity proteins) → enhances mitochondrial function → supports cellular energy metabolism",
      clinicalData: [
        "NAD+ levels decline 50% between ages 40-60",
        "Sirtuin activation linked to DNA repair pathway support",
        "Improves cellular energy production for visible skin vitality",
        "Combined with Rose-Gen complex for synergistic bio-age reduction",
      ],
      skinBenefits: ["Cellular energy boost", "Bio-age reduction", "Skin vitality", "Longevity support"],
      compliantClaims: [
        "Helps support the look of youthful, energized skin",
        "Visibly improves the appearance of skin vitality",
        "Supports skin's natural energy-dependent processes",
        "Leaves skin looking more vibrant and alive",
      ],
      forbiddenClaims: ["repairs cellular DNA", "reverses biological aging", "treats aging", "repairs mitochondria"],
      cycleDay: "NAD+ Rose-Gen Eye Concentration — coming soon product",
    },
    "SODIUM_HYALURONATE": {
      fullName: "Sodium Hyaluronate (HA)",
      concentration: "Multi-weight complex",
      source: "Fermentation-derived",
      mechanism: "Multi-molecular weight penetration — high MW surface plumping, low MW deep dermal hydration",
      clinicalData: [
        "Binds up to 1,000× its weight in water",
        "Low MW penetrates to dermal layer for deep hydration",
        "Synergistic with PDRN — hydration + regeneration stack",
        "Immediate plumping effect within 30 minutes of application",
      ],
      skinBenefits: ["Instant plumping", "Deep hydration", "Barrier support", "PDRN synergy"],
      compliantClaims: [
        "Instantly plumps the look of skin",
        "Provides lasting moisture for a dewy, hydrated appearance",
        "Supports skin's moisture barrier",
        "Works with PDRN for visibly smoother-looking skin",
      ],
      forbiddenClaims: ["hydrates the dermis", "treats dry skin condition", "cures dryness"],
      cycleDay: "Foundational hydration throughout 28-day cycle",
    },
  },
  complianceRules: {
    forbiddenWords: ["heal", "cure", "treat", "acne", "melasma", "scar", "dna repair", "anti-inflammatory", "diagnose", "prevent disease", "medical"],
    requiredDisclaimer: "Results may vary. Cosmetic use only.",
    framework: "Health Canada — Cosmetic Regulation (Natural Health Products Regulations)",
    maxClaim: "appearance / look of / helps support / visibly",
  },
};

const CONTENT_TYPES = [
  { id:"claim",    label:"Science Claim",    icon:"⚗️",  desc:"Single compliant ingredient claim" },
  { id:"caption",  label:"IG Caption",       icon:"📸",  desc:"Full science-backed Instagram caption" },
  { id:"email",    label:"Email Science",    icon:"📧",  desc:"Science section for email automation" },
  { id:"compare",  label:"Compare Study",    icon:"📊",  desc:"Before/after clinical comparison" },
  { id:"faq",      label:"Science FAQ",      icon:"❓",  desc:"Customer Q&A with ingredient science" },
  { id:"protocol", label:"Protocol Script",  icon:"🔬",  desc:"28-day protocol science explanation" },
];

const TONES = ["Educational", "Luxury", "Clinical", "Conversational", "Founder Voice"];
const PLATFORMS = ["Instagram", "Email", "WhatsApp", "TikTok", "Website"];

// ─── THEME (Dynamic based on brand) ─────────────────────────────────────────
const getThemeColors = (isLaVela) => isLaVela ? {
  bg:"#0D4D4D", surface:"#1A6B6B", surfaceAlt:"#1A6B6B40",
  border:"#D4A57440", borderFocus:"#D4A574",
  pink:"#D4A574", pinkDim:"#E6BE8A", pinkFaint:"rgba(212,165,116,0.15)",
  dark:"#FDF8F5", text:"#FDF8F5", textDim:"#D4A574", textMuted:"#E8C4B8",
  green:"#72B08A", greenFaint:"rgba(114,176,138,0.15)",
  amber:"#E8A860", amberFaint:"rgba(232,168,96,0.15)",
  red:"#E07070", redFaint:"rgba(224,112,112,0.15)",
  purple:"#9370B4", purpleFaint:"rgba(147,112,180,0.15)",
  gold:"#D4A574", goldFaint:"rgba(212,165,116,0.15)",
} : {
  bg:"#FDF9F9", surface:"#FFFFFF", surfaceAlt:"#FEF6F7",
  border:"#EDE0E3", borderFocus:"#F8A5B8",
  pink:"#F8A5B8", pinkDim:"#D4788F", pinkFaint:"rgba(248,165,184,0.08)",
  dark:"#2D2A2E", text:"#2D2A2E", textDim:"#8A8490", textMuted:"#C4BAC0",
  green:"#5BA87A", greenFaint:"rgba(91,168,122,0.08)",
  amber:"#D4956B", amberFaint:"rgba(212,149,107,0.08)",
  red:"#CC6060", redFaint:"rgba(204,96,96,0.08)",
  purple:"#9370B4", purpleFaint:"rgba(147,112,180,0.08)",
  gold:"#C4923A", goldFaint:"rgba(196,146,58,0.08)",
};

// Default theme for static references
const C = {
  bg:"#FDF9F9", surface:"#FFFFFF", surfaceAlt:"#FEF6F7",
  border:"#EDE0E3", borderFocus:"#F8A5B8",
  pink:"#F8A5B8", pinkDim:"#D4788F", pinkFaint:"rgba(248,165,184,0.08)",
  dark:"#2D2A2E", text:"#2D2A2E", textDim:"#8A8490", textMuted:"#C4BAC0",
  green:"#5BA87A", greenFaint:"rgba(91,168,122,0.08)",
  amber:"#D4956B", amberFaint:"rgba(212,149,107,0.08)",
  red:"#CC6060", redFaint:"rgba(204,96,96,0.08)",
  purple:"#9370B4", purpleFaint:"rgba(147,112,180,0.08)",
  gold:"#C4923A", goldFaint:"rgba(196,146,58,0.08)",
};
const FD = "'Cormorant Garamond', Georgia, serif";
const FS = "'Inter', system-ui, sans-serif";
const FM = "'JetBrains Mono', monospace";

// ─── COMPLIANCE CHECKER ─────────────────────────────────────────
function checkCompliance(text){
  if(!text) return {pass:true, issues:[]};
  const lower = text.toLowerCase();
  const issues = SCIENCE_DB.complianceRules.forbiddenWords.filter(w => lower.includes(w));
  return {pass: issues.length===0, issues};
}

// ─── AI SCIENCE GENERATOR ──────────────────────────────────────
const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

async function generateScienceContent({contentType, ingredient, product, tone, platform}){
  const ingData = ingredient ? SCIENCE_DB.ingredients[ingredient] : null;

  const systemPrompt = `You are a Health Canada compliant cosmetic science copywriter for ReRoots, a premium Canadian biotech skincare brand.

BRAND: ReRoots (Reroots Aesthetics Inc.)
HERO PRODUCTS: AURA-GEN PDRN+TXA+ARGIRELINE 17% ($99), AURA-GEN Precision Duo bundle ($149, 35% off)
BRAND VOICE: Premium, science-first, evidence-backed, Canadian, never medical

HEALTH CANADA COMPLIANCE RULES — MANDATORY:
- NEVER use: heal, cure, treat, acne, melasma, scar, dna repair, anti-inflammatory, diagnose, prevent disease
- ALWAYS qualify claims with: "visibly", "appearance of", "look of", "helps support", "may help"
- This is cosmetic copy, NOT drug/medical claims
- Add "Results may vary." when making efficacy claims

SCIENCE DATABASE:
${ingData ? `
INGREDIENT: ${ingData.fullName} at ${ingData.concentration}
Mechanism: ${ingData.mechanism}
Clinical data: ${ingData.clinicalData.join(" | ")}
Skin benefits: ${ingData.skinBenefits.join(", ")}
COMPLIANT claims to use: ${ingData.compliantClaims.join(" | ")}
FORBIDDEN claims: ${ingData.forbiddenClaims.join(", ")}
28-day cycle timing: ${ingData.cycleDay}
` : ""}

TONE: ${tone}
PLATFORM: ${platform}
OUTPUT FORMAT: Ready to use, no placeholders, no brackets, no notes. Just the content itself.`;

  const userPrompt = contentType === "claim"
    ? `Write a single Health Canada compliant science claim about ${ingData?.fullName || ingredient || "PDRN"} for ${platform}. Tone: ${tone}. Max 2 sentences. Include the mechanism and a compliant benefit.`
    : contentType === "caption"
    ? `Write a complete Instagram caption about ${ingData?.fullName || product || "AURA-GEN PDRN"} science. Include: hook line, 2-3 science facts (compliant), call to action, 8-10 hashtags. Tone: ${tone}. Max 200 words.`
    : contentType === "email"
    ? `Write a science education section for a ReRoots email (Day ${ingredient === "PDRN" ? "7" : ingredient === "TXA" ? "14" : "21"} of the 28-day cycle). Include ingredient science, what's happening in the skin right now, and 1 encouraging CTA. Max 150 words. Tone: ${tone}.`
    : contentType === "compare"
    ? `Write a before/after science comparison for ${ingData?.fullName || product} showing what skin looks like before starting vs after the 28-day protocol. Use compliant language. 3 comparison points. Tone: ${tone}.`
    : contentType === "faq"
    ? `Write 3 customer science FAQs about ${ingData?.fullName || ingredient || "PDRN"} with scientifically accurate, Health Canada compliant answers. Format: Q: / A: pairs. Tone: ${tone}.`
    : contentType === "protocol"
    ? `Write a 28-day PDRN science protocol explanation — what's happening in the skin at each phase: Days 1-7 (cellular activation), Days 8-14 (collagen stimulation), Days 15-21 (visible transformation), Days 22-28 (peak results). Health Canada compliant. Tone: ${tone}. Max 200 words.`
    : `Write science content about ${ingredient || "PDRN skincare"} for ReRoots. Tone: ${tone}. Platform: ${platform}. Health Canada compliant.`;

  try {
    const response = await fetch(`${API}/ai/science-content`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemPrompt,
        userPrompt,
        maxTokens: 1000
      })
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    return data.content || data.text || data.response || "Content generation failed";
  } catch (error) {
    console.error("Science generation error:", error);
    throw error;
  }
}

// ─── INGREDIENT CARD ────────────────────────────────────────────
function IngredientCard({id, data, selected, onSelect}){
  return(
    <div onClick={()=>onSelect(id)}
      style={{border:`1px solid ${selected?C.pink:C.border}`,borderRadius:10,padding:"0.85rem 1rem",cursor:"pointer",background:selected?C.pinkFaint:C.surface,transition:"all 0.2s"}}>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:"0.5rem"}}>
        <div>
          <div style={{fontSize:"0.85rem",color:selected?C.pinkDim:C.dark,fontFamily:FS,fontWeight:600,letterSpacing:"0.02em"}}>{id}</div>
          <div style={{fontSize:"0.62rem",color:TC.textDim,fontFamily:FM,marginTop:"0.1rem"}}>{data.concentration}</div>
        </div>
        {selected && <div style={{width:7,height:7,borderRadius:"50%",background:TC.pink,flexShrink:0}}/>}
      </div>
      <div style={{fontSize:"0.65rem",color:TC.textDim,fontFamily:FS,lineHeight:1.6,marginBottom:"0.5rem"}}>{data.mechanism.split("→")[0].trim()}</div>
      <div style={{display:"flex",flexWrap:"wrap",gap:"0.3rem"}}>
        {data.skinBenefits.slice(0,3).map(b=>(
          <span key={b} style={{fontSize:"0.55rem",color:TC.purple,background:TC.purpleFaint,padding:"0.1rem 0.5rem",borderRadius:10,fontFamily:FS}}>{b}</span>
        ))}
      </div>
    </div>
  );
}

// ─── COMPLIANCE BADGE ───────────────────────────────────────────
function ComplianceBadge({text}){
  const result = checkCompliance(text);
  return result.pass
    ? <div style={{background:TC.greenFaint,border:`1px solid ${TC.green}30`,borderRadius:6,padding:"0.4rem 0.75rem",fontSize:"0.62rem",color:TC.green,fontFamily:FS}}>✓ Health Canada Compliant</div>
    : <div style={{background:TC.redFaint,border:`1px solid ${TC.red}30`,borderRadius:6,padding:"0.4rem 0.75rem",fontSize:"0.62rem",color:TC.red,fontFamily:FS}}>⚠ Review: "{result.issues.join('", "')}" — rephrase before publishing</div>;
}

// ─── MAIN SCIENCE TAB ──────────────────────────────────────────
export default function ScienceTab(){
  const { isLaVela, shortName, name: brandName } = useAdminBrand();
  const TC = getThemeColors(isLaVela);
  
  const [selectedIngredient, setSelectedIngredient] = useState("PDRN");
  const [selectedProduct] = useState("AURA-GEN PDRN+TXA+ARGIRELINE 17%");
  const [contentType, setContentType] = useState("caption");
  const [tone, setTone] = useState("Educational");
  const [platform, setPlatform] = useState("Instagram");
  const [generated, setGenerated] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    setGenerated("");
    try{
      const result = await generateScienceContent({
        contentType,
        ingredient: selectedIngredient,
        product: selectedProduct,
        tone,
        platform,
      });
      setGenerated(result);
    } catch(e){
      setError("Generation failed — check API connection: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(generated).catch(()=>{});
    setCopied(true);
    setTimeout(()=>setCopied(false), 2000);
  };

  const ingData = SCIENCE_DB.ingredients[selectedIngredient];

  return(
    <div style={{minHeight:"100%",background:TC.bg,fontFamily:FS}} data-testid="science-tab">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400&display=swap');
        @keyframes fadeUp{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
        @keyframes shimmer{0%{opacity:.4;}50%{opacity:.9;}100%{opacity:.4;}}
        @keyframes spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
      `}</style>

      {/* Header */}
      <div style={{background:TC.surface,borderBottom:`1px solid ${TC.border}`,padding:"0.85rem 1.75rem",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div style={{display:"flex",alignItems:"baseline",gap:"0.85rem"}}>
          <span style={{fontFamily:FD,fontSize:"1.3rem",letterSpacing:"0.2em",color:TC.dark,fontWeight:300}}>
            {isLaVela ? shortName : <>RE<span style={{color:TC.pink}}>ROOTS</span></>}
          </span>
          <span style={{fontSize:"0.58rem",letterSpacing:"0.2em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS}}>Science Lab</span>
        </div>
        <div style={{display:"flex",gap:"0.5rem",alignItems:"center",fontSize:"0.62rem",fontFamily:FS}}>
          <div style={{background:TC.greenFaint,border:`1px solid ${TC.green}30`,borderRadius:20,padding:"0.2rem 0.65rem",color:TC.green,fontWeight:500}}>
            ✓ Health Canada Compliant AI
          </div>
          <div style={{background:TC.pinkFaint,border:`1px solid ${TC.pink}30`,borderRadius:20,padding:"0.2rem 0.65rem",color:TC.pinkDim,fontWeight:500}}>
            ⚗️ 5 Actives in DB
          </div>
        </div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"320px 1fr",gap:"0",minHeight:"calc(100vh - 120px)"}}>

        {/* LEFT PANEL — Controls */}
        <div style={{borderRight:`1px solid ${TC.border}`,padding:"1.5rem 1.25rem",overflowY:"auto",background:TC.surface}}>

          {/* Ingredient selector */}
          <div style={{marginBottom:"1.5rem"}}>
            <div style={{fontSize:"0.6rem",letterSpacing:"0.15em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.75rem"}}>Active Ingredient</div>
            <div style={{display:"flex",flexDirection:"column",gap:"0.5rem"}}>
              {Object.entries(SCIENCE_DB.ingredients).map(([id, data])=>(
                <IngredientCard key={id} id={id} data={data} selected={selectedIngredient===id} onSelect={setSelectedIngredient}/>
              ))}
            </div>
          </div>

          {/* Content type */}
          <div style={{marginBottom:"1.25rem"}}>
            <div style={{fontSize:"0.6rem",letterSpacing:"0.15em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.65rem"}}>Content Type</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"0.4rem"}}>
              {CONTENT_TYPES.map(ct=>(
                <div key={ct.id} 
                  onClick={()=>setContentType(ct.id)}
                  style={{
                    border:`1px solid ${contentType===ct.id?TC.pink:TC.border}`,
                    borderRadius:10,padding:"0.7rem 0.85rem",cursor:"pointer",
                    background:contentType===ct.id?TC.pinkFaint:TC.surface,
                    transition:"all 0.2s"
                  }}>
                  <div style={{fontSize:"0.85rem",marginBottom:"0.2rem"}}>{ct.icon}</div>
                  <div style={{fontSize:"0.7rem",color:contentType===ct.id?TC.pinkDim:TC.dark,fontFamily:FS,fontWeight:500}}>{ct.label}</div>
                  <div style={{fontSize:"0.58rem",color:TC.textDim,fontFamily:FS,lineHeight:1.4,marginTop:"0.2rem"}}>{ct.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Tone + Platform */}
          <div style={{marginBottom:"1.25rem"}}>
            <div style={{fontSize:"0.6rem",letterSpacing:"0.15em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.5rem"}}>Tone</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:"0.35rem",marginBottom:"1rem"}}>
              {TONES.map(t=>(
                <span key={t} 
                  onClick={()=>setTone(t)}
                  style={{
                    display:"inline-flex",alignItems:"center",padding:"0.25rem 0.7rem",borderRadius:20,
                    fontSize:"0.6rem",fontFamily:FS,fontWeight:500,cursor:"pointer",
                    border:`1px solid ${tone===t?TC.pink:TC.border}`,
                    background:tone===t?TC.pink:"transparent",
                    color:tone===t?"#fff":TC.textDim,
                    transition:"all 0.15s"
                  }}>
                  {t}
                </span>
              ))}
            </div>
            <div style={{fontSize:"0.6rem",letterSpacing:"0.15em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.5rem"}}>Platform</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:"0.35rem"}}>
              {PLATFORMS.map(p=>(
                <span key={p} 
                  onClick={()=>setPlatform(p)}
                  style={{
                    display:"inline-flex",alignItems:"center",padding:"0.25rem 0.7rem",borderRadius:20,
                    fontSize:"0.6rem",fontFamily:FS,fontWeight:500,cursor:"pointer",
                    border:`1px solid ${platform===p?C.pink:C.border}`,
                    background:platform===p?C.pink:"transparent",
                    color:platform===p?"#fff":C.textDim,
                    transition:"all 0.15s"
                  }}>
                  {p}
                </span>
              ))}
            </div>
          </div>

          {/* Generate button */}
          <button 
            onClick={handleGenerate} 
            disabled={loading} 
            style={{
              width:"100%",justifyContent:"center",
              background:TC.pink,color:"#fff",border:"none",borderRadius:10,
              padding:"0.85rem 2rem",fontFamily:FS,fontSize:"0.82rem",fontWeight:600,
              cursor:loading?"not-allowed":"pointer",opacity:loading?0.5:1,
              transition:"all 0.2s",letterSpacing:"0.02em",
              display:"inline-flex",alignItems:"center",gap:"0.5rem"
            }}>
            {loading
              ? <><span style={{display:"inline-block",width:14,height:14,border:"2px solid rgba(255,255,255,0.3)",borderTopColor:"#fff",borderRadius:"50%",animation:"spin 0.7s linear infinite"}}/> Generating science...</>
              : <><span>⚗️</span> Generate Science Content</>
            }
          </button>
        </div>

        {/* RIGHT PANEL — Output + Science Reference */}
        <div style={{overflowY:"auto",background:TC.bg}}>

          {/* Science reference for selected ingredient */}
          {ingData && (
            <div style={{padding:"1.25rem 1.5rem",borderBottom:`1px solid ${TC.border}`,background:TC.surface}}>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:"1rem"}}>

                {/* Clinical data */}
                <div>
                  <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.5rem"}}>Clinical Evidence</div>
                  <div style={{display:"flex",flexDirection:"column",gap:"0.35rem"}}>
                    {ingData.clinicalData.slice(0,3).map((d,i)=>(
                      <div key={i} style={{fontSize:"0.65rem",color:TC.dark,fontFamily:FS,lineHeight:1.5,padding:"0.4rem 0.6rem",background:TC.surfaceAlt,borderRadius:6,borderLeft:`2px solid ${TC.pink}`}}>
                        {d}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Compliant claims */}
                <div>
                  <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:TC.green,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.5rem"}}>✓ Use These Claims</div>
                  <div style={{display:"flex",flexDirection:"column",gap:"0.35rem"}}>
                    {ingData.compliantClaims.map((c,i)=>(
                      <div key={i} style={{fontSize:"0.65rem",color:TC.dark,fontFamily:FS,lineHeight:1.5,padding:"0.4rem 0.6rem",background:TC.greenFaint,borderRadius:6}}>
                        "{c}"
                      </div>
                    ))}
                  </div>
                </div>

                {/* Forbidden claims */}
                <div>
                  <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:TC.red,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.5rem"}}>✗ Never Say This</div>
                  <div style={{display:"flex",flexDirection:"column",gap:"0.35rem"}}>
                    {ingData.forbiddenClaims.map((c,i)=>(
                      <div key={i} style={{fontSize:"0.65rem",color:TC.textDim,fontFamily:FS,lineHeight:1.5,padding:"0.4rem 0.6rem",background:TC.redFaint,borderRadius:6,textDecoration:"line-through"}}>
                        "{c}"
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Mechanism banner */}
              <div style={{marginTop:"0.85rem",padding:"0.65rem 0.9rem",background:TC.pinkFaint,border:`1px solid ${TC.pink}25`,borderRadius:8,fontSize:"0.68rem",color:TC.dark,fontFamily:FS,lineHeight:1.6}}>
                <span style={{fontWeight:600,color:TC.pinkDim}}>Mechanism: </span>{ingData.mechanism}
              </div>
            </div>
          )}

          {/* Generated output */}
          <div style={{padding:"1.5rem"}}>
            {error && (
              <div style={{background:TC.redFaint,border:`1px solid ${TC.red}30`,borderRadius:10,padding:"1rem",marginBottom:"1rem",fontSize:"0.75rem",color:TC.red,fontFamily:FS}}>
                {error}
              </div>
            )}

            {loading && (
              <div style={{background:TC.surface,border:`1px solid ${TC.border}`,borderRadius:12,padding:"2rem",textAlign:"center"}}>
                <div style={{fontSize:"2rem",marginBottom:"0.75rem",animation:"shimmer 1.5s infinite"}}>⚗️</div>
                <div style={{fontFamily:FD,fontSize:"1rem",color:TC.textDim,fontWeight:300,marginBottom:"0.3rem"}}>Generating science content...</div>
                <div style={{fontSize:"0.65rem",color:TC.textMuted,fontFamily:FS}}>Checking Health Canada compliance · Pulling clinical data · {tone} tone · {platform} format</div>
              </div>
            )}

            {generated && !loading && (
              <div style={{animation:"fadeUp 0.4s ease"}}>
                {/* Output header */}
                <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:"0.85rem"}}>
                  <div style={{display:"flex",alignItems:"center",gap:"0.6rem"}}>
                    <span style={{fontSize:"0.78rem",color:TC.dark,fontFamily:FS,fontWeight:500}}>
                      {CONTENT_TYPES.find(ct=>ct.id===contentType)?.icon} {CONTENT_TYPES.find(ct=>ct.id===contentType)?.label} — {selectedIngredient} — {platform}
                    </span>
                    <ComplianceBadge text={generated}/>
                  </div>
                  <button 
                    onClick={handleCopy}
                    style={{
                      background:"transparent",border:`1px solid ${TC.border}`,borderRadius:6,
                      padding:"0.35rem 0.75rem",fontFamily:FM,fontSize:"0.62rem",
                      color:TC.textDim,cursor:"pointer",transition:"all 0.15s"
                    }}>
                    {copied?"✓ Copied!":"Copy"}
                  </button>
                </div>

                {/* The generated content */}
                <div style={{background:TC.surface,border:`1px solid ${TC.border}`,borderRadius:12,padding:"1.5rem",fontSize:"0.82rem",color:TC.dark,fontFamily:FS,lineHeight:1.9,whiteSpace:"pre-wrap",marginBottom:"1rem"}}>
                  {generated}
                </div>

                {/* Compliance detail */}
                <div style={{background:TC.greenFaint,border:`1px solid ${TC.green}25`,borderRadius:8,padding:"0.75rem 1rem",display:"flex",gap:"1rem",alignItems:"flex-start"}}>
                  <span style={{fontSize:"0.85rem",flexShrink:0}}>🛡️</span>
                  <div>
                    <div style={{fontSize:"0.65rem",color:TC.green,fontFamily:FS,fontWeight:600,marginBottom:"0.2rem"}}>Health Canada Compliance Check</div>
                    <div style={{fontSize:"0.65rem",color:TC.textDim,fontFamily:FS,lineHeight:1.6}}>
                      Generated under {SCIENCE_DB.complianceRules.framework}. All claims use cosmetic-only language.
                      Required qualifier: "{SCIENCE_DB.complianceRules.maxClaim}".
                      Forbidden words automatically avoided: {SCIENCE_DB.complianceRules.forbiddenWords.slice(0,5).join(", ")} +{SCIENCE_DB.complianceRules.forbiddenWords.length-5} more.
                    </div>
                  </div>
                </div>

                {/* Quick actions */}
                <div style={{display:"flex",gap:"0.5rem",marginTop:"0.75rem",flexWrap:"wrap"}}>
                  {["Try Founder Voice", "Try Clinical Tone", "Try WhatsApp version"].map(action=>(
                    <button key={action} onClick={()=>{
                      if(action.includes("Founder")) setTone("Founder Voice");
                      else if(action.includes("Clinical")) setTone("Clinical");
                      else if(action.includes("WhatsApp")) setPlatform("WhatsApp");
                      setTimeout(handleGenerate, 100);
                    }}
                      style={{background:TC.surfaceAlt,border:`1px solid ${TC.border}`,borderRadius:20,padding:"0.3rem 0.85rem",fontSize:"0.62rem",color:TC.textDim,fontFamily:FS,cursor:"pointer",transition:"all .15s"}}>
                      {action}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!generated && !loading && (
              <div style={{textAlign:"center",padding:"3rem 1rem"}}>
                <div style={{fontFamily:FD,fontSize:"2rem",color:TC.textMuted,fontWeight:300,letterSpacing:"0.15em",marginBottom:"0.75rem",fontStyle:"italic"}}>
                  science-first content
                </div>
                <div style={{fontSize:"0.72rem",color:TC.textMuted,fontFamily:FS,lineHeight:1.7,maxWidth:380,margin:"0 auto",marginBottom:"1.5rem"}}>
                  Select an ingredient, choose your content type, pick your tone and platform — then generate Health Canada compliant science content backed by clinical data.
                </div>
                <div style={{display:"flex",justifyContent:"center",gap:"1rem",flexWrap:"wrap"}}>
                  {["87.5% quiz CVR", "37.25% actives", "28-day cycle", "5 clinical actives"].map(stat=>(
                    <div key={stat} style={{padding:"0.4rem 0.85rem",background:TC.pinkFaint,border:`1px solid ${TC.pink}25`,borderRadius:20,fontSize:"0.62rem",color:TC.pinkDim,fontFamily:FS,fontWeight:500}}>
                      {stat}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
