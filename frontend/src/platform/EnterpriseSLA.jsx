/**
 * AUREM Enterprise SLA + MSA page.
 *
 * Public route at /enterprise/sla. Procurement teams + their lawyers
 * link directly here. We pull live data from /api/compliance/sla so
 * uptime + insurance numbers stay accurate without code edits.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BACKEND_URL } from "../lib/api";

const ORANGE = "#FF6B00";
const GOLD = "#F2C265";
const VOID = "#0a0a0a";

function Card({ title, eyebrow, children, testid }) {
  return (
    <div
      data-testid={testid}
      style={{
        background: "rgba(20,20,20,0.55)",
        border: "1px solid rgba(255,107,0,0.10)",
        borderRadius: 8,
        padding: 24,
        marginBottom: 18,
      }}
    >
      {eyebrow && (
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10, letterSpacing: "0.25em",
          textTransform: "uppercase", color: ORANGE, marginBottom: 6,
        }}>
          {eyebrow}
        </div>
      )}
      <div style={{
        fontFamily: "'Cinzel', serif",
        fontSize: 22, letterSpacing: "0.02em",
        color: "#f6f5f1", marginBottom: 14,
      }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, testid }) {
  return (
    <div
      data-testid={testid}
      style={{
        display: "grid", gridTemplateColumns: "180px 1fr",
        gap: 16, padding: "10px 0",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
        color: "#ddd",
      }}>
      <div style={{ color: "#888", letterSpacing: "0.05em" }}>{label}</div>
      <div>{value}</div>
    </div>
  );
}

export default function EnterpriseSLA() {
  const [data, setData] = useState(null);
  const [err,  setErr]  = useState(null);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/compliance/sla`)
      .then(r => r.json())
      .then(d => { if (d.ok) setData(d); else setErr("Could not load SLA"); })
      .catch(() => setErr("Could not load SLA"));
  }, []);

  if (err) {
    return (
      <div style={{ minHeight: "100vh", background: VOID, color: "#fff",
                     padding: 40, fontFamily: "'JetBrains Mono', monospace" }}>
        {err}
      </div>
    );
  }
  if (!data) {
    return (
      <div data-testid="enterprise-sla-loading"
            style={{ minHeight: "100vh", background: VOID, color: "#777",
                     padding: 40, fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 11, letterSpacing: "0.25em",
                     textTransform: "uppercase" }}>
        Loading commitments…
      </div>
    );
  }

  const { sla, msa, audit_certifications } = data;

  return (
    <div data-testid="enterprise-sla-page"
          style={{ minHeight: "100vh", background: VOID, color: "#f6f5f1",
                   padding: "60px 24px" }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        {/* Eyebrow + headline */}
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10, letterSpacing: "0.30em",
          textTransform: "uppercase", color: ORANGE, marginBottom: 14,
        }}>
          Enterprise / Commitments
        </div>
        <h1 data-testid="enterprise-sla-headline"
             style={{ fontFamily: "'Cinzel', serif",
                      fontSize: 44, letterSpacing: "0.02em",
                      color: "#f6f5f1", margin: 0, marginBottom: 8,
                      lineHeight: 1.05 }}>
          Service-level &amp;<br/>master-service agreement
        </h1>
        <p style={{ color: "#888", fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 12, lineHeight: 1.7, maxWidth: 640,
                     margin: "12px 0 36px" }}>
          The commitments below back every Enterprise contract. They live
          here in a single source of truth — your procurement team can
          link directly to this page.
        </p>

        {/* SLA */}
        <Card eyebrow="Uptime &amp; response" title="Service-level commitments"
               testid="sla-uptime-card">
          <Row label="Uptime target"   value={sla.uptime_target}
                testid="sla-row-target" />
          <Row label="Actual (30-day)" value={
            <span style={{ color: GOLD }}>{sla.uptime_actual_30d}</span>
          } testid="sla-row-actual" />
          <Row label="Sev 1 response"  value={sla.incident_response.severity_1} />
          <Row label="Sev 2 response"  value={sla.incident_response.severity_2} />
          <Row label="Sev 3 response"  value={sla.incident_response.severity_3} />
          <Row label="Sev 4 response"  value={sla.incident_response.severity_4} />
        </Card>

        {/* Credits */}
        <Card eyebrow="If we miss" title="Service credits" testid="sla-credits-card">
          <Row label="Below 99.9%" value={sla.credits["below_99.9"]} />
          <Row label="Below 99.5%" value={sla.credits["below_99.5"]} />
          <Row label="Below 99.0%" value={sla.credits["below_99.0"]} />
        </Card>

        {/* MSA */}
        <Card eyebrow="Contract" title="Master service agreement"
               testid="sla-msa-card">
          <Row label="Template"
                value={
                  <a href={msa.template_url} target="_blank" rel="noopener noreferrer"
                      style={{ color: ORANGE }}>
                    msa.pdf →
                  </a>
                } />
          <Row label="Redline window"  value={`${msa.redline_window_days} business days`} />
          <Row label="Governing law"   value={msa.governing_law} />
          <Row label="DPA"
                value={
                  <a href={msa.data_processing_agreement} target="_blank" rel="noopener noreferrer"
                      style={{ color: ORANGE }}>
                    dpa.pdf →
                  </a>
                } />
          <Row label="Subprocessors"
                value={
                  <a href={msa.subprocessors_url} target="_blank" rel="noopener noreferrer"
                      style={{ color: ORANGE }}>
                    Current list →
                  </a>
                } />
          <Row label="Cyber insurance"  value={msa.insurance.cyber} />
          <Row label="General liability" value={msa.insurance.general} />
          <Row label="E&amp;O"             value={msa.insurance.errors_and_omissions} />
        </Card>

        {/* Certifications */}
        <Card eyebrow="Certifications" title="Audit posture"
               testid="sla-certifications-card">
          {audit_certifications.map((c, i) => (
            <Row key={i} label={c.name}
                  value={
                    <span style={{
                      color: c.status.includes("complete") ? GOLD : "#aaa",
                    }}>
                      {c.status}{c.auditor ? ` — ${c.auditor}` : ""}
                    </span>
                  } />
          ))}
        </Card>

        <div style={{ marginTop: 40, textAlign: "center",
                       fontFamily: "'JetBrains Mono', monospace",
                       fontSize: 11, color: "#666" }}>
          Need something specific in your contract?{" "}
          <Link to="/enterprise" style={{ color: ORANGE }}>
            Talk to sales →
          </Link>
        </div>
      </div>
    </div>
  );
}
