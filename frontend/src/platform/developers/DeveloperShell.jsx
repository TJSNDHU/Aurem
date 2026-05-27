/**
 * DeveloperShell.jsx — iter 331f-b
 * Two modes:
 *   • `landing`  → AUREM homepage style (Cinzel serif, orange→gold gradient,
 *                   dark void background, marketing feel). Used by
 *                   /developers ONLY.
 *   • `dashboard` → LuxeDashboardV2 style (Apple-ish av2-* primitives,
 *                   compact sans-serif, edge-to-edge sidebar). Used by
 *                   the 8 authed pages.
 *
 * Auth gating + token-chip + nav live inside the dashboard mode.
 */
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  Home as HomeIcon, Github, Activity, BarChart3, Coins,
  ScrollText, Settings as SettingsIcon, Briefcase, ShieldCheck,
  LogOut, Sun, Moon, BookOpen,
  ChevronLeft, ChevronRight, Menu, X,
} from "lucide-react";

import "../../styles/dashboard-theme.css";

const API = process.env.REACT_APP_BACKEND_URL || "";

// ────────────────────────────────────────────────────────────────
// Auth helpers
// ────────────────────────────────────────────────────────────────
export function getDevJwt() { return localStorage.getItem("dev_jwt") || ""; }
export function setDevJwt(t) {
  if (t) localStorage.setItem("dev_jwt", t);
  else   localStorage.removeItem("dev_jwt");
}
// iter 332b D-5 — falls back to platform admin JWT so the founder can
// browse /developers/* with their existing admin session. Backend
// auto-provisions an internal_admin developer row when the admin
// token hits /api/developers/me.
export function devAuthHeaders() {
  const t = getDevJwt()
         || localStorage.getItem("platform_token")
         || localStorage.getItem("aurem_admin_token")
         || "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export function useDevMe() {
  const [me, setMe]     = useState(null);
  const [loading, setL] = useState(true);
  const [error, setErr] = useState(null);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await fetch(`${API}/api/developers/me`,
                               { headers: devAuthHeaders() });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (!cancelled) setMe(j);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setL(false);
      }
    }
    if (getDevJwt()
        || localStorage.getItem("platform_token")
        || localStorage.getItem("aurem_admin_token")) {
      load();
    } else {
      setL(false);
    }
    return () => { cancelled = true; };
  }, []);
  return { me, loading, error };
}

// ────────────────────────────────────────────────────────────────
// Landing mode (homepage-style)
// ────────────────────────────────────────────────────────────────
const LANDING_FONTS_LINK = (
  <link
    rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Jost:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
  />
);

const LANDING_CSS = `
.dev-home {
  background: #050508;
  color: #F0EDE8;
  font-family: 'Jost', sans-serif;
  font-weight: 300;
  line-height: 1.6;
  min-height: 100vh;
  overflow-x: hidden;
}
.dev-home-bg-glow {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 90% 50% at 50% -10%, rgba(255,107,0,0.10) 0%, transparent 60%),
    radial-gradient(ellipse 50% 60% at 95% 40%, rgba(201,168,76,0.06) 0%, transparent 55%);
}
.dev-home-bg-grid {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(255,107,0,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,107,0,0.03) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: radial-gradient(ellipse 100% 70% at 50% 0%, black 20%, transparent 75%);
}
.dev-home nav.dev-topnav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 200;
  padding: 18px 5%;
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(to bottom, rgba(5,5,8,0.97), rgba(5,5,8,0.85));
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255,107,0,0.10);
}
.dev-wordmark {
  font-family: 'Cinzel', serif;
  font-size: 18px; font-weight: 700; letter-spacing: 0.2em;
  color: #E8C86A;
}
.dev-wordmark em {
  color: #7A7590; font-style: normal; font-size: 13px;
  letter-spacing: 0.15em; margin-left: 8px;
}
.dev-nav-login {
  background: transparent;
  border: 1px solid #E8C86A;
  color: #E8C86A;
  padding: 9px 20px;
  border-radius: 4px;
  font-size: 13px;
  letter-spacing: 0.05em;
  transition: all 0.2s;
  cursor: pointer;
}
.dev-nav-login:hover {
  background: rgba(201,168,76,0.10);
  border-color: #C9A84C;
}
.dev-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  border: 1px solid rgba(201,168,76,0.15);
  padding: 6px 18px; border-radius: 100px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; letter-spacing: 0.12em;
  color: #C9A84C;
}
.dev-eyebrow .dot {
  width: 6px; height: 6px; background: #FF6B00; border-radius: 50%;
  animation: dev-blink 2s ease-in-out infinite;
}
@keyframes dev-blink {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255,107,0,0.5); }
  50%      { opacity: 0.7; box-shadow: 0 0 0 8px rgba(255,107,0,0); }
}
.dev-title {
  font-family: 'Cinzel', serif;
  font-size: clamp(34px, 6vw, 78px);
  font-weight: 700;
  line-height: 1.06;
  letter-spacing: 0.02em;
  margin-bottom: 8px;
}
.dev-title .t1 { display: block; color: #F0EDE8; }
.dev-title .t2 {
  display: block;
  background: linear-gradient(135deg, #FF6B00 0%, #E8C86A 55%, #FF8C35 100%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.dev-punch {
  font-size: clamp(15px, 1.8vw, 19px);
  color: #7A7590;
  max-width: 580px;
  line-height: 1.75;
}
.dev-punch strong { color: #F0EDE8; font-weight: 500; }
.dev-btn-primary {
  background: linear-gradient(135deg, #FF6B00, #FF8C35);
  color: #fff; padding: 15px 38px;
  border-radius: 4px;
  font-size: 15px; font-weight: 500;
  letter-spacing: 0.05em;
  transition: all 0.25s;
  display: inline-flex; align-items: center; gap: 8px;
  border: none; cursor: pointer;
  font-family: 'Jost', sans-serif;
}
.dev-btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 40px rgba(255,107,0,0.35);
}
.dev-btn-ghost {
  background: transparent;
  color: #F0EDE8;
  padding: 14px 32px;
  border-radius: 4px;
  font-size: 15px;
  letter-spacing: 0.05em;
  transition: all 0.25s;
  border: 1px solid rgba(201,168,76,0.15);
  cursor: pointer;
}
.dev-btn-ghost:hover {
  background: rgba(201,168,76,0.08);
  border-color: #C9A84C;
}
.dev-section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #FF6B00;
  margin-bottom: 14px;
  display: block;
}
.dev-section-title {
  font-family: 'Cinzel', serif;
  font-size: clamp(24px, 3.5vw, 44px);
  font-weight: 600;
  line-height: 1.15;
  letter-spacing: 0.02em;
  color: #F0EDE8;
}
.dev-input {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,107,0,0.10);
  border-radius: 4px;
  padding: 13px 16px;
  color: #F0EDE8;
  font-family: 'Jost', sans-serif;
  font-size: 14px;
  outline: none;
  transition: border 0.2s;
}
.dev-input:focus { border-color: #FF6B00; }
.dev-input::placeholder { color: #4A4560; }
.dev-feature-card {
  background: #0F0F1A;
  border: 1px solid rgba(255,107,0,0.10);
  border-radius: 8px;
  padding: 32px 26px;
  position: relative;
  transition: border 0.2s, transform 0.2s;
}
.dev-feature-card:hover {
  border-color: rgba(201,168,76,0.30);
  transform: translateY(-2px);
}
.dev-feature-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, rgba(255,107,0,0.6), rgba(201,168,76,0.6));
}
`;

function LandingTopNav() {
  return (
    <nav className="dev-topnav" data-testid="dev-shell-topbar">
      <Link to="/developers" data-testid="dev-shell-logo"
             className="dev-wordmark" style={{ textDecoration: "none" }}>
        AUREM <em>/ DEVELOPERS</em>
      </Link>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <Link to="/developers/login" className="dev-nav-login"
               data-testid="dev-shell-login-link"
               style={{ textDecoration: "none" }}>
          Sign in
        </Link>
        <Link to="/developers/signup"
               data-testid="dev-shell-signup-cta"
               style={{
                 background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                 color: "#fff", padding: "9px 22px", borderRadius: 4,
                 fontSize: 13, letterSpacing: "0.05em",
                 textDecoration: "none", fontWeight: 500,
               }}>
          Claim 1000 tokens
        </Link>
      </div>
    </nav>
  );
}

function LandingShell({ children }) {
  return (
    <>
      {LANDING_FONTS_LINK}
      <style>{LANDING_CSS}</style>
      <div className="dev-home" data-testid="dev-shell">
        <div className="dev-home-bg-glow" />
        <div className="dev-home-bg-grid" />
        <LandingTopNav />
        <div style={{ position: "relative", zIndex: 1 }}>
          {children}
        </div>
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────
// Dashboard mode (LuxeDashboardV2 style)
// ────────────────────────────────────────────────────────────────
const DASH_NAV = [
  { to: "/developers/dashboard", label: "Home",       icon: HomeIcon,    testid: "dev-nav-dashboard" },
  { to: "/developers/connect",   label: "Connect",    icon: Github,      testid: "dev-nav-connect" },
  { to: "/developers/analytics", label: "Analytics",  icon: BarChart3,   testid: "dev-nav-analytics" },
  { to: "/developers/examples",  label: "Examples",   icon: Briefcase,   testid: "dev-nav-examples" },
  { to: "/developers/tokens",    label: "Tokens",     icon: Coins,       testid: "dev-nav-tokens" },
  { to: "/developers/docs",      label: "API Docs",   icon: BookOpen,    testid: "dev-nav-docs" },
  { to: "/developers/status",    label: "Status",     icon: Activity,    testid: "dev-nav-status" },
  { to: "/developers/settings",  label: "Settings",   icon: SettingsIcon,testid: "dev-nav-settings" },
  { to: "/developers/terms",     label: "Terms",      icon: ScrollText,  testid: "dev-nav-terms" },
];

function DashboardTopbar({ me, theme, toggleTheme, onMobileMenu, mobileOpen }) {
  const navigate = useNavigate();
  function logout() {
    setDevJwt("");
    navigate("/developers");
  }
  return (
    <div className="av2-topbar" data-testid="dev-shell-topbar">
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {/* iter D-38 — hamburger; CSS hides on >=768px */}
        <button className="av2-icon-btn av2-mobile-menu-btn"
                onClick={onMobileMenu}
                data-testid="dev-shell-mobile-menu"
                aria-label={mobileOpen ? "Close menu" : "Open menu"}
                aria-expanded={mobileOpen}>
          {mobileOpen ? <X size={16} /> : <Menu size={16} />}
        </button>
        <ShieldCheck size={18} style={{ color: "var(--dash-orange)" }} />
        <span style={{
          fontFamily: "'Cinzel', serif",
          fontSize: 14, fontWeight: 700,
          letterSpacing: "0.18em",
          color: "var(--dash-gold-bright)",
        }}>
          AUREM
        </span>
        <span style={{
          fontSize: 11, letterSpacing: "0.15em",
          color: "var(--dash-text-faint)",
        }}>
          / DEVELOPERS
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {me && (
          <div data-testid="dev-shell-token-chip"
                className="av2-pill"
                style={{
                  background: "rgba(255,107,0,0.10)",
                  color: "var(--dash-orange)",
                  borderColor: "rgba(255,107,0,0.30)",
                  fontWeight: 600,
                }}>
            <Coins size={11} /> {(me.tokens_remaining ?? 0).toLocaleString()}
          </div>
        )}
        <button className="av2-icon-btn" onClick={toggleTheme}
                 data-testid="dev-shell-theme-toggle"
                 aria-label="Toggle theme">
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
        <button className="av2-icon-btn" onClick={logout}
                 data-testid="dev-shell-logout"
                 aria-label="Log out">
          <LogOut size={15} />
        </button>
      </div>
    </div>
  );
}

function DashboardSidebar({ me, collapsed, onToggle }) {
  const loc = useLocation();
  const navigate = useNavigate();
  // iter 332b D-20 — saved projects list, sourced from
  // /api/developers/projects. Click a row to deep-link to
  // /developers/dashboard?project=<id> which the chat panel then loads.
  const [projects, setProjects] = useState([]);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await fetch(`${API}/api/developers/projects`,
                               { headers: devAuthHeaders() });
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled) setProjects(j.projects || []);
      } catch { /* ignore */ }
    }
    load();
    // Refresh when chat panel signals a new save.
    function onSaved() { load(); }
    window.addEventListener("dev-cto-project-saved", onSaved);
    return () => {
      cancelled = true;
      window.removeEventListener("dev-cto-project-saved", onSaved);
    };
  }, []);

  return (
    <aside className={`av2-sidebar av2-scroll${collapsed ? " av2-sidebar--collapsed" : ""}`}
           data-testid="dev-sidebar"
           data-collapsed={collapsed ? "true" : "false"}>
      <div style={{ padding: "0 6px 18px 6px",
                     borderBottom: "1px solid var(--dash-divider)",
                     marginBottom: 14,
                     display: "flex",
                     alignItems: "center",
                     justifyContent: collapsed ? "center" : "space-between",
                     gap: 8 }}>
        {!collapsed && (
          <div>
            <div style={{
              fontFamily: "'Cinzel', serif",
              fontSize: 16, fontWeight: 700,
              letterSpacing: "0.18em",
              color: "var(--dash-gold-bright)",
            }}>
              AUREM
            </div>
            <div className="av2-section-label" style={{
              fontSize: 10, color: "var(--dash-text-faint)",
              letterSpacing: "0.15em", marginTop: 4,
              textTransform: "uppercase",
            }}>
              Developer Portal
            </div>
          </div>
        )}
        {/* iter 332b D-13 — collapse / expand toggle.
            Persisted to localStorage via the parent. */}
        <button data-testid="dev-sidebar-toggle"
                onClick={onToggle}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                title={collapsed ? "Expand" : "Collapse"}
                style={{
                  background: "transparent",
                  border: "1px solid var(--dash-divider)",
                  color: "var(--dash-text-muted)",
                  width: 28, height: 28, borderRadius: 6,
                  display: "inline-flex", alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  flexShrink: 0,
                  transition: "color 160ms ease, border-color 160ms ease",
                }}>
          {collapsed
            ? <ChevronRight size={14} />
            : <ChevronLeft size={14} />}
        </button>
      </div>
      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {DASH_NAV.map(n => {
          const active = loc.pathname === n.to;
          const Icon = n.icon;
          return (
            <Link key={n.to} to={n.to}
                  data-testid={n.testid}
                  className="av2-nav-item"
                  title={collapsed ? n.label : undefined}
                  style={{
                    display: "flex", alignItems: "center",
                    gap: 10,
                    padding: collapsed ? "10px 0" : "9px 10px",
                    justifyContent: collapsed ? "center" : "flex-start",
                    borderRadius: 8,
                    color: active
                      ? "var(--dash-orange)"
                      : "var(--dash-text-muted)",
                    background: active
                      ? "var(--dash-nav-active-bg)"
                      : "transparent",
                    borderLeft: active
                      ? "2px solid var(--dash-nav-active-bar)"
                      : "2px solid transparent",
                    fontSize: 13, fontWeight: active ? 500 : 400,
                    textDecoration: "none",
                    transition: "all 160ms ease",
                  }}>
              <Icon size={15} />
              {!collapsed && (
                <span className="av2-nav-label">{n.label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* iter 332b D-20 — Saved projects strip. Only renders when the
          sidebar is expanded; otherwise we'd waste vertical space. */}
      {!collapsed && (
        <div data-testid="dev-sidebar-projects"
             style={{ marginTop: 18, paddingTop: 14,
                      borderTop: "1px solid var(--dash-divider)" }}>
          <div className="av2-section-label"
               style={{ fontSize: 10, letterSpacing: "0.18em",
                        color: "var(--dash-text-faint)",
                        textTransform: "uppercase",
                        marginBottom: 8, padding: "0 10px",
                        display: "flex", justifyContent: "space-between" }}>
            <span>Saved projects</span>
            <span data-testid="dev-sidebar-projects-count">
              {projects.length}
            </span>
          </div>
          {projects.length === 0 ? (
            <div data-testid="dev-sidebar-projects-empty"
                 style={{ fontSize: 11, color: "var(--dash-text-faint)",
                          padding: "6px 10px", lineHeight: 1.5 }}>
              Save a build from the chat to pin it here.
            </div>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0,
                          display: "flex", flexDirection: "column", gap: 2,
                          maxHeight: 240, overflowY: "auto" }}>
              {projects.map(p => (
                <li key={p.project_id}>
                  <button data-testid={`dev-sidebar-project-${p.project_id}`}
                           onClick={() => navigate(
                             `/developers/dashboard?project=${encodeURIComponent(p.project_id)}`
                           )}
                           title={p.domain || ""}
                           style={{ width: "100%", textAlign: "left",
                                    background: loc.search.includes(p.project_id)
                                      ? "var(--dash-nav-active-bg)"
                                      : "transparent",
                                    border: "none",
                                    color: "var(--dash-text)",
                                    padding: "7px 10px", borderRadius: 6,
                                    fontSize: 12,
                                    fontFamily: "inherit",
                                    cursor: "pointer",
                                    display: "flex", flexDirection: "column",
                                    gap: 2 }}>
                    <span style={{ overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap" }}>
                      {p.title}
                    </span>
                    {p.domain && (
                      <span style={{ fontSize: 10,
                                      color: "var(--dash-text-faint)",
                                      fontFamily: "'JetBrains Mono', monospace" }}>
                        {p.domain}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {me && !collapsed && (
        <div className="av2-sidebar-footer"
              style={{
                marginTop: "auto", padding: 12,
                borderTop: "1px solid var(--dash-divider)",
                fontSize: 12, color: "var(--dash-text-muted)",
              }}>
          <div className="av2-user-meta">
            <div style={{ color: "var(--dash-text)", fontWeight: 500,
                           marginBottom: 2 }}>
              {me.name || me.email}
            </div>
            <div style={{ fontSize: 11, color: "var(--dash-text-faint)" }}>
              {me.email}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function DashboardShell({ children, requireAuth }) {
  const { me, loading } = useDevMe();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(
    () => localStorage.getItem("dev_theme") || "dark"
  );
  // iter 332b D-13 — collapsible sidebar, preference persisted.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem("dev_sidebar_collapsed") === "1"
  );
  // iter D-38 — mobile sidebar open/close. On <768px the sidebar is a
  // slide-in drawer toggled by the hamburger in the topbar.
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("dev_theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(
      "dev_sidebar_collapsed", sidebarCollapsed ? "1" : "0"
    );
  }, [sidebarCollapsed]);

  // iter D-38 — auto-close the mobile drawer on route change so links
  // navigate AND collapse the menu in one click.
  const loc = useLocation();
  useEffect(() => { setMobileSidebarOpen(false); }, [loc.pathname]);

  useEffect(() => {
    if (requireAuth && !loading && !me) {
      navigate("/developers/signup", { replace: true });
    }
  }, [requireAuth, loading, me, navigate]);

  function toggleTheme() {
    setTheme(prev => prev === "dark" ? "light" : "dark");
  }

  return (
    <div className="aurem-v2-root" data-testid="dev-shell"
         data-sidebar-collapsed={sidebarCollapsed ? "true" : "false"}
         style={{
           // iter 332b D-12 — Roman coin background image injected as a
           // CSS variable so dashboard-theme.css ::before can compose it
           // with the dark overlay. Public folder assets are served from
           // PUBLIC_URL at runtime, which keeps webpack's CSS-loader
           // happy (it was failing to resolve url("/img/...") at build).
           "--dev-bg-image": `url("${process.env.PUBLIC_URL || ""}/img/aurem-dev-bg.png")`,
         }}>
      <div className={`av2-shell${sidebarCollapsed ? " av2-shell--collapsed" : ""}${mobileSidebarOpen ? " av2-shell--mobile-open" : ""}`}>
        {/* iter D-38 — backdrop dims the page when the mobile drawer
            is open. Tap to dismiss. */}
        {mobileSidebarOpen && (
          <div className="av2-mobile-backdrop"
               data-testid="dev-mobile-backdrop"
               onClick={() => setMobileSidebarOpen(false)} />
        )}
        <DashboardSidebar me={me}
                          collapsed={sidebarCollapsed}
                          onToggle={() => setSidebarCollapsed(c => !c)} />
        <div className="av2-main">
          <DashboardTopbar me={me} theme={theme} toggleTheme={toggleTheme}
                            onMobileMenu={() => setMobileSidebarOpen(o => !o)}
                            mobileOpen={mobileSidebarOpen} />
          <div className="av2-content">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Public wrapper — picks the mode
// ────────────────────────────────────────────────────────────────
export default function DeveloperShell({ children, mode = "dashboard", requireAuth = false }) {
  if (mode === "landing") return <LandingShell>{children}</LandingShell>;
  return <DashboardShell requireAuth={requireAuth}>{children}</DashboardShell>;
}
