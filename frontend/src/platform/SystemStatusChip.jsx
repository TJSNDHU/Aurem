/**
 * SystemStatusChip — floating top-right live trust chip.
 * iter 280: combines BuildBadge + CorePulseDot + uptime into a single
 * always-visible component. Mounts on every authenticated page via App.js.
 *
 * States:
 *   🟢 green  — all pillars healthy
 *   🟡 amber  — some pillar degraded
 *   🔴 red    — at least one pillar down
 *   ⚪ gray   — loading
 *
 * Shows: live dot + short SHA + uptime  (e.g., "● git-3582770 · 42m")
 * Hover: tooltip with pillar counts + full version + click-to-jump to Pillars Map
 */
import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL || "";

function readToken() {
  return (
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    ""
  );
}

const STATE_META = {
  healthy:  { color: "#22C55E", glow: "0 0 8px rgba(34,197,94,0.6)",  label: "All systems operational" },
  degraded: { color: "#F59E0B", glow: "0 0 8px rgba(245,158,11,0.6)", label: "Some pillars degraded" },
  down:     { color: "#EF4444", glow: "0 0 10px rgba(239,68,68,0.7)", label: "Pillar down" },
  loading:  { color: "#6B7280", glow: "none",                         label: "Loading…" },
  unknown:  { color: "#6B7280", glow: "none",                         label: "No data" },
  deploy_ok:{ color: "#22C55E", glow: "0 0 10px rgba(34,197,94,0.7)", label: "Deploy verified · build live" },
};

// iter 280.1 — first-60s Deploy Health Mini-Mode:
// during a fresh rollout, legacy broken inter-pillar wires can initially
// paint the dot red before workers settle. To give operators an
// unambiguous "deploy landed" signal, we force green + "DEPLOY OK" label
// while uptime < DEPLOY_GRACE_SECONDS, as long as /api/health came back
// 200 with a build SHA. After the grace window, real pillar state takes
// over.
const DEPLOY_GRACE_SECONDS = 60;

// Admin email whitelist — kept in sync with backend `utils/admin_guard.py`.
// SystemStatusChip is an admin-only observability widget. Default-DENY
// rendering on every page; only show when BOTH conditions are met:
//   1. URL path starts with `/admin/` (explicit admin surface), AND
//   2. A non-empty token exists in storage AND its `email` claim is in
//      this whitelist OR the token has an `is_admin`/`is_super_admin`
//      claim, OR `role` is "admin"/"super_admin".
// This kills the entire class of "grey/offline chip leaked onto customer
// pages" bugs forever — adding any new public route requires zero
// changes to this file. iter 280.11
const ADMIN_EMAIL_WHITELIST = [
  "admin@aurem.live",
  "teji.ss1986@gmail.com",
];

function decodeJwtPayload(token) {
  try {
    const part = (token || "").split(".")[1];
    if (!part) return null;
    // base64url → base64 → utf8 JSON
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "===".slice((b64.length + 3) % 4);
    return JSON.parse(atob(padded));
  } catch (_) {
    return null;
  }
}

// iter 322ai — DOGFOOD HARDENING: removed the email whitelist fallback.
// Admin status now derives EXCLUSIVELY from JWT claims (is_admin /
// is_super_admin / role). Email is never a source of truth for routing
// or admin-vs-customer decisions anywhere in the frontend.
function isAdminToken(token) {
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload) return false;
  if (payload.is_admin === true || payload.is_super_admin === true) return true;
  const role = String(payload.role || "").toLowerCase();
  return role === "admin" || role === "super_admin";
}

export default function SystemStatusChip() {
  const [version, setVersion] = useState(null);
  const [uptime, setUptime] = useState(0);
  const [pulse, setPulse] = useState({ status: "loading", counts: { healthy: 0, degraded: 0, down: 0 } });
  const [drift, setDrift] = useState(null); // iter 280.2 — deploy drift state
  const navigate = useNavigate();
  const location = useLocation();

  // ─── DEFAULT-DENY rendering policy (iter 280.11) ─────────────────
  // The chip renders ONLY on explicit admin URLs WITH a valid admin
  // token. Any other surface (customer, marketing, public, onboarding,
  // login, etc.) implicitly skips the chip — no maintenance required
  // when adding new public routes.
  const onAdminRoute = location.pathname.startsWith("/admin/")
                    || location.pathname === "/admin";
  const adminAuthed = isAdminToken(readToken());
  const shouldRender = onAdminRoute && adminAuthed;

  useEffect(() => {
    if (!shouldRender) return undefined;
    let cancel = false;
    const token = readToken();
    // Hard guard: if we have no token, skip every authenticated poll.
    // Public /api/health is still safe to call. (iter 280.4 — kills the
    // 401 "Missing token" client_error storm seen on /admin/login.)
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    const pollHealth = async () => {
      try {
        const r = await fetch(`${API}/api/health`, { cache: "no-store" });
        const d = await r.json();
        if (cancel) return;
        setVersion(d.v);
        setUptime(d.uptime_seconds || 0);
      } catch {
        /* ignore */
      }
    };

    const pollPulse = async () => {
      if (!token) return; // skip — no auth, would 401-storm
      try {
        const r = await fetch(`${API}/api/admin/pillars-map/overview`, {
          headers,
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (cancel) return;
        const pillars = d.pillars || [];
        let healthy = 0, degraded = 0, down = 0;
        for (const p of pillars) {
          const s = String(p.status || p.overall || "").toLowerCase();
          if (s.includes("healthy") || s.includes("ok") || s === "green") healthy++;
          else if (s.includes("degrad") || s.includes("warn") || s === "amber") degraded++;
          else down++;
        }
        let status = "unknown";
        if (down > 0) status = "down";
        else if (degraded > 0) status = "degraded";
        else if (healthy > 0) status = "healthy";
        setPulse({ status, counts: { healthy, degraded, down } });
      } catch {
        if (!cancel) setPulse({ status: "unknown", counts: { healthy: 0, degraded: 0, down: 0 } });
      }
    };

    const pollDrift = async () => {
      if (!token) return; // skip — no auth, would 401-storm
      try {
        const r = await fetch(`${API}/api/admin/deploy-drift`, {
          headers,
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (cancel) return;
        setDrift({
          needsDeploy: !!d.needs_deploy,
          pendingCommits: d.pending_commits || 0,
          oldestSec: d.oldest_drift_seconds || 0,
          prodSha: d.prod_sha || "",
          previewSha: d.preview_sha || "",
          prodReachable: !!d.prod_reachable,
          inSync: !!d.in_sync,
          recent: d.recent_commits || [],
        });
      } catch {
        if (!cancel) setDrift(null);
      }
    };

    pollHealth();
    pollPulse();
    pollDrift();
    const hid = setInterval(pollHealth, 30_000);
    const pid = setInterval(pollPulse, 25_000);
    const did = setInterval(pollDrift, 60_000);
    // 1s local tick — increments uptime between polls so the deploy
    // grace window transitions cleanly (no "frozen at 5s for 30s" UX).
    const tick = setInterval(() => {
      if (!cancel) setUptime((u) => (u > 0 ? u + 1 : u));
    }, 1000);
    return () => {
      cancel = true;
      clearInterval(hid);
      clearInterval(pid);
      clearInterval(did);
      clearInterval(tick);
    };
  }, [shouldRender]);

  if (!shouldRender) return null;

  // Deploy Health Mini-Mode: first 60s after a fresh build flip, force
  // green so operators get a clean "deploy landed" confirmation signal.
  const inDeployGrace = version && uptime > 0 && uptime < DEPLOY_GRACE_SECONDS;
  // Drift override: if pending commits are unpushed to prod beyond threshold,
  // escalate the chip to amber regardless of current pillar pulse so the
  // operator is nudged to deploy.
  const driftActive = drift && drift.needsDeploy && !inDeployGrace;
  const effectiveStatus = inDeployGrace
    ? "deploy_ok"
    : driftActive
      ? "degraded"
      : pulse.status;
  const meta = STATE_META[effectiveStatus] || STATE_META.loading;
  const uptimeMin = Math.round(uptime / 60);
  const fresh = uptime < 600; // fresh deploy indicator (≤10 min)

  const driftMin = drift ? Math.round((drift.oldestSec || 0) / 60) : 0;
  const driftTooltip = drift
    ? `\nprod: ${drift.prodSha || "?"} · preview: ${drift.previewSha || "?"}\n` +
      (drift.inSync
        ? "In sync — aurem.live serves latest commit"
        : `${drift.pendingCommits} commit(s) unpushed · oldest ${driftMin}m behind`)
    : "";

  const tooltip = inDeployGrace
    ? `${meta.label}  ·  build ${version}\nuptime ${Math.round(uptime)}s\nReal pillar state resumes in ${Math.max(0, DEPLOY_GRACE_SECONDS - Math.round(uptime))}s`
    : `${meta.label}  ·  ${pulse.counts.healthy}✓ ${pulse.counts.degraded}⚠ ${pulse.counts.down}✗\n` +
      `Build: ${version || "?"}  ·  uptime ${uptimeMin}m` +
      driftTooltip +
      `\nClick to open Pillars Map`;

  const onChipClick = () => {
    // If drift active, send operator to the drift-aware admin page first.
    if (driftActive) {
      navigate("/admin/pillars-map?focus=deploy-drift");
      return;
    }
    navigate("/admin/pillars-map");
  };

  return (
    <button
      type="button"
      data-testid="system-status-chip"
      data-drift-active={driftActive ? "true" : "false"}
      onClick={onChipClick}
      title={tooltip}
      style={{
        position: "fixed",
        top: 14,
        right: 14,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px 6px 10px",
        borderRadius: 20,
        background: "rgba(10,10,20,0.78)",
        backdropFilter: "blur(14px) saturate(160%)",
        WebkitBackdropFilter: "blur(14px) saturate(160%)",
        border: `1px solid ${meta.color}44`,
        boxShadow: `0 4px 16px rgba(0,0,0,0.35), ${meta.glow}`,
        cursor: "pointer",
        fontFamily: "'Jost', 'Montserrat', sans-serif",
        fontSize: 11,
        color: "#E8E0D0",
        letterSpacing: "0.3px",
        transition: "transform 120ms ease, box-shadow 160ms ease",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-1px)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; }}
    >
      {/* Live pulse dot */}
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: 50,
          background: meta.color,
          boxShadow: `0 0 6px ${meta.color}`,
          animation:
            pulse.status === "down"
              ? "chipPulse 1.1s ease-in-out infinite"
              : pulse.status === "degraded"
                ? "chipPulse 2.2s ease-in-out infinite"
                : "none",
          flexShrink: 0,
        }}
      />
      {/* Version */}
      <span
        style={{
          fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
          fontSize: 10,
          color: "#9CA3AF",
          whiteSpace: "nowrap",
        }}
      >
        {version || "loading"}
      </span>
      {/* Uptime */}
      <span style={{ color: "#6B7280", fontSize: 10, whiteSpace: "nowrap" }}>
        · {uptimeMin}m
      </span>
      {/* Fresh deploy badge — "DEPLOY OK" during 60s grace, else "FRESH" for ≤10min */}
      {fresh && uptime > 0 ? (
        <span
          data-testid={inDeployGrace ? "chip-deploy-ok" : "chip-fresh"}
          style={{
            padding: "1px 6px",
            fontSize: 8,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            background: "rgba(34,197,94,0.15)",
            color: "#86EFAC",
            borderRadius: 4,
            border: "1px solid rgba(34,197,94,0.35)",
          }}
        >
          {inDeployGrace ? "deploy ok" : "fresh"}
        </span>
      ) : null}
      {/* Drift badge — shown only when commits are pending beyond threshold */}
      {driftActive ? (
        <span
          data-testid="chip-deploy-drift"
          style={{
            padding: "1px 6px",
            fontSize: 8,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            background: "rgba(245,158,11,0.18)",
            color: "#FCD34D",
            borderRadius: 4,
            border: "1px solid rgba(245,158,11,0.45)",
            animation: "chipPulse 2.2s ease-in-out infinite",
          }}
        >
          deploy {drift.pendingCommits}↑ {driftMin}m
        </span>
      ) : null}
      <style>{`
        @keyframes chipPulse {
          0%,100% { transform: scale(1);   opacity: 1; }
          50%     { transform: scale(1.35); opacity: 0.65; }
        }
      `}</style>
    </button>
  );
}
