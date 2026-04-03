import { useState } from "react";
import { useNavigate } from "react-router-dom";

// ═══════════════════════════════════════════════════════════════════════════════
// DESIGN TOKENS
// ═══════════════════════════════════════════════════════════════════════════════
const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH = "#ffffff", WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const GREEN = "#4ade80";

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
// PROGRESS BAR
// ═══════════════════════════════════════════════════════════════════════════════
const ProgressBar = ({ current, total }) => (
  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
    {Array.from({ length: total }).map((_, i) => (
      <div key={i} style={{ 
        flex: 1, 
        height: 4, 
        borderRadius: 2, 
        background: i < current ? `linear-gradient(90deg, ${GOLD}, ${GOLD2})` : "rgba(201,168,76,0.15)",
        transition: "all 0.3s"
      }} />
    ))}
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 1: WELCOME
// ═══════════════════════════════════════════════════════════════════════════════
const WelcomeStep = ({ onNext, data, setData }) => (
  <div style={{ textAlign: "center", maxWidth: 500, margin: "0 auto" }}>
    <div style={{ marginBottom: 32, animation: "float 3s ease-in-out infinite" }}>
      <AuremLogo size={80} />
    </div>
    <h1 style={{ fontSize: 36, fontWeight: 400, margin: "0 0 16px", letterSpacing: "-0.02em" }}>
      Welcome to <span style={{ color: GOLD2 }}>AUREM</span>
    </h1>
    <p style={{ color: SV, fontSize: 16, lineHeight: 1.7, marginBottom: 40 }}>
      Let's set up your AI-powered business automation in just a few minutes. We'll customize everything to match your needs.
    </p>
    
    <div style={{ marginBottom: 32 }}>
      <input
        type="text"
        placeholder="What's your name?"
        value={data.name || ""}
        onChange={e => setData({ ...data, name: e.target.value })}
        style={{ 
          width: "100%", 
          padding: "16px 20px", 
          background: OB3, 
          border: `1px solid rgba(201,168,76,0.2)`, 
          borderRadius: 12, 
          color: WH, 
          fontSize: 16, 
          outline: "none",
          textAlign: "center"
        }}
      />
    </div>
    
    <button 
      onClick={onNext}
      disabled={!data.name}
      style={{ 
        padding: "16px 48px", 
        background: data.name ? `linear-gradient(135deg, ${GOLD}, ${GDIM})` : "rgba(201,168,76,0.2)", 
        border: "none", 
        borderRadius: 12, 
        color: data.name ? OB : MU, 
        fontWeight: 600, 
        cursor: data.name ? "pointer" : "default", 
        fontSize: 16,
        transition: "all 0.3s"
      }}
    >
      Let's Get Started →
    </button>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 2: BUSINESS INFO
// ═══════════════════════════════════════════════════════════════════════════════
const BusinessInfoStep = ({ onNext, onBack, data, setData }) => {
  const industries = [
    { id: "ecommerce", icon: "🛒", label: "E-Commerce" },
    { id: "saas", icon: "💻", label: "SaaS / Software" },
    { id: "agency", icon: "🏢", label: "Agency" },
    { id: "healthcare", icon: "🏥", label: "Healthcare" },
    { id: "finance", icon: "💰", label: "Finance" },
    { id: "retail", icon: "🏪", label: "Retail" },
    { id: "education", icon: "📚", label: "Education" },
    { id: "other", icon: "✨", label: "Other" },
  ];

  const sizes = [
    { id: "solo", label: "Just me" },
    { id: "small", label: "2-10 employees" },
    { id: "medium", label: "11-50 employees" },
    { id: "large", label: "51-200 employees" },
    { id: "enterprise", label: "200+ employees" },
  ];

  const canProceed = data.company && data.industry && data.size;

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", width: "100%", padding: "0 16px" }}>
      <h2 style={{ fontSize: "clamp(22px, 5vw, 28px)", fontWeight: 400, margin: "0 0 8px", textAlign: "center" }}>
        Tell us about your <span style={{ color: GOLD2 }}>business</span>
      </h2>
      <p style={{ color: MU, textAlign: "center", marginBottom: 24, fontSize: 14 }}>This helps us customize AUREM for your needs</p>
      
      <div style={{ marginBottom: 20 }}>
        <label style={{ display: "block", fontSize: 14, color: SV, marginBottom: 8 }}>Company Name</label>
        <input
          type="text"
          placeholder="Your company name"
          value={data.company || ""}
          onChange={e => setData({ ...data, company: e.target.value })}
          style={{ 
            width: "100%", 
            padding: "12px 16px", 
            background: OB3, 
            border: `1px solid rgba(201,168,76,0.2)`, 
            borderRadius: 10, 
            color: WH, 
            fontSize: 15, 
            outline: "none",
            boxSizing: "border-box"
          }}
        />
      </div>

      <div style={{ marginBottom: 20 }}>
        <label style={{ display: "block", fontSize: 14, color: SV, marginBottom: 8 }}>Industry</label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
          {industries.map(({ id, icon, label }) => (
            <div 
              key={id}
              onClick={() => setData({ ...data, industry: id })}
              style={{ 
                padding: "12px 8px", 
                background: data.industry === id ? "rgba(201,168,76,0.15)" : OB3, 
                border: `1px solid ${data.industry === id ? GOLD : "rgba(201,168,76,0.1)"}`, 
                borderRadius: 10, 
                cursor: "pointer",
                textAlign: "center",
                transition: "all 0.2s"
              }}
            >
              <div style={{ fontSize: 20, marginBottom: 4 }}>{icon}</div>
              <div style={{ fontSize: 11, color: data.industry === id ? GOLD : SV }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <label style={{ display: "block", fontSize: 14, color: SV, marginBottom: 8 }}>Team Size</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {sizes.map(({ id, label }) => (
            <div 
              key={id}
              onClick={() => setData({ ...data, size: id })}
              style={{ 
                padding: "10px 16px", 
                background: data.size === id ? "rgba(201,168,76,0.15)" : OB3, 
                border: `1px solid ${data.size === id ? GOLD : "rgba(201,168,76,0.1)"}`, 
                borderRadius: 8, 
                cursor: "pointer",
                fontSize: 12,
                color: data.size === id ? GOLD : SV,
                transition: "all 0.2s"
              }}
            >
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Fixed Navigation Buttons at Bottom */}
      <div style={{ 
        display: "flex", 
        gap: 12, 
        position: "sticky",
        bottom: 0,
        background: OB,
        padding: "16px 0",
        marginTop: 16
      }}>
        <button 
          onClick={onBack} 
          data-testid="onboarding-back-btn"
          style={{ 
            flex: 1, 
            padding: "16px", 
            background: "transparent", 
            border: `1px solid rgba(201,168,76,0.2)`, 
            borderRadius: 10, 
            color: MU, 
            cursor: "pointer", 
            fontSize: 14 
          }}
        >
          ← Back
        </button>
        <button 
          onClick={onNext}
          disabled={!canProceed}
          data-testid="onboarding-next-btn"
          style={{ 
            flex: 2, 
            padding: "16px", 
            background: canProceed ? `linear-gradient(135deg, ${GOLD}, ${GDIM})` : "rgba(201,168,76,0.2)", 
            border: "none", 
            borderRadius: 10, 
            color: canProceed ? OB : MU, 
            fontWeight: 600, 
            cursor: canProceed ? "pointer" : "default", 
            fontSize: 15 
          }}
        >
          Continue →
        </button>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 3: GOALS
// ═══════════════════════════════════════════════════════════════════════════════
const GoalsStep = ({ onNext, onBack, data, setData }) => {
  const goals = [
    { id: "support", icon: "💬", title: "Automate Customer Support", desc: "AI handles inquiries 24/7" },
    { id: "sales", icon: "📈", title: "Increase Sales & Conversions", desc: "AI-powered lead nurturing" },
    { id: "marketing", icon: "📧", title: "Automate Marketing", desc: "Email, WhatsApp, SMS campaigns" },
    { id: "analytics", icon: "📊", title: "Better Business Intelligence", desc: "Real-time insights & reporting" },
    { id: "operations", icon: "⚙️", title: "Streamline Operations", desc: "Automate repetitive tasks" },
    { id: "retention", icon: "❤️", title: "Improve Customer Retention", desc: "Reduce churn with AI" },
  ];

  const toggleGoal = (id) => {
    const current = data.goals || [];
    if (current.includes(id)) {
      setData({ ...data, goals: current.filter(g => g !== id) });
    } else {
      setData({ ...data, goals: [...current, id] });
    }
  };

  return (
    <div style={{ maxWidth: 650, margin: "0 auto" }}>
      <h2 style={{ fontSize: 28, fontWeight: 400, margin: "0 0 8px", textAlign: "center" }}>
        What do you want to <span style={{ color: GOLD2 }}>achieve</span>?
      </h2>
      <p style={{ color: MU, textAlign: "center", marginBottom: 40 }}>Select all that apply — we'll customize your setup</p>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginBottom: 40 }}>
        {goals.map(({ id, icon, title, desc }) => {
          const selected = (data.goals || []).includes(id);
          return (
            <div 
              key={id}
              onClick={() => toggleGoal(id)}
              style={{ 
                padding: "20px", 
                background: selected ? "rgba(201,168,76,0.1)" : OB3, 
                border: `1px solid ${selected ? GOLD : "rgba(201,168,76,0.1)"}`, 
                borderRadius: 12, 
                cursor: "pointer",
                transition: "all 0.2s",
                position: "relative"
              }}
            >
              {selected && (
                <div style={{ position: "absolute", top: 12, right: 12, width: 20, height: 20, borderRadius: "50%", background: GREEN, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ color: OB, fontSize: 12 }}>✓</span>
                </div>
              )}
              <div style={{ fontSize: 28, marginBottom: 10 }}>{icon}</div>
              <div style={{ fontSize: 15, fontWeight: 500, color: WH, marginBottom: 4 }}>{title}</div>
              <div style={{ fontSize: 13, color: MU }}>{desc}</div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={onBack} style={{ flex: 1, padding: "14px", background: "transparent", border: `1px solid rgba(201,168,76,0.2)`, borderRadius: 10, color: MU, cursor: "pointer", fontSize: 14 }}>← Back</button>
        <button 
          onClick={onNext}
          disabled={!(data.goals?.length > 0)}
          style={{ 
            flex: 2, 
            padding: "14px", 
            background: (data.goals?.length > 0) ? `linear-gradient(135deg, ${GOLD}, ${GDIM})` : "rgba(201,168,76,0.2)", 
            border: "none", 
            borderRadius: 10, 
            color: (data.goals?.length > 0) ? OB : MU, 
            fontWeight: 600, 
            cursor: (data.goals?.length > 0) ? "pointer" : "default", 
            fontSize: 14 
          }}
        >
          Continue →
        </button>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 4: INTEGRATIONS
// ═══════════════════════════════════════════════════════════════════════════════
const IntegrationsStep = ({ onNext, onBack, data, setData }) => {
  const integrations = [
    { id: "whatsapp", icon: "💬", name: "WhatsApp Business", desc: "Connect your WhatsApp for automated messaging", color: "#25D366" },
    { id: "email", icon: "📧", name: "Email (Gmail/Outlook)", desc: "Sync your email for AI-powered responses", color: "#EA4335" },
    { id: "shopify", icon: "🛒", name: "Shopify", desc: "Connect your store for order automation", color: "#96BF48" },
    { id: "stripe", icon: "💳", name: "Stripe", desc: "Payment data for revenue analytics", color: "#635BFF" },
    { id: "hubspot", icon: "🔶", name: "HubSpot", desc: "Sync contacts and deals", color: "#FF7A59" },
    { id: "slack", icon: "💼", name: "Slack", desc: "Get AI alerts in your workspace", color: "#4A154B" },
  ];

  const toggleIntegration = (id) => {
    const current = data.integrations || [];
    if (current.includes(id)) {
      setData({ ...data, integrations: current.filter(i => i !== id) });
    } else {
      setData({ ...data, integrations: [...current, id] });
    }
  };

  return (
    <div style={{ maxWidth: 600, margin: "0 auto" }}>
      <h2 style={{ fontSize: 28, fontWeight: 400, margin: "0 0 8px", textAlign: "center" }}>
        Connect your <span style={{ color: GOLD2 }}>tools</span>
      </h2>
      <p style={{ color: MU, textAlign: "center", marginBottom: 40 }}>Select the integrations you want to set up (you can add more later)</p>
      
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 40 }}>
        {integrations.map(({ id, icon, name, desc, color }) => {
          const selected = (data.integrations || []).includes(id);
          return (
            <div 
              key={id}
              onClick={() => toggleIntegration(id)}
              style={{ 
                padding: "16px 20px", 
                background: selected ? "rgba(201,168,76,0.08)" : OB3, 
                border: `1px solid ${selected ? GOLD : "rgba(201,168,76,0.1)"}`, 
                borderRadius: 12, 
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 16,
                transition: "all 0.2s"
              }}
            >
              <div style={{ fontSize: 28 }}>{icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 500, color: WH }}>{name}</div>
                <div style={{ fontSize: 12, color: MU }}>{desc}</div>
              </div>
              <div style={{ 
                width: 24, 
                height: 24, 
                borderRadius: 6, 
                border: `2px solid ${selected ? GREEN : "rgba(201,168,76,0.3)"}`,
                background: selected ? GREEN : "transparent",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s"
              }}>
                {selected && <span style={{ color: OB, fontSize: 14, fontWeight: "bold" }}>✓</span>}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={onBack} style={{ flex: 1, padding: "14px", background: "transparent", border: `1px solid rgba(201,168,76,0.2)`, borderRadius: 10, color: MU, cursor: "pointer", fontSize: 14 }}>← Back</button>
        <button 
          onClick={onNext}
          style={{ 
            flex: 2, 
            padding: "14px", 
            background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, 
            border: "none", 
            borderRadius: 10, 
            color: OB, 
            fontWeight: 600, 
            cursor: "pointer", 
            fontSize: 14 
          }}
        >
          {(data.integrations?.length > 0) ? "Continue →" : "Skip for now →"}
        </button>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 5: INVITE TEAM
// ═══════════════════════════════════════════════════════════════════════════════
const InviteTeamStep = ({ onNext, onBack, data, setData }) => {
  const [email, setEmail] = useState("");
  
  const addTeamMember = () => {
    if (email && email.includes("@")) {
      setData({ ...data, team: [...(data.team || []), email] });
      setEmail("");
    }
  };

  const removeTeamMember = (e) => {
    setData({ ...data, team: (data.team || []).filter(t => t !== e) });
  };

  return (
    <div style={{ maxWidth: 500, margin: "0 auto" }}>
      <h2 style={{ fontSize: 28, fontWeight: 400, margin: "0 0 8px", textAlign: "center" }}>
        Invite your <span style={{ color: GOLD2 }}>team</span>
      </h2>
      <p style={{ color: MU, textAlign: "center", marginBottom: 40 }}>Add team members who will use AUREM with you</p>
      
      <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
        <input
          type="email"
          placeholder="colleague@company.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          onKeyDown={e => e.key === "Enter" && addTeamMember()}
          style={{ 
            flex: 1, 
            padding: "14px 18px", 
            background: OB3, 
            border: `1px solid rgba(201,168,76,0.2)`, 
            borderRadius: 10, 
            color: WH, 
            fontSize: 15, 
            outline: "none"
          }}
        />
        <button 
          onClick={addTeamMember}
          style={{ 
            padding: "14px 20px", 
            background: "rgba(201,168,76,0.15)", 
            border: `1px solid ${GOLD}`, 
            borderRadius: 10, 
            color: GOLD, 
            cursor: "pointer", 
            fontSize: 14 
          }}
        >
          + Add
        </button>
      </div>

      {(data.team?.length > 0) && (
        <div style={{ marginBottom: 32, padding: 16, background: OB3, borderRadius: 12, border: "1px solid rgba(201,168,76,0.1)" }}>
          <div style={{ fontSize: 12, color: MU, marginBottom: 12 }}>TEAM MEMBERS ({data.team.length})</div>
          {data.team.map(e => (
            <div key={e} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid rgba(201,168,76,0.05)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, display: "flex", alignItems: "center", justifyContent: "center", color: OB, fontSize: 12, fontWeight: 600 }}>
                  {e[0].toUpperCase()}
                </div>
                <span style={{ color: WH2, fontSize: 14 }}>{e}</span>
              </div>
              <button onClick={() => removeTeamMember(e)} style={{ background: "none", border: "none", color: MU, cursor: "pointer", fontSize: 18 }}>×</button>
            </div>
          ))}
        </div>
      )}

      {!(data.team?.length > 0) && (
        <div style={{ textAlign: "center", padding: 32, background: OB3, borderRadius: 12, border: "1px dashed rgba(201,168,76,0.2)", marginBottom: 32 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>👥</div>
          <div style={{ color: MU, fontSize: 14 }}>No team members added yet</div>
        </div>
      )}

      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={onBack} style={{ flex: 1, padding: "14px", background: "transparent", border: `1px solid rgba(201,168,76,0.2)`, borderRadius: 10, color: MU, cursor: "pointer", fontSize: 14 }}>← Back</button>
        <button 
          onClick={onNext}
          style={{ 
            flex: 2, 
            padding: "14px", 
            background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, 
            border: "none", 
            borderRadius: 10, 
            color: OB, 
            fontWeight: 600, 
            cursor: "pointer", 
            fontSize: 14 
          }}
        >
          {(data.team?.length > 0) ? "Continue →" : "Skip for now →"}
        </button>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 6: COMPLETE
// ═══════════════════════════════════════════════════════════════════════════════
const CompleteStep = ({ data, onLaunch }) => (
  <div style={{ textAlign: "center", maxWidth: 500, margin: "0 auto" }}>
    <div style={{ 
      width: 100, 
      height: 100, 
      borderRadius: "50%", 
      background: `linear-gradient(135deg, rgba(74,222,128,0.2), rgba(74,222,128,0.05))`,
      border: `2px solid ${GREEN}`,
      display: "flex", 
      alignItems: "center", 
      justifyContent: "center",
      margin: "0 auto 32px",
      animation: "pulse 2s infinite"
    }}>
      <span style={{ fontSize: 48 }}>✓</span>
    </div>
    
    <h1 style={{ fontSize: 36, fontWeight: 400, margin: "0 0 16px" }}>
      You're all set, <span style={{ color: GOLD2 }}>{data.name}!</span>
    </h1>
    <p style={{ color: SV, fontSize: 16, lineHeight: 1.7, marginBottom: 40 }}>
      AUREM is ready to transform {data.company}. Your AI workforce is standing by.
    </p>

    <div style={{ background: OB3, borderRadius: 16, padding: 24, marginBottom: 32, textAlign: "left" }}>
      <div style={{ fontSize: 12, color: GDIM, letterSpacing: "0.1em", marginBottom: 16 }}>YOUR SETUP SUMMARY</div>
      
      <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid rgba(201,168,76,0.1)" }}>
        <span style={{ color: MU }}>Company</span>
        <span style={{ color: WH2 }}>{data.company}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid rgba(201,168,76,0.1)" }}>
        <span style={{ color: MU }}>Industry</span>
        <span style={{ color: WH2, textTransform: "capitalize" }}>{data.industry}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid rgba(201,168,76,0.1)" }}>
        <span style={{ color: MU }}>Goals</span>
        <span style={{ color: GOLD }}>{data.goals?.length || 0} selected</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid rgba(201,168,76,0.1)" }}>
        <span style={{ color: MU }}>Integrations</span>
        <span style={{ color: GOLD }}>{data.integrations?.length || 0} connected</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0" }}>
        <span style={{ color: MU }}>Team Members</span>
        <span style={{ color: GOLD }}>{data.team?.length || 0} invited</span>
      </div>
    </div>

    <button 
      onClick={onLaunch}
      style={{ 
        width: "100%",
        padding: "18px 48px", 
        background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, 
        border: "none", 
        borderRadius: 12, 
        color: OB, 
        fontWeight: 600, 
        cursor: "pointer", 
        fontSize: 18,
        boxShadow: "0 8px 32px rgba(201,168,76,0.3)"
      }}
    >
      🚀 Launch AUREM Platform
    </button>
    
    <p style={{ color: MU, fontSize: 13, marginTop: 16 }}>
      Your 14-day free trial starts now. No credit card required.
    </p>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN ONBOARDING COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
export default function AuremOnboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [data, setData] = useState({});
  const totalSteps = 6;

  const handleLaunch = () => {
    // Save onboarding data to localStorage
    localStorage.setItem("aurem_onboarding", JSON.stringify(data));
    localStorage.setItem("aurem_onboarded", "true");
    navigate("/aurem-ai");
  };

  return (
    <div style={{ 
      fontFamily: "'Inter', system-ui, sans-serif", 
      background: OB, 
      color: WH2, 
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      position: "fixed",
      top: 0, left: 0, right: 0, bottom: 0,
      zIndex: 99999
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
        @keyframes pulse { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.05);opacity:0.8} }
        input::placeholder { color: ${MU}; }
      `}</style>

      {/* Header */}
      <div style={{ padding: "24px 48px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <AuremLogo size={36} />
          <span style={{ fontSize: 18, letterSpacing: "0.15em", color: GOLD2, fontWeight: 300 }}>AUREM</span>
        </div>
        <div style={{ color: MU, fontSize: 13 }}>Step {step} of {totalSteps}</div>
      </div>

      {/* Progress */}
      <div style={{ padding: "0 48px 32px" }}>
        <ProgressBar current={step} total={totalSteps} />
      </div>

      {/* Content */}
      <div style={{ 
        flex: 1, 
        display: "flex", 
        alignItems: step === 1 || step === 6 ? "center" : "flex-start", 
        justifyContent: "center", 
        padding: "0 16px 32px",
        overflowY: "auto",
        WebkitOverflowScrolling: "touch"
      }}>
        {step === 1 && <WelcomeStep onNext={() => setStep(2)} data={data} setData={setData} />}
        {step === 2 && <BusinessInfoStep onNext={() => setStep(3)} onBack={() => setStep(1)} data={data} setData={setData} />}
        {step === 3 && <GoalsStep onNext={() => setStep(4)} onBack={() => setStep(2)} data={data} setData={setData} />}
        {step === 4 && <IntegrationsStep onNext={() => setStep(5)} onBack={() => setStep(3)} data={data} setData={setData} />}
        {step === 5 && <InviteTeamStep onNext={() => setStep(6)} onBack={() => setStep(4)} data={data} setData={setData} />}
        {step === 6 && <CompleteStep data={data} onLaunch={handleLaunch} />}
      </div>
    </div>
  );
}
