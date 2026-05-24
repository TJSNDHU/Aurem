/**
 * EnterpriseSSO — /enterprise/admin/sso
 *
 * Two stacked cards:
 *   1. SAML config form — IdP entity ID, SSO URL, x509 cert, attribute map,
 *      status toggle (pending → active). "Test connection" button does a
 *      light fetch to /api/saml/{org_id}/metadata to confirm the SP-side
 *      pieces resolve.
 *   2. SCIM token management — list / issue (reveal once) / revoke.
 *
 * Backend wiring (already shipped iter 332b B-2/B-3):
 *   GET    /api/saml/{org_id}/config
 *   PUT    /api/saml/{org_id}/config
 *   DELETE /api/saml/{org_id}/config
 *   GET    /api/saml/{org_id}/metadata      (SP XML)
 *   GET    /api/scim/{org_id}/tokens
 *   POST   /api/scim/{org_id}/tokens
 *   DELETE /api/scim/{org_id}/tokens/{id}
 */
import React, { useEffect, useState } from "react";
import EnterpriseAdminShell, { Banner, PrimaryButton, ENT_API, adminHeaders }
  from "./EnterpriseAdminShell";

const ORANGE = "#FF6B00";

const PROVIDERS = [
  { value: "okta",      label: "Okta" },
  { value: "azure_ad",  label: "Azure AD / Entra ID" },
  { value: "google",    label: "Google Workspace" },
  { value: "onelogin",  label: "OneLogin" },
  { value: "generic",   label: "Generic SAML 2.0" },
];

function MonoLabel({ children }) {
  return (
    <label style={{ display: "block",
                     fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 10, letterSpacing: "0.18em",
                     textTransform: "uppercase",
                     color: "var(--dash-text-muted)", marginBottom: 6 }}>
      {children}
    </label>
  );
}

function TextField({ label, value, onChange, placeholder, testid, type = "text" }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <MonoLabel>{label}</MonoLabel>
      <input type={type} value={value || ""} placeholder={placeholder}
              data-testid={testid}
              onChange={(e) => onChange(e.target.value)}
              className="dev-input" style={{ width: "100%" }} />
    </div>
  );
}

function TextAreaField({ label, value, onChange, placeholder, testid, rows = 6 }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <MonoLabel>{label}</MonoLabel>
      <textarea value={value || ""} placeholder={placeholder} rows={rows}
                 data-testid={testid}
                 onChange={(e) => onChange(e.target.value)}
                 className="dev-input"
                 style={{ width: "100%",
                           fontFamily: "'JetBrains Mono', monospace",
                           fontSize: 11, lineHeight: 1.5,
                           resize: "vertical" }} />
    </div>
  );
}

export default function EnterpriseSSO() {
  const [orgs, setOrgs]     = useState([]);
  const [orgId, setOrgId]   = useState(null);

  // SAML state
  const [saml, setSaml] = useState({
    idp_provider:  "okta",
    idp_entity_id: "",
    idp_sso_url:   "",
    idp_cert:      "",
    status:        "pending",
    default_role:  "member",
  });
  const [samlMeta, setSamlMeta] = useState(null);  // {acs_url, sp_entity_id}
  const [samlBusy, setSamlBusy] = useState(false);
  const [samlBanner, setSamlBanner] = useState(null);
  const [testBusy, setTestBusy] = useState(false);

  // SCIM state
  const [scimTokens, setScimTokens] = useState([]);
  const [scimName, setScimName] = useState("");
  const [scimReveal, setScimReveal] = useState(null);  // {token, key_id}
  const [scimBusy, setScimBusy] = useState(false);
  const [scimBanner, setScimBanner] = useState(null);

  // ── Load orgs
  useEffect(() => {
    fetch(`${ENT_API}/api/orgs/me`, { headers: adminHeaders() })
      .then(r => r.json())
      .then(d => {
        if (d.ok && d.rows?.length) {
          setOrgs(d.rows);
          setOrgId(d.current_org_id || d.rows[0].org_id);
        }
      })
      .catch(() => { /* Banner below */ });
  }, []);

  // ── Hydrate SAML config + SCIM tokens on orgId change
  useEffect(() => {
    if (!orgId) return;
    fetch(`${ENT_API}/api/saml/${orgId}/config`, { headers: adminHeaders() })
      .then(r => r.json())
      .then(d => {
        if (d.ok && d.config) {
          setSaml({
            idp_provider:  d.config.idp_provider || "okta",
            idp_entity_id: d.config.idp_entity_id || "",
            idp_sso_url:   d.config.idp_sso_url || "",
            idp_cert:      d.config.idp_cert || "",
            status:        d.config.status || "pending",
            default_role:  d.config.default_role || "member",
          });
          setSamlMeta({
            acs_url:       d.config.acs_url,
            sp_entity_id:  d.config.sp_entity_id,
          });
        }
      })
      .catch(() => { /* ignore */ });

    fetch(`${ENT_API}/api/scim/${orgId}/tokens`, { headers: adminHeaders() })
      .then(r => r.json())
      .then(d => { if (d.ok) setScimTokens(d.rows || []); })
      .catch(() => { /* ignore */ });
  }, [orgId]);

  // ── SAML save
  const saveSaml = async () => {
    if (!orgId) return;
    setSamlBusy(true); setSamlBanner(null);
    try {
      const res = await fetch(`${ENT_API}/api/saml/${orgId}/config`, {
        method: "PUT",
        headers: adminHeaders(),
        body: JSON.stringify(saml),
      });
      const d = await res.json();
      if (res.ok && d.ok) {
        setSamlMeta({
          acs_url:      d.config.acs_url,
          sp_entity_id: d.config.sp_entity_id,
        });
        setSamlBanner({
          tone: "ok",
          text: `Saved. Status: ${d.config.status.toUpperCase()}.${d.config.status === "active" ? " SSO is now live." : " Flip status to ACTIVE when ready."}`,
        });
      } else {
        setSamlBanner({ tone: "warn",
                          text: d.detail || d.error || "Save failed." });
      }
    } catch {
      setSamlBanner({ tone: "warn", text: "Network error. Try again." });
    } finally {
      setSamlBusy(false);
    }
  };

  // ── Test connection: hit the SP metadata XML
  const testConnection = async () => {
    if (!orgId) return;
    setTestBusy(true); setSamlBanner(null);
    try {
      const res = await fetch(`${ENT_API}/api/saml/${orgId}/metadata`);
      if (!res.ok) {
        setSamlBanner({ tone: "warn",
                          text: `SP metadata endpoint returned HTTP ${res.status}. Save the config first.` });
      } else {
        const xml = await res.text();
        if (xml.includes("EntityDescriptor")) {
          setSamlBanner({ tone: "ok",
                            text: "✓ SP metadata is reachable. Copy your IdP-side fields from the box below and finish the IdP setup." });
        } else {
          setSamlBanner({ tone: "warn",
                            text: "SP metadata response was not valid XML. Check the org settings." });
        }
      }
    } catch {
      setSamlBanner({ tone: "warn", text: "Could not reach the SP metadata endpoint." });
    } finally {
      setTestBusy(false);
    }
  };

  // ── SCIM token actions
  const issueScimToken = async (e) => {
    e?.preventDefault?.();
    if (!orgId || !scimName.trim()) return;
    setScimBusy(true); setScimBanner(null); setScimReveal(null);
    try {
      const res = await fetch(`${ENT_API}/api/scim/${orgId}/tokens`, {
        method: "POST", headers: adminHeaders(),
        body: JSON.stringify({ name: scimName }),
      });
      const d = await res.json();
      if (res.ok && d.ok) {
        setScimReveal({ token: d.token, token_id: d.token_id });
        setScimName("");
        // refresh list
        const list = await fetch(`${ENT_API}/api/scim/${orgId}/tokens`,
                                   { headers: adminHeaders() }).then(r => r.json());
        setScimTokens(list.rows || []);
      } else {
        setScimBanner({ tone: "warn", text: d.detail || d.error || "Issue failed." });
      }
    } catch {
      setScimBanner({ tone: "warn", text: "Network error." });
    } finally {
      setScimBusy(false);
    }
  };

  const revokeScim = async (token_id) => {
    if (!window.confirm("Revoke this SCIM token? The IdP using it will stop syncing immediately.")) return;
    try {
      await fetch(`${ENT_API}/api/scim/${orgId}/tokens/${token_id}`, {
        method: "DELETE", headers: adminHeaders(),
      });
      const list = await fetch(`${ENT_API}/api/scim/${orgId}/tokens`,
                                 { headers: adminHeaders() }).then(r => r.json());
      setScimTokens(list.rows || []);
      setScimBanner({ tone: "ok", text: "Token revoked." });
    } catch {
      setScimBanner({ tone: "warn", text: "Revoke failed." });
    }
  };

  if (!orgs.length) {
    return (
      <EnterpriseAdminShell eyebrow="ENTERPRISE / SSO &amp; SCIM"
                              title="Single sign-on & user provisioning"
                              sub="SAML 2.0 + SCIM 2.0 for Okta, Azure AD, Google Workspace, OneLogin.">
        <Banner tone="warn" testid="sso-no-org-banner">
          No organizations on your account. Create one via POST /api/orgs
          before configuring SSO.
        </Banner>
      </EnterpriseAdminShell>
    );
  }

  return (
    <EnterpriseAdminShell eyebrow="ENTERPRISE / SSO &amp; SCIM"
                            title="Single sign-on & user provisioning"
                            sub="SAML 2.0 + SCIM 2.0 for Okta, Azure AD, Google Workspace, OneLogin.">

      {/* Org selector when admin owns more than one */}
      {orgs.length > 1 && (
        <div style={{ marginBottom: 18 }}>
          <MonoLabel>Organization</MonoLabel>
          <select data-testid="sso-org-selector"
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

      {/* SAML config card */}
      <div className="av2-card" data-testid="sso-saml-card"
            style={{ marginBottom: 18 }}>
        <h3 style={{ fontFamily: "'Cinzel', serif", fontSize: 18,
                      color: "var(--dash-text)", margin: "0 0 6px" }}>
          SAML 2.0 single sign-on
        </h3>
        <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                     marginBottom: 16 }}>
          Paste the IdP-side metadata your security team gave you. We'll
          generate the SP-side URLs you need to paste back into Okta /
          Azure / Google.
        </p>

        {samlBanner && (
          <Banner tone={samlBanner.tone} testid="sso-saml-banner">
            {samlBanner.text}
          </Banner>
        )}

        <div style={{ marginBottom: 12 }}>
          <MonoLabel>IdP provider</MonoLabel>
          <select data-testid="sso-saml-provider"
                   value={saml.idp_provider}
                   onChange={e => setSaml({ ...saml, idp_provider: e.target.value })}
                   className="dev-input" style={{ width: "100%" }}>
            {PROVIDERS.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <TextField label="IdP entity ID"
                    value={saml.idp_entity_id}
                    onChange={v => setSaml({ ...saml, idp_entity_id: v })}
                    placeholder="http://www.okta.com/exk1abcde"
                    testid="sso-saml-entity-id" />
        <TextField label="IdP SSO URL"
                    value={saml.idp_sso_url}
                    onChange={v => setSaml({ ...saml, idp_sso_url: v })}
                    placeholder="https://acme.okta.com/app/abc/sso/saml"
                    testid="sso-saml-sso-url" />
        <TextAreaField label="IdP X.509 certificate (PEM)"
                        value={saml.idp_cert}
                        onChange={v => setSaml({ ...saml, idp_cert: v })}
                        placeholder="-----BEGIN CERTIFICATE-----&#10;MIID…&#10;-----END CERTIFICATE-----"
                        testid="sso-saml-cert" rows={6} />

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr",
                       gap: 12, marginBottom: 16 }}>
          <div>
            <MonoLabel>Status</MonoLabel>
            <select data-testid="sso-saml-status"
                     value={saml.status}
                     onChange={e => setSaml({ ...saml, status: e.target.value })}
                     className="dev-input" style={{ width: "100%" }}>
              <option value="pending">Pending (config only)</option>
              <option value="active">Active (live SSO)</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
          <div>
            <MonoLabel>Default role for new users</MonoLabel>
            <select data-testid="sso-saml-default-role"
                     value={saml.default_role}
                     onChange={e => setSaml({ ...saml, default_role: e.target.value })}
                     className="dev-input" style={{ width: "100%" }}>
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
        </div>

        {/* SP-side metadata (read-only) */}
        {samlMeta && (
          <div data-testid="sso-sp-metadata-box"
                style={{ background: "rgba(0,0,0,0.30)",
                          border: "1px solid rgba(255,107,0,0.15)",
                          padding: 14, borderRadius: 6,
                          marginBottom: 16,
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 11, color: "#ddd",
                          display: "grid", gap: 6 }}>
            <div style={{ fontSize: 9, color: "#888",
                           letterSpacing: "0.20em",
                           textTransform: "uppercase", marginBottom: 4 }}>
              Paste these into your IdP setup
            </div>
            <div><span style={{ color: "#888" }}>SP Entity ID: </span>{samlMeta.sp_entity_id}</div>
            <div><span style={{ color: "#888" }}>ACS URL:      </span>{samlMeta.acs_url}</div>
          </div>
        )}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <PrimaryButton onClick={saveSaml} busy={samlBusy}
                          testid="sso-saml-save-btn">
            Save SAML config
          </PrimaryButton>
          <button
            data-testid="sso-saml-test-btn"
            onClick={testConnection} disabled={testBusy}
            style={{
              padding: "10px 20px",
              background: "transparent",
              color: "var(--dash-text)",
              border: "1px solid var(--dash-text-muted)",
              borderRadius: 6, fontSize: 13, cursor: "pointer",
              opacity: testBusy ? 0.5 : 1,
            }}>
            {testBusy ? "Testing…" : "Test connection"}
          </button>
        </div>
      </div>

      {/* SCIM card */}
      <div className="av2-card" data-testid="sso-scim-card">
        <h3 style={{ fontFamily: "'Cinzel', serif", fontSize: 18,
                      color: "var(--dash-text)", margin: "0 0 6px" }}>
          SCIM 2.0 user provisioning
        </h3>
        <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                     marginBottom: 16 }}>
          Issue a bearer token for your IdP. Okta / Azure AD push user
          create / disable events to{" "}
          <code style={{ color: ORANGE, fontFamily: "inherit" }}>
            {ENT_API}/scim/v2/{orgId}/Users
          </code>{" "}
          using that token.
        </p>

        {scimBanner && (
          <Banner tone={scimBanner.tone} testid="sso-scim-banner">
            {scimBanner.text}
          </Banner>
        )}

        {scimReveal && (
          <div data-testid="sso-scim-reveal"
                style={{ background: "rgba(242,194,101,0.10)",
                          border: `1px solid rgba(242,194,101,0.40)`,
                          padding: 14, borderRadius: 6, marginBottom: 14 }}>
            <div style={{ fontSize: 9, color: "#F2C265",
                           letterSpacing: "0.20em",
                           textTransform: "uppercase", marginBottom: 6 }}>
              Save this NOW — you won't see it again
            </div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace",
                           fontSize: 12, color: "#f6f5f1",
                           wordBreak: "break-all", marginBottom: 8 }}>
              {scimReveal.token}
            </div>
            <button onClick={() => {
                      navigator.clipboard?.writeText(scimReveal.token);
                    }}
                    data-testid="sso-scim-copy-btn"
                    style={{ padding: "6px 12px", background: ORANGE,
                              color: "#0a0a0a", border: "none",
                              borderRadius: 4, fontSize: 10,
                              letterSpacing: "0.15em",
                              textTransform: "uppercase", cursor: "pointer",
                              fontFamily: "'JetBrains Mono', monospace" }}>
              Copy
            </button>
          </div>
        )}

        <form onSubmit={issueScimToken}
               style={{ display: "flex", gap: 10, marginBottom: 18,
                         alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <MonoLabel>Token name (for your records)</MonoLabel>
            <input type="text" value={scimName}
                    data-testid="sso-scim-name"
                    onChange={e => setScimName(e.target.value)}
                    placeholder="e.g. Okta production integration"
                    className="dev-input" style={{ width: "100%" }} />
          </div>
          <PrimaryButton busy={scimBusy} testid="sso-scim-issue-btn">
            Issue token
          </PrimaryButton>
        </form>

        {/* List */}
        <div data-testid="sso-scim-list">
          {scimTokens.length === 0 ? (
            <div style={{ padding: 14, textAlign: "center",
                           fontFamily: "'JetBrains Mono', monospace",
                           fontSize: 11, color: "#666" }}>
              No SCIM tokens yet.
            </div>
          ) : (
            <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
              {scimTokens.map(t => (
                <div key={t.token_id}
                      data-testid={`sso-scim-row-${t.token_id}`}
                      style={{ display: "grid",
                                gridTemplateColumns: "1fr 200px auto",
                                gap: 12, padding: "12px 0",
                                borderBottom: "1px solid rgba(255,255,255,0.04)",
                                alignItems: "center",
                                fontFamily: "'JetBrains Mono', monospace",
                                fontSize: 11, color: "#ddd" }}>
                  <div>
                    <div style={{ color: "#f6f5f1", fontSize: 12 }}>{t.name}</div>
                    <div style={{ color: "#777", fontSize: 10, marginTop: 2 }}>
                      {t.token_preview} · created {(t.created_at || "").slice(0, 10)}
                      {t.last_used_at && ` · last used ${t.last_used_at.slice(0, 10)}`}
                    </div>
                  </div>
                  <div style={{ color: "#888", fontSize: 10 }}>
                    {(t.scopes || []).join(", ")}
                  </div>
                  <div>
                    {t.revoked_at ? (
                      <span style={{ color: "#777" }}>revoked</span>
                    ) : (
                      <button onClick={() => revokeScim(t.token_id)}
                              data-testid={`sso-scim-revoke-${t.token_id}`}
                              style={{ padding: "4px 10px",
                                        background: "transparent",
                                        color: "#EF4444",
                                        border: "1px solid rgba(239,68,68,0.30)",
                                        borderRadius: 4, fontSize: 10,
                                        letterSpacing: "0.10em",
                                        textTransform: "uppercase",
                                        cursor: "pointer",
                                        fontFamily: "inherit" }}>
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

    </EnterpriseAdminShell>
  );
}
