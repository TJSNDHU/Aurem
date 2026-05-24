/**
 * OrgSwitcher — iter 332b C-2
 *
 * Sidebar dropdown that lists the admin's orgs (from GET /api/orgs/me),
 * shows the active one + role, and lets them switch via POST /api/orgs/switch.
 *
 * Hidden entirely if the admin has 0 orgs (avoids visual noise for
 * single-tenant operations).
 *
 * Lives in AdminShell — pulls token from secureTokenStore.
 */
import React, { useEffect, useState } from "react";
import { BACKEND_URL } from "../lib/api";
import { getPlatformToken } from "../utils/secureTokenStore";
import { ChevronDown, Check, Building2 } from "lucide-react";

const ORANGE = "#FF6B00";

export default function OrgSwitcher() {
  const [orgs,    setOrgs]    = useState([]);
  const [active,  setActive]  = useState(null);
  const [open,    setOpen]    = useState(false);
  const [busy,    setBusy]    = useState(false);

  const authHeaders = () => {
    const tok = getPlatformToken();
    return tok ? { Authorization: `Bearer ${tok}`,
                   "Content-Type": "application/json" }
               : { "Content-Type": "application/json" };
  };

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/orgs/me`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => {
        if (d.ok && d.rows?.length) {
          setOrgs(d.rows);
          const initial = d.current_org_id
            ? d.rows.find(o => o.org_id === d.current_org_id)
            : d.rows[0];
          setActive(initial || d.rows[0]);
        }
      })
      .catch(() => { /* silent — sidebar just hides if request fails */ });
  }, []);

  const handleSwitch = async (org) => {
    if (!org || org.org_id === active?.org_id) {
      setOpen(false);
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/orgs/switch`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ org_id: org.org_id }),
      });
      const d = await res.json();
      if (res.ok && d.ok) {
        setActive(org);
      }
    } catch {
      /* silent */
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  if (orgs.length === 0) return null;

  return (
    <div data-testid="org-switcher"
          style={{ position: "relative", marginBottom: 14 }}>
      <button
        type="button"
        data-testid="org-switcher-btn"
        onClick={() => setOpen(v => !v)}
        disabled={busy}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 12px",
          background: "rgba(255,107,0,0.05)",
          border: "1px solid rgba(255,107,0,0.20)",
          borderRadius: 6, cursor: "pointer", color: "#f6f5f1",
          fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
        }}>
        <Building2 size={14} color={ORANGE} />
        <div style={{ flex: 1, textAlign: "left", overflow: "hidden",
                       textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <div style={{ color: "#f6f5f1", fontSize: 12 }}>
            {active?.name || "Select organization"}
          </div>
          <div style={{ color: "#888", fontSize: 9, letterSpacing: "0.15em",
                         textTransform: "uppercase", marginTop: 1 }}>
            {active?.role || "—"}
          </div>
        </div>
        <ChevronDown size={14} color="#666"
                      style={{
                        transform: open ? "rotate(180deg)" : "none",
                        transition: "transform 120ms ease",
                      }} />
      </button>
      {open && (
        <div data-testid="org-switcher-dropdown"
              style={{
                position: "absolute", left: 0, right: 0, top: "100%",
                marginTop: 4, zIndex: 90,
                background: "#0d0d0d",
                border: "1px solid rgba(255,107,0,0.25)",
                borderRadius: 6, padding: 4,
                maxHeight: 260, overflowY: "auto",
              }}>
          {orgs.map(o => (
            <button
              key={o.org_id}
              type="button"
              data-testid={`org-switcher-row-${o.org_id}`}
              onClick={() => handleSwitch(o)}
              style={{
                width: "100%", textAlign: "left",
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 10px", border: "none",
                background: o.org_id === active?.org_id
                  ? "rgba(255,107,0,0.10)" : "transparent",
                color: "#f6f5f1", cursor: "pointer", borderRadius: 4,
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
              }}>
              <div style={{ flex: 1 }}>
                <div>{o.name}</div>
                <div style={{ color: "#888", fontSize: 9,
                               letterSpacing: "0.15em",
                               textTransform: "uppercase", marginTop: 1 }}>
                  {o.role}
                </div>
              </div>
              {o.org_id === active?.org_id && (
                <Check size={14} color={ORANGE} />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
