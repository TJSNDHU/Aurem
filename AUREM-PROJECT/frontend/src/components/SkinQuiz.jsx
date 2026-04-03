import { useState, useEffect, useRef } from "react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// ─── QUIZ LOGIC ──────────────────────────────────────────────────
const QUESTIONS = [
  {
    id: "q1",
    question: "What's your primary skin concern right now?",
    subtitle: "Choose the one that bothers you most",
    options: [
      { value: "aging",        label: "Fine lines & aging",      icon: "⏳", score: { PDRN: 3, TXA: 1, ARG: 3 } },
      { value: "pigmentation", label: "Dark spots & uneven tone", icon: "🌑", score: { PDRN: 1, TXA: 3, ARG: 1 } },
      { value: "texture",      label: "Rough texture & dullness", icon: "🪨", score: { PDRN: 3, TXA: 2, ARG: 1 } },
      { value: "sensitivity",  label: "Sensitivity & redness",    icon: "🌸", score: { PDRN: 2, TXA: 1, ARG: 0 } },
    ],
  },
  {
    id: "q2",
    question: "How does your skin feel by midday?",
    subtitle: "Without any products on",
    options: [
      { value: "dry",         label: "Tight and dry",           icon: "🏜️", score: { PDRN: 3, TXA: 0, ARG: 1 } },
      { value: "oily",        label: "Shiny and oily",          icon: "💧", score: { PDRN: 1, TXA: 2, ARG: 1 } },
      { value: "combo",       label: "Oily T-zone, dry cheeks", icon: "⚖️", score: { PDRN: 2, TXA: 2, ARG: 2 } },
      { value: "normal",      label: "Pretty balanced",         icon: "✨", score: { PDRN: 2, TXA: 1, ARG: 2 } },
    ],
  },
  {
    id: "q3",
    question: "When you look in the mirror, you notice most:",
    subtitle: "Be honest with yourself",
    options: [
      { value: "forehead",    label: "Lines on my forehead",    icon: "📏", score: { PDRN: 2, TXA: 0, ARG: 3 } },
      { value: "undereye",    label: "Under-eye area",          icon: "👁️", score: { PDRN: 3, TXA: 1, ARG: 2 } },
      { value: "cheeks",      label: "Tone on my cheeks",       icon: "🎭", score: { PDRN: 1, TXA: 3, ARG: 0 } },
      { value: "overall",     label: "Overall dullness",        icon: "🌫️", score: { PDRN: 2, TXA: 2, ARG: 1 } },
    ],
  },
  {
    id: "q4",
    question: "How consistent is your current routine?",
    subtitle: "No judgment — this helps us calibrate",
    options: [
      { value: "strict",      label: "AM + PM, never miss",     icon: "💯", score: { PDRN: 3, TXA: 3, ARG: 3 } },
      { value: "mostly",      label: "Most mornings",           icon: "☀️", score: { PDRN: 2, TXA: 2, ARG: 2 } },
      { value: "sometimes",   label: "When I remember",         icon: "🤷", score: { PDRN: 2, TXA: 2, ARG: 2 } },
      { value: "starting",    label: "Building a routine now",  icon: "🌱", score: { PDRN: 3, TXA: 2, ARG: 1 } },
    ],
  },
  {
    id: "q5",
    question: "What has your skin been through recently?",
    subtitle: "Skin has memory — this matters",
    options: [
      { value: "sun",         label: "A lot of sun exposure",   icon: "☀️", score: { PDRN: 2, TXA: 3, ARG: 1 } },
      { value: "stress",      label: "High stress period",      icon: "😮‍💨", score: { PDRN: 3, TXA: 1, ARG: 2 } },
      { value: "nothing",     label: "Nothing notable",         icon: "😌", score: { PDRN: 2, TXA: 2, ARG: 2 } },
      { value: "hormonal",    label: "Hormonal changes",        icon: "🔄", score: { PDRN: 2, TXA: 2, ARG: 1 } },
    ],
  },
  {
    id: "q6",
    question: "What's your age range?",
    subtitle: "PDRN protocols are calibrated by decade",
    options: [
      { value: "20s",  label: "20–29", icon: "🌱", score: { PDRN: 1, TXA: 2, ARG: 2 } },
      { value: "30s",  label: "30–39", icon: "🌿", score: { PDRN: 2, TXA: 2, ARG: 3 } },
      { value: "40s",  label: "40–49", icon: "🌳", score: { PDRN: 3, TXA: 2, ARG: 3 } },
      { value: "50+",  label: "50+",   icon: "🏔️", score: { PDRN: 3, TXA: 3, ARG: 3 } },
    ],
  },
];

// Score → product recommendation
function scoreQuiz(answers) {
  const totals = { PDRN: 0, TXA: 0, ARG: 0 };
  const concerns = [];

  QUESTIONS.forEach(q => {
    const ans = answers[q.id];
    const opt = q.options.find(o => o.value === ans);
    if (opt) {
      totals.PDRN += opt.score.PDRN;
      totals.TXA  += opt.score.TXA;
      totals.ARG  += opt.score.ARG;
    }
  });

  // Map answers to concern labels
  const concernMap = {
    aging: "fine lines & aging", pigmentation: "dark spots", texture: "texture",
    sensitivity: "sensitivity", dry: "dehydration", stress: "stress-related skin changes",
    sun: "sun damage", hormonal: "hormonal changes",
  };
  Object.values(answers).forEach(v => { if (concernMap[v]) concerns.push(concernMap[v]); });

  // Determine protocol
  const maxScore = Math.max(totals.PDRN, totals.TXA, totals.ARG);
  const dominant = Object.entries(totals).filter(([,v]) => v === maxScore).map(([k]) => k);

  if (dominant.includes("ARG") && dominant.includes("PDRN")) {
    return {
      product: "AURA-GEN PDRN+TXA+ARGIRELINE 17%",
      headline: "Your skin needs cellular renewal + expression line support",
      protocol: "28-Day Regeneration Protocol",
      price: "$99",
      url: "/products/aura-gen-pdrn-txa-argireline",
      bundle: true,
      bundleUrl: "/products/bundle",
      bundlePrice: "$149",
      keyIngredients: ["PDRN 2.0% — cellular renewal", "TXA 5.0% — brightening", "Argireline 17% — expression lines"],
      score: totals,
      concerns: [...new Set(concerns)].slice(0, 3),
      confidence: Math.round((maxScore / 18) * 100),
    };
  }

  return {
    product: "AURA-GEN PDRN+TXA+ARGIRELINE 17%",
    headline: "Your personalised PDRN ritual is ready",
    protocol: "28-Day Science Protocol",
    price: "$99",
    url: "/products/aura-gen-pdrn-txa-argireline",
    bundle: totals.PDRN >= 12,
    bundleUrl: "/products/bundle",
    bundlePrice: "$149",
    keyIngredients: ["PDRN 2.0% — cellular renewal", "TXA 5.0% — brightening", "Argireline 17% — expression lines"],
    score: totals,
    concerns: [...new Set(concerns)].slice(0, 3),
    confidence: Math.round((maxScore / 18) * 100),
  };
}

// ─── THEME ───────────────────────────────────────────────────────
const C = {
  bg: "#FBF4F6",
  surface: "#FFFFFF",
  border: "#EDE0E5",
  pink: "#F8A5B8",
  pinkDeep: "#D4788F",
  pinkFaint: "rgba(248,165,184,0.08)",
  dark: "#2D2A2E",
  text: "#2D2A2E",
  textDim: "#8A7890",
  textMuted: "#C4B8C0",
  green: "#5BA87A",
  greenFaint: "rgba(91,168,122,0.08)",
  gold: "#C4923A",
  purple: "#9370B4",
};
const FD = "'Cormorant Garamond',Georgia,serif";
const FS = "'Inter',system-ui,sans-serif";

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Inter:wght@300;400;500;600&display=swap');
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:${C.bg};-webkit-font-smoothing:antialiased;}
  ::-webkit-scrollbar{width:3px;} ::-webkit-scrollbar-track{background:${C.bg};} ::-webkit-scrollbar-thumb{background:${C.border};}
  @keyframes fadeUp{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
  @keyframes fadeIn{from{opacity:0;}to{opacity:1;}}
  @keyframes scaleIn{from{opacity:0;transform:scale(.96);}to{opacity:1;transform:scale(1);}}
  @keyframes spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
  @keyframes shimmer{0%{background-position:-200px 0;}100%{background-position:calc(200px + 100%) 0;}}
  @keyframes progressFill{from{width:0%;}to{width:var(--pct);}}
  @keyframes reveal{from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);}}
  @keyframes float{0%,100%{transform:translateY(0);}50%{transform:translateY(-6px);}}

  .option-card{
    background:${C.surface};
    border:1.5px solid ${C.border};
    border-radius:14px;
    padding:1rem 1.1rem;
    cursor:pointer;
    transition:all .2s;
    display:flex;
    align-items:center;
    gap:.85rem;
    text-align:left;
    width:100%;
    user-select:none;
  }
  .option-card:hover{
    border-color:${C.pink};
    background:${C.pinkFaint};
    transform:translateY(-2px);
    box-shadow:0 4px 16px rgba(248,165,184,0.15);
  }
  .option-card.selected{
    border-color:${C.pink};
    background:${C.pinkFaint};
    box-shadow:0 0 0 3px rgba(248,165,184,0.2), 0 4px 16px rgba(248,165,184,0.15);
  }
  .btn-main{
    background:${C.pink};
    color:#fff;
    border:none;
    border-radius:12px;
    padding:1rem 2.5rem;
    font-family:${FS};
    font-size:.88rem;
    font-weight:600;
    cursor:pointer;
    transition:all .25s;
    letter-spacing:.03em;
    display:inline-flex;
    align-items:center;
    gap:.5rem;
  }
  .btn-main:hover:not(:disabled){
    opacity:.9;
    transform:translateY(-2px);
    box-shadow:0 8px 24px rgba(248,165,184,0.35);
  }
  .btn-main:disabled{opacity:.5;cursor:not-allowed;}
  .btn-outline{
    background:transparent;
    border:1.5px solid ${C.pink};
    color:${C.pink};
    border-radius:12px;
    padding:.85rem 2rem;
    font-family:${FS};
    font-size:.85rem;
    font-weight:500;
    cursor:pointer;
    transition:all .2s;
  }
  .btn-outline:hover{background:${C.pinkFaint};}
  input[type="text"],input[type="email"]{
    background:${C.surface};
    border:1.5px solid ${C.border};
    border-radius:10px;
    padding:.8rem 1rem;
    font-family:${FS};
    font-size:.85rem;
    color:${C.text};
    outline:none;
    transition:border .2s;
    width:100%;
  }
  input:focus{border-color:${C.pink};box-shadow:0 0 0 3px rgba(248,165,184,0.12);}
`;

// ─── PROGRESS BAR ────────────────────────────────────────────────
function ProgressBar({ current, total }) {
  const pct = Math.round((current / total) * 100);
  return (
    <div style={{ marginBottom: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: ".5rem" }}>
        <span style={{ fontSize: ".6rem", letterSpacing: ".18em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 600 }}>
          Question {current} of {total}
        </span>
        <span style={{ fontSize: ".6rem", color: C.pink, fontFamily: FS, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div style={{ height: 3, background: C.border, borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          height: "100%", borderRadius: 2,
          background: `linear-gradient(to right, ${C.pink}, ${C.pinkDeep})`,
          width: `${pct}%`, transition: "width .5s cubic-bezier(.4,0,.2,1)"
        }} />
      </div>
    </div>
  );
}

// ─── QUESTION SCREEN ─────────────────────────────────────────────
function QuestionScreen({ question, qIndex, total, onAnswer, currentAnswer }) {
  const [selected, setSelected] = useState(currentAnswer || null);

  const handleSelect = (value) => {
    setSelected(value);
    setTimeout(() => onAnswer(value), 350);
  };

  return (
    <div style={{ animation: "scaleIn .35s ease" }}>
      <ProgressBar current={qIndex + 1} total={total} />

      <div style={{ marginBottom: "2rem" }}>
        <h2 style={{
          fontFamily: FD, fontSize: "clamp(1.4rem, 3vw, 1.9rem)",
          color: C.dark, fontWeight: 400, lineHeight: 1.35,
          marginBottom: ".5rem", letterSpacing: ".01em"
        }}>
          {question.question}
        </h2>
        <p style={{ fontSize: ".8rem", color: C.textDim, fontFamily: FS, lineHeight: 1.5 }}>
          {question.subtitle}
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: ".65rem" }}>
        {question.options.map((opt, i) => (
          <button
            key={opt.value}
            className={`option-card${selected === opt.value ? " selected" : ""}`}
            onClick={() => handleSelect(opt.value)}
            style={{ animation: `fadeUp .25s ${i * .07}s both` }}
            data-testid={`quiz-option-${opt.value}`}
          >
            <span style={{
              fontSize: "1.4rem", width: 42, height: 42, flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: selected === opt.value ? "rgba(248,165,184,0.15)" : C.bg,
              borderRadius: 10, transition: "background .2s"
            }}>{opt.icon}</span>
            <span style={{
              fontSize: ".85rem", color: selected === opt.value ? C.pinkDeep : C.dark,
              fontFamily: FS, fontWeight: selected === opt.value ? 600 : 400,
              transition: "color .15s, font-weight .15s"
            }}>
              {opt.label}
            </span>
            {selected === opt.value && (
              <span style={{ marginLeft: "auto", color: C.pink, fontSize: ".9rem" }}>✓</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── CONTACT SCREEN ──────────────────────────────────────────────
function ContactScreen({ onSubmit, loading }) {
  const [name, setName]   = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
    if (!email.includes("@")) { setError("Please enter a valid email"); return; }
    if (!name.trim()) { setError("Please enter your name"); return; }
    onSubmit({ name: name.trim(), email: email.trim() });
  };

  return (
    <div style={{ animation: "fadeUp .4s ease" }}>
      <div style={{ textAlign: "center", marginBottom: "2rem" }}>
        <div style={{ fontSize: "2.5rem", marginBottom: "1rem", animation: "float 3s ease infinite" }}>🧬</div>
        <h2 style={{ fontFamily: FD, fontSize: "clamp(1.5rem,3vw,2rem)", color: C.dark, fontWeight: 400, marginBottom: ".5rem" }}>
          Your protocol is ready
        </h2>
        <p style={{ fontSize: ".8rem", color: C.textDim, fontFamily: FS, lineHeight: 1.6, maxWidth: 320, margin: "0 auto" }}>
          Tell us where to send your personalised PDRN ritual and science breakdown.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: ".75rem", marginBottom: "1.25rem" }}>
        <div>
          <label style={{ fontSize: ".7rem", color: C.textDim, fontFamily: FS, display: "block", marginBottom: ".35rem" }}>Your name</label>
          <input type="text" placeholder="First name" value={name} onChange={e => { setName(e.target.value); setError(""); }} data-testid="quiz-name-input" />
        </div>
        <div>
          <label style={{ fontSize: ".7rem", color: C.textDim, fontFamily: FS, display: "block", marginBottom: ".35rem" }}>Email address</label>
          <input type="email" placeholder="your@email.com" value={email} onChange={e => { setEmail(e.target.value); setError(""); }}
            onKeyDown={e => e.key === "Enter" && handleSubmit()} data-testid="quiz-email-input" />
        </div>
        {error && <div style={{ fontSize: ".7rem", color: "#CC5555", fontFamily: FS }}>{error}</div>}
      </div>

      <button className="btn-main" onClick={handleSubmit} disabled={loading} style={{ width: "100%", justifyContent: "center" }} data-testid="quiz-submit-btn">
        {loading
          ? <><span style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin .7s linear infinite", display: "inline-block" }} /> Analysing your skin...</>
          : "See My Personalised Protocol →"}
      </button>

      <p style={{ fontSize: ".65rem", color: C.textMuted, fontFamily: FS, textAlign: "center", marginTop: "1rem", lineHeight: 1.6 }}>
        We'll send your results + science breakdown to your inbox.
        No spam — unsubscribe any time.
      </p>
    </div>
  );
}

// ─── RESULTS SCREEN ──────────────────────────────────────────────
function ResultsScreen({ result, contactInfo }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText("QUIZ10").catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const scoreMax = Math.max(result.score.PDRN, result.score.TXA, result.score.ARG);
  const scoreLabels = { PDRN: "Cellular Renewal", TXA: "Brightening", ARG: "Expression Lines" };

  return (
    <div style={{ animation: "fadeIn .5s ease" }}>
      {/* Hero result */}
      <div style={{ textAlign: "center", marginBottom: "2rem", paddingBottom: "1.5rem", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: ".4rem", background: C.greenFaint, border: `1px solid ${C.green}25`, borderRadius: 20, padding: ".3rem .85rem", marginBottom: "1rem" }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.green }} />
          <span style={{ fontSize: ".62rem", color: C.green, fontFamily: FS, fontWeight: 600 }}>Protocol matched</span>
        </div>
        <h2 style={{ fontFamily: FD, fontSize: "clamp(1.4rem,3vw,1.8rem)", color: C.dark, fontWeight: 400, marginBottom: ".5rem", letterSpacing: ".01em" }}>
          {contactInfo.name ? `${contactInfo.name.split(" ")[0]}, here's your ritual` : "Your personalised ritual"}
        </h2>
        <p style={{ fontSize: ".8rem", color: C.textDim, fontFamily: FS, lineHeight: 1.6, maxWidth: 340, margin: "0 auto" }}>
          {result.headline}
        </p>
      </div>

      {/* Score breakdown */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ fontSize: ".6rem", letterSpacing: ".15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 600, marginBottom: ".75rem" }}>
          Your Skin Profile
        </div>
        {Object.entries(result.score).map(([key, val]) => (
          <div key={key} style={{ marginBottom: ".5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: ".25rem" }}>
              <span style={{ fontSize: ".72rem", color: C.dark, fontFamily: FS }}>{scoreLabels[key]}</span>
              <span style={{ fontSize: ".65rem", color: C.textDim, fontFamily: FS }}>{val}/18</span>
            </div>
            <div style={{ height: 5, background: C.border, borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 3,
                background: val === scoreMax
                  ? `linear-gradient(to right, ${C.pink}, ${C.pinkDeep})`
                  : `linear-gradient(to right, ${C.border}, ${C.textMuted})`,
                width: `${(val / 18) * 100}%`,
                transition: "width .8s ease"
              }} />
            </div>
          </div>
        ))}
      </div>

      {/* Product recommendation */}
      <div style={{ background: C.surface, border: `1.5px solid ${C.pink}`, borderRadius: 14, padding: "1.25rem", marginBottom: "1.25rem" }}>
        <div style={{ fontSize: ".58rem", letterSpacing: ".15em", color: C.pink, textTransform: "uppercase", fontFamily: FS, fontWeight: 600, marginBottom: ".5rem" }}>
          Recommended for you
        </div>
        <div style={{ fontFamily: FD, fontSize: "1.1rem", color: C.dark, fontWeight: 400, marginBottom: ".4rem" }}>
          {result.product}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: ".75rem", marginBottom: ".85rem" }}>
          <span style={{ fontSize: "1.4rem", color: C.pink, fontFamily: FD, fontWeight: 300 }}>{result.price}</span>
          <span style={{ fontSize: ".7rem", color: C.textDim, fontFamily: FS }}>CAD · {result.protocol}</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: ".35rem", marginBottom: "1rem" }}>
          {result.keyIngredients.map((ing, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: ".5rem", fontSize: ".72rem", color: C.textDim, fontFamily: FS }}>
              <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.pink, flexShrink: 0 }} />
              {ing}
            </div>
          ))}
        </div>

        <a href={`https://reroots.ca${result.url}?discount=QUIZ10`}
          style={{ display: "block", background: C.pink, color: "#fff", textAlign: "center", padding: "1rem", borderRadius: 10, textDecoration: "none", fontFamily: FS, fontSize: ".82rem", fontWeight: 600, letterSpacing: ".03em" }}
          data-testid="quiz-cta-btn">
          Start My 28-Day Protocol →
        </a>
      </div>

      {/* Exclusive code */}
      <div style={{ background: "#FFFBF2", border: "1.5px dashed #C4923A", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: "1.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: ".62rem", letterSpacing: ".12em", color: C.gold, textTransform: "uppercase", fontFamily: FS, fontWeight: 600, marginBottom: ".25rem" }}>Quiz Exclusive — 10% Off</div>
            <div style={{ fontFamily: "'JetBrains Mono','Courier New',monospace", fontSize: "1.1rem", color: C.gold, letterSpacing: ".12em", fontWeight: 700 }}>QUIZ10</div>
            <div style={{ fontSize: ".62rem", color: C.textDim, fontFamily: FS, marginTop: ".2rem" }}>Apply at checkout · One use only</div>
          </div>
          <button onClick={copy}
            style={{ background: copied ? C.green : "transparent", border: `1px solid ${copied ? C.green : C.gold}`, borderRadius: 8, padding: ".45rem .85rem", fontFamily: FS, fontSize: ".68rem", color: copied ? "#fff" : C.gold, cursor: "pointer", transition: "all .2s", fontWeight: 500 }}
            data-testid="quiz-copy-code-btn">
            {copied ? "✓ Copied" : "Copy Code"}
          </button>
        </div>
      </div>

      {/* Bundle upsell */}
      {result.bundle && (
        <div style={{ background: "linear-gradient(135deg, #F8EEF5, #EEF0FD)", border: `1px solid ${C.purple}25`, borderRadius: 14, padding: "1.25rem", marginBottom: "1.25rem" }}>
          <div style={{ fontSize: ".62rem", letterSpacing: ".12em", color: C.purple, textTransform: "uppercase", fontFamily: FS, fontWeight: 600, marginBottom: ".4rem" }}>
            Recommended Upgrade
          </div>
          <div style={{ fontFamily: FD, fontSize: "1rem", color: C.dark, fontWeight: 400, marginBottom: ".25rem" }}>
            AURA-GEN Precision Duo — 35% off
          </div>
          <div style={{ fontSize: ".75rem", color: C.textDim, fontFamily: FS, marginBottom: ".75rem", lineHeight: 1.6 }}>
            Your full protocol + advanced complex. Based on your quiz score, the dual system is the better fit. {result.bundlePrice} vs $228.99.
          </div>
          <a href={`https://reroots.ca${result.bundleUrl}`}
            style={{ display: "inline-flex", alignItems: "center", gap: ".4rem", background: C.purple, color: "#fff", padding: ".75rem 1.5rem", borderRadius: 9, textDecoration: "none", fontFamily: FS, fontSize: ".75rem", fontWeight: 600 }}>
            Upgrade to the Bundle →
          </a>
        </div>
      )}

      {/* Science note */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1rem 1.25rem", borderLeft: `3px solid ${C.pink}` }}>
        <div style={{ fontSize: ".6rem", letterSpacing: ".12em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 600, marginBottom: ".4rem" }}>The Science Behind Your Match</div>
        <p style={{ fontSize: ".75rem", color: C.textDim, fontFamily: FS, lineHeight: 1.7 }}>
          PDRN activates adenosine A2A receptors to visibly support skin renewal. At 2% concentration, clinical data shows 72% increase in fibroblast activity after 28 days. Your quiz results indicate this is the right protocol for your concerns: {result.concerns.join(", ")}. Results may vary.
        </p>
      </div>
    </div>
  );
}

// ─── MAIN QUIZ ───────────────────────────────────────────────────
export default function SkinQuiz() {
  const [step, setStep]           = useState("intro");   // intro | quiz | contact | loading | results
  const [qIndex, setQIndex]       = useState(0);
  const [answers, setAnswers]     = useState({});
  const [contactInfo, setContact] = useState({ name: "", email: "" });
  const [result, setResult]       = useState(null);
  const [apiError, setApiError]   = useState(null);
  const topRef                    = useRef(null);

  const scrollTop = () => topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  const handleAnswer = (value) => {
    const newAnswers = { ...answers, [QUESTIONS[qIndex].id]: value };
    setAnswers(newAnswers);
    scrollTop();
    if (qIndex < QUESTIONS.length - 1) {
      setTimeout(() => setQIndex(i => i + 1), 200);
    } else {
      setTimeout(() => setStep("contact"), 200);
    }
  };

  const handleContactSubmit = async ({ name, email }) => {
    setContact({ name, email });
    setStep("loading");

    const quizResult = scoreQuiz(answers);
    setResult(quizResult);

    // Submit to API
    try {
      await fetch(`${API}/quiz/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          name,
          answers,
          score:               quizResult.score,
          recommended_product: quizResult.product,
          concerns:            quizResult.concerns,
          protocol:            quizResult.protocol,
          source:              "website_quiz",
        }),
      });
    } catch (e) {
      // Don't block results on API error
      setApiError(e.message);
    }

    setTimeout(() => { setStep("results"); scrollTop(); }, 1800);
  };

  const restart = () => {
    setStep("intro"); setQIndex(0); setAnswers({}); setContact({ name: "", email: "" }); setResult(null);
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: FS }} ref={topRef}>
      <style>{css}</style>

      {/* Brand header */}
      <div style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: ".85rem 1.5rem", textAlign: "center" }}>
        <a href="https://reroots.ca" style={{ textDecoration: "none" }}>
          <span style={{ fontFamily: FD, fontSize: "1.3rem", letterSpacing: ".28em", color: C.dark, fontWeight: 300 }}>
            RE<span style={{ color: C.pink }}>ROOTS</span>
          </span>
        </a>
        <div style={{ fontSize: ".55rem", letterSpacing: ".2em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, marginTop: ".2rem" }}>
          Biotech Skincare · Toronto, Canada
        </div>
      </div>

      <div style={{ maxWidth: 520, margin: "0 auto", padding: "2.5rem 1.25rem 4rem" }}>

        {/* INTRO */}
        {step === "intro" && (
          <div style={{ textAlign: "center", animation: "fadeUp .5s ease" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1.5rem", animation: "float 3s ease infinite" }}>🧬</div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: ".4rem", background: C.pinkFaint, border: `1px solid ${C.pink}25`, borderRadius: 20, padding: ".3rem .85rem", marginBottom: "1.25rem" }}>
              <span style={{ fontSize: ".62rem", color: C.pink, fontFamily: FS, fontWeight: 600 }}>87.5% match accuracy</span>
            </div>
            <h1 style={{ fontFamily: FD, fontSize: "clamp(1.8rem,5vw,2.5rem)", color: C.dark, fontWeight: 400, lineHeight: 1.25, marginBottom: ".75rem", letterSpacing: ".01em" }}>
              Find your personalised<br />
              <span style={{ color: C.pink, fontStyle: "italic" }}>PDRN ritual</span>
            </h1>
            <p style={{ fontSize: ".85rem", color: C.textDim, fontFamily: FS, lineHeight: 1.7, marginBottom: "2rem", maxWidth: 380, margin: "0 auto 2rem" }}>
              6 questions. 2 minutes. A science-backed protocol matched to your actual skin — not a generic routine.
            </p>

            <button className="btn-main" onClick={() => setStep("quiz")} style={{ marginBottom: "1.5rem" }} data-testid="quiz-start-btn">
              Start My Skin Assessment →
            </button>

            <div style={{ display: "flex", justifyContent: "center", gap: "1.5rem", flexWrap: "wrap" }}>
              {["2 min", "6 questions", "Free", "Health Canada compliant"].map((t, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: ".35rem", fontSize: ".65rem", color: C.textDim, fontFamily: FS }}>
                  <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.pink }} />
                  {t}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* QUIZ */}
        {step === "quiz" && (
          <QuestionScreen
            question={QUESTIONS[qIndex]}
            qIndex={qIndex}
            total={QUESTIONS.length}
            onAnswer={handleAnswer}
            currentAnswer={answers[QUESTIONS[qIndex].id]}
          />
        )}

        {/* CONTACT */}
        {step === "contact" && (
          <ContactScreen onSubmit={handleContactSubmit} loading={false} />
        )}

        {/* LOADING */}
        {step === "loading" && (
          <div style={{ textAlign: "center", padding: "4rem 0", animation: "fadeIn .3s ease" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "1.25rem", animation: "float 2s ease infinite" }}>⚗️</div>
            <h3 style={{ fontFamily: FD, fontSize: "1.4rem", color: C.dark, fontWeight: 300, marginBottom: ".5rem" }}>
              Analysing your skin profile
            </h3>
            <p style={{ fontSize: ".75rem", color: C.textDim, fontFamily: FS, marginBottom: "1.5rem" }}>
              Matching ingredients to your concerns...
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: ".4rem", maxWidth: 240, margin: "0 auto" }}>
              {["Scoring 6 answers", "Mapping to PDRN matrix", "Calibrating protocol", "Personalising results"].map((t, i) => (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: ".5rem", fontSize: ".68rem", color: C.textDim, fontFamily: FS, animation: `fadeUp .3s ${i * .35}s both`, opacity: 0 }}>
                  <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.pink, flexShrink: 0 }} />
                  {t}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* RESULTS */}
        {step === "results" && result && (
          <>
            <ResultsScreen result={result} contactInfo={contactInfo} />
            <div style={{ textAlign: "center", marginTop: "2rem" }}>
              <button onClick={restart}
                style={{ background: "none", border: "none", fontSize: ".68rem", color: C.textMuted, fontFamily: FS, cursor: "pointer", textDecoration: "underline" }}
                data-testid="quiz-retake-btn">
                Retake the quiz
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
