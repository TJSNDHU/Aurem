/**
 * OraAdminUnified.jsx — One unified frontend for everything ORA.
 *
 * Founder mandate (iter 322ex):
 *   "Admin ORA ko multitask bnao jisma ik he ORA frontend ho or vo sara
 *    task apna aap automaticaly backend select kr k ik he frontend main
 *    perform kre. ORA PWA and ORA CTO Bhe usi main ho jaye and ye only
 *    admin LOcked ho."
 *
 * What this page does:
 *   1. ONE entry-point at /admin/ora for ALL ORA capabilities:
 *      - Chat (auto-routing tool picker — backend's ora_agent.run_turn
 *        already does this via the 35-tool LLM loop)
 *      - Cockpit (live audit trail, tool invocations, council overrides)
 *      - Settings (permissions, council vote rules, audit retention)
 *      - Optimizer (LLM budget watchdog)
 *      - Founder Console (the legacy /admin/console — chat with ORA Brain)
 *
 *   2. Admin-locked at the component level. Non-admin = bounce to login.
 *
 *   3. Mobile-first: same beautiful PWA-style chrome on small screens,
 *      side-rail nav on desktop. Bottom tab-bar on mobile.
 *
 * Auto task selection:
 *   The CHAT panel is the primary surface. Whatever the founder types,
 *   the backend (services/ora_agent.py) picks the right tools
 *   automatically — no manual mode-switching needed. The other tabs are
 *   read-only / config panels for when the founder wants to inspect or
 *   tune ORA herself.
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Crown, MessageSquare, Activity, Settings as SettingsIcon,
  Zap, Terminal, LogOut, Menu, X,
} from "lucide-react";

import OraChat from "./OraChat";
import OraCtoCockpit from "./OraCtoCockpit";
import OraSettings from "./OraSettings";
import OraOptimizer from "./OraOptimizer";
import CommandPalette from "./CommandPalette";

// We lazy-load the legacy founder console so its 1374-line bundle only
// loads when the founder explicitly opens the Console tab.
const AdminConsole = React.lazy(() => import("../AdminConsole"));

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const BG = "#0A0A12";
const PANEL_BG = "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))";

const TABS = [
  { id: "chat",      label: "Chat",       icon: MessageSquare, Comp: OraChat },
  { id: "cockpit",   label: "Cockpit",    icon: Activity,      Comp: OraCtoCockpit },
  { id: "console",   label: "Console",    icon: Terminal,      Comp: AdminConsole, lazy: true },
  { id: "optimizer", label: "Optimizer",  icon: Zap,           Comp: OraOptimizer },
  { id: "settings",  label: "Settings",   icon: SettingsIcon,  Comp: OraSettings },
];

function readToken() {
  try {
    return (
      sessionStorage.getItem("platform_token") ||
      localStorage.getItem("platform_token") ||
      localStorage.getItem("aurem_admin_token") ||
      sessionStorage.getItem("aurem_admin_token") ||
      localStorage.getItem("token") ||
      ""
    );
  } catch { return ""; }
}

function decodeJwt(token) {
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    const padded = part + "===".slice((part.length + 3) % 4);
    return JSON.parse(atob(padded.replace(/-/g, "+").replace(/_/g, "/")));
  } catch { return null; }
}

function useAdminGate() {
  const [state, setState] = useState({ loading: true, ok: false, payload: null });
  useEffect(() => {
    const tok = readToken();
    const p = decodeJwt(tok);
    if (!p) {
      setState({ loading: false, ok: false, payload: null });
      return;
    }
    const adminEmails = new Set([
      "teji.ss1986@gmail.com",
      "admin@aurem.live",
    ]);
    const isAdmin = !!(
      p.is_admin ||
      p.is_super_admin ||
      p.role === "admin" ||
      p.role === "super_admin" ||
      (p.email && adminEmails.has(String(p.email).toLowerCase()))
    );
    setState({ loading: false, ok: isAdmin, payload: p });
  }, []);
  return state;
}

function tabFromUrl(location) {
  // Allow ?tab=cockpit OR #cockpit to deep-link.
  const sp = new URLSearchParams(location.search);
  const fromSearch = sp.get("tab");
  if (fromSearch && TABS.find((t) => t.id === fromSearch)) return fromSearch;
  const fromHash = (location.hash || "").replace("#", "").trim();
  if (fromHash && TABS.find((t) => t.id === fromHash)) return fromHash;
  return "chat";
}

export default function OraAdminUnified() {
  const navigate = useNavigate();
  const location = useLocation();
  const gate = useAdminGate();
  const [active, setActive] = useState(() => tabFromUrl(location));
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMobile = useIsMobile();

  // Keep URL in sync so refresh / share preserves the active tab.
  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    if (sp.get("tab") !== active) {
      sp.set("tab", active);
      navigate({ pathname: "/admin/ora", search: `?${sp.toString()}` }, { replace: true });
    }
  }, [active, location.search, navigate]);

  if (gate.loading) {
    return (
      <div style={{ minHeight: "100vh", background: BG, color: TEXT_DIM,
        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
        Verifying admin session…
      </div>
    );
  }

  if (!gate.ok) {
    return (
      <div style={{ minHeight: "100vh", background: BG, color: TEXT, padding: 40,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <Crown size={32} color={GOLD} />
        <h2 style={{ marginTop: 16 }}>ORA — Admin Only</h2>
        <p style={{ color: TEXT_DIM, marginBottom: 24 }}>
          You need a founder / super-admin token to access this surface.
        </p>
        <button
          data-testid="ora-admin-login-btn"
          onClick={() => navigate("/admin/login")}
          style={{ ...btn(true) }}
        >
          Go to Admin Login
        </button>
      </div>
    );
  }

  const ActiveTab = TABS.find((t) => t.id === active) || TABS[0];

  return (
    <div data-testid="ora-admin-unified" style={{ minHeight: "100vh", background: BG, color: TEXT, display: "flex" }}>
      {/* DESKTOP SIDEBAR */}
      {!isMobile && (
        <aside style={{
          width: 220, padding: "20px 14px", borderRight: `1px solid ${BORDER}`,
          background: PANEL_BG, position: "sticky", top: 0, height: "100vh",
          display: "flex", flexDirection: "column", gap: 6,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 6px 18px" }}>
            <Crown size={20} color={GOLD} />
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>ORA</div>
              <div style={{ fontSize: 10, color: TEXT_DIM, letterSpacing: 0.3 }}>Admin · iter 322ex</div>
            </div>
          </div>

          {TABS.map((t) => (
            <NavButton key={t.id} tab={t} active={active === t.id} onClick={() => setActive(t.id)} />
          ))}

          <div style={{ flex: 1 }} />
          <div style={{ fontSize: 11, color: TEXT_DIM, padding: "10px 6px", borderTop: `1px solid ${BORDER}` }}>
            {gate.payload?.email || "admin"}
          </div>
          <button
            data-testid="ora-admin-logout-btn"
            onClick={() => { try { localStorage.clear(); sessionStorage.clear(); } catch {} navigate("/admin/login"); }}
            style={{ ...btn(false), justifyContent: "flex-start" }}
          >
            <LogOut size={14} /> Logout
          </button>
        </aside>
      )}

      {/* MOBILE TOP-BAR */}
      {isMobile && (
        <header style={{
          position: "fixed", top: 0, left: 0, right: 0, height: 52, zIndex: 30,
          display: "flex", alignItems: "center", gap: 10, padding: "0 14px",
          background: PANEL_BG, borderBottom: `1px solid ${BORDER}`,
        }}>
          <button
            data-testid="ora-admin-menu-btn"
            onClick={() => setMobileOpen(true)}
            style={iconBtn}
            aria-label="Open menu"
          ><Menu size={20} color={TEXT} /></button>
          <Crown size={18} color={GOLD} />
          <div style={{ fontWeight: 700, fontSize: 15 }}>{ActiveTab.label}</div>
        </header>
      )}

      {/* MOBILE DRAWER */}
      {isMobile && mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: "fixed", inset: 0, zIndex: 40,
            background: "rgba(0,0,0,0.55)", backdropFilter: "blur(2px)",
          }}>
          <aside onClick={(e) => e.stopPropagation()} style={{
            width: 260, height: "100vh", padding: "20px 14px",
            background: BG, borderRight: `1px solid ${BORDER}`,
            display: "flex", flexDirection: "column", gap: 6,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 6px 18px" }}>
              <Crown size={20} color={GOLD} />
              <div style={{ fontWeight: 700, fontSize: 15 }}>ORA Admin</div>
              <div style={{ flex: 1 }} />
              <button data-testid="ora-admin-drawer-close" onClick={() => setMobileOpen(false)} style={iconBtn}>
                <X size={18} color={TEXT_DIM} />
              </button>
            </div>
            {TABS.map((t) => (
              <NavButton key={t.id} tab={t} active={active === t.id}
                onClick={() => { setActive(t.id); setMobileOpen(false); }} />
            ))}
            <div style={{ flex: 1 }} />
            <button
              onClick={() => { try { localStorage.clear(); sessionStorage.clear(); } catch {} navigate("/admin/login"); }}
              style={{ ...btn(false), justifyContent: "flex-start" }}>
              <LogOut size={14} /> Logout
            </button>
          </aside>
        </div>
      )}

      {/* MAIN PANEL — embeds the active component */}
      <main style={{
        flex: 1, minWidth: 0, overflowX: "hidden",
        paddingTop: isMobile ? 52 : 0,
      }}>
        <React.Suspense fallback={<TabLoading label={ActiveTab.label} />}>
          {/* keepAlive: we mount only the active tab; switching unmounts the others.
              Chat retains its session via SESSION_KEY in localStorage so the thread
              is not lost when the founder navigates away and back. */}
          <ActiveTab.Comp key={ActiveTab.id} />
        </React.Suspense>
      </main>

      {/* Founder velocity multiplier — ⌘K / Ctrl+K opens overlay */}
      <CommandPalette tabs={TABS} setActive={setActive} />
    </div>
  );
}

function NavButton({ tab, active, onClick }) {
  const Icon = tab.icon;
  return (
    <button
      data-testid={`ora-admin-tab-${tab.id}`}
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "10px 12px", borderRadius: 8,
        border: "1px solid transparent",
        background: active ? "rgba(212,175,55,0.10)" : "transparent",
        color: active ? GOLD : TEXT,
        fontSize: 13, fontWeight: active ? 600 : 500,
        cursor: "pointer", textAlign: "left", width: "100%",
        transition: "background 120ms ease, color 120ms ease",
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "rgba(255,255,255,0.04)"; }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
    >
      <Icon size={16} />
      <span>{tab.label}</span>
    </button>
  );
}

function TabLoading({ label }) {
  return (
    <div style={{ padding: 40, color: TEXT_DIM, fontSize: 13 }}>
      Loading {label}…
    </div>
  );
}

function useIsMobile() {
  const [m, setM] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth <= 768;
  });
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onR = () => setM(window.innerWidth <= 768);
    window.addEventListener("resize", onR);
    return () => window.removeEventListener("resize", onR);
  }, []);
  return m;
}

function btn(primary) {
  return {
    display: "inline-flex", alignItems: "center", gap: 8,
    padding: "8px 14px", borderRadius: 8,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    background: primary ? GOLD : "transparent",
    color: primary ? "#0B0B16" : TEXT,
    fontSize: 13, fontWeight: 600, cursor: "pointer",
  };
}

const iconBtn = {
  width: 32, height: 32, display: "inline-flex", alignItems: "center", justifyContent: "center",
  background: "transparent", border: "none", borderRadius: 6, cursor: "pointer",
};
