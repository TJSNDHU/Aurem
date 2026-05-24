/**
 * AUREM Trust Center — /enterprise/security
 *
 * The single page procurement teams Google after the demo call.
 * Pulls live data from:
 *   GET /api/compliance/sla
 *   GET /api/compliance/subprocessors
 *   GET /api/compliance/regions
 *
 * Links to:
 *   - SOC 2 PDF (gated — requires login + org membership)
 *   - /enterprise/sla (public)
 *   - /enterprise (Contact Sales)
 *   - /legal/msa.pdf + /legal/dpa.pdf
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BACKEND_URL } from "../lib/api";

const ORANGE = "#FF6B00";
const GOLD = "#F2C265";
const VOID = "#0a0a0a";

function Eyebrow({ children }) {
  return (
    <div style={{
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: 10, letterSpacing: "0.30em",
      textTransform: "uppercase", color: ORANGE, marginBottom: 6,
    }}>
      {children}
    </div>
  );
}

function PillBadge({ children, tone = "default" }) {
  const map = {
    default:  { bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.10)", color: "#aaa" },
    ok:       { bg: "rgba(34,197,94,0.10)",   border: "rgba(34,197,94,0.30)",   color: "#22C55E" },
    pending:  { bg: "rgba(245,158,11,0.10)",  border: "rgba(245,158,11,0.30)",  color: "#F59E0B" },
    gold:     { bg: "rgba(242,194,101,0.10)", border: "rgba(242,194,101,0.30)", color: GOLD },
  };
  const t = map[tone] || map.default;
  return (
    <span style={{
      display: "inline-block", padding: "3px 9px", borderRadius: 999,
      background: t.bg, border: `1px solid ${t.border}`, color: t.color,
      fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
      letterSpacing: "0.15em", textTransform: "uppercase",
    }}>
      {children}
    </span>
  );
}

function Card({ children, testid, style }) {
  return (
    <div
      data-testid={testid}
      style={{
        background: "rgba(20,20,20,0.55)",
        border: "1px solid rgba(255,107,0,0.10)",
        borderRadius: 8, padding: 22, marginBottom: 16, ...style,
      }}
    >
      {children}
    </div>
  );
}

function ArtifactRow({ icon, title, sub, action, testid }) {
  return (
    <div
      data-testid={testid}
      style={{
        display: "grid",
        gridTemplateColumns: "44px 1fr auto",
        gap: 16, alignItems: "center",
        padding: "16px 4px",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
      }}>
      <div style={{
          width: 36, height: 36, borderRadius: 6,
          background: "rgba(255,107,0,0.10)",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: ORANGE, fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11, fontWeight: "bold",
      }}>
        {icon}
      </div>
      <div>
        <div style={{
          fontFamily: "'Cinzel', serif",
          fontSize: 15, letterSpacing: "0.02em",
          color: "#f6f5f1", marginBottom: 2,
        }}>{title}</div>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11, color: "#888", lineHeight: 1.5,
        }}>{sub}</div>
      </div>
      <div>{action}</div>
    </div>
  );
}

const ArtifactCTA = ({ children, ...rest }) => (
  <a {...rest} style={{
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 11, letterSpacing: "0.15em",
    textTransform: "uppercase", padding: "8px 14px",
    border: `1px solid ${ORANGE}`, color: ORANGE,
    borderRadius: 4, textDecoration: "none",
    transition: "all 160ms ease",
  }}>
    {children}
  </a>
);

export default function TrustCenter() {
  const [sla, setSla]   = useState(null);
  const [subs, setSubs] = useState([]);
  const [regions, setRegions] = useState({});
  const [err, setErr]   = useState(null);
  // Lead-capture modal state
  const [leadOpen, setLeadOpen]   = useState(false);
  const [leadBusy, setLeadBusy]   = useState(false);
  const [leadErr,  setLeadErr]    = useState(null);
  const [leadDone, setLeadDone]   = useState(false);
  const [leadForm, setLeadForm]   = useState({ email: "", company: "", role: "" });

  const submitLead = async (e) => {
    e?.preventDefault?.();
    setLeadErr(null);
    if (!leadForm.email || !leadForm.company) {
      setLeadErr("Email and company are required.");
      return;
    }
    setLeadBusy(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/compliance/soc2/sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(leadForm),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail || "Could not generate the sample PDF.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "aurem-soc2-sample.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setLeadDone(true);
    } catch (ex) {
      setLeadErr(ex.message || "Something went wrong. Try again.");
    } finally {
      setLeadBusy(false);
    }
  };

  useEffect(() => {
    Promise.all([
      fetch(`${BACKEND_URL}/api/compliance/sla`).then(r => r.json()),
      fetch(`${BACKEND_URL}/api/compliance/subprocessors`).then(r => r.json()),
      fetch(`${BACKEND_URL}/api/compliance/regions`).then(r => r.json()),
    ])
      .then(([s, sp, rg]) => {
        if (s.ok) setSla(s);
        if (sp.ok) setSubs(sp.rows || []);
        if (rg.ok) setRegions(rg.rows || {});
      })
      .catch(() => setErr("Trust Center failed to load"));
  }, []);

  if (err) {
    return (
      <div style={{ minHeight: "100vh", background: VOID, color: "#fff",
                     padding: 40, fontFamily: "'JetBrains Mono', monospace" }}>
        {err}
      </div>
    );
  }

  return (
    <div data-testid="trust-center-page"
          style={{ minHeight: "100vh", background: VOID, color: "#f6f5f1",
                   padding: "60px 24px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>

        {/* Hero */}
        <Eyebrow>Enterprise / Trust Center</Eyebrow>
        <h1 data-testid="trust-center-headline"
             style={{ fontFamily: "'Cinzel', serif",
                      fontSize: 48, letterSpacing: "0.02em",
                      color: "#f6f5f1", margin: 0,
                      lineHeight: 1.05, marginBottom: 14 }}>
          Trust, in&nbsp;writing.
        </h1>
        <p style={{ color: "#888", fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 12, lineHeight: 1.7, maxWidth: 620,
                     margin: "12px 0 36px" }}>
          Everything procurement and security teams ask for, in one place.
          Live numbers, audit posture, and downloadable artifacts.
        </p>

        {/* Status pill row */}
        <Card testid="trust-status-strip"
               style={{ display: "flex", gap: 18, alignItems: "center",
                         flexWrap: "wrap", padding: "16px 22px" }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace",
                         fontSize: 10, letterSpacing: "0.20em",
                         textTransform: "uppercase", color: "#666" }}>
            Live
          </div>
          {sla && (
            <>
              <PillBadge tone="gold">
                Uptime · {sla.sla.uptime_actual_30d}
              </PillBadge>
              <PillBadge tone="ok">PIPEDA</PillBadge>
              <PillBadge tone="ok">Québec Law 25</PillBadge>
              <PillBadge tone="pending">SOC 2 Type II · in progress</PillBadge>
              <PillBadge tone="ok">HIPAA · BAA on request</PillBadge>
            </>
          )}
        </Card>

        {/* Artifacts */}
        <Card testid="trust-artifacts-card">
          <Eyebrow>Documents &amp; receipts</Eyebrow>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                         color: "#f6f5f1", marginBottom: 16 }}>
            Pre-built artifacts
          </div>
          <ArtifactRow
            icon="PDF" title="SOC 2 Type II evidence package"
            sub="Multi-page report covering CC1 / CC6 / CC7 / CC8 + audit event summary. Email it to me and I'll send a sample copy. Customer-scoped reports are available after sign-in."
            testid="trust-artifact-soc2"
            action={
              <button
                data-testid="trust-soc2-download-btn"
                onClick={() => { setLeadOpen(true); setLeadDone(false); setLeadErr(null); }}
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11, letterSpacing: "0.15em",
                  textTransform: "uppercase", padding: "8px 14px",
                  background: "transparent",
                  border: `1px solid ${ORANGE}`, color: ORANGE,
                  borderRadius: 4, cursor: "pointer",
                  transition: "all 160ms ease",
                }}>
                Get sample →
              </button>
            }
          />
          <ArtifactRow
            icon="SLA" title="Service-level &amp; MSA"
            sub="Uptime targets, incident response SLAs, service credits, governing law, insurance limits. Lives at one URL — procurement can link straight to it."
            testid="trust-artifact-sla"
            action={
              <ArtifactCTA href="/enterprise/sla"
                            data-testid="trust-sla-link">
                Open →
              </ArtifactCTA>
            }
          />
          <ArtifactRow
            icon="MSA" title="Master Service Agreement template"
            sub={sla
              ? `${sla.msa.redline_window_days}-business-day redline window. Governing law: ${sla.msa.governing_law}.`
              : "Standard MSA template available on request."}
            testid="trust-artifact-msa"
            action={
              <ArtifactCTA href={sla?.msa?.template_url || "/legal/msa.pdf"}
                            target="_blank" rel="noopener noreferrer"
                            data-testid="trust-msa-link">
                msa.pdf →
              </ArtifactCTA>
            }
          />
          <ArtifactRow
            icon="DPA" title="Data Processing Agreement"
            sub="GDPR Article 28 + Québec Law 25 compliant. Pre-signed; we'll add your details on request."
            testid="trust-artifact-dpa"
            action={
              <ArtifactCTA href={sla?.msa?.data_processing_agreement || "/legal/dpa.pdf"}
                            target="_blank" rel="noopener noreferrer"
                            data-testid="trust-dpa-link">
                dpa.pdf →
              </ArtifactCTA>
            }
          />
        </Card>

        {/* Subprocessors */}
        <Card testid="trust-subprocessors-card">
          <Eyebrow>Who else touches your data</Eyebrow>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                         color: "#f6f5f1", marginBottom: 16 }}>
            Subprocessor list
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "200px 200px 1fr",
            gap: 12, fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10, letterSpacing: "0.15em",
            textTransform: "uppercase", color: "#666",
            paddingBottom: 8, borderBottom: "1px solid rgba(255,255,255,0.05)",
            marginBottom: 8,
          }}>
            <div>Vendor</div><div>Region</div><div>Purpose</div>
          </div>
          {subs.map((s, i) => (
            <div key={i}
                  data-testid={`trust-subprocessor-row-${i}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "200px 200px 1fr",
                    gap: 12, padding: "8px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12, color: "#ddd",
                  }}>
              <div style={{ color: "#f6f5f1" }}>{s.name}</div>
              <div style={{ color: "#888" }}>{s.region}</div>
              <div style={{ color: "#888" }}>{s.purpose}</div>
            </div>
          ))}
        </Card>

        {/* Data residency */}
        <Card testid="trust-residency-card">
          <Eyebrow>Where your data lives</Eyebrow>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                         color: "#f6f5f1", marginBottom: 16 }}>
            Data residency options
          </div>
          {Object.entries(regions).map(([k, info]) => (
            <div key={k}
                  data-testid={`trust-region-${k}`}
                  style={{
                    display: "grid", gridTemplateColumns: "100px 1fr auto",
                    gap: 16, padding: "12px 0", alignItems: "center",
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                  }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 14, color: info.primary ? GOLD : "#aaa",
                letterSpacing: "0.10em", textTransform: "uppercase",
              }}>
                {k.toUpperCase()}
              </div>
              <div style={{
                fontFamily: "'Cinzel', serif", fontSize: 14, color: "#f6f5f1",
              }}>
                {info.name}
                <div style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10, color: "#666", marginTop: 2,
                }}>
                  {info.location}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {info.pipeda && <PillBadge tone="ok">PIPEDA</PillBadge>}
                {info.law25  && <PillBadge tone="ok">Law 25</PillBadge>}
                {info.gdpr   && <PillBadge tone="ok">GDPR</PillBadge>}
                {info.hipaa  && <PillBadge tone="ok">HIPAA</PillBadge>}
                {info.fedramp && <PillBadge tone="ok">FedRAMP</PillBadge>}
                {info.primary && <PillBadge tone="gold">DEFAULT</PillBadge>}
              </div>
            </div>
          ))}
        </Card>

        {/* CTA */}
        <div style={{ marginTop: 36, textAlign: "center",
                       fontFamily: "'JetBrains Mono', monospace",
                       fontSize: 11, color: "#666" }}>
          Need anything custom in your contract or DPA?{" "}
          <Link to="/enterprise"
                 data-testid="trust-contact-sales-link"
                 style={{ color: ORANGE }}>
            Talk to sales →
          </Link>
        </div>

        {/* Lead-capture modal — fires on "Get sample" click. */}
        {leadOpen && (
          <div
            data-testid="trust-lead-modal"
            onClick={(e) => { if (e.target === e.currentTarget) setLeadOpen(false); }}
            style={{
              position: "fixed", inset: 0, zIndex: 100,
              background: "rgba(0,0,0,0.75)",
              backdropFilter: "blur(8px)",
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: 20,
            }}>
            <div style={{
              maxWidth: 460, width: "100%",
              background: "#0d0d0d",
              border: `1px solid ${ORANGE}`,
              borderRadius: 8, padding: 28,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              <Eyebrow>Trust Center / SOC 2 sample</Eyebrow>
              <div style={{
                fontFamily: "'Cinzel', serif",
                fontSize: 24, color: "#f6f5f1",
                margin: "8px 0 14px",
              }}>
                Where should I send it?
              </div>
              {leadDone ? (
                <div data-testid="trust-lead-success"
                      style={{ color: GOLD, fontSize: 13,
                                lineHeight: 1.7, marginBottom: 18 }}>
                  PDF downloaded. The real one (with your org's audit
                  events) lives at <strong>/enterprise/admin/compliance</strong>
                  once you're signed in. I'll be in touch.
                </div>
              ) : (
                <form onSubmit={submitLead}>
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ display: "block", fontSize: 10,
                                     letterSpacing: "0.20em",
                                     textTransform: "uppercase",
                                     color: "#888", marginBottom: 6 }}>
                      Work email
                    </label>
                    <input
                      type="email" required autoFocus
                      data-testid="trust-lead-email"
                      value={leadForm.email}
                      onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })}
                      style={{
                        width: "100%", padding: "10px 12px",
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.10)",
                        borderRadius: 4, color: "#f6f5f1",
                        fontFamily: "inherit", fontSize: 13,
                      }} />
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ display: "block", fontSize: 10,
                                     letterSpacing: "0.20em",
                                     textTransform: "uppercase",
                                     color: "#888", marginBottom: 6 }}>
                      Company
                    </label>
                    <input
                      type="text" required
                      data-testid="trust-lead-company"
                      value={leadForm.company}
                      onChange={(e) => setLeadForm({ ...leadForm, company: e.target.value })}
                      style={{
                        width: "100%", padding: "10px 12px",
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.10)",
                        borderRadius: 4, color: "#f6f5f1",
                        fontFamily: "inherit", fontSize: 13,
                      }} />
                  </div>
                  <div style={{ marginBottom: 16 }}>
                    <label style={{ display: "block", fontSize: 10,
                                     letterSpacing: "0.20em",
                                     textTransform: "uppercase",
                                     color: "#888", marginBottom: 6 }}>
                      Your role (optional)
                    </label>
                    <input
                      type="text"
                      data-testid="trust-lead-role"
                      value={leadForm.role}
                      placeholder="e.g. Head of Security"
                      onChange={(e) => setLeadForm({ ...leadForm, role: e.target.value })}
                      style={{
                        width: "100%", padding: "10px 12px",
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.10)",
                        borderRadius: 4, color: "#f6f5f1",
                        fontFamily: "inherit", fontSize: 13,
                      }} />
                  </div>
                  {leadErr && (
                    <div data-testid="trust-lead-error"
                          style={{ color: "#EF4444", fontSize: 11,
                                    marginBottom: 12 }}>
                      {leadErr}
                    </div>
                  )}
                  <button
                    type="submit"
                    disabled={leadBusy}
                    data-testid="trust-lead-submit-btn"
                    style={{
                      width: "100%", padding: "12px",
                      background: leadBusy ? "#555"
                        : "linear-gradient(135deg, #FF6B00, #F2C265)",
                      color: "#0a0a0a", border: "none", borderRadius: 4,
                      fontFamily: "inherit", fontSize: 12,
                      letterSpacing: "0.15em", textTransform: "uppercase",
                      fontWeight: "bold", cursor: leadBusy ? "wait" : "pointer",
                    }}>
                    {leadBusy ? "Building PDF…" : "Send me the sample"}
                  </button>
                </form>
              )}
              <button
                data-testid="trust-lead-close-btn"
                onClick={() => setLeadOpen(false)}
                style={{
                  marginTop: 14, width: "100%",
                  padding: "8px", background: "transparent",
                  border: "1px solid rgba(255,255,255,0.10)",
                  color: "#888", borderRadius: 4, cursor: "pointer",
                  fontFamily: "inherit", fontSize: 10,
                  letterSpacing: "0.20em", textTransform: "uppercase",
                }}>
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
