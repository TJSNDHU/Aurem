/**
 * /developers/signup — Multi-step signup with OTP (Public)
 * Uses landing-mode shell so unauthenticated users still see the
 * homepage chrome (orange/gold), not the dashboard sidebar.
 */
import React, { useState } from "react";
import SEO from "../../components/SEO";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Mail, CheckCircle2 } from "lucide-react";
import DeveloperShell, { setDevJwt } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevSignup() {
  const navigate = useNavigate();
  const [params]  = useSearchParams();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    email:           params.get("email")  || "",
    name:            params.get("name")   || "",
    password:        "",
    github_username: "",
    build_intent:    params.get("intent") || "",
    referral_code:   "",
    otp:             "",
  });
  const [busy, setBusy]       = useState(false);
  const [error, setError]     = useState(null);
  const [signupInfo, setSI]   = useState(null);

  const u = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  async function submit1(e) {
    e.preventDefault(); setError(null); setBusy(true);
    try {
      const r = await fetch(`${API}/api/developers/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email:           form.email,
          name:            form.name,
          password:        form.password,
          github_username: form.github_username,
          build_intent:    form.build_intent,
          referral_code:   form.referral_code,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "signup failed");
      setSI(j); setStep(2);
    } catch (e) {
      setError(String(e.message || e));
    } finally { setBusy(false); }
  }

  async function submit2(e) {
    e.preventDefault(); setError(null); setBusy(true);
    try {
      const r = await fetch(`${API}/api/developers/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.email, otp: form.otp }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "verify failed");
      setDevJwt(j.jwt); setStep(3);
      setTimeout(() => navigate("/developers/connect"), 1500);
    } catch (e) {
      setError(String(e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <DeveloperShell mode="landing">
      <SEO
        title="Developer Sign Up — Get Free AUREM API Tokens"
        description="Create your AUREM developer account. Free-tier OpenRouter chat (DeepSeek V3 → Llama 3.3 → Mistral). BYOK support, SSE streaming, PIPEDA-compliant. 60-second setup."
        path="/developers/signup"
        keywords={["AUREM signup", "developer API tokens", "free LLM API", "BYOK"]}
        schema={["Organization", "SoftwareApplication"]}
        appName="AUREM Developer Portal"
        appCategory="DeveloperApplication"
        breadcrumbs={[
          { name: "Home", url: "/" },
          { name: "Developers", url: "/developers" },
          { name: "Sign Up", url: "/developers/signup" },
        ]}
        aiSummary="AUREM developer signup gives every dev a free-tier account with OpenRouter LLM access (DeepSeek V3 → Llama 3.3 → Mistral fallback ladder), BYOK support for production scale, real-time SSE streaming chat, and PIPEDA-compliant Canadian data residency. 60-second setup, no credit card."
      />
      <section style={{ minHeight: "82vh", padding: "120px 5% 60px",
                         display: "flex", justifyContent: "center" }}>
        <div style={{ width: "100%", maxWidth: 480 }}>
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <span className="dev-section-label">SIGN UP</span>
            <h1 style={{ fontFamily: "'Cinzel', serif",
                          fontSize: 32, color: "#F0EDE8",
                          letterSpacing: "0.02em" }}>
              Create your developer account
            </h1>
          </div>

          <Stepper step={step} />

          <div data-testid="signup-step-container"
               style={{
                 background: "#0F0F1A",
                 border: "1px solid rgba(255,107,0,0.10)",
                 borderRadius: 8, padding: 28, marginTop: 24,
               }}>
            {step === 1 && (
              <form onSubmit={submit1} style={{ display: "grid", gap: 14 }}>
                <Field label="Full name" value={form.name}
                        onChange={v => u("name", v)} testid="signup-name" />
                <Field label="Email" type="email" value={form.email}
                        onChange={v => u("email", v)} testid="signup-email" />
                <Field label="Password (min 8 chars)" type="password"
                        value={form.password} minLength={8}
                        onChange={v => u("password", v)}
                        testid="signup-password" />
                <Field label="GitHub username"
                        value={form.github_username}
                        onChange={v => u("github_username", v)}
                        testid="github-username-input" />
                <Textarea label="What will you build?"
                           value={form.build_intent}
                           onChange={v => u("build_intent", v)}
                           testid="build-intent-textarea" />
                <Field label="Referral code (optional)"
                        value={form.referral_code}
                        onChange={v => u("referral_code", v)}
                        required={false} testid="referral-input" />
                {error && <ErrBox>{error}</ErrBox>}
                <button type="submit" disabled={busy}
                         data-testid="signup-continue-btn"
                         className="dev-btn-primary"
                         style={{ width: "100%", justifyContent: "center" }}>
                  {busy ? "Sending code…" : "Send verification code"}
                </button>
              </form>
            )}
            {step === 2 && (
              <form onSubmit={submit2} style={{ display: "grid", gap: 14 }}>
                <Mail size={22} style={{ color: "#FF6B00" }} />
                <div>
                  <h3 style={{ fontFamily: "'Cinzel', serif", fontSize: 18,
                                color: "#F0EDE8", marginBottom: 4 }}>
                    Check your email
                  </h3>
                  <p style={{ fontSize: 13, color: "#7A7590" }}>
                    6-digit code sent to <span style={{ color: "#F0EDE8" }}>
                    {form.email}</span>. Expires in 10 minutes.
                  </p>
                </div>
                <Field label="6-digit code" value={form.otp}
                        onChange={v => u("otp", v)}
                        testid="signup-otp-input" />
                {signupInfo?._otp_for_testing && (
                  <p data-testid="signup-otp-hint"
                      style={{ fontSize: 11, color: "#C9A84C" }}>
                    Dev mode hint: {signupInfo._otp_for_testing}
                  </p>
                )}
                {error && <ErrBox>{error}</ErrBox>}
                <button type="submit" disabled={busy}
                         data-testid="signup-verify-btn"
                         className="dev-btn-primary"
                         style={{ width: "100%", justifyContent: "center" }}>
                  {busy ? "Verifying…" : "Verify & sign in"}
                </button>
              </form>
            )}
            {step === 3 && (
              <div data-testid="signup-done"
                   style={{ textAlign: "center", padding: "20px 0" }}>
                <CheckCircle2 size={42} style={{ color: "#50C878",
                                                   margin: "0 auto 10px" }} />
                <h3 style={{ fontFamily: "'Cinzel', serif", fontSize: 20,
                              color: "#F0EDE8", marginBottom: 8 }}>
                  You're in.
                </h3>
                <p style={{ fontSize: 14, color: "#7A7590" }}>
                  1,000 tokens added. Routing you to the connect page…
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </DeveloperShell>
  );
}

function Stepper({ step }) {
  return (
    <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
      {[1, 2, 3].map(n => (
        <div key={n} data-testid={`signup-stepper-${n}`}
              style={{
                height: 3, width: 56, borderRadius: 999,
                background: n <= step ? "#FF6B00" : "rgba(255,255,255,0.10)",
                transition: "background 250ms ease",
              }} />
      ))}
    </div>
  );
}

function Field({ label, value, onChange, type = "text", testid,
                 required = true, minLength }) {
  return (
    <label style={{ display: "block" }}>
      <span style={{
        display: "block",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        color: "#7A7590", marginBottom: 6,
        textTransform: "uppercase",
      }}>{label}</span>
      <input data-testid={testid} type={type} required={required}
              minLength={minLength} value={value}
              onChange={e => onChange(e.target.value)}
              className="dev-input"
              style={{ width: "100%" }} />
    </label>
  );
}

function Textarea({ label, value, onChange, testid }) {
  return (
    <label style={{ display: "block" }}>
      <span style={{
        display: "block",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        color: "#7A7590", marginBottom: 6,
        textTransform: "uppercase",
      }}>{label}</span>
      <textarea data-testid={testid} value={value} rows={3}
                 onChange={e => onChange(e.target.value)}
                 className="dev-input"
                 style={{ width: "100%", resize: "vertical" }} />
    </label>
  );
}

function ErrBox({ children }) {
  return (
    <div data-testid="signup-error" style={{
      fontSize: 12, color: "#FF6060",
      border: "1px solid rgba(255,96,96,0.30)",
      background: "rgba(255,96,96,0.08)",
      padding: "10px 12px", borderRadius: 4,
    }}>{children}</div>
  );
}
