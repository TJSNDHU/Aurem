/**
 * /enterprise/admin/branding — White-label settings
 * Logo URL + primary color picker + company name + live preview.
 */
import React, { useEffect, useState } from "react";
import { Upload, Palette as PaletteIcon } from "lucide-react";
import EnterpriseAdminShell, {
  Field, PrimaryButton, Banner, ENT_API, adminHeaders,
} from "./EnterpriseAdminShell";

export default function EnterpriseBranding() {
  const [form, setForm] = useState({
    tenant_id: "default", logo_url: "",
    primary_color: "#FF6B00", company_name: "",
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg]   = useState(null);
  const [err, setErr]   = useState(null);

  useEffect(() => {
    fetch(`${ENT_API}/api/enterprise/branding?tenant_id=default`,
           { headers: adminHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (j?.branding) setForm(prev => ({ ...prev, ...j.branding }));
      })
      .catch(() => {});
  }, []);

  async function save() {
    setBusy(true); setMsg(null); setErr(null);
    try {
      const r = await fetch(`${ENT_API}/api/enterprise/branding`, {
        method: "PUT",
        headers: adminHeaders(),
        body: JSON.stringify(form),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "save failed");
      setMsg("Branding saved. Reload the app to see it applied.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally { setBusy(false); }
  }

  return (
    <EnterpriseAdminShell
      eyebrow="ENTERPRISE / ADMIN"
      title="White-label branding"
      sub="Your logo, your colors, your name across the AUREM CTO app."
    >
      <div className="av2-grid-2">
        {/* Editor */}
        <div className="av2-card" data-testid="branding-editor"
              style={{ display: "grid", gap: 14 }}>
          <Field label="Tenant ID" value={form.tenant_id}
                  onChange={v => setForm({ ...form, tenant_id: v })}
                  testid="branding-tenant" />
          <Field label="Company name" value={form.company_name}
                  placeholder="e.g. Acme Corp"
                  onChange={v => setForm({ ...form, company_name: v })}
                  testid="branding-name" />
          <Field label="Logo URL (PNG/SVG)" value={form.logo_url}
                  placeholder="https://cdn.example.com/logo.svg"
                  onChange={v => setForm({ ...form, logo_url: v })}
                  testid="branding-logo" />
          <label>
            <span style={{
              display: "block",
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10, letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--dash-text-muted)", marginBottom: 6,
            }}>Primary color</span>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input data-testid="branding-color-picker"
                      type="color" value={form.primary_color || "#FF6B00"}
                      onChange={e => setForm({ ...form,
                                                primary_color: e.target.value })}
                      style={{ width: 44, height: 44, borderRadius: 6,
                                border: "1px solid rgba(255,107,0,0.20)",
                                background: "transparent",
                                cursor: "pointer" }} />
              <input data-testid="branding-color-hex"
                      value={form.primary_color}
                      onChange={e => setForm({ ...form,
                                                primary_color: e.target.value })}
                      className="dev-input"
                      style={{ width: 130 }} />
            </div>
          </label>
          <PrimaryButton onClick={save} busy={busy}
                          testid="branding-save-btn">
            <Upload size={13} /> Save branding
          </PrimaryButton>
          {msg && <Banner tone="ok" testid="branding-success">{msg}</Banner>}
          {err && <Banner tone="err" testid="branding-error">{err}</Banner>}
        </div>

        {/* Live preview */}
        <div className="av2-card" data-testid="branding-preview"
              style={{
                background: form.primary_color
                  ? `linear-gradient(160deg, ${form.primary_color}11, rgba(10,10,18,0.85))`
                  : undefined,
                display: "flex", flexDirection: "column", gap: 12,
                justifyContent: "center", alignItems: "center",
                minHeight: 260,
              }}>
          <PaletteIcon size={16} style={{ color: form.primary_color || "#FF6B00",
                                            opacity: 0.6 }} />
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10, letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "var(--dash-text-muted)",
          }}>Live preview</span>
          {form.logo_url ? (
            <img src={form.logo_url} alt="logo"
                  data-testid="branding-preview-logo"
                  style={{ maxHeight: 60, maxWidth: 240,
                            objectFit: "contain" }} />
          ) : (
            <span style={{
              fontFamily: "'Cinzel', serif", fontSize: 26, fontWeight: 700,
              color: form.primary_color || "var(--dash-gold-bright)",
              letterSpacing: "0.15em",
            }}>
              {form.company_name || "YOUR COMPANY"}
            </span>
          )}
          <button style={{
            padding: "8px 18px",
            background: form.primary_color
              ? `linear-gradient(135deg, ${form.primary_color}, ${form.primary_color}cc)`
              : "linear-gradient(135deg, #FF6B00, #FF8C35)",
            color: "#fff", border: "none", borderRadius: 6,
            fontSize: 13, fontWeight: 500,
          }}>Primary CTA</button>
        </div>
      </div>
    </EnterpriseAdminShell>
  );
}
