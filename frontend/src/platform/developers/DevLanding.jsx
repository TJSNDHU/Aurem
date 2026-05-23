/**
 * /developers — Landing (Public)
 * AUREM homepage aesthetic: Cinzel serif headline with gold/orange
 * gradient, Jost body, eyebrow pill, primary CTA gradient, ghost CTA.
 * Hero copy must be EXACT: "Build with an autonomous CTO. 1000 tokens free."
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Code2, Github, Zap, Shield } from "lucide-react";
import DeveloperShell from "./DeveloperShell";

export default function DevLanding() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [betaCount, setBetaCount] = useState(null);

  React.useEffect(() => {
    let cancelled = false;
    fetch(`${process.env.REACT_APP_BACKEND_URL || ""}/api/developers/public/stats`)
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j && !cancelled) setBetaCount(j.verified_developers || 0); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  function go(e) {
    e.preventDefault();
    if (!email.includes("@")) return;
    navigate(`/developers/signup?email=${encodeURIComponent(email)}`);
  }

  return (
    <DeveloperShell mode="landing">
      {/* HERO */}
      <section data-testid="dev-landing-hero"
               style={{
                 minHeight: "92vh",
                 display: "flex", alignItems: "center", justifyContent: "center",
                 textAlign: "center", padding: "120px 5% 80px",
               }}>
        <div style={{ maxWidth: 860 }}>
          <div className="dev-eyebrow" style={{ marginBottom: 32 }}>
            <span className="dot" />
            AUREM / DEVELOPERS / IN PUBLIC BETA
          </div>
          <h1 data-testid="dev-landing-hero-headline" className="dev-title">
            <span className="t1">Build with</span>
            <span className="t2">AUREM CTO</span>
          </h1>
          <p className="dev-punch" style={{ margin: "20px auto 44px" }}>
            <strong>1000 tokens free</strong> on signup. AUREM CTO plans, writes,
            tests and ships features into your repo — you just review the
            pull request.
          </p>
          <form onSubmit={go}
                 style={{ display: "flex", gap: 10, maxWidth: 520,
                           margin: "0 auto 12px", flexWrap: "wrap",
                           justifyContent: "center" }}>
            <input data-testid="hero-email-input" type="email" required
                    placeholder="you@company.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="dev-input"
                    style={{ flex: "1 1 240px", minWidth: 240 }} />
            <button data-testid="hero-submit-btn" type="submit"
                     className="dev-btn-primary">
              Claim 1000 tokens <ArrowRight size={15} />
            </button>
          </form>
          <p style={{ fontSize: 12, color: "#4A4560",
                       letterSpacing: "0.05em", marginTop: 12 }}>
            No credit card. BYOK any time to stop deductions on your own LLM calls.
          </p>
        </div>
      </section>

      {/* 3-card belt — same look as homepage .pain-cards */}
      <section style={{ padding: "60px 5% 100px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 48 }}>
            <span className="dev-section-label">Why developers like it</span>
            <h2 className="dev-section-title">A real teammate. Not a chatbot.</h2>
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 16,
          }}>
            {[
              { icon: Zap, tag: "PLAN → SHIP",
                text: "AUREM CTO opens a PR with a working feature, plus tests, in minutes." },
              { icon: Github, tag: "GROUNDED",
                text: "Reads your repo first. Respects existing patterns, conventions, file layout." },
              { icon: Shield, tag: "BYOK READY",
                text: "Bring your own Anthropic, DeepSeek or Gemini key. Free tokens just remove the setup tax." },
            ].map((b, i) => (
              <div key={i} className="dev-feature-card"
                    data-testid="dev-landing-feature">
                <b.icon size={20} style={{ color: "#FF6B00", marginBottom: 16 }} />
                <span style={{
                  display: "block",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10, letterSpacing: "0.18em",
                  color: "#C9A84C", marginBottom: 12,
                }}>{b.tag}</span>
                <p style={{ fontSize: 15, color: "#F0EDE8",
                              lineHeight: 1.65 }}>{b.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cost strip */}
      <section style={{ borderTop: "1px solid rgba(201,168,76,0.10)",
                         padding: "30px 5%" }}>
        <div style={{ maxWidth: 960, margin: "0 auto",
                       display: "flex", flexWrap: "wrap",
                       gap: "12px 32px",
                       fontFamily: "'JetBrains Mono', monospace",
                       fontSize: 12, color: "#7A7590",
                       letterSpacing: "0.05em" }}>
          <span>chat = 1 token</span>
          <span>file edit = 2</span>
          <span>test run = 3</span>
          <span>deploy = 5</span>
          <span>fork context = 10</span>
          <Code2 size={14} style={{ color: "#FF6B00", marginLeft: "auto" }} />
        </div>
      </section>

      <footer style={{ borderTop: "1px solid rgba(255,107,0,0.10)",
                        padding: "30px 5% 40px",
                        textAlign: "center",
                        fontSize: 12, color: "#4A4560",
                        letterSpacing: "0.05em" }}>
        © 2026 AUREM · Built in Canada · PIPEDA-compliant
      </footer>
    </DeveloperShell>
  );
}
