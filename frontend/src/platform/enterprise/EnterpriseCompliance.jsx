/**
 * EnterpriseCompliance — /enterprise/admin/compliance
 *
 * Lives inside the Enterprise Admin shell. Two responsibilities:
 *   1. Data residency picker (CA / US / EU) — POST to
 *      /api/compliance/{org_id}/residency queues a region change.
 *   2. SOC 2 Type II PDF download — GET /api/compliance/{org_id}/soc2.pdf
 *      with optional start/end date pickers.
 *
 * Requires an org_id from /api/orgs/me. If the admin doesn't own any
 * orgs yet, we show a friendly hint pointing them at the org creator.
 */
import React, { useEffect, useMemo, useState } from "react";
import EnterpriseAdminShell, { Banner, PrimaryButton, ENT_API, adminHeaders }
  from "./EnterpriseAdminShell";

const ORANGE = "#FF6B00";

function RegionTile({ code, info, selected, onSelect, testid, disabled }) {
  return (
    <button
      type="button"
      data-testid={testid}
      onClick={() => !disabled && onSelect(code)}
      disabled={disabled}
      style={{
        textAlign: "left",
        padding: 18,
        borderRadius: 8,
        background: selected ? "rgba(255,107,0,0.08)" : "rgba(20,20,20,0.55)",
        border: selected
          ? `2px solid ${ORANGE}`
          : "1px solid rgba(255,255,255,0.06)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        transition: "all 160ms ease",
      }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.20em",
        textTransform: "uppercase",
        color: selected ? ORANGE : "#666", marginBottom: 4,
      }}>
        {code.toUpperCase()}{info.primary && " · default"}
      </div>
      <div style={{
        fontFamily: "'Cinzel', serif",
        fontSize: 16, color: "var(--dash-text)", marginBottom: 4,
      }}>
        {info.name}
      </div>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, color: "#888",
      }}>
        {info.location}
      </div>
      <div style={{ marginTop: 10,
                     display: "flex", flexWrap: "wrap", gap: 4 }}>
        {info.pipeda  && <PillBadge>PIPEDA</PillBadge>}
        {info.law25   && <PillBadge>Law 25</PillBadge>}
        {info.gdpr    && <PillBadge>GDPR</PillBadge>}
        {info.hipaa   && <PillBadge>HIPAA</PillBadge>}
        {info.fedramp && <PillBadge>FedRAMP</PillBadge>}
      </div>
    </button>
  );
}

const PillBadge = ({ children }) => (
  <span style={{
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 8, letterSpacing: "0.15em",
    textTransform: "uppercase",
    padding: "2px 6px", borderRadius: 999,
    background: "rgba(255,255,255,0.04)",
    color: "#aaa",
  }}>{children}</span>
);

export default function EnterpriseCompliance() {
  const [orgs, setOrgs]     = useState([]);
  const [orgId, setOrgId]   = useState(null);
  const [residency, setResidency] = useState(null);
  const [regions, setRegions] = useState({});
  const [picked, setPicked] = useState(null);
  const [busy, setBusy]     = useState(false);
  const [banner, setBanner] = useState(null);
  // SOC 2 download date pickers
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const ninetyDaysAgo = useMemo(() => {
    const d = new Date(); d.setDate(d.getDate() - 90);
    return d.toISOString().slice(0, 10);
  }, []);
  const [soc2Start, setSoc2Start] = useState(ninetyDaysAgo);
  const [soc2End,   setSoc2End]   = useState(today);

  // Step 1: load my orgs
  useEffect(() => {
    fetch(`${ENT_API}/api/orgs/me`, { headers: adminHeaders() })
      .then(r => r.json())
      .then(d => {
        if (d.ok && d.rows?.length) {
          setOrgs(d.rows);
          const initial = d.current_org_id
            || d.rows.find(o => o.role === "owner")?.org_id
            || d.rows[0].org_id;
          setOrgId(initial);
        }
      })
      .catch(() => { /* silent — Banner shows below if no orgs */ });
  }, []);

  // Step 2: when org changes, load residency
  useEffect(() => {
    if (!orgId) return;
    fetch(`${ENT_API}/api/compliance/${orgId}/residency`,
           { headers: adminHeaders() })
      .then(r => r.json())
      .then(d => {
        if (d.ok) {
          setResidency(d.residency);
          setRegions(d.options);
          setPicked(d.residency.region);
        }
      })
      .catch(() => { /* surface in Banner on save */ });
  }, [orgId]);

  const saveResidency = async () => {
    if (!orgId || !picked) return;
    if (picked === residency?.region) {
      setBanner({ tone: "info", text: "Already in that region — nothing to do." });
      return;
    }
    setBusy(true); setBanner(null);
    try {
      const res = await fetch(`${ENT_API}/api/compliance/${orgId}/residency`, {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ region: picked }),
      });
      const d = await res.json();
      if (res.ok && d.ok) {
        setBanner({
          tone: "ok",
          text: `Migration queued from ${d.from?.toUpperCase()} → ${d.to?.toUpperCase()}. ETA ${d.eta || "5–10 business days"}.`,
        });
      } else {
        setBanner({ tone: "warn",
                     text: d.detail || d.error || "Migration request failed." });
      }
    } catch {
      setBanner({ tone: "warn", text: "Network error. Try again." });
    } finally {
      setBusy(false);
    }
  };

  const downloadSoc2 = () => {
    if (!orgId) return;
    const tok = localStorage.getItem("platform_token")
              || localStorage.getItem("aurem_admin_token")
              || "";
    const url = new URL(`${ENT_API}/api/compliance/${orgId}/soc2.pdf`);
    url.searchParams.set("start", `${soc2Start}T00:00:00+00:00`);
    url.searchParams.set("end",   `${soc2End}T23:59:59+00:00`);
    // Stream via fetch+blob so we can pass the Authorization header.
    setBusy(true);
    fetch(url.toString(), {
      headers: { Authorization: `Bearer ${tok}` },
    })
      .then(r => {
        if (!r.ok) throw new Error("download_failed");
        return r.blob();
      })
      .then(blob => {
        const dl = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        dl.href = objectUrl;
        dl.download = `aurem-soc2-${orgId.slice(0, 8)}-${soc2End}.pdf`;
        document.body.appendChild(dl);
        dl.click();
        document.body.removeChild(dl);
        URL.revokeObjectURL(objectUrl);
        setBanner({ tone: "ok", text: "SOC 2 PDF downloaded." });
      })
      .catch(() => setBanner({
        tone: "warn",
        text: "Could not generate the PDF. Try again in a moment.",
      }))
      .finally(() => setBusy(false));
  };

  if (!orgs.length) {
    return (
      <EnterpriseAdminShell eyebrow="ENTERPRISE / COMPLIANCE"
                              title="Compliance & residency"
                              sub="Data residency, SOC 2 evidence, audit posture.">
        <Banner tone="warn" testid="compliance-no-org-banner">
          You aren't an Owner / Admin of any organization yet. Create one
          via the API (POST /api/orgs) or ask the founder to add you to
          an existing org.
        </Banner>
      </EnterpriseAdminShell>
    );
  }

  return (
    <EnterpriseAdminShell eyebrow="ENTERPRISE / COMPLIANCE"
                            title="Compliance & residency"
                            sub="Data residency, SOC 2 evidence, audit posture.">

      {/* Org selector when admin owns more than one */}
      {orgs.length > 1 && (
        <div style={{ marginBottom: 18 }}>
          <label style={{
            display: "block",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10, letterSpacing: "0.18em",
            textTransform: "uppercase", color: "var(--dash-text-muted)",
            marginBottom: 6,
          }}>Organization</label>
          <select data-testid="compliance-org-selector"
                   value={orgId || ""}
                   onChange={e => setOrgId(e.target.value)}
                   className="dev-input" style={{ width: 320 }}>
            {orgs.map(o => (
              <option key={o.org_id} value={o.org_id}>
                {o.name} ({o.role})
              </option>
            ))}
          </select>
        </div>
      )}

      {banner && (
        <Banner tone={banner.tone} testid="compliance-banner">
          {banner.text}
        </Banner>
      )}

      {/* Residency picker */}
      <div className="av2-card" data-testid="compliance-residency-card"
            style={{ marginBottom: 18 }}>
        <h3 style={{
          fontFamily: "'Cinzel', serif", fontSize: 18,
          color: "var(--dash-text)", margin: "0 0 6px",
        }}>Data residency</h3>
        <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                     marginBottom: 16 }}>
          Pick where your tenant's data lives. Migrations are manual ops
          (Atlas snapshot → restore → DNS flip) — we queue the request
          and ship the data within 5–10 business days.
        </p>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12, marginBottom: 16,
        }}>
          {Object.entries(regions).map(([code, info]) => (
            <RegionTile key={code} code={code} info={info}
                         selected={picked === code}
                         onSelect={setPicked}
                         testid={`compliance-region-${code}`}
                         disabled={busy} />
          ))}
        </div>
        <PrimaryButton onClick={saveResidency} busy={busy}
                        testid="compliance-residency-save-btn">
          {picked === residency?.region ? "No change" : "Queue migration"}
        </PrimaryButton>
        <div style={{ marginLeft: 14, display: "inline-block",
                       fontFamily: "'JetBrains Mono', monospace",
                       fontSize: 11, color: "#777" }}>
          Currently in {residency?.region?.toUpperCase() || "—"}{" "}
          since {residency?.effective_since?.slice(0, 10) || "—"}
        </div>
      </div>

      {/* SOC 2 download */}
      <div className="av2-card" data-testid="compliance-soc2-card">
        <h3 style={{
          fontFamily: "'Cinzel', serif", fontSize: 18,
          color: "var(--dash-text)", margin: "0 0 6px",
        }}>SOC 2 Type II evidence</h3>
        <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                     marginBottom: 16 }}>
          Generates a multi-page PDF covering CC1 (control environment),
          CC6 (logical access), CC7 (audit summary for the date window),
          CC8 (change management), Appendix A (residency), Appendix B
          (subprocessors). Hand to your auditor or attach to procurement
          reviews.
        </p>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end",
                       flexWrap: "wrap", marginBottom: 14 }}>
          <div>
            <label style={{
              display: "block",
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10, letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--dash-text-muted)", marginBottom: 6,
            }}>Start</label>
            <input type="date" value={soc2Start}
                    onChange={e => setSoc2Start(e.target.value)}
                    data-testid="compliance-soc2-start"
                    className="dev-input" />
          </div>
          <div>
            <label style={{
              display: "block",
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10, letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--dash-text-muted)", marginBottom: 6,
            }}>End</label>
            <input type="date" value={soc2End}
                    onChange={e => setSoc2End(e.target.value)}
                    data-testid="compliance-soc2-end"
                    className="dev-input" />
          </div>
        </div>
        <PrimaryButton onClick={downloadSoc2} busy={busy}
                        testid="compliance-soc2-download-btn">
          Download PDF
        </PrimaryButton>
      </div>

    </EnterpriseAdminShell>
  );
}
