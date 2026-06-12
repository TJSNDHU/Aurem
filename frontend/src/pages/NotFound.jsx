/**
 * NotFound — real 404 page (iter D-82c P2-8).
 * Replaces the old catch-all redirect-to-"/" soft-404 so mistyped/dead URLs
 * surface honestly instead of silently bouncing to the landing page.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div
      data-testid="not-found-page"
      style={{
        minHeight: "100vh", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", gap: 18,
        background: "#0A0A0F", color: "#E8E4DE", textAlign: "center", padding: 24,
      }}
    >
      <Compass style={{ width: 44, height: 44, color: "#D4A373" }} />
      <div style={{ fontSize: 72, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1 }}>404</div>
      <p style={{ fontSize: 16, color: "#9A9590", maxWidth: 420, margin: 0 }}>
        This page doesn’t exist or has moved. Let’s get you back on track.
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <Link to="/" data-testid="nf-home-link" style={btn(true)}>Go home</Link>
        <Link to="/my" data-testid="nf-portal-link" style={btn(false)}>My dashboard</Link>
      </div>
    </div>
  );
}

const btn = (primary) => ({
  padding: "10px 22px", borderRadius: 999, textDecoration: "none", fontSize: 14, fontWeight: 600,
  color: primary ? "#0A0A0F" : "#E8E4DE",
  background: primary ? "#D4A373" : "transparent",
  border: `1px solid ${primary ? "#D4A373" : "rgba(212,163,115,0.4)"}`,
});
