/**
 * CustomerShell.jsx — layout shell for the /my customer portal (iter D-82c).
 *
 * Renders the Luxe-styled left nav + <Outlet/> for the 8 customer pages, using
 * the shared Luxe design tokens so it matches the /my home dashboard. Auth is
 * enforced upstream by CustomerGuard (this only mounts with a valid token).
 *
 * Mobile: nav collapses to a horizontal scroll bar under 768px.
 */
import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Globe, Star, Share2, FileText, Gift, CreditCard,
  MessageSquare, Settings, Home, LogOut, Activity, Target, CalendarDays,
} from "lucide-react";
import { GOLD, INK, PANEL, STROKE, TEXT_HI, TEXT_MD } from "../luxe/tokens";
import { clearCustomerAuth } from "../../utils/secureTokenStore";

const NAV = [
  { to: "/my",             label: "Home",         icon: Home, end: true },
  { to: "/my/activity",    label: "Activity",     icon: Activity },
  { to: "/my/website",     label: "Website",      icon: Globe },
  { to: "/my/leads",       label: "Leads",        icon: Target },
  { to: "/my/appointments",label: "Appointments", icon: CalendarDays },
  { to: "/my/reviews",     label: "Reviews",      icon: Star },
  { to: "/my/social",      label: "Social",       icon: Share2 },
  { to: "/my/report",      label: "Reports",      icon: FileText },
  { to: "/my/referrals",   label: "Referrals",    icon: Gift },
  { to: "/my/billing",     label: "Billing",      icon: CreditCard },
  { to: "/my/ora",         label: "Ask ORA",      icon: MessageSquare },
  { to: "/my/settings",    label: "Settings",     icon: Settings },
];

export default function CustomerShell() {
  const navigate = useNavigate();

  const logout = () => {
    try { clearCustomerAuth(); } catch { /* ignore */ }
    navigate("/my", { replace: true });
  };

  return (
    <div style={{ minHeight: "100vh", background: INK, color: TEXT_HI, display: "flex" }}
         data-testid="customer-shell">
      {/* ── Left nav (desktop) / top scroll bar (mobile) ── */}
      <nav className="cust-nav"
           style={{ background: PANEL, borderRight: `1px solid ${STROKE}`,
                    padding: "20px 12px", display: "flex",
                    flexDirection: "column", gap: 4, minWidth: 190 }}>
        <p style={{ color: GOLD, fontWeight: 600, fontSize: 14,
                    letterSpacing: 1, margin: "0 10px 14px" }}>
          MY AUREM
        </p>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}
                   data-testid={`cust-nav-${label.toLowerCase().replace(" ", "-")}`}
                   style={({ isActive }) => ({
                     display: "flex", alignItems: "center", gap: 10,
                     padding: "9px 12px", borderRadius: 10, fontSize: 14,
                     textDecoration: "none",
                     color: isActive ? GOLD : TEXT_MD,
                     background: isActive ? "rgba(212,163,115,0.10)" : "transparent",
                     border: isActive ? `1px solid ${STROKE}` : "1px solid transparent",
                   })}>
            <Icon size={16} aria-hidden />
            {label}
          </NavLink>
        ))}
        <button onClick={logout}
                data-testid="cust-nav-logout"
                style={{ marginTop: "auto", display: "flex", alignItems: "center",
                         gap: 10, padding: "9px 12px", borderRadius: 10,
                         fontSize: 14, color: TEXT_MD, background: "transparent",
                         border: "1px solid transparent", cursor: "pointer" }}>
          <LogOut size={16} aria-hidden />
          Log out
        </button>
      </nav>

      {/* ── Page body ── */}
      <main style={{ flex: 1, padding: "24px clamp(16px, 4vw, 40px)", maxWidth: 1100 }}>
        <Outlet />
      </main>

      {/* Mobile: collapse nav to horizontal bar */}
      <style>{`
        @media (max-width: 768px) {
          [data-testid="customer-shell"] { flex-direction: column; }
          .cust-nav {
            flex-direction: row !important;
            overflow-x: auto;
            min-width: 0 !important;
            border-right: none !important;
            border-bottom: 1px solid ${STROKE};
            padding: 10px 8px !important;
          }
          .cust-nav p, .cust-nav button { display: none !important; }
        }
      `}</style>
    </div>
  );
}
