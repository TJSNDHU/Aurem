/**
 * /enterprise/admin/domain — Custom domain wizard
 * Step 1: enter domain → Step 2: show CNAME → Step 3: Verify → Step 4: done
 */
import React, { useState } from "react";
import { Globe, CheckCircle2, AlertTriangle } from "lucide-react";
import EnterpriseAdminShell, {
  Field, PrimaryButton, Banner, ENT_API, adminHeaders,
} from "./EnterpriseAdminShell";

export default function EnterpriseDomain() {
  const [step, setStep]     = useState(1);
  const [domain, setDomain] = useState("");
  const [instructions, setInstructions] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr]   = useState(null);

  async function registerDomain() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${ENT_API}/api/enterprise/domain`, {
        method: "POST", headers: adminHeaders(),
        body: JSON.stringify({ tenant_id: "default", domain }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "register_failed");
      setInstructions(j);
      setStep(2);
    } catch (e) {
      setErr(String(e.message || e));
    } finally { setBusy(false); }
  }

  async function verifyDomain() {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${ENT_API}/api/enterprise/domain/verify`, {
        method: "POST", headers: adminHeaders(),
        body: JSON.stringify({ tenant_id: "default", domain }),
      });
      const j = await r.json();
      setVerifyResult(j);
      if (j.verified) setStep(3);
    } catch (e) {
      setErr(String(e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <EnterpriseAdminShell
      eyebrow="ENTERPRISE / ADMIN"
      title="Custom domain"
      sub="Map your own domain to AUREM CTO. Three steps."
    >
      <div className="av2-card" data-testid="domain-wizard"
            style={{ maxWidth: 600 }}>
        {/* Stepper */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          {[1, 2, 3].map(n => (
            <div key={n} data-testid={`domain-step-${n}`}
                  style={{
                    height: 3, width: 56, borderRadius: 999,
                    background: n <= step ? "var(--dash-orange)"
                                          : "rgba(255,255,255,0.10)",
                  }} />
          ))}
        </div>

        {step === 1 && (
          <div style={{ display: "grid", gap: 14 }}>
            <Field label="Your domain" value={domain}
                    placeholder="enterprise.yourcompany.com"
                    onChange={setDomain} testid="domain-input" />
            <PrimaryButton onClick={registerDomain} busy={busy}
                            testid="domain-register-btn">
              <Globe size={13} /> Get CNAME instructions
            </PrimaryButton>
          </div>
        )}

        {step === 2 && instructions && (
          <div style={{ display: "grid", gap: 14 }}>
            <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
              Add this CNAME record in your DNS provider:
            </p>
            <div data-testid="domain-cname-instructions"
                  style={{
                    background: "rgba(0,0,0,0.30)",
                    border: "1px solid rgba(255,107,0,0.15)",
                    padding: 14, borderRadius: 6,
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 13, color: "var(--dash-text)",
                    display: "grid", gap: 4,
                  }}>
              <div><span style={{ color: "var(--dash-text-muted)" }}>Type:  </span> CNAME</div>
              <div><span style={{ color: "var(--dash-text-muted)" }}>Name:  </span> {instructions.domain}</div>
              <div><span style={{ color: "var(--dash-text-muted)" }}>Value: </span> {instructions.cname_target}</div>
              <div><span style={{ color: "var(--dash-text-muted)" }}>TTL:   </span> 300 seconds</div>
            </div>
            <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>
              DNS can take up to 30 minutes to propagate. Hit Verify when ready.
            </p>
            <PrimaryButton onClick={verifyDomain} busy={busy}
                            testid="domain-verify-btn">
              <CheckCircle2 size={13} /> Verify DNS
            </PrimaryButton>
            {verifyResult && !verifyResult.verified && (
              <Banner tone="warn" testid="domain-not-verified">
                <AlertTriangle size={13} style={{ display: "inline", marginRight: 6 }} />
                Not verified yet. {verifyResult.detail || "Try again in a few minutes."}
              </Banner>
            )}
          </div>
        )}

        {step === 3 && (
          <div data-testid="domain-success"
                style={{ textAlign: "center", padding: "10px 0" }}>
            <CheckCircle2 size={42}
                            style={{ color: "var(--dash-green)",
                                      margin: "0 auto 12px" }} />
            <h3 style={{ fontFamily: "'Cinzel', serif",
                          fontSize: 20, color: "var(--dash-text)",
                          marginBottom: 8 }}>
              {domain} is active.
            </h3>
            <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
              Your custom domain is now routing to AUREM CTO.
            </p>
          </div>
        )}

        {err && <Banner tone="err" testid="domain-error" >{err}</Banner>}
      </div>
    </EnterpriseAdminShell>
  );
}
