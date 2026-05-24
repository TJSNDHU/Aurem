/**
 * EnterpriseAdminShell — iter 332b A-2b
 * Shared shell for all /enterprise/admin/* pages. Reuses the dashboard-mode
 * DeveloperShell styling (av2-card primitives) but adds an enterprise nav.
 */
import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Palette, Globe, KeyRound, ShieldCheck,
} from "lucide-react";
import DeveloperShell from "../developers/DeveloperShell";

const NAV = [
  { to: "/enterprise/admin",            label: "Overview",   icon: LayoutDashboard, testid: "ent-nav-overview" },
  { to: "/enterprise/admin/branding",   label: "Branding",   icon: Palette,         testid: "ent-nav-branding" },
  { to: "/enterprise/admin/domain",     label: "Domain",     icon: Globe,           testid: "ent-nav-domain" },
  { to: "/enterprise/admin/keys",       label: "API Keys",   icon: KeyRound,        testid: "ent-nav-keys" },
  { to: "/enterprise/admin/compliance", label: "Compliance", icon: ShieldCheck,     testid: "ent-nav-compliance" },
];

export default function EnterpriseAdminShell({ children, eyebrow, title, sub }) {
  const loc = useLocation();
  // Note: This area uses platform_token (admin) auth, NOT dev_jwt.
  // We do not wrap in DeveloperShell's requireAuth gate — backend
  // 401s drive the auth UX instead.
  return (
    <DeveloperShell>
      <div style={{ marginBottom: 18 }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10, letterSpacing: "0.2em",
          textTransform: "uppercase",
          color: "var(--dash-orange)",
        }}>{eyebrow}</span>
        <h1 style={{
          fontFamily: "'Cinzel', serif",
          fontSize: 26, fontWeight: 600,
          color: "var(--dash-text)", margin: "8px 0 6px",
        }}>{title}</h1>
        {sub && (
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
            {sub}
          </p>
        )}
      </div>

      {/* Pill nav */}
      <div data-testid="enterprise-admin-nav"
            style={{ display: "flex", gap: 6, flexWrap: "wrap",
                      marginBottom: 18,
                      borderBottom: "1px solid var(--dash-divider)",
                      paddingBottom: 6 }}>
        {NAV.map((n) => {
          const active = loc.pathname === n.to;
          const Icon = n.icon;
          return (
            <Link key={n.to} to={n.to}
                   data-testid={n.testid}
                   style={{
                     display: "inline-flex", alignItems: "center", gap: 6,
                     padding: "6px 12px", borderRadius: 6,
                     fontSize: 12, fontWeight: 500,
                     color: active
                       ? "var(--dash-orange)"
                       : "var(--dash-text-muted)",
                     background: active
                       ? "rgba(255,107,0,0.08)"
                       : "transparent",
                     textDecoration: "none",
                     transition: "all 160ms ease",
                   }}>
              <Icon size={12} /> {n.label}
            </Link>
          );
        })}
      </div>

      {children}
    </DeveloperShell>
  );
}

// Shared inline-input helper used by all sub-pages
export function Field({ label, value, onChange, type = "text", testid, placeholder }) {
  return (
    <label style={{ display: "block" }}>
      <span style={{
        display: "block",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--dash-text-muted)", marginBottom: 6,
      }}>{label}</span>
      <input data-testid={testid} type={type} value={value}
              placeholder={placeholder}
              onChange={e => onChange(e.target.value)}
              className="dev-input"
              style={{ width: "100%" }} />
    </label>
  );
}

export function PrimaryButton({ onClick, busy, children, testid }) {
  return (
    <button data-testid={testid} onClick={onClick} disabled={busy}
             style={{
               padding: "10px 20px",
               background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
               color: "#fff", border: "none", borderRadius: 6,
               fontSize: 13, fontWeight: 500, cursor: "pointer",
               opacity: busy ? 0.5 : 1,
               display: "inline-flex", alignItems: "center", gap: 8,
             }}>
      {busy ? "…" : children}
    </button>
  );
}

export function Banner({ tone = "info", testid, children }) {
  const color = tone === "ok" ? "var(--dash-green)"
              : tone === "warn" ? "var(--dash-amber)"
              : "var(--dash-red)";
  return (
    <div data-testid={testid} className="av2-card"
          style={{
            borderColor: `${color}55`,
            background: `${color}11`,
            color, fontSize: 13,
          }}>
      {children}
    </div>
  );
}

export const ENT_API = process.env.REACT_APP_BACKEND_URL || "";

export function adminHeaders() {
  const t = localStorage.getItem("platform_token")
        || localStorage.getItem("aurem_admin_token")
        || localStorage.getItem("admin_token")
        || localStorage.getItem("token")
        || "";
  return t ? { Authorization: `Bearer ${t}`,
                "Content-Type": "application/json" }
            : { "Content-Type": "application/json" };
}
