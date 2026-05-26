/**
 * /developers/login — iter 332b D-9
 *
 * Real sign-in page for returning developers. The top-right "Sign in"
 * button on the dev panel pointed at /developers/signup, which forced
 * returning users through a 3-step signup form. This page mirrors the
 * landing aesthetic and hits POST /api/developers/login directly so
 * existing accounts can sign in with email + password in one screen.
 */
import React, { useState } from "react";
import SEO from "../../components/SEO";
import { Link, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import DeveloperShell, { setDevJwt } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevLogin() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState(null);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/developers/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const j = await r.json();
      if (!r.ok) {
        // Map the backend's machine codes to plain English
        const code = j.detail || "login_failed";
        const msg = {
          account_not_found:    "We couldn't find that email. Want to create an account?",
          email_not_verified:   "Your email isn't verified yet. Check your inbox for the code.",
          invalid_credentials:  "That password doesn't match. Try again or reset.",
          account_under_review: "This account is under review. Contact support.",
        }[code] || "Sign in failed. Try again in a moment.";
        throw new Error(msg);
      }
      setDevJwt(j.jwt);
      navigate("/developers/dashboard");
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <DeveloperShell mode="landing">
      <SEO
        title="Developer Sign In"
        description="Access your AUREM developer dashboard. Manage tokens, BYOK keys, sessions, and chat with AUREM CTO for fast SMB AI builds."
        path="/developers/login"
        noindex
        breadcrumbs={[
          { name: "Home", url: "/" },
          { name: "Developers", url: "/developers" },
          { name: "Sign In", url: "/developers/login" },
        ]}
      />
      <section style={{ minHeight: "82vh", padding: "120px 5% 60px",
                        display: "flex", justifyContent: "center" }}>
        <div style={{ width: "100%", maxWidth: 440 }}>
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <span className="dev-section-label">SIGN IN</span>
            <h1 data-testid="dev-login-title"
                style={{ fontFamily: "'Cinzel', serif",
                          fontSize: 32, color: "#F0EDE8",
                          letterSpacing: "0.02em" }}>
              Welcome back, builder.
            </h1>
            <p style={{ fontSize: 13, color: "#7A7590",
                        marginTop: 8 }}>
              Sign in to your AUREM CTO developer account.
            </p>
          </div>

          <div data-testid="dev-login-card"
               style={{ background: "#0F0F1A",
                        border: "1px solid rgba(255,107,0,0.10)",
                        borderRadius: 8, padding: 28 }}>
            <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
              <Field label="Email" type="email" value={email}
                     onChange={setEmail} testid="dev-login-email" />
              <Field label="Password" type="password" value={password}
                     onChange={setPassword} testid="dev-login-password"
                     minLength={8} />
              {error && (
                <div data-testid="dev-login-error"
                     style={{ fontSize: 12, color: "#FF6060",
                              border: "1px solid rgba(255,96,96,0.30)",
                              background: "rgba(255,96,96,0.08)",
                              padding: "10px 12px", borderRadius: 4 }}>
                  {error}
                </div>
              )}
              <button type="submit" disabled={busy}
                      data-testid="dev-login-submit"
                      className="dev-btn-primary"
                      style={{ width: "100%", justifyContent: "center" }}>
                <LogIn size={16} /> {busy ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)",
                          marginTop: 22, paddingTop: 18,
                          textAlign: "center" }}>
              <p style={{ fontSize: 13, color: "#7A7590", margin: 0 }}>
                No account yet?{" "}
                <Link to="/developers/signup"
                      data-testid="dev-login-go-signup"
                      style={{ color: "#E8C86A",
                               textDecoration: "none",
                               fontWeight: 500 }}>
                  Claim 1000 tokens →
                </Link>
              </p>
            </div>
          </div>
        </div>
      </section>
    </DeveloperShell>
  );
}

function Field({ label, value, onChange, type = "text",
                 testid, minLength }) {
  return (
    <label style={{ display: "block" }}>
      <span style={{
        display: "block",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        color: "#7A7590", marginBottom: 6,
        textTransform: "uppercase",
      }}>{label}</span>
      <input data-testid={testid} type={type} required
             minLength={minLength} value={value}
             onChange={e => onChange(e.target.value)}
             className="dev-input"
             style={{ width: "100%" }} />
    </label>
  );
}
