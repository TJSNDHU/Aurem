import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

// ═══════════════════════════════════════════════════════════════════════════════
// DESIGN TOKENS
// ═══════════════════════════════════════════════════════════════════════════════
const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH = "#ffffff", WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";

// ═══════════════════════════════════════════════════════════════════════════════
// AUREM LOGO
// ═══════════════════════════════════════════════════════════════════════════════
const AuremLogo = ({ size = 40 }) => (
  <div style={{ width: size, height: size, border: `1px solid ${GDIM}`, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}>
    <svg viewBox="0 0 24 24" fill="none" stroke={GOLD} strokeWidth="1.2" width={size * 0.4} height={size * 0.4}>
      <circle cx="12" cy="12" r="3.5"/>
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2"/>
    </svg>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// ANIMATED COUNTER
// ═══════════════════════════════════════════════════════════════════════════════
const Counter = ({ end, suffix = "", duration = 2000 }) => {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    let start = 0;
    const increment = end / (duration / 16);
    const timer = setInterval(() => {
      start += increment;
      if (start >= end) {
        setCount(end);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [end, duration]);
  
  return <span>{count.toLocaleString()}{suffix}</span>;
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN LANDING PAGE
// ═══════════════════════════════════════════════════════════════════════════════
export default function AuremLanding() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (email) {
      setSubmitted(true);
      // Here you would send to your backend
    }
  };

  const features = [
    {
      icon: "⚡",
      title: "AI Agent Swarm",
      desc: "5 autonomous agents work 24/7 — Scout, Architect, Envoy, Closer, and Orchestrator handle everything from market analysis to customer conversion.",
      stats: "50+ tasks/hour"
    },
    {
      icon: "◎",
      title: "Omnichannel Automation",
      desc: "WhatsApp, Email, SMS — all managed by AI. Personalized messages at scale with zero manual effort.",
      stats: "10K+ messages/day"
    },
    {
      icon: "◈",
      title: "Business Intelligence",
      desc: "Real-time analytics, revenue tracking, customer insights, and growth recommendations powered by AI.",
      stats: "360° visibility"
    },
    {
      icon: "⬡",
      title: "CRM Connect",
      desc: "AI-powered customer relationship management. Automatic segmentation, LTV scoring, and churn prediction.",
      stats: "98% accuracy"
    },
    {
      icon: "✦",
      title: "Voice AI",
      desc: "Speak to AUREM, and it speaks back. Natural language interface for hands-free operation.",
      stats: "Multi-language"
    },
    {
      icon: "◉",
      title: "API Gateway",
      desc: "Connect AUREM to any system. RESTful APIs, webhooks, and pre-built integrations for popular tools.",
      stats: "99.9% uptime"
    }
  ];

  const useCases = [
    { tab: "E-Commerce", icon: "🛒", content: "Automate abandoned cart recovery, send personalized product recommendations, handle customer support, and manage inventory alerts — all while you sleep." },
    { tab: "SaaS", icon: "💻", content: "Qualify leads automatically, onboard new users with AI guidance, reduce churn with proactive engagement, and scale support without scaling headcount." },
    { tab: "Agencies", icon: "🏢", content: "Manage multiple client accounts, automate reporting, handle client communications, and deliver white-label AI solutions under your brand." },
    { tab: "Healthcare", icon: "🏥", content: "Patient engagement, appointment reminders, follow-up care coordination, and HIPAA-compliant communication automation." }
  ];

  const testimonials = [
    { name: "Sarah Chen", role: "CEO, Luxe Beauty", quote: "AUREM replaced our entire support team of 5 with one AI that works 24/7. ROI was visible in week one.", avatar: "SC" },
    { name: "Marcus Williams", role: "Founder, TechScale", quote: "The Agent Swarm is like having a team of specialists working around the clock. Our conversion rate jumped 34%.", avatar: "MW" },
    { name: "Emma Thompson", role: "COO, RetailPro", quote: "We saved $12,000/month on tools alone. AUREM replaced Intercom, HubSpot, and Mailchimp for us.", avatar: "ET" }
  ];

  const pricing = [
    { 
      name: "Starter", 
      price: 99, 
      desc: "Perfect for small businesses",
      features: ["AI Chat Assistant", "1,000 AI queries/month", "Email automation", "Basic analytics", "Email support"],
      cta: "Start Free Trial"
    },
    { 
      name: "Growth", 
      price: 299, 
      desc: "For scaling businesses",
      features: ["Everything in Starter", "10,000 AI queries/month", "WhatsApp integration", "CRM Connect", "Agent Swarm (3 agents)", "Priority support"],
      cta: "Start Free Trial",
      popular: true
    },
    { 
      name: "Enterprise", 
      price: 499, 
      desc: "For large operations",
      features: ["Everything in Growth", "Unlimited AI queries", "Full Agent Swarm (5 agents)", "API Gateway access", "Custom integrations", "Dedicated success manager", "SLA guarantee"],
      cta: "Contact Sales"
    }
  ];

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", background: OB, color: WH2, minHeight: "100vh", overflowX: "hidden" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
        @keyframes gradient { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
        @keyframes fadeInUp { from{opacity:0;transform:translateY(30px)} to{opacity:1;transform:translateY(0)} }
        .fade-in { animation: fadeInUp 0.8s ease forwards; }
        .hover-lift { transition: transform 0.3s, box-shadow 0.3s; }
        .hover-lift:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(201,168,76,0.15); }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: rgba(201,168,76,0.3); border-radius: 4px; }
        ::-webkit-scrollbar-track { background: ${OB2}; }
      `}</style>

      {/* ════════════════════════════════════════════════════════════════════════
          NAVIGATION
          ════════════════════════════════════════════════════════════════════════ */}
      <nav style={{ 
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 1000,
        padding: "16px 48px",
        background: "rgba(10,10,15,0.9)",
        backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(201,168,76,0.1)",
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <AuremLogo size={36} />
          <span style={{ fontSize: 20, letterSpacing: "0.2em", color: GOLD2, fontWeight: 300 }}>AUREM</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          <a href="#features" style={{ color: MU, textDecoration: "none", fontSize: 14, transition: "color 0.2s" }} onMouseEnter={e => e.target.style.color = GOLD} onMouseLeave={e => e.target.style.color = MU}>Features</a>
          <a href="#pricing" style={{ color: MU, textDecoration: "none", fontSize: 14, transition: "color 0.2s" }} onMouseEnter={e => e.target.style.color = GOLD} onMouseLeave={e => e.target.style.color = MU}>Pricing</a>
          <a href="#testimonials" style={{ color: MU, textDecoration: "none", fontSize: 14, transition: "color 0.2s" }} onMouseEnter={e => e.target.style.color = GOLD} onMouseLeave={e => e.target.style.color = MU}>Testimonials</a>
          <button onClick={() => navigate("/aurem-ai")} style={{ padding: "10px 20px", background: "transparent", border: `1px solid rgba(201,168,76,0.3)`, borderRadius: 6, color: GOLD2, fontWeight: 500, cursor: "pointer", fontSize: 14 }}>Login</button>
          <button onClick={() => navigate("/aurem-onboarding")} style={{ padding: "10px 24px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 6, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 14 }}>Get Started →</button>
        </div>
      </nav>

      {/* ════════════════════════════════════════════════════════════════════════
          HERO SECTION
          ════════════════════════════════════════════════════════════════════════ */}
      <section style={{ 
        minHeight: "100vh", 
        display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center",
        textAlign: "center",
        padding: "120px 24px 80px",
        position: "relative",
        overflow: "hidden"
      }}>
        {/* Background gradient orbs */}
        <div style={{ position: "absolute", top: "10%", left: "10%", width: 400, height: 400, background: `radial-gradient(circle, rgba(201,168,76,0.1) 0%, transparent 70%)`, filter: "blur(60px)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", bottom: "20%", right: "10%", width: 300, height: 300, background: `radial-gradient(circle, rgba(201,168,76,0.08) 0%, transparent 70%)`, filter: "blur(40px)", pointerEvents: "none" }} />
        
        <div className="fade-in" style={{ marginBottom: 24 }}>
          <span style={{ padding: "8px 16px", background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.2)", borderRadius: 20, fontSize: 12, letterSpacing: "0.1em", color: GOLD }}>AI-POWERED BUSINESS AUTOMATION</span>
        </div>
        
        <h1 className="fade-in" style={{ fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 300, lineHeight: 1.1, margin: "0 0 24px", maxWidth: 900, letterSpacing: "-0.02em" }}>
          Your Business.<br/>
          <span style={{ color: GOLD2 }}>Automated by AI.</span>
        </h1>
        
        <p className="fade-in" style={{ fontSize: 18, color: SV, maxWidth: 600, lineHeight: 1.7, margin: "0 0 40px" }}>
          AUREM deploys an autonomous AI workforce that handles customer engagement, sales automation, and business intelligence — 24/7, without human intervention.
        </p>
        
        <div className="fade-in" style={{ display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
          <button onClick={() => navigate("/aurem-onboarding")} className="hover-lift" style={{ padding: "16px 32px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 8, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 16 }}>
            Start Free Trial →
          </button>
          <button className="hover-lift" style={{ padding: "16px 32px", background: "transparent", border: `1px solid rgba(201,168,76,0.3)`, borderRadius: 8, color: GOLD2, fontWeight: 500, cursor: "pointer", fontSize: 16 }}>
            Watch Demo
          </button>
        </div>

        {/* Stats */}
        <div className="fade-in" style={{ display: "flex", gap: 48, marginTop: 80, flexWrap: "wrap", justifyContent: "center" }}>
          {[
            { value: 2847, suffix: "+", label: "Active Businesses" },
            { value: 12, suffix: "M+", label: "AI Queries Processed" },
            { value: 340, suffix: "%", label: "Avg. ROI Increase" },
            { value: 99.9, suffix: "%", label: "Uptime Guaranteed" }
          ].map(({ value, suffix, label }) => (
            <div key={label} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, fontWeight: 600, color: GOLD2, fontFamily: "monospace" }}>
                <Counter end={value} suffix={suffix} />
              </div>
              <div style={{ fontSize: 12, color: MU, letterSpacing: "0.1em", marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════════
          FEATURES SECTION
          ════════════════════════════════════════════════════════════════════════ */}
      <section id="features" style={{ padding: "100px 48px", background: OB2 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 64 }}>
            <span style={{ fontSize: 12, letterSpacing: "0.2em", color: GDIM }}>CAPABILITIES</span>
            <h2 style={{ fontSize: 40, fontWeight: 400, margin: "16px 0 0", letterSpacing: "-0.02em" }}>
              Everything Your Business Needs.<br/>
              <span style={{ color: GOLD2 }}>In One AI Platform.</span>
            </h2>
          </div>
          
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 24 }}>
            {features.map(({ icon, title, desc, stats }) => (
              <div key={title} className="hover-lift" style={{ 
                padding: 32, 
                background: OB3, 
                border: "1px solid rgba(201,168,76,0.1)", 
                borderRadius: 16,
                cursor: "pointer"
              }}>
                <div style={{ fontSize: 32, marginBottom: 16 }}>{icon}</div>
                <h3 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 12px", color: WH }}>{title}</h3>
                <p style={{ fontSize: 14, color: SV, lineHeight: 1.7, margin: "0 0 16px" }}>{desc}</p>
                <div style={{ fontSize: 12, color: GOLD, letterSpacing: "0.05em", padding: "6px 12px", background: "rgba(201,168,76,0.1)", borderRadius: 20, display: "inline-block" }}>{stats}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════════
          USE CASES
          ════════════════════════════════════════════════════════════════════════ */}
      <section style={{ padding: "100px 48px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 48 }}>
            <span style={{ fontSize: 12, letterSpacing: "0.2em", color: GDIM }}>USE CASES</span>
            <h2 style={{ fontSize: 40, fontWeight: 400, margin: "16px 0 0" }}>Built for <span style={{ color: GOLD2 }}>Every Industry</span></h2>
          </div>
          
          <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 32, flexWrap: "wrap" }}>
            {useCases.map(({ tab, icon }, i) => (
              <button key={tab} onClick={() => setActiveTab(i)} style={{ 
                padding: "12px 24px", 
                background: activeTab === i ? "rgba(201,168,76,0.15)" : "transparent", 
                border: `1px solid ${activeTab === i ? GOLD : "rgba(201,168,76,0.2)"}`, 
                borderRadius: 8, 
                color: activeTab === i ? GOLD : MU, 
                cursor: "pointer", 
                fontSize: 14,
                display: "flex", alignItems: "center", gap: 8,
                transition: "all 0.2s"
              }}>
                <span>{icon}</span> {tab}
              </button>
            ))}
          </div>
          
          <div style={{ padding: 40, background: OB3, border: "1px solid rgba(201,168,76,0.1)", borderRadius: 16, textAlign: "center" }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>{useCases[activeTab].icon}</div>
            <p style={{ fontSize: 18, color: SV, lineHeight: 1.8, maxWidth: 600, margin: "0 auto" }}>{useCases[activeTab].content}</p>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════════
          TESTIMONIALS
          ════════════════════════════════════════════════════════════════════════ */}
      <section id="testimonials" style={{ padding: "100px 48px", background: OB2 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 64 }}>
            <span style={{ fontSize: 12, letterSpacing: "0.2em", color: GDIM }}>TESTIMONIALS</span>
            <h2 style={{ fontSize: 40, fontWeight: 400, margin: "16px 0 0" }}>Trusted by <span style={{ color: GOLD2 }}>Industry Leaders</span></h2>
          </div>
          
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24 }}>
            {testimonials.map(({ name, role, quote, avatar }) => (
              <div key={name} className="hover-lift" style={{ padding: 32, background: OB3, border: "1px solid rgba(201,168,76,0.1)", borderRadius: 16 }}>
                <p style={{ fontSize: 16, color: WH2, lineHeight: 1.8, margin: "0 0 24px", fontStyle: "italic" }}>"{quote}"</p>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 48, height: 48, borderRadius: "50%", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, display: "flex", alignItems: "center", justifyContent: "center", color: OB, fontWeight: 600, fontSize: 14 }}>{avatar}</div>
                  <div>
                    <div style={{ fontWeight: 500, color: WH }}>{name}</div>
                    <div style={{ fontSize: 13, color: MU }}>{role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════════
          PRICING
          ════════════════════════════════════════════════════════════════════════ */}
      <section id="pricing" style={{ padding: "100px 48px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 64 }}>
            <span style={{ fontSize: 12, letterSpacing: "0.2em", color: GDIM }}>PRICING</span>
            <h2 style={{ fontSize: 40, fontWeight: 400, margin: "16px 0 0" }}>Simple, <span style={{ color: GOLD2 }}>Transparent Pricing</span></h2>
            <p style={{ color: MU, marginTop: 16 }}>Start free. Scale as you grow. No hidden fees.</p>
          </div>
          
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 24 }}>
            {pricing.map(({ name, price, desc, features, cta, popular }) => (
              <div key={name} className="hover-lift" style={{ 
                padding: 32, 
                background: popular ? `linear-gradient(135deg, rgba(201,168,76,0.1) 0%, rgba(201,168,76,0.02) 100%)` : OB3, 
                border: `1px solid ${popular ? GOLD : "rgba(201,168,76,0.1)"}`, 
                borderRadius: 16,
                position: "relative"
              }}>
                {popular && (
                  <div style={{ position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)", padding: "6px 16px", background: GOLD, borderRadius: 20, fontSize: 11, fontWeight: 600, color: OB, letterSpacing: "0.05em" }}>MOST POPULAR</div>
                )}
                <div style={{ fontSize: 14, color: MU, marginBottom: 8 }}>{desc}</div>
                <div style={{ fontSize: 24, fontWeight: 500, color: WH, marginBottom: 4 }}>{name}</div>
                <div style={{ marginBottom: 24 }}>
                  <span style={{ fontSize: 48, fontWeight: 600, color: GOLD2 }}>${price}</span>
                  <span style={{ color: MU }}>/month</span>
                </div>
                <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px" }}>
                  {features.map(f => (
                    <li key={f} style={{ padding: "10px 0", borderBottom: "1px solid rgba(201,168,76,0.05)", color: SV, fontSize: 14, display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ color: GOLD }}>✓</span> {f}
                    </li>
                  ))}
                </ul>
                <button style={{ 
                  width: "100%", 
                  padding: "14px", 
                  background: popular ? `linear-gradient(135deg, ${GOLD}, ${GDIM})` : "transparent", 
                  border: popular ? "none" : `1px solid rgba(201,168,76,0.3)`, 
                  borderRadius: 8, 
                  color: popular ? OB : GOLD2, 
                  fontWeight: 600, 
                  cursor: "pointer", 
                  fontSize: 14 
                }}>{cta}</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════════
          CTA SECTION
          ════════════════════════════════════════════════════════════════════════ */}
      <section style={{ padding: "100px 48px", background: `linear-gradient(135deg, rgba(201,168,76,0.1) 0%, ${OB2} 100%)` }}>
        <div style={{ maxWidth: 700, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontSize: 40, fontWeight: 400, margin: "0 0 16px" }}>Ready to <span style={{ color: GOLD2 }}>Transform</span> Your Business?</h2>
          <p style={{ color: SV, fontSize: 18, marginBottom: 40 }}>Join 2,847+ businesses already using AUREM to automate and scale.</p>
          
          {!submitted ? (
            <form onSubmit={handleSubmit} style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
              <input 
                type="email" 
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="Enter your email"
                style={{ padding: "16px 24px", background: OB3, border: "1px solid rgba(201,168,76,0.2)", borderRadius: 8, color: WH, fontSize: 16, width: 300, outline: "none" }}
              />
              <button type="submit" style={{ padding: "16px 32px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 8, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 16 }}>
                Get Started Free
              </button>
            </form>
          ) : (
            <div style={{ padding: 24, background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)", borderRadius: 12 }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>✓</div>
              <div style={{ color: "#4ade80", fontSize: 18 }}>You're on the list! We'll be in touch soon.</div>
            </div>
          )}
          
          <p style={{ color: MU, fontSize: 13, marginTop: 16 }}>No credit card required · 14-day free trial · Cancel anytime</p>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════════
          FOOTER
          ════════════════════════════════════════════════════════════════════════ */}
      <footer style={{ padding: "60px 48px", borderTop: "1px solid rgba(201,168,76,0.1)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <AuremLogo size={32} />
            <span style={{ fontSize: 16, letterSpacing: "0.15em", color: GOLD2, fontWeight: 300 }}>AUREM</span>
          </div>
          <div style={{ display: "flex", gap: 32 }}>
            <a href="#" style={{ color: MU, textDecoration: "none", fontSize: 13 }}>Privacy</a>
            <a href="#" style={{ color: MU, textDecoration: "none", fontSize: 13 }}>Terms</a>
            <a href="#" style={{ color: MU, textDecoration: "none", fontSize: 13 }}>Contact</a>
          </div>
          <div style={{ color: MU, fontSize: 13 }}>© 2025 AUREM. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
